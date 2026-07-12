from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.schemas.stage07_governance_write import (
    GovernanceEditableMemberPageResponse,
    GovernanceFieldPermissionListResponse,
    GovernanceFieldPermissionReceipt,
    GovernanceFieldPermissionRequest,
    GovernanceMemberRoleReceipt,
    GovernanceMemberRoleRequest,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
    workspace_id_for_table,
)
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_pagination import Stage06PaginationError, paginate_items
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    Stage06PlatformUnitOfWork,
    change_workspace_member_role,
    governance_field_permission_policy,
    list_governance_editable_members,
    list_governance_field_permissions,
    replace_field_permission_policy,
)


router = APIRouter(tags=["stage07-governance-write"])
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


@router.get(
    "/mini-app/workspaces/{workspace_id}/governance/member-editor",
    response_model=GovernanceEditableMemberPageResponse,
)
def list_governance_editable_member_context(
    workspace_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> GovernanceEditableMemberPageResponse:
    try:
        actor = authorize_workspace_action(uow, identity, workspace_id, "member.manage")
        page = paginate_items(
            list_governance_editable_members(uow, workspace_id, actor=actor),
            limit=limit,
            cursor=cursor,
        )
        return GovernanceEditableMemberPageResponse(
            workspace_id=str(workspace_id),
            members=[
                {
                    "id": str(member.id),
                    "user_id": member.user_id,
                    "role": member.role,
                    "status": member.status,
                    "version": member.version,
                    "assignable_roles": member.assignable_roles,
                }
                for member in page.items
            ],
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        )
    except (Stage06AuthorizationError, Stage06PaginationError, PlatformValidationError) as exc:
        raise _http_error(exc) from exc


@router.patch(
    "/mini-app/workspaces/{workspace_id}/governance/members/{member_id}/role",
    response_model=GovernanceMemberRoleReceipt,
)
def change_governance_member_role(
    workspace_id: UUID,
    member_id: UUID,
    request: GovernanceMemberRoleRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> GovernanceMemberRoleReceipt:
    try:
        actor = authorize_workspace_action(uow, identity, workspace_id, "member.manage")
        return _execute_idempotent(
            uow,
            workspace_id=workspace_id,
            operation="stage07.governance.member_role_change",
            idempotency_key=idempotency_key,
            payload={
                "workspace_id": str(workspace_id),
                "member_id": str(member_id),
                "role": request.role,
                "expected_version": request.expected_version,
            },
            response_model=GovernanceMemberRoleReceipt,
            build=lambda: _member_role_receipt(
                change_workspace_member_role(
                    uow,
                    workspace_id,
                    member_id,
                    role=request.role,
                    expected_version=request.expected_version,
                    actor=actor,
                )
            ),
        )
    except (Stage06AuthorizationError, PlatformValidationError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _http_error(exc) from exc


@router.get(
    "/mini-app/tables/{table_id}/governance/field-permissions",
    response_model=GovernanceFieldPermissionListResponse,
)
def list_governance_field_permission_context(
    table_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> GovernanceFieldPermissionListResponse:
    try:
        workspace_id = workspace_id_for_table(uow, table_id)
        authorize_workspace_action(uow, identity, workspace_id, "field.permission.manage")
        return GovernanceFieldPermissionListResponse(
            table_id=str(table_id),
            fields=list_governance_field_permissions(uow, table_id),
        )
    except (Stage06AuthorizationError, PlatformValidationError) as exc:
        raise _http_error(exc) from exc


@router.put(
    "/mini-app/tables/{table_id}/governance/fields/{field_id}/permission-policy",
    response_model=GovernanceFieldPermissionReceipt,
)
def replace_governance_field_permission_policy(
    table_id: UUID,
    field_id: UUID,
    request: GovernanceFieldPermissionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> GovernanceFieldPermissionReceipt:
    try:
        workspace_id = workspace_id_for_table(uow, table_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "field.permission.manage",
        )
        return _execute_idempotent(
            uow,
            workspace_id=workspace_id,
            operation="stage07.governance.field_permission_policy_replace",
            idempotency_key=idempotency_key,
            payload={
                "table_id": str(table_id),
                "field_id": str(field_id),
                "expected_permission_version": request.expected_permission_version,
                "policy": request.policy,
            },
            response_model=GovernanceFieldPermissionReceipt,
            build=lambda: _field_permission_receipt(
                replace_field_permission_policy(
                    uow,
                    table_id,
                    field_id,
                    policy=request.policy,
                    expected_permission_version=request.expected_permission_version,
                    actor=actor,
                )
            ),
        )
    except (Stage06AuthorizationError, PlatformValidationError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _http_error(exc) from exc


def _member_role_receipt(member: object) -> GovernanceMemberRoleReceipt:
    return GovernanceMemberRoleReceipt(
        id=str(member.id),
        user_id=member.user_id,
        role=member.role,
        status=member.status,
        version=member.version or 1,
    )


def _field_permission_receipt(field: object) -> GovernanceFieldPermissionReceipt:
    return GovernanceFieldPermissionReceipt(
        id=str(field.id),
        key=field.key,
        policy=governance_field_permission_policy(field),
        permission_version=field.permission_version or 1,
    )


def _execute_idempotent(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    operation: str,
    idempotency_key: str,
    payload: dict[str, object],
    response_model: type[ResponseModel],
    build: Callable[[], ResponseModel],
) -> ResponseModel:
    fingerprint = fingerprint_request(payload)
    try:
        decision = begin_idempotent_operation(
            uow,
            workspace_id=workspace_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            trace_id=idempotency_trace_id(operation, fingerprint, idempotency_key),
        )
        if decision.status == "replay":
            if decision.response_ref is None:
                raise PlatformValidationError("idempotency_in_progress", operation)
            return response_model(**decision.response_ref)
        result = build()
        complete_idempotent_operation(decision.record, response_ref=result.model_dump())
        _commit_if_sqlalchemy(uow)
        return result
    except IntegrityError as exc:
        _rollback_if_sqlalchemy(uow)
        raise PlatformValidationError("idempotency_in_progress", operation) from exc
    except PlatformValidationError:
        _rollback_if_sqlalchemy(uow)
        raise


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    if isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        uow.session.commit()


def _rollback_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    if isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        uow.session.rollback()


def _http_error(
    exc: Stage06AuthorizationError | Stage06PaginationError | PlatformValidationError,
) -> HTTPException:
    if isinstance(exc, Stage06AuthorizationError):
        status_code = 404 if exc.code.endswith("_not_found") else 403
    elif isinstance(exc, Stage06PaginationError):
        status_code = 422
    elif exc.code.endswith("_not_found"):
        status_code = 404
    elif exc.code in {"idempotency_conflict", "idempotency_in_progress", "governance_revision_conflict"}:
        status_code = 409
    elif exc.code in {"permission_denied", "governance_field_policy_forbidden"}:
        status_code = 403
    else:
        status_code = 422
    return HTTPException(status_code=status_code, detail=error_detail(exc.code, exc.code))
