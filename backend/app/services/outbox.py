from typing import Any

from app.models.outbox import OutboxEvent


def enqueue_outbox_event(
    session: Any,
    *,
    event_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    trace_id: str,
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    max_attempts: int = 3,
) -> OutboxEvent:
    event = OutboxEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=max_attempts,
        idempotency_key=idempotency_key,
        trace_id=trace_id,
    )
    session.add(event)
    return event
