from app.schemas.telegram import MockTelegramUpdate
from app.services.telegram_ingestion import (
    InMemoryTelegramIngestionUnitOfWork,
    ingest_mock_telegram_update,
)


def make_update() -> MockTelegramUpdate:
    return MockTelegramUpdate(
        update_id="update-1",
        chat_id="chat-1",
        message_id="message-1",
        sender_user_id="sender-1",
        username="customer_user",
        text="给账户 act_1001 充值 1000 USD",
    )


def test_ingest_known_group_message_creates_message_and_outbox_event() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    uow.bind_customer_group(
        telegram_chat_id="chat-1",
        customer_group_id="group-1",
        customer_id="customer-1",
    )

    result = ingest_mock_telegram_update(make_update(), uow)

    assert result.status == "stored"
    assert len(uow.messages) == 1
    assert uow.messages[0].customer_id == "customer-1"
    assert uow.messages[0].intent_status == "unclassified"
    assert len(uow.outbox_events) == 1
    assert uow.outbox_events[0].event_type == "agent.intent_extract"
    assert uow.outbox_events[0].idempotency_key == f"intent:{uow.messages[0].id}"
    assert uow.audit_events[0].event_type == "message_ingested"
    assert uow.audit_events[0].entity_type == "message"
    assert uow.audit_events[0].after_state["intent_status"] == "unclassified"


def test_duplicate_update_is_idempotent() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()

    first = ingest_mock_telegram_update(make_update(), uow)
    second = ingest_mock_telegram_update(make_update(), uow)

    assert first.status == "stored"
    assert second.status == "duplicate"
    assert len(uow.messages) == 1
    assert len(uow.outbox_events) == 1
