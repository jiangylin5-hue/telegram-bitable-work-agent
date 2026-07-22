from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4
import warnings

import pytest
from starlette.exceptions import StarletteDeprecationWarning

warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)

from fastapi.testclient import TestClient

import app.api.routes.stage08_collaboration as collaboration_route
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.runtime.stage08_collaboration_contracts import (
    AssistantQuerySafeCitation,
    AssistantQuerySafeView,
    _command_snapshot,
)
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


PATH = "/api/stage08/assistant/query"
INVALID_DETAIL = {
    "detail": {
        "code": "stage08_collaboration_request_invalid",
        "message": "stage08_collaboration_request_invalid",
    }
}


def _fixture() -> SimpleNamespace:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="e4-owner", role="owner")
    workspace = create_workspace(
        uow,
        name="E4 API",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    table = create_table(
        uow,
        base.id,
        name="Customers",
        key="customers",
        actor=actor,
    )
    create_field(
        uow,
        table.id,
        name="Name",
        key="name",
        field_type="text",
        actor=actor,
    )
    record = create_record(
        uow,
        table.id,
        values={"name": "E4 customer"},
        actor=actor,
    )
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Customers",
        view_type="grid",
        config={"fields": ["name"]},
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="E4 employee",
        description="strict assistant API",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["query", "summarize", "draft_update"],
        actor=actor,
    )
    return SimpleNamespace(
        uow=uow,
        actor=actor,
        workspace=workspace,
        base=base,
        table=table,
        record=record,
        view=view,
        employee=employee,
    )


def _client(fixture: SimpleNamespace, user_id: str | None = "e4-owner") -> TestClient:
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: fixture.uow
    client = TestClient(app, raise_server_exceptions=False)
    if user_id is not None:
        client.headers["X-Stage06-User-Id"] = user_id
    return client


def _payload(fixture: SimpleNamespace, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "workspace_id": str(fixture.workspace.id),
        "employee_id": str(fixture.employee.id),
        "intent": "general_advice",
        "query": "下一步应该怎么做？",
        "requested_action": "read_only",
        "target_record_id": None,
        "idempotency_key": "e4-query-1",
    }
    payload.update(overrides)
    return payload


def _degraded() -> AssistantQuerySafeView:
    return AssistantQuerySafeView(
        status="degraded",
        answer=None,
        citations=(),
        degradation_codes=("analysis_unavailable",),
        draft_id=None,
    )


def test_assistant_query_is_the_only_public_route_on_its_router() -> None:
    assert [
        (route.path, route.methods)
        for route in collaboration_route.router.routes
    ] == [(PATH, {"POST"})]


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "scope",
        "field_filters",
        "provider",
        "budget",
        "tools",
        "ticket_status",
        "draft_values",
        "audit",
    ],
)
def test_assistant_query_rejects_client_control_fields_without_echo(
    monkeypatch: pytest.MonkeyPatch,
    forbidden_field: str,
) -> None:
    fixture = _fixture()
    sentinel = "E4_PRIVATE_SENTINEL"
    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", lambda *args, **kwargs: _degraded())

    with _client(fixture) as client:
        response = client.post(
            PATH,
            json={**_payload(fixture), forbidden_field: {"raw": sentinel}},
        )

    assert response.status_code == 422
    assert response.json() == INVALID_DETAIL
    assert sentinel.casefold() not in response.text.casefold()
    assert forbidden_field.casefold() not in response.text.casefold()
    assert fixture.uow.idempotency_records == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workspace_id", "not-a-uuid"),
        ("employee_id", True),
        ("query", ""),
        ("idempotency_key", "bad\nkey"),
        ("requested_action", "send_telegram"),
    ],
)
def test_assistant_query_rejects_invalid_body_as_redacted_422(
    field: str,
    value: object,
) -> None:
    fixture = _fixture()

    with _client(fixture) as client:
        response = client.post(PATH, json=_payload(fixture, **{field: value}))

    assert response.status_code == 422
    assert response.json() == INVALID_DETAIL
    assert "not-a-uuid" not in response.text
    assert "send_telegram" not in response.text


def test_assistant_query_requires_verified_identity() -> None:
    fixture = _fixture()

    with _client(fixture, None) as client:
        response = client.post(PATH, json=_payload(fixture))

    assert response.status_code == 401
    assert fixture.uow.idempotency_records == []


