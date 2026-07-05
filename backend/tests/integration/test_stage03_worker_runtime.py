from datetime import datetime, timezone
from uuid import uuid4

from app.models.outbox import OutboxEvent
from app.queues.redis_streams import InMemoryRedisStreams
from app.services.bitable_views import InMemoryBitableViewDataSource, get_view_records
from app.services.telegram_ingestion import IngestedMessage
from app.workers.runner import RedisStreamsWorker
from app.workers.stage03_handlers import (
    InMemoryStage03WorkerUnitOfWork,
    RetryableStage03WorkerError,
    handle_telegram_message_received,
)


STREAM_NAME = "local:stage03:events"
GROUP_NAME = "telegram-message-workers"


def test_worker_processes_message_registration_job() -> None:
    message = _message()
    event = _event(message)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])
    streams = _stream_with_event(event, message)
    worker = _worker(
        streams,
        handlers={
            "telegram.message_received": (
                lambda fields: handle_telegram_message_received(fields, uow)
            )
        },
    )

    result = worker.run_once()

    assert result.processed == 1
    assert result.retried == 0
    assert result.dead_lettered == 0
    assert message.processing_status == "processed"
    assert message.outbox_status == "processed"
    assert message.last_error_code is None
    assert message.processed_at is not None
    assert event.status == "processed"
    assert event.processed_at is not None
    assert streams.pending_count(STREAM_NAME, GROUP_NAME) == 0
    assert uow.commits == 1
    assert [audit.event_type for audit in uow.audit_events] == [
        "telegram.message_processed"
    ]
    assert uow.audit_events[0].after_state["message_id"] == str(message.id)
    assert uow.audit_events[0].after_state["processing_status"] == "processed"


def test_worker_rerun_is_idempotent() -> None:
    message = _message()
    event = _event(message)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])
    streams = _stream_with_event(event, message)
    worker = _worker(
        streams,
        handlers={
            "telegram.message_received": (
                lambda fields: handle_telegram_message_received(fields, uow)
            )
        },
    )

    first = worker.run_once()
    second = worker.run_once()

    assert first.processed == 1
    assert second.processed == 0
    assert second.retried == 0
    assert second.dead_lettered == 0
    assert message.processing_status == "processed"
    assert event.status == "processed"
    assert [audit.event_type for audit in uow.audit_events] == [
        "telegram.message_processed"
    ]


def test_worker_continuous_loop_can_be_bounded_for_staging_smoke() -> None:
    message = _message()
    event = _event(message)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])
    streams = _stream_with_event(event, message)
    worker = _worker(
        streams,
        handlers={
            "telegram.message_received": (
                lambda fields: handle_telegram_message_received(fields, uow)
            )
        },
    )

    result = worker.run_continuously(max_iterations=2, poll_interval_seconds=0)

    assert result.processed == 1
    assert message.processing_status == "processed"
    assert streams.pending_count(STREAM_NAME, GROUP_NAME) == 0


def test_worker_retryable_failure_moves_event_back_to_retry() -> None:
    message = _message()
    event = _event(message, max_attempts=2)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])
    streams = _stream_with_event(event, message)
    worker = _worker(
        streams,
        handlers={
            "telegram.message_received": (
                lambda _fields: (_ for _ in ()).throw(
                    RetryableStage03WorkerError("temporary_worker_error")
                )
            )
        },
        uow=uow,
    )

    result = worker.run_once()

    assert result.processed == 0
    assert result.retried == 1
    assert result.dead_lettered == 0
    assert event.status == "retry"
    assert event.attempts == 1
    assert event.attempt_count == 1
    assert event.last_error == "temporary_worker_error"
    assert message.processing_status == "retrying"
    assert message.outbox_status == "retry"
    assert message.last_error_code == "temporary_worker_error"
    assert streams.pending_count(STREAM_NAME, GROUP_NAME) == 0
    assert uow.audit_events[0].event_type == "telegram.message_processing_retry"


