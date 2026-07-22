from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.customers import CustomerGroup
from app.models.stage06_platform import (
    BitableBase,
    PlatformRecord,
    PlatformTable,
    Stage06TelegramBinding,
)
from app.models.stage08_group_context import (
    Stage08GroupBusinessContextBinding,
    Stage08GroupMessageProjection,
)
from app.models.telegram import Message, TelegramCustomerBinding
from app.schemas.telegram import MockTelegramUpdate
from app.services.audit import record_audit_event
from app.services.customer_binding import (
    CustomerBindingResolution,
    TelegramCustomerBindingRecord,
    resolve_customer_binding,
)
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
    telegram_user_id: str | None = None
    binding_status: str = "needs_manual_binding"
    processing_status: str = "queued"
    outbox_status: str = "pending"
    last_error_code: str | None = None
    processed_at: Any | None = None


@dataclass(frozen=True)
class TelegramIngestionResult:
    status: str
    message_id: str
    trace_id: str


@dataclass(frozen=True)
class StoredMessageReceipt:
    id: Any
    trace_id: str


class TelegramIngestionPersistenceError(RuntimeError):
    pass


class TelegramIngestionUnitOfWork(Protocol):
    def get_message_by_update_id(self, update_id: str) -> IngestedMessage | None:
        pass

    def get_message_receipt_by_update_id(
        self,
        update_id: str,
    ) -> StoredMessageReceipt | None:
        pass

    def get_message_receipt_by_source_identity(
        self,
        *,
        telegram_chat_id: str,
        telegram_message_id: str,
    ) -> StoredMessageReceipt | None:
        pass

    def list_group_context_telegram_bindings(
        self,
        *,
        telegram_chat_id: str,
        telegram_user_id: str,
    ) -> list[Stage06TelegramBinding]:
        pass

    def list_group_business_context_bindings(
        self,
        telegram_binding_id: UUID,
    ) -> list[Stage08GroupBusinessContextBinding]:
        pass

    def group_context_records_match_workspace(
        self,
        binding: Stage08GroupBusinessContextBinding,
    ) -> bool:
        pass

    def list_group_message_projections_for_source(
        self,
        source_message_id: UUID,
    ) -> list[Stage08GroupMessageProjection]:
        pass

    def add_group_message_projection(
        self,
        projection: Stage08GroupMessageProjection,
    ) -> None:
        pass

    def find_customer_group_by_chat_id(
        self,
        telegram_chat_id: str,
    ) -> BoundCustomerGroup | None:
        pass

    def list_customer_bindings(
        self,
        *,
        telegram_chat_id: str,
        telegram_user_id: str | None,
    ) -> list[TelegramCustomerBindingRecord]:
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
        self.customer_bindings: list[TelegramCustomerBindingRecord] = []
        self.audit_events: list[object] = []
        self.group_context_telegram_bindings: list[Stage06TelegramBinding] = []
        self.group_business_context_bindings: list[
            Stage08GroupBusinessContextBinding
        ] = []
        self.group_context_record_workspaces: dict[UUID, UUID] = {}
        self.group_message_projections: list[Stage08GroupMessageProjection] = []
        self._message_receipts_by_update_id: dict[str, StoredMessageReceipt] = {}
        self._message_receipts_by_source_identity: dict[
            tuple[str, str], StoredMessageReceipt
        ] = {}
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

    def add_customer_binding(self, binding: TelegramCustomerBindingRecord) -> None:
        self.customer_bindings.append(binding)

    def get_message_by_update_id(self, update_id: str) -> IngestedMessage | None:
        return next(
            (
                message
                for message in self.messages
                if message.telegram_update_id == update_id
            ),
            None,
        )

    def get_message_receipt_by_update_id(
        self,
        update_id: str,
    ) -> StoredMessageReceipt | None:
        return self._message_receipts_by_update_id.get(update_id)

    def get_message_receipt_by_source_identity(
        self,
        *,
        telegram_chat_id: str,
        telegram_message_id: str,
    ) -> StoredMessageReceipt | None:
        return self._message_receipts_by_source_identity.get(
            (telegram_chat_id, telegram_message_id)
        )

    def list_group_context_telegram_bindings(
        self,
        *,
        telegram_chat_id: str,
        telegram_user_id: str,
    ) -> list[Stage06TelegramBinding]:
        return [
            binding
            for binding in self.group_context_telegram_bindings
            if binding.telegram_chat_id == telegram_chat_id
            and binding.telegram_user_id == telegram_user_id
        ]

    def list_group_business_context_bindings(
        self,
        telegram_binding_id: UUID,
    ) -> list[Stage08GroupBusinessContextBinding]:
        return [
            binding
            for binding in self.group_business_context_bindings
            if binding.telegram_binding_id == telegram_binding_id
        ]

    def group_context_records_match_workspace(
        self,
        binding: Stage08GroupBusinessContextBinding,
    ) -> bool:
        return (
            binding.customer_record_id != binding.project_record_id
            and self.group_context_record_workspaces.get(binding.customer_record_id)
            == binding.workspace_id
            and self.group_context_record_workspaces.get(binding.project_record_id)
            == binding.workspace_id
        )

    def list_group_message_projections_for_source(
        self,
        source_message_id: UUID,
    ) -> list[Stage08GroupMessageProjection]:
        return sorted(
            (
                projection
                for projection in self.group_message_projections
                if projection.source_message_id == source_message_id
            ),
            key=lambda projection: (projection.content_version, projection.id),
            reverse=True,
        )

    def add_group_message_projection(
        self,
        projection: Stage08GroupMessageProjection,
    ) -> None:
        self.group_message_projections.append(projection)

    def find_customer_group_by_chat_id(
        self,
        telegram_chat_id: str,
    ) -> BoundCustomerGroup | None:
        return self.customer_groups.get(telegram_chat_id)

    def list_customer_bindings(
        self,
        *,
        telegram_chat_id: str,
        telegram_user_id: str | None,
    ) -> list[TelegramCustomerBindingRecord]:
        return [
            binding
            for binding in self.customer_bindings
            if binding.telegram_chat_id == telegram_chat_id
            or (
                telegram_user_id is not None
                and binding.telegram_user_id == telegram_user_id
            )
        ]

    def add_message(self, message: IngestedMessage) -> None:
        self.messages.append(message)
        receipt = StoredMessageReceipt(id=message.id, trace_id=message.trace_id)
        self._message_receipts_by_update_id[message.telegram_update_id] = receipt
        self._message_receipts_by_source_identity[
            (message.telegram_chat_id, message.telegram_message_id)
        ] = receipt

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

    def get_message_receipt_by_update_id(
        self,
        update_id: str,
    ) -> StoredMessageReceipt | None:
        row = self.session.execute(
            select(Message.id, Message.trace_id).where(
                Message.telegram_update_id == update_id
            )
        ).one_or_none()
        if row is None:
            return None
        return StoredMessageReceipt(id=row.id, trace_id=row.trace_id)

    def get_message_receipt_by_source_identity(
        self,
        *,
        telegram_chat_id: str,
        telegram_message_id: str,
    ) -> StoredMessageReceipt | None:
        row = self.session.execute(
            select(Message.id, Message.trace_id).where(
                Message.telegram_chat_id == telegram_chat_id,
                Message.telegram_message_id == telegram_message_id,
            )
        ).one_or_none()
        if row is None:
            return None
        return StoredMessageReceipt(id=row.id, trace_id=row.trace_id)

    def list_group_context_telegram_bindings(
        self,
        *,
        telegram_chat_id: str,
        telegram_user_id: str,
    ) -> list[Stage06TelegramBinding]:
        return list(
            self.session.scalars(
                select(Stage06TelegramBinding).where(
                    Stage06TelegramBinding.telegram_chat_id == telegram_chat_id,
                    Stage06TelegramBinding.telegram_user_id == telegram_user_id,
                )
            )
        )

    def list_group_business_context_bindings(
        self,
        telegram_binding_id: UUID,
    ) -> list[Stage08GroupBusinessContextBinding]:
        return list(
            self.session.scalars(
                select(Stage08GroupBusinessContextBinding).where(
                    Stage08GroupBusinessContextBinding.telegram_binding_id
                    == telegram_binding_id
                )
            )
        )

    def group_context_records_match_workspace(
        self,
        binding: Stage08GroupBusinessContextBinding,
    ) -> bool:
        if binding.customer_record_id == binding.project_record_id:
            return False
        customer_workspace_id = self._active_record_workspace_id(
            binding.customer_record_id
        )
        project_workspace_id = self._active_record_workspace_id(
            binding.project_record_id
        )
        return (
            customer_workspace_id == binding.workspace_id
            and project_workspace_id == binding.workspace_id
        )

    def _active_record_workspace_id(self, record_id: UUID) -> UUID | None:
        return self.session.scalar(
            select(BitableBase.workspace_id)
            .join(PlatformTable, PlatformTable.base_id == BitableBase.id)
            .join(PlatformRecord, PlatformRecord.table_id == PlatformTable.id)
            .where(
                PlatformRecord.id == record_id,
                PlatformRecord.record_status == "active",
                PlatformTable.status == "active",
                BitableBase.status == "active",
            )
        )

    def list_group_message_projections_for_source(
        self,
        source_message_id: UUID,
    ) -> list[Stage08GroupMessageProjection]:
        return list(
            self.session.scalars(
                select(Stage08GroupMessageProjection)
                .where(
                    Stage08GroupMessageProjection.source_message_id
                    == source_message_id
                )
                .order_by(
                    Stage08GroupMessageProjection.content_version.desc(),
                    Stage08GroupMessageProjection.id.desc(),
                )
                .with_for_update()
            )
        )

    def add_group_message_projection(
        self,
        projection: Stage08GroupMessageProjection,
    ) -> None:
        self.session.add(projection)
        try:
            self.session.flush([projection])
        except SQLAlchemyError:
            raise TelegramIngestionPersistenceError(
                "group_context_projection_write_failed"
            ) from None

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

    def list_customer_bindings(
        self,
        *,
        telegram_chat_id: str,
        telegram_user_id: str | None,
    ) -> list[TelegramCustomerBindingRecord]:
        conditions = [TelegramCustomerBinding.telegram_chat_id == telegram_chat_id]
        if telegram_user_id is not None:
            conditions.append(TelegramCustomerBinding.telegram_user_id == telegram_user_id)
        bindings = self.session.scalars(
            select(TelegramCustomerBinding).where(or_(*conditions))
        )
        return [
            TelegramCustomerBindingRecord(
                id=binding.id,
                customer_id=binding.customer_id,
                telegram_chat_id=binding.telegram_chat_id,
                telegram_user_id=binding.telegram_user_id,
                binding_scope=binding.binding_scope,
                status=binding.status,
                label=binding.label,
                created_by=binding.created_by,
            )
            for binding in bindings
        ]

    def add_message(self, message: IngestedMessage) -> None:
        row = Message(
            id=message.id,
            telegram_update_id=message.telegram_update_id,
            telegram_chat_id=message.telegram_chat_id,
            telegram_message_id=message.telegram_message_id,
            telegram_user_id=message.telegram_user_id,
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
            binding_status=message.binding_status,
            processing_status=message.processing_status,
            outbox_status=message.outbox_status,
            last_error_code=message.last_error_code,
            processed_at=message.processed_at,
            trace_id=message.trace_id,
        )
        self.session.add(row)
        try:
            self.session.flush([row])
        except SQLAlchemyError:
            raise TelegramIngestionPersistenceError(
                "telegram_message_write_failed"
            ) from None

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
    existing_message = uow.get_message_receipt_by_update_id(update.update_id)
    trace_id = f"tg:{update.update_id}"
    if existing_message is not None:
        return TelegramIngestionResult(
            status="duplicate",
            message_id=str(existing_message.id),
            trace_id=existing_message.trace_id,
        )

    group_context_binding = _resolve_group_context_binding(update, uow)
    source_receipt = uow.get_message_receipt_by_source_identity(
        telegram_chat_id=update.chat_id,
        telegram_message_id=update.message_id,
    )
    if update.update_kind == "edited":
        if source_receipt is None:
            return TelegramIngestionResult(
                status="ignored",
                message_id="",
                trace_id=trace_id,
            )
        if group_context_binding is not None:
            _write_group_context_projection(
                update,
                uow,
                source_message_id=source_receipt.id,
                business_context_binding=group_context_binding,
                edited=True,
            )
        return TelegramIngestionResult(
            status="stored",
            message_id=str(source_receipt.id),
            trace_id=source_receipt.trace_id,
        )

    if source_receipt is not None:
        return TelegramIngestionResult(
            status="duplicate",
            message_id=str(source_receipt.id),
            trace_id=source_receipt.trace_id,
        )

    binding = resolve_customer_binding(
        uow,
        telegram_chat_id=update.chat_id,
        telegram_user_id=update.sender_user_id,
    )
    bound_group = None
    if binding.binding_status == "needs_manual_binding":
        bound_group = uow.find_customer_group_by_chat_id(update.chat_id)
        if bound_group is not None:
            binding = CustomerBindingResolution(
                binding_status="bound",
                customer_id=bound_group.customer_id,
                binding_scope="legacy_customer_group",
            )
    message = IngestedMessage(
        id=uuid4(),
        telegram_update_id=update.update_id,
        telegram_chat_id=update.chat_id,
        telegram_message_id=update.message_id,
        telegram_user_id=update.sender_user_id,
        customer_group_id=(
            None if bound_group is None else bound_group.customer_group_id
        ),
        customer_id=binding.customer_id,
        raw_text=update.text,
        raw_caption=update.caption,
        normalized_text=normalize_message_text(update.text or update.caption),
        message_type=update.message_type,
        intent_status=(
            "unclassified"
            if binding.binding_status == "bound"
            else "needs_review"
        ),
        intent_type=None,
        ingestion_status="stored",
        binding_status=binding.binding_status,
        processing_status="queued",
        outbox_status="pending",
        trace_id=trace_id,
    )
    message.received_at = update.received_at

    uow.add_message(message)
    if group_context_binding is not None:
        _write_group_context_projection(
            update,
            uow,
            source_message_id=message.id,
            business_context_binding=group_context_binding,
            edited=False,
        )
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
            "binding_status": message.binding_status,
            "intent_status": message.intent_status,
            "ingestion_status": message.ingestion_status,
            "processing_status": message.processing_status,
            "outbox_status": message.outbox_status,
        },
    )
    record_audit_event(
        uow,
        trace_id=trace_id,
        actor_type="system",
        actor_id="customer_binding",
        event_type=_binding_audit_event_type(message.binding_status),
        entity_type="message",
        entity_id=message.id,
        after_state={
            "telegram_chat_id": update.chat_id,
            "telegram_user_id": update.sender_user_id,
            "customer_id": None if message.customer_id is None else str(message.customer_id),
            "binding_status": message.binding_status,
            "binding_scope": binding.binding_scope,
        },
    )
    return TelegramIngestionResult(
        status="stored",
        message_id=str(message.id),
        trace_id=trace_id,
    )


