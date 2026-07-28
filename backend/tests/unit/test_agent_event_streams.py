from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.agent_event_runtime import AgentOutboxEvent
from app.queues.agent_event_streams import (
    publish_agent_command_outbox,
    publish_agent_outbox_event,
)
from app.queues.redis_streams import InMemoryRedisStreams
from app.schemas.agent_event_runtime import AgentCommandEnvelope, AgentEventEnvelope


def _event_payload() -> dict[str, object]:
    run_id = uuid4()
    return AgentEventEnvelope(
        event_id=uuid4(),
        run_id=run_id,
        causation_id=run_id,
        correlation_id=run_id,
        sequence=1,
        event_type="run.accepted",
        status="accepted",
        source_role="supervisor",
        safe_summary="任务已受理",
        occurred_at=datetime(2026, 7, 28, 8, 0, tzinfo=UTC),
    ).model_dump(mode="json")


def test_outbox_publish_is_idempotent_and_marks_receipt_after_stream_write() -> None:
    streams = InMemoryRedisStreams()
    payload = _event_payload()
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
    now = datetime(2026, 7, 28, 8, 1, tzinfo=UTC)

    assert publish_agent_outbox_event(outbox, streams, now=now) is True
    assert publish_agent_outbox_event(outbox, streams, now=now) is False
    assert outbox.published_at == now
    assert outbox.publish_attempts == 1
    assert len(streams.entries("agent.events")) == 1


def test_outbox_publish_rejects_payload_outside_event_contract() -> None:
    streams = InMemoryRedisStreams()
    outbox = AgentOutboxEvent(
        id=uuid4(),
        aggregate_type="agent_run",
        aggregate_id=uuid4(),
        topic="agent.events",
        event_id=uuid4(),
        payload_json={"prompt": "private"},
        published_at=None,
        publish_attempts=0,
        next_attempt_at=None,
        last_error_code=None,
    )

    with pytest.raises(ValidationError):
        publish_agent_outbox_event(
            outbox,
            streams,
            now=datetime(2026, 7, 28, 8, 1, tzinfo=UTC),
        )
    assert streams.entries("agent.events") == []


def test_pending_stream_entry_can_be_claimed_by_recovery_worker() -> None:
    streams = InMemoryRedisStreams()
    streams.xadd_once(
        "agent.events",
        idempotency_key="event-1",
        fields={"payload": "{}"},
    )
    first = streams.read_group(
        "agent.events",
        group_name="orchestrator",
        consumer_name="worker-a",
    )

    claimed = streams.claim_pending(
        "agent.events",
        group_name="orchestrator",
        consumer_name="worker-b",
        min_idle_ms=30_000,
        count=10,
    )

    assert [job.entry_id for job in first] == ["1-0"]
    assert [job.entry_id for job in claimed] == ["1-0"]
    assert streams.ack(
        "agent.events", group_name="orchestrator", entry_id="1-0"
    )


def test_command_outbox_is_validated_and_published_to_registered_stream() -> None:
    streams = InMemoryRedisStreams()
    now = datetime(2026, 7, 28, 8, 0, tzinfo=UTC)
    command = AgentCommandEnvelope(
        command_id=uuid4(),
        run_id=uuid4(),
        causation_id=uuid4(),
        correlation_id=uuid4(),
        sequence=1,
        target_capability="platform.tabular.analyse",
        command_type="analyse_visible_records",
        scope_proof_ref="scope:sha256:" + "a" * 64,
        input_artifact_refs=(),
        deadline_at=now + timedelta(minutes=1),
        idempotency_key_hash="b" * 64,
    )
    outbox = AgentOutboxEvent(
        id=uuid4(),
        aggregate_type="agent_command",
        aggregate_id=command.run_id,
        topic="agent.commands.platform.tabular.analyse",
        event_id=command.command_id,
        payload_json=command.model_dump(mode="json"),
        published_at=None,
        publish_attempts=0,
        next_attempt_at=None,
        last_error_code=None,
    )

    assert publish_agent_command_outbox(outbox, streams, now=now) is True
    jobs = streams.read_group(
        "agent.commands.platform.tabular.analyse",
        group_name="tabular-workers",
        consumer_name="worker-1",
    )
    assert len(jobs) == 1
    assert jobs[0].fields["schema_version"] == "agent-command.v1"
    assert str(command.command_id) in jobs[0].fields["payload"]
