from __future__ import annotations

import json
from uuid import UUID

from app.schemas.agent_controlled_actions import (
    CreateRecordProposal,
    CreateTaskProposal,
    ReminderRequestProposal,
    UpdateRecordProposal,
)
from app.schemas.stage12_action_runtime import (
    ActionPrivatePayloadV1,
    ActionSlotControlV1,
)
from app.services.agent_tool_gateway import (
    AgentControlledToolGateway,
    ControlledActionMaterialization,
)
from app.services.permissions import Actor
from app.services.stage06_platform import Stage06PlatformUnitOfWork
from app.services.stage12_action_runtime import (
    Stage12ActionConflict,
    Stage12ActionNotFound,
    Stage12ActionRuntimeRepository,
    transition_action_slot,
)


def materialize_action_slot(
    repository: Stage12ActionRuntimeRepository,
    platform_uow: Stage06PlatformUnitOfWork,
    *,
    slot_id: UUID,
    expected_proposal_version: int,
    workspace_id: UUID,
    employee_id: UUID,
    actor: Actor,
    private_payload: ActionPrivatePayloadV1,
    gateway: AgentControlledToolGateway | None = None,
) -> ControlledActionMaterialization:
    slot = repository.get_action(slot_id, for_update=True)
    if slot is None:
        raise Stage12ActionNotFound("action_slot_not_found")
    if slot.proposal_version != expected_proposal_version:
        raise Stage12ActionConflict("action_version_conflict")
    if (
        private_payload.objective_key
        != _objective_key(repository, slot.objective_run_id)
        or private_payload.slot_key != slot.slot_key
        or private_payload.action_kind != slot.action_kind
    ):
        raise Stage12ActionConflict("action_private_payload_mismatch")
    control = ActionSlotControlV1.model_validate_json(
        json.dumps(slot.control_json, ensure_ascii=False, separators=(",", ":"))
    )
    if control.action_kind != private_payload.action_kind:
        raise Stage12ActionConflict("action_control_mismatch")
    if slot.status == "pending_confirmation":
        if slot.materialized_resource_id is None or slot.execution_ticket_id is None:
            raise Stage12ActionConflict("action_materialization_replay_invalid")
        return ControlledActionMaterialization(
            proposal_id=slot.id,
            action_type=_provider_action_type(slot.action_kind),
            ticket_id=slot.execution_ticket_id,
            resource_id=slot.materialized_resource_id,
            resource_status=_resource_status(
                platform_uow, slot.action_kind, slot.materialized_resource_id
            ),
            confirmation_required=True,
            external_send_count=0,
            replayed=True,
        )
    transition_action_slot(
        repository,
        slot_id=slot.id,
        expected_proposal_version=expected_proposal_version,
        target_status="running",
    )
    proposal = _proposal(slot.id, control, private_payload)
    transition_action_slot(
        repository,
        slot_id=slot.id,
        expected_proposal_version=slot.proposal_version,
        target_status="proposed",
    )
    result = (gateway or AgentControlledToolGateway()).materialize(
        platform_uow,
        workspace_id=workspace_id,
        employee_id=employee_id,
        actor=actor,
        proposal=proposal,
    )
    transition_action_slot(
        repository,
        slot_id=slot.id,
        expected_proposal_version=slot.proposal_version,
        target_status="pending_confirmation",
    )
    slot.materialized_resource_id = result.resource_id
    slot.execution_ticket_id = result.ticket_id
    return result


def _proposal(
    proposal_id: UUID,
    control: ActionSlotControlV1,
    payload: ActionPrivatePayloadV1,
):
    field_keys = {item.field_id: item.field_key for item in control.editable_fields}
    if any(item.field_id not in field_keys for item in payload.assignments):
        raise Stage12ActionConflict("action_field_scope_changed")
    proposed_values = {
        field_keys[item.field_id]: item.value for item in payload.assignments
    }
    common = {
        "proposal_id": proposal_id,
        "reason": control.safe_summary,
        "source_artifact_refs": (),
    }
    if payload.action_kind == "record.create":
        if payload.target_table_id is None or payload.target_record_ids:
            raise Stage12ActionConflict("action_target_invalid")
        return CreateRecordProposal(
            **common,
            action_type="create_record",
            table_id=payload.target_table_id,
            proposed_values=proposed_values,
        )
    if payload.action_kind == "task.create":
        if payload.target_table_id is None or payload.target_record_ids:
            raise Stage12ActionConflict("action_target_invalid")
        return CreateTaskProposal(
            **common,
            action_type="create_task",
            table_id=payload.target_table_id,
            proposed_values=proposed_values,
        )
    if payload.action_kind == "record.update":
        if len(payload.target_record_ids) != 1 or len(payload.record_versions) != 1:
            raise Stage12ActionConflict("action_target_invalid")
        target = payload.target_record_ids[0]
        version = payload.record_versions[0]
        if version.record_id != target:
            raise Stage12ActionConflict("action_version_proof_invalid")
        return UpdateRecordProposal(
            **common,
            action_type="update_record",
            record_id=target,
            expected_version=version.record_version,
            proposed_values=proposed_values,
        )
    if payload.action_kind == "reminder.request":
        source_record_id = (
            payload.target_record_ids[0]
            if len(payload.target_record_ids) == 1
            else None
        )
        return ReminderRequestProposal(
            **common,
            action_type="request_reminder",
            base_id=None,
            source_record_id=source_record_id,
            target=payload.reminder_target or {},
            message_payload=payload.reminder_message_payload or {},
            send_policy={"confirmation": "required", "dry_run": True},
        )
    raise Stage12ActionConflict("action_kind_unsupported")


def _objective_key(repository, objective_run_id: UUID) -> str:
    objectives = getattr(repository, "objectives", None)
    if isinstance(objectives, list):
        objective = next(
            (item for item in objectives if item.id == objective_run_id), None
        )
        if objective is not None:
            return objective.objective_key
    session = getattr(repository, "session", None)
    if session is not None:
        from app.models.agent_event_runtime import AgentObjectiveRun

        objective = session.get(AgentObjectiveRun, objective_run_id)
        if objective is not None:
            return objective.objective_key
    raise Stage12ActionNotFound("action_objective_not_found")


def _provider_action_type(action_kind: str) -> str:
    return {
        "record.create": "create_record",
        "record.update": "update_record",
        "task.create": "create_task",
        "reminder.request": "request_reminder",
    }[action_kind]


def _resource_status(
    uow: Stage06PlatformUnitOfWork, action_kind: str, resource_id: UUID
) -> str:
    if action_kind == "reminder.request":
        value = uow.get_notification_request(resource_id)
    else:
        value = uow.get_record_change_draft(resource_id)
    if value is None:
        raise Stage12ActionNotFound("action_materialized_resource_not_found")
    return value.status


__all__ = ["materialize_action_slot"]
