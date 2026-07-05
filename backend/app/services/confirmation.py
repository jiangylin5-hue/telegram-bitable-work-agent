from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.service import ExecutionTicket, ServiceRecord
from app.models.service_drafts import ServiceDraft
from app.services.audit import record_audit_event
from app.services.permissions import Actor, assert_action_allowed


class ConfirmationStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConfirmationResult:
    service_record: ServiceRecord
    execution_ticket: ExecutionTicket


class ConfirmationUnitOfWork(Protocol):
    def get_service_draft(self, draft_id: UUID) -> ServiceDraft | None:
        pass

    def add_service_record(self, service_record: ServiceRecord) -> None:
        pass

    def add_execution_ticket(self, ticket: ExecutionTicket) -> None:
        pass

    def add(self, value: object) -> None:
        pass

    def commit(self) -> None:
        pass


class InMemoryConfirmationUnitOfWork:
    def __init__(self, service_drafts: list[ServiceDraft] | None = None) -> None:
        self.service_drafts = list(service_drafts or [])
        self.service_records: list[ServiceRecord] = []
        self.execution_tickets: list[ExecutionTicket] = []
        self.audit_events: list[object] = []
        self.committed = False

    def get_service_draft(self, draft_id: UUID) -> ServiceDraft | None:
        return next((draft for draft in self.service_drafts if draft.id == draft_id), None)

    def add_service_record(self, service_record: ServiceRecord) -> None:
        self.service_records.append(service_record)

    def add_execution_ticket(self, ticket: ExecutionTicket) -> None:
        self.execution_tickets.append(ticket)

    def add(self, value: object) -> None:
        self.audit_events.append(value)

    def commit(self) -> None:
        self.committed = True


class SqlAlchemyConfirmationUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_service_draft(self, draft_id: UUID) -> ServiceDraft | None:
        return self.session.get(ServiceDraft, draft_id)

    def add_service_record(self, service_record: ServiceRecord) -> None:
        self.session.add(service_record)

    def add_execution_ticket(self, ticket: ExecutionTicket) -> None:
        self.session.add(ticket)

    def add(self, value: object) -> None:
        self.session.add(value)

    def commit(self) -> None:
        self.session.commit()


def confirm_service_draft(
    uow: ConfirmationUnitOfWork,
    draft_id: UUID,
    actor: Actor,
) -> ConfirmationResult:
    draft = uow.get_service_draft(draft_id)
    if draft is None:
        raise ConfirmationStateError(f"Draft not found: {draft_id}")

    assert_action_allowed(
        actor,
        "confirm_draft",
        session=uow,
        trace_id=draft.trace_id,
        entity_type="service_draft",
        entity_id=draft.id,
    )
    if draft.status != "pending_confirmation":
        raise ConfirmationStateError(f"Draft cannot be confirmed from {draft.status}")
    if draft.missing_fields:
        raise ConfirmationStateError("Draft has missing fields")
    if draft.customer_id is None:
        raise ConfirmationStateError("Draft has no customer")

    approved_by_user_id = UUID(actor.actor_id)
    service_record = _create_service_record(draft, approved_by_user_id)
    ticket = _create_execution_ticket(draft, service_record, approved_by_user_id, actor)
    draft.status = "confirmed"

    uow.add_service_record(service_record)
    uow.add_execution_ticket(ticket)
    record_audit_event(
        uow,
        trace_id=draft.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="draft_confirmed",
        entity_type="service_draft",
        entity_id=draft.id,
        after_state={
            "draft_status": draft.status,
            "service_record_id": str(service_record.id),
            "execution_ticket_id": str(ticket.id),
        },
        permission_snapshot={"role": actor.role, "action": "confirm_draft"},
    )
    return ConfirmationResult(service_record=service_record, execution_ticket=ticket)


def reject_service_draft(
    uow: ConfirmationUnitOfWork,
    draft_id: UUID,
    actor: Actor,
    *,
    reason: str,
) -> ServiceDraft:
    draft = _require_draft(uow, draft_id)
    assert_action_allowed(
        actor,
        "reject_draft",
        session=uow,
        trace_id=draft.trace_id,
        entity_type="service_draft",
        entity_id=draft.id,
    )
    _ensure_terminal_action_allowed(draft)
    before_status = draft.status
    draft.status = "rejected"
    record_audit_event(
        uow,
        trace_id=draft.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="draft_rejected",
        entity_type="service_draft",
        entity_id=draft.id,
        before_state={"draft_status": before_status},
        after_state={"draft_status": draft.status, "reason": reason},
        permission_snapshot={"role": actor.role, "action": "reject_draft"},
    )
    return draft


