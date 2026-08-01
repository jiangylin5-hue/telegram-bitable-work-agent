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
    record = create_record(uow, table.id, values={"name": "安全客户"}, actor=actor)
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


def test_allowlisted_stage12_runtime_uses_isolated_admission_and_never_legacy(
    monkeypatch,
) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    settings = replace(Settings(), agent_event_runtime_enabled=True)
    calls: list[object] = []
    monkeypatch.setattr(agent_run_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(
        agent_run_routes,
        "build_stage12_runtime_profile",
        lambda value: object(),
        raising=False,
    )
    monkeypatch.setattr(
        agent_run_routes,
        "stage12_runtime_enabled",
        lambda profile, *, workspace_id: workspace_id == fixture.workspace.id,
        raising=False,
    )

    def admit(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            run_id=fixture.workspace.id,
            status="queued",
            replayed=False,
        )

    monkeypatch.setattr(
        agent_run_routes,
        "admit_stage12_runtime_run",
        admit,
        raising=False,
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy Stage08 must not execute")
        ),
    )

    with _client(fixture, runtime) as client:
        response = client.post("/api/stage10/agent-runs", json=_payload(fixture))

    assert response.status_code == 202, response.text
    assert response.json() == {
        "run_id": str(fixture.workspace.id),
        "status": "queued",
        "replayed": False,
    }
    assert len(calls) == 1
    assert runtime.runs == []


def test_non_allowlisted_workspace_preserves_legacy_stage10_path(monkeypatch) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(Settings(), agent_event_runtime_enabled=True),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "build_stage12_runtime_profile",
        lambda value: object(),
        raising=False,
    )
    monkeypatch.setattr(
        agent_run_routes,
        "stage12_runtime_enabled",
        lambda profile, *, workspace_id: False,
        raising=False,
    )
    monkeypatch.setattr(
        agent_run_routes,
        "admit_stage12_runtime_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Stage12 admission must stay isolated")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda prepared, uow: _complete(prepared, "legacy result"),
    )

    with _client(fixture, runtime) as client:
        response = client.post("/api/stage10/agent-runs", json=_payload(fixture))

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "completed"
    assert runtime.runs[0].workflow_version == "stage10-agent-event-runtime.v1"


def test_allowlisted_stage12_admission_failure_is_fail_closed(monkeypatch) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(Settings(), agent_event_runtime_enabled=True),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "build_stage12_runtime_profile",
        lambda value: object(),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "stage12_runtime_enabled",
        lambda profile, *, workspace_id: True,
    )
    monkeypatch.setattr(
        agent_run_routes,
        "admit_stage12_runtime_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("stage12_structured_query_required")
        ),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("allowlisted failure must not fall through to legacy")
        ),
    )

    with _client(fixture, runtime) as client:
        response = client.post("/api/stage10/agent-runs", json=_payload(fixture))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "agent_run_request_invalid"
    assert runtime.runs == []


def test_allowlisted_stage12_admission_replay_is_returned_without_legacy(
    monkeypatch,
) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(Settings(), agent_event_runtime_enabled=True),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "build_stage12_runtime_profile",
        lambda value: object(),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "stage12_runtime_enabled",
        lambda profile, *, workspace_id: True,
    )
    monkeypatch.setattr(
        agent_run_routes,
        "admit_stage12_runtime_run",
        lambda *_args, **_kwargs: SimpleNamespace(
            run_id=fixture.workspace.id,
            status="queued",
            replayed=True,
        ),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("replay must not invoke legacy")
        ),
    )

    with _client(fixture, runtime) as client:
        response = client.post("/api/stage10/agent-runs", json=_payload(fixture))

    assert response.status_code == 202
    assert response.json()["replayed"] is True
    assert runtime.runs == []


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
    assert runtime.events[-2].event_type == "agent.failed"
    assert runtime.events[-2].source_role == "specialist"
    assert runtime.events[-1].event_type == "run.failed"
    assert runtime.events[-1].source_role == "supervisor"
    serialized = json.dumps(runtime.events[-1].safe_summary, ensure_ascii=False)
    assert "provider secret" not in serialized


