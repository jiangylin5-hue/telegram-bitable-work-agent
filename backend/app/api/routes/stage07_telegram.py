from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_required_telegram_mini_app_launch,
    get_stage06_request_identity,
)
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.schemas.stage07_telegram import (
    SafeTelegramDeepLinkDestination,
    TelegramDeepLinkResolveRequest,
    TelegramDeepLinkResolveResponse,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import Stage06PlatformUnitOfWork
from app.services.stage07_telegram_deep_links import resolve_telegram_deep_link
from app.services.stage07_telegram_mini_app_identity import (
    ValidatedTelegramMiniAppLaunch,
)


router = APIRouter(tags=["stage07-telegram"])


@router.post(
    "/mini-app/telegram/deep-links/resolve",
    response_model=TelegramDeepLinkResolveResponse,
    response_model_exclude_none=True,
)
def resolve_telegram_deep_link_endpoint(
    request: TelegramDeepLinkResolveRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    launch: ValidatedTelegramMiniAppLaunch = Depends(
        get_required_telegram_mini_app_launch
    ),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> TelegramDeepLinkResolveResponse:
    destination = resolve_telegram_deep_link(
        uow,
        identity=identity,
        launch=launch,
        start_param=request.start_param,
        now=datetime.now(UTC),
    )
    if destination is None:
        return TelegramDeepLinkResolveResponse(outcome="recovery")
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()
    return TelegramDeepLinkResolveResponse(
        outcome="resolved",
        destination=SafeTelegramDeepLinkDestination(
            kind=destination.kind,
            workspace_id=str(destination.workspace_id),
            base_id=None if destination.base_id is None else str(destination.base_id),
            table_id=None if destination.table_id is None else str(destination.table_id),
            view_id=None if destination.view_id is None else str(destination.view_id),
            record_id=(
                None if destination.record_id is None else str(destination.record_id)
            ),
            draft_id=None if destination.draft_id is None else str(destination.draft_id),
        ),
    )
