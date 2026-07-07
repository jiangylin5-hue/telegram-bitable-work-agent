from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.service_drafts import ServiceDraft
from app.schemas.service_drafts import ServiceDraftListResponse, ServiceDraftRecord
from app.services.service_drafts import (
    ServiceDraftUnitOfWork,
    SqlAlchemyServiceDraftUnitOfWork,
)

router = APIRouter(prefix="/service-drafts", tags=["service-drafts"])


def get_service_draft_uow(
    session: Session = Depends(get_session),
) -> ServiceDraftUnitOfWork:
    return SqlAlchemyServiceDraftUnitOfWork(session)


@router.get("", response_model=ServiceDraftListResponse)
def list_service_drafts(
    status: str | None = None,
    draft_type: str | None = None,
    customer_id: UUID | None = None,
    source_message_id: UUID | None = None,
    trace_id: str | None = None,
    limit: int | None = None,
    uow: ServiceDraftUnitOfWork = Depends(get_service_draft_uow),
) -> ServiceDraftListResponse:
    drafts = uow.list_service_drafts(
        status=status,
        draft_type=draft_type,
        customer_id=customer_id,
        source_message_id=source_message_id,
        trace_id=trace_id,
        limit=limit,
    )
    return ServiceDraftListResponse(records=[_to_record(draft) for draft in drafts])


def _to_record(draft: ServiceDraft) -> ServiceDraftRecord:
    return ServiceDraftRecord(
        id=str(draft.id),
        draft_type=draft.draft_type,
        status=draft.status,
        customer_id=None if draft.customer_id is None else str(draft.customer_id),
        source_message_id=(
            None if draft.source_message_id is None else str(draft.source_message_id)
        ),
        created_by_type=draft.created_by_type,
        created_by_id=draft.created_by_id,
        trace_id=draft.trace_id,
        payload=draft.payload,
        missing_fields=draft.missing_fields,
        risk_flags=draft.risk_flags,
        confidence=draft.confidence,
        created_at=draft.created_at,
    )
