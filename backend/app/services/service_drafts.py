from collections.abc import Iterable
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.interfaces import DraftCandidate
from app.models.audit import OpsAuditEvent
from app.models.service_drafts import ServiceDraft
from app.models.telegram import Message
from app.services.audit import record_audit_event
from app.services.telegram_ingestion import IngestedMessage


class ServiceDraftUnitOfWork(Protocol):
    def get_message(self, message_id: str) -> IngestedMessage | None:
        pass

    def add_service_draft(self, draft: ServiceDraft) -> None:
        pass

    def mark_message_routed(self, message: IngestedMessage, intent_type: str) -> None:
        pass

    def record_draft_created(self, draft: ServiceDraft, trace_id: str) -> None:
        pass

    def list_service_drafts(self) -> list[ServiceDraft]:
        pass


class InMemoryServiceDraftUnitOfWork:
    def __init__(self, messages: Iterable[IngestedMessage] | None = None) -> None:
        self.messages = list(messages or [])
        self.service_drafts: list[ServiceDraft] = []
        self.audit_events: list[OpsAuditEvent] = []

    def get_message(self, message_id: str) -> IngestedMessage | None:
        return next(
            (message for message in self.messages if str(message.id) == message_id),
            None,
        )

    def add_service_draft(self, draft: ServiceDraft) -> None:
        self.service_drafts.append(draft)

    def mark_message_routed(self, message: IngestedMessage, intent_type: str) -> None:
        message.intent_status = "routed"
        message.intent_type = intent_type

    def record_draft_created(self, draft: ServiceDraft, trace_id: str) -> None:
        self.audit_events.append(
            OpsAuditEvent(
                trace_id=trace_id,
                actor_type="agent",
                actor_id="mock_router",
                event_type="draft_created",
                entity_type="service_draft",
                entity_id=draft.id,
                after_state={
                    "draft_type": draft.draft_type,
                    "status": draft.status,
                    "payload": draft.payload,
                },
            )
        )

    def list_service_drafts(self) -> list[ServiceDraft]:
        return list(self.service_drafts)


class SqlAlchemyServiceDraftUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_message(self, message_id: str) -> IngestedMessage | None:
        message = self.session.scalar(
            select(Message).where(Message.id == UUID(message_id))
        )
        if message is None:
            return None
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

    def add_service_draft(self, draft: ServiceDraft) -> None:
        self.session.add(draft)

    def mark_message_routed(self, message: IngestedMessage, intent_type: str) -> None:
        stored_message = self.session.scalar(
            select(Message).where(Message.id == message.id)
        )
        if stored_message is None:
            return
        stored_message.intent_status = "routed"
        stored_message.intent_type = intent_type

    def record_draft_created(self, draft: ServiceDraft, trace_id: str) -> None:
        record_audit_event(
            self.session,
            trace_id=trace_id,
            actor_type="agent",
            actor_id="mock_router",
            event_type="draft_created",
            entity_type="service_draft",
            entity_id=draft.id,
            after_state={
                "draft_type": draft.draft_type,
                "status": draft.status,
                "payload": draft.payload,
            },
        )

    def list_service_drafts(self) -> list[ServiceDraft]:
        return list(self.session.scalars(select(ServiceDraft)))


def create_service_draft_from_candidate(
    message: IngestedMessage,
    candidate: DraftCandidate,
) -> ServiceDraft:
    return ServiceDraft(
        id=uuid4(),
        draft_type=candidate.draft_type,
        status=candidate.status,
        customer_id=message.customer_id,
        source_message_id=message.id,
        created_by_type="agent",
        created_by_id="mock_router",
        payload=candidate.payload,
        missing_fields=candidate.missing_fields,
        risk_flags=[],
        confidence=candidate.confidence,
        trace_id=message.trace_id,
        idempotency_key=f"draft:{message.id}:{candidate.draft_type}",
    )
