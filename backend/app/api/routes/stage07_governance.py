from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.core.errors import error_detail
from app.schemas.stage07_governance import (
    GovernanceAuditEventResponse,
    GovernanceAuditPageResponse,
    GovernanceMemberPageResponse,
    GovernanceMemberResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
    workspace_id_for_base,
)
from app.services.stage06_digital_employees import (
    Stage06RuntimeUnitOfWork,
    list_base_audit_events,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_pagination import Stage06PaginationError, paginate_items
from app.services.stage06_platform import (
    Stage06PlatformUnitOfWork,
    list_workspace_members,
)


router = APIRouter(tags=["stage07-governance"])


@router.get(
    "/mini-app/workspaces/{workspace_id}/governance/members",
    response_model=GovernanceMemberPageResponse,
)
def list_governance_members(
    workspace_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> GovernanceMemberPageResponse:
    try:
        authorize_workspace_action(uow, identity, workspace_id, "member.read")
        page = paginate_items(
            list_workspace_members(uow, workspace_id),
            limit=limit,
            cursor=cursor,
        )
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except Stage06PaginationError as exc:
        raise _governance_pagination_error(exc) from exc
    return GovernanceMemberPageResponse(
        workspace_id=str(workspace_id),
        members=[
            GovernanceMemberResponse(
                id=str(member.id),
                user_id=member.user_id,
                role=member.role,
                status=member.status,
            )
            for member in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get(
    "/mini-app/bases/{base_id}/governance/audit-events",
    response_model=GovernanceAuditPageResponse,
)
def list_governance_audit_events(
    base_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> GovernanceAuditPageResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(uow, identity, workspace_id, "audit.read")
        page = paginate_items(
            list_base_audit_events(uow, base_id),
            limit=limit,
            cursor=cursor,
        )
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except Stage06PaginationError as exc:
        raise _governance_pagination_error(exc) from exc
    return GovernanceAuditPageResponse(
        base_id=str(base_id),
        events=[
            GovernanceAuditEventResponse(
                id=str(event.id),
                occurred_at=event.created_at,
                actor_type=_safe_actor_type(event.actor_type),
                event_type=event.event_type,
                entity_type=event.entity_type,
            )
            for event in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


def _safe_actor_type(value: object) -> str:
    return value if value in {"user", "digital_employee", "system"} else "system"


def _authorization_error(exc: Stage06AuthorizationError) -> HTTPException:
    return HTTPException(
        status_code=404 if exc.code.endswith("_not_found") else 403,
        detail=error_detail(exc.code, exc.code),
    )


def _governance_pagination_error(exc: Stage06PaginationError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=error_detail("governance_invalid_cursor", "governance_invalid_cursor"),
    )
