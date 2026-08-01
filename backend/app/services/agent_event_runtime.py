from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_event_runtime import (
    AgentArtifact,
    AgentCommand,
    AgentEvent,
    AgentOutboxEvent,
    AgentPrivateInput,
    AgentRunCheckpoint,
    AgentWorkflowRun,
)
from app.schemas.agent_event_runtime import AgentEventEnvelope, RunCheckpointControl


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_STATUSES = frozenset(
    {"completed", "degraded", "failed", "cancelled", "timed_out"}
)


class RuntimeConflict(RuntimeError):
    pass


class RuntimeScopeDrift(RuntimeError):
    pass


class RuntimeNotFound(RuntimeError):
    pass


class AgentEventRuntimeUnitOfWork(Protocol):
    def flush(self) -> None: ...

    def get_run(
        self, run_id: UUID, *, for_update: bool = False
    ) -> AgentWorkflowRun | None: ...

    def get_run_by_idempotency(self, key_hash: str) -> AgentWorkflowRun | None: ...

    def add_run(self, run: AgentWorkflowRun) -> None: ...

    def next_checkpoint_no(self, run_id: UUID) -> int: ...

    def add_checkpoint(self, checkpoint: AgentRunCheckpoint) -> None: ...

    def list_checkpoints(self, run_id: UUID) -> list[AgentRunCheckpoint]: ...

    def next_event_sequence(self, run_id: UUID) -> int: ...

    def add_event(self, event: AgentEvent) -> None: ...

    def add_outbox_event(self, event: AgentOutboxEvent) -> None: ...

    def get_outbox_event_by_event_id(
        self, event_id: UUID
    ) -> AgentOutboxEvent | None: ...

    def add_private_input(self, value: AgentPrivateInput) -> None: ...

    def get_private_input(
        self, input_id: UUID, *, for_update: bool = False
    ) -> AgentPrivateInput | None: ...

    def get_command(
        self, command_id: UUID, *, for_update: bool = False
    ) -> AgentCommand | None: ...

    def list_commands(
        self, run_id: UUID, *, for_update: bool = False
    ) -> list[AgentCommand]: ...

    def next_command_sequence(self, run_id: UUID) -> int: ...

    def add_command(self, command: AgentCommand) -> None: ...

    def add_artifact(self, artifact: AgentArtifact) -> None: ...

    def get_artifact(self, artifact_id: UUID) -> AgentArtifact | None: ...

    def list_artifacts(self, run_id: UUID) -> list[AgentArtifact]: ...

    def list_events(
        self, run_id: UUID, *, after_sequence: int = 0
    ) -> list[AgentEvent]: ...


@dataclass(frozen=True, slots=True)
class AgentRunCreation:
    run: AgentWorkflowRun
    replayed: bool


