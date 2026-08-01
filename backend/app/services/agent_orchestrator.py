from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid4

from app.agents.agent_capability_registry import (
    registered_capabilities as capability_registry,
)
from app.models.agent_event_runtime import (
    AgentArtifact,
    AgentCommand,
    AgentOutboxEvent,
    AgentWorkflowRun,
)
from app.schemas.agent_event_runtime import (
    AgentCommandEnvelope,
    AgentEventEnvelope,
    RunCheckpointControl,
)
from app.services.agent_event_runtime import (
    AgentEventRuntimeUnitOfWork,
    RuntimeConflict,
    append_checkpoint_and_event,
    claim_run_lease,
)


_CAPABILITY_DEFINITIONS = capability_registry()
_CAPABILITIES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        capability: frozenset({definition.command_type})
        for capability, definition in _CAPABILITY_DEFINITIONS.items()
    }
)
_COMMAND_BY_CAPABILITY = MappingProxyType(
    {capability: next(iter(commands)) for capability, commands in _CAPABILITIES.items()}
)
_SAFE_PAYLOAD_REF = re.compile(
    r"^(?:stage08-idempotency|agent-private-input|telegram-message|record-snapshot):"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class OrchestratorError(RuntimeError):
    pass


class OrchestratorCapabilityDenied(OrchestratorError):
    pass


class OrchestratorScopeDrift(OrchestratorError):
    pass


@dataclass(frozen=True, slots=True)
class SpecialistSafeResult:
    storage_ref: str
    content_hash: str
    safe_summary: str
    metrics: dict[str, int] | None = None
    artifact_kind: str | None = None


@dataclass(frozen=True, slots=True)
class SpecialistCommandDispatch:
    target_capability: str
    payload_ref: str
    input_artifact_refs: tuple[UUID, ...] = ()
    required: bool = True
    command_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SpecialistExecutionResult:
    run: AgentWorkflowRun
    artifact: AgentArtifact
    replayed: bool


def registered_capabilities() -> tuple[str, ...]:
    return tuple(_CAPABILITIES)


def build_authorization_hash(
    *,
    workspace_id: UUID,
    employee_id: UUID,
    target_record_id: UUID | None,
    actor_user_id: str,
) -> str:
    payload = {
        "actor_user_id": actor_user_id,
        "employee_id": str(employee_id),
        "requested_action": "read_only",
        "target_record_id": None if target_record_id is None else str(target_record_id),
        "workspace_id": str(workspace_id),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def dispatch_specialist_command(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    target_capability: str,
    payload_ref: str,
    authorization_hash: str,
    now: datetime,
    command_id: UUID | None = None,
    input_artifact_refs: tuple[UUID, ...] = (),
) -> AgentCommand:
    if target_capability not in _CAPABILITIES:
        raise OrchestratorCapabilityDenied("capability_not_registered")
    if not _SAFE_PAYLOAD_REF.fullmatch(payload_ref):
        raise ValueError("specialist_payload_ref_invalid")
    run = uow.get_run(run_id, for_update=True)
    if run is None:
        raise OrchestratorError("agent_run_not_found")
    if run.scope_hash != authorization_hash:
        raise OrchestratorScopeDrift("scope_proof_mismatch")
    if run.deadline_at <= now or run.status not in {"accepted", "queued"}:
        raise OrchestratorError("agent_run_not_dispatchable")
    _validate_input_artifact_refs(
        uow,
        run_id=run.id,
        input_artifact_refs=input_artifact_refs,
        authorization_hash=authorization_hash,
        now=now,
    )

    command_id = command_id or uuid4()
    command_sequence = uow.next_command_sequence(run.id)
    command_key_hash = hashlib.sha256(
        f"{run.id}:{command_sequence}:{target_capability}".encode("utf-8")
    ).hexdigest()
    command = AgentCommand(
        id=command_id,
        run_id=run.id,
        parent_command_id=None,
        target_capability=target_capability,
        command_type=_COMMAND_BY_CAPABILITY[target_capability],
        sequence=command_sequence,
        payload_ref=payload_ref,
        deadline_at=run.deadline_at,
        idempotency_key_hash=command_key_hash,
        status="queued",
    )
    envelope = AgentCommandEnvelope(
        command_id=command.id,
        run_id=run.id,
        parent_command_id=None,
        causation_id=run.id,
        correlation_id=run.id,
        sequence=command.sequence,
        target_capability=target_capability,
        command_type=_COMMAND_BY_CAPABILITY[target_capability],
        scope_proof_ref=f"scope:sha256:{authorization_hash}",
        input_artifact_refs=input_artifact_refs,
        deadline_at=run.deadline_at,
        idempotency_key_hash=command.idempotency_key_hash,
    )
    uow.add_command(command)
    uow.flush()
    uow.add_outbox_event(
        AgentOutboxEvent(
            id=uuid4(),
            aggregate_type="agent_command",
            aggregate_id=run.id,
            topic=f"agent.commands.{target_capability}",
            event_id=command.id,
            payload_json=envelope.model_dump(mode="json"),
            published_at=None,
            publish_attempts=0,
            next_attempt_at=None,
            last_error_code=None,
        )
    )

    owner = "supervisor-dispatch"
    claim_run_lease(
        uow,
        run_id=run.id,
        lease_owner=owner,
        now=now,
        lease_seconds=30,
    )
    append_checkpoint_and_event(
        uow,
        run_id=run.id,
        expected_version=run.version,
        lease_owner=owner,
        authorization_hash=authorization_hash,
        node_key="command_dispatched",
        control=RunCheckpointControl(
            completed_command_ids=(),
            pending_command_ids=(command.id,),
            retry_count=0,
            next_action="wait_children",
        ),
        event=_event(
            uow,
            run_id=run.id,
            command_id=command.id,
            event_type="command.dispatched",
            status="queued",
            source_role="supervisor",
            safe_summary="只读分析任务已派发",
            occurred_at=now,
        ),
    )
    run.lease_owner = None
    run.lease_expires_at = None
    return command


def dispatch_specialist_commands(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    dispatches: tuple[SpecialistCommandDispatch, ...],
    authorization_hash: str,
    now: datetime,
) -> tuple[AgentCommand, ...]:
    if not dispatches or len(dispatches) > 16:
        raise ValueError("specialist_dispatch_count_invalid")
    identities = tuple(
        (item.target_capability, item.input_artifact_refs) for item in dispatches
    )
    if len(set(identities)) != len(identities):
        raise ValueError("specialist_dispatch_duplicate_objective")
    existing = uow.list_commands(run_id, for_update=True)
    if existing:
        expected = [
            (
                item.target_capability,
                _COMMAND_BY_CAPABILITY.get(item.target_capability),
                item.payload_ref,
                item.input_artifact_refs,
            )
            for item in dispatches
        ]
        actual = []
        for item in existing:
            envelope = _durable_command_envelope(uow, item)
            actual.append(
                (
                    item.target_capability,
                    item.command_type,
                    item.payload_ref,
                    envelope.input_artifact_refs,
                )
            )
        if actual == expected:
            return tuple(existing)
        raise OrchestratorError("agent_run_dispatch_conflict")

    commands = tuple(
        dispatch_specialist_command(
            uow,
            run_id=run_id,
            target_capability=item.target_capability,
            payload_ref=item.payload_ref,
            authorization_hash=authorization_hash,
            now=now,
            command_id=item.command_id,
            input_artifact_refs=item.input_artifact_refs,
        )
        for item in dispatches
    )
    run = uow.get_run(run_id, for_update=True)
    if run is None:
        raise OrchestratorError("agent_run_not_found")
    owner = "supervisor-fan-out"
    claim_run_lease(
        uow,
        run_id=run.id,
        lease_owner=owner,
        now=now,
        lease_seconds=30,
    )
    append_checkpoint_and_event(
        uow,
        run_id=run.id,
        expected_version=run.version,
        lease_owner=owner,
        authorization_hash=authorization_hash,
        node_key="commands_dispatched",
        control=RunCheckpointControl(
            completed_command_ids=(),
            pending_command_ids=tuple(item.id for item in commands),
            required_command_ids=tuple(
                command.id
                for command, dispatch in zip(commands, dispatches, strict=True)
                if dispatch.required
            ),
            optional_command_ids=tuple(
                command.id
                for command, dispatch in zip(commands, dispatches, strict=True)
                if not dispatch.required
            ),
            retry_count=0,
            next_action="wait_children",
        ),
        event=_event(
            uow,
            run_id=run.id,
            command_id=commands[0].id,
            event_type="command.dispatched",
            status="queued",
            source_role="supervisor",
            safe_summary=f"已派发 {len(commands)} 个受控 Specialist 任务",
            occurred_at=now,
        ),
    )
    run.lease_owner = None
    run.lease_expires_at = None
    return commands


def dispatch_unlocked_specialist_command(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    parent_command_id: UUID,
    target_capability: str,
    payload_ref: str,
    input_artifact_refs: tuple[UUID, ...],
    authorization_hash: str,
    worker_id: str,
    now: datetime,
    command_id: UUID,
) -> AgentCommand:
    """Append one dependency-unlocked command under the current run lease."""

    if target_capability not in _CAPABILITIES:
        raise OrchestratorCapabilityDenied("capability_not_registered")
    if not _SAFE_PAYLOAD_REF.fullmatch(payload_ref):
        raise ValueError("specialist_payload_ref_invalid")
    run = uow.get_run(run_id, for_update=True)
    parent = uow.get_command(parent_command_id, for_update=True)
    if (
        run is None
        or parent is None
        or parent.run_id != run.id
        or parent.status != "completed"
        or run.scope_hash != authorization_hash
        or run.status != "running"
        or run.lease_owner != worker_id
        or run.deadline_at <= now
    ):
        raise OrchestratorError("agent_run_dependency_dispatch_invalid")
    existing = uow.get_command(command_id, for_update=True)
    if existing is not None:
        durable = _durable_command_envelope(uow, existing)
        if (
            existing.run_id == run.id
            and existing.parent_command_id == parent.id
            and existing.target_capability == target_capability
            and existing.payload_ref == payload_ref
            and durable.input_artifact_refs == input_artifact_refs
        ):
            return existing
        raise OrchestratorError("agent_dependency_dispatch_conflict")
    _validate_input_artifact_refs(
        uow,
        run_id=run.id,
        input_artifact_refs=input_artifact_refs,
        authorization_hash=authorization_hash,
        now=now,
    )
    sequence = uow.next_command_sequence(run.id)
    command_key_hash = hashlib.sha256(
        f"{run.id}:{sequence}:{target_capability}".encode("utf-8")
    ).hexdigest()
    command = AgentCommand(
        id=command_id,
        run_id=run.id,
        parent_command_id=parent.id,
        target_capability=target_capability,
        command_type=_COMMAND_BY_CAPABILITY[target_capability],
        sequence=sequence,
        payload_ref=payload_ref,
        deadline_at=run.deadline_at,
        idempotency_key_hash=command_key_hash,
        status="queued",
    )
    envelope = AgentCommandEnvelope(
        command_id=command.id,
        run_id=run.id,
        parent_command_id=parent.id,
        causation_id=parent.id,
        correlation_id=run.id,
        sequence=command.sequence,
        target_capability=target_capability,
        command_type=command.command_type,
        scope_proof_ref=f"scope:sha256:{authorization_hash}",
        input_artifact_refs=input_artifact_refs,
        deadline_at=run.deadline_at,
        idempotency_key_hash=command.idempotency_key_hash,
    )
    uow.add_command(command)
    uow.flush()
    uow.add_outbox_event(
        AgentOutboxEvent(
            id=uuid4(),
            aggregate_type="agent_command",
            aggregate_id=run.id,
            topic=f"agent.commands.{target_capability}",
            event_id=command.id,
            payload_json=envelope.model_dump(mode="json"),
            published_at=None,
            publish_attempts=0,
            next_attempt_at=None,
            last_error_code=None,
        )
    )
    return command


def validate_specialist_event(event: AgentEventEnvelope) -> AgentEventEnvelope:
    validated = AgentEventEnvelope.model_validate(event.model_dump())
    if validated.source_role != "specialist":
        raise ValueError("specialist_event_role_required")
    if validated.source_capability not in _CAPABILITIES:
        raise OrchestratorCapabilityDenied("capability_not_registered")
    return validated


def execute_read_only_specialist(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    command_id: UUID,
    authorization_hash: str,
    worker_id: str,
    now: datetime,
    execute: Callable[[], SpecialistSafeResult],
    fan_in: Callable[[], SpecialistSafeResult] | None = None,
    after_command_completed: Callable[[AgentArtifact], None] | None = None,
) -> SpecialistExecutionResult:
    command = uow.get_command(command_id, for_update=True)
    if command is None:
        raise OrchestratorError("agent_command_not_found")
    run = uow.get_run(command.run_id, for_update=True)
    if run is None:
        raise OrchestratorError("agent_run_not_found")
    if run.scope_hash != authorization_hash:
        raise OrchestratorScopeDrift("scope_proof_mismatch")
    if command.target_capability not in _CAPABILITIES:
        raise OrchestratorCapabilityDenied("capability_not_registered")
    if command.command_type not in _CAPABILITIES[command.target_capability]:
        raise OrchestratorCapabilityDenied("command_type_not_registered")
    if command.status == "completed":
        artifact = _artifact_for_command(uow, command.id)
        if artifact is None:
            raise OrchestratorError("agent_result_artifact_missing")
        return SpecialistExecutionResult(run=run, artifact=artifact, replayed=True)
    if command.status not in {"queued", "running"} or command.deadline_at <= now:
        raise OrchestratorError("agent_command_not_executable")

    claim_run_lease(
        uow,
        run_id=run.id,
        lease_owner=worker_id,
        now=now,
        lease_seconds=60,
    )
    command.status = "running"
    append_checkpoint_and_event(
        uow,
        run_id=run.id,
        expected_version=run.version,
        lease_owner=worker_id,
        authorization_hash=authorization_hash,
        node_key="specialist_started",
        control=RunCheckpointControl(
            completed_command_ids=(),
            pending_command_ids=(command.id,),
            retry_count=0,
            next_action="wait_children",
        ),
        event=_event(
            uow,
            run_id=run.id,
            command_id=command.id,
            event_type="agent.started",
            status="running",
            source_role="specialist",
            source_capability=command.target_capability,
            safe_summary="只读表格分析已开始",
            occurred_at=now,
        ),
    )

    result = _validate_result(execute())
    artifact = AgentArtifact(
        id=uuid4(),
        run_id=run.id,
        kind=result.artifact_kind or _artifact_kind(command.target_capability),
        storage_ref=result.storage_ref,
        content_hash=result.content_hash,
        visibility_scope_hash=authorization_hash,
        validation_status="validated",
        expires_at=None,
    )
    uow.add_artifact(artifact)
    uow.flush()
    command.status = "completed"
    if after_command_completed is not None:
        after_command_completed(artifact)
    commands = uow.list_commands(run.id, for_update=True)
    completed_ids = tuple(item.id for item in commands if item.status == "completed")
    pending_ids = tuple(
        item.id for item in commands if item.status in {"queued", "running"}
    )
    failed_ids = tuple(item.id for item in commands if item.status == "failed")
    append_checkpoint_and_event(
        uow,
        run_id=run.id,
        expected_version=run.version,
        lease_owner=worker_id,
        authorization_hash=authorization_hash,
        node_key="specialist_completed",
        control=RunCheckpointControl(
            completed_command_ids=completed_ids,
            pending_command_ids=pending_ids,
            failed_command_ids=failed_ids,
            retry_count=0,
            next_action="wait_children" if pending_ids else "fan_in",
        ),
        event=_event(
            uow,
            run_id=run.id,
            command_id=command.id,
            event_type="agent.completed",
            status="running",
            source_role="specialist",
            source_capability=command.target_capability,
            safe_summary=result.safe_summary,
            artifact_ref=artifact.id,
            metrics=result.metrics or {},
            occurred_at=now,
        ),
    )
    if pending_ids:
        run.lease_owner = None
        run.lease_expires_at = None
        return SpecialistExecutionResult(run=run, artifact=artifact, replayed=False)
    final_artifact = artifact
    if fan_in is not None:
        composed = _validate_result(fan_in())
        final_artifact = AgentArtifact(
            id=uuid4(),
            run_id=run.id,
            kind=composed.artifact_kind or "composer_result",
            storage_ref=composed.storage_ref,
            content_hash=composed.content_hash,
            visibility_scope_hash=authorization_hash,
            validation_status="validated",
            expires_at=None,
        )
        uow.add_artifact(final_artifact)
        uow.flush()
        if final_artifact.kind == "grounded_composer_result":
            append_checkpoint_and_event(
                uow,
                run_id=run.id,
                expected_version=run.version,
                lease_owner=worker_id,
                authorization_hash=authorization_hash,
                node_key="grounded_result_available",
                control=RunCheckpointControl(
                    completed_command_ids=completed_ids,
                    pending_command_ids=(),
                    failed_command_ids=failed_ids,
                    retry_count=0,
                    next_action="finalize",
                ),
                event=_event(
                    uow,
                    run_id=run.id,
                    command_id=command.id,
                    event_type="result.available",
                    status="running",
                    source_role="supervisor",
                    safe_summary="已生成受证据约束的回答",
                    artifact_ref=final_artifact.id,
                    occurred_at=now,
                ),
            )
    if failed_ids:
        required_ids, optional_ids = _plan_command_sets(uow, run.id, commands)
        required_failed = required_ids.intersection(failed_ids)
        terminal_status = "failed" if required_failed else "degraded"
        terminal_event = "run.failed" if required_failed else "run.degraded"
        if not required_failed:
            run.safe_result_ref = final_artifact.id
        append_checkpoint_and_event(
            uow,
            run_id=run.id,
            expected_version=run.version,
            lease_owner=worker_id,
            authorization_hash=authorization_hash,
            node_key="run_failed" if required_failed else "run_degraded",
            control=RunCheckpointControl(
                completed_command_ids=completed_ids,
                pending_command_ids=(),
                failed_command_ids=failed_ids,
                required_command_ids=tuple(required_ids),
                optional_command_ids=tuple(optional_ids),
                retry_count=0,
                next_action="stop",
            ),
            event=_event(
                uow,
                run_id=run.id,
                command_id=command.id,
                event_type=terminal_event,
                status=terminal_status,
                source_role="supervisor",
                safe_summary=(
                    "必需 Specialist 未全部完成"
                    if required_failed
                    else "可选 Specialist 未完成，已返回安全降级结果"
                ),
                artifact_ref=None if required_failed else final_artifact.id,
                occurred_at=now,
            ),
        )
        return SpecialistExecutionResult(run=run, artifact=artifact, replayed=False)

    run.safe_result_ref = final_artifact.id
    append_checkpoint_and_event(
        uow,
        run_id=run.id,
        expected_version=run.version,
        lease_owner=worker_id,
        authorization_hash=authorization_hash,
        node_key="run_completed",
        control=RunCheckpointControl(
            completed_command_ids=completed_ids,
            pending_command_ids=(),
            retry_count=0,
            next_action="stop",
        ),
        event=_event(
            uow,
            run_id=run.id,
            command_id=command.id,
            event_type="run.completed",
            status="completed",
            source_role="supervisor",
            safe_summary="只读分析已完成",
            artifact_ref=final_artifact.id,
            occurred_at=now,
        ),
    )
    return SpecialistExecutionResult(run=run, artifact=artifact, replayed=False)


def fail_specialist_command(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    command_id: UUID,
    authorization_hash: str,
    worker_id: str,
    now: datetime,
    fan_in: Callable[[], SpecialistSafeResult] | None = None,
    required_command_ids: frozenset[UUID] | None = None,
    optional_command_ids: frozenset[UUID] | None = None,
) -> AgentWorkflowRun:
    command = uow.get_command(command_id, for_update=True)
    if command is None:
        raise OrchestratorError("agent_command_not_found")
    run = uow.get_run(command.run_id, for_update=True)
    if run is None:
        raise OrchestratorError("agent_run_not_found")
    if run.scope_hash != authorization_hash:
        raise OrchestratorScopeDrift("scope_proof_mismatch")
    if run.status == "failed" and command.status == "failed":
        return run
    if run.status in {"completed", "cancelled", "degraded"}:
        raise OrchestratorError("agent_run_terminal")
    if run.deadline_at <= now:
        command.status = "failed"
        return expire_agent_run(
            uow,
            run_id=run.id,
            authorization_hash=authorization_hash,
            supervisor_id=worker_id,
            now=now,
        )
    claim_run_lease(
        uow,
        run_id=run.id,
        lease_owner=worker_id,
        now=now,
        lease_seconds=30,
    )
    command.status = "failed"
    commands = uow.list_commands(run.id, for_update=True)
    completed_ids = tuple(item.id for item in commands if item.status == "completed")
    pending_ids = tuple(
        item.id for item in commands if item.status in {"queued", "running"}
    )
    failed_ids = tuple(item.id for item in commands if item.status == "failed")
    if (required_command_ids is None) != (optional_command_ids is None):
        raise ValueError("agent_command_plan_override_invalid")
    if required_command_ids is None:
        required_ids, optional_ids = _plan_command_sets(uow, run.id, commands)
    else:
        required_ids = required_command_ids
        optional_ids = optional_command_ids or frozenset()
        command_ids = {item.id for item in commands}
        if (
            required_ids.intersection(optional_ids)
            or required_ids.union(optional_ids) != command_ids
        ):
            raise ValueError("agent_command_plan_override_invalid")
    append_checkpoint_and_event(
        uow,
        run_id=run.id,
        expected_version=run.version,
        lease_owner=worker_id,
        authorization_hash=authorization_hash,
        node_key="specialist_failed",
        control=RunCheckpointControl(
            completed_command_ids=completed_ids,
            pending_command_ids=pending_ids,
            failed_command_ids=failed_ids,
            required_command_ids=tuple(required_ids),
            optional_command_ids=tuple(optional_ids),
            retry_count=0,
            next_action="fan_in" if not pending_ids else "wait_children",
        ),
        event=_event(
            uow,
            run_id=run.id,
            command_id=command.id,
            event_type="agent.failed",
            status="running",
            source_role="specialist",
            source_capability=command.target_capability,
            safe_summary="只读分析未能完成",
            occurred_at=now,
        ),
    )
    if command.id in required_ids:
        # A required failure is terminal for the whole run. Mark every
        # unfinished sibling failed in the same locked transaction so queued
        # deliveries cannot keep retrying after Supervisor has stopped.
        for sibling in commands:
            if sibling.status in {"queued", "running"}:
                sibling.status = "failed"
        completed_ids = tuple(
            item.id for item in commands if item.status == "completed"
        )
        pending_ids = ()
        failed_ids = tuple(item.id for item in commands if item.status == "failed")
        append_checkpoint_and_event(
            uow,
            run_id=run.id,
            expected_version=run.version,
            lease_owner=worker_id,
            authorization_hash=authorization_hash,
            node_key="run_failed",
            control=RunCheckpointControl(
                completed_command_ids=completed_ids,
                pending_command_ids=pending_ids,
                failed_command_ids=failed_ids,
                required_command_ids=tuple(required_ids),
                optional_command_ids=tuple(optional_ids),
                retry_count=0,
                next_action="stop",
            ),
            event=_event(
                uow,
                run_id=run.id,
                command_id=command.id,
                event_type="run.failed",
                status="failed",
                source_role="supervisor",
                safe_summary="必需 Specialist 未能完成",
                occurred_at=now,
            ),
        )
    else:
        if not pending_ids:
            final_artifact = None
            if fan_in is not None:
                composed = _validate_result(fan_in())
                final_artifact = AgentArtifact(
                    id=uuid4(),
                    run_id=run.id,
                    kind=composed.artifact_kind or "composer_result",
                    storage_ref=composed.storage_ref,
                    content_hash=composed.content_hash,
                    visibility_scope_hash=authorization_hash,
                    validation_status="validated",
                    expires_at=None,
                )
                uow.add_artifact(final_artifact)
                uow.flush()
                if final_artifact.kind == "grounded_composer_result":
                    append_checkpoint_and_event(
                        uow,
                        run_id=run.id,
                        expected_version=run.version,
                        lease_owner=worker_id,
                        authorization_hash=authorization_hash,
                        node_key="grounded_result_available",
                        control=RunCheckpointControl(
                            completed_command_ids=completed_ids,
                            pending_command_ids=(),
                            failed_command_ids=failed_ids,
                            required_command_ids=tuple(required_ids),
                            optional_command_ids=tuple(optional_ids),
                            retry_count=0,
                            next_action="finalize",
                        ),
                        event=_event(
                            uow,
                            run_id=run.id,
                            command_id=command.id,
                            event_type="result.available",
                            status="running",
                            source_role="supervisor",
                            safe_summary="已生成受证据约束的降级回答",
                            artifact_ref=final_artifact.id,
                            occurred_at=now,
                        ),
                    )
            else:
                completed_artifacts = tuple(
                    artifact
                    for completed_id in completed_ids
                    if (artifact := _artifact_for_command(uow, completed_id))
                    is not None
                )
                if completed_artifacts:
                    final_artifact = completed_artifacts[-1]
            if final_artifact is not None:
                run.safe_result_ref = final_artifact.id
                append_checkpoint_and_event(
                    uow,
                    run_id=run.id,
                    expected_version=run.version,
                    lease_owner=worker_id,
                    authorization_hash=authorization_hash,
                    node_key="run_degraded",
                    control=RunCheckpointControl(
                        completed_command_ids=completed_ids,
                        pending_command_ids=(),
                        failed_command_ids=failed_ids,
                        required_command_ids=tuple(required_ids),
                        optional_command_ids=tuple(optional_ids),
                        retry_count=0,
                        next_action="stop",
                    ),
                    event=_event(
                        uow,
                        run_id=run.id,
                        command_id=command.id,
                        event_type="run.degraded",
                        status="degraded",
                        source_role="supervisor",
                        safe_summary="可选 Specialist 未完成，已返回安全降级结果",
                        artifact_ref=final_artifact.id,
                        occurred_at=now,
                    ),
                )
                return run
        run.lease_owner = None
        run.lease_expires_at = None
    return run


def cancel_agent_run(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    authorization_hash: str,
    supervisor_id: str,
    now: datetime,
) -> AgentWorkflowRun:
    run = uow.get_run(run_id, for_update=True)
    if run is None:
        raise OrchestratorError("agent_run_not_found")
    if run.scope_hash != authorization_hash:
        raise OrchestratorScopeDrift("scope_proof_mismatch")
    if run.status == "cancelled":
        return run
    if run.status in {"completed", "degraded", "failed", "timed_out"}:
        raise OrchestratorError("agent_run_terminal")
    claim_run_lease(
        uow,
        run_id=run.id,
        lease_owner=supervisor_id,
        now=now,
        lease_seconds=30,
    )
    append_checkpoint_and_event(
        uow,
        run_id=run.id,
        expected_version=run.version,
        lease_owner=supervisor_id,
        authorization_hash=authorization_hash,
        node_key="run_cancelled",
        control=RunCheckpointControl(
            completed_command_ids=(),
            pending_command_ids=(),
            retry_count=0,
            next_action="stop",
        ),
        event=_event(
            uow,
            run_id=run.id,
            command_id=None,
            event_type="run.cancelled",
            status="cancelled",
            source_role="supervisor",
            safe_summary="任务已取消",
            occurred_at=now,
        ),
    )
    return run


def expire_agent_run(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    authorization_hash: str,
    supervisor_id: str,
    now: datetime,
) -> AgentWorkflowRun:
    if not supervisor_id.strip():
        raise ValueError("agent_timeout_supervisor_required")
    run = uow.get_run(run_id, for_update=True)
    if run is None:
        raise OrchestratorError("agent_run_not_found")
    if run.scope_hash != authorization_hash:
        raise OrchestratorScopeDrift("scope_proof_mismatch")
    if run.status == "timed_out":
        return run
    if run.status in {"completed", "degraded", "failed", "cancelled"}:
        raise OrchestratorError("agent_run_terminal")
    if now < run.deadline_at:
        raise OrchestratorError("agent_run_deadline_not_reached")

    # The row is locked.  Advancing the version and replacing any stale lease
    # makes a concurrent worker fail its optimistic append after the deadline.
    run.lease_owner = supervisor_id
    run.lease_expires_at = now
    run.version += 1
    append_checkpoint_and_event(
        uow,
        run_id=run.id,
        expected_version=run.version,
        lease_owner=supervisor_id,
        authorization_hash=authorization_hash,
        node_key="run_timed_out",
        control=RunCheckpointControl(
            completed_command_ids=(),
            pending_command_ids=(),
            retry_count=0,
            next_action="stop",
        ),
        event=_event(
            uow,
            run_id=run.id,
            command_id=None,
            event_type="run.timed_out",
            status="timed_out",
            source_role="supervisor",
            safe_summary="任务已超时",
            occurred_at=now,
        ),
    )
    return run


def _artifact_for_command(
    uow: AgentEventRuntimeUnitOfWork,
    command_id: UUID,
) -> AgentArtifact | None:
    command = uow.get_command(command_id)
    if command is None:
        return None
    for event in reversed(uow.list_events(command.run_id)):
        if event.command_id == command_id and event.artifact_ref is not None:
            return uow.get_artifact(event.artifact_ref)
    return None


def _plan_command_sets(
    uow: AgentEventRuntimeUnitOfWork,
    run_id: UUID,
    commands: list[AgentCommand],
) -> tuple[frozenset[UUID], frozenset[UUID]]:
    for checkpoint in reversed(uow.list_checkpoints(run_id)):
        control = checkpoint.control_json
        required = control.get("required_command_ids")
        optional = control.get("optional_command_ids")
        if required or optional:
            return (
                frozenset(UUID(str(item)) for item in required or ()),
                frozenset(UUID(str(item)) for item in optional or ()),
            )
    return frozenset(item.id for item in commands), frozenset()


def _artifact_kind(capability: str) -> str:
    return _CAPABILITY_DEFINITIONS[capability].output_kind


def _validate_input_artifact_refs(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    input_artifact_refs: tuple[UUID, ...],
    authorization_hash: str,
    now: datetime,
) -> None:
    if len(input_artifact_refs) > 16 or len(set(input_artifact_refs)) != len(
        input_artifact_refs
    ):
        raise ValueError("specialist_input_artifact_refs_invalid")
    for artifact_ref in input_artifact_refs:
        artifact = uow.get_artifact(artifact_ref)
        if (
            artifact is None
            or artifact.run_id != run_id
            or artifact.visibility_scope_hash != authorization_hash
            or artifact.validation_status != "validated"
            or (artifact.expires_at is not None and artifact.expires_at <= now)
        ):
            raise OrchestratorScopeDrift("specialist_input_artifact_invalid")


def _durable_command_envelope(
    uow: AgentEventRuntimeUnitOfWork,
    command: AgentCommand,
) -> AgentCommandEnvelope:
    outbox = uow.get_outbox_event_by_event_id(command.id)
    if outbox is None or outbox.topic != f"agent.commands.{command.target_capability}":
        raise OrchestratorError("agent_command_outbox_missing")
    try:
        return AgentCommandEnvelope.model_validate_json(
            json.dumps(outbox.payload_json, ensure_ascii=False, separators=(",", ":"))
        )
    except Exception as exc:
        raise OrchestratorError("agent_command_outbox_invalid") from exc


def _validate_result(result: SpecialistSafeResult) -> SpecialistSafeResult:
    if not isinstance(result, SpecialistSafeResult):
        raise TypeError("specialist_safe_result_required")
    if not _SAFE_PAYLOAD_REF.fullmatch(result.storage_ref):
        raise ValueError("specialist_storage_ref_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", result.content_hash):
        raise ValueError("specialist_content_hash_invalid")
    if not result.safe_summary or len(result.safe_summary) > 240:
        raise ValueError("specialist_safe_summary_invalid")
    if result.metrics is not None and (
        not all(
            isinstance(key, str) and isinstance(value, int) and value >= 0
            for key, value in result.metrics.items()
        )
    ):
        raise ValueError("specialist_metrics_invalid")
    return result


def _event(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    command_id: UUID | None,
    event_type: str,
    status: str,
    source_role: str,
    safe_summary: str,
    occurred_at: datetime,
    source_capability: str | None = None,
    artifact_ref: UUID | None = None,
    metrics: dict[str, int] | None = None,
) -> AgentEventEnvelope:
    return AgentEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "run_id": run_id,
            "command_id": command_id,
            "causation_id": command_id or run_id,
            "correlation_id": run_id,
            "sequence": uow.next_event_sequence(run_id),
            "event_type": event_type,
            "status": status,
            "source_role": source_role,
            "source_capability": source_capability,
            "safe_summary": safe_summary,
            "artifact_ref": artifact_ref,
            "metrics": metrics or {},
            "occurred_at": occurred_at,
        }
    )


__all__ = [
    "OrchestratorCapabilityDenied",
    "OrchestratorError",
    "OrchestratorScopeDrift",
    "SpecialistExecutionResult",
    "SpecialistCommandDispatch",
    "SpecialistSafeResult",
    "build_authorization_hash",
    "dispatch_specialist_command",
    "dispatch_specialist_commands",
    "execute_read_only_specialist",
    "fail_specialist_command",
    "cancel_agent_run",
    "expire_agent_run",
    "registered_capabilities",
    "validate_specialist_event",
]
