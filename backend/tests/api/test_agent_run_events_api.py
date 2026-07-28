from dataclasses import replace
import base64
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api.routes.agent_runs as agent_run_routes
import app.api.routes.stage08_collaboration as collaboration_routes
from app.api.routes.agent_runs import get_agent_event_runtime_uow
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.config import Settings
from app.main import create_app
from app.runtime.stage08_collaboration_contracts import (
    AssistantQuerySafeView,
    AssistantSkillSafeSummary,
)
from app.services.agent_event_runtime import InMemoryAgentEventRuntimeUnitOfWork
from app.services.stage06_idempotency import complete_idempotent_operation
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


def _fixture() -> SimpleNamespace:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="stage10-owner", role="owner")
    workspace = create_workspace(
        uow, name="Stage10", owner_user_id=actor.actor_id, actor=actor
    )
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    table = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
    create_field(
        uow,
        table.id,
        name="Name",
        key="name",
        field_type="text",
        actor=actor,
    )
    record = create_record(
        uow, table.id, values={"name": "安全客户"}, actor=actor
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
        name="只读分析员工",
        description="Stage10 test",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["query", "summarize"],
        actor=actor,
    )
    return SimpleNamespace(
        uow=uow,
        actor=actor,
        workspace=workspace,
        record=record,
        employee=employee,
    )


def _client(fixture: SimpleNamespace, runtime: InMemoryAgentEventRuntimeUnitOfWork):
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: fixture.uow
    app.dependency_overrides[get_agent_event_runtime_uow] = lambda: runtime
    client = TestClient(app, raise_server_exceptions=False)
    client.headers["X-Stage06-User-Id"] = fixture.actor.actor_id
    return client


def _payload(fixture: SimpleNamespace) -> dict[str, object]:
    return {
        "workspace_id": str(fixture.workspace.id),
        "employee_id": str(fixture.employee.id),
        "intent": "business_fact",
        "query": "这个客户的当前情况是什么？",
        "requested_action": "read_only",
        "target_record_id": str(fixture.record.id),
        "idempotency_key": "stage10-api-case-1",
        "skill_id": "platform-tabular-analysis",
    }


def _parse_sse(text: str) -> list[dict[str, object]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def _complete(prepared, answer: str) -> AssistantQuerySafeView:
    view = AssistantQuerySafeView(
        status="completed",
        answer=answer,
        citations=(),
        degradation_codes=(),
        draft_id=None,
        skill=AssistantSkillSafeSummary(
            skill_id="platform-tabular-analysis",
            label="汇总分析",
            manifest_version="stage06-larksuite-skills-v1",
            selection_mode="explicit",
        ),
    )
    complete_idempotent_operation(
        prepared.reservation,
        response_ref=collaboration_routes._safe_replay_projection(view),
    )
    return view


def test_create_and_reconnect_run_exposes_safe_ordered_events(monkeypatch) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(Settings(), agent_event_runtime_enabled=True),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda prepared, uow: _complete(prepared, "客户状态稳定，可以继续跟进。"),
    )

    with _client(fixture, runtime) as client:
        created = client.post("/api/stage10/agent-runs", json=_payload(fixture))
        assert created.status_code == 202, created.text
        replay = client.get(
            f"/api/stage10/agent-runs/{created.json()['run_id']}/events",
            headers={
                "Last-Event-ID": "2",
                "X-Stage06-User-Id": fixture.actor.actor_id,
            },
        )

    assert created.status_code == 202
    assert created.json()["status"] == "completed"
    assert replay.status_code == 200
    assert replay.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(replay.text)
    assert [event["sequence"] for event in events] == [3, 4, 5]
    assert [event["event"] for event in events] == ["status", "result", "done"]
    serialized = json.dumps(events, ensure_ascii=False)
    assert "这个客户" not in serialized
    assert "安全客户" not in serialized
    assert "metrics" not in serialized
    assert "source_capability" not in serialized


