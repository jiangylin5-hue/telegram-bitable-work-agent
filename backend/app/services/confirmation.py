from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service import ExecutionLog, ExecutionTicket, ServiceRecord
from app.models.service_drafts import ServiceDraft
from app.models.telegram import Message, TelegramSendRequest
from app.services.audit import record_audit_event
from app.services.permissions import Actor, PermissionDenied, assert_action_allowed
from app.services.telegram_send_requests import (
    CUSTOMER_REPLY_SEND_PURPOSE,
    NOT_ALLOWLISTED_ERROR,
    summarize_message_text,
)


class ConfirmationStateError(RuntimeError):
    pass


STAGE05_BUSINESS_DRAFT_TYPES = frozenset(
    {"recharge", "card_binding", "bm_invite", "account_assignment"}
)
STAGE05_DRAFT_AGENT_IDS = frozenset(
    {
        "recharge_draft_agent",
        "card_binding_draft_agent",
        "bm_invite_draft_agent",
        "customer_reply_draft_agent",
        "account_inventory_agent",
    }
)
STAGE05_CONFIRM_ROLES = frozenset({"admin", "manager"})


@dataclass(frozen=True)
class ConfirmationResult:
    service_record: ServiceRecord | None = None
    execution_ticket: ExecutionTicket | None = None
    execution_log: ExecutionLog | None = None
    telegram_send_request: TelegramSendRequest | None = None
    side_effect: str | None = None


class ConfirmationUnitOfWork(Protocol):
    allowed_chat_ids: tuple[str, ...]

    def get_service_draft(self, draft_id: UUID) -> ServiceDraft | None:
        pass

    def get_source_message(self, message_id: UUID) -> Message | None:
        pass

    def add_service_record(self, service_record: ServiceRecord) -> None:
        pass

    def add_execution_ticket(self, ticket: ExecutionTicket) -> None:
        pass

    def add_execution_log(self, log: ExecutionLog) -> None:
        pass

    def add_send_request(self, request: TelegramSendRequest) -> None:
        pass

    def get_send_request_by_trace_id(
        self,
        trace_id: str,
    ) -> TelegramSendRequest | None:
        pass

    def add(self, value: object) -> None:
        pass

    def commit(self) -> None:
        pass


class InMemoryConfirmationUnitOfWork:
    def __init__(
        self,
        service_drafts: Iterable[ServiceDraft] | None = None,
        *,
        messages: Iterable[Message] | None = None,
        send_requests: Iterable[TelegramSendRequest] | None = None,
        execution_logs: Iterable[ExecutionLog] | None = None,
        allowed_chat_ids: tuple[str, ...] = (),
    ) -> None:
        self.service_drafts = list(service_drafts or [])
        self.messages = list(messages or [])
        self.send_requests = list(send_requests or [])
        self.service_records: list[ServiceRecord] = []
        self.execution_tickets: list[ExecutionTicket] = []
        self.execution_logs = list(execution_logs or [])
        self.outbox_events: list[object] = []
        self.audit_events: list[object] = []
        self.allowed_chat_ids = allowed_chat_ids
        self.committed = False

    def get_service_draft(self, draft_id: UUID) -> ServiceDraft | None:
        return next((draft for draft in self.service_drafts if draft.id == draft_id), None)

    def get_source_message(self, message_id: UUID) -> Message | None:
        return next((message for message in self.messages if message.id == message_id), None)

    def add_service_record(self, service_record: ServiceRecord) -> None:
        self.service_records.append(service_record)

    def add_execution_ticket(self, ticket: ExecutionTicket) -> None:
        self.execution_tickets.append(ticket)

    def add_execution_log(self, log: ExecutionLog) -> None:
        self.execution_logs.append(log)

    def add_send_request(self, request: TelegramSendRequest) -> None:
        self.send_requests.append(request)

    def get_send_request_by_trace_id(
        self,
        trace_id: str,
    ) -> TelegramSendRequest | None:
        return next(
            (request for request in self.send_requests if request.trace_id == trace_id),
            None,
        )

    def add(self, value: object) -> None:
        self.audit_events.append(value)

    def commit(self) -> None:
        self.committed = True


