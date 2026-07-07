from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_system_actor
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.schemas.telegram_send_requests import (
    TelegramSendRequestConfirm,
    TelegramSendRequestCreate,
    TelegramSendRequestMutationResponse,
)
from app.services.permissions import Actor, PermissionDenied
from app.services.telegram_send_requests import (
    NOT_ALLOWLISTED_ERROR,
    SqlAlchemyTelegramSendRequestUnitOfWork,
    TelegramSendRequestNotFound,
    TelegramSendRequestStateError,
    TelegramSendRequestUnitOfWork,
    TelegramTestSendTargetNotAllowlisted,
    confirm_test_send_request,
    create_test_send_request,
)

router = APIRouter(prefix="/telegram/send-requests", tags=["telegram-send-requests"])


def get_telegram_send_request_uow(
    session: Session = Depends(get_session),
) -> TelegramSendRequestUnitOfWork:
    return SqlAlchemyTelegramSendRequestUnitOfWork(session)


def get_telegram_send_settings() -> Settings:
    return get_settings()


@router.post(
    "",
    response_model=TelegramSendRequestMutationResponse,
    response_model_exclude_none=True,
)
def create_send_request(
    request: TelegramSendRequestCreate,
    actor: Actor = Depends(get_system_actor),
    settings: Settings = Depends(get_telegram_send_settings),
    uow: TelegramSendRequestUnitOfWork = Depends(get_telegram_send_request_uow),
) -> TelegramSendRequestMutationResponse:
    try:
        send_request = create_test_send_request(
            uow,
            actor=actor,
            request=request,
            allowed_chat_ids=settings.telegram_test_send_allowed_chat_ids,
        )
        uow.commit()
        return TelegramSendRequestMutationResponse(
            status=send_request.status,
            request_id=send_request.id,
            trace_id=send_request.trace_id,
            error_code=send_request.last_error_code,
        )
    except PermissionDenied as exc:
        uow.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/{request_id}/confirm",
    response_model=TelegramSendRequestMutationResponse,
    response_model_exclude_none=True,
)
def confirm_send_request(
    request_id: UUID,
    request: TelegramSendRequestConfirm,
    actor: Actor = Depends(get_system_actor),
    settings: Settings = Depends(get_telegram_send_settings),
    uow: TelegramSendRequestUnitOfWork = Depends(get_telegram_send_request_uow),
) -> TelegramSendRequestMutationResponse | JSONResponse:
    if not request.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true")
    try:
        send_request, _event = confirm_test_send_request(
            uow,
            actor=actor,
            request_id=request_id,
            allowed_chat_ids=settings.telegram_test_send_allowed_chat_ids,
        )
        uow.commit()
        return TelegramSendRequestMutationResponse(
            status=send_request.status,
            request_id=send_request.id,
            queued=True,
        )
    except PermissionDenied as exc:
        uow.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TelegramSendRequestNotFound:
        return _error_response(
            404,
            "telegram_send_request_not_found",
            "Telegram send request not found",
        )
    except TelegramSendRequestStateError:
        return _error_response(
            409,
            "telegram_send_request_invalid_state",
            "Telegram send request is not pending confirmation",
        )
    except TelegramTestSendTargetNotAllowlisted:
        uow.commit()
        return _error_response(
            409,
            NOT_ALLOWLISTED_ERROR,
            "Telegram test send target is not allowlisted",
        )


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )
