from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.schemas.stage07_digital_employee_management import (
    ManagedEmployeeContextBaseResponse,
    ManagedEmployeeContextMemberResponse,
    ManagedEmployeeContextTableResponse,
    ManagedEmployeeContextViewResponse,
    ManagedEmployeeCreateRequest,
    ManagedEmployeeDetailResponse,
    ManagedEmployeeDirectoryResponse,
    ManagedEmployeeLifecycleReceipt,
    ManagedEmployeeLifecycleRequest,
    ManagedEmployeeManagementContextResponse,
    ManagedEmployeeMemberGrantRequest,
    ManagedEmployeeSummaryResponse,
    ManagedEmployeeUpdateRequest,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
    workspace_id_for_base,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_pagination import Stage06PaginationError, paginate_items
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    list_tables_for_base,
    list_views_for_base,
)
from app.services.stage07_digital_employee_management import (
    ManagedEmployeeCreateCommand,
    ManagedEmployeeUpdateCommand,
    activate_managed_employee,
    create_managed_employee,
    pause_managed_employee,
    replace_managed_employee_grants,
    update_managed_employee,
)


router = APIRouter(tags=["stage07-digital-employee-management"])
_SAFE_VIEW_TYPES = frozenset({"grid", "kanban", "calendar", "form"})
_CONFLICT_CODES = frozenset(
    {
        "digital_employee_revision_conflict",
        "digital_employee_alias_conflict",
        "digital_employee_active_requires_pause",
        "idempotency_conflict",
        "idempotency_in_progress",
    }
)
_NOT_FOUND_CODES = frozenset(
    {
        "base_not_found",
        "digital_employee_not_found",
    }
)


@router.get(
    "/mini-app/bases/{base_id}/digital-employee-management-context",
    response_model=ManagedEmployeeManagementContextResponse,
)
def get_digital_employee_management_context(
    base_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ManagedEmployeeManagementContextResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        actor = _authorize_management_context(uow, identity, workspace_id)
        base = uow.get_base(base_id)
        if base is None or base.status != "active":
            raise PlatformValidationError("base_not_found", str(base_id))
        tables = list_tables_for_base(uow, base.id)
        views = list_views_for_base(uow, base.id, actor=actor)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _management_error(exc) from exc
    members = [
        member
        for member in uow.list_workspace_members(workspace_id)
        if member.status == "active" and member.role in {"owner", "admin", "builder", "operator", "viewer"}
    ]
    return ManagedEmployeeManagementContextResponse(
        base=ManagedEmployeeContextBaseResponse(id=str(base.id), name=base.name),
        tables=[
            ManagedEmployeeContextTableResponse(id=str(table.id), name=table.name)
            for table in sorted(tables, key=lambda item: (item.name.casefold(), str(item.id)))
        ],
        views=[
            ManagedEmployeeContextViewResponse(
                id=str(view.id),
                table_id=str(view.table_id),
                name=view.name,
                view_type=view.view_type,
            )
            for view in sorted(views, key=lambda item: (item.name.casefold(), str(item.id)))
            if view.table_id is not None and view.view_type in _SAFE_VIEW_TYPES
        ],
        members=[
            ManagedEmployeeContextMemberResponse(
                id=str(member.id),
                label=_safe_member_label(member.id),
                role=member.role,
            )
            for member in sorted(members, key=lambda item: str(item.id))
        ],
    )


@router.get(
    "/mini-app/bases/{base_id}/digital-employees/management",
    response_model=ManagedEmployeeDirectoryResponse,
)
def list_managed_digital_employees(
    base_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ManagedEmployeeDirectoryResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(uow, identity, workspace_id, "digital_employee.update")
        base = uow.get_base(base_id)
        if base is None or base.status != "active":
            raise PlatformValidationError("base_not_found", str(base_id))
        employees = [
            employee
            for employee in uow.list_digital_employees(base.id)
            if employee.workspace_id == workspace_id
        ]
        page = paginate_items(employees, limit=limit, cursor=cursor)
    except (PlatformValidationError, Stage06AuthorizationError, Stage06PaginationError) as exc:
        raise _management_error(exc) from exc
    return ManagedEmployeeDirectoryResponse(
        base_id=str(base.id),
        employees=[_managed_employee_summary(uow, employee) for employee in page.items],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.post(
    "/mini-app/bases/{base_id}/digital-employees/management",
    response_model=ManagedEmployeeDetailResponse,
)
def create_managed_digital_employee(
    base_id: UUID,
    request: ManagedEmployeeCreateRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=160,
    ),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ManagedEmployeeDetailResponse:
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail=error_detail("idempotency_key_required", "idempotency_key_required"),
        )
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "digital_employee.create")
        employee = create_managed_employee(
            uow,
            base_id,
            actor=actor,
            command=ManagedEmployeeCreateCommand(
                name=request.name,
                description=request.description,
                telegram_alias=request.telegram_alias,
            ),
            idempotency_key=idempotency_key,
        )
        _commit_if_sqlalchemy(uow)
    except (PlatformValidationError, Stage06AuthorizationError, IntegrityError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _management_error(exc) from exc
    return _managed_employee_detail(uow, employee)


@router.get(
    "/mini-app/digital-employees/{employee_id}/management",
    response_model=ManagedEmployeeDetailResponse,
)
def get_managed_digital_employee(
    employee_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ManagedEmployeeDetailResponse:
    try:
        employee = _managed_employee_with_update_authority(uow, employee_id, identity)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _management_error(exc) from exc
    return _managed_employee_detail(uow, employee)


@router.patch(
    "/mini-app/digital-employees/{employee_id}/management",
    response_model=ManagedEmployeeDetailResponse,
)
def update_managed_digital_employee(
    employee_id: UUID,
    request: ManagedEmployeeUpdateRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ManagedEmployeeDetailResponse:
    try:
        employee = _managed_employee_with_update_authority(uow, employee_id, identity)
        actor = authorize_workspace_action(
            uow,
            identity,
            employee.workspace_id,
            "digital_employee.update",
        )
        command = _update_command(request)
        employee = update_managed_employee(
            uow,
            employee.id,
            actor=actor,
            command=command,
            expected_version=request.expected_version,
        )
        _commit_if_sqlalchemy(uow)
    except (PlatformValidationError, Stage06AuthorizationError, IntegrityError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _management_error(exc) from exc
    return _managed_employee_detail(uow, employee)


@router.put(
    "/mini-app/digital-employees/{employee_id}/member-grants",
    response_model=ManagedEmployeeDetailResponse,
)
def replace_managed_digital_employee_grants(
    employee_id: UUID,
    request: ManagedEmployeeMemberGrantRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=160,
    ),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ManagedEmployeeDetailResponse:
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail=error_detail("idempotency_key_required", "idempotency_key_required"),
        )
    try:
        employee = _managed_employee_with_update_authority(uow, employee_id, identity)
        actor = authorize_workspace_action(
            uow,
            identity,
            employee.workspace_id,
            "digital_employee.update",
        )
        employee = replace_managed_employee_grants(
            uow,
            employee.id,
            actor=actor,
            member_ids=list(request.member_ids),
            expected_version=request.expected_version,
            idempotency_key=idempotency_key,
        )
        _commit_if_sqlalchemy(uow)
    except (PlatformValidationError, Stage06AuthorizationError, IntegrityError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _management_error(exc) from exc
    return _managed_employee_detail(uow, employee)


@router.post(
    "/mini-app/digital-employees/{employee_id}/activate",
    response_model=ManagedEmployeeLifecycleReceipt,
)
def activate_managed_digital_employee(
    employee_id: UUID,
    request: ManagedEmployeeLifecycleRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=160,
    ),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ManagedEmployeeLifecycleReceipt:
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail=error_detail("idempotency_key_required", "idempotency_key_required"),
        )
    try:
        employee = _managed_employee_with_update_authority(uow, employee_id, identity)
        actor = authorize_workspace_action(
            uow,
            identity,
            employee.workspace_id,
            "digital_employee.update",
        )
        receipt = activate_managed_employee(
            uow,
            employee.id,
            actor=actor,
            expected_version=request.expected_version,
            idempotency_key=idempotency_key,
        )
        _commit_if_sqlalchemy(uow)
    except (PlatformValidationError, Stage06AuthorizationError, IntegrityError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _management_error(exc) from exc
    return ManagedEmployeeLifecycleReceipt(
        id=str(receipt.id),
        status=receipt.status,
        version=receipt.version,
        audit_event_id=str(receipt.audit_event_id),
    )


@router.post(
    "/mini-app/digital-employees/{employee_id}/pause",
    response_model=ManagedEmployeeLifecycleReceipt,
)
def pause_managed_digital_employee(
    employee_id: UUID,
    request: ManagedEmployeeLifecycleRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=160,
    ),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ManagedEmployeeLifecycleReceipt:
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail=error_detail("idempotency_key_required", "idempotency_key_required"),
        )
    try:
        employee = _managed_employee_with_update_authority(uow, employee_id, identity)
        actor = authorize_workspace_action(
            uow,
            identity,
            employee.workspace_id,
            "digital_employee.update",
        )
        receipt = pause_managed_employee(
            uow,
            employee.id,
            actor=actor,
            expected_version=request.expected_version,
            idempotency_key=idempotency_key,
        )
        _commit_if_sqlalchemy(uow)
    except (PlatformValidationError, Stage06AuthorizationError, IntegrityError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _management_error(exc) from exc
    return ManagedEmployeeLifecycleReceipt(
        id=str(receipt.id),
        status=receipt.status,
        version=receipt.version,
        audit_event_id=str(receipt.audit_event_id),
    )


def _authorize_management_context(
    uow: Stage06PlatformUnitOfWork,
    identity: Stage06RequestIdentity,
    workspace_id: UUID,
):
    try:
        return authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.create",
        )
    except Stage06AuthorizationError as create_error:
        if create_error.code.endswith("_not_found"):
            raise
        return authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.update",
        )


def _managed_employee_with_update_authority(
    uow: Stage06PlatformUnitOfWork,
    employee_id: UUID,
    identity: Stage06RequestIdentity,
):
    employee = uow.get_digital_employee(employee_id)
    if employee is None:
        raise PlatformValidationError("digital_employee_not_found", str(employee_id))
    authorize_workspace_action(
        uow,
        identity,
        employee.workspace_id,
        "digital_employee.update",
    )
    return employee


def _update_command(request: ManagedEmployeeUpdateRequest) -> ManagedEmployeeUpdateCommand:
    values: dict[str, object] = {
        "name": request.name,
        "description": request.description,
        "accessible_table_ids": request.accessible_table_ids,
        "accessible_view_ids": request.accessible_view_ids,
        "allowed_actions": request.allowed_actions,
        "access_mode": request.access_mode,
    }
    if "telegram_alias" in request.model_fields_set:
        values["telegram_alias"] = request.telegram_alias
    return ManagedEmployeeUpdateCommand(**values)


def _managed_employee_summary(
    uow: Stage06PlatformUnitOfWork,
    employee,
) -> ManagedEmployeeSummaryResponse:
    return ManagedEmployeeSummaryResponse(
        id=str(employee.id),
        name=employee.name,
        description=employee.description,
        status=employee.status,
        access_mode=employee.access_mode,
        table_count=len(employee.accessible_tables),
        view_count=len(employee.accessible_views),
        member_count=len(uow.list_digital_employee_member_grants(employee.id)),
        version=employee.version,
    )


def _managed_employee_detail(
    uow: Stage06PlatformUnitOfWork,
    employee,
) -> ManagedEmployeeDetailResponse:
    summary = _managed_employee_summary(uow, employee)
    return ManagedEmployeeDetailResponse(
        **summary.model_dump(),
        base_id=str(employee.base_id),
        telegram_alias=employee.telegram_alias,
        accessible_table_ids=sorted(str(item) for item in employee.accessible_tables),
        accessible_view_ids=sorted(str(item) for item in employee.accessible_views),
        allowed_actions=sorted(employee.allowed_actions),
        member_ids=sorted(
            str(grant.workspace_member_id)
            for grant in uow.list_digital_employee_member_grants(employee.id)
        ),
    )


def _safe_member_label(member_id: UUID) -> str:
    return f"成员 {str(member_id)[:8]}"


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _rollback_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.rollback()


def _management_error(
    exc: Exception,
) -> HTTPException:
    if isinstance(exc, IntegrityError):
        return HTTPException(
            status_code=409,
            detail=error_detail("digital_employee_alias_conflict", "digital_employee_alias_conflict"),
        )
    if isinstance(exc, Stage06PaginationError):
        return HTTPException(
            status_code=422,
            detail=error_detail("digital_employee_management_invalid_cursor", "digital_employee_management_invalid_cursor"),
        )
    if isinstance(exc, Stage06AuthorizationError):
        return HTTPException(
            status_code=404 if exc.code.endswith("_not_found") else 403,
            detail=error_detail(exc.code, exc.code),
        )
    if isinstance(exc, PlatformValidationError):
        if exc.code in _NOT_FOUND_CODES:
            status_code = 404
        elif exc.code in _CONFLICT_CODES:
            status_code = 409
        else:
            status_code = 422
        return HTTPException(
            status_code=status_code,
            detail=error_detail(exc.code, exc.code),
        )
    return HTTPException(
        status_code=500,
        detail=error_detail("digital_employee_management_failed", "digital_employee_management_failed"),
    )
