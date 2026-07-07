from app.schemas.telegram import MockTelegramUpdate
from app.services.customer_binding import TelegramCustomerBindingRecord
from app.services.telegram_ingestion import (
    InMemoryTelegramIngestionUnitOfWork,
    ingest_mock_telegram_update,
)


def test_stage04_chat_user_binding_takes_precedence_for_new_messages() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    uow.add_customer_binding(
        TelegramCustomerBindingRecord(
            customer_id="customer-chat",
            telegram_chat_id="chat-1",
            telegram_user_id=None,
            binding_scope="chat",
            status="active",
        )
    )
    uow.add_customer_binding(
        TelegramCustomerBindingRecord(
            customer_id="customer-exact",
            telegram_chat_id="chat-1",
            telegram_user_id="user-1",
            binding_scope="chat_user",
            status="active",
        )
    )

    ingest_mock_telegram_update(_update("update-1", chat_id="chat-1", user_id="user-1"), uow)

    assert uow.messages[0].customer_id == "customer-exact"
    assert uow.messages[0].binding_status == "bound"


def test_stage04_chat_binding_resolves_new_messages() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    uow.add_customer_binding(
        TelegramCustomerBindingRecord(
            customer_id="customer-chat",
            telegram_chat_id="chat-1",
            telegram_user_id=None,
            binding_scope="chat",
            status="active",
        )
    )

    ingest_mock_telegram_update(_update("update-1", chat_id="chat-1", user_id="user-2"), uow)

    assert uow.messages[0].customer_id == "customer-chat"
    assert uow.messages[0].binding_status == "bound"


def test_stage04_user_binding_resolves_new_messages() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    uow.add_customer_binding(
        TelegramCustomerBindingRecord(
            customer_id="customer-user",
            telegram_chat_id=None,
            telegram_user_id="user-1",
            binding_scope="user",
            status="active",
        )
    )

    ingest_mock_telegram_update(_update("update-1", chat_id="chat-2", user_id="user-1"), uow)

    assert uow.messages[0].customer_id == "customer-user"
    assert uow.messages[0].binding_status == "bound"


def test_stage04_inactive_binding_is_ignored_for_new_messages() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    uow.add_customer_binding(
        TelegramCustomerBindingRecord(
            customer_id="customer-inactive",
            telegram_chat_id="chat-1",
            telegram_user_id=None,
            binding_scope="chat",
            status="inactive",
        )
    )

    ingest_mock_telegram_update(_update("update-1", chat_id="chat-1", user_id="user-1"), uow)

    assert uow.messages[0].customer_id is None
    assert uow.messages[0].binding_status == "needs_manual_binding"


def test_stage04_new_binding_does_not_rewrite_historical_messages() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    ingest_mock_telegram_update(_update("update-old", chat_id="chat-1", user_id="user-1"), uow)

    uow.add_customer_binding(
        TelegramCustomerBindingRecord(
            customer_id="customer-new",
            telegram_chat_id="chat-1",
            telegram_user_id=None,
            binding_scope="chat",
            status="active",
        )
    )
    ingest_mock_telegram_update(_update("update-new", chat_id="chat-1", user_id="user-1"), uow)

    assert uow.messages[0].customer_id is None
    assert uow.messages[0].binding_status == "needs_manual_binding"
    assert uow.messages[1].customer_id == "customer-new"
    assert uow.messages[1].binding_status == "bound"


def _update(update_id: str, *, chat_id: str, user_id: str) -> MockTelegramUpdate:
    return MockTelegramUpdate(
        update_id=update_id,
        chat_id=chat_id,
        message_id=f"message:{update_id}",
        sender_user_id=user_id,
        username="stage04_user",
        text="stage04 binding regression",
    )