class SqlAlchemyConfirmationUnitOfWork:
    def __init__(
        self,
        session: Session,
        *,
        allowed_chat_ids: tuple[str, ...] = (),
    ) -> None:
        self.session = session
        self.allowed_chat_ids = allowed_chat_ids

    def get_service_draft(self, draft_id: UUID) -> ServiceDraft | None:
        return self.session.get(ServiceDraft, draft_id)

    def get_source_message(self, message_id: UUID) -> Message | None:
        return self.session.get(Message, message_id)

    def add_service_record(self, service_record: ServiceRecord) -> None:
        self.session.add(service_record)

    def add_execution_ticket(self, ticket: ExecutionTicket) -> None:
        self.session.add(ticket)

    def add_execution_log(self, log: ExecutionLog) -> None:
        self.session.add(log)

    def add_send_request(self, request: TelegramSendRequest) -> None:
        self.session.add(request)

    def get_send_request_by_trace_id(
        self,
        trace_id: str,
    ) -> TelegramSendRequest | None:
        return self.session.scalar(
            select(TelegramSendRequest).where(TelegramSendRequest.trace_id == trace_id)
        )

    def add(self, value: object) -> None:
        self.session.add(value)

    def commit(self) -> None:
        self.session.commit()


def confirm_service_draft(
    uow: ConfirmationUnitOfWork,
    draft_id: UUID,
    actor: Actor,
    *,
    allowed_chat_ids: tuple[str, ...] | None = None,
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

    if _is_stage05_draft(draft):
        _assert_stage05_confirmation_allowed(uow, draft, actor)
        if draft.draft_type == "customer_reply":
            return _confirm_stage05_customer_reply(
                uow,
                draft,
                actor,
                allowed_chat_ids=_effective_allowed_chat_ids(
                    uow,
                    allowed_chat_ids,
                ),
            )
        if draft.draft_type in STAGE05_BUSINESS_DRAFT_TYPES:
            return _confirm_stage05_business_draft(uow, draft, actor)

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
    return ConfirmationResult(
        service_record=service_record,
        execution_ticket=ticket,
        side_effect="execution_ticket_created",
    )


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


def _is_stage05_draft(draft: ServiceDraft) -> bool:
    return (
        draft.source_agent_run_id is not None
        or draft.created_by_id in STAGE05_DRAFT_AGENT_IDS
    )


def _assert_stage05_confirmation_allowed(
    uow: ConfirmationUnitOfWork,
    draft: ServiceDraft,
    actor: Actor,
) -> None:
    if actor.role in STAGE05_CONFIRM_ROLES:
        return
    record_audit_event(
        uow,
        trace_id=draft.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="permission_denied",
        entity_type="service_draft",
        entity_id=draft.id,
        permission_snapshot={
            "action": "confirm_draft",
            "role": actor.role,
            "actor_type": actor.actor_type,
            "stage": "stage05",
        },
    )
    raise PermissionDenied(f"{actor.role} cannot perform confirm_draft")


def _effective_allowed_chat_ids(
    uow: ConfirmationUnitOfWork,
    allowed_chat_ids: tuple[str, ...] | None,
) -> tuple[str, ...]:
    if allowed_chat_ids is not None:
        return allowed_chat_ids
    return getattr(uow, "allowed_chat_ids", ())


def _confirm_stage05_customer_reply(
    uow: ConfirmationUnitOfWork,
    draft: ServiceDraft,
    actor: Actor,
    *,
    allowed_chat_ids: tuple[str, ...],
) -> ConfirmationResult:
    reply_text = _reply_text(draft)
    target_chat_id = _reply_target_chat_id(uow, draft)
    trace_id = f"reply-send:{draft.id}"
    send_request = uow.get_send_request_by_trace_id(trace_id)
    side_effect = "customer_reply_send_request_reused"
    if send_request is None:
        target_allowed = target_chat_id in set(allowed_chat_ids)
        now = datetime.now(timezone.utc)
        send_request = TelegramSendRequest(
            id=uuid4(),
            target_chat_id=target_chat_id,
            message_text=reply_text,
            source_service_draft_id=draft.id,
            send_purpose=CUSTOMER_REPLY_SEND_PURPOSE,
            message_text_summary=summarize_message_text(reply_text),
            status="pending_confirmation" if target_allowed else "blocked",
            requested_by_actor_type=actor.actor_type,
            requested_by_actor_id=actor.actor_id,
            allowlist_snapshot={
                "target_allowed": target_allowed,
                "allowed_chat_count": len(allowed_chat_ids),
                "send_purpose": "customer_reply_rehearsal",
            },
            last_error_code=None if target_allowed else NOT_ALLOWLISTED_ERROR,
            trace_id=trace_id,
            created_at=now,
            updated_at=now,
        )
        uow.add_send_request(send_request)
        side_effect = "customer_reply_send_request_created"
    else:
        if send_request.source_service_draft_id is None:
            send_request.source_service_draft_id = draft.id
        send_request.send_purpose = CUSTOMER_REPLY_SEND_PURPOSE
        if send_request.message_text_summary is None:
            send_request.message_text_summary = summarize_message_text(
                send_request.message_text,
            )

    draft.status = "confirmed"
    draft.confirmed_at = datetime.now(timezone.utc)
    draft.payload = {
        **draft.payload,
        "send_request_created": True,
        "telegram_send_request_id": str(send_request.id),
    }
    record_audit_event(
        uow,
        trace_id=draft.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="customer_reply_send_requested",
        entity_type="telegram_send_request",
        entity_id=send_request.id,
        after_state={
            "draft_id": str(draft.id),
            "status": send_request.status,
            "target_allowed": send_request.status == "pending_confirmation",
            "side_effect": side_effect,
        },
        permission_snapshot={"role": actor.role, "action": "confirm_draft"},
    )
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
            "telegram_send_request_id": str(send_request.id),
            "side_effect": side_effect,
        },
        permission_snapshot={"role": actor.role, "action": "confirm_draft"},
    )
    return ConfirmationResult(
        telegram_send_request=send_request,
        side_effect=side_effect,
    )


