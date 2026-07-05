from datetime import datetime, timezone
from uuid import uuid4

from app.models.outbox import OutboxEvent
from app.queues.redis_streams import InMemoryRedisStreams
from app.services.telegram_ingestion import IngestedMessage
from app.workers.stage03_handlers import InMemoryStage03WorkerUnitOfWork
from app.workers.stage03_runtime import (
    DEFAULT_STAGE03_GROUP_NAME,
    DEFAULT_STAGE03_STREAM_NAME,
    create_stage03_worker,
)


def test_stage03_worker_factory_wires_telegram_message_handler() -> None:
    message = _message()
    event = _event(message)
    streams = InMemoryRedisStreams()
    streams.xadd_once(
        DEFAULT_STAGE03_STREAM_NAME,
        idempotency_key=event.idempotency_key,
        fields={
            "event_id": str(event.id),
            "event_type": event.event_type,
            "trace_id": event.trace_id,
            "idempotency_key": event.idempotency_key,
            "message_id": str(message.id),
        },
    )
    uow = InMemoryStage03WorkerUnitOfWork(
        messages=[message],
        outbox_events=[event],
    )

    worker = create_stage03_worker(
        streams=streams,
        uow=uow,
        consumer_name="factory-test-worker",
    )
    result = worker.run_once()

    assert worker.stream_name == DEFAULT_STAGE03_STREAM_NAME
    assert worker.group_name == DEFAULT_STAGE03_GROUP_NAME
    assert result.processed == 1
    assert message.processing_status == "processed"
    assert event.status == "processed"


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


def _event(message: IngestedMessage) -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        event_type="telegram.message_received",
        payload={"message_id": str(message.id), "telegram_update_id": "update-1"},
        status="enqueued",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=f"telegram.message_received:{message.id}",
        trace_id="tg:update-1",
        created_at=datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
    )
