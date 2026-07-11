from collections.abc import Callable
from typing import Any, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_stage06_request_identity
from app.core.database import get_session
from app.core.errors import error_detail
from app.schemas.stage06_platform import (
    BaseResponse,
    BaseListResponse,
    BaseSummaryResponse,
    BuilderInitializationResponse,
    CreateBaseRequest,
    CreateFieldRequest,
    CreateFormResponse,
    CreateRecordRequest,
    CreateTableRequest,
    CreateViewRequest,
    CreateWorkspaceRequest,
    FieldResponse,
    FieldInitializationResponse,
    InitializeFieldRequest,
    InitializeLookupFieldRequest,
    InitializeRelationFieldRequest,
    MiniAppBootstrapResponse,
    MiniAppWorkspaceHomeResponse,
    InitializeBaseRequest,
    InitializeTableRequest,
    RecordResponse,
    RecordDetailResponse,
    RelationCandidatePageResponse,
    TableResponse,
    TableListResponse,
    SafeTableFieldResponse,
    TableSchemaResponse,
    UpdateRecordRequest,
    ViewResponse,
    ViewPresentationResponse,
    ViewListResponse,
    ViewSummaryResponse,
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
    get_create_form,
    create_record,
    create_table,
    create_workspace,
    create_form_view,
    get_table_schema,
    get_view_presentation,
    initialize_base,
    initialize_field,
    initialize_relation_field,
    initialize_lookup_field,
    initialize_table,
    list_workspace_members,
    list_bases_for_workspace,
    list_relation_candidates,
    list_tables_for_base,
    list_views_for_base,
    list_view_records,
    read_base,
    read_record_for_actor,
    read_workspace,
    update_record,
    safe_table_schema_field,
    _validated_f1_choices,
)
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
)
from app.services.stage07_mini_app import get_mini_app_bootstrap, get_workspace_home

router = APIRouter(tags=["stage06-platform"])
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


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


