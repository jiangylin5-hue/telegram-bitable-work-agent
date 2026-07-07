from datetime import datetime, timezone
from uuid import uuid4

from app.models.outbox import OutboxEvent
from app.services.telegram_ingestion import IngestedMessage
from app.workers.stage03_handlers import (
    InMemoryStage03WorkerUnitOfWork,
    handle_telegram_message_received,
)


def test_worker_delegates_bound_intent_ready_message_to_stage05_workflow() -> None:
    message = _message(binding_status="bound", intent_status="unclassified")
    event = _event(message)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])
    workflow = RecordingStage05Workflow(status_to_apply="routed")

    handle_telegram_message_received(
        {"event_id": str(event.id), "message_id": str(message.id)},
        uow,
        stage05_workflow=workflow,
    )

    assert workflow.calls == [
        {
            "message_id": str(message.id),
            "trace_id": event.trace_id,
            "intent_status": "intent_ready",
        }
    ]
    assert message.processing_status == "processed"
    assert message.intent_status == "routed"
    assert [audit.event_type for audit in uow.audit_events[:2]] == [
        "telegram.intent_placeholder.ready",
        "telegram.message_processed",
    ]


def test_worker_does_not_delegate_unbound_message_to_stage05_workflow() -> None:
    message = _message(
        binding_status="needs_manual_binding",
        intent_status="needs_review",
    )
    event = _event(message)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])
    workflow = RecordingStage05Workflow(status_to_apply="routed")

    handle_telegram_message_received(
        {"event_id": str(event.id), "message_id": str(message.id)},
        uow,
        stage05_workflow=workflow,
    )

    assert workflow.calls == []
    assert message.intent_status == "needs_review"
    assert [audit.event_type for audit in uow.audit_events] == [
        "telegram.message_processed"
    ]


def test_worker_without_stage05_workflow_preserves_stage04_placeholder_behavior() -> None:
    message = _message(binding_status="bound", intent_status="unclassified")
    event = _event(message)
    uow = InMemoryStage03WorkerUnitOfWork(messages=[message], outbox_events=[event])

    handle_telegram_message_received(
        {"event_id": str(event.id), "message_id": str(message.id)},
        uow,
    )

    assert message.intent_status == "intent_ready"
    assert [audit.event_type for audit in uow.audit_events] == [
        "telegram.intent_placeholder.ready",
        "telegram.message_processed",
    ]


class RecordingStage05Workflow:
    def __init__(self, *, status_to_apply: str) -> None:
        self.status_to_apply = status_to_apply
        self.calls: list[dict[str, str]] = []

    def run_for_message(self, *, message, trace_id: str, uow) -> None:
        self.calls.append(
            {
                "message_id": str(message.id),
                "trace_id": trace_id,
                "intent_status": message.intent_status,
            }
        )
        message.intent_status = self.status_to_apply
        uow.save_message(message)


def _message(*, binding_status: str, intent_status: str) -> IngestedMessage:
    message = IngestedMessage(
        id=uuid4(),
        telegram_update_id="update-stage05-worker",
        telegram_chat_id="chat-stage05-worker",
        telegram_message_id="telegram-message-stage05-worker",
        telegram_user_id="user-stage05-worker",
        customer_group_id=None,
        customer_id=uuid4() if binding_status == "bound" else None,
        raw_text="stage05 worker message",
        raw_caption=None,
        normalized_text="stage05 worker message",
        message_type="text",
        intent_status=intent_status,
        intent_type=None,
        ingestion_status="stored",
        trace_id="tg:update-stage05-worker",
        binding_status=binding_status,
        processing_status="queued",
        outbox_status="enqueued",
    )
    message.received_at = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
    return message


def _event(message: IngestedMessage) -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        event_type="telegram.message_received",
        payload={
            "message_id": str(message.id),
            "telegram_update_id": "update-stage05-worker",
        },
        status="enqueued",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=f"telegram.message_received:{message.id}",
        trace_id="tg:update-stage05-worker",
        created_at=datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc),
    )
