from __future__ import annotations

from datetime import datetime
import json

from app.models.agent_event_runtime import AgentOutboxEvent
from app.queues.redis_streams import RedisStreams
from app.schemas.agent_event_runtime import AgentCommandEnvelope, AgentEventEnvelope


def publish_agent_outbox_event(
    outbox: AgentOutboxEvent,
    streams: RedisStreams,
    *,
    now: datetime,
) -> bool:
    # Outbox payloads cross a JSON persistence boundary, so UUID and datetime
    # values are represented as strings.  Keep the in-process schema strict,
    # but validate this boundary with Pydantic's JSON-aware parser.
    envelope = AgentEventEnvelope.model_validate_json(
        json.dumps(outbox.payload_json, ensure_ascii=False, separators=(",", ":"))
    )
    if envelope.event_id != outbox.event_id or envelope.run_id != outbox.aggregate_id:
        raise ValueError("agent_outbox_identity_mismatch")
    if outbox.topic != "agent.events":
        raise ValueError("agent_outbox_topic_invalid")
    if outbox.published_at is not None:
        return False

    published = streams.xadd_once(
        outbox.topic,
        idempotency_key=str(outbox.event_id),
        fields={
            "schema_version": envelope.schema_version,
            "payload": json.dumps(
                envelope.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )
    outbox.publish_attempts += 1
    outbox.published_at = now
    outbox.next_attempt_at = None
    outbox.last_error_code = None
    return published


def publish_agent_command_outbox(
    outbox: AgentOutboxEvent,
    streams: RedisStreams,
    *,
    now: datetime,
) -> bool:
    envelope = AgentCommandEnvelope.model_validate_json(
        json.dumps(outbox.payload_json, ensure_ascii=False, separators=(",", ":"))
    )
    expected_topic = f"agent.commands.{envelope.target_capability}"
    if envelope.command_id != outbox.event_id or envelope.run_id != outbox.aggregate_id:
        raise ValueError("agent_outbox_identity_mismatch")
    if outbox.aggregate_type != "agent_command" or outbox.topic != expected_topic:
        raise ValueError("agent_outbox_topic_invalid")
    if outbox.published_at is not None:
        return False

    published = streams.xadd_once(
        outbox.topic,
        idempotency_key=str(outbox.event_id),
        fields={
            "schema_version": envelope.schema_version,
            "payload": json.dumps(
                envelope.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )
    outbox.publish_attempts += 1
    outbox.published_at = now
    outbox.next_attempt_at = None
    outbox.last_error_code = None
    return published


__all__ = ["publish_agent_command_outbox", "publish_agent_outbox_event"]
