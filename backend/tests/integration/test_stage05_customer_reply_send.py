from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.models.outbox import OutboxEvent
from app.models.service_drafts import ServiceDraft
from app.models.telegram import Message, TelegramSendRequest
from app.services.confirmation import InMemoryConfirmationUnitOfWork, confirm_service_draft
from app.services.permissions import Actor
from app.services.telegram_send_requests import (
    InMemoryTelegramSendRequestUnitOfWork,
    TelegramTestSendTargetNotAllowlisted,
    confirm_test_send_request,
)
from app.workers.stage03_handlers import (
    InMemoryStage03WorkerUnitOfWork,
    handle_telegram_test_send_requested,
)


def test_customer_reply_draft_to_confirmed_send_request_to_fake_worker_send() -> None:
    message = _message(telegram_chat_id="stage05-test-chat")
    draft = _customer_reply_draft(
        source_message_id=message.id,
        reply_text="We are checking the account and will update you.",
    )
    confirmation_uow = InMemoryConfirmationUnitOfWork(
        service_drafts=[draft],
        messages=[message],
    )

    confirmation = confirm_service_draft(
        confirmation_uow,
        draft.id,
        _manager(),
        allowed_chat_ids=("stage05-test-chat",),
    )
    send_request = confirmation.telegram_send_request

    assert send_request is not None
    assert send_request.source_service_draft_id == draft.id
    assert send_request.send_purpose == "customer_reply_rehearsal"
    assert send_request.message_text_summary == {
        "length": 48,
        "preview": "We are checking the account and will update you.",
    }
    assert send_request.status == "pending_confirmation"

    send_uow = InMemoryTelegramSendRequestUnitOfWork(send_requests=[send_request])
    confirmed_request, outbox_event = confirm_test_send_request(
        send_uow,
        actor=_manager(),
        request_id=send_request.id,
        allowed_chat_ids=("stage05-test-chat",),
    )

    assert confirmed_request.status == "confirmed"
    assert outbox_event.event_type == "telegram.test_send_requested"
    assert outbox_event.payload == {"request_id": str(send_request.id)}
    assert send_uow.audit_events[-1].event_type == "customer_reply_send_confirmed"

    bot_client = FakeTelegramBotClient(ok=True)
    worker_uow = InMemoryStage03WorkerUnitOfWork(
        send_requests=[send_request],
        outbox_events=[outbox_event],
    )

    handle_telegram_test_send_requested(
        {"event_id": str(outbox_event.id), "request_id": str(send_request.id)},
        worker_uow,
        bot_client=bot_client,
        allowed_chat_ids=("stage05-test-chat",),
    )

    assert bot_client.calls == [
        {
            "chat_id": "stage05-test-chat",
            "text": "We are checking the account and will update you.",
        }
    ]
    assert send_request.status == "sent"
    assert send_request.sent_at is not None
    assert send_request.telegram_response_summary == {
        "ok": True,
        "telegram_message_id": 42,
    }
    assert outbox_event.status == "processed"
    assert worker_uow.audit_events[-1].event_type == "customer_reply_send_sent"


def test_customer_reply_send_confirm_blocks_allowlist_drift_without_outbox() -> None:
    draft_id = uuid4()
    send_request = _reply_send_request(
        source_service_draft_id=draft_id,
        target_chat_id="stage05-test-chat",
        status="pending_confirmation",
    )
    uow = InMemoryTelegramSendRequestUnitOfWork(send_requests=[send_request])

    with pytest.raises(TelegramTestSendTargetNotAllowlisted):
        confirm_test_send_request(
            uow,
            actor=_manager(),
            request_id=send_request.id,
            allowed_chat_ids=("other-test-chat",),
        )

    assert send_request.status == "blocked"
    assert send_request.source_service_draft_id == draft_id
    assert send_request.send_purpose == "customer_reply_rehearsal"
    assert uow.outbox_events == []
    assert uow.audit_events[-1].event_type == "customer_reply_send_failed"
    assert uow.audit_events[-1].after_state["error_code"] == (
        "telegram_test_send_target_not_allowlisted"
    )