def test_reconnect_reauthorizes_and_denies_revoked_member(monkeypatch) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(Settings(), agent_event_runtime_enabled=True),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda prepared, uow: _complete(prepared, "安全结果"),
    )

    with _client(fixture, runtime) as client:
        created = client.post("/api/stage10/agent-runs", json=_payload(fixture))
        assert created.status_code == 202, created.text
        member = next(
            item
            for item in fixture.uow.workspace_members
            if item.user_id == fixture.actor.actor_id
        )
        member.status = "disabled"
        denied = client.get(
            f"/api/stage10/agent-runs/{created.json()['run_id']}/events"
        )

    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "agent_run_scope_denied"


def test_routes_are_hidden_when_feature_flag_is_disabled() -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()

    with _client(fixture, runtime) as client:
        response = client.post("/api/stage10/agent-runs", json=_payload(fixture))

    assert response.status_code == 404


def test_redis_worker_mode_enqueues_ciphertext_without_embedded_execution(
    monkeypatch,
) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    settings = replace(
        Settings(),
        agent_event_runtime_enabled=True,
        agent_event_runtime_mode="redis_worker",
        agent_event_runtime_allowed_workspace_ids=(str(fixture.workspace.id),),
        agent_runtime_input_key=base64.urlsafe_b64encode(b"k" * 32).decode("ascii"),
    )
    monkeypatch.setattr(agent_run_routes, "get_settings", lambda: settings)
    execute = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("embedded worker must not run")
    )
    monkeypatch.setattr(agent_run_routes, "complete_assistant_query", execute)

    with _client(fixture, runtime) as client:
        response = client.post("/api/stage10/agent-runs", json=_payload(fixture))

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "queued"
    assert len(runtime.private_inputs) == 1
    assert "这个客户".encode("utf-8") not in runtime.private_inputs[0].ciphertext
    assert runtime.commands[0].payload_ref == (
        f"agent-private-input:{runtime.private_inputs[0].id}"
    )


def test_stage10_workspace_allowlist_is_fail_closed(monkeypatch) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(
            Settings(),
            agent_event_runtime_enabled=True,
            agent_event_runtime_allowed_workspace_ids=(
                "11111111-1111-4111-8111-111111111111",
            ),
        ),
    )

    with _client(fixture, runtime) as client:
        response = client.post("/api/stage10/agent-runs", json=_payload(fixture))

    assert response.status_code == 404
    assert runtime.runs == []


def test_provider_failure_leaves_a_redacted_durable_terminal_event(monkeypatch) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(Settings(), agent_event_runtime_enabled=True),
    )

    def fail(prepared, uow):
        raise RuntimeError("raw provider secret must not escape")

    monkeypatch.setattr(agent_run_routes, "complete_assistant_query", fail)

    with _client(fixture, runtime) as client:
        response = client.post("/api/stage10/agent-runs", json=_payload(fixture))

    assert response.status_code == 500
    assert len(runtime.runs) == 1
    assert runtime.runs[0].status == "failed"
    assert runtime.events[-1].event_type == "agent.failed"
    serialized = json.dumps(runtime.events[-1].safe_summary, ensure_ascii=False)
    assert "provider secret" not in serialized


def test_safe_projection_corruption_is_not_misreported_as_scope_denial(monkeypatch) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(Settings(), agent_event_runtime_enabled=True),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda prepared, uow: _complete(prepared, "safe result"),
    )

    with _client(fixture, runtime) as client:
        created = client.post("/api/stage10/agent-runs", json=_payload(fixture))
        assert created.status_code == 202, created.text
        monkeypatch.setattr(
            agent_run_routes,
            "_safe_view_from_replay",
            lambda value: (_ for _ in ()).throw(
                PlatformValidationError("safe_projection_corrupt", "private detail")
            ),
        )
        response = client.get(
            f"/api/stage10/agent-runs/{created.json()['run_id']}/events"
        )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "agent_run_projection_failure"
    assert "private detail" not in response.text
