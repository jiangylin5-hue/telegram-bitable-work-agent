from datetime import datetime, timezone
from uuid import uuid4

from app.models.outbox import OutboxEvent
from app.queues.redis_streams import InMemoryRedisStreams
from app.repositories.outbox import InMemoryOutboxRepository
from app.services.outbox import OutboxToRedisStreamsBridge


def test_committed_outbox_event_becomes_redis_stream_job() -> None:
    event = _message_event()
    repository = InMemoryOutboxRepository([event])
    streams = InMemoryRedisStreams()
    bridge = OutboxToRedisStreamsBridge(
        repository=repository,
        streams=streams,
        stream_name="local:stage03:events",
    )

    result = bridge.dispatch_once()

    assert result.enqueued == 1
    assert result.skipped == 0
    assert event.status == "enqueued"
    assert repository.saved == [event]
    assert streams.entries("local:stage03:events") == [
        {
            "idempotency_key": event.idempotency_key,
            "fields": {
                "event_id": str(event.id),
                "event_type": "telegram.message_received",
                "trace_id": "tg:update-1",
                "idempotency_key": "telegram.message_received:message-1",
                "message_id": "message-1",
                "created_at": "2026-07-06T10:00:00+00:00",
            },
        }
    ]


def test_rolled_back_outbox_event_is_not_enqueued() -> None:
    repository = InMemoryOutboxRepository()
    streams = InMemoryRedisStreams()
    bridge = OutboxToRedisStreamsBridge(
        repository=repository,
        streams=streams,
        stream_name="local:stage03:events",
    )

    result = bridge.dispatch_once()

    assert result.enqueued == 0
    assert result.skipped == 0
    assert streams.entries("local:stage03:events") == []


def test_bridge_rerun_is_idempotent() -> None:
    event = _message_event()
    repository = InMemoryOutboxRepository([event])
    streams = InMemoryRedisStreams()
    bridge = OutboxToRedisStreamsBridge(
        repository=repository,
        streams=streams,
        stream_name="local:stage03:events",
    )

    first = bridge.dispatch_once()
    second = bridge.dispatch_once()

    assert first.enqueued == 1
    assert second.enqueued == 0
    assert second.skipped == 0
    assert len(streams.entries("local:stage03:events")) == 1
    assert event.status == "enqueued"


def _message_event() -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        event_type="telegram.message_received",
        payload={"message_id": "message-1", "telegram_update_id": "update-1"},
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key="telegram.message_received:message-1",
        trace_id="tg:update-1",
        created_at=datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
    )
