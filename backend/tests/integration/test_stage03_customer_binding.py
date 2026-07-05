from app.schemas.telegram import MockTelegramUpdate
from app.services.customer_binding import TelegramCustomerBindingRecord
from app.services.telegram_ingestion import (
    InMemoryTelegramIngestionUnitOfWork,
    ingest_mock_telegram_update,
)


def test_bound_chat_resolves_customer() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    uow.add_customer_binding(
        TelegramCustomerBindingRecord(
            customer_id="customer-1",
            telegram_chat_id="chat-1",
            telegram_user_id=None,
            binding_scope="chat",
            status="active",
        )
    )

    ingest_mock_telegram_update(_update(chat_id="chat-1", sender_user_id="user-1"), uow)

    assert len(uow.messages) == 1
    assert uow.messages[0].customer_id == "customer-1"
    assert uow.messages[0].binding_status == "bound"
    assert uow.messages[0].intent_status == "unclassified"
    assert uow.audit_events[0].after_state["binding_status"] == "bound"
    assert uow.audit_events[1].event_type == "telegram.binding.resolved"
    assert uow.audit_events[1].after_state["customer_id"] == "customer-1"


def test_chat_user_binding_takes_precedence_over_chat_binding() -> None:
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

    ingest_mock_telegram_update(_update(chat_id="chat-1", sender_user_id="user-1"), uow)

    assert uow.messages[0].customer_id == "customer-exact"
    assert uow.messages[0].binding_status == "bound"


def test_unbound_chat_enters_manual_binding_state() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()

    ingest_mock_telegram_update(_update(chat_id="unknown-chat", sender_user_id="user-1"), uow)

    assert len(uow.messages) == 1
    assert uow.messages[0].customer_id is None
    assert uow.messages[0].binding_status == "needs_manual_binding"
    assert uow.messages[0].intent_status == "needs_review"
    assert uow.audit_events[0].after_state["binding_status"] == "needs_manual_binding"
    assert uow.audit_events[1].event_type == "telegram.binding.unbound"


def test_inactive_binding_is_ignored() -> None:
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

    ingest_mock_telegram_update(_update(chat_id="chat-1", sender_user_id="user-1"), uow)

    assert uow.messages[0].customer_id is None
    assert uow.messages[0].binding_status == "needs_manual_binding"


def test_conflicting_binding_enters_manual_review_without_customer_guess() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    for customer_id in ("customer-a", "customer-b"):
        uow.add_customer_binding(
            TelegramCustomerBindingRecord(
                customer_id=customer_id,
                telegram_chat_id="chat-1",
                telegram_user_id=None,
                binding_scope="chat",
                status="active",
            )
        )

    ingest_mock_telegram_update(_update(chat_id="chat-1", sender_user_id="user-1"), uow)

    assert uow.messages[0].customer_id is None
    assert uow.messages[0].binding_status == "binding_conflict"
    assert uow.messages[0].intent_status == "needs_review"
    assert uow.audit_events[0].after_state["binding_status"] == "binding_conflict"
    assert uow.audit_events[1].event_type == "telegram.binding.conflict"


def _update(*, chat_id: str, sender_user_id: str) -> MockTelegramUpdate:
    return MockTelegramUpdate(
        update_id=f"update:{chat_id}:{sender_user_id}",
        chat_id=chat_id,
        message_id=f"message:{chat_id}:{sender_user_id}",
        sender_user_id=sender_user_id,
        username="customer_user",
        text="hello stage03",
    )
