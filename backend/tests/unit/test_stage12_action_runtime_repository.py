from uuid import uuid4

import pytest

from app.schemas.stage12_action_runtime import ActionSlotControlV1
from app.services.stage12_action_runtime import (
    InMemoryStage12ActionRuntimeRepository,
    Stage12ActionConflict,
    create_action_slot,
    create_objective_run,
    transition_action_slot,
)


def _control() -> ActionSlotControlV1:
    return ActionSlotControlV1(
        action_kind="task.create",
        confirmation_policy="required",
        dependency_keys=(),
        evidence_refs=("ev-01",),
        editable_fields=(),
        safe_summary="创建一条待确认任务",
    )


def test_objective_and_action_persistence_are_idempotent() -> None:
    repository = InMemoryStage12ActionRuntimeRepository()
    run_id = uuid4()
    objective = create_objective_run(
        repository,
        run_id=run_id,
        objective_key="obj-01",
        kind="action",
        required=True,
        dependency_keys=(),
    )
    replayed_objective = create_objective_run(
        repository,
        run_id=run_id,
        objective_key="obj-01",
        kind="action",
        required=True,
        dependency_keys=(),
    )
    created = create_action_slot(
        repository,
        run_id=run_id,
        objective_run_id=objective.id,
        slot_key="act-01",
        action_kind="task.create",
        control=_control(),
        private_payload_ref="agent-private-input:" + str(uuid4()),
        target_scope_hash="a" * 64,
        data_version_hash=None,
        idempotency_key_hash="b" * 64,
    )
    replayed = create_action_slot(
        repository,
        run_id=run_id,
        objective_run_id=objective.id,
        slot_key="act-01",
        action_kind="task.create",
        control=_control(),
        private_payload_ref=created.private_payload_ref,
        target_scope_hash="a" * 64,
        data_version_hash=None,
        idempotency_key_hash="b" * 64,
    )

    assert replayed_objective.id == objective.id
    assert replayed.id == created.id
    assert len(repository.objectives) == 1
    assert len(repository.action_slots) == 1


def test_action_transition_checks_proposal_version() -> None:
    repository = InMemoryStage12ActionRuntimeRepository()
    objective = create_objective_run(
        repository,
        run_id=uuid4(),
        objective_key="obj-01",
        kind="action",
        required=True,
        dependency_keys=(),
    )
    slot = create_action_slot(
        repository,
        run_id=objective.run_id,
        objective_run_id=objective.id,
        slot_key="act-01",
        action_kind="task.create",
        control=_control(),
        private_payload_ref="agent-private-input:" + str(uuid4()),
        target_scope_hash="a" * 64,
        data_version_hash=None,
        idempotency_key_hash="b" * 64,
    )

    transition_action_slot(
        repository,
        slot_id=slot.id,
        expected_proposal_version=1,
        target_status="running",
    )
    with pytest.raises(Stage12ActionConflict, match="action_version_conflict"):
        transition_action_slot(
            repository,
            slot_id=slot.id,
            expected_proposal_version=1,
            target_status="proposed",
        )
