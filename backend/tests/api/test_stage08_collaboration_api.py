from __future__ import annotations

import json
from dataclasses import replace
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
from app.agents.stage06_skills import get_stage06_skill_manifest
from app.schemas.stage08_collaboration import AssistantQueryRequest
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_identity import Stage06RequestIdentity
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
STREAM_PATH = "/api/stage08/assistant/query-stream"
SKILLS_PATH = "/api/stage08/assistant/skills"
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


def _skills_params(fixture: SimpleNamespace, **overrides: object) -> dict[str, object]:
    params: dict[str, object] = {
        "workspace_id": str(fixture.workspace.id),
        "employee_id": str(fixture.employee.id),
    }
    params.update(overrides)
    return params


def test_assistant_skills_catalog_is_safe_and_server_derived() -> None:
    fixture = _fixture()

    with _client(fixture) as client:
        response = client.get(SKILLS_PATH, params=_skills_params(fixture))

    assert response.status_code == 200
    assert response.json() == {
        "manifest_version": "stage06-larksuite-skills-v1",
        "default_selection": "auto",
        "skills": [
            {
                "skill_id": "platform-base",
                "label": "查表问答",
                "description": "基于已授权表格、视图与记录回答问题",
                "enabled": True,
                "disabled_reason": None,
                "supported_intents": ["business_fact", "mixed"],
                "supported_actions": ["read_only"],
                "confirmation_policy": "read_only",
            },
            {
                "skill_id": "platform-tabular-analysis",
                "label": "汇总分析",
                "description": "基于已授权表格与视图整理结论",
                "enabled": True,
                "disabled_reason": None,
                "supported_intents": ["business_fact", "mixed"],
                "supported_actions": ["read_only"],
                "confirmation_policy": "read_only",
            },
            {
                "skill_id": "platform-task",
                "label": "待办梳理",
                "description": "基于已授权记录梳理待办与后续行动",
                "enabled": True,
                "disabled_reason": None,
                "supported_intents": ["business_fact", "mixed"],
                "supported_actions": ["read_only"],
                "confirmation_policy": "read_only",
            },
            {
                "skill_id": "platform-telegram-im",
                "label": "群聊上下文",
                "description": "基于当前受控群聊上下文整理结论",
                "enabled": False,
                "disabled_reason": "chat_scope_unavailable",
                "supported_intents": ["mixed"],
                "supported_actions": ["read_only"],
                "confirmation_policy": "read_only",
            },
        ],
    }
    assert "trigger" not in response.text
    assert str(fixture.table.id) not in response.text


def test_assistant_skills_catalog_rejects_invalid_or_inactive_scope_at_redacted_boundary() -> None:
    fixture = _fixture()
    fixture.employee.status = "paused"

    with _client(fixture) as client:
        inactive = client.get(SKILLS_PATH, params=_skills_params(fixture))
        malformed = client.get(
            SKILLS_PATH,
            params=_skills_params(fixture, workspace_id="not-a-uuid"),
        )

    assert inactive.status_code == 403
    assert inactive.json()["detail"] == {
        "code": "stage08_collaboration_scope_denied",
        "message": "stage08_collaboration_scope_denied",
    }
    assert malformed.status_code == 422
    assert malformed.json() == INVALID_DETAIL
    assert "not-a-uuid" not in malformed.text


@pytest.mark.parametrize("scope_drift", ["workspace", "base", "eligibility", "malformed"])
def test_assistant_skills_catalog_rejects_each_current_scope_drift(
    scope_drift: str,
) -> None:
    fixture = _fixture()
    if scope_drift == "workspace":
        fixture.workspace.status = "paused"
    elif scope_drift == "base":
        fixture.base.status = "archived"
    elif scope_drift == "eligibility":
        fixture.employee.access_mode = "assigned"
    else:
        fixture.employee.accessible_tables = ["not-a-uuid"]

    with _client(fixture) as client:
        response = client.get(SKILLS_PATH, params=_skills_params(fixture))

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "stage08_collaboration_scope_denied",
        "message": "stage08_collaboration_scope_denied",
    }
    assert "stage09_skill_catalog_scope_denied" not in response.text


