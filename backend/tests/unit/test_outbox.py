from app.models.outbox import OutboxEvent
from app.services.outbox import enqueue_outbox_event
from app.workers.outbox_dispatcher import (
    InMemoryOutboxRepository,
    OutboxDispatcher,
    RetryableOutboxError,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)


def make_event(max_attempts: int = 3) -> OutboxEvent:
    return OutboxEvent(
        event_type="agent.intent_extract",
        payload={"message_id": "message-1"},
        status="pending",
        attempts=0,
        max_attempts=max_attempts,
        idempotency_key="intent:message-1",
        trace_id="trace-1",
    )


def test_enqueue_outbox_event_adds_pending_event_inside_session() -> None:
    session = FakeSession()

    event = enqueue_outbox_event(
        session,
        event_type="agent.intent_extract",
        payload={"message_id": "message-1"},
        idempotency_key="intent:message-1",
        trace_id="trace-1",
        aggregate_type="message",
        aggregate_id="message-1",
    )

    assert session.added == [event]
    assert event.status == "pending"
    assert event.attempts == 0
    assert event.attempt_count == 0
    assert event.max_attempts == 3
    assert event.aggregate_type == "message"
    assert event.aggregate_id == "message-1"
    assert event.available_at is None
    assert event.processed_at is None
    assert event.last_error is None


def test_dispatcher_processes_successful_event() -> None:
    event = make_event()
    repository = InMemoryOutboxRepository([event])
    handled_payloads: list[dict] = []

    dispatcher = OutboxDispatcher(
        repository=repository,
        handlers={
            "agent.intent_extract": lambda handled_event: handled_payloads.append(
                handled_event.payload
            )
        },
    )

    result = dispatcher.dispatch_once()

    assert result.processed == 1
    assert handled_payloads == [{"message_id": "message-1"}]
    assert event.status == "processed"


def test_dispatcher_retries_then_dead_letters_and_writes_audit() -> None:
    event = make_event(max_attempts=2)
    repository = InMemoryOutboxRepository([event])
    session = FakeSession()

    def failing_handler(_event: OutboxEvent) -> None:
        raise RetryableOutboxError("temporary_network")

    dispatcher = OutboxDispatcher(
        repository=repository,
        handlers={"agent.intent_extract": failing_handler},
        audit_session=session,
    )

    first_result = dispatcher.dispatch_once()
    second_result = dispatcher.dispatch_once()

    assert first_result.retried == 1
    assert event.attempts == 2
    assert second_result.dead_lettered == 1
    assert event.status == "dead_letter"
    assert len(session.added) == 1
    assert session.added[0].event_type == "outbox_dead_letter"
