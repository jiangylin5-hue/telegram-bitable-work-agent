from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module
from uuid import UUID

import pytest

from app.schemas.agent_stage12_runtime import Stage12RuntimeAdmissionRequest
from app.services.agent_event_runtime import InMemoryAgentEventRuntimeUnitOfWork
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from app.services.stage12_action_runtime import InMemoryStage12ActionRuntimeRepository


RUN_ID = UUID("33000000-0000-4000-8000-000000000001")
WORKSPACE_ID = UUID("33000000-0000-4000-8000-000000000002")
EMPLOYEE_ID = UUID("33000000-0000-4000-8000-000000000003")
HASH = "a" * 64


def _admission_module():
    try:
        return import_module("app.services.agent_stage12_runtime_admission")
    except ModuleNotFoundError:
        pytest.fail("Stage12 SQL admission service is not implemented")


def _graph_module():
    try:
        return import_module("app.agents.stage12_runtime_admission")
    except ModuleNotFoundError:
        pytest.fail("Stage12 admission LangGraph is not implemented")


def _request() -> Stage12RuntimeAdmissionRequest:
    return Stage12RuntimeAdmissionRequest(
        run_id=RUN_ID,
        actor_user_id="owner-1",
        workspace_id=WORKSPACE_ID,
        digital_employee_id=EMPLOYEE_ID,
        intent="business_fact",
        query="列出所有阻塞事项",
        target_record_id=None,
        idempotency_key="stage12-admission-unit-1",
        skill_id="platform-tabular-analysis",
        authorization_hash=HASH,
        deadline_at=datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
    )


def test_admission_graph_executes_the_five_bounded_nodes_in_order() -> None:
    module = _graph_module()
    observed: list[str] = []

    def node(name: str):
        def execute(state):
            observed.append(name)
            return {"completed_nodes": (*state.get("completed_nodes", ()), name)}

        return execute

    dependencies = module.Stage12AdmissionDependencies(
        authorize_schema=node("authorize_schema"),
        plan_task=node("plan_task"),
        execute_authorized_inputs=node("execute_authorized_inputs"),
        persist_typed_inputs=node("persist_typed_inputs"),
        dispatch_commands=node("dispatch_commands"),
    )

    result = module.build_stage12_admission_graph(dependencies).invoke(
        {"request": _request(), "completed_nodes": ()}
    )

    assert observed == [
        "authorize_schema",
        "plan_task",
        "execute_authorized_inputs",
        "persist_typed_inputs",
        "dispatch_commands",
    ]
    assert result["completed_nodes"] == tuple(observed)


def test_deployed_admission_rejects_in_memory_uows_before_any_artifact_write() -> None:
    module = _admission_module()
    platform = InMemoryStage06PlatformUnitOfWork()
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    objectives = InMemoryStage12ActionRuntimeRepository()

    with pytest.raises(ValueError, match="stage12_sql_uow_required"):
        module.admit_stage12_runtime_run(
            platform,
            runtime,
            objectives,
            request=_request(),
            settings=None,
            actor=None,
        )

    assert runtime.runs == []
    assert runtime.commands == []
    assert runtime.artifacts == []
