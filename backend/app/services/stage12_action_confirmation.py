from __future__ import annotations

from datetime import UTC, datetime
import json
from uuid import UUID, uuid4

from app.schemas.agent_event_runtime import AgentEventEnvelope
from app.schemas.stage12_action_runtime import (
    ActionConfirmRequestV1,
    ActionPrivatePayloadV1,
    ActionRejectRequestV1,
    ActionSlotControlV1,
    ActionTerminalReceiptV1,
)
from app.services.agent_event_runtime import (
    AgentEventRuntimeUnitOfWork,
    append_agent_runtime_event,
)
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    confirm_record_change_draft,
    reject_record_change_draft,
)
from app.services.stage06_platform import Stage06PlatformUnitOfWork
from app.services.stage12_action_runtime import (
    Stage12ActionConflict,
    Stage12ActionNotFound,
    Stage12ActionRuntimeRepository,
    transition_action_slot,
)


def confirm_stage12_action(
    action_repository: Stage12ActionRuntimeRepository,
    runtime_uow: AgentEventRuntimeUnitOfWork,
    platform_uow: Stage06PlatformUnitOfWork,
    *,
    run_id: UUID,
    slot_id: UUID,
    request: ActionConfirmRequestV1,
    private_payload: ActionPrivatePayloadV1,
    actor: Actor,
) -> ActionTerminalReceiptV1:
    slot = _slot(action_repository, run_id, slot_id)
    if slot.proposal_version != request.proposal_version:
        raise Stage12ActionConflict("action_version_conflict")
    if slot.status != "pending_confirmation":
        raise Stage12ActionConflict("action_invalid_state")
    _validate_payload(action_repository, slot, private_payload)
    control = _control(slot.control_json)
    values = _confirmed_values(control, private_payload, request.proposed_values)
    if slot.action_kind == "record.update":
        if request.record_version is None or len(private_payload.record_versions) != 1:
            raise Stage12ActionConflict("action_version_conflict")
        proof = private_payload.record_versions[0]
        record = platform_uow.get_record(proof.record_id)
        if (
            request.record_version != proof.record_version
            or record is None
            or record.version != proof.record_version
        ):
            raise Stage12ActionConflict("action_version_conflict")
    elif request.record_version is not None:
        raise Stage12ActionConflict("action_version_conflict")

    resource_id = slot.materialized_resource_id
    if resource_id is None:
        raise Stage12ActionConflict("action_materialized_resource_missing")
    transition_action_slot(
        action_repository,
        slot_id=slot.id,
        expected_proposal_version=slot.proposal_version,
        target_status="confirmed",
    )
    if slot.action_kind == "reminder.request":
        notification = platform_uow.get_notification_request(resource_id)
        if notification is None or notification.status != "blocked":
            raise Stage12ActionConflict("action_notification_invalid_state")
        record_audit_event(
            platform_uow,
            trace_id=f"stage12:action-confirm:{slot.id}",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            event_type="stage12.action_notification_confirmed_blocked",
            entity_type="notification_request",
            entity_id=notification.id,
            after_state={"status": "blocked", "external_send_count": 0},
        )
    else:
        draft = platform_uow.get_record_change_draft(resource_id)
        if draft is None or draft.status != "pending_confirmation":
            raise Stage12ActionConflict("action_draft_invalid_state")
        draft.proposed_values = values
        # SQL-backed units of work disable autoflush.  The confirmation service
        # reacquires the draft with populate_existing=True, so persist the user's
        # reviewed edits inside the current transaction before taking that lock.
        platform_uow.flush()
        confirm_record_change_draft(platform_uow, draft.id, actor=actor)
    transition_action_slot(
        action_repository,
        slot_id=slot.id,
        expected_proposal_version=slot.proposal_version,
        target_status="executed",
    )
    _append_action_event(
        action_repository,
        runtime_uow,
        slot,
        event_type="action.executed",
        safe_summary="受控动作已由用户确认执行",
    )
    return _receipt(slot, replayed=False)


def reject_stage12_action(
    action_repository: Stage12ActionRuntimeRepository,
    runtime_uow: AgentEventRuntimeUnitOfWork,
    platform_uow: Stage06PlatformUnitOfWork,
    *,
    run_id: UUID,
    slot_id: UUID,
    request: ActionRejectRequestV1,
    actor: Actor,
) -> ActionTerminalReceiptV1:
    slot = _slot(action_repository, run_id, slot_id)
    if slot.proposal_version != request.proposal_version:
        raise Stage12ActionConflict("action_version_conflict")
    if slot.status != "pending_confirmation":
        raise Stage12ActionConflict("action_invalid_state")
    resource_id = slot.materialized_resource_id
    if resource_id is None:
        raise Stage12ActionConflict("action_materialized_resource_missing")
    if slot.action_kind == "reminder.request":
        notification = platform_uow.get_notification_request(resource_id)
        if notification is None or notification.status != "blocked":
            raise Stage12ActionConflict("action_notification_invalid_state")
        record_audit_event(
            platform_uow,
            trace_id=f"stage12:action-reject:{slot.id}",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            event_type="stage12.action_notification_rejected",
            entity_type="notification_request",
            entity_id=notification.id,
            after_state={"status": "blocked", "external_send_count": 0},
        )
    else:
        draft = platform_uow.get_record_change_draft(resource_id)
        if draft is None:
            raise Stage12ActionConflict("action_draft_invalid_state")
        reject_record_change_draft(platform_uow, draft.id, actor=actor)
    transition_action_slot(
        action_repository,
        slot_id=slot.id,
        expected_proposal_version=slot.proposal_version,
        target_status="rejected",
    )
    _append_action_event(
        action_repository,
        runtime_uow,
        slot,
        event_type="action.denied",
        safe_summary="用户已拒绝受控动作",
    )
    return _receipt(slot, replayed=False)