def test_assistant_query_requires_current_invoke_scope() -> None:
    fixture = _fixture()
    fixture.uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=fixture.workspace.id,
            user_id="e4-manager",
            role="manager",
            status="active",
            version=1,
        )
    )

    with _client(fixture, "e4-manager") as client:
        response = client.post(PATH, json=_payload(fixture))

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "stage08_collaboration_scope_denied"
    assert fixture.uow.idempotency_records == []


def test_assistant_query_default_provider_returns_safe_degraded_terminal() -> None:
    fixture = _fixture()

    with _client(fixture) as client:
        response = client.post(PATH, json=_payload(fixture))

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "answer": None,
        "citations": [],
        "degradation_codes": ["analysis_unavailable"],
        "draft_id": None,
    }
    assert len(fixture.uow.agent_runs) == 1
    assert len(fixture.uow.idempotency_records) == 1


def test_assistant_query_derives_command_server_side_and_returns_only_safe_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    captured: dict[str, object] = {}

    def run(uow, command, actor, *, now):
        del uow, now
        captured["command"] = _command_snapshot(command)
        captured["actor"] = actor
        return AssistantQuerySafeView(
            status="completed",
            answer="执行已分析",
            citations=(AssistantQuerySafeCitation(ordinal=1, label="general_advice"),),
            degradation_codes=(),
            draft_id=None,
        )

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)

    with _client(fixture) as client:
        response = client.post(PATH, json=_payload(fixture))

    assert response.status_code == 200
    assert set(response.json()) == {
        "status",
        "answer",
        "citations",
        "degradation_codes",
        "draft_id",
    }
    assert response.json()["answer"] == "执行已分析"
    command = captured["command"]
    assert command.workspace_id == fixture.workspace.id
    assert command.employee_id == fixture.employee.id
    assert command.actor_user_id == fixture.actor.actor_id
    assert command.query == "下一步应该怎么做？"
    assert captured["actor"] == fixture.actor


def test_assistant_query_denies_inactive_or_unassigned_employee(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", lambda *args, **kwargs: _degraded())

    fixture.employee.status = "paused"
    with _client(fixture) as client:
        inactive = client.post(PATH, json=_payload(fixture))
    fixture.employee.status = "active"
    fixture.employee.access_mode = "assigned"
    with _client(fixture) as client:
        unassigned = client.post(PATH, json=_payload(fixture))

    assert inactive.status_code == 403
    assert unassigned.status_code == 403
    assert fixture.uow.idempotency_records == []


def test_assistant_query_maps_absent_employee_and_target_to_non_disclosing_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", lambda *args, **kwargs: _degraded())

    with _client(fixture) as client:
        missing_employee = client.post(
            PATH,
            json=_payload(fixture, employee_id=str(uuid4())),
        )
        missing_target = client.post(
            PATH,
            json=_payload(fixture, target_record_id=str(uuid4())),
        )

    assert missing_employee.status_code == 404
    assert missing_target.status_code == 404
    assert "employee_id" not in missing_employee.text
    assert "target_record_id" not in missing_target.text


def test_assistant_query_revalidates_target_readability_before_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    called = False

    def run(*args, **kwargs):
        nonlocal called
        called = True
        return _degraded()

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)
    fixture.employee.accessible_tables = []

    with _client(fixture) as client:
        response = client.post(
            PATH,
            json=_payload(fixture, target_record_id=str(fixture.record.id)),
        )

    assert response.status_code == 403
    assert called is False
    assert fixture.uow.idempotency_records == []


