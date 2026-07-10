from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_stage06_request_identity
from app.core.database import get_session
from app.core.errors import error_detail
from app.schemas.stage06_platform import (
    BaseResponse,
    CreateBaseRequest,
    CreateFieldRequest,
    CreateRecordRequest,
    CreateTableRequest,
    CreateViewRequest,
    CreateWorkspaceRequest,
    FieldResponse,
    MiniAppBootstrapResponse,
    MiniAppWorkspaceHomeResponse,
    RecordResponse,
    TableResponse,
    TableSchemaResponse,
    UpdateRecordRequest,
    ViewResponse,
    ViewRecordsResponse,
    WorkspaceMemberListResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    actor_for_workspace_bootstrap,
    authorize_workspace_action,
    workspace_id_for_base,
    workspace_id_for_record,
    workspace_id_for_table,
    workspace_id_for_view,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_pagination import Stage06PaginationError
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    Stage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    create_form_view,
    get_table_schema,
    list_workspace_members,
    list_view_records,
    read_base,
    read_workspace,
    update_record,
)
from app.services.stage07_mini_app import get_mini_app_bootstrap, get_workspace_home

router = APIRouter(tags=["stage06-platform"])


def get_stage06_platform_uow(
    session: Session = Depends(get_session),
) -> Stage06PlatformUnitOfWork:
    return SqlAlchemyStage06PlatformUnitOfWork(session)


