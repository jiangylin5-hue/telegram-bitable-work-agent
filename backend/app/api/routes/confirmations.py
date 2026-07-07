from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.schemas.service_drafts import (
    ConfirmationActionRequest,
    ConfirmationActionResponse,
)
from app.services.confirmation import (
    ConfirmationStateError,
    ConfirmationUnitOfWork,
    SqlAlchemyConfirmationUnitOfWork,
    confirm_service_draft,
    escalate_service_draft,
    reject_service_draft,
    request_more_info_for_service_draft,
)
from app.services.permissions import Actor, PermissionDenied

router = APIRouter(prefix="/confirmations", tags=["confirmations"])


def get_confirmation_uow(
    session: Session = Depends(get_session),
) -> ConfirmationUnitOfWork:
    return SqlAlchemyConfirmationUnitOfWork(session)


def get_confirmation_settings() -> Settings:
    return get_settings()


@router.post(
    "/service-drafts/{draft_id}/actions",
    response_model=ConfirmationActionResponse,
)
def apply_service_draft_action(
    draft_id: UUID,
    request: ConfirmationActionRequest,
    settings: Settings = Depends(get_confirmation_settings),
    uow: ConfirmationUnitOfWork = Depends(get_confirmation_uow),
) -> ConfirmationActionResponse:
    actor = Actor(
        actor_type=request.actor_type,
        actor_id=request.actor_id,
        role=request.role,
    )
    try:
        if request.action == "confirm":
            result = confirm_service_draft(
                uow,
                draft_id,
                actor,
                allowed_chat_ids=_allowed_chat_ids(settings, uow),
            )
            uow.commit()
            return ConfirmationActionResponse(
                draft_id=str(draft_id),
                draft_status=_confirmed_draft_status(result),
                service_record_id=(
                    None
                    if result.service_record is None
                    else str(result.service_record.id)
                ),
                execution_ticket_id=(
                    None
                    if result.execution_ticket is None
                    else str(result.execution_ticket.id)
                ),
                telegram_send_request_id=(
                    None
                    if result.telegram_send_request is None
                    else str(result.telegram_send_request.id)
                ),
                side_effect=result.side_effect,
            )
        if request.action == "reject":
            draft = reject_service_draft(
                uow,
                draft_id,
                actor,
                reason=request.reason or "no reason provided",
            )
            uow.commit()
            return _draft_response(draft.id, draft.status)
        if request.action == "request_more_info":
            draft = request_more_info_for_service_draft(
                uow,
                draft_id,
                actor,
                missing_fields=request.missing_fields,
            )
            uow.commit()
            return _draft_response(draft.id, draft.status)
        if request.action == "escalate":
            draft = escalate_service_draft(
                uow,
                draft_id,
                actor,
                reason=request.reason or "manual review requested",
            )
            uow.commit()
            return _draft_response(draft.id, draft.status)
    except PermissionDenied as exc:
        uow.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ConfirmationStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")


def _draft_response(draft_id: UUID, status: str) -> ConfirmationActionResponse:
    return ConfirmationActionResponse(draft_id=str(draft_id), draft_status=status)


def _allowed_chat_ids(
    settings: Settings,
    uow: ConfirmationUnitOfWork,
) -> tuple[str, ...]:
    return settings.telegram_test_send_allowed_chat_ids or getattr(
        uow,
        "allowed_chat_ids",
        (),
    )


def _confirmed_draft_status(result) -> str:
    if result.service_record is not None and result.execution_ticket is None:
        return "service_record_created"
    return "confirmed"
