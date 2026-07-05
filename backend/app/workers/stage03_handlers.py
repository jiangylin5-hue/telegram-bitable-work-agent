from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.outbox import OutboxEvent
from app.models.telegram import Message
from app.services.audit import record_audit_event
from app.services.telegram_ingestion import IngestedMessage


class RetryableStage03WorkerError(RuntimeError):
    pass


class NonRetryableStage03WorkerError(RuntimeError):
    pass


class Stage03WorkerUnitOfWork(Protocol):
    def get_outbox_event(self, event_id: str) -> OutboxEvent | None:
        pass

    def get_message(self, message_id: str) -> IngestedMessage | Message | None:
        pass

    def save_outbox_event(self, event: OutboxEvent) -> None:
        pass

    def save_message(self, message: IngestedMessage | Message) -> None:
        pass

    def add(self, value: object) -> None:
        pass

    def commit(self) -> None:
        pass


class InMemoryStage03WorkerUnitOfWork:
    def __init__(
        self,
        *,
        messages: Iterable[IngestedMessage] | None = None,
        outbox_events: Iterable[OutboxEvent] | None = None,
    ) -> None:
        self.messages = {str(message.id): message for message in messages or []}
        self.outbox_events = {
            str(event.id): event for event in outbox_events or []
        }
        self.audit_events: list[object] = []
        self.commits = 0
        self.saved_messages: list[IngestedMessage | Message] = []
        self.saved_outbox_events: list[OutboxEvent] = []

    def get_outbox_event(self, event_id: str) -> OutboxEvent | None:
        return self.outbox_events.get(event_id)

    def get_message(self, message_id: str) -> IngestedMessage | Message | None:
        return self.messages.get(message_id)

    def save_outbox_event(self, event: OutboxEvent) -> None:
        self.saved_outbox_events.append(event)

    def save_message(self, message: IngestedMessage | Message) -> None:
        self.saved_messages.append(message)

    def add(self, value: object) -> None:
        self.audit_events.append(value)

    def commit(self) -> None:
        self.commits += 1


class SqlAlchemyStage03WorkerUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_outbox_event(self, event_id: str) -> OutboxEvent | None:
        return self.session.get(OutboxEvent, UUID(event_id))

    def get_message(self, message_id: str) -> Message | None:
        return self.session.get(Message, UUID(message_id))

    def save_outbox_event(self, event: OutboxEvent) -> None:
        self.session.add(event)

    def save_message(self, message: IngestedMessage | Message) -> None:
        self.session.add(message)

    def add(self, value: object) -> None:
        self.session.add(value)

    def commit(self) -> None:
        self.session.commit()


def handle_telegram_message_received(
    fields: dict[str, str],
    uow: Stage03WorkerUnitOfWork,
) -> None:
    event = _load_outbox_event(fields, uow)
    message = _load_message(fields, event, uow)

    if event.status == "processed" and message.processing_status == "processed":
        return

    now = datetime.now(timezone.utc)
    message.processing_status = "processed"
    message.outbox_status = "processed"
    message.last_error_code = None
    message.processed_at = now
    event.status = "processed"
    event.dispatched_at = now
    event.processed_at = now
    event.attempt_count = event.attempts

    uow.save_message(message)
    uow.save_outbox_event(event)
    record_audit_event(
        uow,
        trace_id=event.trace_id,
        actor_type="worker",
        actor_id="stage03_redis_streams_worker",
        event_type="telegram.message_processed",
        entity_type="message",
        entity_id=message.id,
        after_state={
            "message_id": str(message.id),
            "outbox_event_id": str(event.id),
            "processing_status": message.processing_status,
            "outbox_status": message.outbox_status,
            "binding_status": message.binding_status,
            "customer_id": _string_or_none(message.customer_id),
        },
    )
    uow.commit()


def mark_message_processing_failure(
    fields: dict[str, str],
    uow: Stage03WorkerUnitOfWork,
    *,
    error_code: str,
    retryable: bool,
) -> str:
    event = _load_outbox_event(fields, uow)
    message = _load_message(fields, event, uow)
    now = datetime.now(timezone.utc)

    event.attempts += 1
    event.attempt_count = event.attempts
    event.last_error = error_code
    event.last_error_redacted = error_code

    exhausted = (not retryable) or event.attempts >= event.max_attempts
    if exhausted:
        disposition = "dead_letter"
        audit_type = "telegram.message_dead_letter"
        event.status = "dead_letter"
        message.processing_status = "dead_letter"
        message.outbox_status = "dead_letter"
        message.processed_at = now
    else:
        disposition = "retry"
        audit_type = "telegram.message_processing_retry"
        event.status = "retry"
        event.next_attempt_at = now + timedelta(seconds=2**event.attempts)
        event.available_at = event.next_attempt_at
        message.processing_status = "retrying"
        message.outbox_status = "retry"

    message.last_error_code = error_code
    uow.save_message(message)
    uow.save_outbox_event(event)
    record_audit_event(
        uow,
        trace_id=event.trace_id,
        actor_type="worker",
        actor_id="stage03_redis_streams_worker",
        event_type=audit_type,
        entity_type="message",
        entity_id=message.id,
        after_state={
            "message_id": str(message.id),
            "outbox_event_id": str(event.id),
            "processing_status": message.processing_status,
            "outbox_status": message.outbox_status,
            "attempts": event.attempts,
            "error_code": error_code,
        },
    )
    uow.commit()
    return disposition


def _load_outbox_event(
    fields: dict[str, str],
    uow: Stage03WorkerUnitOfWork,
) -> OutboxEvent:
    event_id = fields.get("event_id")
    if event_id is None:
        raise NonRetryableStage03WorkerError("missing_event_id")
    event = uow.get_outbox_event(event_id)
    if event is None:
        raise NonRetryableStage03WorkerError("outbox_event_not_found")
    return event


def _load_message(
    fields: dict[str, str],
    event: OutboxEvent,
    uow: Stage03WorkerUnitOfWork,
) -> IngestedMessage | Message:
    message_id = fields.get("message_id") or event.payload.get("message_id")
    if message_id is None:
        raise NonRetryableStage03WorkerError("missing_message_id")
    message = uow.get_message(str(message_id))
    if message is None:
        raise NonRetryableStage03WorkerError("message_not_found")
    return message


def _string_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)