def test_worker_failure_becomes_dead_letter() -> None:
    message = _message()
    event = _event(message, max_attempts=1)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])
    streams = _stream_with_event(event, message)
    worker = _worker(
        streams,
        handlers={
            "telegram.message_received": (
                lambda _fields: (_ for _ in ()).throw(
                    RetryableStage03WorkerError("temporary_worker_error")
                )
            )
        },
        uow=uow,
    )

    result = worker.run_once()

    assert result.processed == 0
    assert result.retried == 0
    assert result.dead_lettered == 1
    assert event.status == "dead_letter"
    assert event.attempts == 1
    assert event.attempt_count == 1
    assert event.last_error == "temporary_worker_error"
    assert message.processing_status == "dead_letter"
    assert message.outbox_status == "dead_letter"
    assert message.last_error_code == "temporary_worker_error"
    assert streams.pending_count(STREAM_NAME, GROUP_NAME) == 0
    assert uow.audit_events[0].event_type == "telegram.message_dead_letter"

    view_source = InMemoryBitableViewDataSource()
    view_source.add_record(
        "messages",
        record_id=str(message.id),
        fields=_view_fields(message),
    )
    inbox = get_view_records("telegram_inbox", data_source=view_source)

    assert inbox.records[0].fields["processing_status"] == "dead_letter"
    assert inbox.records[0].fields["outbox_status"] == "dead_letter"
    assert inbox.records[0].fields["last_error_code"] == "temporary_worker_error"


def _worker(
    streams: InMemoryRedisStreams,
    *,
    handlers: dict[str, object],
    uow: InMemoryStage03WorkerUnitOfWork | None = None,
) -> RedisStreamsWorker:
    return RedisStreamsWorker(
        streams=streams,
        stream_name=STREAM_NAME,
        group_name=GROUP_NAME,
        consumer_name="test-worker-1",
        handlers=handlers,
        failure_uow=uow,
    )


def _stream_with_event(
    event: OutboxEvent,
    message: IngestedMessage,
) -> InMemoryRedisStreams:
    streams = InMemoryRedisStreams()
    streams.xadd_once(
        STREAM_NAME,
        idempotency_key=event.idempotency_key,
        fields={
            "event_id": str(event.id),
            "event_type": event.event_type,
            "trace_id": event.trace_id,
            "idempotency_key": event.idempotency_key,
            "message_id": str(message.id),
            "created_at": "2026-07-06T10:00:00+00:00",
        },
    )
    return streams


def _message() -> IngestedMessage:
    message = IngestedMessage(
        id=uuid4(),
        telegram_update_id="update-1",
        telegram_chat_id="chat-1",
        telegram_message_id="telegram-message-1",
        telegram_user_id="user-1",
        customer_group_id=None,
        customer_id="customer-1",
        raw_text="hello",
        raw_caption=None,
        normalized_text="hello",
        message_type="text",
        intent_status="unclassified",
        intent_type=None,
        ingestion_status="stored",
        trace_id="tg:update-1",
        binding_status="bound",
        processing_status="queued",
        outbox_status="enqueued",
    )
    message.received_at = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)
    return message


def _event(message: IngestedMessage, *, max_attempts: int = 3) -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        event_type="telegram.message_received",
        payload={"message_id": str(message.id), "telegram_update_id": "update-1"},
        status="enqueued",
        attempts=0,
        attempt_count=0,
        max_attempts=max_attempts,
        idempotency_key=f"telegram.message_received:{message.id}",
        trace_id="tg:update-1",
        created_at=datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
    )


def _view_fields(message: IngestedMessage) -> dict[str, object]:
    return {
        "telegram_update_id": message.telegram_update_id,
        "telegram_chat_id": message.telegram_chat_id,
        "telegram_user_id": message.telegram_user_id,
        "customer_id": message.customer_id,
        "binding_status": message.binding_status,
        "message_type": message.message_type,
        "normalized_text": message.normalized_text,
        "processing_status": message.processing_status,
        "outbox_status": message.outbox_status,
        "last_error_code": message.last_error_code,
        "received_at": message.received_at.isoformat(),
        "processed_at": None,
    }