def _degraded() -> AssistantQuerySafeView:
    return AssistantQuerySafeView(
        status="degraded",
        answer=None,
        citations=(),
        degradation_codes=("analysis_unavailable",),
        draft_id=None,
    )


def _parse_test_sse(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(
            line[5:].lstrip()
            for line in block.splitlines()
            if line.startswith("data:")
        )
        if data:
            parsed = json.loads(data)
            assert isinstance(parsed, dict)
            events.append(parsed)
    return events


def test_assistant_query_router_exposes_catalog_sync_and_stream_routes() -> None:
    assert [
        (route.path, route.methods)
        for route in collaboration_route.router.routes
    ] == [
        (SKILLS_PATH, {"GET"}),
        (PATH, {"POST"}),
        (STREAM_PATH, {"POST"}),
    ]


def test_assistant_query_stream_emits_monotonic_safe_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    answer = "Review the permitted context. Then confirm the next controlled action."
    monkeypatch.setattr(
        collaboration_route,
        "run_stage08_collaboration",
        lambda *args, **kwargs: AssistantQuerySafeView(
            status="completed",
            answer=answer,
            citations=(
                AssistantQuerySafeCitation(
                    ordinal=1,
                    label="general_advice",
                ),
            ),
            degradation_codes=(),
            draft_id=None,
        ),
    )

    with _client(fixture) as client:
        response = client.post(STREAM_PATH, json=_payload(fixture))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"
    events = _parse_test_sse(response.text)
    assert [event["event"] for event in events] == [
        "status",
        "status",
        "answer_delta",
        "result",
        "status",
        "done",
    ]
    assert [event["sequence"] for event in events] == list(
        range(1, len(events) + 1)
    )
    assert len({event["request_id"] for event in events}) == 1
    assert [
        event["phase"] for event in events if event["event"] == "status"
    ] == ["authorizing", "analysing", "completed"]
    assert "".join(
        str(event["text"])
        for event in events
        if event["event"] == "answer_delta"
    ) == events[-3]["safe_view"]["answer"]
    assert events[-3]["safe_view"] == {
        "status": "completed",
        "answer": answer,
        "citations": [{"ordinal": 1, "label": "general_advice"}],
        "degradation_codes": [],
        "draft_id": None,
        "skill": {
            "skill_id": "platform-base",
            "label": "查表问答",
            "manifest_version": "stage06-larksuite-skills-v1",
            "selection_mode": "auto",
        },
    }


def test_assistant_query_stream_does_not_emit_phase_before_its_runtime_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    runtime_calls = 0

    def run(*args, **kwargs):
        nonlocal runtime_calls
        runtime_calls += 1
        return AssistantQuerySafeView(
            status="completed",
            answer="Safe answer.",
            citations=(),
            degradation_codes=(),
            draft_id=None,
        )

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)
    events = collaboration_route.iter_assistant_stream_events(
        AssistantQueryRequest.model_validate(_payload(fixture)),
        Stage06RequestIdentity(
            user_id=fixture.actor.actor_id,
            source="development_header",
        ),
        fixture.uow,
        "req-boundary",
    )

    authorizing = next(events)
    assert authorizing.phase == "authorizing"
    assert runtime_calls == 0
    analysing = next(events)
    assert analysing.phase == "analysing"
    assert runtime_calls == 0
    answer = next(events)
    assert answer.event == "answer_delta"
    assert runtime_calls == 1