def _confirm_stage05_business_draft(
    uow: ConfirmationUnitOfWork,
    draft: ServiceDraft,
    actor: Actor,
) -> ConfirmationResult:
    approved_by_user_id = UUID(actor.actor_id)
    service_record = _create_noop_service_record(draft, approved_by_user_id)
    execution_log = _create_noop_execution_log(draft, service_record)
    draft.status = "service_record_created"
    draft.confirmed_at = datetime.now(timezone.utc)
    uow.add_service_record(service_record)
    uow.add_execution_log(execution_log)
    record_audit_event(
        uow,
        trace_id=draft.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="business_noop_evidence_created",
        entity_type="service_record",
        entity_id=service_record.id,
        after_state={
            "draft_id": str(draft.id),
            "draft_type": draft.draft_type,
            "service_record_id": str(service_record.id),
            "execution_log_id": str(execution_log.id),
            "provider_execution_allowed": False,
        },
        permission_snapshot={"role": actor.role, "action": "confirm_draft"},
    )
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
            "execution_log_id": str(execution_log.id),
            "execution_ticket_id": None,
            "side_effect": "noop_service_evidence_created",
        },
        permission_snapshot={"role": actor.role, "action": "confirm_draft"},
    )
    return ConfirmationResult(
        service_record=service_record,
        execution_log=execution_log,
        side_effect="noop_service_evidence_created",
    )


def _reply_text(draft: ServiceDraft) -> str:
    value = draft.payload.get("reply_text")
    if value is None or not str(value).strip():
        raise ConfirmationStateError("Draft has no reply_text")
    return str(value).strip()


def _reply_target_chat_id(
    uow: ConfirmationUnitOfWork,
    draft: ServiceDraft,
) -> str:
    payload_target = draft.payload.get("target_chat_id")
    if payload_target is not None and str(payload_target).strip():
        return str(payload_target).strip()
    if draft.source_message_id is None:
        raise ConfirmationStateError("Draft has no source message")
    message = uow.get_source_message(draft.source_message_id)
    if message is None or not message.telegram_chat_id:
        raise ConfirmationStateError("Draft has no source Telegram chat")
    return message.telegram_chat_id


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


def _create_noop_service_record(
    draft: ServiceDraft,
    confirmed_by_user_id: UUID,
) -> ServiceRecord:
    return ServiceRecord(
        id=uuid4(),
        service_type=draft.draft_type,
        status="recorded",
        customer_id=draft.customer_id,
        account_asset_id=draft.account_asset_id,
        source_draft_id=draft.id,
        confirmed_by_user_id=confirmed_by_user_id,
        confirmed_at=datetime.now(timezone.utc),
        idempotency_key=f"service:{draft.id}",
        trace_id=draft.trace_id,
    )


def _create_noop_execution_log(
    draft: ServiceDraft,
    service_record: ServiceRecord,
) -> ExecutionLog:
    return ExecutionLog(
        id=uuid4(),
        service_record=service_record,
        service_record_id=service_record.id,
        provider="noop",
        provider_request_id=f"noop-execution:{service_record.id}",
        provider_response_id=None,
        execution_status="skipped",
        request_summary={
            "draft_id": str(draft.id),
            "draft_type": draft.draft_type,
            "provider_execution_allowed": False,
        },
        response_summary={
            "external_call_performed": False,
            "reason": "stage05_noop_evidence_only",
        },
        error_code=None,
        error_message_redacted=None,
        executed_at=datetime.now(timezone.utc),
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