def request_more_info_for_service_draft(
    uow: ConfirmationUnitOfWork,
    draft_id: UUID,
    actor: Actor,
    *,
    missing_fields: list[str],
) -> ServiceDraft:
    draft = _require_draft(uow, draft_id)
    assert_action_allowed(
        actor,
        "request_more_info",
        session=uow,
        trace_id=draft.trace_id,
        entity_type="service_draft",
        entity_id=draft.id,
    )
    _ensure_terminal_action_allowed(draft)
    before_status = draft.status
    draft.status = "needs_more_info"
    draft.missing_fields = list(missing_fields)
    record_audit_event(
        uow,
        trace_id=draft.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="draft_more_info_requested",
        entity_type="service_draft",
        entity_id=draft.id,
        before_state={"draft_status": before_status},
        after_state={
            "draft_status": draft.status,
            "missing_fields": draft.missing_fields,
        },
        permission_snapshot={"role": actor.role, "action": "request_more_info"},
    )
    return draft


def escalate_service_draft(
    uow: ConfirmationUnitOfWork,
    draft_id: UUID,
    actor: Actor,
    *,
    reason: str,
) -> ServiceDraft:
    draft = _require_draft(uow, draft_id)
    assert_action_allowed(
        actor,
        "escalate_review",
        session=uow,
        trace_id=draft.trace_id,
        entity_type="service_draft",
        entity_id=draft.id,
    )
    _ensure_terminal_action_allowed(draft)
    before_status = draft.status
    draft.status = "manual_review"
    record_audit_event(
        uow,
        trace_id=draft.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="draft_escalated",
        entity_type="service_draft",
        entity_id=draft.id,
        before_state={"draft_status": before_status},
        after_state={"draft_status": draft.status, "reason": reason},
        permission_snapshot={"role": actor.role, "action": "escalate_review"},
    )
    return draft


def _require_draft(
    uow: ConfirmationUnitOfWork,
    draft_id: UUID,
) -> ServiceDraft:
    draft = uow.get_service_draft(draft_id)
    if draft is None:
        raise ConfirmationStateError(f"Draft not found: {draft_id}")
    return draft


def _ensure_terminal_action_allowed(draft: ServiceDraft) -> None:
    if draft.status in {"confirmed", "rejected", "blocked"}:
        raise ConfirmationStateError(f"Draft cannot be changed from {draft.status}")


def _create_service_record(
    draft: ServiceDraft,
    confirmed_by_user_id: UUID,
) -> ServiceRecord:
    return ServiceRecord(
        id=uuid4(),
        service_type=draft.draft_type,
        status="pending",
        customer_id=draft.customer_id,
        account_asset_id=draft.account_asset_id,
        source_draft_id=draft.id,
        confirmed_by_user_id=confirmed_by_user_id,
        confirmed_at=datetime.now(timezone.utc),
        idempotency_key=f"service:{draft.id}",
        trace_id=draft.trace_id,
    )


def _create_execution_ticket(
    draft: ServiceDraft,
    service_record: ServiceRecord,
    approved_by_user_id: UUID,
    actor: Actor,
) -> ExecutionTicket:
    amount_limit = None
    if "amount" in draft.payload:
        amount_limit = Decimal(str(draft.payload["amount"]))
    return ExecutionTicket(
        id=uuid4(),
        approved_by_user_id=approved_by_user_id,
        approved_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        allowed_action=f"execution.{draft.draft_type}",
        allowed_customer_id=draft.customer_id,
        allowed_account_id=draft.account_asset_id,
        amount_limit=amount_limit,
        risk_snapshot={"risk_flags": draft.risk_flags},
        permission_snapshot={"role": actor.role, "service_record_id": str(service_record.id)},
        idempotency_key=f"ticket:{service_record.id}",
        status="issued",
        trace_id=draft.trace_id,
    )
