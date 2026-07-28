from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agent_event_runtime import (
    AgentCommandEnvelope,
    AgentEventEnvelope,
    RunCheckpointControl,
)
from app.services.agent_event_runtime import (
    InMemoryAgentEventRuntimeUnitOfWork,
    RuntimeConflict,
    RuntimeScopeDrift,
    append_checkpoint_and_event,
    claim_run_lease,
    create_agent_run,
)


def _now() -> datetime:
    return datetime(2026, 7, 28, 8, 0, tzinfo=UTC)


def test_command_envelope_accepts_safe_references_only() -> None:
    command = AgentCommandEnvelope(
        command_id=uuid4(),
        run_id=uuid4(),
        causation_id=uuid4(),
        correlation_id=uuid4(),
        sequence=1,
        target_capability="platform.tabular.analyse",
        command_type="analyse_visible_records",
        scope_proof_ref="scope:sha256:" + "a" * 64,
        input_artifact_refs=(uuid4(),),
        deadline_at=_now() + timedelta(minutes=2),
        idempotency_key_hash="b" * 64,
    )

    assert command.schema_version == "agent-command.v1"
    assert command.target_capability == "platform.tabular.analyse"
    assert command.model_dump(mode="json")["input_artifact_refs"]


@pytest.mark.parametrize("forbidden", ["prompt", "raw_result", "record_values"])
def test_command_envelope_rejects_private_payload_fields(forbidden: str) -> None:
    payload = {
        "command_id": uuid4(),
        "run_id": uuid4(),
        "causation_id": uuid4(),
        "correlation_id": uuid4(),
        "sequence": 1,
        "target_capability": "platform.tabular.analyse",
        "command_type": "analyse_visible_records",
        "scope_proof_ref": "scope:sha256:" + "a" * 64,
        "input_artifact_refs": [],
        "deadline_at": _now() + timedelta(minutes=2),
        "idempotency_key_hash": "b" * 64,
        forbidden: "private-value",
    }

    with pytest.raises(ValidationError):
        AgentCommandEnvelope.model_validate(payload)


def test_event_envelope_rejects_supervisor_terminal_event_from_specialist() -> None:
    with pytest.raises(ValidationError):
        AgentEventEnvelope(
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
            safe_summary="完成",
            metrics={"records_read": 2},
            occurred_at=_now(),
        )


def test_checkpoint_control_rejects_private_material_and_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        RunCheckpointControl(
            completed_command_ids=(uuid4(),),
            pending_command_ids=(),
            retry_count=0,
            next_action="fan_in",
            prompt="private",
        )


def test_create_run_is_idempotent_and_writes_initial_checkpoint_event_outbox() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    workspace_id = uuid4()
    employee_id = uuid4()
    kwargs = {
        "workspace_id": workspace_id,
        "root_employee_id": employee_id,
        "scope_hash": "a" * 64,
        "idempotency_key_hash": "b" * 64,
        "deadline_at": _now() + timedelta(minutes=5),
        "now": _now(),
    }

    first = create_agent_run(uow, **kwargs)
    replay = create_agent_run(uow, **kwargs)

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.run.id == first.run.id
    assert len(uow.runs) == 1
    assert len(uow.checkpoints) == 1
    assert len(uow.events) == 1
    assert len(uow.outbox_events) == 1
    assert uow.outbox_events[0].payload_json["event_type"] == "run.accepted"


def test_lease_can_only_be_taken_over_after_expiry() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    created = create_agent_run(
        uow,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash="a" * 64,
        idempotency_key_hash="b" * 64,
        deadline_at=_now() + timedelta(minutes=5),
        now=_now(),
    )

    claim_run_lease(
        uow,
        run_id=created.run.id,
        lease_owner="worker-a",
        now=_now(),
        lease_seconds=30,
    )
    with pytest.raises(RuntimeConflict):
        claim_run_lease(
            uow,
            run_id=created.run.id,
            lease_owner="worker-b",
            now=_now() + timedelta(seconds=20),
            lease_seconds=30,
        )

    taken_over = claim_run_lease(
        uow,
        run_id=created.run.id,
        lease_owner="worker-b",
        now=_now() + timedelta(seconds=31),
        lease_seconds=30,
    )
    assert taken_over.lease_owner == "worker-b"


def test_checkpoint_rejects_scope_drift_without_persisting_event() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    created = create_agent_run(
        uow,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash="a" * 64,
        idempotency_key_hash="b" * 64,
        deadline_at=_now() + timedelta(minutes=5),
        now=_now(),
    )
    run = claim_run_lease(
        uow,
        run_id=created.run.id,
        lease_owner="worker-a",
        now=_now(),
        lease_seconds=30,
    )
    event = AgentEventEnvelope(
        event_id=uuid4(),
        run_id=run.id,
        causation_id=run.id,
        correlation_id=run.id,
        sequence=2,
        event_type="run.completed",
        status="completed",
        source_role="supervisor",
        safe_summary="完成",
        occurred_at=_now(),
    )

    with pytest.raises(RuntimeScopeDrift):
        append_checkpoint_and_event(
            uow,
            run_id=run.id,
            expected_version=run.version,
            lease_owner="worker-a",
            authorization_hash="c" * 64,
            node_key="finalize",
            control=RunCheckpointControl(
                completed_command_ids=(),
                pending_command_ids=(),
                retry_count=0,
                next_action="stop",
            ),
            event=event,
        )

    assert len(uow.checkpoints) == 1
    assert len(uow.events) == 1
    assert len(uow.outbox_events) == 1
