from datetime import UTC, datetime
import importlib.util
import os
from uuid import UUID, uuid4

import pytest

from app.models.agent_event_runtime import AgentOutboxEvent
from app.queues.redis_streams import RedisStreamsClient
from app.schemas.agent_event_runtime import AgentEventEnvelope


REDIS_URL_ENV = "STAGE10_REDIS_URL"
pytestmark = pytest.mark.skipif(
    not os.getenv(REDIS_URL_ENV) or importlib.util.find_spec("redis") is None,
    reason=f"{REDIS_URL_ENV} and the redis package are required for Stage10 Redis evidence",
)


def test_real_redis_duplicate_publish_pending_claim_and_ack() -> None:
    from redis import Redis

    redis_url = os.environ[REDIS_URL_ENV]
    stream_name = f"stage10-test-agent-events-{uuid4().hex}"
    raw = Redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=2)
    streams = RedisStreamsClient(raw)
    now = datetime(2026, 7, 28, 11, 0, tzinfo=UTC)
    payload = AgentEventEnvelope(
        event_id=uuid4(),
        run_id=uuid4(),
        causation_id=uuid4(),
        correlation_id=uuid4(),
        sequence=1,
        event_type="run.accepted",
        status="accepted",
        source_role="supervisor",
        safe_summary="真实 Redis 测试",
        occurred_at=now,
    ).model_dump(mode="json")
    outbox = AgentOutboxEvent(
        id=uuid4(),
        aggregate_type="agent_run",
        aggregate_id=UUID(str(payload["run_id"])),
        topic="agent.events",
        event_id=UUID(str(payload["event_id"])),
        payload_json=payload,
        published_at=None,
        publish_attempts=0,
        next_attempt_at=None,
        last_error_code=None,
    )
    try:
        # The production publisher fixes the public stream name.  Isolate this
        # test by temporarily rewriting the exact row topic and calling the
        # lower-level adapter for pending recovery semantics.
        assert streams.xadd_once(
            stream_name,
            idempotency_key=str(outbox.event_id),
            fields={"schema_version": "agent-event.v1", "payload": "{}"},
        )
        assert not streams.xadd_once(
            stream_name,
            idempotency_key=str(outbox.event_id),
            fields={"schema_version": "agent-event.v1", "payload": "{}"},
        )
        delivered = streams.read_group(
            stream_name,
            group_name="orchestrator",
            consumer_name="worker-a",
        )
        claimed = streams.claim_pending(
            stream_name,
            group_name="orchestrator",
            consumer_name="worker-b",
            min_idle_ms=0,
        )
        assert len(delivered) == 1
        assert [item.entry_id for item in claimed] == [delivered[0].entry_id]
        assert streams.ack(
            stream_name,
            group_name="orchestrator",
            entry_id=delivered[0].entry_id,
        )
    finally:
        raw.delete(stream_name)
        raw.close()
