from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customers import CustomerGroup
from app.models.telegram import Message
from app.schemas.telegram import MockTelegramUpdate
from app.services.audit import record_audit_event
from app.services.outbox import enqueue_outbox_event


@dataclass
class BoundCustomerGroup:
    customer_group_id: Any
    customer_id: Any


@dataclass
class IngestedMessage:
    id: Any
    telegram_update_id: str
    telegram_chat_id: str
    telegram_message_id: str
    customer_group_id: Any | None
    customer_id: Any | None
    raw_text: str | None
    raw_caption: str | None
    normalized_text: str | None
    message_type: str
    intent_status: str
    intent_type: str | None
    ingestion_status: str
    trace_id: str


@dataclass(frozen=True)
class TelegramIngestionResult:
    status: str
    message_id: str
    trace_id: str


class TelegramIngestionUnitOfWork(Protocol):
    def get_message_by_update_id(self, update_id: str) -> IngestedMessage | None:
        pass

    def find_customer_group_by_chat_id(
        self,
        telegram_chat_id: str,
    ) -> BoundCustomerGroup | None:
        pass

    def add_message(self, message: IngestedMessage) -> None:
        pass

    def add_outbox_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        trace_id: str,
    ) -> None:
        pass

    def add(self, value: object) -> None:
        pass

    def commit(self) -> None:
        pass


class InMemoryTelegramIngestionUnitOfWork:
    def __init__(self) -> None:
        self.messages: list[IngestedMessage] = []
        self.outbox_events: list[Any] = []
        self.customer_groups: dict[str, BoundCustomerGroup] = {}
        self.audit_events: list[object] = []
        self.committed = False

    def bind_customer_group(
        self,
        *,
        telegram_chat_id: str,
        customer_group_id: Any,
        customer_id: Any,
    ) -> None:
        self.customer_groups[telegram_chat_id] = BoundCustomerGroup(
            customer_group_id=customer_group_id,
            customer_id=customer_id,
        )

    def get_message_by_update_id(self, update_id: str) -> IngestedMessage | None:
        return next(
            (
                message
                for message in self.messages
                if message.telegram_update_id == update_id
            ),
            None,
        )

    def find_customer_group_by_chat_id(
        self,
        telegram_chat_id: str,
    ) -> BoundCustomerGroup | None:
        return self.customer_groups.get(telegram_chat_id)

    def add_message(self, message: IngestedMessage) -> None:
        self.messages.append(message)

    def add_outbox_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        trace_id: str,
    ) -> None:
        class OutboxEventRecord:
            pass

        event = OutboxEventRecord()
        event.event_type = event_type
        event.payload = payload
        event.idempotency_key = idempotency_key
        event.trace_id = trace_id
        self.outbox_events.append(event)

    def add(self, value: object) -> None:
        self.audit_events.append(value)

    def commit(self) -> None:
        self.committed = True


class SqlAlchemyTelegramIngestionUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_message_by_update_id(self, update_id: str) -> IngestedMessage | None:
        message = self.session.scalar(
            select(Message).where(Message.telegram_update_id == update_id)
        )
        if message is None:
            return None
        return _to_ingested_message(message)

    def find_customer_group_by_chat_id(
        self,
        telegram_chat_id: str,
    ) -> BoundCustomerGroup | None:
        group = self.session.scalar(
            select(CustomerGroup).where(
                CustomerGroup.telegram_chat_id == telegram_chat_id,
                CustomerGroup.status == "active",
            )
        )
        if group is None:
            return None
        return BoundCustomerGroup(
            customer_group_id=group.id,
            customer_id=group.customer_id,
        )

    def add_message(self, message: IngestedMessage) -> None:
        self.session.add(
            Message(
                id=message.id,
                telegram_update_id=message.telegram_update_id,
                telegram_chat_id=message.telegram_chat_id,
                telegram_message_id=message.telegram_message_id,
                customer_group_id=message.customer_group_id,
                customer_id=message.customer_id,
                raw_text=message.raw_text,
                raw_caption=message.raw_caption,
                normalized_text=message.normalized_text,
                message_type=message.message_type,
                intent_status=message.intent_status,
                intent_type=message.intent_type,
                received_at=message_received_at(message),
                ingestion_status=message.ingestion_status,
                trace_id=message.trace_id,
            )
        )

    def add_outbox_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        trace_id: str,
    ) -> None:
        enqueue_outbox_event(
            self.session,
            event_type=event_type,
            payload=payload,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
        )

    def add(self, value: object) -> None:
        self.session.add(value)

    def commit(self) -> None:
        self.session.commit()