def test_assistant_query_stream_draft_degradation_never_claims_draft_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    fixture.employee.field_policy = {"writable_fields": ["name"]}
    monkeypatch.setattr(
        collaboration_route,
        "run_stage08_collaboration",
        lambda *args, **kwargs: _degraded(),
    )

    with _client(fixture) as client:
        response = client.post(
            STREAM_PATH,
            json=_payload(
                fixture,
                requested_action="draft_update",
                target_record_id=str(fixture.record.id),
            ),
        )

    assert response.status_code == 200
    events = _parse_test_sse(response.text)
    assert [
        event["phase"] for event in events if event["event"] == "status"
    ] == ["authorizing", "analysing", "completed"]


def test_assistant_query_stream_close_after_prepare_releases_reservation_for_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    monkeypatch.setattr(
        collaboration_route,
        "run_stage08_collaboration",
        lambda *args, **kwargs: AssistantQuerySafeView(
            status="completed",
            answer="Safe answer.",
            citations=(),
            degradation_codes=(),
            draft_id=None,
        ),
    )
    request = AssistantQueryRequest.model_validate(_payload(fixture))
    identity = Stage06RequestIdentity(
        user_id=fixture.actor.actor_id,
        source="development_header",
    )
    events = collaboration_route.iter_assistant_stream_events(
        request,
        identity,
        fixture.uow,
        "req-close-direct",
    )

    assert next(events).phase == "authorizing"
    assert next(events).phase == "analysing"
    assert len(fixture.uow.idempotency_records) == 1
    assert fixture.uow.idempotency_records[0].status == "in_progress"
    events.close()

    assert fixture.uow.idempotency_records == []
    retry_events = list(
        collaboration_route.iter_assistant_stream_events(
            request,
            identity,
            fixture.uow,
            "req-close-retry",
        )
    )
    assert retry_events[-1].event == "done"
    assert len(fixture.uow.idempotency_records) == 1
    assert fixture.uow.idempotency_records[0].status == "completed"


def test_sse_encoder_close_propagates_to_prepared_event_generator() -> None:
    fixture = _fixture()
    events = collaboration_route.iter_assistant_stream_events(
        AssistantQueryRequest.model_validate(_payload(fixture)),
        Stage06RequestIdentity(
            user_id=fixture.actor.actor_id,
            source="development_header",
        ),
        fixture.uow,
        "req-close-encoded",
    )
    encoded = collaboration_route.encode_sse_events(events)

    assert b'"phase":"authorizing"' in next(encoded)
    assert b'"phase":"analysing"' in next(encoded)
    assert len(fixture.uow.idempotency_records) == 1
    encoded.close()

    assert fixture.uow.idempotency_records == []


def test_assistant_query_stream_close_rolls_back_sql_session_once() -> None:
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
    events = collaboration_route.iter_assistant_stream_events(
        AssistantQueryRequest.model_validate(_payload(fixture)),
        Stage06RequestIdentity(
            user_id=fixture.actor.actor_id,
            source="development_header",
        ),
        fixture.uow,
        "req-close-sql",
    )

    assert next(events).phase == "authorizing"
    assert next(events).phase == "analysing"
    events.close()

    assert session.flush_count == 1
    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_assistant_query_stream_splits_only_validated_answer_at_safe_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    answer = ("A" * 400) + ". " + ("B" * 300)
    monkeypatch.setattr(
        collaboration_route,
        "run_stage08_collaboration",
        lambda *args, **kwargs: AssistantQuerySafeView(
            status="completed",
            answer=answer,
            citations=(),
            degradation_codes=(),
            draft_id=None,
        ),
    )

    with _client(fixture) as client:
        response = client.post(STREAM_PATH, json=_payload(fixture))

    assert response.status_code == 200
    events = _parse_test_sse(response.text)
    chunks = [
        str(event["text"])
        for event in events
        if event["event"] == "answer_delta"
    ]
    assert len(chunks) == 2
    assert chunks[0].endswith(". ")
    assert all(1 <= len(chunk) <= 512 for chunk in chunks)
    assert "".join(chunks) == answer
    result = next(
        event["safe_view"] for event in events if event["event"] == "result"
    )
    assert result["answer"] == answer