@router.get("/mini-app/bootstrap", response_model=MiniAppBootstrapResponse)
def mini_app_bootstrap_endpoint(
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> MiniAppBootstrapResponse:
    return MiniAppBootstrapResponse(**get_mini_app_bootstrap(uow, identity))


@router.get(
    "/workspaces/{workspace_id}/home",
    response_model=MiniAppWorkspaceHomeResponse,
)
def get_workspace_home_endpoint(
    workspace_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> MiniAppWorkspaceHomeResponse:
    try:
        return MiniAppWorkspaceHomeResponse(
            **get_workspace_home(uow, identity, workspace_id)
        )
    except Stage06AuthorizationError as exc:
        raise _http_error(exc) from exc


@router.post("/workspaces", response_model=WorkspaceResponse)
def create_workspace_endpoint(
    request: CreateWorkspaceRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> WorkspaceResponse:
    if request.owner_user_id != identity.user_id:
        raise HTTPException(
            status_code=403,
            detail=error_detail(
                "workspace_owner_mismatch",
                "Workspace owner must match the authenticated identity",
            ),
        )
    workspace = create_workspace(
        uow,
        name=request.name,
        owner_user_id=identity.user_id,
        actor=actor_for_workspace_bootstrap(identity),
    )
    _commit_if_sqlalchemy(uow)
    return WorkspaceResponse(
        id=str(workspace.id),
        name=workspace.name,
        slug=workspace.slug,
        owner_user_id=workspace.owner_user_id,
        status=workspace.status,
    )


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def read_workspace_endpoint(
    workspace_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> WorkspaceResponse:
    try:
        authorize_workspace_action(uow, identity, workspace_id, "workspace.read")
        workspace = read_workspace(uow, workspace_id)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return WorkspaceResponse(
        id=str(workspace.id),
        name=workspace.name,
        slug=workspace.slug,
        owner_user_id=workspace.owner_user_id,
        status=workspace.status,
    )


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMemberListResponse,
)
def list_workspace_members_endpoint(
    workspace_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> WorkspaceMemberListResponse:
    try:
        authorize_workspace_action(uow, identity, workspace_id, "member.read")
        members = list_workspace_members(uow, workspace_id)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return WorkspaceMemberListResponse(
        members=[
            WorkspaceMemberResponse(
                id=str(member.id),
                workspace_id=str(member.workspace_id),
                user_id=member.user_id,
                role=member.role,
                status=member.status,
            )
            for member in members
        ]
    )


@router.post("/workspaces/{workspace_id}/bases", response_model=BaseResponse)
def create_base_endpoint(
    workspace_id: UUID,
    request: CreateBaseRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> BaseResponse:
    try:
        actor = authorize_workspace_action(uow, identity, workspace_id, "base.create")
        base = create_base(
            uow,
            workspace_id,
            name=request.name,
            description=request.description,
            actor=actor,
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return BaseResponse(
        id=str(base.id),
        workspace_id=str(base.workspace_id),
        name=base.name,
        description=base.description,
        source_type=base.source_type,
        status=base.status,
    )


@router.get("/bases/{base_id}", response_model=BaseResponse)
def read_base_endpoint(
    base_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> BaseResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(uow, identity, workspace_id, "base.read")
        base = read_base(uow, base_id)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return BaseResponse(
        id=str(base.id),
        workspace_id=str(base.workspace_id),
        name=base.name,
        description=base.description,
        source_type=base.source_type,
        status=base.status,
    )


@router.post("/bases/{base_id}/tables", response_model=TableResponse)
def create_table_endpoint(
    base_id: UUID,
    request: CreateTableRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> TableResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "table.create")
        table = create_table(
            uow,
            base_id,
            name=request.name,
            key=request.key,
            actor=actor,
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return TableResponse(
        id=str(table.id),
        base_id=str(table.base_id),
        name=table.name,
        key=table.key,
        status=table.status,
    )


@router.post("/bases/{base_id}/views", response_model=ViewResponse)
def create_view_endpoint(
    base_id: UUID,
    request: CreateViewRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ViewResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "view.manage")
        view = create_form_view(
            uow,
            base_id,
            UUID(request.table_id),
            name=request.name,
            view_type=request.view_type,
            config=request.config,
            permission_policy=request.permission_policy,
            actor=actor,
        )
    except (PlatformValidationError, Stage06AuthorizationError, ValueError) as exc:
        if isinstance(exc, PlatformValidationError):
            raise _http_error(exc) from exc
        if isinstance(exc, Stage06AuthorizationError):
            raise _http_error(exc) from exc
        raise HTTPException(
            status_code=422,
            detail=error_detail("invalid_uuid", str(exc)),
        ) from exc
    _commit_if_sqlalchemy(uow)
    return ViewResponse(
        id=str(view.id),
        base_id=str(view.base_id),
        table_id=None if view.table_id is None else str(view.table_id),
        name=view.name,
        view_type=view.view_type,
        config=view.config,
        permission_policy=view.permission_policy,
        status=view.status,
    )


@router.post("/tables/{table_id}/fields", response_model=FieldResponse)
def create_field_endpoint(
    table_id: UUID,
    request: CreateFieldRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> FieldResponse:
    try:
        workspace_id = workspace_id_for_table(uow, table_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "field.manage")
        field = create_field(
            uow,
            table_id,
            name=request.name,
            key=request.key,
            field_type=request.field_type,
            required=request.required,
            options=request.options,
            permission_policy=request.permission_policy,
            actor=actor,
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return FieldResponse(
        id=str(field.id),
        table_id=str(field.table_id),
        name=field.name,
        key=field.key,
        field_type=field.field_type,
        required=field.required,
        options=field.options,
        permission_policy=field.permission_policy,
        order_index=field.order_index,
    )


@router.post("/tables/{table_id}/records", response_model=RecordResponse)
def create_record_endpoint(
    table_id: UUID,
    request: CreateRecordRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> RecordResponse:
    try:
        workspace_id = workspace_id_for_table(uow, table_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "record.create")
        record = create_record(uow, table_id, values=request.values, actor=actor)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return RecordResponse(
        id=str(record.id),
        table_id=str(record.table_id),
        values=record.values,
        record_status=record.record_status,
        version=record.version,
    )


@router.patch("/records/{record_id}", response_model=RecordResponse)
def update_record_endpoint(
    record_id: UUID,
    request: UpdateRecordRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> RecordResponse:
    try:
        workspace_id = workspace_id_for_record(uow, record_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "record.update")
        record = update_record(
            uow,
            record_id,
            values=request.values,
            expected_version=request.expected_version,
            actor=actor,
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        _commit_if_sqlalchemy(uow)
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return RecordResponse(
        id=str(record.id),
        table_id=str(record.table_id),
        values=record.values,
        record_status=record.record_status,
        version=record.version,
    )


@router.get("/tables/{table_id}/schema", response_model=TableSchemaResponse)
def get_table_schema_endpoint(
    table_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> TableSchemaResponse:
    try:
        workspace_id = workspace_id_for_table(uow, table_id)
        authorize_workspace_action(uow, identity, workspace_id, "table.read")
        schema = get_table_schema(uow, table_id)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return TableSchemaResponse(**schema)


@router.get("/views/{view_id:uuid}/records", response_model=ViewRecordsResponse)
def list_view_records_endpoint(
    view_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ViewRecordsResponse:
    try:
        workspace_id = workspace_id_for_view(uow, view_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "record.read")
        response = list_view_records(
            uow,
            view_id,
            actor=actor,
            limit=limit,
            cursor=cursor,
        )
    except (
        PlatformValidationError,
        Stage06AuthorizationError,
        Stage06PaginationError,
    ) as exc:
        _commit_if_sqlalchemy(uow)
        raise _http_error(exc) from exc
    return ViewRecordsResponse(**response)


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _http_error(
    exc: PlatformValidationError | Stage06AuthorizationError | Stage06PaginationError,
) -> HTTPException:
    if isinstance(exc, Stage06PaginationError):
        return HTTPException(
            status_code=422,
            detail=error_detail(exc.code, str(exc)),
        )
    if isinstance(exc, Stage06AuthorizationError):
        status_code = 404 if exc.code.endswith("_not_found") else 403
        return HTTPException(
            status_code=status_code,
            detail=error_detail(exc.code, str(exc)),
        )
    if exc.code.endswith("_not_found"):
        status_code = 404
    elif exc.code == "permission_denied":
        status_code = 403
    elif exc.code == "record_version_conflict":
        status_code = 409
    else:
        status_code = 422
    return HTTPException(status_code=status_code, detail=error_detail(exc.code, str(exc)))
