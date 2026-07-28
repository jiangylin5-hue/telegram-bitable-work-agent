from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.schemas.agent_event_runtime import AgentEventEnvelope, RunCheckpointControl
from app.runtime.stage08_collaboration_contracts import AssistantQuerySafeView
from app.services.agent_event_runtime import (
    InMemoryAgentEventRuntimeUnitOfWork,
    RuntimeScopeDrift,
    append_checkpoint_and_event,
    claim_run_lease,
    create_agent_run,
)
from app.services.agent_sse_projection import project_safe_run_events
from app.services.agent_orchestrator import expire_agent_run


NOW = datetime(2026, 7, 28, 9, 0, tzinfo=UTC)


def test_projection_replays_after_cursor_and_exposes_only_allowlisted_fields() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = create_agent_run(
        uow,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash="a" * 64,
        idempotency_key_hash="b" * 64,
        deadline_at=NOW + timedelta(minutes=1),
        now=NOW,
    ).run
    claim_run_lease(
        uow,
        run_id=run.id,
        lease_owner="worker",
        now=NOW,
        lease_seconds=30,
    )
    append_checkpoint_and_event(
        uow,
        run_id=run.id,
        expected_version=run.version,
        lease_owner="worker",
        authorization_hash="a" * 64,
        node_key="working",
        control=RunCheckpointControl(
            completed_command_ids=(),
            pending_command_ids=(),
            retry_count=0,
            next_action="wait_children",
        ),
        event=AgentEventEnvelope(
            event_id=uuid4(),
            run_id=run.id,
            causation_id=run.id,
            correlation_id=run.id,
            sequence=2,
            event_type="agent.progressed",
            status="running",
            source_role="specialist",
            source_capability="platform.tabular.analyse",
            safe_summary="已读取授权数据",
            metrics={"records_read": 2},
            occurred_at=NOW,
        ),
    )

    projected = project_safe_run_events(
        uow,
        run_id=run.id,
        authorization_hash="a" * 64,
        after_sequence=1,
        resolve_safe_view=lambda artifact_ref: AssistantQuerySafeView(
            status="completed",
            answer="安全结果",
            citations=(),
            degradation_codes=(),
            draft_id=None,
        ),
    )

    assert len(projected) == 1
    payload = projected[0].model_dump(mode="json")
    assert payload == {
        "run_id": str(run.id),
        "event_id": str(uow.events[1].id),
        "sequence": 2,
        "event": "status",
        "phase": "running",
        "message": "已读取授权数据",
    }
    assert "metrics" not in payload
    assert "source_capability" not in payload


def test_projection_rejects_scope_drift_before_replay() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = create_agent_run(
        uow,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash="a" * 64,
        idempotency_key_hash="b" * 64,
        deadline_at=NOW + timedelta(minutes=1),
        now=NOW,
    ).run

    with pytest.raises(RuntimeScopeDrift, match="agent_run_scope_drift"):
        project_safe_run_events(
            uow,
            run_id=run.id,
            authorization_hash="c" * 64,
            after_sequence=0,
        )


def test_projection_exposes_only_a_stable_timeout_error() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = create_agent_run(
        uow,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash="a" * 64,
        idempotency_key_hash="b" * 64,
        deadline_at=NOW + timedelta(minutes=1),
        now=NOW,
    ).run
    expire_agent_run(
        uow,
        run_id=run.id,
        authorization_hash="a" * 64,
        supervisor_id="timeout-worker",
        now=NOW + timedelta(minutes=1),
    )

    projected = project_safe_run_events(
        uow,
        run_id=run.id,
        authorization_hash="a" * 64,
        after_sequence=1,
    )

    assert len(projected) == 1
    assert projected[0].event == "error"
    assert projected[0].code == "run_timed_out"
    assert projected[0].message == "任务已超时"