def ingest_mock_telegram_update(
    update: MockTelegramUpdate,
    uow: TelegramIngestionUnitOfWork,
    *,
    outbox_event_type: str = "agent.intent_extract",
) -> TelegramIngestionResult:
    existing_message = uow.get_message_by_update_id(update.update_id)
    trace_id = f"tg:{update.update_id}"
    if existing_message is not None:
        return TelegramIngestionResult(
            status="duplicate",
            message_id=str(existing_message.id),
            trace_id=existing_message.trace_id,
        )

    bound_group = uow.find_customer_group_by_chat_id(update.chat_id)
    message = IngestedMessage(
        id=uuid4(),
        telegram_update_id=update.update_id,
        telegram_chat_id=update.chat_id,
        telegram_message_id=update.message_id,
        customer_group_id=(
            None if bound_group is None else bound_group.customer_group_id
        ),
        customer_id=None if bound_group is None else bound_group.customer_id,
        raw_text=update.text,
        raw_caption=update.caption,
        normalized_text=normalize_message_text(update.text or update.caption),
        message_type=update.message_type,
        intent_status="needs_review" if bound_group is None else "unclassified",
        intent_type=None,
        ingestion_status="stored",
        trace_id=trace_id,
    )
    message.received_at = update.received_at

    uow.add_message(message)
    idempotency_prefix = (
        "intent" if outbox_event_type == "agent.intent_extract" else outbox_event_type
    )
    uow.add_outbox_event(
        event_type=outbox_event_type,
        payload={
            "message_id": str(message.id),
            "telegram_update_id": update.update_id,
            "customer_id": None if message.customer_id is None else str(message.customer_id),
        },
        idempotency_key=f"{idempotency_prefix}:{message.id}",
        trace_id=trace_id,
    )
    record_audit_event(
        uow,
        trace_id=trace_id,
        actor_type="telegram",
        actor_id=update.sender_user_id,
        event_type="message_ingested",
        entity_type="message",
        entity_id=message.id,
        after_state={
            "telegram_chat_id": update.chat_id,
            "telegram_message_id": update.message_id,
            "customer_id": None if message.customer_id is None else str(message.customer_id),
            "intent_status": message.intent_status,
            "ingestion_status": message.ingestion_status,
        },
    )
    return TelegramIngestionResult(
        status="stored",
        message_id=str(message.id),
        trace_id=trace_id,
    )


def normalize_message_text(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.strip().split())


def message_received_at(message: IngestedMessage):
    return getattr(message, "received_at")


def _to_ingested_message(message: Message) -> IngestedMessage:
    ingested = IngestedMessage(
        id=message.id,
        telegram_update_id=message.telegram_update_id,
        telegram_chat_id=message.telegram_chat_id,
        telegram_message_id=message.telegram_message_id,
        customer_group_id=message.customer_group_id,
        customer_id=message.customer_id,
        raw_text=message.raw_text,
        raw_caption=message.raw_caption,
        normalized_text=message.normalized_text,
        message_type=message.message_type,
        intent_status=message.intent_status,
        intent_type=message.intent_type,
        ingestion_status=message.ingestion_status,
        trace_id=message.trace_id,
    )
    ingested.received_at = message.received_at
    return ingested
