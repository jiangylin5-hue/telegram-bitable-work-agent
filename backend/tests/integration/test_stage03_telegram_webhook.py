from fastapi.testclient import TestClient

from app.api.routes.telegram_webhook import get_telegram_webhook_ingestion_uow
from app.main import create_app
from app.services.telegram_ingestion import InMemoryTelegramIngestionUnitOfWork


RUNTIME_ENV_VARS = [
    "APP_ENV",
    "DATABASE_URL",
    "REDIS_URL",
    "TELEGRAM_WEBHOOK_SECRET",
    "TELEGRAM_ALLOWED_CHAT_IDS",
    "TELEGRAM_ALLOWED_USER_IDS",
    "TELEGRAM_SEND_MODE",
    "LLM_ENABLED",
    "PROVIDER_MODE",
]


def _clear_runtime_env(monkeypatch) -> None:
    for name in RUNTIME_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _make_app(monkeypatch, uow: InMemoryTelegramIngestionUnitOfWork):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "stage-secret")
    app = create_app()
    app.dependency_overrides[get_telegram_webhook_ingestion_uow] = lambda: uow
    return app


def _telegram_payload(update_id: int = 123456789, chat_id: str = "chat-1"):
    return {
        "update_id": update_id,
        "message": {
            "message_id": 77,
            "date": 1783276800,
            "chat": {"id": chat_id, "type": "group"},
            "from": {"id": "user-1", "is_bot": False, "username": "alice"},
            "text": "  hello   stage03  ",
        },
    }


def test_receive_only_webhook_accepts_valid_update_and_enqueues_message_event(
    monkeypatch,
) -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    uow.bind_customer_group(
        telegram_chat_id="chat-1",
        customer_group_id="group-1",
        customer_id="customer-1",
    )
    app = _make_app(monkeypatch, uow)

    with TestClient(app) as client:
        response = client.post(
            "/telegram/webhook",
            json=_telegram_payload(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "stage-secret"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["duplicate"] is False
    assert len(uow.messages) == 1
    assert uow.messages[0].telegram_update_id == "123456789"
    assert uow.messages[0].telegram_chat_id == "chat-1"
    assert uow.messages[0].telegram_message_id == "77"
    assert uow.messages[0].normalized_text == "hello stage03"
    assert len(uow.outbox_events) == 1
    assert uow.outbox_events[0].event_type == "telegram.message_received"
    assert uow.outbox_events[0].event_type != "agent.intent_extract"
    assert uow.outbox_events[0].idempotency_key.startswith("telegram.message_received:")
    assert uow.audit_events[0].event_type == "message_ingested"


def test_receive_only_webhook_duplicate_update_is_idempotent(monkeypatch) -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    app = _make_app(monkeypatch, uow)

    with TestClient(app) as client:
        first = client.post(
            "/telegram/webhook",
            json=_telegram_payload(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "stage-secret"},
        )
        second = client.post(
            "/telegram/webhook",
            json=_telegram_payload(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "stage-secret"},
        )

    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    assert second.status_code == 200
    assert second.json()["status"] == "accepted"
    assert second.json()["duplicate"] is True
    assert len(uow.messages) == 1
    assert len(uow.outbox_events) == 1


def test_receive_only_webhook_rejects_invalid_secret_without_business_rows(
    monkeypatch,
) -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    app = _make_app(monkeypatch, uow)

    with TestClient(app) as client:
        response = client.post(
            "/telegram/webhook",
            json=_telegram_payload(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "telegram_webhook_forbidden"
    assert "stage-secret" not in str(body)
    assert "wrong-secret" not in str(body)
    assert len(uow.messages) == 0
    assert len(uow.outbox_events) == 0


def test_receive_only_webhook_rejects_malformed_update_without_raw_leak(
    monkeypatch,
) -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    app = _make_app(monkeypatch, uow)

    with TestClient(app) as client:
        response = client.post(
            "/telegram/webhook",
            json={"update_id": 1, "secret_like": "do-not-echo", "message": {}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "stage-secret"},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "telegram_update_invalid"
    assert "do-not-echo" not in str(body)
    assert len(uow.messages) == 0
    assert len(uow.outbox_events) == 0


def test_receive_only_webhook_allowlist_blocks_untrusted_chat(monkeypatch) -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "stage-secret")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "allowed-chat")
    app = create_app()
    app.dependency_overrides[get_telegram_webhook_ingestion_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.post(
            "/telegram/webhook",
            json=_telegram_payload(chat_id="blocked-chat"),
            headers={"X-Telegram-Bot-Api-Secret-Token": "stage-secret"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "telegram_source_not_allowed"
    assert len(uow.messages) == 0
    assert len(uow.outbox_events) == 0