class InMemoryAgentEventRuntimeUnitOfWork:
    def __init__(self) -> None:
        self.runs: list[AgentWorkflowRun] = []
        self.checkpoints: list[AgentRunCheckpoint] = []
        self.commands: list[AgentCommand] = []
        self.events: list[AgentEvent] = []
        self.outbox_events: list[AgentOutboxEvent] = []
        self.artifacts: list[AgentArtifact] = []
        self.private_inputs: list[AgentPrivateInput] = []

    def flush(self) -> None:
        return None

    def get_run(
        self, run_id: UUID, *, for_update: bool = False
    ) -> AgentWorkflowRun | None:
        del for_update
        return next((run for run in self.runs if run.id == run_id), None)

    def get_run_by_idempotency(self, key_hash: str) -> AgentWorkflowRun | None:
        return next(
            (run for run in self.runs if run.idempotency_key_hash == key_hash),
            None,
        )

    def add_run(self, run: AgentWorkflowRun) -> None:
        self.runs.append(run)

    def next_checkpoint_no(self, run_id: UUID) -> int:
        return 1 + max(
            (item.checkpoint_no for item in self.checkpoints if item.run_id == run_id),
            default=0,
        )

    def add_checkpoint(self, checkpoint: AgentRunCheckpoint) -> None:
        self.checkpoints.append(checkpoint)

    def list_checkpoints(self, run_id: UUID) -> list[AgentRunCheckpoint]:
        return sorted(
            (item for item in self.checkpoints if item.run_id == run_id),
            key=lambda item: item.checkpoint_no,
        )

    def next_event_sequence(self, run_id: UUID) -> int:
        return 1 + max(
            (item.sequence for item in self.events if item.run_id == run_id),
            default=0,
        )

    def add_event(self, event: AgentEvent) -> None:
        self.events.append(event)

    def add_outbox_event(self, event: AgentOutboxEvent) -> None:
        self.outbox_events.append(event)

    def get_outbox_event_by_event_id(self, event_id: UUID) -> AgentOutboxEvent | None:
        return next(
            (
                item
                for item in self.outbox_events
                if item.event_id == event_id and item.aggregate_type == "agent_command"
            ),
            None,
        )

    def add_private_input(self, value: AgentPrivateInput) -> None:
        self.private_inputs.append(value)

    def get_private_input(
        self, input_id: UUID, *, for_update: bool = False
    ) -> AgentPrivateInput | None:
        del for_update
        return next((item for item in self.private_inputs if item.id == input_id), None)

    def get_command(
        self, command_id: UUID, *, for_update: bool = False
    ) -> AgentCommand | None:
        del for_update
        return next((item for item in self.commands if item.id == command_id), None)

    def list_commands(
        self, run_id: UUID, *, for_update: bool = False
    ) -> list[AgentCommand]:
        del for_update
        return sorted(
            (item for item in self.commands if item.run_id == run_id),
            key=lambda item: item.sequence,
        )

    def next_command_sequence(self, run_id: UUID) -> int:
        return 1 + max(
            (item.sequence for item in self.commands if item.run_id == run_id),
            default=0,
        )

    def add_command(self, command: AgentCommand) -> None:
        self.commands.append(command)

    def add_artifact(self, artifact: AgentArtifact) -> None:
        self.artifacts.append(artifact)

    def get_artifact(self, artifact_id: UUID) -> AgentArtifact | None:
        return next((item for item in self.artifacts if item.id == artifact_id), None)

    def list_artifacts(self, run_id: UUID) -> list[AgentArtifact]:
        return [item for item in self.artifacts if item.run_id == run_id]

    def list_events(self, run_id: UUID, *, after_sequence: int = 0) -> list[AgentEvent]:
        return sorted(
            (
                event
                for event in self.events
                if event.run_id == run_id and event.sequence > after_sequence
            ),
            key=lambda event: event.sequence,
        )


class SqlAlchemyAgentEventRuntimeUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def flush(self) -> None:
        self.session.flush()

    def get_run(
        self, run_id: UUID, *, for_update: bool = False
    ) -> AgentWorkflowRun | None:
        pending = next(
            (
                item
                for item in self.session.new
                if isinstance(item, AgentWorkflowRun) and item.id == run_id
            ),
            None,
        )
        if pending is not None:
            return pending
        statement = select(AgentWorkflowRun).where(AgentWorkflowRun.id == run_id)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_run_by_idempotency(self, key_hash: str) -> AgentWorkflowRun | None:
        pending = next(
            (
                item
                for item in self.session.new
                if isinstance(item, AgentWorkflowRun)
                and item.idempotency_key_hash == key_hash
            ),
            None,
        )
        if pending is not None:
            return pending
        return self.session.scalar(
            select(AgentWorkflowRun).where(
                AgentWorkflowRun.idempotency_key_hash == key_hash
            )
        )

    def add_run(self, run: AgentWorkflowRun) -> None:
        self.session.add(run)

    def next_checkpoint_no(self, run_id: UUID) -> int:
        current = self.session.scalar(
            select(func.max(AgentRunCheckpoint.checkpoint_no)).where(
                AgentRunCheckpoint.run_id == run_id
            )
        )
        pending = max(
            (
                item.checkpoint_no
                for item in self.session.new
                if isinstance(item, AgentRunCheckpoint) and item.run_id == run_id
            ),
            default=0,
        )
        return max(int(current or 0), pending) + 1

    def add_checkpoint(self, checkpoint: AgentRunCheckpoint) -> None:
        self.session.add(checkpoint)

    def list_checkpoints(self, run_id: UUID) -> list[AgentRunCheckpoint]:
        persisted = list(
            self.session.scalars(
                select(AgentRunCheckpoint)
                .where(AgentRunCheckpoint.run_id == run_id)
                .order_by(AgentRunCheckpoint.checkpoint_no)
            )
        )
        persisted_ids = {item.id for item in persisted}
        pending = [
            item
            for item in self.session.new
            if isinstance(item, AgentRunCheckpoint)
            and item.run_id == run_id
            and item.id not in persisted_ids
        ]
        return sorted((*persisted, *pending), key=lambda item: item.checkpoint_no)

    def next_event_sequence(self, run_id: UUID) -> int:
        current = self.session.scalar(
            select(func.max(AgentEvent.sequence)).where(AgentEvent.run_id == run_id)
        )
        pending = max(
            (
                item.sequence
                for item in self.session.new
                if isinstance(item, AgentEvent) and item.run_id == run_id
            ),
            default=0,
        )
        return max(int(current or 0), pending) + 1

    def add_event(self, event: AgentEvent) -> None:
        self.session.add(event)

    def add_outbox_event(self, event: AgentOutboxEvent) -> None:
        self.session.add(event)

    def get_outbox_event_by_event_id(self, event_id: UUID) -> AgentOutboxEvent | None:
        pending = next(
            (
                item
                for item in self.session.new
                if isinstance(item, AgentOutboxEvent)
                and item.event_id == event_id
                and item.aggregate_type == "agent_command"
            ),
            None,
        )
        if pending is not None:
            return pending
        return self.session.scalar(
            select(AgentOutboxEvent).where(
                AgentOutboxEvent.event_id == event_id,
                AgentOutboxEvent.aggregate_type == "agent_command",
            )
        )

    def add_private_input(self, value: AgentPrivateInput) -> None:
        self.session.add(value)

    def get_private_input(
        self, input_id: UUID, *, for_update: bool = False
    ) -> AgentPrivateInput | None:
        statement = select(AgentPrivateInput).where(AgentPrivateInput.id == input_id)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_command(
        self, command_id: UUID, *, for_update: bool = False
    ) -> AgentCommand | None:
        pending = next(
            (
                item
                for item in self.session.new
                if isinstance(item, AgentCommand) and item.id == command_id
            ),
            None,
        )
        if pending is not None:
            return pending
        statement = select(AgentCommand).where(AgentCommand.id == command_id)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def list_commands(
        self, run_id: UUID, *, for_update: bool = False
    ) -> list[AgentCommand]:
        statement = (
            select(AgentCommand)
            .where(AgentCommand.run_id == run_id)
            .order_by(AgentCommand.sequence)
        )
        if for_update:
            statement = statement.with_for_update()
        persisted = list(self.session.scalars(statement))
        persisted_ids = {item.id for item in persisted}
        pending = [
            item
            for item in self.session.new
            if isinstance(item, AgentCommand)
            and item.run_id == run_id
            and item.id not in persisted_ids
        ]
        return sorted((*persisted, *pending), key=lambda item: item.sequence)

    def next_command_sequence(self, run_id: UUID) -> int:
        current = self.session.scalar(
            select(func.max(AgentCommand.sequence)).where(AgentCommand.run_id == run_id)
        )
        pending = max(
            (
                item.sequence
                for item in self.session.new
                if isinstance(item, AgentCommand) and item.run_id == run_id
            ),
            default=0,
        )
        return max(int(current or 0), pending) + 1

    def add_command(self, command: AgentCommand) -> None:
        self.session.add(command)

    def add_artifact(self, artifact: AgentArtifact) -> None:
        self.session.add(artifact)

    def get_artifact(self, artifact_id: UUID) -> AgentArtifact | None:
        pending = next(
            (
                item
                for item in self.session.new
                if isinstance(item, AgentArtifact) and item.id == artifact_id
            ),
            None,
        )
        if pending is not None:
            return pending
        return self.session.get(AgentArtifact, artifact_id)

    def list_artifacts(self, run_id: UUID) -> list[AgentArtifact]:
        persisted = list(
            self.session.scalars(
                select(AgentArtifact).where(AgentArtifact.run_id == run_id)
            )
        )
        persisted_ids = {item.id for item in persisted}
        pending = [
            item
            for item in self.session.new
            if isinstance(item, AgentArtifact)
            and item.run_id == run_id
            and item.id not in persisted_ids
        ]
        return [*persisted, *pending]

    def list_events(self, run_id: UUID, *, after_sequence: int = 0) -> list[AgentEvent]:
        persisted = list(
            self.session.scalars(
                select(AgentEvent)
                .where(
                    AgentEvent.run_id == run_id,
                    AgentEvent.sequence > after_sequence,
                )
                .order_by(AgentEvent.sequence)
            )
        )
        pending = [
            item
            for item in self.session.new
            if isinstance(item, AgentEvent)
            and item.run_id == run_id
            and item.sequence > after_sequence
        ]
        return sorted((*persisted, *pending), key=lambda item: item.sequence)


