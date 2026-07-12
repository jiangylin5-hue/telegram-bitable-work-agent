from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.config import get_settings
from app.core.errors import error_detail
from app.services.permissions import Actor
from app.services.stage06_identity import (
    Stage06IdentityError,
    Stage06RequestIdentity,
    resolve_stage06_request_identity,
)
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    Stage06PlatformUnitOfWork,
)
from app.services.stage07_telegram_mini_app_identity import (
    Stage07TelegramMiniAppIdentityError,
    resolve_telegram_request_identity,
    validate_telegram_mini_app_init_data,
)


def get_system_actor() -> Actor:
    return Actor(actor_type="system", actor_id="stage-02-system", role="admin")


def get_stage06_identity_uow(
    session: Session = Depends(get_session),
) -> Stage06PlatformUnitOfWork:
    return SqlAlchemyStage06PlatformUnitOfWork(session)


def get_stage06_request_identity(
    x_stage06_user_id: str | None = Header(
        default=None,
        alias="X-Stage06-User-Id",
    ),
    x_telegram_init_data: str | None = Header(
        default=None,
        alias="X-Telegram-Init-Data",
    ),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_identity_uow),
) -> Stage06RequestIdentity:
    try:
        settings = get_settings()
        if x_telegram_init_data is not None:
            launch = validate_telegram_mini_app_init_data(
                x_telegram_init_data,
                bot_token=settings.telegram_bot_token,
                now=datetime.now(UTC),
                max_age_seconds=settings.telegram_mini_app_init_max_age_seconds,
            )
            return resolve_telegram_request_identity(uow, launch)
        return resolve_stage06_request_identity(
            settings,
            development_user_id=x_stage06_user_id,
        )
    except (Stage06IdentityError, Stage07TelegramMiniAppIdentityError) as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 401),
            detail=error_detail(exc.code, str(exc)),
        ) from exc