def _confirmed_values(
    control: ActionSlotControlV1,
    payload: ActionPrivatePayloadV1,
    edits: dict[str, object],
) -> dict[str, object]:
    fields = {item.field_id: item for item in control.editable_fields}
    original = {
        fields[item.field_id].field_key: item.value
        for item in payload.assignments
        if item.field_id in fields
    }
    values = original if not edits else dict(edits)
    allowed = {item.field_key for item in control.editable_fields}
    required = {item.field_key for item in control.editable_fields if item.required}
    if not set(values).issubset(allowed):
        raise Stage12ActionConflict("action_scope_changed")
    if not required.issubset(values) or any(
        value is None or (isinstance(value, str) and not value.strip())
        for key, value in values.items()
        if key in required
    ):
        raise Stage12ActionConflict("action_required_field_missing")
    return values


def _slot(repository, run_id: UUID, slot_id: UUID):
    slot = repository.get_action(slot_id, for_update=True)
    if slot is None or slot.run_id != run_id:
        raise Stage12ActionNotFound("action_slot_not_found")
    return slot


def _validate_payload(repository, slot, payload: ActionPrivatePayloadV1) -> None:
    objective = repository.get_objective(slot.objective_run_id)
    if (
        payload.slot_key != slot.slot_key
        or payload.action_kind != slot.action_kind
        or objective is None
        or payload.objective_key != objective.objective_key
    ):
        raise Stage12ActionConflict("action_private_payload_mismatch")


def _control(value: dict) -> ActionSlotControlV1:
    return ActionSlotControlV1.model_validate_json(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    )


def _append_action_event(repository, runtime_uow, slot, *, event_type, safe_summary):
    objective = repository.get_objective(slot.objective_run_id)
    command_id = None if objective is None else objective.command_id
    run = runtime_uow.get_run(slot.run_id, for_update=True)
    if run is None:
        raise Stage12ActionNotFound("agent_run_not_found")
    all_terminal = all(
        item.status
        in {
            "executed",
            "denied",
            "degraded",
            "failed",
            "rejected",
            "conflicted",
            "cancelled",
            "expired",
        }
        for item in repository.list_actions(run.id)
    )
    objective_actions = tuple(
        item
        for item in repository.list_actions(run.id)
        if item.objective_run_id == slot.objective_run_id
    )
    objective_terminal = all(
        item.status
        in {
            "executed",
            "denied",
            "degraded",
            "failed",
            "rejected",
            "conflicted",
            "cancelled",
            "expired",
        }
        for item in objective_actions
    )
    append_agent_runtime_event(
        runtime_uow,
        AgentEventEnvelope(
            event_id=uuid4(),
            run_id=run.id,
            command_id=command_id,
            causation_id=command_id or slot.id,
            correlation_id=run.id,
            sequence=runtime_uow.next_event_sequence(run.id),
            event_type=event_type,
            status="waiting_approval",
            source_role="supervisor",
            safe_summary=safe_summary,
            metrics={"external_send_count": 0},
            occurred_at=datetime.now(UTC),
        ),
        authorization_hash=run.scope_hash,
        update_run_status="waiting_approval",
    )
    if objective is not None and objective_terminal:
        objective.status = "completed" if slot.status == "executed" else "denied"
        objective_event_type = (
            "objective.completed"
            if objective.status == "completed"
            else "objective.denied"
        )
        append_agent_runtime_event(
            runtime_uow,
            AgentEventEnvelope(
                event_id=uuid4(),
                run_id=run.id,
                command_id=command_id,
                causation_id=objective.id,
                correlation_id=run.id,
                sequence=runtime_uow.next_event_sequence(run.id),
                event_type=objective_event_type,
                status=objective.status,
                source_role="supervisor",
                safe_summary=(
                    "受控动作 Objective 已完成"
                    if objective.status == "completed"
                    else "受控动作 Objective 已终止"
                ),
                metrics={},
                occurred_at=datetime.now(UTC),
            ),
            authorization_hash=run.scope_hash,
        )
    if all_terminal:
        append_agent_runtime_event(
            runtime_uow,
            AgentEventEnvelope(
                event_id=uuid4(),
                run_id=run.id,
                command_id=None,
                causation_id=slot.id,
                correlation_id=run.id,
                sequence=runtime_uow.next_event_sequence(run.id),
                event_type="run.completed",
                status="completed",
                source_role="supervisor",
                safe_summary="受控动作任务已进入安全终态",
                metrics={"external_send_count": 0},
                occurred_at=datetime.now(UTC),
            ),
            authorization_hash=run.scope_hash,
            update_run_status="completed",
        )


def _receipt(slot, *, replayed: bool) -> ActionTerminalReceiptV1:
    return ActionTerminalReceiptV1(
        slot_id=slot.id,
        status=slot.status,
        proposal_version=slot.proposal_version,
        execution_ticket_id=slot.execution_ticket_id,
        resource_id=slot.materialized_resource_id,
        replayed=replayed,
    )


__all__ = ["confirm_stage12_action", "reject_stage12_action"]