def create_agent_run(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    workspace_id: UUID,
    root_employee_id: UUID,
    target_record_id: UUID | None = None,
    scope_hash: str,
    idempotency_key_hash: str,
    deadline_at: datetime,
    now: datetime,
    workflow_version: str = "stage10-agent-event-runtime.v1",
) -> AgentRunCreation:
    _require_hash(scope_hash)
    _require_hash(idempotency_key_hash)
    existing = uow.get_run_by_idempotency(idempotency_key_hash)
    if existing is not None:
        if existing.workspace_id != workspace_id or existing.scope_hash != scope_hash:
            raise RuntimeConflict("agent_run_idempotency_conflict")
        return AgentRunCreation(run=existing, replayed=True)
    if deadline_at <= now:
        raise ValueError("agent_run_deadline_invalid")

    run_id = uuid4()
    run = AgentWorkflowRun(
        id=run_id,
        workspace_id=workspace_id,
        root_employee_id=root_employee_id,
        target_record_id=target_record_id,
        parent_run_id=None,
        workflow_version=workflow_version,
        status="accepted",
        scope_hash=scope_hash,
        data_version_hash=None,
        deadline_at=deadline_at,
        lease_owner=None,
        lease_expires_at=None,
        idempotency_key_hash=idempotency_key_hash,
        safe_result_ref=None,
        version=1,
    )
    uow.add_run(run)
    # The models intentionally avoid ORM relationships.  Flush the parent row
    # before append-only children so PostgreSQL FK ordering is deterministic
    # while the surrounding transaction remains atomic.
    uow.flush()
    checkpoint = AgentRunCheckpoint(
        id=uuid4(),
        run_id=run_id,
        checkpoint_no=uow.next_checkpoint_no(run_id),
        node_key="accepted",
        status="accepted",
        control_json=RunCheckpointControl(
            completed_command_ids=(),
            pending_command_ids=(),
            retry_count=0,
            next_action="dispatch",
        ).model_dump(mode="json"),
        authorization_hash=scope_hash,
        data_version_hash=None,
    )
    uow.add_checkpoint(checkpoint)
    envelope = AgentEventEnvelope(
        event_id=uuid4(),
        run_id=run_id,
        causation_id=run_id,
        correlation_id=run_id,
        sequence=uow.next_event_sequence(run_id),
        event_type="run.accepted",
        status="accepted",
        source_role="supervisor",
        safe_summary="任务已受理",
        occurred_at=now,
    )
    _persist_event_and_outbox(uow, envelope)
    return AgentRunCreation(run=run, replayed=False)


def claim_run_lease(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    lease_owner: str,
    now: datetime,
    lease_seconds: int,
) -> AgentWorkflowRun:
    if not lease_owner.strip() or not 1 <= lease_seconds <= 300:
        raise ValueError("agent_run_lease_invalid")
    run = _require_run(uow, run_id, for_update=True)
    if run.status in _TERMINAL_STATUSES or run.deadline_at <= now:
        raise RuntimeConflict("agent_run_not_claimable")
    if (
        run.lease_owner is not None
        and run.lease_owner != lease_owner
        and run.lease_expires_at is not None
        and run.lease_expires_at > now
    ):
        raise RuntimeConflict("agent_run_lease_conflict")
    run.lease_owner = lease_owner
    run.lease_expires_at = now + timedelta(seconds=lease_seconds)
    run.status = "running"
    run.version += 1
    return run