def test_assistant_query_stream_replays_one_draft_and_sync_returns_same_safe_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    fixture.employee.field_policy = {"writable_fields": ["name"]}
    calls = 0
    draft_id = uuid4()

    def run(*args, **kwargs):
        nonlocal calls
        calls += 1
        fixture.uow.record_change_drafts.append(SimpleNamespace(id=draft_id))
        return AssistantQuerySafeView(
            status="draft_pending",
            answer="A controlled draft is ready for confirmation.",
            citations=(
                AssistantQuerySafeCitation(
                    ordinal=1,
                    label="general_advice",
                ),
            ),
            degradation_codes=(),
            draft_id=draft_id,
        )

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)
    payload = _payload(
        fixture,
        requested_action="draft_update",
        target_record_id=str(fixture.record.id),
    )

    with _client(fixture) as client:
        first = client.post(STREAM_PATH, json=payload)
        replay = client.post(STREAM_PATH, json=payload)
        synchronous = client.post(PATH, json=payload)

    assert first.status_code == replay.status_code == synchronous.status_code == 200
    first_events = _parse_test_sse(first.text)
    replay_events = _parse_test_sse(replay.text)
    first_result = next(
        event["safe_view"] for event in first_events if event["event"] == "result"
    )
    replay_result = next(
        event["safe_view"] for event in replay_events if event["event"] == "result"
    )
    assert first_result == replay_result == synchronous.json()
    assert [
        event.get("phase") for event in first_events if event["event"] == "status"
    ] == ["authorizing", "analysing", "completed"]
    assert [
        event.get("phase") for event in replay_events if event["event"] == "status"
    ] == ["authorizing", "completed"]
    assert calls == 1
    assert len(fixture.uow.record_change_drafts) == 1
    assert len(fixture.uow.idempotency_records) == 1


def test_assistant_query_stream_denied_scope_is_redacted_terminal_error() -> None:
    fixture = _fixture()
    fixture.employee.status = "paused"

    with _client(fixture) as client:
        response = client.post(STREAM_PATH, json=_payload(fixture))

    assert response.status_code == 200
    events = _parse_test_sse(response.text)
    assert [event["event"] for event in events] == ["status", "error"]
    assert events[0]["phase"] == "authorizing"
    assert events[1]["code"] == "stage08_collaboration_scope_denied"
    assert events[1]["message"] == "stage08_collaboration_scope_denied"
    assert "employee_scope_denied" not in response.text
    assert fixture.uow.idempotency_records == []


def test_assistant_query_stream_never_emits_provider_or_internal_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    sentinel = "PRIVATE_PROVIDER_RAW_TOKEN_AND_TRACEBACK"

    def fail(*args, **kwargs):
        raise RuntimeError(sentinel)

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", fail)

    with _client(fixture) as client:
        response = client.post(STREAM_PATH, json=_payload(fixture))

    assert response.status_code == 200
    events = _parse_test_sse(response.text)
    assert [event["event"] for event in events] == [
        "status",
        "status",
        "error",
    ]
    assert [
        event["phase"] for event in events if event["event"] == "status"
    ] == ["authorizing", "analysing"]
    assert events[-1]["code"] == "stage08_collaboration_internal_failure"
    assert events[-1]["message"] == "stage08_collaboration_internal_failure"
    assert sentinel not in response.text
    assert fixture.uow.idempotency_records == []


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
        "skill": {
            "skill_id": "platform-base",
            "label": "查表问答",
            "manifest_version": "stage06-larksuite-skills-v1",
            "selection_mode": "auto",
        },
    }
    assert len(fixture.uow.agent_runs) == 1
    assert len(fixture.uow.idempotency_records) == 1


