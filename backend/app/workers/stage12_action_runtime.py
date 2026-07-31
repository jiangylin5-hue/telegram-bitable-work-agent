from __future__ import annotations

from datetime import UTC, datetime
import json
from uuid import UUID, uuid4

from app.models.agent_event_runtime import AgentPrivateInput
from app.schemas.agent_event_runtime import AgentCommandEnvelope, AgentEventEnvelope
from app.schemas.stage12_action_runtime import (
    ActionSlotControlV1,
    DurableAuthorizedCandidateSetV1,
)
from app.services.agent_event_runtime import AgentEventRuntimeUnitOfWork
from app.services.agent_orchestrator import OrchestratorError
from app.services.stage06_authorization import authorize_workspace_action
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import Stage06PlatformUnitOfWork
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.agent_typed_artifacts import read_typed_artifact
from app.services.stage12_action_materialization import materialize_action_slot
from app.services.stage12_durable_action_specialist import (
    DurableActionSemanticError,
    propose_durable_action,
)
from app.services.stage12_action_private_payload import (
    open_stage12_action_private_payload,
)
from app.services.stage12_action_runtime import Stage12ActionRuntimeRepository


def process_stage12_action_command(
    runtime_uow: AgentEventRuntimeUnitOfWork,
    action_repository: Stage12ActionRuntimeRepository,
    platform_uow: Stage06PlatformUnitOfWork,
    envelope: AgentCommandEnvelope,
    *,
    private_key_b64: str,
    worker_id: str,
    now: datetime | None = None,
):
    now = now or datetime.now(UTC)
    if (
        envelope.target_capability != "platform.action.propose"
        or envelope.command_type != "propose_controlled_action"
    ):
        raise OrchestratorError("action_command_capability_mismatch")
    run = runtime_uow.get_run(envelope.run_id, for_update=True)
    command = runtime_uow.get_command(envelope.command_id, for_update=True)
    authorization_hash = envelope.scope_proof_ref.removeprefix("scope:sha256:")
    if (
        run is None
        or command is None
        or command.run_id != run.id
        or run.scope_hash != authorization_hash
        or command.target_capability != envelope.target_capability
        or command.command_type != envelope.command_type
        or command.idempotency_key_hash != envelope.idempotency_key_hash
        or command.deadline_at != envelope.deadline_at
    ):
        raise OrchestratorError("action_command_envelope_mismatch")
    if now >= command.deadline_at:
        raise OrchestratorError("action_command_expired")
    prefix = "agent-private-input:"
    if command.payload_ref is None or not command.payload_ref.startswith(prefix):
        raise OrchestratorError("action_private_input_ref_invalid")
    try:
        private_input_id = UUID(command.payload_ref.removeprefix(prefix))
    except ValueError as exc:
        raise OrchestratorError("action_private_input_ref_invalid") from exc
    sealed = runtime_uow.get_private_input(private_input_id, for_update=True)
    if sealed is None or sealed.run_id != run.id or sealed.command_id != command.id:
        raise OrchestratorError("action_private_input_unavailable")
    payload = open_stage12_action_private_payload(
        sealed,
        key_b64=private_key_b64,
        run_id=run.id,
        command_id=command.id,
        scope_hash=authorization_hash,
        now=now,
    )
    slot = action_repository.get_action_by_private_payload_ref(command.payload_ref)
    if (
        slot is None
        or slot.run_id != run.id
        or slot.target_scope_hash != authorization_hash
    ):
        raise OrchestratorError("action_slot_scope_mismatch")
    objective = _objective(action_repository, slot.objective_run_id)
    if objective.command_id not in {None, command.id}:
        raise OrchestratorError("action_objective_command_mismatch")
    objective.command_id = command.id
    actor = authorize_workspace_action(
        platform_uow,
        Stage06RequestIdentity(
            user_id=payload.actor_user_id,
            source="verified_adapter",
        ),
        run.workspace_id,
        "digital_employee.invoke",
    )
    snapshot = build_authorized_schema_snapshot(
        platform_uow,
        workspace_id=run.workspace_id,
        employee_id=run.root_employee_id,
        actor=actor,
        require_field_policy_v2=(
            run.workflow_version == "stage12.quality-v2.action.v1"
        ),
    )
    if run.workflow_version == "stage12.quality-v2.action.v1" and (
        payload.field_policy_version != snapshot.field_policy_version
        or payload.field_policy_hash != snapshot.field_policy_hash
    ):
        raise OrchestratorError("action_field_policy_scope_mismatch")
    candidate_set = _load_candidate_set(
        runtime_uow,
        platform_uow,
        envelope=envelope,
        workspace_id=run.workspace_id,
        run_id=run.id,
        authorization_hash=authorization_hash,
    )
    control = ActionSlotControlV1.model_validate_json(
        json.dumps(slot.control_json, ensure_ascii=False)
    )
    try:
        proposal = propose_durable_action(
            candidate_set=candidate_set,
            control=control,
            private_payload=payload,
            objective_key=objective.objective_key,
            slot_key=slot.slot_key,
            schema_hash=snapshot.schema_hash,
            scope_hash=snapshot.scope_hash,
            current_record_version=lambda record_id: _current_record_version(
                platform_uow, record_id
            ),
        )
    except DurableActionSemanticError as exc:
        raise OrchestratorError(exc.code) from exc
    if slot.status == "queued":
        objective.status = "running"
        _append_action_runtime_event(
            runtime_uow,
            run=run,
            command_id=command.id,
            causation_id=objective.id,
            event_type="objective.started",
            status="running",
            safe_summary="受控动作 Objective 正在生成建议",
            authorization_hash=authorization_hash,
            now=now,
        )
        _append_action_runtime_event(
            runtime_uow,
            run=run,
            command_id=command.id,
            causation_id=command.id,
            event_type="action.proposed",
            status="running",
            safe_summary="受控动作建议已通过语义校验",
            authorization_hash=authorization_hash,
            now=now,
        )
    result = materialize_action_slot(
        action_repository,
        platform_uow,
        slot_id=slot.id,
        expected_proposal_version=slot.proposal_version,
        workspace_id=run.workspace_id,
        employee_id=run.root_employee_id,
        actor=actor,
        private_payload=proposal,
    )
    command.status = "completed"
    objective.status = "proposed"
    sealed.consumed_at = now
    if not any(
        item.event_type == "action.pending_confirmation"
        and item.command_id == command.id
        for item in runtime_uow.list_events(run.id)
    ):
        _append_action_runtime_event(
            runtime_uow,
            run=run,
            command_id=command.id,
            causation_id=command.id,
            event_type="action.pending_confirmation",
            status="waiting_approval",
            safe_summary="受控动作等待确认",
            authorization_hash=authorization_hash,
            now=now,
            metrics={"external_send_count": result.external_send_count},
            update_run_status="waiting_approval",
        )
    return result


