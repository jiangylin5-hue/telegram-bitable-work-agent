from hmac import compare_digest
from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.schemas.telegram import MockTelegramUpdate
from app.services.telegram_ingestion import (
    SqlAlchemyTelegramIngestionUnitOfWork,
    TelegramIngestionUnitOfWork,
    ingest_mock_telegram_update,
)
from app.services.telegram_update_parser import (
    TelegramUpdateParseError,
    parse_telegram_update,
)

TELEGRAM_MESSAGE_RECEIVED_EVENT = "telegram.message_received"

router = APIRouter(prefix="/telegram", tags=["telegram"])


def get_telegram_webhook_ingestion_uow(
    session: Session = Depends(get_session),
) -> TelegramIngestionUnitOfWork:
    return SqlAlchemyTelegramIngestionUnitOfWork(session)


@router.post("/webhook")
def receive_telegram_webhook(
    payload: dict[str, Any],
    secret_token: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
    settings: Settings = Depends(get_settings),
    uow: TelegramIngestionUnitOfWork = Depends(get_telegram_webhook_ingestion_uow),
):
    if not _valid_secret(secret_token, settings.telegram_webhook_secret):
        return _error_response(
            403,
            "telegram_webhook_forbidden",
            "Forbidden",
        )

    try:
        parsed = parse_telegram_update(payload)
    except TelegramUpdateParseError:
        return _error_response(
            400,
            "telegram_update_invalid",
            "Invalid Telegram update",
        )

    if not _allowed_source(parsed.chat_id, settings.telegram_allowed_chat_ids):
        return _error_response(
            403,
            "telegram_source_not_allowed",
            "Telegram source is not allowed",
        )
    if not _allowed_source(parsed.sender_user_id, settings.telegram_allowed_user_ids):
        return _error_response(
            403,
            "telegram_source_not_allowed",
            "Telegram source is not allowed",
        )

    update = MockTelegramUpdate(
        update_id=parsed.update_id,
        chat_id=parsed.chat_id,
        message_id=parsed.message_id,
        sender_user_id=parsed.sender_user_id or "",
        username=parsed.username,
        text=parsed.text,
        caption=parsed.caption,
        message_type=parsed.message_type,
        received_at=parsed.received_at,
    )
    result = ingest_mock_telegram_update(
        update,
        uow,
        outbox_event_type=TELEGRAM_MESSAGE_RECEIVED_EVENT,
    )
    uow.commit()
    duplicate = result.status == "duplicate"
    return {
        "status": "accepted",
        "message_id": result.message_id,
        "duplicate": duplicate,
    }


def _valid_secret(
    provided_secret: str | None,
    configured_secret: str | None,
) -> bool:
    if configured_secret is None:
        return True
    return compare_digest(provided_secret or "", configured_secret)


def _allowed_source(value: str | None, allowlist: tuple[str, ...]) -> bool:
    if not allowlist:
        return True
    if value is None:
        return False
    return value in allowlist


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )
