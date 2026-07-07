from datetime import datetime, timezone
from uuid import uuid4

from app.models.outbox import OutboxEvent
from app.services.telegram_ingestion import IngestedMessage
from app.workers.stage03_handlers import (
    InMemoryStage03WorkerUnitOfWork,
    handle_telegram_message_received,
)


def test_bound_message_becomes_intent_ready_without_service_draft() -> None:
    message = _message(binding_status="bound", intent_status="unclassified")
    event = _event(message)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])

    handle_telegram_message_received(
        {"event_id": str(event.id), "message_id": str(message.id)},
        uow,
    )

    assert message.processing_status == "processed"
    assert message.intent_status == "intent_ready"
    assert message.intent_type is None
    assert [audit.event_type for audit in uow.audit_events] == [
        "telegram.intent_placeholder.ready",
        "telegram.message_processed",
    ]
    assert all(audit.entity_type != "service_draft" for audit in uow.audit_events)


def test_unbound_message_does_not_become_intent_ready() -> None:
    message = _message(
        binding_status="needs_manual_binding",
        intent_status="needs_review",
    )
    event = _event(message)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])

    handle_telegram_message_received(
        {"event_id": str(event.id), "message_id": str(message.id)},
        uow,
    )

    assert message.processing_status == "processed"
    assert message.intent_status == "needs_review"
    assert [audit.event_type for audit in uow.audit_events] == [
        "telegram.message_processed"
    ]


def _message(*, binding_status: str, intent_status: str) -> IngestedMessage:
    message = IngestedMessage(
        id=uuid4(),
        telegram_update_id="update-1",
        telegram_chat_id="chat-1",
        telegram_message_id="telegram-message-1",
        telegram_user_id="user-1",
        customer_group_id=None,
        customer_id="customer-1" if binding_status == "bound" else None,
        raw_text="stage04 intent placeholder",
        raw_caption=None,
        normalized_text="stage04 intent placeholder",
        message_type="text",
        intent_status=intent_status,
        intent_type=None,
        ingestion_status="stored",
        trace_id="tg:update-1",
        binding_status=binding_status,
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
