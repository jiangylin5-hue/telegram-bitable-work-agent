from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.runtime.stage08_contracts import (
    ExecutionBudget,
    ExecutionPlan,
    ExecutionTicketState,
    ToolInvocation,
)
from app.runtime.stage08_tool_gateway import Stage08ToolGateway
from app.schemas.agent_controlled_actions import (
    ControlledActionProposal,
    CreateRecordProposal,
    CreateTaskProposal,
    ReminderRequestProposal,
    UpdateRecordProposal,
)
from app.services.permissions import Actor
from app.services.stage06_platform import PlatformValidationError, Stage06PlatformUnitOfWork
from app.services.stage08_runtime import begin_execution_plan


@dataclass(frozen=True, slots=True)
class ControlledActionMaterialization:
    proposal_id: UUID
    action_type: str
    ticket_id: UUID
    resource_id: UUID
    resource_status: str
    confirmation_required: bool
    external_send_count: int
    replayed: bool


class AgentControlledToolGateway:
    def __init__(self, gateway: Stage08ToolGateway | None = None) -> None:
        self._gateway = gateway or Stage08ToolGateway()

    def materialize(
        self,
        uow: Stage06PlatformUnitOfWork,
        *,
        workspace_id: UUID,
        employee_id: UUID,
        actor: Actor,
        proposal: ControlledActionProposal,
    ) -> ControlledActionMaterialization:
        employee = uow.get_digital_employee(employee_id)
        if employee is None or employee.workspace_id != workspace_id:
            raise PlatformValidationError("resource_scope_mismatch", "employee_workspace")
        tool_name, tool_input = self._tool_invocation(uow, proposal)
        trace_id = f"stage11:action:{proposal.proposal_id}"
        invocation = ToolInvocation(tool_name=tool_name, input=tool_input)
        plan = ExecutionPlan(
            ticket_id=str(proposal.proposal_id),
            workspace_id=str(workspace_id),
            employee_id=str(employee_id),
            actor=f"user:{actor.actor_id}",
            action=tool_name,
            trace_id=trace_id,
            idempotency_key=str(proposal.proposal_id),
            state=ExecutionTicketState.planned,
            budget=ExecutionBudget(
                max_tool_calls=1,
                max_wall_time_ms=5_000,
                max_graph_depth=1,
                max_retries=0,
                max_retrieval_chunks=0,
            ),
            invocations=[invocation],
        )
        ticket = begin_execution_plan(uow, plan)
        # SQL-backed UOWs disable implicit autoflush.  Stage08ToolGateway
        # immediately reloads the ticket before its first transition, so the
        # planned ticket must be visible inside the current transaction.
        session = getattr(uow, "session", None)
        if session is not None:
            session.flush()
        replayed = ticket.status == ExecutionTicketState.succeeded.value
        if not replayed:
            result = self._gateway.execute(uow, ticket, invocation)
            resource_id = UUID(result.entity_refs[0])
            if session is not None:
                session.flush()
        else:
            if not ticket.tool_summary:
                raise PlatformValidationError(
                    "stage11_action_replay_invalid",
                    "stage11_action_replay_invalid",
                )
            resource_id = self._replayed_resource_id(ticket)
        resource_status = self._resource_status(uow, proposal, resource_id)
        return ControlledActionMaterialization(
            proposal_id=proposal.proposal_id,
            action_type=proposal.action_type,
            ticket_id=ticket.id,
            resource_id=resource_id,
            resource_status=resource_status,
            confirmation_required=True,
            external_send_count=0,
            replayed=replayed,
        )

    @staticmethod
    def _tool_invocation(
        uow: Stage06PlatformUnitOfWork,
        proposal: ControlledActionProposal,
    ) -> tuple[str, dict[str, object]]:
        if isinstance(proposal, (CreateRecordProposal, CreateTaskProposal)):
            return "task.create_draft", {
                "table_id": str(proposal.table_id),
                "proposed_values": proposal.proposed_values,
            }
        if isinstance(proposal, UpdateRecordProposal):
            record = uow.get_record(proposal.record_id)
            if record is None:
                raise PlatformValidationError("record_not_found", str(proposal.record_id))
            if record.version != proposal.expected_version:
                raise PlatformValidationError(
                    "record_version_conflict",
                    str(proposal.record_id),
                )
            return "record_change_draft.create", {
                "record_id": str(proposal.record_id),
                "proposed_values": proposal.proposed_values,
            }
        if isinstance(proposal, ReminderRequestProposal):
            return "notification.request", {
                "base_id": None if proposal.base_id is None else str(proposal.base_id),
                "source_record_id": (
                    None
                    if proposal.source_record_id is None
                    else str(proposal.source_record_id)
                ),
                "channel": proposal.channel,
                "target": proposal.target,
                "message_payload": proposal.message_payload,
                "send_policy": {
                    **proposal.send_policy,
                    "confirmation": "required",
                    "dry_run": True,
                },
            }
        raise TypeError("controlled_action_proposal_invalid")

    @staticmethod
    def _resource_status(
        uow: Stage06PlatformUnitOfWork,
        proposal: ControlledActionProposal,
        resource_id: UUID,
    ) -> str:
        if isinstance(proposal, ReminderRequestProposal):
            request = uow.get_notification_request(resource_id)
            if request is None:
                raise PlatformValidationError("notification_request_not_found", str(resource_id))
            return request.status
        draft = uow.get_record_change_draft(resource_id)
        if draft is None:
            raise PlatformValidationError("record_change_draft_not_found", str(resource_id))
        return draft.status

    @staticmethod
    def _replayed_resource_id(ticket) -> UUID:
        summary = ticket.tool_summary[-1] if ticket.tool_summary else None
        refs = summary.get("entity_refs") if isinstance(summary, dict) else None
        if not isinstance(refs, list) or not refs:
            raise PlatformValidationError(
                "stage11_action_replay_invalid",
                "stage11_action_replay_invalid",
            )
        try:
            return UUID(str(refs[0]))
        except ValueError as exc:
            raise PlatformValidationError(
                "stage11_action_replay_invalid",
                "stage11_action_replay_invalid",
            ) from exc


__all__ = ["AgentControlledToolGateway", "ControlledActionMaterialization"]
