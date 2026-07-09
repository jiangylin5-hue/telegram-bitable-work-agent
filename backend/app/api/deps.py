from fastapi import Header, HTTPException

from app.core.config import get_settings
from app.core.errors import error_detail
from app.services.permissions import Actor
from app.services.stage06_identity import (
    Stage06IdentityError,
    Stage06RequestIdentity,
    resolve_stage06_request_identity,
)


def get_system_actor() -> Actor:
    return Actor(actor_type="system", actor_id="stage-02-system", role="admin")


def get_stage06_request_identity(
    x_stage06_user_id: str | None = Header(
        default=None,
        alias="X-Stage06-User-Id",
    ),
) -> Stage06RequestIdentity:
    try:
        return resolve_stage06_request_identity(
            get_settings(),
            development_user_id=x_stage06_user_id,
        )
    except Stage06IdentityError as exc:
        raise HTTPException(
            status_code=401,
            detail=error_detail(exc.code, str(exc)),
        ) from exc