def test_assistant_query_replay_is_hash_only_stable_and_rechecks_current_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    calls = 0

    def run(*args, **kwargs):
        nonlocal calls
        calls += 1
        return AssistantQuerySafeView(
            status="completed",
            answer="先核对当前记录，再创建下一步行动。",
            citations=(
                AssistantQuerySafeCitation(
                    ordinal=1,
                    label="general_advice",
                ),
            ),
            degradation_codes=(),
            draft_id=None,
        )

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)
    payload = _payload(fixture)

    with _client(fixture) as client:
        first = client.post(PATH, json=payload)
        replay = client.post(PATH, json=payload)
        conflict = client.post(PATH, json={**payload, "query": "不同语义"})
        fixture.employee.status = "paused"
        revoked = client.post(PATH, json=payload)

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    assert revoked.status_code == 403
    assert calls == 1
    assert len(fixture.uow.idempotency_records) == 1
    record = fixture.uow.idempotency_records[0]
    assert record.response_ref == {
        "version": "stage08-assistant-query-replay.v1",
        "status": "completed",
        "answer": "先核对当前记录，再创建下一步行动。",
        "citations": [{"ordinal": 1, "label": "general_advice"}],
        "degradation_codes": [],
        "draft_id": None,
    }
    replay_projection = json.dumps(record.response_ref, ensure_ascii=False)
    assert str(fixture.workspace.id) not in replay_projection
    assert str(fixture.employee.id) not in replay_projection
    assert str(fixture.record.id) not in replay_projection
    assert "下一步应该怎么做" not in record.request_fingerprint
    assert "下一步应该怎么做" not in record.trace_id
    assert "下一步应该怎么做" not in replay_projection


@pytest.mark.parametrize(
    "corruption",
    [
        "unknown_field",
        "wrong_version",
        "missing_answer",
        "wrong_citation_type",
        "unknown_citation_label",
        "wrong_degradation_type",
    ],
)
def test_assistant_query_rejects_forged_replay_projection_as_409(
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
) -> None:
    fixture = _fixture()
    calls = 0

    def run(*args, **kwargs):
        nonlocal calls
        calls += 1
        return AssistantQuerySafeView(
            status="completed",
            answer="严格安全回答",
            citations=(
                AssistantQuerySafeCitation(
                    ordinal=1,
                    label="general_advice",
                ),
            ),
            degradation_codes=(),
            draft_id=None,
        )

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)

    with _client(fixture) as client:
        first = client.post(PATH, json=_payload(fixture))
        projection = fixture.uow.idempotency_records[0].response_ref
        assert isinstance(projection, dict)
        if corruption == "unknown_field":
            projection["private_material"] = "FORGED_PRIVATE_SENTINEL"
        elif corruption == "wrong_version":
            projection["version"] = "stage08-assistant-query-replay.v0"
        elif corruption == "missing_answer":
            projection.pop("answer")
        elif corruption == "wrong_citation_type":
            projection["citations"] = [{"ordinal": True, "label": "general_advice"}]
        elif corruption == "unknown_citation_label":
            projection["citations"] = [{"ordinal": 1, "label": "private_record"}]
        else:
            projection["degradation_codes"] = "internal_failure"
        replay = client.post(PATH, json=_payload(fixture))

    assert first.status_code == 200
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "stage08_collaboration_replay_invalid"
    assert "FORGED_PRIVATE_SENTINEL" not in replay.text
    assert calls == 1


def test_assistant_query_rejects_forged_safe_view_and_releases_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    sentinel = "FORGED_PRIVATE_QUERY"
    forged = AssistantQuerySafeView.model_construct(
        status="degraded",
        answer=None,
        citations=(),
        degradation_codes=("analysis_unavailable",),
        draft_id=None,
    )
    object.__getattribute__(forged, "__dict__")["query"] = sentinel
    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", lambda *args, **kwargs: forged)

    with _client(fixture) as client:
        response = client.post(PATH, json=_payload(fixture))

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "stage08_collaboration_internal_failure"
    assert sentinel not in response.text
    assert fixture.uow.idempotency_records == []


def test_assistant_query_rolls_back_unexpected_service_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()

    class _SessionSpy:
        def __init__(self) -> None:
            self.flush_count = 0
            self.commit_count = 0
            self.rollback_count = 0

        def flush(self) -> None:
            self.flush_count += 1

        def commit(self) -> None:
            self.commit_count += 1

        def rollback(self) -> None:
            self.rollback_count += 1

    session = _SessionSpy()
    fixture.uow.session = session

    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_SERVICE_FAILURE")

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", fail)

    with _client(fixture) as client:
        response = client.post(PATH, json=_payload(fixture))

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "stage08_collaboration_internal_failure"
    assert "PRIVATE_SERVICE_FAILURE" not in response.text
    assert session.flush_count == 1
    assert session.commit_count == 0
    assert session.rollback_count == 1