@router.post(
    "/workspaces/{workspace_id}/base-initializations",
    response_model=BuilderInitializationResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_base_endpoint(
    workspace_id: UUID,
    request: InitializeBaseRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> BuilderInitializationResponse:
    try:
        base_name = _validated_builder_name(request.base_name, label="base_name")
        table_name = _validated_builder_name(request.table_name, label="table_name")
        actor = authorize_workspace_action(uow, identity, workspace_id, "base.create")
        authorize_workspace_action(uow, identity, workspace_id, "table.create")
        authorize_workspace_action(uow, identity, workspace_id, "view.manage")
        initialization, replayed = _run_atomic_builder_initialization(
            uow,
            workspace_id=workspace_id,
            operation="stage07.base.initialize",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "workspace_id": workspace_id,
                    "operation": "stage07.base.initialize",
                    "actor_user_id": identity.user_id,
                    "base_name": base_name,
                    "table_name": table_name,
                }
            ),
            response_model=BuilderInitializationResponse,
            build=lambda: _builder_initialization_response(
                initialize_base(
                    uow,
                    workspace_id,
                    base_name=base_name,
                    table_name=table_name,
                    actor=actor,
                )
            ),
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return initialization


@router.get("/workspaces/{workspace_id}/bases", response_model=BaseListResponse)
def list_bases_endpoint(
    workspace_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> BaseListResponse:
    try:
        authorize_workspace_action(uow, identity, workspace_id, "base.read")
        bases = list_bases_for_workspace(uow, workspace_id)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return BaseListResponse(
        bases=[
            {
                "id": str(base.id),
                "name": base.name,
                "source_type": base.source_type,
                "status": base.status,
            }
            for base in bases
        ]
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


@router.get("/bases/{base_id}/tables", response_model=TableListResponse)
def list_tables_endpoint(
    base_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> TableListResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(uow, identity, workspace_id, "table.read")
        tables = list_tables_for_base(uow, base_id)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return TableListResponse(
        tables=[
            TableResponse(
                id=str(table.id),
                base_id=str(table.base_id),
                name=table.name,
                key=table.key,
                status=table.status,
            )
            for table in tables
        ]
    )


@router.get("/bases/{base_id}/views", response_model=ViewListResponse)
def list_views_endpoint(
    base_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ViewListResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(uow, identity, workspace_id, "table.read")
        views = list_views_for_base(uow, base_id)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return ViewListResponse(
        views=[
            ViewSummaryResponse(
                id=str(view.id),
                base_id=str(view.base_id),
                table_id=None if view.table_id is None else str(view.table_id),
                name=view.name,
                view_type=view.view_type,
                status=view.status,
            )
            for view in views
        ]
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


@router.post(
    "/bases/{base_id}/table-initializations",
    response_model=BuilderInitializationResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_table_endpoint(
    base_id: UUID,
    request: InitializeTableRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> BuilderInitializationResponse:
    try:
        table_name = _validated_builder_name(request.table_name, label="table_name")
        workspace_id = workspace_id_for_base(uow, base_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "table.create")
        authorize_workspace_action(uow, identity, workspace_id, "view.manage")
        base = read_base(uow, base_id)
        initialization, replayed = _run_atomic_builder_initialization(
            uow,
            workspace_id=workspace_id,
            operation="stage07.table.initialize",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "workspace_id": workspace_id,
                    "operation": "stage07.table.initialize",
                    "actor_user_id": identity.user_id,
                    "base_id": base_id,
                    "table_name": table_name,
                }
            ),
            response_model=BuilderInitializationResponse,
            build=lambda: _builder_initialization_response(
                initialize_table(
                    uow,
                    base_id,
                    table_name=table_name,
                    actor=actor,
                ),
                base=base,
            ),
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return initialization


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


@router.post(
    "/tables/{table_id}/field-initializations",
    response_model=FieldInitializationResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_field_endpoint(
    table_id: UUID,
    request: InitializeFieldRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> FieldInitializationResponse:
    try:
        workspace_id = workspace_id_for_table(uow, table_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "field.manage")
        name = _validated_field_name(request.name)
        choices = _validated_f1_choices(request.field_type, request.choices)
        initialization, replayed = _run_atomic_builder_initialization(
            uow,
            workspace_id=workspace_id,
            operation="stage07.field.initialize",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "workspace_id": workspace_id,
                    "operation": "stage07.field.initialize",
                    "actor_user_id": identity.user_id,
                    "table_id": table_id,
                    "name": name,
                    "field_type": request.field_type,
                    "required": request.required,
                    "choices": choices,
                }
            ),
            response_model=FieldInitializationResponse,
            build=lambda: _field_initialization_response(
                initialize_field(
                    uow,
                    table_id,
                    name=name,
                    field_type=request.field_type,
                    required=request.required,
                    choices=choices,
                    actor=actor,
                )
            ),
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return initialization


@router.post(
    "/tables/{table_id}/relation-field-initializations",
    response_model=FieldInitializationResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_relation_field_endpoint(
    table_id: UUID,
    request: InitializeRelationFieldRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> FieldInitializationResponse:
    try:
        workspace_id = workspace_id_for_table(uow, table_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "field.manage")
        name = _validated_field_name(request.name)
        try:
            target_table_id = UUID(request.target_table_id)
        except (TypeError, ValueError) as exc:
            raise PlatformValidationError("table_not_found", "target_table") from exc
        target_workspace_id = workspace_id_for_table(uow, target_table_id)
        authorize_workspace_action(uow, identity, target_workspace_id, "table.read")
        initialization, replayed = _run_atomic_builder_initialization(
            uow,
            workspace_id=workspace_id,
            operation="stage07.relation_field.initialize",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "workspace_id": workspace_id,
                    "operation": "stage07.relation_field.initialize",
                    "actor_user_id": identity.user_id,
                    "table_id": table_id,
                    "name": name,
                    "target_table_id": target_table_id,
                    "required": request.required,
                }
            ),
            response_model=FieldInitializationResponse,
            build=lambda: _field_initialization_response(
                initialize_relation_field(
                    uow,
                    table_id,
                    name=name,
                    target_table_id=target_table_id,
                    required=request.required,
                    actor=actor,
                )
            ),
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return initialization


@router.post(
    "/tables/{table_id}/lookup-field-initializations",
    response_model=FieldInitializationResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_lookup_field_endpoint(
    table_id: UUID,
    request: InitializeLookupFieldRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> FieldInitializationResponse:
    try:
        workspace_id = workspace_id_for_table(uow, table_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "field.manage")
        authorize_workspace_action(uow, identity, workspace_id, "table.read")
        name = _validated_field_name(request.name)
        try:
            source_relation_field_id = UUID(request.source_relation_field_id)
            target_field_id = UUID(request.target_field_id)
        except (TypeError, ValueError) as exc:
            raise PlatformValidationError("lookup_target_incompatible", "field") from exc
        initialization, replayed = _run_atomic_builder_initialization(
            uow,
            workspace_id=workspace_id,
            operation="stage07.lookup_field.initialize",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "workspace_id": workspace_id,
                    "operation": "stage07.lookup_field.initialize",
                    "actor_user_id": identity.user_id,
                    "table_id": table_id,
                    "name": name,
                    "source_relation_field_id": source_relation_field_id,
                    "target_field_id": target_field_id,
                    "aggregation": request.aggregation,
                }
            ),
            response_model=FieldInitializationResponse,
            build=lambda: _field_initialization_response(
                initialize_lookup_field(
                    uow,
                    table_id,
                    name=name,
                    source_relation_field_id=source_relation_field_id,
                    target_field_id=target_field_id,
                    aggregation=request.aggregation,
                    actor=actor,
                )
            ),
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return initialization


@router.get(
    "/fields/{field_id}/relation-candidates",
    response_model=RelationCandidatePageResponse,
)
def list_relation_candidates_endpoint(
    field_id: UUID,
    q: str | None = Query(default=None, max_length=160),
    cursor: str | None = Query(default=None, max_length=512),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> RelationCandidatePageResponse:
    try:
        field = uow.get_field(field_id)
        if field is None:
            raise PlatformValidationError("field_not_found", "field")
        workspace_id = workspace_id_for_table(uow, field.table_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "record.read")
        page = list_relation_candidates(
            uow,
            field_id,
            actor=actor,
            query=q,
            cursor=cursor,
            limit=50,
        )
    except (
        PlatformValidationError,
        Stage06AuthorizationError,
        Stage06PaginationError,
    ) as exc:
        raise _http_error(exc) from exc
    return RelationCandidatePageResponse(**page)


@router.get("/tables/{table_id}/create-form", response_model=CreateFormResponse)
def get_create_form_endpoint(
    table_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> CreateFormResponse:
    try:
        workspace_id = workspace_id_for_table(uow, table_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "record.create")
        form = get_create_form(uow, table_id, actor=actor)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return CreateFormResponse(**form)


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
        actor = authorize_workspace_action(uow, identity, workspace_id, "table.read")
        schema = get_table_schema(uow, table_id, actor=actor)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return TableSchemaResponse(**schema)


@router.get(
    "/views/{view_id}/presentation",
    response_model=ViewPresentationResponse,
)
def get_view_presentation_endpoint(
    view_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> ViewPresentationResponse:
    try:
        workspace_id = workspace_id_for_view(uow, view_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "record.read")
        presentation = get_view_presentation(uow, view_id, actor=actor)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return ViewPresentationResponse(**presentation)


@router.get("/records/{record_id}", response_model=RecordDetailResponse)
def read_record_detail_endpoint(
    record_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> RecordDetailResponse:
    try:
        workspace_id = workspace_id_for_record(uow, record_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "record.read")
        record = read_record_for_actor(uow, record_id, actor=actor)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return RecordDetailResponse(**record)


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


def _rollback_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> bool:
    session = getattr(uow, "session", None)
    if session is None:
        return False
    session.rollback()
    return True


def _validated_builder_name(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 160:
        raise PlatformValidationError("invalid_builder_name", label)
    return normalized


def _validated_field_name(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 160:
        raise PlatformValidationError("invalid_field_name", "field_name")
    return normalized


def _builder_initialization_response(
    result: Any,
    *,
    base: Any | None = None,
) -> BuilderInitializationResponse:
    base_resource = result.base if hasattr(result, "base") else base
    if base_resource is None:
        raise PlatformValidationError("base_not_found", "builder_initialization")
    return BuilderInitializationResponse(
        base=BaseSummaryResponse(
            id=str(base_resource.id),
            name=base_resource.name,
            source_type=base_resource.source_type,
            status=base_resource.status,
        ),
        table=TableResponse(
            id=str(result.table.id),
            base_id=str(result.table.base_id),
            name=result.table.name,
            key=result.table.key,
            status=result.table.status,
        ),
        default_view=ViewSummaryResponse(
            id=str(result.default_view.id),
            base_id=str(result.default_view.base_id),
            table_id=str(result.default_view.table_id),
            name=result.default_view.name,
            view_type=result.default_view.view_type,
            status=result.default_view.status,
        ),
    )


def _field_initialization_response(result: Any) -> FieldInitializationResponse:
    return FieldInitializationResponse(
        field=SafeTableFieldResponse(**safe_table_schema_field(result.field)),
        affected_view_ids=[str(view_id) for view_id in result.affected_view_ids],
    )


def _run_atomic_builder_initialization(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    operation: str,
    idempotency_key: str,
    request_fingerprint: str,
    response_model: type[ResponseModel],
    build: Callable[[], ResponseModel],
) -> tuple[ResponseModel, bool]:
    trace_id = f"idempotency:{operation}:{request_fingerprint[:24]}"
    for attempt in range(2):
        try:
            decision = begin_idempotent_operation(
                uow,
                workspace_id=workspace_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                trace_id=trace_id,
            )
            if decision.status == "replay":
                if decision.response_ref is None:
                    raise PlatformValidationError("idempotency_in_progress", operation)
                return response_model(**decision.response_ref), True
            initialization = build()
            complete_idempotent_operation(
                decision.record,
                response_ref=initialization.model_dump(),
            )
            _commit_if_sqlalchemy(uow)
            return initialization, False
        except IntegrityError as exc:
            if not _rollback_if_sqlalchemy(uow) or attempt == 1:
                raise PlatformValidationError("idempotency_in_progress", operation) from exc
        except PlatformValidationError:
            _rollback_if_sqlalchemy(uow)
            raise
        except Exception:
            _rollback_if_sqlalchemy(uow)
            raise
    raise PlatformValidationError("idempotency_in_progress", operation)


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
    elif exc.code in {
        "record_version_conflict",
        "idempotency_conflict",
        "idempotency_in_progress",
    }:
        status_code = 409
    else:
        status_code = 422
    return HTTPException(status_code=status_code, detail=error_detail(exc.code, str(exc)))
