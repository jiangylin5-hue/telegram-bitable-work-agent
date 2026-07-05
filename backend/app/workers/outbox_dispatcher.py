from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.outbox import OutboxEvent
from app.repositories.outbox import InMemoryOutboxRepository
from app.services.audit import record_audit_event
from app.workers.handlers import OutboxHandler


class RetryableOutboxError(RuntimeError):
    pass


class NonRetryableOutboxError(RuntimeError):
    pass


@dataclass(frozen=True)
class DispatchResult:
    processed: int = 0
    retried: int = 0
    dead_lettered: int = 0
    missing_handler: int = 0

    def add(self, other: "DispatchResult") -> "DispatchResult":
        return DispatchResult(
            processed=self.processed + other.processed,
            retried=self.retried + other.retried,
            dead_lettered=self.dead_lettered + other.dead_lettered,
            missing_handler=self.missing_handler + other.missing_handler,
        )


class OutboxDispatcher:
    def __init__(
        self,
        *,
        repository: InMemoryOutboxRepository,
        handlers: dict[str, OutboxHandler],
        audit_session: object | None = None,
    ) -> None:
        self.repository = repository
        self.handlers = handlers
        self.audit_session = audit_session

    def dispatch_once(self, limit: int = 10) -> DispatchResult:
        result = DispatchResult()
        for event in self.repository.list_ready(limit=limit):
            result = result.add(self._dispatch_event(event))
        return result

    def _dispatch_event(self, event: OutboxEvent) -> DispatchResult:
        handler = self.handlers.get(event.event_type)
        if handler is None:
            return self._mark_dead_letter(
                event,
                error_code="missing_handler",
                message=f"No handler for {event.event_type}",
                count_as_missing_handler=True,
            )

        event.status = "processing"
        self.repository.save(event)

        try:
            handler(event)
        except RetryableOutboxError as exc:
            return self._handle_retryable_failure(event, str(exc))
        except NonRetryableOutboxError as exc:
            return self._mark_dead_letter(
                event,
                error_code="non_retryable",
                message=str(exc),
            )

        event.status = "processed"
        event.dispatched_at = datetime.now(timezone.utc)
        event.processed_at = event.dispatched_at
        event.attempt_count = event.attempts
        self.repository.save(event)
        return DispatchResult(processed=1)

    def _handle_retryable_failure(
        self,
        event: OutboxEvent,
        message: str,
    ) -> DispatchResult:
        event.attempts += 1
        event.attempt_count = event.attempts
        event.last_error_redacted = message
        event.last_error = message
        if event.attempts >= event.max_attempts:
            return self._mark_dead_letter(
                event,
                error_code="retry_exhausted",
                message=message,
                increment_attempts=False,
            )

        event.status = "retry"
        event.next_attempt_at = datetime.now(timezone.utc) + timedelta(
            seconds=2**event.attempts
        )
        event.available_at = event.next_attempt_at
        self.repository.save(event)
        return DispatchResult(retried=1)

    def _mark_dead_letter(
        self,
        event: OutboxEvent,
        *,
        error_code: str,
        message: str,
        count_as_missing_handler: bool = False,
        increment_attempts: bool = True,
    ) -> DispatchResult:
        if increment_attempts and event.status != "dead_letter":
            event.attempts += 1
        event.attempt_count = event.attempts
        event.status = "dead_letter"
        event.last_error_redacted = message
        event.last_error = message
        self.repository.save(event)
        self._record_dead_letter_audit(event, error_code=error_code, message=message)

        if count_as_missing_handler:
            return DispatchResult(dead_lettered=1, missing_handler=1)
        return DispatchResult(dead_lettered=1)

    def _record_dead_letter_audit(
        self,
        event: OutboxEvent,
        *,
        error_code: str,
        message: str,
    ) -> None:
        if self.audit_session is None:
            return

        record_audit_event(
            self.audit_session,
            trace_id=event.trace_id,
            actor_type="worker",
            actor_id="outbox_dispatcher",
            event_type="outbox_dead_letter",
            entity_type="outbox_event",
            entity_id=event.id,
            after_state={
                "event_type": event.event_type,
                "status": event.status,
                "attempts": event.attempts,
                "error_code": error_code,
                "error_message": message,
            },
        )


__all__ = [
    "DispatchResult",
    "InMemoryOutboxRepository",
    "NonRetryableOutboxError",
    "OutboxDispatcher",
    "RetryableOutboxError",
]
