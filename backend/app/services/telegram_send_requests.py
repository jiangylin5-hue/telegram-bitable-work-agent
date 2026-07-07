from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.audit import OpsAuditEvent
from app.models.outbox import OutboxEvent
from app.models.telegram import TelegramSendRequest
from app.schemas.telegram_send_requests import TelegramSendRequestCreate
from app.services.audit import record_audit_event
from app.services.permissions import Actor, assert_action_allowed

NOT_ALLOWLISTED_ERROR = "telegram_test_send_target_not_allowlisted"


class TelegramSendRequestNotFound(LookupError):
    pass


class TelegramSendRequestStateError(ValueError):
    pass


class TelegramTestSendTargetNotAllowlisted(ValueError):
    pass


class TelegramSendRequestUnitOfWork(Protocol):
    audit_session: object

    def add_send_request(self, request: TelegramSendRequest) -> None:
        ...

    def get_send_request(self, request_id: UUID) -> TelegramSendRequest | None:
        ...

    def add_outbox_event(self, event: OutboxEvent) -> None:
        ...

    def flush(self) -> None:
        ...

    def commit(self) -> None:
        ...


class InMemoryTelegramSendRequestUnitOfWork:
    def __init__(
        self,
        *,
        send_requests: Iterable[TelegramSendRequest] | None = None,
        outbox_events: Iterable[OutboxEvent] | None = None,
    ) -> None:
        self.send_requests = list(send_requests or [])
        self.outbox_events = list(outbox_events or [])
        self.audit_events: list[OpsAuditEvent] = []
        self.committed = False
        self.flushed = False
        self.audit_session = self

    def add(self, value: object) -> None:
        if isinstance(value, OpsAuditEvent):
            self.audit_events.append(value)
            return
        raise TypeError(f"Unsupported in-memory value: {type(value)!r}")

    def add_send_request(self, request: TelegramSendRequest) -> None:
        self.send_requests.append(request)

    def get_send_request(self, request_id: UUID) -> TelegramSendRequest | None:
        return next(
            (request for request in self.send_requests if request.id == request_id),
            None,
        )

    def add_outbox_event(self, event: OutboxEvent) -> None:
        self.outbox_events.append(event)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True


class SqlAlchemyTelegramSendRequestUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit_session = session

    def add_send_request(self, request: TelegramSendRequest) -> None:
        self.session.add(request)

    def get_send_request(self, request_id: UUID) -> TelegramSendRequest | None:
        return self.session.get(TelegramSendRequest, request_id)

    def add_outbox_event(self, event: OutboxEvent) -> None:
        self.session.add(event)

    def flush(self) -> None:
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()


def create_test_send_request(
    uow: TelegramSendRequestUnitOfWork,
    *,
    actor: Actor,
    request: TelegramSendRequestCreate,
    allowed_chat_ids: tuple[str, ...],
) -> TelegramSendRequest:
    trace_id = f"tg-send:{uuid4()}"
    assert_action_allowed(
        actor,
        "request_test_telegram_send",
        session=uow.audit_session,
        trace_id=trace_id,
        entity_type="telegram_send_request",
    )
    target_allowed = _is_target_allowlisted(
        request.target_chat_id,
        allowed_chat_ids,
    )
    now = datetime.now(timezone.utc)
    send_request = TelegramSendRequest(
        id=uuid4(),
        target_chat_id=request.target_chat_id,
        message_text=request.message_text,
        status="pending_confirmation" if target_allowed else "blocked",
        requested_by_actor_type=actor.actor_type,
        requested_by_actor_id=actor.actor_id,
        allowlist_snapshot=_allowlist_snapshot(
            allowed=target_allowed,
            allowed_chat_ids=allowed_chat_ids,
        ),
        last_error_code=None if target_allowed else NOT_ALLOWLISTED_ERROR,
        trace_id=trace_id,
        created_at=now,
        updated_at=now,
    )
    uow.add_send_request(send_request)
    uow.flush()
    record_audit_event(
        uow.audit_session,
        trace_id=trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="telegram.test_send.requested",
        entity_type="telegram_send_request",
        entity_id=send_request.id,
        after_state={
            "request_id": str(send_request.id),
            "status": send_request.status,
            "target_allowed": target_allowed,
        },
    )
    return send_request


def confirm_test_send_request(
    uow: TelegramSendRequestUnitOfWork,
    *,
    actor: Actor,
    request_id: UUID,
    allowed_chat_ids: tuple[str, ...],
) -> tuple[TelegramSendRequest, OutboxEvent]:
    trace_id = f"tg-send-confirm:{request_id}"
    assert_action_allowed(
        actor,
        "confirm_test_telegram_send",
        session=uow.audit_session,
        trace_id=trace_id,
        entity_type="telegram_send_request",
        entity_id=request_id,
    )
    send_request = uow.get_send_request(request_id)
    if send_request is None:
        raise TelegramSendRequestNotFound(f"Telegram send request {request_id} not found")
    if send_request.status != "pending_confirmation":
        raise TelegramSendRequestStateError(
            f"Telegram send request {request_id} is {send_request.status}"
        )
    if not _is_target_allowlisted(send_request.target_chat_id, allowed_chat_ids):
        send_request.status = "blocked"
        send_request.last_error_code = NOT_ALLOWLISTED_ERROR
        send_request.updated_at = datetime.now(timezone.utc)
        uow.flush()
        record_audit_event(
            uow.audit_session,
            trace_id=send_request.trace_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            event_type="telegram.test_send.blocked",
            entity_type="telegram_send_request",
            entity_id=send_request.id,
            after_state={
                "request_id": str(send_request.id),
                "status": send_request.status,
                "error_code": NOT_ALLOWLISTED_ERROR,
            },
        )
        raise TelegramTestSendTargetNotAllowlisted(NOT_ALLOWLISTED_ERROR)

    now = datetime.now(timezone.utc)
    send_request.status = "confirmed"
    send_request.confirmed_by_actor_type = actor.actor_type
    send_request.confirmed_by_actor_id = actor.actor_id
    send_request.confirmed_at = now
    send_request.allowlist_snapshot = _allowlist_snapshot(
        allowed=True,
        allowed_chat_ids=allowed_chat_ids,
    )
    send_request.updated_at = now
    event = OutboxEvent(
        id=uuid4(),
        event_type="telegram.test_send_requested",
        aggregate_type="telegram_send_request",
        aggregate_id=str(send_request.id),
        payload={"request_id": str(send_request.id)},
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=f"telegram.test_send_requested:{send_request.id}",
        trace_id=send_request.trace_id,
        created_at=now,
    )
    uow.add_outbox_event(event)
    uow.flush()
    record_audit_event(
        uow.audit_session,
        trace_id=send_request.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="telegram.test_send.confirmed",
        entity_type="telegram_send_request",
        entity_id=send_request.id,
        after_state={
            "request_id": str(send_request.id),
            "status": send_request.status,
            "outbox_event_id": str(event.id),
        },
    )
    return send_request, event


def _is_target_allowlisted(target_chat_id: str, allowed_chat_ids: tuple[str, ...]) -> bool:
    return target_chat_id in set(allowed_chat_ids)


def _allowlist_snapshot(
    *,
    allowed: bool,
    allowed_chat_ids: tuple[str, ...],
) -> dict[str, object]:
    return {
        "target_allowed": allowed,
        "allowed_chat_count": len(allowed_chat_ids),
    }
