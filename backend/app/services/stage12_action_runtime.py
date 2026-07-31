from __future__ import annotations

import re
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_event_runtime import AgentActionSlot, AgentObjectiveRun
from app.schemas.stage12_action_runtime import ActionRuntimeStatus, ActionSlotControlV1


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ACTION_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "denied", "cancelled", "expired"}),
    "running": frozenset({"proposed", "denied", "degraded", "failed", "expired"}),
    "proposed": frozenset({"pending_confirmation", "denied", "failed", "expired"}),
    "pending_confirmation": frozenset(
        {"confirmed", "rejected", "conflicted", "cancelled", "expired"}
    ),
    "confirmed": frozenset({"executed", "conflicted", "failed"}),
}


class Stage12ActionConflict(RuntimeError):
    pass


class Stage12ActionNotFound(RuntimeError):
    pass


class Stage12ActionRuntimeRepository(Protocol):
    def get_objective(self, objective_id: UUID) -> AgentObjectiveRun | None: ...

    def get_objective_by_key(
        self, run_id: UUID, objective_key: str
    ) -> AgentObjectiveRun | None: ...

    def add_objective(self, value: AgentObjectiveRun) -> None: ...

    def list_objectives(self, run_id: UUID) -> list[AgentObjectiveRun]: ...

    def get_objective_by_command(
        self, run_id: UUID, command_id: UUID
    ) -> AgentObjectiveRun | None: ...

    def get_action_by_idempotency(self, value: str) -> AgentActionSlot | None: ...

    def get_action_by_private_payload_ref(
        self, value: str
    ) -> AgentActionSlot | None: ...

    def get_action(
        self, slot_id: UUID, *, for_update: bool = False
    ) -> AgentActionSlot | None: ...

    def add_action(self, value: AgentActionSlot) -> None: ...

    def list_actions(self, run_id: UUID) -> list[AgentActionSlot]: ...

    def get_action_by_command(
        self, run_id: UUID, command_id: UUID
    ) -> AgentActionSlot | None: ...


class InMemoryStage12ActionRuntimeRepository:
    def __init__(self) -> None:
        self.objectives: list[AgentObjectiveRun] = []
        self.action_slots: list[AgentActionSlot] = []

    def get_objective(self, objective_id: UUID) -> AgentObjectiveRun | None:
        return next((item for item in self.objectives if item.id == objective_id), None)

    def get_objective_by_key(
        self, run_id: UUID, objective_key: str
    ) -> AgentObjectiveRun | None:
        return next(
            (
                item
                for item in self.objectives
                if item.run_id == run_id and item.objective_key == objective_key
            ),
            None,
        )

    def add_objective(self, value: AgentObjectiveRun) -> None:
        self.objectives.append(value)

    def list_objectives(self, run_id: UUID) -> list[AgentObjectiveRun]:
        return sorted(
            (item for item in self.objectives if item.run_id == run_id),
            key=lambda item: item.objective_key,
        )

    def get_objective_by_command(
        self, run_id: UUID, command_id: UUID
    ) -> AgentObjectiveRun | None:
        return next(
            (
                item
                for item in self.objectives
                if item.run_id == run_id and item.command_id == command_id
            ),
            None,
        )

    def get_action_by_idempotency(self, value: str) -> AgentActionSlot | None:
        return next(
            (item for item in self.action_slots if item.idempotency_key_hash == value),
            None,
        )

    def get_action_by_private_payload_ref(self, value: str) -> AgentActionSlot | None:
        return next(
            (item for item in self.action_slots if item.private_payload_ref == value),
            None,
        )

    def get_action(
        self, slot_id: UUID, *, for_update: bool = False
    ) -> AgentActionSlot | None:
        del for_update
        return next((item for item in self.action_slots if item.id == slot_id), None)

    def add_action(self, value: AgentActionSlot) -> None:
        self.action_slots.append(value)

    def list_actions(self, run_id: UUID) -> list[AgentActionSlot]:
        return sorted(
            (item for item in self.action_slots if item.run_id == run_id),
            key=lambda item: item.slot_key,
        )

    def get_action_by_command(
        self, run_id: UUID, command_id: UUID
    ) -> AgentActionSlot | None:
        objective = self.get_objective_by_command(run_id, command_id)
        if objective is None:
            return None
        return next(
            (
                item
                for item in self.action_slots
                if item.run_id == run_id and item.objective_run_id == objective.id
            ),
            None,
        )


