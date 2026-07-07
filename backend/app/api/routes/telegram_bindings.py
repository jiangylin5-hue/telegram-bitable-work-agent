from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_system_actor
from app.core.database import get_session
from app.schemas.telegram_bindings import (
    TelegramBindingCreate,
    TelegramBindingDisableRequest,
    TelegramBindingListResponse,
    TelegramBindingMutationResponse,
    TelegramBindingRecord,
)
from app.services.permissions import Actor, PermissionDenied
from app.services.telegram_binding_management import (
    SqlAlchemyTelegramBindingUnitOfWork,
    TelegramBindingConflict,
    TelegramBindingCustomerNotFound,
    TelegramBindingFilters,
    TelegramBindingNotFound,
    TelegramBindingUnitOfWork,
    create_telegram_binding,
    disable_telegram_binding,
    list_telegram_bindings,
)

router = APIRouter(prefix="/telegram/bindings", tags=["telegram-bindings"])


def get_telegram_binding_uow(
    session: Session = Depends(get_session),
) -> TelegramBindingUnitOfWork:
    return SqlAlchemyTelegramBindingUnitOfWork(session)


@router.post("", response_model=TelegramBindingMutationResponse)
def create_binding(
    request: TelegramBindingCreate,
    actor: Actor = Depends(get_system_actor),
    uow: TelegramBindingUnitOfWork = Depends(get_telegram_binding_uow),
) -> TelegramBindingMutationResponse | JSONResponse:
    try:
        binding = create_telegram_binding(uow, actor=actor, request=request)
        uow.commit()
        return TelegramBindingMutationResponse(
            status="created",
            binding_id=binding.id,
            customer_id=binding.customer_id,
            binding_scope=binding.binding_scope,
        )
    except PermissionDenied as exc:
        uow.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TelegramBindingCustomerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TelegramBindingConflict:
        uow.commit()
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "telegram_binding_conflict",
                    "message": "Active Telegram binding already exists",
                }
            },
        )


@router.get("", response_model=TelegramBindingListResponse)
def list_bindings(
    customer_id: UUID | None = None,
    telegram_chat_id: str | None = None,
    telegram_user_id: str | None = None,
    status: str | None = Query(default=None, pattern="^(active|inactive)$"),
    actor: Actor = Depends(get_system_actor),
    uow: TelegramBindingUnitOfWork = Depends(get_telegram_binding_uow),
) -> TelegramBindingListResponse:
    try:
        bindings = list_telegram_bindings(
            uow,
            actor=actor,
            filters=TelegramBindingFilters(
                customer_id=customer_id,
                telegram_chat_id=telegram_chat_id,
                telegram_user_id=telegram_user_id,
                status=status,
            ),
        )
    except PermissionDenied as exc:
        uow.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return TelegramBindingListResponse(
        bindings=[_binding_record(binding) for binding in bindings]
    )


@router.post(
    "/{binding_id}/disable",
    response_model=TelegramBindingMutationResponse,
    response_model_exclude_none=True,
)
def disable_binding(
    binding_id: UUID,
    request: TelegramBindingDisableRequest,
    actor: Actor = Depends(get_system_actor),
    uow: TelegramBindingUnitOfWork = Depends(get_telegram_binding_uow),
) -> TelegramBindingMutationResponse | JSONResponse:
    try:
        binding = disable_telegram_binding(
            uow,
            actor=actor,
            binding_id=binding_id,
            reason=request.reason,
        )
        uow.commit()
        return TelegramBindingMutationResponse(
            status="disabled",
            binding_id=binding.id,
        )
    except PermissionDenied as exc:
        uow.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TelegramBindingNotFound:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "telegram_binding_not_found",
                    "message": "Telegram binding not found",
                }
            },
        )


def _binding_record(binding) -> TelegramBindingRecord:
    return TelegramBindingRecord(
        binding_id=binding.id,
        customer_id=binding.customer_id,
        telegram_chat_id=binding.telegram_chat_id,
        telegram_user_id=binding.telegram_user_id,
        binding_scope=binding.binding_scope,
        status=binding.status,
        label=binding.label,
        created_by=binding.created_by,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
    )
