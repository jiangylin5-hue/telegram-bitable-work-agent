from datetime import UTC, datetime, timedelta
import importlib.util
import json
import os
from uuid import UUID, uuid4

import pytest

from app.models.agent_event_runtime import AgentOutboxEvent
from app.queues.redis_streams import RedisStreamsClient
from app.schemas.agent_event_runtime import AgentCommandEnvelope, AgentEventEnvelope
from app.services.agent_event_runtime import (
    InMemoryAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_orchestrator import (
    SpecialistCommandDispatch,
    dispatch_specialist_commands,
    fail_specialist_command,
)
from app.workers.agent_tabular_runtime import AgentTabularStreamWorker


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


def test_real_redis_worker_crash_is_claimed_and_acked_exactly_once() -> None:
    from redis import Redis

    raw = Redis.from_url(
        os.environ[REDIS_URL_ENV],
        decode_responses=False,
        socket_connect_timeout=2,
    )
    streams = RedisStreamsClient(raw)
    suffix = uuid4().hex
    stream_name = f"stage12-task8-crash-{suffix}"
    group_name = f"stage12-task8-workers-{suffix}"
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
        deadline_at=datetime(2026, 7, 30, 12, 5, tzinfo=UTC),
        idempotency_key_hash="b" * 64,
    )
    assert streams.xadd_once(
        stream_name,
        idempotency_key=str(envelope.command_id),
        fields={
            "schema_version": envelope.schema_version,
            "payload": envelope.model_dump_json(),
        },
    )
    calls: list[str] = []

    def crash(_envelope: AgentCommandEnvelope) -> None:
        calls.append("crash")
        raise RuntimeError("stage12_task8_worker_crash")

    first = AgentTabularStreamWorker(
        streams=streams,
        consumer_name="worker-a",
        process=crash,
        stream_name=stream_name,
        group_name=group_name,
        pending_min_idle_ms=0,
    )
    try:
        with pytest.raises(RuntimeError, match="stage12_task8_worker_crash"):
            first.run_once()
        assert raw.xpending(stream_name, group_name)["pending"] == 1

        recovery = AgentTabularStreamWorker(
            streams=streams,
            consumer_name="worker-b",
            process=lambda item: calls.append(str(item.command_id)),
            stream_name=stream_name,
            group_name=group_name,
            pending_min_idle_ms=0,
        )
        result = recovery.run_once()

        assert result.recovered == 1
        assert result.processed == 1
        assert raw.xpending(stream_name, group_name)["pending"] == 0
        assert recovery.run_once().processed == 0
        assert calls == ["crash", str(envelope.command_id)]
    finally:
        raw.delete(stream_name)
        raw.close()


def test_real_redis_drains_terminalized_sibling_without_reexecution() -> None:
    from redis import Redis

    raw = Redis.from_url(
        os.environ[REDIS_URL_ENV],
        decode_responses=False,
        socket_connect_timeout=2,
    )
    streams = RedisStreamsClient(raw)
    suffix = uuid4().hex
    group_name = f"stage12-task8-workers-{suffix}"
    tabular_stream = f"stage12-task8-tabular-{suffix}"
    risk_stream = f"stage12-task8-risk-{suffix}"
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    scope_hash = "a" * 64
    run = create_agent_run(
        runtime,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash=scope_hash,
        idempotency_key_hash="c" * 64,
        deadline_at=now + timedelta(minutes=5),
        now=now,
        workflow_version="stage12.task8.v1",
    ).run
    required, sibling = dispatch_specialist_commands(
        runtime,
        run_id=run.id,
        dispatches=(
            SpecialistCommandDispatch(
                target_capability="platform.tabular.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
                required=True,
            ),
            SpecialistCommandDispatch(
                target_capability="platform.risk.analyse",
                payload_ref=f"agent-private-input:{uuid4()}",
                required=False,
            ),
        ),
        authorization_hash=scope_hash,
        now=now,
    )
    streams_by_command = {required.id: tabular_stream, sibling.id: risk_stream}
    for command in (required, sibling):
        outbox = runtime.get_outbox_event_by_event_id(command.id)
        assert outbox is not None
        envelope = AgentCommandEnvelope.model_validate_json(
            json.dumps(outbox.payload_json)
        )
        assert streams.xadd_once(
            streams_by_command[command.id],
            idempotency_key=str(command.id),
            fields={
                "schema_version": envelope.schema_version,
                "payload": envelope.model_dump_json(),
            },
        )
    calls: list[str] = []

    def fail_required(envelope: AgentCommandEnvelope) -> None:
        calls.append("required-failed")
        fail_specialist_command(
            runtime,
            command_id=envelope.command_id,
            authorization_hash=scope_hash,
            worker_id="worker-required",
            now=now + timedelta(seconds=1),
        )

    def drain_sibling(envelope: AgentCommandEnvelope) -> None:
        calls.append("sibling-drained")
        assert runtime.get_command(envelope.command_id).status == "failed"
        fail_specialist_command(
            runtime,
            command_id=envelope.command_id,
            authorization_hash=scope_hash,
            worker_id="worker-sibling",
            now=now + timedelta(seconds=2),
        )

    required_worker = AgentTabularStreamWorker(
        streams=streams,
        consumer_name="worker-required",
        process=fail_required,
        stream_name=tabular_stream,
        group_name=group_name,
        pending_min_idle_ms=0,
    )
    sibling_worker = AgentTabularStreamWorker(
        streams=streams,
        consumer_name="worker-sibling",
        process=drain_sibling,
        stream_name=risk_stream,
        group_name=group_name,
        pending_min_idle_ms=0,
    )
    try:
        assert required_worker.run_once().processed == 1
        assert run.status == "failed"
        assert required.status == sibling.status == "failed"
        assert sibling_worker.run_once().processed == 1
        assert raw.xpending(tabular_stream, group_name)["pending"] == 0
        assert raw.xpending(risk_stream, group_name)["pending"] == 0
        assert required_worker.run_once().processed == 0
        assert sibling_worker.run_once().processed == 0
        assert calls == ["required-failed", "sibling-drained"]
        assert [item.event_type for item in runtime.events].count("run.failed") == 1
    finally:
        raw.delete(tabular_stream, risk_stream)
        raw.close()