class SqlAlchemyStage12ActionRuntimeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_objective(self, objective_id: UUID) -> AgentObjectiveRun | None:
        pending = next(
            (
                item
                for item in self.session.new
                if isinstance(item, AgentObjectiveRun) and item.id == objective_id
            ),
            None,
        )
        return pending or self.session.get(AgentObjectiveRun, objective_id)

    def get_objective_by_key(
        self, run_id: UUID, objective_key: str
    ) -> AgentObjectiveRun | None:
        pending = next(
            (
                item
                for item in self.session.new
                if isinstance(item, AgentObjectiveRun)
                and item.run_id == run_id
                and item.objective_key == objective_key
            ),
            None,
        )
        if pending is not None:
            return pending
        return self.session.scalar(
            select(AgentObjectiveRun).where(
                AgentObjectiveRun.run_id == run_id,
                AgentObjectiveRun.objective_key == objective_key,
            )
        )

    def add_objective(self, value: AgentObjectiveRun) -> None:
        self.session.add(value)
        self.session.flush()

    def list_objectives(self, run_id: UUID) -> list[AgentObjectiveRun]:
        return list(
            self.session.scalars(
                select(AgentObjectiveRun)
                .where(AgentObjectiveRun.run_id == run_id)
                .order_by(AgentObjectiveRun.objective_key)
            )
        )

    def get_objective_by_command(
        self, run_id: UUID, command_id: UUID
    ) -> AgentObjectiveRun | None:
        return self.session.scalar(
            select(AgentObjectiveRun).where(
                AgentObjectiveRun.run_id == run_id,
                AgentObjectiveRun.command_id == command_id,
            )
        )

    def get_action_by_idempotency(self, value: str) -> AgentActionSlot | None:
        pending = next(
            (
                item
                for item in self.session.new
                if isinstance(item, AgentActionSlot)
                and item.idempotency_key_hash == value
            ),
            None,
        )
        if pending is not None:
            return pending
        return self.session.scalar(
            select(AgentActionSlot).where(AgentActionSlot.idempotency_key_hash == value)
        )

    def get_action_by_private_payload_ref(self, value: str) -> AgentActionSlot | None:
        pending = next(
            (
                item
                for item in self.session.new
                if isinstance(item, AgentActionSlot)
                and item.private_payload_ref == value
            ),
            None,
        )
        if pending is not None:
            return pending
        return self.session.scalar(
            select(AgentActionSlot).where(AgentActionSlot.private_payload_ref == value)
        )

    def get_action(
        self, slot_id: UUID, *, for_update: bool = False
    ) -> AgentActionSlot | None:
        statement = select(AgentActionSlot).where(AgentActionSlot.id == slot_id)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def add_action(self, value: AgentActionSlot) -> None:
        self.session.add(value)
        self.session.flush()

    def list_actions(self, run_id: UUID) -> list[AgentActionSlot]:
        return list(
            self.session.scalars(
                select(AgentActionSlot)
                .where(AgentActionSlot.run_id == run_id)
                .order_by(AgentActionSlot.slot_key)
            )
        )

    def get_action_by_command(
        self, run_id: UUID, command_id: UUID
    ) -> AgentActionSlot | None:
        return self.session.scalar(
            select(AgentActionSlot)
            .join(
                AgentObjectiveRun,
                AgentObjectiveRun.id == AgentActionSlot.objective_run_id,
            )
            .where(
                AgentActionSlot.run_id == run_id,
                AgentObjectiveRun.command_id == command_id,
            )
        )


