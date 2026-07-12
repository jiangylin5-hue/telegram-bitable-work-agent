from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_stage06_request_identity
from app.core.database import get_session
from app.core.config import Settings, get_settings
from app.core.errors import error_detail
from app.schemas.stage06_runtime import (
    AuditEventListResponse,
    AuditEventResponse,
    BindTelegramContextRequest,
    CreateDigitalEmployeeRequest,
    CreateNotificationRequest,
    DigitalEmployeeResponse,
    InvokeDigitalEmployeeRequest,
    InvokeDigitalEmployeeResponse,
    NotificationRequestListResponse,
    NotificationRequestResponse,
    RecordChangeDraftListResponse,
    RecordChangeDraftResponse,
    TelegramBindingResponse,
    TelegramMentionRequest,
    UpdateDigitalEmployeeRequest,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
    workspace_id_for_base,
    workspace_id_for_draft,
    workspace_id_for_employee,
    workspace_id_for_notification,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_audit import sanitize_stage06_audit_state
from app.services.stage06_pagination import (
    Stage06PaginationError,
    paginate_items,
)
from app.services.stage06_digital_employees import (
    Stage06RuntimeUnitOfWork,
    bind_telegram_context,
    confirm_notification_request,
    confirm_record_change_draft,
    create_digital_employee,
    create_notification_request,
    invoke_digital_employee,
    list_notification_requests,
    list_base_audit_events,
    list_record_change_drafts,
    reject_record_change_draft,
    resolve_telegram_mention,
    update_digital_employee,
)
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
)

router = APIRouter(tags=["stage06-runtime"])


class SqlAlchemyStage06RuntimeUnitOfWork(SqlAlchemyStage06PlatformUnitOfWork):
    pass


def get_stage06_runtime_uow(
    session: Session = Depends(get_session),
) -> Stage06RuntimeUnitOfWork:
    return SqlAlchemyStage06RuntimeUnitOfWork(session)


