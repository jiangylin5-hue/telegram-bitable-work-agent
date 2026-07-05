from datetime import datetime, timezone
from uuid import uuid4

from app.models.outbox import OutboxEvent
from app.queues.redis_streams import InMemoryRedisStreams
from app.repositories.outbox import InMemoryOutboxRepository
from app.workers.stage03_outbox_bridge_runtime import (
    create_stage03_outbox_bridge,
)
from app.workers.stage03_runtime import DEFAULT_STAGE03_STREAM_NAME


def test_stage03_outbox_bridge_factory_wires_repository_to_streams() -> None:
    event = OutboxEvent(
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
    repository = InMemoryOutboxRepository([event])
    streams = InMemoryRedisStreams()

    bridge = create_stage03_outbox_bridge(
        repository=repository,
        streams=streams,
    )
    result = bridge.dispatch_once()

    assert result.enqueued == 1
    assert streams.entries(DEFAULT_STAGE03_STREAM_NAME) == [
        {
            "idempotency_key": "telegram.message_received:message-1",
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