def _resolve_group_context_binding(
    update: MockTelegramUpdate,
    uow: TelegramIngestionUnitOfWork,
) -> Stage08GroupBusinessContextBinding | None:
    if update.chat_type not in {"group", "supergroup"}:
        return None
    if not update.sender_user_id:
        return None
    bindings = [
        binding
        for binding in uow.list_group_context_telegram_bindings(
            telegram_chat_id=update.chat_id,
            telegram_user_id=update.sender_user_id,
        )
        if binding.status == "active" and binding.binding_type == "chat_user"
    ]
    if len(bindings) != 1:
        return None
    telegram_binding = bindings[0]
    mappings = [
        mapping
        for mapping in uow.list_group_business_context_bindings(telegram_binding.id)
        if mapping.status == "active"
        and mapping.workspace_id == telegram_binding.workspace_id
        and uow.group_context_records_match_workspace(mapping)
    ]
    if len(mappings) != 1:
        return None
    return mappings[0]


def _write_group_context_projection(
    update: MockTelegramUpdate,
    uow: TelegramIngestionUnitOfWork,
    *,
    source_message_id: UUID,
    business_context_binding: Stage08GroupBusinessContextBinding,
    edited: bool,
) -> None:
    body = update.text if update.text is not None else update.caption
    content_fragment = normalize_message_text(body)
    if not content_fragment:
        return
    content_fragment = content_fragment[:500]
    event_at = _as_utc(update.received_at)
    existing = uow.list_group_message_projections_for_source(source_message_id)
    if edited:
        active = [
            projection
            for projection in existing
            if projection.lifecycle_status == "active"
            and projection.retention_expires_at > event_at
        ]
        if len(active) != 1:
            return
        previous = active[0]
        if (
            previous.business_context_binding_id != business_context_binding.id
            or _as_utc(previous.event_at) != event_at
        ):
            return
        edited_at = (
            None if update.edited_at is None else _as_utc(update.edited_at)
        )
        previous_edited_at = (
            None
            if previous.edited_at is None
            else _as_utc(previous.edited_at)
        )
        if (
            previous.content_fragment == content_fragment
            and previous_edited_at == edited_at
        ):
            return
        content_version = max(
            projection.content_version for projection in existing
        ) + 1
        previous.lifecycle_status = "superseded"
    else:
        if existing:
            return
        content_version = 1
        edited_at = None
    uow.add_group_message_projection(
        Stage08GroupMessageProjection(
            id=uuid4(),
            source_message_id=source_message_id,
            business_context_binding_id=business_context_binding.id,
            content_fragment=content_fragment,
            content_version=content_version,
            event_at=event_at,
            edited_at=edited_at,
            retention_expires_at=event_at + timedelta(days=30),
            lifecycle_status="active",
            source_chat_type=update.chat_type,
        )
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_message_text(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.strip().split())


def message_received_at(message: IngestedMessage):
    return getattr(message, "received_at")


def _binding_audit_event_type(binding_status: str) -> str:
    if binding_status == "bound":
        return "telegram.binding.resolved"
    if binding_status == "binding_conflict":
        return "telegram.binding.conflict"
    return "telegram.binding.unbound"


def _to_ingested_message(message: Message) -> IngestedMessage:
    ingested = IngestedMessage(
        id=message.id,
        telegram_update_id=message.telegram_update_id,
        telegram_chat_id=message.telegram_chat_id,
        telegram_message_id=message.telegram_message_id,
        telegram_user_id=message.telegram_user_id,
        customer_group_id=message.customer_group_id,
        customer_id=message.customer_id,
        raw_text=message.raw_text,
        raw_caption=message.raw_caption,
        normalized_text=message.normalized_text,
        message_type=message.message_type,
        intent_status=message.intent_status,
        intent_type=message.intent_type,
        ingestion_status=message.ingestion_status,
        binding_status=message.binding_status,
        processing_status=message.processing_status,
        outbox_status=message.outbox_status,
        last_error_code=message.last_error_code,
        processed_at=message.processed_at,
        trace_id=message.trace_id,
    )
    ingested.received_at = message.received_at
    return ingested
