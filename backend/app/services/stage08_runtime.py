from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.models.stage08_runtime import Stage08ExecutionTicket
from app.runtime.stage08_collaboration_contracts import (
    Stage08SafeExecutionContext,
    _safe_execution_context_snapshot,
    _stage08_safe_execution_summary,
)
from app.runtime.stage08_contracts import ExecutionPlan, ExecutionTicketState
from app.runtime.stage08_policy import evaluate_execution_plan
from app.services.audit import record_audit_event
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
)
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
)


_OPERATION = "stage08.execution_plan"
_TERMINAL_STATES = frozenset(
    {
        ExecutionTicketState.succeeded,
        ExecutionTicketState.failed,
        ExecutionTicketState.denied,
        ExecutionTicketState.cancelled,
        ExecutionTicketState.timed_out,
        ExecutionTicketState.expired,
    }
)
_ALLOWED_TRANSITIONS = {
    ExecutionTicketState.planned: frozenset({ExecutionTicketState.executing}),
    ExecutionTicketState.executing: _TERMINAL_STATES,
}


def begin_execution_plan(
    uow: Stage06PlatformUnitOfWork,
    plan: ExecutionPlan,
    *,
    safe_context: Stage08SafeExecutionContext | None = None,
) -> Stage08ExecutionTicket:
    safe_snapshot = (
        None
        if safe_context is None
        else _safe_execution_context_snapshot(safe_context)
    )
    if safe_snapshot is not None and safe_snapshot.trace_hash != plan.trace_id:
        raise PlatformValidationError(
            "stage08_safe_execution_trace_mismatch",
            "stage08_safe_execution_trace_mismatch",
        )
    decision = evaluate_execution_plan(uow, plan)
    if not decision.allowed:
        raise PlatformValidationError("stage08_policy_denied", decision.reason_code or "")

    workspace_id = UUID(plan.workspace_id)
    employee_id = UUID(plan.employee_id)
    request_fingerprint = fingerprint_request(_semantic_payload(plan))
    if uow.lock_workspace_for_stage08_execution(workspace_id) is None:
        raise PlatformValidationError(
            "stage08_workspace_lock_not_found",
            "stage08_workspace_lock_not_found",
        )
    existing_ticket = uow.get_execution_ticket_by_trace(workspace_id, plan.trace_id)
    if existing_ticket is not None:
        if existing_ticket.request_fingerprint == request_fingerprint:
            return _return_replayed_ticket(
                existing_ticket,
                safe_context=safe_context,
            )
        raise PlatformValidationError("stage08_trace_conflict", "stage08_trace_conflict")

    idempotency = begin_idempotent_operation(
        uow,
        workspace_id=workspace_id,
        operation=_OPERATION,
        idempotency_key=plan.idempotency_key,
        request_fingerprint=request_fingerprint,
        trace_id=plan.trace_id,
    )
    if idempotency.status == "replay":
        ticket_id = _replay_ticket_id(idempotency.response_ref)
        ticket = uow.get_execution_ticket(ticket_id)
        if (
            ticket is None
            or ticket.workspace_id != workspace_id
            or ticket.request_fingerprint != request_fingerprint
        ):
            raise PlatformValidationError(
                "stage08_idempotency_replay_invalid",
                "stage08_idempotency_replay_invalid",
            )
        return _return_replayed_ticket(ticket, safe_context=safe_context)

    ticket = Stage08ExecutionTicket(
        id=uuid4(),
        workspace_id=workspace_id,
        employee_id=employee_id,
        actor_id=plan.actor,
        action=plan.action,
        trace_id=plan.trace_id,
        request_fingerprint=request_fingerprint,
        status=ExecutionTicketState.planned.value,
        budget=plan.budget.model_dump(),
        tool_summary=[],
        completed_at=None,
    )
    uow.add_execution_ticket(ticket)
    complete_idempotent_operation(
        idempotency.record,
        response_ref={"ticket_id": str(ticket.id), "status": ticket.status},
    )
    _record_ticket_created_audit(
        uow,
        ticket,
        decision.effective_tool_names,
        safe_context=safe_context,
    )
    return ticket


