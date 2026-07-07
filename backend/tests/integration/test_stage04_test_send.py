from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_system_actor
from app.api.routes.telegram_send_requests import (
    get_telegram_send_request_uow,
    get_telegram_send_settings,
)
from app.core.config import Settings
from app.main import create_app
from app.models.outbox import OutboxEvent
from app.models.telegram import TelegramSendRequest
from app.services.permissions import Actor
from app.services.telegram_send_requests import InMemoryTelegramSendRequestUnitOfWork
from app.workers.stage03_handlers import (
    InMemoryStage03WorkerUnitOfWork,
    handle_telegram_test_send_requested,
)


def test_send_request_api_creates_pending_confirmation_without_outbox() -> None:
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork()
    _override_send_dependencies(app, uow, allowed_chat_ids=("test-chat",))

    with TestClient(app) as client:
        response = client.post(
            "/telegram/send-requests",
            json={
                "target_chat_id": "test-chat",
                "message_text": "Stage04 test send smoke",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_confirmation"
    assert body["request_id"]
    assert body["trace_id"].startswith("tg-send:")
    assert uow.send_requests[0].status == "pending_confirmation"
    assert uow.outbox_events == []
    assert uow.audit_events[0].event_type == "telegram.test_send.requested"
    assert uow.committed is True


def test_send_request_confirm_queues_outbox_event() -> None:
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork()
    _override_send_dependencies(app, uow, allowed_chat_ids=("test-chat",))

    with TestClient(app) as client:
        create_response = client.post(
            "/telegram/send-requests",
            json={
                "target_chat_id": "test-chat",
                "message_text": "Stage04 test send smoke",
            },
        )
        request_id = create_response.json()["request_id"]
        confirm_response = client.post(
            f"/telegram/send-requests/{request_id}/confirm",
            json={"confirm": True},
        )

    assert confirm_response.status_code == 200
    assert confirm_response.json() == {
        "status": "confirmed",
        "request_id": request_id,
        "queued": True,
    }
    assert uow.send_requests[0].status == "confirmed"
    assert uow.outbox_events[0].event_type == "telegram.test_send_requested"
    assert uow.outbox_events[0].payload == {"request_id": request_id}
    assert uow.outbox_events[0].idempotency_key == (
        f"telegram.test_send_requested:{request_id}"
    )
    assert uow.audit_events[-1].event_type == "telegram.test_send.confirmed"


def test_send_request_non_allowlisted_target_is_blocked() -> None:
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork()
    _override_send_dependencies(app, uow, allowed_chat_ids=("test-chat",))

    with TestClient(app) as client:
        response = client.post(
            "/telegram/send-requests",
            json={
                "target_chat_id": "customer-chat",
                "message_text": "Stage04 test send smoke",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["error_code"] == "telegram_test_send_target_not_allowlisted"
    assert uow.send_requests[0].status == "blocked"
    assert uow.send_requests[0].last_error_code == (
        "telegram_test_send_target_not_allowlisted"
    )
    assert uow.outbox_events == []


def test_send_request_rejects_message_text_over_stage04_limit() -> None:
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork()
    _override_send_dependencies(app, uow, allowed_chat_ids=("test-chat",))

    with TestClient(app) as client:
        response = client.post(
            "/telegram/send-requests",
            json={
                "target_chat_id": "test-chat",
                "message_text": "x" * 1001,
            },
        )

    assert response.status_code == 422
    assert uow.send_requests == []
    assert uow.outbox_events == []
    assert uow.audit_events == []


def test_send_request_sales_create_is_forbidden_and_audited() -> None:
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork()
    _override_send_dependencies(
        app,
        uow,
        allowed_chat_ids=("test-chat",),
        actor=Actor(actor_type="user", actor_id="sales-1", role="sales"),
    )

    with TestClient(app) as client:
        response = client.post(
            "/telegram/send-requests",
            json={
                "target_chat_id": "test-chat",
                "message_text": "Stage04 test send smoke",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "sales cannot perform request_test_telegram_send"
    )
    assert uow.send_requests == []
    assert uow.outbox_events == []
    assert uow.audit_events[0].event_type == "permission_denied"
    assert uow.audit_events[0].permission_snapshot["action"] == (
        "request_test_telegram_send"
    )
    assert uow.committed is True


def test_send_request_confirm_rejects_invalid_state() -> None:
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork()
    _override_send_dependencies(app, uow, allowed_chat_ids=("test-chat",))

    with TestClient(app) as client:
        create_response = client.post(
            "/telegram/send-requests",
            json={
                "target_chat_id": "test-chat",
                "message_text": "Stage04 test send smoke",
            },
        )
        request_id = create_response.json()["request_id"]
        first_confirm = client.post(
            f"/telegram/send-requests/{request_id}/confirm",
            json={"confirm": True},
        )
        second_confirm = client.post(
            f"/telegram/send-requests/{request_id}/confirm",
            json={"confirm": True},
        )

    assert first_confirm.status_code == 200
    assert second_confirm.status_code == 409
    assert second_confirm.json()["error"]["code"] == "telegram_send_request_invalid_state"
    assert len(uow.outbox_events) == 1


def test_send_request_confirm_false_is_rejected_without_side_effects() -> None:
    send_request = _send_request(
        status="pending_confirmation",
        target_chat_id="test-chat",
    )
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork(send_requests=[send_request])
    _override_send_dependencies(app, uow, allowed_chat_ids=("test-chat",))

    with TestClient(app) as client:
        response = client.post(
            f"/telegram/send-requests/{send_request.id}/confirm",
            json={"confirm": False},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "confirm must be true"
    assert send_request.status == "pending_confirmation"
    assert uow.outbox_events == []
    assert uow.audit_events == []
    assert uow.committed is False


def test_send_request_confirm_blocks_when_allowlist_changes() -> None:
    send_request = _send_request(
        status="pending_confirmation",
        target_chat_id="test-chat",
    )
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork(send_requests=[send_request])
    _override_send_dependencies(app, uow, allowed_chat_ids=("other-test-chat",))

    with TestClient(app) as client:
        response = client.post(
            f"/telegram/send-requests/{send_request.id}/confirm",
            json={"confirm": True},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == (
        "telegram_test_send_target_not_allowlisted"
    )
    assert send_request.status == "blocked"
    assert send_request.last_error_code == "telegram_test_send_target_not_allowlisted"
    assert uow.outbox_events == []
    assert uow.audit_events[0].event_type == "telegram.test_send.blocked"
    assert uow.committed is True


def test_send_request_sales_confirm_is_forbidden_and_audited() -> None:
    send_request = _send_request(status="pending_confirmation", target_chat_id="test-chat")
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork(send_requests=[send_request])
    _override_send_dependencies(
        app,
        uow,
        allowed_chat_ids=("test-chat",),
        actor=Actor(actor_type="user", actor_id="sales-1", role="sales"),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/telegram/send-requests/{send_request.id}/confirm",
            json={"confirm": True},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "sales cannot perform confirm_test_telegram_send"
    )
    assert send_request.status == "pending_confirmation"
    assert uow.outbox_events == []
    assert uow.audit_events[0].event_type == "permission_denied"
    assert uow.audit_events[0].permission_snapshot["action"] == (
        "confirm_test_telegram_send"
    )
    assert uow.committed is True


def test_send_request_confirm_missing_request_returns_stable_error() -> None:
    app = create_app()
    uow = InMemoryTelegramSendRequestUnitOfWork()
    _override_send_dependencies(app, uow, allowed_chat_ids=("test-chat",))

    with TestClient(app) as client:
        response = client.post(
            f"/telegram/send-requests/{uuid4()}/confirm",
            json={"confirm": True},
        )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "telegram_send_request_not_found",
            "message": "Telegram send request not found",
        }
    }
    assert uow.outbox_events == []


def test_send_worker_sends_allowlisted_confirmed_request_once() -> None:
    send_request = _send_request(status="confirmed", target_chat_id="test-chat")
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
        allowed_chat_ids=("test-chat",),
    )
    handle_telegram_test_send_requested(
        {"event_id": str(event.id), "request_id": str(send_request.id)},
        uow,
        bot_client=bot_client,
        allowed_chat_ids=("test-chat",),
    )

    assert bot_client.calls == [
        {"chat_id": "test-chat", "text": "Stage04 test send smoke"}
    ]
    assert send_request.status == "sent"
    assert send_request.sent_at is not None
    assert send_request.telegram_response_summary == {
        "ok": True,
        "telegram_message_id": 42,
    }
    assert event.status == "processed"
    assert [audit.event_type for audit in uow.audit_events] == [
        "telegram.test_send.sent"
    ]


def test_send_worker_rechecks_allowlist_before_sending() -> None:
    send_request = _send_request(status="confirmed", target_chat_id="customer-chat")
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
        allowed_chat_ids=("test-chat",),
    )

    assert bot_client.calls == []
    assert send_request.status == "blocked"
    assert send_request.last_error_code == "telegram_test_send_target_not_allowlisted"
    assert event.status == "dead_letter"
    assert uow.audit_events[0].event_type == "telegram.test_send.blocked"


def test_send_worker_records_failed_telegram_response() -> None:
    send_request = _send_request(status="confirmed", target_chat_id="test-chat")
    event = _send_event(send_request)
    bot_client = FakeTelegramBotClient(ok=False)
    uow = InMemoryStage03WorkerUnitOfWork(
        send_requests=[send_request],
        outbox_events=[event],
    )

    handle_telegram_test_send_requested(
        {"event_id": str(event.id), "request_id": str(send_request.id)},
        uow,
        bot_client=bot_client,
        allowed_chat_ids=("test-chat",),
    )

    assert bot_client.calls == [
        {"chat_id": "test-chat", "text": "Stage04 test send smoke"}
    ]
    assert send_request.status == "failed"
    assert send_request.sent_at is None
    assert send_request.last_error_code == "500"
    assert send_request.telegram_response_summary == {"ok": False, "error_code": 500}
    assert event.status == "dead_letter"
    assert event.last_error_redacted == "500"
    assert [audit.event_type for audit in uow.audit_events] == [
        "telegram.test_send.failed"
    ]


def _override_send_dependencies(
    app,
    uow: InMemoryTelegramSendRequestUnitOfWork,
    *,
    allowed_chat_ids: tuple[str, ...],
    actor: Actor | None = None,
) -> None:
    app.dependency_overrides[get_telegram_send_request_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor or Actor(
        actor_type="user",
        actor_id=f"manager-{uuid4()}",
        role="manager",
    )
    app.dependency_overrides[get_telegram_send_settings] = lambda: Settings(
        telegram_send_mode="restricted_test",
        telegram_bot_token="123456:stage04-token",
        telegram_test_send_allowed_chat_ids=allowed_chat_ids,
    )


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


def _send_request(*, status: str, target_chat_id: str) -> TelegramSendRequest:
    now = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)
    return TelegramSendRequest(
        id=uuid4(),
        target_chat_id=target_chat_id,
        message_text="Stage04 test send smoke",
        status=status,
        requested_by_actor_type="user",
        requested_by_actor_id="manager-1",
        confirmed_by_actor_type="user",
        confirmed_by_actor_id="manager-2",
        confirmed_at=now,
        trace_id="tg-send:test",
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
        created_at=datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
    )