def append_checkpoint_and_event(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    expected_version: int,
    lease_owner: str,
    authorization_hash: str,
    node_key: str,
    control: RunCheckpointControl,
    event: AgentEventEnvelope,
) -> AgentWorkflowRun:
    _require_hash(authorization_hash)
    run = _require_run(uow, run_id, for_update=True)
    if run.scope_hash != authorization_hash:
        raise RuntimeScopeDrift("agent_run_scope_drift")
    if run.version != expected_version or run.lease_owner != lease_owner:
        raise RuntimeConflict("agent_run_version_or_lease_conflict")
    if event.run_id != run_id or event.sequence != uow.next_event_sequence(run_id):
        raise RuntimeConflict("agent_event_sequence_conflict")
    checkpoint = AgentRunCheckpoint(
        id=uuid4(),
        run_id=run_id,
        checkpoint_no=uow.next_checkpoint_no(run_id),
        node_key=node_key,
        status=event.status,
        control_json=control.model_dump(mode="json"),
        authorization_hash=authorization_hash,
        data_version_hash=run.data_version_hash,
    )
    uow.add_checkpoint(checkpoint)
    _persist_event_and_outbox(uow, event)
    run.status = event.status
    run.version += 1
    if run.status in _TERMINAL_STATUSES:
        run.lease_owner = None
        run.lease_expires_at = None
    return run


def replay_safe_events(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    after_sequence: int,
) -> list[AgentEvent]:
    _require_run(uow, run_id)
    if after_sequence < 0:
        raise ValueError("agent_event_cursor_invalid")
    return uow.list_events(run_id, after_sequence=after_sequence)


def append_agent_runtime_event(
    uow: AgentEventRuntimeUnitOfWork,
    envelope: AgentEventEnvelope,
    *,
    authorization_hash: str,
    update_run_status: str | None = None,
) -> AgentEvent:
    _require_hash(authorization_hash)
    run = _require_run(uow, envelope.run_id, for_update=True)
    if run.scope_hash != authorization_hash:
        raise RuntimeScopeDrift("agent_run_scope_drift")
    if envelope.sequence != uow.next_event_sequence(run.id):
        raise RuntimeConflict("agent_event_sequence_conflict")
    _persist_event_and_outbox(uow, envelope)
    if update_run_status is not None:
        if update_run_status not in {
            "accepted",
            "queued",
            "running",
            "waiting_approval",
            "completed",
            "degraded",
            "failed",
            "cancelled",
            "timed_out",
        }:
            raise ValueError("agent_run_status_invalid")
        run.status = update_run_status
        run.version += 1
    event = uow.list_events(run.id, after_sequence=envelope.sequence - 1)[0]
    return event


def _persist_event_and_outbox(
    uow: AgentEventRuntimeUnitOfWork,
    envelope: AgentEventEnvelope,
) -> None:
    event = AgentEvent(
        id=envelope.event_id,
        run_id=envelope.run_id,
        command_id=envelope.command_id,
        event_type=envelope.event_type,
        sequence=envelope.sequence,
        causation_id=envelope.causation_id,
        correlation_id=envelope.correlation_id,
        source_role=envelope.source_role,
        source_capability=envelope.source_capability,
        status=envelope.status,
        safe_summary=envelope.safe_summary,
        artifact_ref=envelope.artifact_ref,
        metrics_json=dict(envelope.metrics),
    )
    uow.add_event(event)
    uow.add_outbox_event(
        AgentOutboxEvent(
            id=uuid4(),
            aggregate_type="agent_run",
            aggregate_id=envelope.run_id,
            topic="agent.events",
            event_id=envelope.event_id,
            payload_json=envelope.model_dump(mode="json"),
            published_at=None,
            publish_attempts=0,
            next_attempt_at=None,
            last_error_code=None,
        )
    )


def _require_run(
    uow: AgentEventRuntimeUnitOfWork,
    run_id: UUID,
    *,
    for_update: bool = False,
) -> AgentWorkflowRun:
    run = uow.get_run(run_id, for_update=for_update)
    if run is None:
        raise RuntimeNotFound("agent_run_not_found")
    return run


def _require_hash(value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError("agent_runtime_hash_invalid")


__all__ = [
    "AgentRunCreation",
    "InMemoryAgentEventRuntimeUnitOfWork",
    "RuntimeConflict",
    "RuntimeNotFound",
    "RuntimeScopeDrift",
    "SqlAlchemyAgentEventRuntimeUnitOfWork",
    "append_checkpoint_and_event",
    "append_agent_runtime_event",
    "claim_run_lease",
    "create_agent_run",
    "replay_safe_events",
]