def test_assistant_query_resolves_an_explicit_public_skill_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    captured: dict[str, object] = {}

    def run(uow, command, actor, *, deps, now, runtime_control):
        del uow, actor, deps, now, runtime_control
        captured["command"] = _command_snapshot(command)
        return AssistantQuerySafeView(
            status="completed",
            answer="已完成汇总。",
            citations=(
                AssistantQuerySafeCitation(ordinal=1, label="business_data"),
            ),
            degradation_codes=(),
            draft_id=None,
        )

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)

    with _client(fixture) as client:
        response = client.post(
            PATH,
            json=_payload(
                fixture,
                intent="business_fact",
                skill_id="platform-tabular-analysis",
            ),
        )

    assert response.status_code == 200
    assert response.json()["skill"] == {
        "skill_id": "platform-tabular-analysis",
        "label": "汇总分析",
        "manifest_version": "stage06-larksuite-skills-v1",
        "selection_mode": "explicit",
    }
    assert captured["command"].skill_profile.primary_skill_id == "platform-tabular-analysis"


def test_explicit_skill_profile_uses_the_stage06_manifest_not_catalog_constants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    captured: dict[str, object] = {}
    manifest = get_stage06_skill_manifest("platform-tabular-analysis")

    monkeypatch.setattr(
        collaboration_route,
        "get_stage06_skill_manifest",
        lambda skill_id: replace(
            manifest,
            source_skill="registry-owned-source",
            output_contract="registry-owned-output",
            confirmation_policy="registry-owned-policy",
            allowed_actions=("registry-owned-action",),
        ),
    )

    def run(uow, command, actor, *, deps, now, runtime_control):
        del uow, actor, deps, now, runtime_control
        captured["command"] = _command_snapshot(command)
        return _degraded()

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)

    with _client(fixture) as client:
        response = client.post(
            PATH,
            json=_payload(
                fixture,
                intent="business_fact",
                skill_id="platform-tabular-analysis",
            ),
        )

    assert response.status_code == 200
    profile = captured["command"].skill_profile
    assert profile.source_skill == "registry-owned-source"
    assert profile.output_contract == "registry-owned-output"
    assert profile.confirmation_policy == "registry-owned-policy"
    assert profile.manifest_allowed_actions == ("registry-owned-action",)


def test_auto_skill_uses_stage06_matcher_candidate_before_server_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    request = AssistantQueryRequest.model_validate(
        _payload(fixture, intent="business_fact", query="summarize this table")
    )
    catalog = collaboration_route.resolve_stage09_skill_catalog(
        fixture.uow,
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        target_record_id=None,
        actor=fixture.actor,
    )
    calls: list[dict[str, object]] = []

    def match(**kwargs):
        calls.append(kwargs)
        return {
            "selected_skills": [
                {"skill_id": "platform-tabular-analysis", "confidence": "0.90"}
            ]
        }

    monkeypatch.setattr(collaboration_route, "build_stage06_skill_evidence", match)

    assert collaboration_route._auto_primary_skill_id(catalog, request) == "platform-tabular-analysis"
    assert calls[0]["source_text"] == "summarize this table"


def test_auto_skill_uses_unique_highest_matcher_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    request = AssistantQueryRequest.model_validate(
        _payload(fixture, intent="business_fact", query="analyze risk")
    )
    catalog = collaboration_route.resolve_stage09_skill_catalog(
        fixture.uow,
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        target_record_id=None,
        actor=fixture.actor,
    )
    monkeypatch.setattr(
        collaboration_route,
        "build_stage06_skill_evidence",
        lambda **kwargs: {
            "selected_skills": [
                {"skill_id": "platform-base", "confidence": "0.80"},
                {"skill_id": "platform-tabular-analysis", "confidence": "0.90"},
            ]
        },
    )

    assert collaboration_route._auto_primary_skill_id(catalog, request) == "platform-tabular-analysis"


