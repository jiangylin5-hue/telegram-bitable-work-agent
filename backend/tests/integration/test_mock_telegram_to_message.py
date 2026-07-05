from fastapi.testclient import TestClient

from app.api.routes.mock_telegram import get_telegram_ingestion_uow
from app.main import create_app
from app.services.service_drafts import InMemoryServiceDraftUnitOfWork
from app.services.telegram_ingestion import InMemoryTelegramIngestionUnitOfWork
from app.workers.handlers import handle_agent_intent_extract


def test_mock_telegram_update_api_is_idempotent() -> None:
    app = create_app()
    uow = InMemoryTelegramIngestionUnitOfWork()
    uow.bind_customer_group(
        telegram_chat_id="chat-1",
        customer_group_id="group-1",
        customer_id="customer-1",
    )
    app.dependency_overrides[get_telegram_ingestion_uow] = lambda: uow

    payload = {
        "update_id": "update-1",
        "chat_id": "chat-1",
        "message_id": "message-1",
        "sender_user_id": "sender-1",
        "username": "customer_user",
        "text": "给账户 act_1001 充值 1000 USD",
    }

    with TestClient(app) as client:
        first_response = client.post("/mock/telegram/updates", json=payload)
        second_response = client.post("/mock/telegram/updates", json=payload)

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "stored"
    assert second_response.status_code == 200
    assert second_response.json()["status"] == "duplicate"
    assert len(uow.messages) == 1
    assert len(uow.outbox_events) == 1


def test_mock_telegram_recharge_message_reaches_draft_queue() -> None:
    app = create_app()
    ingestion_uow = InMemoryTelegramIngestionUnitOfWork()
    ingestion_uow.bind_customer_group(
        telegram_chat_id="chat-1",
        customer_group_id="group-1",
        customer_id="customer-1",
    )
    app.dependency_overrides[get_telegram_ingestion_uow] = lambda: ingestion_uow

    with TestClient(app) as client:
        response = client.post(
            "/mock/telegram/updates",
            json={
                "update_id": "update-1",
                "chat_id": "chat-1",
                "message_id": "message-1",
                "sender_user_id": "sender-1",
                "username": "customer_user",
                "text": "给账户 act_1001 充值 1000 USD",
            },
        )

    draft_uow = InMemoryServiceDraftUnitOfWork(messages=ingestion_uow.messages)
    handle_agent_intent_extract(ingestion_uow.outbox_events[0], draft_uow)

    assert response.status_code == 200
    assert ingestion_uow.messages[0].intent_type == "recharge"
    assert draft_uow.service_drafts[0].draft_type == "recharge"
    assert draft_uow.service_drafts[0].status == "pending_confirmation"
    assert draft_uow.audit_events[0].event_type == "draft_created"