def _append_action_runtime_event(
    runtime_uow,
    *,
    run,
    command_id,
    causation_id,
    event_type,
    status,
    safe_summary,
    authorization_hash,
    now,
    metrics=None,
    update_run_status=None,
):
    from app.services.agent_event_runtime import append_agent_runtime_event

    append_agent_runtime_event(
        runtime_uow,
        AgentEventEnvelope(
            event_id=uuid4(),
            run_id=run.id,
            command_id=command_id,
            causation_id=causation_id,
            correlation_id=run.id,
            sequence=runtime_uow.next_event_sequence(run.id),
            event_type=event_type,
            status=status,
            source_role="specialist",
            source_capability="platform.action.propose",
            safe_summary=safe_summary,
            metrics=metrics or {},
            occurred_at=now,
        ),
        authorization_hash=authorization_hash,
        update_run_status=update_run_status,
    )


def _load_candidate_set(
    runtime_uow,
    platform_uow,
    *,
    envelope,
    workspace_id,
    run_id,
    authorization_hash,
):
    if len(envelope.input_artifact_refs) != 1:
        raise OrchestratorError("action_candidate_artifact_required")
    artifact = runtime_uow.get_artifact(envelope.input_artifact_refs[0])
    if artifact is None or artifact.run_id != run_id:
        raise OrchestratorError("action_candidate_artifact_unavailable")
    try:
        return read_typed_artifact(
            platform_uow,
            artifact=artifact,
            workspace_id=workspace_id,
            current_scope_hash=authorization_hash,
            expected_kind="authorized_candidate_set",
            payload_type=DurableAuthorizedCandidateSetV1,
        )
    except ValueError as exc:
        raise OrchestratorError("action_candidate_artifact_invalid") from exc


def _current_record_version(platform_uow, record_id):
    record = platform_uow.get_record(record_id)
    if record is None:
        return None
    return record.table_id, record.version


def _objective(repository, objective_id: UUID):
    values = getattr(repository, "objectives", None)
    if isinstance(values, list):
        value = next((item for item in values if item.id == objective_id), None)
    else:
        session = getattr(repository, "session", None)
        if session is None:
            value = None
        else:
            from app.models.agent_event_runtime import AgentObjectiveRun

            value = session.get(AgentObjectiveRun, objective_id)
    if value is None:
        raise OrchestratorError("action_objective_not_found")
    return value


__all__ = ["process_stage12_action_command"]