def test_auto_skill_rejects_equal_highest_matcher_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    request = AssistantQueryRequest.model_validate(
        _payload(fixture, intent="business_fact", query="ambiguous summary")
    )
    catalog = collaboration_route.resolve_stage09_skill_catalog(
        fixture.uow,
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        target_record_id=None,
        actor=fixture.actor,
    )
    monkeypatch.setattr(
        collaboration_route,
        "build_stage06_skill_evidence",
        lambda **kwargs: {
            "selected_skills": [
                {"skill_id": "platform-base", "confidence": "0.90"},
                {"skill_id": "platform-tabular-analysis", "confidence": "0.90"},
            ]
        },
    )

    with pytest.raises(Exception) as exc_info:
        collaboration_route._auto_primary_skill_id(catalog, request)

    assert getattr(exc_info.value, "code", None) == "stage09_skill_resolution_denied"


def test_auto_telegram_without_proof_does_not_fall_back_to_lower_confidence_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    request = AssistantQueryRequest.model_validate(
        _payload(fixture, intent="mixed", query="telegram chat summary")
    )
    catalog = collaboration_route.resolve_stage09_skill_catalog(
        fixture.uow,
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        target_record_id=None,
        actor=fixture.actor,
    )
    monkeypatch.setattr(
        collaboration_route,
        "build_stage06_skill_evidence",
        lambda **kwargs: {
            "selected_skills": [
                {"skill_id": "platform-telegram-im", "confidence": "0.90"},
                {"skill_id": "platform-base", "confidence": "0.80"},
            ]
        },
    )

    with pytest.raises(Exception) as exc_info:
        collaboration_route._auto_primary_skill_id(catalog, request)

    assert getattr(exc_info.value, "code", None) == "stage09_skill_resolution_denied"


@pytest.mark.parametrize(
    ("query", "expected_skill"),
    [
        ("inspect this schema", "platform-base"),
        ("analyze the current work", "platform-tabular-analysis"),
        ("organize the follow up task", "platform-task"),
    ],
)
def test_auto_skill_uses_real_stage06_matcher_queries(
    query: str,
    expected_skill: str,
) -> None:
    fixture = _fixture()
    request = AssistantQueryRequest.model_validate(
        _payload(fixture, intent="business_fact", query=query)
    )
    catalog = collaboration_route.resolve_stage09_skill_catalog(
        fixture.uow,
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        target_record_id=None,
        actor=fixture.actor,
    )

    assert collaboration_route._auto_primary_skill_id(catalog, request) == expected_skill


@pytest.mark.parametrize(
    "skill_id",
    ["unknown-skill", "platform-shared-policy", "platform-calendar"],
)
def test_nonpublic_or_inactive_explicit_skill_fails_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
    skill_id: str,
) -> None:
    fixture = _fixture()
    called = False

    def run(*args, **kwargs):
        nonlocal called
        called = True
        return _degraded()

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)
    with _client(fixture) as client:
        response = client.post(
            PATH,
            json=_payload(
                fixture,
                intent="business_fact",
                skill_id=skill_id,
            ),
        )

    assert response.status_code == 422
    assert called is False
    assert fixture.uow.idempotency_records == []


def test_explicit_skill_rejects_incompatible_action_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    called = False
    fixture.employee.field_policy = {"writable_fields": ["name"]}

    def run(*args, **kwargs):
        nonlocal called
        called = True
        return _degraded()

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)
    with _client(fixture) as client:
        response = client.post(
            PATH,
            json=_payload(
                fixture,
                intent="business_fact",
                requested_action="draft_update",
                target_record_id=str(fixture.record.id),
                skill_id="platform-tabular-analysis",
            ),
        )

    assert response.status_code == 422
    assert called is False


def test_explicit_skill_rejects_incompatible_intent_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    called = False

    def run(*args, **kwargs):
        nonlocal called
        called = True
        return _degraded()

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)
    with _client(fixture) as client:
        response = client.post(
            PATH,
            json=_payload(
                fixture,
                intent="general_advice",
                skill_id="platform-tabular-analysis",
            ),
        )

    assert response.status_code == 422
    assert called is False


def test_explicit_telegram_skill_without_chat_proof_fails_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    called = False

    def run(*args, **kwargs):
        nonlocal called
        called = True
        return _degraded()

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)
    with _client(fixture) as client:
        response = client.post(
            PATH,
            json=_payload(
                fixture,
                intent="mixed",
                skill_id="platform-telegram-im",
            ),
        )

    assert response.status_code == 422
    assert called is False