def create_objective_run(
    repository: Stage12ActionRuntimeRepository,
    *,
    run_id: UUID,
    objective_key: str,
    kind: str,
    required: bool,
    dependency_keys: tuple[str, ...],
) -> AgentObjectiveRun:
    existing = repository.get_objective_by_key(run_id, objective_key)
    if existing is not None:
        if (
            existing.kind != kind
            or existing.required != required
            or tuple(existing.dependency_keys) != dependency_keys
        ):
            raise Stage12ActionConflict("objective_idempotency_conflict")
        return existing
    value = AgentObjectiveRun(
        id=uuid4(),
        run_id=run_id,
        objective_key=objective_key,
        kind=kind,
        required=required,
        status="queued",
        dependency_keys=list(dependency_keys),
        command_id=None,
        result_artifact_id=None,
        error_code=None,
    )
    repository.add_objective(value)
    return value


def create_action_slot(
    repository: Stage12ActionRuntimeRepository,
    *,
    run_id: UUID,
    objective_run_id: UUID,
    slot_key: str,
    action_kind: str,
    control: ActionSlotControlV1,
    private_payload_ref: str,
    target_scope_hash: str,
    data_version_hash: str | None,
    idempotency_key_hash: str,
) -> AgentActionSlot:
    _require_hash(target_scope_hash)
    _require_hash(idempotency_key_hash)
    if data_version_hash is not None:
        _require_hash(data_version_hash)
    existing = repository.get_action_by_idempotency(idempotency_key_hash)
    if existing is not None:
        if (
            existing.run_id != run_id
            or existing.objective_run_id != objective_run_id
            or existing.slot_key != slot_key
            or existing.action_kind != action_kind
            or existing.control_json != control.model_dump(mode="json")
            or existing.private_payload_ref != private_payload_ref
            or existing.target_scope_hash != target_scope_hash
            or existing.data_version_hash != data_version_hash
        ):
            raise Stage12ActionConflict("action_idempotency_conflict")
        return existing
    value = AgentActionSlot(
        id=uuid4(),
        run_id=run_id,
        objective_run_id=objective_run_id,
        slot_key=slot_key,
        action_kind=action_kind,
        status="queued",
        proposal_version=1,
        control_json=control.model_dump(mode="json"),
        private_payload_ref=private_payload_ref,
        target_scope_hash=target_scope_hash,
        data_version_hash=data_version_hash,
        materialized_resource_id=None,
        execution_ticket_id=None,
        idempotency_key_hash=idempotency_key_hash,
    )
    repository.add_action(value)
    return value


def transition_action_slot(
    repository: Stage12ActionRuntimeRepository,
    *,
    slot_id: UUID,
    expected_proposal_version: int,
    target_status: ActionRuntimeStatus,
) -> AgentActionSlot:
    value = repository.get_action(slot_id, for_update=True)
    if value is None:
        raise Stage12ActionNotFound("action_slot_not_found")
    if value.proposal_version != expected_proposal_version:
        raise Stage12ActionConflict("action_version_conflict")
    if target_status not in _ACTION_TRANSITIONS.get(value.status, frozenset()):
        raise Stage12ActionConflict("action_invalid_state")
    value.status = target_status
    value.proposal_version += 1
    return value


def _require_hash(value: str) -> None:
    if not _HASH_RE.fullmatch(value):
        raise ValueError("action_runtime_hash_invalid")


__all__ = [
    "InMemoryStage12ActionRuntimeRepository",
    "SqlAlchemyStage12ActionRuntimeRepository",
    "Stage12ActionConflict",
    "Stage12ActionNotFound",
    "create_action_slot",
    "create_objective_run",
    "transition_action_slot",
]
