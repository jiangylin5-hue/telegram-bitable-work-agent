from datetime import UTC, datetime, timedelta
import hashlib
from uuid import uuid4

import pytest

from app.schemas.agent_event_runtime import AgentEventEnvelope
from app.services.agent_event_runtime import (
    InMemoryAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_orchestrator import (
    OrchestratorCapabilityDenied,
    OrchestratorError,
    OrchestratorScopeDrift,
    SpecialistSafeResult,
    dispatch_specialist_command,
    execute_read_only_specialist,
    expire_agent_run,
    fail_specialist_command,
    cancel_agent_run,
    validate_specialist_event,
)


NOW = datetime(2026, 7, 28, 8, 0, tzinfo=UTC)
HASH = "a" * 64


def _run(uow: InMemoryAgentEventRuntimeUnitOfWork):
    return create_agent_run(
        uow,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash=HASH,
        idempotency_key_hash="b" * 64,
        deadline_at=NOW + timedelta(minutes=2),
        now=NOW,
    ).run


def test_dispatch_rejects_unregistered_capability_without_side_effects() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = _run(uow)

    with pytest.raises(OrchestratorCapabilityDenied, match="capability_not_registered"):
        dispatch_specialist_command(
            uow,
            run_id=run.id,
            target_capability="platform.unrestricted.execute",
            payload_ref="stage08-idempotency:" + str(uuid4()),
            authorization_hash=HASH,
            now=NOW,
        )

    assert uow.commands == []
    assert len(uow.events) == 1


def test_dispatch_rejects_stale_scope_proof_without_side_effects() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = _run(uow)

    with pytest.raises(OrchestratorScopeDrift, match="scope_proof_mismatch"):
        dispatch_specialist_command(
            uow,
            run_id=run.id,
            target_capability="platform.tabular.analyse",
            payload_ref="stage08-idempotency:" + str(uuid4()),
            authorization_hash="c" * 64,
            now=NOW,
        )

    assert uow.commands == []
    assert len(uow.events) == 1


def test_specialist_cannot_emit_run_terminal_event() -> None:
    with pytest.raises(ValueError, match="specialist_run_event_forbidden"):
        validate_specialist_event(
            AgentEventEnvelope.model_construct(
                schema_version="agent-event.v1",
                event_id=uuid4(),
                run_id=uuid4(),
                command_id=uuid4(),
                causation_id=uuid4(),
                correlation_id=uuid4(),
                sequence=2,
                event_type="run.completed",
                status="completed",
                source_role="specialist",
                source_capability="platform.tabular.analyse",
                safe_summary="越权完成",
                artifact_ref=None,
                metrics={},
                occurred_at=NOW,
            )
        )


def test_read_only_specialist_finishes_via_supervisor_without_business_writes() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = _run(uow)
    command = dispatch_specialist_command(
        uow,
        run_id=run.id,
        target_capability="platform.tabular.analyse",
        payload_ref="stage08-idempotency:" + str(uuid4()),
        authorization_hash=HASH,
        now=NOW,
    )
    calls = 0

    def execute() -> SpecialistSafeResult:
        nonlocal calls
        calls += 1
        return SpecialistSafeResult(
            storage_ref="stage08-idempotency:" + str(uuid4()),
            content_hash=hashlib.sha256("安全结果".encode()).hexdigest(),
            safe_summary="已基于授权表格完成只读分析",
            metrics={"records_read": 3},
        )

    result = execute_read_only_specialist(
        uow,
        command_id=command.id,
        authorization_hash=HASH,
        worker_id="test-worker",
        now=NOW + timedelta(seconds=1),
        execute=execute,
    )

    assert calls == 1
    assert result.run.status == "completed"
    assert command.status == "completed"
    assert len(uow.artifacts) == 1
    assert [event.event_type for event in uow.events] == [
        "run.accepted",
        "command.dispatched",
        "agent.started",
        "agent.completed",
        "run.completed",
    ]
    assert uow.events[-2].source_role == "specialist"
    assert uow.events[-1].source_role == "supervisor"
    assert all(not hasattr(item, "record_values") for item in uow.artifacts)


def test_duplicate_command_execution_replays_completed_result() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = _run(uow)
    command = dispatch_specialist_command(
        uow,
        run_id=run.id,
        target_capability="platform.tabular.analyse",
        payload_ref="stage08-idempotency:" + str(uuid4()),
        authorization_hash=HASH,
        now=NOW,
    )
    calls = 0

    def execute() -> SpecialistSafeResult:
        nonlocal calls
        calls += 1
        return SpecialistSafeResult(
            storage_ref="stage08-idempotency:" + str(uuid4()),
            content_hash="d" * 64,
            safe_summary="完成",
        )

    first = execute_read_only_specialist(
        uow,
        command_id=command.id,
        authorization_hash=HASH,
        worker_id="worker-1",
        now=NOW + timedelta(seconds=1),
        execute=execute,
    )
    replay = execute_read_only_specialist(
        uow,
        command_id=command.id,
        authorization_hash=HASH,
        worker_id="worker-2",
        now=NOW + timedelta(seconds=2),
        execute=execute,
    )

    assert calls == 1
    assert replay.artifact.id == first.artifact.id
    assert len(uow.events) == 5


def test_failed_specialist_is_redacted_and_terminal() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = _run(uow)
    command = dispatch_specialist_command(
        uow,
        run_id=run.id,
        target_capability="platform.tabular.analyse",
        payload_ref="stage08-idempotency:" + str(uuid4()),
        authorization_hash=HASH,
        now=NOW,
    )

    failed = fail_specialist_command(
        uow,
        command_id=command.id,
        authorization_hash=HASH,
        worker_id="recovery-worker",
        now=NOW + timedelta(seconds=1),
    )

    assert failed.status == "failed"
    assert command.status == "failed"
    assert uow.events[-1].event_type == "agent.failed"
    assert uow.events[-1].safe_summary == "只读分析未能完成"


def test_failed_specialist_after_deadline_converges_to_timed_out() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = _run(uow)
    command = dispatch_specialist_command(
        uow,
        run_id=run.id,
        target_capability="platform.tabular.analyse",
        payload_ref="stage08-idempotency:" + str(uuid4()),
        authorization_hash=HASH,
        now=NOW,
    )

    timed_out = fail_specialist_command(
        uow,
        command_id=command.id,
        authorization_hash=HASH,
        worker_id="recovery-worker",
        now=run.deadline_at,
    )

    assert timed_out.status == "timed_out"
    assert command.status == "failed"
    assert uow.events[-1].event_type == "run.timed_out"


def test_supervisor_cancellation_stops_new_work() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = _run(uow)

    cancelled = cancel_agent_run(
        uow,
        run_id=run.id,
        authorization_hash=HASH,
        supervisor_id="cancel-worker",
        now=NOW + timedelta(seconds=1),
    )

    assert cancelled.status == "cancelled"
    assert uow.events[-1].event_type == "run.cancelled"
    with pytest.raises(OrchestratorError, match="agent_run_not_dispatchable"):
        dispatch_specialist_command(
            uow,
            run_id=run.id,
            target_capability="platform.tabular.analyse",
            payload_ref="stage08-idempotency:" + str(uuid4()),
            authorization_hash=HASH,
            now=NOW + timedelta(seconds=2),
        )


def test_supervisor_closes_expired_run_once_with_a_safe_terminal_event() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = _run(uow)

    with pytest.raises(OrchestratorError, match="agent_run_deadline_not_reached"):
        expire_agent_run(
            uow,
            run_id=run.id,
            authorization_hash=HASH,
            supervisor_id="timeout-worker",
            now=NOW + timedelta(minutes=1),
        )

    expired = expire_agent_run(
        uow,
        run_id=run.id,
        authorization_hash=HASH,
        supervisor_id="timeout-worker",
        now=NOW + timedelta(minutes=2),
    )
    event_count = len(uow.events)
    replay = expire_agent_run(
        uow,
        run_id=run.id,
        authorization_hash=HASH,
        supervisor_id="timeout-worker",
        now=NOW + timedelta(minutes=3),
    )

    assert expired.status == "timed_out"
    assert replay is expired
    assert len(uow.events) == event_count
    assert uow.events[-1].event_type == "run.timed_out"
    assert uow.events[-1].safe_summary == "任务已超时"
