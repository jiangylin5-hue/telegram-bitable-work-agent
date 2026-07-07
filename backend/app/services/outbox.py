from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from app.models.outbox import OutboxEvent
from app.queues.redis_streams import RedisStreams


class ReadyOutboxRepository(Protocol):
    def list_ready(self, limit: int = 10) -> list[OutboxEvent]:
        pass

    def save(self, event: OutboxEvent) -> None:
        pass


@dataclass(frozen=True)
class RedisBridgeResult:
    enqueued: int = 0
    skipped: int = 0

    def add(self, other: "RedisBridgeResult") -> "RedisBridgeResult":
        return RedisBridgeResult(
            enqueued=self.enqueued + other.enqueued,
            skipped=self.skipped + other.skipped,
        )


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


class OutboxToRedisStreamsBridge:
    def __init__(
        self,
        *,
        repository: ReadyOutboxRepository,
        streams: RedisStreams,
        stream_name: str,
    ) -> None:
        self.repository = repository
        self.streams = streams
        self.stream_name = stream_name

    def dispatch_once(self, limit: int = 10) -> RedisBridgeResult:
        result = RedisBridgeResult()
        for event in self.repository.list_ready(limit=limit):
            result = result.add(self._enqueue_event(event))
        return result

    def _enqueue_event(self, event: OutboxEvent) -> RedisBridgeResult:
        was_added = self.streams.xadd_once(
            self.stream_name,
            idempotency_key=event.idempotency_key,
            fields=self._to_stream_fields(event),
        )
        event.status = "enqueued"
        event.dispatched_at = datetime.now(timezone.utc)
        self.repository.save(event)

        if was_added:
            return RedisBridgeResult(enqueued=1)
        return RedisBridgeResult(skipped=1)

    def _to_stream_fields(self, event: OutboxEvent) -> dict[str, str]:
        created_at = event.created_at
        if created_at is None:
            created_at = datetime.now(timezone.utc)

        fields = {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "trace_id": event.trace_id,
            "idempotency_key": event.idempotency_key,
            "created_at": created_at.isoformat(),
        }

        message_id = event.payload.get("message_id")
        if message_id is not None:
            fields["message_id"] = str(message_id)
        request_id = event.payload.get("request_id")
        if request_id is not None:
            fields["request_id"] = str(request_id)

        return fields