def test_multi_semantic_query_dispatches_three_specialists_and_returns_one_chat_result(
    monkeypatch,
) -> None:
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
        lambda prepared, uow: _complete(prepared, "复杂任务分析完成"),
    )
    payload = _payload(fixture)
    payload["query"] = "汇总今天的逾期和阻塞项目，判断风险并生成运营日报"
    payload["intent"] = "mixed"

    with _client(fixture, runtime) as client:
        created = client.post("/api/stage10/agent-runs", json=payload)
        assert created.status_code == 202, created.text
        streamed = client.get(
            f"/api/stage10/agent-runs/{created.json()['run_id']}/events"
        )

    assert streamed.status_code == 200
    assert runtime.runs[0].workflow_version == "stage11.coordination.v1"
    assert {item.target_capability for item in runtime.commands} == {
        "platform.tabular.analyse",
        "platform.risk.analyse",
        "platform.daily.summarise",
    }
    assert all(item.status == "completed" for item in runtime.commands)
    assert runtime.runs[0].status == "completed"
    assert streamed.text.count("event: result") == 1
    assert streamed.text.count("event: done") == 1


def test_stage12_shadow_difference_keeps_v1_as_the_only_dispatch_authority(
    monkeypatch,
) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(
            Settings(),
            agent_event_runtime_enabled=True,
            agent_task_planner_v2_mode="shadow",
            agent_task_planner_v2_shadow_workspace_ids=(str(fixture.workspace.id),),
        ),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda prepared, uow: _complete(prepared, "V1 authority retained"),
    )
    payload = _payload(fixture)
    payload["query"] = "列出 high 优先级项目"

    with _client(fixture, runtime) as client:
        created = client.post("/api/stage10/agent-runs", json=payload)

    assert created.status_code == 202, created.text
    assert {item.target_capability for item in runtime.commands} == {
        "platform.tabular.analyse",
        "platform.risk.analyse",
    }
    shadow_events = [
        item
        for item in fixture.uow.audit_events
        if item.event_type == "stage12.planner_shadow_observed"
    ]
    assert len(shadow_events) == 1
    assert shadow_events[0].after_state["v1_dispatch_unchanged"] is True
    assert "risk_analysis:-1" in shadow_events[0].after_state["objective_kind_deltas"]


def test_stage12_query_shadow_is_absent_from_http_sse_and_v1_dispatch(
    monkeypatch,
) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    sentinel_plan_hash = "c" * 64
    sentinel_result_hash = "d" * 64
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(
            Settings(),
            agent_event_runtime_enabled=True,
            agent_task_planner_v2_mode="shadow",
            agent_task_planner_v2_shadow_workspace_ids=(str(fixture.workspace.id),),
            authorized_query_engine_v1_mode="shadow",
            authorized_query_engine_v1_workspace_allowlist=(str(fixture.workspace.id),),
        ),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda prepared, uow: _complete(prepared, "V1 public result"),
    )
    sanitized = {
        "version": "authorized-query-shadow-observation.v1",
        "status": "observed",
        "plan_hashes": [sentinel_plan_hash],
        "result_hashes": [sentinel_result_hash],
        "result_record_count": 1,
        "scope_hash": "b" * 64,
    }
    monkeypatch.setattr(
        agent_run_routes,
        "run_authorized_query_shadow",
        lambda *_args, **_kwargs: SimpleNamespace(model_dump=lambda mode: sanitized),
    )
    payload = _payload(fixture)
    payload["query"] = "列出 high 优先级项目"

    with _client(fixture, runtime) as client:
        created = client.post("/api/stage10/agent-runs", json=payload)
        assert created.status_code == 202, created.text
        streamed = client.get(
            f"/api/stage10/agent-runs/{created.json()['run_id']}/events"
        )

    assert set(created.json()) == {"run_id", "status", "replayed"}
    assert streamed.status_code == 200
    assert {item.target_capability for item in runtime.commands} == {
        "platform.tabular.analyse",
        "platform.risk.analyse",
    }
    public_bytes = created.content + streamed.content
    assert sentinel_plan_hash.encode() not in public_bytes
    assert sentinel_result_hash.encode() not in public_bytes
    query_events = [
        item
        for item in fixture.uow.audit_events
        if item.event_type == "stage12.authorized_query_shadow_observed"
    ]
    assert len(query_events) == 1
    assert query_events[0].after_state == sanitized


