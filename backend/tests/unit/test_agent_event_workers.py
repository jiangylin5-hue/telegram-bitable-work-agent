from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.agent_event_runtime import AgentOutboxEvent
from app.queues.redis_streams import InMemoryRedisStreams
from app.schemas.agent_event_runtime import AgentCommandEnvelope
from app.workers.agent_event_outbox_runtime import publish_due_outbox_rows
from app.workers.agent_tabular_runtime import (
    AgentTabularStreamWorker,
    _fail_terminal_command,
)


NOW = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)


def _command_outbox() -> AgentOutboxEvent:
    envelope = AgentCommandEnvelope(
        command_id=uuid4(),
        run_id=uuid4(),
        causation_id=uuid4(),
        correlation_id=uuid4(),
        sequence=1,
        target_capability="platform.tabular.analyse",
        command_type="analyse_visible_records",
        scope_proof_ref="scope:sha256:" + "a" * 64,
        input_artifact_refs=(),
        deadline_at=NOW + timedelta(minutes=2),
        idempotency_key_hash="b" * 64,
    )
    return AgentOutboxEvent(
        id=uuid4(),
        aggregate_type="agent_command",
        aggregate_id=envelope.run_id,
        topic="agent.commands.platform.tabular.analyse",
        event_id=envelope.command_id,
        payload_json=envelope.model_dump(mode="json"),
        published_at=None,
        publish_attempts=0,
        next_attempt_at=None,
        last_error_code=None,
    )


def test_outbox_publisher_marks_only_after_success_and_schedules_retry() -> None:
    row = _command_outbox()

    class FailingStreams(InMemoryRedisStreams):
        def xadd_once(self, *args, **kwargs):
            raise ConnectionError("secret redis detail")

    result = publish_due_outbox_rows([row], FailingStreams(), now=NOW)

    assert result.failed == 1
    assert row.published_at is None
    assert row.publish_attempts == 1
    assert row.last_error_code == "redis_publish_failed"
    assert row.next_attempt_at == NOW + timedelta(seconds=2)

    row.next_attempt_at = NOW
    streams = InMemoryRedisStreams()
    result = publish_due_outbox_rows([row], streams, now=NOW)
    assert result.published == 1
    assert row.published_at == NOW
    assert len(streams.entries(row.topic)) == 1


def test_worker_does_not_ack_crash_and_recovery_consumer_claims_once() -> None:
    outbox = _command_outbox()
    streams = InMemoryRedisStreams()
    publish_due_outbox_rows([outbox], streams, now=NOW)
    calls: list[str] = []

    def crash(_envelope: AgentCommandEnvelope) -> None:
        calls.append("crash")
        raise RuntimeError("process died")

    first = AgentTabularStreamWorker(
        streams=streams,
        consumer_name="worker-a",
        process=crash,
    )
    with pytest.raises(RuntimeError, match="process died"):
        first.run_once()
    assert streams.pending_count(first.stream_name, first.group_name) == 1

    def recover(envelope: AgentCommandEnvelope) -> None:
        calls.append(str(envelope.command_id))

    recovery = AgentTabularStreamWorker(
        streams=streams,
        consumer_name="worker-b",
        process=recover,
        pending_min_idle_ms=0,
    )
    result = recovery.run_once()

    assert result.recovered == 1
    assert result.processed == 1
    assert streams.pending_count(recovery.stream_name, recovery.group_name) == 0
    assert calls == ["crash", str(outbox.event_id)]


def test_worker_dead_letters_malformed_message_without_exposing_payload() -> None:
    streams = InMemoryRedisStreams()
    stream = "agent.commands.platform.tabular.analyse"
    streams.xadd_once(stream, idempotency_key="bad", fields={"payload": "{}"})
    worker = AgentTabularStreamWorker(
        streams=streams,
        consumer_name="worker-a",
        process=lambda _envelope: None,
    )

    result = worker.run_once()

    assert result.dead_lettered == 1
    assert result.processed == 0
    assert streams.pending_count(stream, worker.group_name) == 0
    dead_letters = streams.entries(f"{stream}.dead-letter")
    assert len(dead_letters) == 1
    assert dead_letters[0]["fields"] == {
        "source_stream": stream,
        "source_entry_id": "1-0",
        "error_code": "agent_command_stream_invalid",
    }
    assert "payload" not in dead_letters[0]["fields"]


def test_terminal_scope_or_input_failure_consumes_private_input_and_fails_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Session:
        rolled_back = 0
        committed = 0

        def rollback(self) -> None:
            self.rolled_back += 1

        def commit(self) -> None:
            self.committed += 1

    class PrivateInput:
        consumed_at = None

    class Uow:
        private_input = PrivateInput()

        def get_private_input(self, private_input_id, *, for_update=False):
            assert private_input_id == "private-input"
            assert for_update is True
            return self.private_input

    session = Session()
    uow = Uow()
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "app.workers.agent_tabular_runtime.SqlAlchemyAgentEventRuntimeUnitOfWork",
        lambda value: uow,
    )

    def fail(runtime_uow, **kwargs):
        captured.update({"uow": runtime_uow, **kwargs})

    monkeypatch.setattr(
        "app.workers.agent_tabular_runtime.fail_specialist_command",
        fail,
    )

    _fail_terminal_command(
        session,
        command_id="command",
        private_input_id="private-input",
        authorization_hash="a" * 64,
        worker_id="worker-a",
    )

    assert session.rolled_back == 1
    assert session.committed == 1
    assert uow.private_input.consumed_at is not None
    assert captured["uow"] is uow
    assert captured["command_id"] == "command"
