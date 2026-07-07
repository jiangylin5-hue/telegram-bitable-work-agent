from collections.abc import Iterable
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.interfaces import DraftCandidate
from app.agents.schemas import Stage05DraftCandidate
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

    def get_service_draft_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ServiceDraft | None:
        pass

    def mark_message_routed(self, message: IngestedMessage, intent_type: str) -> None:
        pass

    def record_draft_created(self, draft: ServiceDraft, trace_id: str) -> None:
        pass

    def list_service_drafts(
        self,
        *,
        status: str | None = None,
        draft_type: str | None = None,
        customer_id: UUID | None = None,
        source_message_id: UUID | None = None,
        trace_id: str | None = None,
        limit: int | None = None,
    ) -> list[ServiceDraft]:
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

    def get_service_draft_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ServiceDraft | None:
        return next(
            (
                draft
                for draft in self.service_drafts
                if draft.idempotency_key == idempotency_key
            ),
            None,
        )

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

    def list_service_drafts(
        self,
        *,
        status: str | None = None,
        draft_type: str | None = None,
        customer_id: UUID | None = None,
        source_message_id: UUID | None = None,
        trace_id: str | None = None,
        limit: int | None = None,
    ) -> list[ServiceDraft]:
        drafts = [
            draft
            for draft in self.service_drafts
            if _matches_service_draft_filters(
                draft,
                status=status,
                draft_type=draft_type,
                customer_id=customer_id,
                source_message_id=source_message_id,
                trace_id=trace_id,
            )
        ]
        return drafts[:limit] if limit is not None else drafts


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

    def get_service_draft_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ServiceDraft | None:
        return self.session.scalar(
            select(ServiceDraft).where(ServiceDraft.idempotency_key == idempotency_key)
        )

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

    def list_service_drafts(
        self,
        *,
        status: str | None = None,
        draft_type: str | None = None,
        customer_id: UUID | None = None,
        source_message_id: UUID | None = None,
        trace_id: str | None = None,
        limit: int | None = None,
    ) -> list[ServiceDraft]:
        statement = select(ServiceDraft)
        if status is not None:
            statement = statement.where(ServiceDraft.status == status)
        if draft_type is not None:
            statement = statement.where(ServiceDraft.draft_type == draft_type)
        if customer_id is not None:
            statement = statement.where(ServiceDraft.customer_id == customer_id)
        if source_message_id is not None:
            statement = statement.where(
                ServiceDraft.source_message_id == source_message_id
            )
        if trace_id is not None:
            statement = statement.where(ServiceDraft.trace_id == trace_id)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.scalars(statement))


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


def create_service_draft_from_stage05_candidate(
    candidate: Stage05DraftCandidate,
) -> ServiceDraft:
    return ServiceDraft(
        id=uuid4(),
        draft_type=candidate.draft_type,
        status=candidate.status,
        customer_id=_uuid_or_none(candidate.customer_id),
        source_message_id=_uuid_or_none(candidate.source_message_id),
        source_agent_run_id=_uuid_or_none(candidate.source_agent_run_id),
        created_by_type=candidate.created_by_type,
        created_by_id=candidate.created_by_id,
        payload=candidate.payload,
        payload_summary=candidate.payload_summary,
        missing_fields=candidate.missing_fields,
        risk_flags=candidate.risk_flags,
        confidence=candidate.confidence,
        intent_index=candidate.intent_index,
        review_reason=candidate.review_reason,
        confirmed_at=None,
        trace_id=candidate.trace_id,
        idempotency_key=candidate.idempotency_key,
    )


def _uuid_or_none(value: str | None):
    if value is None:
        return None
    return UUID(value)


def _matches_service_draft_filters(
    draft: ServiceDraft,
    *,
    status: str | None,
    draft_type: str | None,
    customer_id: UUID | None,
    source_message_id: UUID | None,
    trace_id: str | None,
) -> bool:
    if status is not None and draft.status != status:
        return False
    if draft_type is not None and draft.draft_type != draft_type:
        return False
    if customer_id is not None and draft.customer_id != customer_id:
        return False
    if source_message_id is not None and draft.source_message_id != source_message_id:
        return False
    if trace_id is not None and draft.trace_id != trace_id:
        return False
    return True