def transition_execution_ticket(
    uow: Stage06PlatformUnitOfWork,
    ticket: Stage08ExecutionTicket,
    target_state: ExecutionTicketState,
    *,
    safe_context: Stage08SafeExecutionContext | None = None,
) -> Stage08ExecutionTicket:
    safe_snapshot = (
        None
        if safe_context is None
        else _safe_execution_context_snapshot(safe_context)
    )
    tracked_ticket = uow.get_execution_ticket(ticket.id)
    if tracked_ticket is None:
        raise PlatformValidationError("stage08_ticket_not_found", "stage08_ticket_not_found")
    ticket = tracked_ticket
    if safe_snapshot is not None and safe_snapshot.trace_hash != ticket.trace_id:
        raise PlatformValidationError(
            "stage08_safe_execution_trace_mismatch",
            "stage08_safe_execution_trace_mismatch",
        )
    try:
        current_state = ExecutionTicketState(ticket.status)
    except ValueError as exc:
        raise PlatformValidationError(
            "stage08_ticket_transition_invalid",
            "stage08_ticket_transition_invalid",
        ) from exc
    if target_state not in _ALLOWED_TRANSITIONS.get(current_state, frozenset()):
        raise PlatformValidationError(
            "stage08_ticket_transition_invalid",
            "stage08_ticket_transition_invalid",
        )

    ticket.status = target_state.value
    if target_state in _TERMINAL_STATES:
        ticket.completed_at = datetime.now(UTC)
    _record_ticket_transition_audit(
        uow,
        ticket,
        current_state,
        target_state,
        safe_context=safe_context,
    )
    return ticket


def _semantic_payload(plan: ExecutionPlan) -> dict[str, object]:
    return {
        "workspace_id": plan.workspace_id,
        "employee_id": plan.employee_id,
        "actor": plan.actor,
        "action": plan.action,
        "budget": plan.budget.model_dump(),
        "invocations": [
            {"tool_name": invocation.tool_name, "input": invocation.input}
            for invocation in plan.invocations
        ],
    }


def _return_replayed_ticket(
    ticket: Stage08ExecutionTicket,
    *,
    safe_context: Stage08SafeExecutionContext | None,
) -> Stage08ExecutionTicket:
    if safe_context is not None:
        raise PlatformValidationError(
            "stage08_safe_execution_ticket_provenance_unavailable",
            "stage08_safe_execution_ticket_provenance_unavailable",
        )
    return ticket


def _replay_ticket_id(response_ref: dict[str, Any] | None) -> UUID:
    if not isinstance(response_ref, dict):
        raise PlatformValidationError(
            "stage08_idempotency_replay_invalid",
            "stage08_idempotency_replay_invalid",
        )
    raw_ticket_id = response_ref.get("ticket_id")
    if not isinstance(raw_ticket_id, str):
        raise PlatformValidationError(
            "stage08_idempotency_replay_invalid",
            "stage08_idempotency_replay_invalid",
        )
    try:
        return UUID(raw_ticket_id)
    except ValueError as exc:
        raise PlatformValidationError(
            "stage08_idempotency_replay_invalid",
            "stage08_idempotency_replay_invalid",
        ) from exc