def test_query_fingerprint_includes_resolved_skill_semantics() -> None:
    fixture = _fixture()
    request = AssistantQueryRequest.model_validate(_payload(fixture))
    base = SimpleNamespace(
        primary_skill_id="platform-base",
        selection_mode="auto",
        manifest_version="stage06-larksuite-skills-v1",
    )
    changed_primary = SimpleNamespace(
        primary_skill_id="platform-tabular-analysis",
        selection_mode="auto",
        manifest_version="stage06-larksuite-skills-v1",
    )
    changed_mode = SimpleNamespace(
        primary_skill_id="platform-base",
        selection_mode="explicit",
        manifest_version="stage06-larksuite-skills-v1",
    )
    changed_version = SimpleNamespace(
        primary_skill_id="platform-base",
        selection_mode="auto",
        manifest_version="stage06-larksuite-skills-v2",
    )

    fingerprints = {
        collaboration_route._query_fingerprint(
            request, fixture.actor.actor_id, skill_profile=profile
        )
        for profile in (base, changed_primary, changed_mode, changed_version)
    }

    assert len(fingerprints) == 4


@pytest.mark.parametrize("query", ["你好", "您好！", "hello", "你能帮我做什么？"])
def test_auto_mixed_pure_conversation_is_normalized_server_side(query: str) -> None:
    fixture = _fixture()
    request = AssistantQueryRequest.model_validate(
        _payload(fixture, intent="mixed", query=query)
    )

    effective = collaboration_route._effective_auto_conversation_request(request)

    assert effective.intent == "general_advice"
    assert effective.query == query


@pytest.mark.parametrize(
    ("query", "requested_action", "skill_id"),
    [
        ("你好，明日璀璨客户现在是什么阶段？", "read_only", None),
        ("请介绍项目状态", "read_only", None),
        ("你好", "read_only", "platform-base"),
        ("你好", "draft_update", None),
    ],
)
def test_business_explicit_or_write_request_is_never_downgraded_to_general_advice(
    query: str,
    requested_action: str,
    skill_id: str | None,
) -> None:
    fixture = _fixture()
    payload = _payload(
        fixture,
        intent="mixed",
        query=query,
        requested_action=requested_action,
        skill_id=skill_id,
    )
    if requested_action == "draft_update":
        payload["target_record_id"] = str(fixture.record.id)
    request = AssistantQueryRequest.model_validate(payload)

    effective = collaboration_route._effective_auto_conversation_request(request)

    assert effective.intent == "mixed"


def test_prepare_uses_server_normalized_general_advice_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    captured: dict[str, object] = {}

    def run(uow, command, actor, *, deps, now, runtime_control):
        del uow, actor, deps, now, runtime_control
        captured["command"] = _command_snapshot(command)
        return AssistantQuerySafeView(
            status="completed",
            answer="你好，有什么需要我帮助的吗？",
            citations=(
                AssistantQuerySafeCitation(ordinal=1, label="general_advice"),
            ),
            degradation_codes=(),
            draft_id=None,
        )

    monkeypatch.setattr(collaboration_route, "run_stage08_collaboration", run)
    with _client(fixture) as client:
        response = client.post(
            PATH,
            json=_payload(fixture, intent="mixed", query="你好"),
        )

    assert response.status_code == 200
    assert captured["command"].intent == "general_advice"


def test_assistant_query_derives_command_server_side_and_returns_only_safe_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    captured: dict[str, object] = {}

    def run(uow, command, actor, *, deps, now, runtime_control):
        del uow, deps, now, runtime_control
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
        "skill",
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
        "skill": {
            "skill_id": "platform-base",
            "label": "查表问答",
            "manifest_version": "stage06-larksuite-skills-v1",
            "selection_mode": "auto",
        },
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