@router.post("/bases/{base_id}/digital-employees", response_model=DigitalEmployeeResponse)
def create_digital_employee_endpoint(
    base_id: UUID,
    request: CreateDigitalEmployeeRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> DigitalEmployeeResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.create",
        )
        employee = create_digital_employee(
            uow,
            base_id,
            name=request.name,
            description=request.description,
            telegram_alias=request.telegram_alias,
            accessible_tables=request.accessible_tables,
            accessible_views=request.accessible_views,
            allowed_actions=request.allowed_actions,
            actor=actor,
            field_policy=request.field_policy,
            confirmation_policy=request.confirmation_policy,
            response_style=request.response_style,
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _employee_response(employee)


@router.get("/digital-employees/{employee_id}", response_model=DigitalEmployeeResponse)
def read_digital_employee_endpoint(
    employee_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> DigitalEmployeeResponse:
    try:
        workspace_id = workspace_id_for_employee(uow, employee_id)
        authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.read",
        )
        employee = uow.get_digital_employee(employee_id)
        if employee is None:
            raise PlatformValidationError("digital_employee_not_found", str(employee_id))
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return _employee_response(employee)


@router.patch("/digital-employees/{employee_id}", response_model=DigitalEmployeeResponse)
def update_digital_employee_endpoint(
    employee_id: UUID,
    request: UpdateDigitalEmployeeRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> DigitalEmployeeResponse:
    try:
        workspace_id = workspace_id_for_employee(uow, employee_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.update",
        )
        employee = update_digital_employee(
            uow,
            employee_id,
            actor=actor,
            name=request.name,
            description=request.description,
            telegram_alias=request.telegram_alias,
            accessible_tables=request.accessible_tables,
            accessible_views=request.accessible_views,
            allowed_actions=request.allowed_actions,
            field_policy=request.field_policy,
            confirmation_policy=request.confirmation_policy,
            response_style=request.response_style,
            status=request.status,
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _employee_response(employee)


@router.post(
    "/digital-employees/{employee_id}/invoke",
    response_model=InvokeDigitalEmployeeResponse,
)
def invoke_digital_employee_endpoint(
    employee_id: UUID,
    request: InvokeDigitalEmployeeRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> InvokeDigitalEmployeeResponse:
    try:
        workspace_id = workspace_id_for_employee(uow, employee_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.invoke",
        )
        response = invoke_digital_employee(
            uow,
            employee_id,
            action=request.action,
            view_id=_uuid_or_none(request.view_id),
            table_id=_uuid_or_none(request.table_id),
            record_id=_uuid_or_none(request.record_id),
            proposed_values=request.proposed_values,
            runtime_mode=request.runtime_mode,
            prompt=request.prompt,
            actor=actor,
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        _commit_if_sqlalchemy(uow)
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return InvokeDigitalEmployeeResponse(**response)


@router.get(
    "/bases/{base_id}/record-change-drafts",
    response_model=RecordChangeDraftListResponse,
)
def list_record_change_drafts_endpoint(
    base_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> RecordChangeDraftListResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "record_change_draft.read",
        )
    except Stage06AuthorizationError as exc:
        raise _http_error(exc) from exc
    try:
        page = paginate_items(
            list_record_change_drafts(uow, base_id),
            limit=limit,
            cursor=cursor,
        )
    except Stage06PaginationError as exc:
        raise _pagination_http_error(exc) from exc
    return RecordChangeDraftListResponse(
        drafts=[
            _draft_response(draft)
            for draft in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.post(
    "/record-change-drafts/{draft_id}/confirm",
    response_model=RecordChangeDraftResponse,
)
def confirm_record_change_draft_endpoint(
    draft_id: UUID,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> RecordChangeDraftResponse:
    try:
        workspace_id = workspace_id_for_draft(uow, draft_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "record_change_draft.confirm",
        )
        fingerprint = fingerprint_request(
            {
                "draft_id": draft_id,
                "user_id": identity.user_id,
            }
        )
        decision = _begin_and_reserve(
            uow,
            workspace_id=workspace_id,
            operation="record_change_draft.confirm",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        if decision.status == "replay":
            response_ref = decision.response_ref or {}
            draft = uow.get_record_change_draft(UUID(str(response_ref["draft_id"])))
            if draft is None:
                raise PlatformValidationError("record_change_draft_not_found", str(draft_id))
            return _draft_response(draft)
        draft = confirm_record_change_draft(uow, draft_id, actor=actor)
        complete_idempotent_operation(
            decision.record,
            response_ref={"draft_id": str(draft.id)},
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        _commit_if_sqlalchemy(uow)
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _draft_response(draft)


@router.post(
    "/record-change-drafts/{draft_id}/reject",
    response_model=RecordChangeDraftResponse,
)
def reject_record_change_draft_endpoint(
    draft_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> RecordChangeDraftResponse:
    try:
        workspace_id = workspace_id_for_draft(uow, draft_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "record_change_draft.reject",
        )
        draft = reject_record_change_draft(uow, draft_id, actor=actor)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        _commit_if_sqlalchemy(uow)
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _draft_response(draft)


@router.post(
    "/workspaces/{workspace_id}/telegram-bindings",
    response_model=TelegramBindingResponse,
)
def bind_telegram_context_endpoint(
    workspace_id: UUID,
    request: BindTelegramContextRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> TelegramBindingResponse:
    try:
        authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "telegram_binding.manage",
        )
    except Stage06AuthorizationError as exc:
        raise _http_error(exc) from exc
    try:
        binding = bind_telegram_context(
            uow,
            workspace_id,
            workspace_member_id=UUID(request.workspace_member_id),
            telegram_chat_id=request.telegram_chat_id,
            telegram_user_id=request.telegram_user_id,
            binding_type=request.binding_type,
            default_base_id=_uuid_or_none(request.default_base_id),
            default_digital_employee_id=_uuid_or_none(request.default_digital_employee_id),
            scope_policy=request.scope_policy,
        )
    except (PlatformValidationError, ValueError) as exc:
        if isinstance(exc, ValueError) and not isinstance(exc, PlatformValidationError):
            raise HTTPException(
                status_code=422,
                detail=error_detail("invalid_uuid", str(exc)),
            ) from exc
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return TelegramBindingResponse(
        id=str(binding.id),
        workspace_id=str(binding.workspace_id),
        workspace_member_id=str(binding.workspace_member_id),
        telegram_chat_id=binding.telegram_chat_id,
        telegram_user_id=binding.telegram_user_id,
        binding_type=binding.binding_type,
        default_base_id=(
            None if binding.default_base_id is None else str(binding.default_base_id)
        ),
        default_digital_employee_id=(
            None
            if binding.default_digital_employee_id is None
            else str(binding.default_digital_employee_id)
        ),
        scope_policy=binding.scope_policy,
        status=binding.status,
    )


@router.post("/telegram/mentions", response_model=InvokeDigitalEmployeeResponse)
def resolve_telegram_mention_endpoint(
    request: TelegramMentionRequest,
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> InvokeDigitalEmployeeResponse:
    try:
        response = resolve_telegram_mention(
            uow,
            telegram_chat_id=request.telegram_chat_id,
            telegram_user_id=request.telegram_user_id,
            alias=request.alias,
            text=request.text,
        )
    except PlatformValidationError as exc:
        _commit_if_sqlalchemy(uow)
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return InvokeDigitalEmployeeResponse(**response)


@router.post("/notification-requests", response_model=NotificationRequestResponse)
def create_notification_request_endpoint(
    request: CreateNotificationRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    settings: Settings = Depends(get_settings),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> NotificationRequestResponse:
    try:
        workspace_id = UUID(request.workspace_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "notification_request.create",
        )
        fingerprint = fingerprint_request(
            {
                "request": request.model_dump(),
                "user_id": identity.user_id,
            }
        )
        decision = _begin_and_reserve(
            uow,
            workspace_id=workspace_id,
            operation="notification_request.create",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        if decision.status == "replay":
            response_ref = decision.response_ref or {}
            notification = uow.get_notification_request(
                UUID(str(response_ref["notification_request_id"]))
            )
            if notification is None:
                raise PlatformValidationError(
                    "notification_request_not_found",
                    str(response_ref.get("notification_request_id")),
                )
            return _notification_response(notification)
        notification = create_notification_request(
            uow,
            workspace_id=workspace_id,
            base_id=_uuid_or_none(request.base_id),
            source_record_id=_uuid_or_none(request.source_record_id),
            channel=request.channel,
            target=request.target,
            message_payload=request.message_payload,
            send_policy=request.send_policy,
            actor=actor,
            server_mode=settings.stage06_notification_mode,
            server_allowlist=settings.stage06_notification_allowed_chat_ids,
        )
        complete_idempotent_operation(
            decision.record,
            response_ref={"notification_request_id": str(notification.id)},
        )
    except (PlatformValidationError, Stage06AuthorizationError, ValueError) as exc:
        if isinstance(exc, ValueError) and not isinstance(exc, PlatformValidationError):
            raise HTTPException(
                status_code=422,
                detail=error_detail("invalid_uuid", str(exc)),
            ) from exc
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _notification_response(notification)


@router.post(
    "/notification-requests/{request_id}/confirm",
    response_model=NotificationRequestResponse,
)
def confirm_notification_request_endpoint(
    request_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    settings: Settings = Depends(get_settings),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> NotificationRequestResponse:
    try:
        workspace_id = workspace_id_for_notification(uow, request_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "notification_request.confirm",
        )
        notification = confirm_notification_request(
            uow,
            request_id,
            actor=actor,
            server_mode=settings.stage06_notification_mode,
            server_allowlist=settings.stage06_notification_allowed_chat_ids,
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        _commit_if_sqlalchemy(uow)
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _notification_response(notification)


@router.get(
    "/bases/{base_id}/notification-requests",
    response_model=NotificationRequestListResponse,
)
def list_notification_requests_endpoint(
    base_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> NotificationRequestListResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "notification_request.read",
        )
    except Stage06AuthorizationError as exc:
        raise _http_error(exc) from exc
    try:
        page = paginate_items(
            list_notification_requests(uow, base_id),
            limit=limit,
            cursor=cursor,
        )
    except Stage06PaginationError as exc:
        raise _pagination_http_error(exc) from exc
    return NotificationRequestListResponse(
        requests=[
            _notification_response(request)
            for request in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get("/bases/{base_id}/audit-events", response_model=AuditEventListResponse)
def list_base_audit_events_endpoint(
    base_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> AuditEventListResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(uow, identity, workspace_id, "audit.read")
    except Stage06AuthorizationError as exc:
        raise _http_error(exc) from exc
    try:
        page = paginate_items(
            list_base_audit_events(uow, base_id),
            limit=limit,
            cursor=cursor,
        )
    except Stage06PaginationError as exc:
        raise _pagination_http_error(exc) from exc
    return AuditEventListResponse(
        events=[
            _audit_event_response(event)
            for event in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


def _employee_response(employee: object) -> DigitalEmployeeResponse:
    return DigitalEmployeeResponse(
        id=str(employee.id),
        workspace_id=str(employee.workspace_id),
        base_id=str(employee.base_id),
        name=employee.name,
        description=employee.description,
        telegram_alias=employee.telegram_alias,
        accessible_tables=employee.accessible_tables,
        accessible_views=employee.accessible_views,
        allowed_actions=employee.allowed_actions,
        status=employee.status,
    )


def _draft_response(draft: object) -> RecordChangeDraftResponse:
    return RecordChangeDraftResponse(
        id=str(draft.id),
        workspace_id=str(draft.workspace_id),
        base_id=str(draft.base_id),
        table_id=str(draft.table_id),
        record_id=None if draft.record_id is None else str(draft.record_id),
        draft_type=draft.draft_type,
        proposed_values=draft.proposed_values,
        before_values=draft.before_values,
        created_by_type=draft.created_by_type,
        created_by_id=draft.created_by_id,
        status=draft.status,
        trace_id=draft.trace_id,
        expected_version=draft.expected_version,
    )


def _notification_response(request: object) -> NotificationRequestResponse:
    return NotificationRequestResponse(
        id=str(request.id),
        workspace_id=str(request.workspace_id),
        base_id=None if request.base_id is None else str(request.base_id),
        source_record_id=(
            None if request.source_record_id is None else str(request.source_record_id)
        ),
        channel=request.channel,
        target=request.target,
        message_payload=request.message_payload,
        send_policy=request.send_policy,
        status=request.status,
        trace_id=request.trace_id,
    )


def _audit_event_response(event: object) -> AuditEventResponse:
    return AuditEventResponse(
        id=str(event.id),
        trace_id=event.trace_id,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        event_type=event.event_type,
        entity_type=event.entity_type,
        entity_id=None if event.entity_id is None else str(event.entity_id),
        before_state=sanitize_stage06_audit_state(event.before_state),
        after_state=sanitize_stage06_audit_state(event.after_state),
        permission_snapshot=sanitize_stage06_audit_state(event.permission_snapshot),
    )


def _uuid_or_none(value: str | None) -> UUID | None:
    return None if value is None else UUID(value)


def _commit_if_sqlalchemy(uow: Stage06RuntimeUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _begin_and_reserve(
    uow: Stage06RuntimeUnitOfWork,
    *,
    workspace_id: UUID,
    operation: str,
    idempotency_key: str,
    request_fingerprint: str,
):
    trace_id = idempotency_trace_id(operation, request_fingerprint, idempotency_key)
    try:
        decision = begin_idempotent_operation(
            uow,
            workspace_id=workspace_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            trace_id=trace_id,
        )
        if decision.status == "started":
            _commit_if_sqlalchemy(uow)
        return decision
    except IntegrityError:
        session = getattr(uow, "session", None)
        if session is None:
            raise
        session.rollback()
        return begin_idempotent_operation(
            uow,
            workspace_id=workspace_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            trace_id=trace_id,
        )


def _http_error(
    exc: PlatformValidationError | Stage06AuthorizationError,
) -> HTTPException:
    if isinstance(exc, Stage06AuthorizationError):
        status_code = 404 if exc.code.endswith("_not_found") else 403
        return HTTPException(
            status_code=status_code,
            detail=error_detail(exc.code, str(exc)),
        )
    if exc.code.endswith("_not_found"):
        status_code = 404
    elif exc.code.endswith("_denied"):
        status_code = 403
    elif "conflict" in exc.code or exc.code == "idempotency_in_progress":
        status_code = 409
    else:
        status_code = 422
    return HTTPException(status_code=status_code, detail=error_detail(exc.code, str(exc)))


def _pagination_http_error(exc: Stage06PaginationError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=error_detail(exc.code, str(exc)),
    )