def _record_ticket_created_audit(
    uow: Stage06PlatformUnitOfWork,
    ticket: Stage08ExecutionTicket,
    tool_names: tuple[str, ...],
    *,
    safe_context: Stage08SafeExecutionContext | None = None,
) -> None:
    if safe_context is not None:
        record_audit_event(
            getattr(uow, "session", uow),
            trace_id=_safe_execution_context_snapshot(safe_context).trace_hash,
            actor_type="system",
            actor_id="stage08_e3_safe",
            event_type="stage08.execution_ticket_created",
            entity_type="stage08_safe_execution",
            entity_id=None,
            after_state=_stage08_safe_execution_summary(
                safe_context,
                graph="stage08_collaboration_e3",
                status=ticket.status,
                action=ticket.action,
                counts={"tool_count": len(tool_names)},
                code=None,
                latency_ms=0,
                ticket_present=True,
                draft_present=False,
            ),
            permission_snapshot=None,
        )
        return
    record_audit_event(
        getattr(uow, "session", uow),
        trace_id=ticket.trace_id,
        actor_type="user",
        actor_id=_actor_user_id(ticket.actor_id) or "unknown",
        event_type="stage08.execution_ticket_created",
        entity_type="stage08_execution_ticket",
        entity_id=ticket.id,
        after_state={
            "ticket_id": str(ticket.id),
            "status": ticket.status,
            "action": ticket.action,
            "tool_names": list(tool_names),
            "budget": dict(ticket.budget),
        },
        permission_snapshot={"role": _active_member_role(uow, ticket), "actor_type": "user"},
    )


def _record_ticket_transition_audit(
    uow: Stage06PlatformUnitOfWork,
    ticket: Stage08ExecutionTicket,
    previous_state: ExecutionTicketState,
    target_state: ExecutionTicketState,
    *,
    safe_context: Stage08SafeExecutionContext | None = None,
) -> None:
    if safe_context is not None:
        record_audit_event(
            getattr(uow, "session", uow),
            trace_id=_safe_execution_context_snapshot(safe_context).trace_hash,
            actor_type="system",
            actor_id="stage08_e3_safe",
            event_type="stage08.execution_ticket_transitioned",
            entity_type="stage08_safe_execution",
            entity_id=None,
            after_state=_stage08_safe_execution_summary(
                safe_context,
                graph="stage08_collaboration_e3",
                status=target_state.value,
                action=ticket.action,
                counts={"tool_summary_count": len(ticket.tool_summary)},
                code=None,
                latency_ms=0,
                ticket_present=True,
                draft_present=_safe_ticket_has_draft(ticket),
            ),
            permission_snapshot=None,
        )
        return
    record_audit_event(
        getattr(uow, "session", uow),
        trace_id=ticket.trace_id,
        actor_type="user",
        actor_id=_actor_user_id(ticket.actor_id) or "unknown",
        event_type="stage08.execution_ticket_transitioned",
        entity_type="stage08_execution_ticket",
        entity_id=ticket.id,
        before_state={"status": previous_state.value},
        after_state={
            "ticket_id": str(ticket.id),
            "status": target_state.value,
            "action": ticket.action,
            "tool_summary_count": len(ticket.tool_summary),
            "trace_id": ticket.trace_id,
        },
        permission_snapshot={"role": _active_member_role(uow, ticket), "actor_type": "user"},
    )


def _safe_ticket_has_draft(ticket: Stage08ExecutionTicket) -> bool:
    for summary in ticket.tool_summary:
        if not isinstance(summary, dict):
            continue
        if summary.get("draft_present") is True:
            return True
        counts = summary.get("counts")
        if isinstance(counts, dict) and type(counts.get("draft_count")) is int:
            if counts["draft_count"] > 0:
                return True
    return False


def _actor_user_id(actor: str) -> str | None:
    if not actor.startswith("user:"):
        return None
    user_id = actor.removeprefix("user:")
    if not user_id or not user_id.strip():
        return None
    return user_id


def _active_member_role(
    uow: Stage06PlatformUnitOfWork,
    ticket: Stage08ExecutionTicket,
) -> str:
    actor_user_id = _actor_user_id(ticket.actor_id)
    if actor_user_id is None:
        return "unknown"
    member = next(
        (
            candidate
            for candidate in uow.list_workspace_members(ticket.workspace_id)
            if candidate.user_id == actor_user_id and candidate.status == "active"
        ),
        None,
    )
    return member.role if member is not None else "unknown"