def test_customer_reply_worker_rechecks_allowlist_before_send() -> None:
    send_request = _reply_send_request(
        source_service_draft_id=uuid4(),
        target_chat_id="real-customer-chat",
        status="confirmed",
    )
    event = _send_event(send_request)
    bot_client = FakeTelegramBotClient(ok=True)
    uow = InMemoryStage03WorkerUnitOfWork(
        send_requests=[send_request],
        outbox_events=[event],
    )

    handle_telegram_test_send_requested(
        {"event_id": str(event.id), "request_id": str(send_request.id)},
        uow,
        bot_client=bot_client,
        allowed_chat_ids=("stage05-test-chat",),
    )

    assert bot_client.calls == []
    assert send_request.status == "blocked"
    assert send_request.last_error_code == "telegram_test_send_target_not_allowlisted"
    assert event.status == "dead_letter"
    assert uow.audit_events[-1].event_type == "customer_reply_send_failed"


def test_reply_send_link_migration_extends_current_stage05_head() -> None:
    migration = Path(
        "alembic/versions/20260707_0016_stage05_reply_send_link.py"
    )

    text = migration.read_text(encoding="utf-8")

    assert 'down_revision = "20260707_0015"' in text
    assert "source_service_draft_id" in text
    assert "send_purpose" in text
    assert "message_text_summary" in text
    assert "fk_tg_send_req_source_draft" in text


def _customer_reply_draft(*, source_message_id, reply_text: str) -> ServiceDraft:
    return ServiceDraft(
        id=uuid4(),
        draft_type="customer_reply",
        status="pending_confirmation",
        customer_id=uuid4(),
        source_message_id=source_message_id,
        source_agent_run_id=uuid4(),
        created_by_type="agent",
        created_by_id="customer_reply_draft_agent",
        payload={"reply_text": reply_text},
        payload_summary={},
        missing_fields=[],
        risk_flags=[],
        confidence=Decimal("0.9200"),
        intent_index=0,
        trace_id="trace-stage05-customer-reply",
        idempotency_key=f"draft:{uuid4()}:customer_reply:0",
    )


def _message(*, telegram_chat_id: str) -> Message:
    now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
    return Message(
        id=uuid4(),
        telegram_update_id=f"update-{uuid4()}",
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=f"message-{uuid4()}",
        telegram_user_id="telegram-user-1",
        customer_id=uuid4(),
        raw_text="please reply to the customer",
        normalized_text="please reply to the customer",
        message_type="text",
        intent_status="routed",
        binding_status="bound",
        processing_status="agent_succeeded",
        outbox_status="processed",
        received_at=now,
        trace_id=f"trace-message-{telegram_chat_id}",
    )


def _reply_send_request(
    *,
    source_service_draft_id,
    target_chat_id: str,
    status: str,
) -> TelegramSendRequest:
    now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
    return TelegramSendRequest(
        id=uuid4(),
        target_chat_id=target_chat_id,
        message_text="Customer reply text",
        status=status,
        requested_by_actor_type="user",
        requested_by_actor_id="manager-1",
        source_service_draft_id=source_service_draft_id,
        send_purpose="customer_reply_rehearsal",
        message_text_summary={"length": 19, "preview": "Customer reply text"},
        trace_id=f"reply-send:{source_service_draft_id}",
        created_at=now,
        updated_at=now,
    )


def _send_event(send_request: TelegramSendRequest) -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        event_type="telegram.test_send_requested",
        aggregate_type="telegram_send_request",
        aggregate_id=str(send_request.id),
        payload={"request_id": str(send_request.id)},
        status="enqueued",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=f"telegram.test_send_requested:{send_request.id}",
        trace_id=send_request.trace_id,
        created_at=datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc),
    )


def _manager() -> Actor:
    return Actor(actor_type="user", actor_id=str(uuid4()), role="manager")


class FakeTelegramBotResult:
    def __init__(self, *, ok: bool) -> None:
        self.ok = ok
        self.response_summary = (
            {"ok": True, "telegram_message_id": 42}
            if ok
            else {"ok": False, "error_code": 500}
        )


class FakeTelegramBotClient:
    def __init__(self, *, ok: bool) -> None:
        self.ok = ok
        self.calls: list[dict[str, str]] = []

    def send_message(self, *, chat_id: str, text: str) -> FakeTelegramBotResult:
        self.calls.append({"chat_id": chat_id, "text": text})
        return FakeTelegramBotResult(ok=self.ok)
