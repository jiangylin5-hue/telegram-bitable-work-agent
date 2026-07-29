from datetime import UTC, datetime, timedelta
import hashlib
from uuid import uuid4

from app.services.agent_event_runtime import (
    InMemoryAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_orchestrator import (
    SpecialistCommandDispatch,
    SpecialistSafeResult,
    dispatch_specialist_commands,
    execute_read_only_specialist,
    fail_specialist_command,
)


NOW = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def _result(label: str) -> SpecialistSafeResult:
    value = label.encode("utf-8")
    return SpecialistSafeResult(
        storage_ref=f"stage08-idempotency:{uuid4()}",
        content_hash=hashlib.sha256(value).hexdigest(),
        safe_summary=label,
        metrics={"records_read": 2},
    )


def _runtime():
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    scope_hash = "a" * 64
    run = create_agent_run(
        uow,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash=scope_hash,
        idempotency_key_hash="b" * 64,
        deadline_at=NOW + timedelta(minutes=5),
        now=NOW,
        workflow_version="stage11.coordination.v1",
    ).run
    return uow, run, scope_hash


def test_fan_out_dispatches_all_commands_in_one_durable_plan() -> None:
    uow, run, scope_hash = _runtime()
    commands = dispatch_specialist_commands(
        uow,
        run_id=run.id,
        dispatches=(
            SpecialistCommandDispatch(
                target_capability="platform.tabular.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
            ),
            SpecialistCommandDispatch(
                target_capability="platform.risk.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
            ),
        ),
        authorization_hash=scope_hash,
        now=NOW,
    )

    assert len(commands) == 2
    assert {item.command_type for item in commands} == {
        "analyse_visible_records",
        "analyse_visible_risks",
    }
    assert {item.topic for item in uow.outbox_events if item.aggregate_type == "agent_command"} == {
        "agent.commands.platform.tabular.analyse",
        "agent.commands.platform.risk.analyse",
    }
    latest = uow.checkpoints[-1].control_json
    assert set(latest["pending_command_ids"]) == {str(item.id) for item in commands}
    assert run.status == "queued"


def test_first_child_completion_does_not_finish_run_and_last_child_fans_in() -> None:
    uow, run, scope_hash = _runtime()
    first, second = dispatch_specialist_commands(
        uow,
        run_id=run.id,
        dispatches=(
            SpecialistCommandDispatch(
                target_capability="platform.tabular.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
            ),
            SpecialistCommandDispatch(
                target_capability="platform.risk.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
            ),
        ),
        authorization_hash=scope_hash,
        now=NOW,
    )

    first_result = execute_read_only_specialist(
        uow,
        command_id=first.id,
        authorization_hash=scope_hash,
        worker_id="tabular-1",
        now=NOW + timedelta(seconds=1),
        execute=lambda: _result("表格完成"),
    )
    assert first_result.run.status == "running"
    assert first.status == "completed"
    assert second.status == "queued"
    assert run.safe_result_ref is None
    assert not any(item.event_type == "run.completed" for item in uow.events)

    second_result = execute_read_only_specialist(
        uow,
        command_id=second.id,
        authorization_hash=scope_hash,
        worker_id="risk-1",
        now=NOW + timedelta(seconds=2),
        execute=lambda: _result("风险完成"),
    )
    assert second_result.run.status == "completed"
    assert run.safe_result_ref == second_result.artifact.id
    assert [item.event_type for item in uow.events].count("run.completed") == 1


def test_completed_child_replay_returns_its_own_artifact() -> None:
    uow, _run, scope_hash = _runtime()
    command = dispatch_specialist_commands(
        uow,
        run_id=_run.id,
        dispatches=(
            SpecialistCommandDispatch(
                target_capability="platform.tabular.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
            ),
        ),
        authorization_hash=scope_hash,
        now=NOW,
    )[0]
    first = execute_read_only_specialist(
        uow,
        command_id=command.id,
        authorization_hash=scope_hash,
        worker_id="tabular-1",
        now=NOW + timedelta(seconds=1),
        execute=lambda: _result("完成"),
    )
    replay = execute_read_only_specialist(
        uow,
        command_id=command.id,
        authorization_hash=scope_hash,
        worker_id="tabular-1",
        now=NOW + timedelta(seconds=2),
        execute=lambda: (_ for _ in ()).throw(RuntimeError("must not execute")),
    )

    assert replay.replayed is True
    assert replay.artifact.id == first.artifact.id


def test_optional_child_failure_degrades_only_after_required_child_completes() -> None:
    uow, run, scope_hash = _runtime()
    required, optional = dispatch_specialist_commands(
        uow,
        run_id=run.id,
        dispatches=(
            SpecialistCommandDispatch(
                target_capability="platform.tabular.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
                required=True,
            ),
            SpecialistCommandDispatch(
                target_capability="platform.risk.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
                required=False,
            ),
        ),
        authorization_hash=scope_hash,
        now=NOW,
    )

    fail_specialist_command(
        uow,
        command_id=optional.id,
        authorization_hash=scope_hash,
        worker_id="risk-1",
        now=NOW + timedelta(seconds=1),
    )
    assert optional.status == "failed"
    assert run.status == "running"

    result = execute_read_only_specialist(
        uow,
        command_id=required.id,
        authorization_hash=scope_hash,
        worker_id="tabular-1",
        now=NOW + timedelta(seconds=2),
        execute=lambda: _result("表格完成"),
    )
    assert result.run.status == "degraded"
    assert result.run.safe_result_ref == result.artifact.id
    assert [item.event_type for item in uow.events].count("run.degraded") == 1


def test_required_child_failure_terminalizes_unfinished_siblings() -> None:
    uow, run, scope_hash = _runtime()
    required, sibling = dispatch_specialist_commands(
        uow,
        run_id=run.id,
        dispatches=(
            SpecialistCommandDispatch(
                target_capability="platform.tabular.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
                required=True,
            ),
            SpecialistCommandDispatch(
                target_capability="platform.risk.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
                required=False,
            ),
        ),
        authorization_hash=scope_hash,
        now=NOW,
    )

    fail_specialist_command(
        uow,
        command_id=required.id,
        authorization_hash=scope_hash,
        worker_id="tabular-1",
        now=NOW + timedelta(seconds=1),
    )

    assert run.status == "failed"
    assert required.status == "failed"
    assert sibling.status == "failed"
    latest = uow.checkpoints[-1].control_json
    assert latest["pending_command_ids"] == []
    assert set(latest["failed_command_ids"]) == {str(required.id), str(sibling.id)}
