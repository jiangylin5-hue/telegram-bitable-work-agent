from datetime import UTC, datetime, timedelta
import hashlib
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
from app.core.config import Settings
from app.workers.agent_specialist_runtime import (
    AgentSpecialistWorkerPool,
    build_typed_specialist_process_registry,
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


def test_specialist_pool_consumes_each_stream_with_its_own_handler() -> None:
    streams = InMemoryRedisStreams()
    envelopes = []
    for index, (capability, command_type) in enumerate(
        (
            ("platform.tabular.analyse", "analyse_visible_records"),
            ("platform.risk.analyse", "analyse_visible_risks"),
            ("platform.daily.summarise", "summarise_visible_operations"),
            ("platform.action.propose", "propose_controlled_action"),
        ),
        start=1,
    ):
        envelope = AgentCommandEnvelope(
            command_id=uuid4(),
            run_id=uuid4(),
            causation_id=uuid4(),
            correlation_id=uuid4(),
            sequence=index,
            target_capability=capability,
            command_type=command_type,
            scope_proof_ref="scope:sha256:" + "a" * 64,
            input_artifact_refs=(),
            deadline_at=NOW + timedelta(minutes=2),
            idempotency_key_hash=hashlib.sha256(capability.encode()).hexdigest(),
        )
        streams.xadd_once(
            f"agent.commands.{capability}",
            idempotency_key=str(envelope.command_id),
            fields={
                "schema_version": envelope.schema_version,
                "payload": envelope.model_dump_json(),
            },
        )
        envelopes.append(envelope)
    processed: list[tuple[str, str]] = []
    handlers = {
        capability: (
            lambda envelope, capability=capability: processed.append(
                (capability, envelope.target_capability)
            )
        )
        for capability, _command_type in (
            ("platform.tabular.analyse", "analyse_visible_records"),
            ("platform.risk.analyse", "analyse_visible_risks"),
            ("platform.daily.summarise", "summarise_visible_operations"),
            ("platform.action.propose", "propose_controlled_action"),
        )
    }
    pool = AgentSpecialistWorkerPool(
        streams=streams,
        consumer_name="worker-a",
        process_by_capability=handlers,
        pending_min_idle_ms=0,
    )

    result = pool.run_once()

    assert result.processed == 4
    assert processed == [
        ("platform.tabular.analyse", "platform.tabular.analyse"),
        ("platform.risk.analyse", "platform.risk.analyse"),
        ("platform.daily.summarise", "platform.daily.summarise"),
        ("platform.action.propose", "platform.action.propose"),
    ]
    assert {item.target_capability for item in envelopes} == {
        item.target_capability for item in envelopes
    }


def test_real_worker_registry_owns_four_distinct_typed_handlers() -> None:
    registry = build_typed_specialist_process_registry(
        session_factory=lambda: None,
        settings=Settings(),
        consumer_name="typed-worker",
    )

    assert set(registry) == {
        "platform.tabular.analyse",
        "platform.risk.analyse",
        "platform.daily.summarise",
        "platform.action.propose",
    }
    assert [type(item.typed_handler).__name__ for item in registry.values()] == [
        "TabularSpecialistV2",
        "RiskSpecialistV2",
        "DailySpecialistV2",
        "ActionSpecialistV2",
    ]
    assert len({id(item.typed_handler) for item in registry.values()}) == 4


def test_action_stream_crash_is_recovered_and_acked_once() -> None:
    streams = InMemoryRedisStreams()
    envelope = AgentCommandEnvelope(
        command_id=uuid4(),
        run_id=uuid4(),
        causation_id=uuid4(),
        correlation_id=uuid4(),
        sequence=1,
        target_capability="platform.action.propose",
        command_type="propose_controlled_action",
        scope_proof_ref="scope:sha256:" + "a" * 64,
        input_artifact_refs=(),
        deadline_at=NOW + timedelta(minutes=2),
        idempotency_key_hash="d" * 64,
    )
    stream = "agent.commands.platform.action.propose"
    streams.xadd_once(
        stream,
        idempotency_key=str(envelope.command_id),
        fields={
            "schema_version": envelope.schema_version,
            "payload": envelope.model_dump_json(),
        },
    )
    calls: list[str] = []

    def crash(_envelope: AgentCommandEnvelope) -> None:
        calls.append("crash")
        raise RuntimeError("action worker crashed")

    registry = {
        capability: (
            crash if capability == "platform.action.propose" else lambda _item: None
        )
        for capability in (
            "platform.tabular.analyse",
            "platform.risk.analyse",
            "platform.daily.summarise",
            "platform.action.propose",
        )
    }
    first = AgentSpecialistWorkerPool(
        streams=streams,
        consumer_name="worker-a",
        process_by_capability=registry,
        pending_min_idle_ms=0,
    )

    with pytest.raises(RuntimeError, match="action worker crashed"):
        first.run_once()

    recovered_registry = {
        capability: (
            (lambda item: calls.append(str(item.command_id)))
            if capability == "platform.action.propose"
            else (lambda _item: None)
        )
        for capability in registry
    }
    recovery = AgentSpecialistWorkerPool(
        streams=streams,
        consumer_name="worker-b",
        process_by_capability=recovered_registry,
        pending_min_idle_ms=0,
    )
    result = recovery.run_once()

    assert result.recovered == 1
    assert result.processed == 1
    assert calls == ["crash", str(envelope.command_id)]
    action_worker = next(
        item for item in recovery.workers if item.stream_name == stream
    )
    assert streams.pending_count(stream, action_worker.group_name) == 0