def test_stage12_retrieval_shadow_is_audit_only_and_cannot_change_http_sse_or_dispatch(
    monkeypatch,
) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    comparison_hash = "e" * 64
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(
            Settings(),
            agent_event_runtime_enabled=True,
            openrouter_api_key="test-only-key",
            retrieval_v2_mode="shadow",
            retrieval_v2_workspace_allowlist=(str(fixture.workspace.id),),
            retrieval_v2_active_profile="stage12.openrouter-bge-m3-v1",
        ),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda prepared, uow: _complete(prepared, "V1 remains public"),
    )
    sanitized = {
        "version": "retrieval-shadow-observation.v1",
        "status": "observed",
        "v1_candidate_count": 2,
        "v2_candidate_count": 2,
        "overlap_count": 1,
        "recall_at_20": 0.5,
        "mrr_at_20": 1.0,
        "mean_absolute_rank_delta": 0.0,
        "truncated": False,
        "duration_ms": 1,
        "comparison_hash": comparison_hash,
        "failure_code": None,
    }
    monkeypatch.setattr(
        agent_run_routes,
        "run_retrieval_v2_shadow",
        lambda **_kwargs: SimpleNamespace(
            model_dump=lambda mode: sanitized,
        ),
    )

    with _client(fixture, runtime) as client:
        created = client.post("/api/stage10/agent-runs", json=_payload(fixture))
        assert created.status_code == 202, created.text
        streamed = client.get(
            f"/api/stage10/agent-runs/{created.json()['run_id']}/events"
        )

    assert set(created.json()) == {"run_id", "status", "replayed"}
    assert streamed.status_code == 200
    assert {item.target_capability for item in runtime.commands} == {
        "platform.tabular.analyse"
    }
    assert comparison_hash.encode() not in created.content + streamed.content
    events = [
        item
        for item in fixture.uow.audit_events
        if item.event_type == "stage12.retrieval_v2_shadow_observed"
    ]
    assert len(events) == 1
    assert events[0].after_state == sanitized


def test_stage12_typed_specialists_shadow_is_audit_only_and_keeps_v1_bytes(
    monkeypatch,
) -> None:
    fixture = _fixture()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    comparison_hash = "f" * 64
    monkeypatch.setattr(
        agent_run_routes,
        "get_settings",
        lambda: replace(
            Settings(),
            agent_event_runtime_enabled=True,
            openrouter_api_key="test-only-key",
            stage12_provider_v2_profile=("stage12.openrouter-gemini-2.5-flash-v1"),
            typed_specialists_v2_mode="shadow",
            typed_specialists_v2_workspace_allowlist=(str(fixture.workspace.id),),
        ),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "complete_assistant_query",
        lambda prepared, uow: _complete(prepared, "V1 remains public"),
    )
    sanitized = {
        "version": "typed-specialists-shadow-observation.v1",
        "status": "observed",
        "handler_count": 4,
        "typed_artifact_count": 6,
        "claim_count": 2,
        "valid_evidence_count": 2,
        "provider_attempt_count": 0,
        "provider_failure_count": 0,
        "action_proposal_count": 1,
        "write_count": 0,
        "send_count": 0,
        "duration_ms": 1,
        "comparison_hash": comparison_hash,
        "failure_code": None,
    }
    monkeypatch.setattr(
        agent_run_routes,
        "run_typed_specialists_shadow",
        lambda **_kwargs: SimpleNamespace(
            model_dump=lambda mode: sanitized,
        ),
    )

    with _client(fixture, runtime) as client:
        created = client.post("/api/stage10/agent-runs", json=_payload(fixture))
        assert created.status_code == 202, created.text
        streamed = client.get(
            f"/api/stage10/agent-runs/{created.json()['run_id']}/events"
        )

    assert set(created.json()) == {"run_id", "status", "replayed"}
    assert streamed.status_code == 200
    assert {item.target_capability for item in runtime.commands} == {
        "platform.tabular.analyse"
    }
    assert comparison_hash.encode() not in created.content + streamed.content
    events = [
        item
        for item in fixture.uow.audit_events
        if item.event_type == "stage12.typed_specialists_v2_shadow_observed"
    ]
    assert len(events) == 1
    assert events[0].after_state == sanitized


def test_safe_projection_corruption_is_not_misreported_as_scope_denial(
    monkeypatch,
) -> None:
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
