from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.schemas.stage07_draft_employee_hub import (
    DigitalEmployeeContactPageResponse,
    DigitalEmployeeContactResponse,
    SafeDraftActionsResponse,
    SafeDraftDetailResponse,
    SafeDraftFieldResponse,
    SafeDraftPageResponse,
    SafeDraftSummaryResponse,
    SafeDraftTerminalReceipt,
    SafeDraftTerminalRequest,
    SafeEmployeeInvocationRequest,
    SafeEmployeeInvocationResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    action_allowed_for_role,
    authorize_workspace_action,
    workspace_id_for_base,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_pagination import Stage06PaginationError, paginate_items
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    get_table_schema,
    list_bases_for_workspace,
)
from app.services.stage07_draft_employee_hub import confirm_s5_draft, reject_s5_draft
from app.services.stage06_digital_employees import invoke_digital_employee


router = APIRouter(tags=["stage07-draft-employee-hub"])

_SAFE_INTENTS = ("summarize", "draft_update")


@router.get(
    "/mini-app/workspaces/{workspace_id}/digital-employee-contacts",
    response_model=DigitalEmployeeContactPageResponse,
)
def list_digital_employee_contacts(
    workspace_id: UUID,
    base_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> DigitalEmployeeContactPageResponse:
    try:
        authorize_workspace_action(uow, identity, workspace_id, "digital_employee.read")
        bases = list_bases_for_workspace(uow, workspace_id)
    except Stage06AuthorizationError as exc:
        raise HTTPException(
            status_code=404 if exc.code.endswith("_not_found") else 403,
            detail=error_detail(exc.code, exc.code),
        ) from exc

    allowed_base_ids = {base.id for base in bases}
    if base_id is not None and base_id not in allowed_base_ids:
        raise HTTPException(
            status_code=404,
            detail=error_detail("base_not_found", "base_not_found"),
        )
    contacts = [
        employee
        for selected_base_id in sorted(allowed_base_ids)
        if base_id is None or selected_base_id == base_id
        for employee in uow.list_digital_employees(selected_base_id)
        if employee.status == "active" and employee.workspace_id == workspace_id
    ]
    contacts.sort(key=lambda employee: (employee.name.casefold(), str(employee.id)))
    try:
        page = paginate_items(contacts, limit=limit, cursor=cursor)
    except Stage06PaginationError as exc:
        raise HTTPException(
            status_code=422,
            detail=error_detail("digital_employee_contact_invalid_cursor", "digital_employee_contact_invalid_cursor"),
        ) from exc
    return DigitalEmployeeContactPageResponse(
        workspace_id=str(workspace_id),
        contacts=[
            DigitalEmployeeContactResponse(
                id=str(employee.id),
                base_id=str(employee.base_id),
                name=employee.name,
                description=employee.description,
                status="active",
                available_intents=[
                    action for action in _SAFE_INTENTS if action in employee.allowed_actions
                ],
            )
            for employee in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.post(
    "/mini-app/digital-employees/{employee_id}/invocations",
    response_model=SafeEmployeeInvocationResponse,
)
def invoke_safe_digital_employee(
    employee_id: UUID,
    request: SafeEmployeeInvocationRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> SafeEmployeeInvocationResponse:
    employee = uow.get_digital_employee(employee_id)
    if employee is None or employee.status != "active":
        raise HTTPException(status_code=404, detail=error_detail("digital_employee_not_found", "digital_employee_not_found"))
    try:
        actor = authorize_workspace_action(uow, identity, employee.workspace_id, "digital_employee.invoke")
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    try:
        base_id = UUID(request.base_id)
        view_id = None if request.view_id is None else UUID(request.view_id)
        record_id = None if request.record_id is None else UUID(request.record_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=error_detail("invalid_uuid", "invalid_uuid")) from exc
    if base_id != employee.base_id:
        raise HTTPException(status_code=404, detail=error_detail("resource_scope_mismatch", "resource_scope_mismatch"))
    if request.intent == "summarize" and view_id is None:
        raise HTTPException(status_code=422, detail=error_detail("view_required", "view_required"))
    if request.intent == "draft_update" and (view_id is None or record_id is None):
        raise HTTPException(status_code=422, detail=error_detail("draft_context_required", "draft_context_required"))
    try:
        result = invoke_digital_employee(
            uow,
            employee_id,
            action=request.intent,
            view_id=view_id,
            record_id=record_id,
            runtime_mode="live",
            prompt=request.instruction,
            actor=actor,
        )
    except PlatformValidationError as exc:
        raise _platform_error(exc) from exc
    if request.intent == "draft_update":
        draft_id = result.get("draft_id")
        if not isinstance(draft_id, str) or result.get("status") != "pending_confirmation":
            raise HTTPException(status_code=422, detail=error_detail("safe_draft_result_unavailable", "safe_draft_result_unavailable"))
        return SafeEmployeeInvocationResponse(kind="draft", draft_id=draft_id, status="pending_confirmation")
    answer = result.get("answer")
    if not isinstance(answer, str):
        raise HTTPException(status_code=422, detail=error_detail("safe_summary_result_unavailable", "safe_summary_result_unavailable"))
    return SafeEmployeeInvocationResponse(kind="summary", answer=answer)


@router.get("/mini-app/bases/{base_id}/drafts", response_model=SafeDraftPageResponse)
def list_safe_drafts(
    base_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> SafeDraftPageResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(uow, identity, workspace_id, "record_change_draft.read")
        page = paginate_items(uow.list_record_change_drafts(base_id), limit=limit, cursor=cursor)
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except Stage06PaginationError as exc:
        raise HTTPException(status_code=422, detail=error_detail("draft_invalid_cursor", "draft_invalid_cursor")) from exc
    return SafeDraftPageResponse(
        base_id=str(base_id),
        drafts=[_safe_draft_summary(draft) for draft in page.items],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get("/mini-app/drafts/{draft_id}", response_model=SafeDraftDetailResponse)
def get_safe_draft(
    draft_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> SafeDraftDetailResponse:
    draft = uow.get_record_change_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=error_detail("record_change_draft_not_found", "record_change_draft_not_found"))
    try:
        actor = authorize_workspace_action(uow, identity, draft.workspace_id, "record_change_draft.read")
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    schema = get_table_schema(uow, draft.table_id, actor=actor)
    fields_by_key = {field["key"]: field for field in schema["fields"]}
    fields = [
        SafeDraftFieldResponse(
            key=key,
            label=field["name"],
            field_type=field["field_type"],
            before_value=_safe_value((draft.before_values or {}).get(key)),
            proposed_value=_safe_value(draft.proposed_values.get(key)),
        )
        for key, field in fields_by_key.items()
        if key in draft.proposed_values and _safe_value(draft.proposed_values.get(key)) is not _UNSAFE
    ]
    pending = draft.status == "pending_confirmation"
    return SafeDraftDetailResponse(
        **_safe_draft_summary(draft).model_dump(),
        fields=fields,
        actions=SafeDraftActionsResponse(
            can_confirm=pending and action_allowed_for_role(actor.role, "record_change_draft.confirm"),
            can_reject=pending and action_allowed_for_role(actor.role, "record_change_draft.reject"),
        ),
        terminal_audit_event_id=(None if draft.terminal_audit_event_id is None else str(draft.terminal_audit_event_id)),
    )


@router.post("/mini-app/drafts/{draft_id}/reject", response_model=SafeDraftTerminalReceipt)
def reject_safe_draft(
    draft_id: UUID,
    request: SafeDraftTerminalRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> SafeDraftTerminalReceipt:
    draft = uow.get_record_change_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=error_detail("record_change_draft_not_found", "record_change_draft_not_found"))
    try:
        actor = authorize_workspace_action(uow, identity, draft.workspace_id, "record_change_draft.reject")
        fingerprint = fingerprint_request({"draft_id": str(draft_id), "expected_version": request.expected_version, "user_id": identity.user_id})
        decision = begin_idempotent_operation(
            uow, workspace_id=draft.workspace_id, operation="stage07.s5.draft.reject",
            idempotency_key=idempotency_key, request_fingerprint=fingerprint,
            trace_id=idempotency_trace_id("stage07.s5.draft.reject", fingerprint, idempotency_key),
        )
        if decision.status == "replay":
            replay_draft = uow.get_record_change_draft(UUID(str((decision.response_ref or {})["draft_id"])))
            if replay_draft is None or replay_draft.terminal_audit_event_id is None:
                raise PlatformValidationError("record_change_draft_not_found", str(draft_id))
            return _terminal_receipt(replay_draft)
        terminal = reject_s5_draft(uow, draft_id, expected_version=request.expected_version, actor=actor)
        complete_idempotent_operation(decision.record, response_ref={"draft_id": str(terminal.id)})
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except PlatformValidationError as exc:
        raise _platform_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _terminal_receipt(terminal)


@router.post("/mini-app/drafts/{draft_id}/confirm", response_model=SafeDraftTerminalReceipt)
def confirm_safe_draft(
    draft_id: UUID,
    request: SafeDraftTerminalRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> SafeDraftTerminalReceipt:
    draft = uow.get_record_change_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=error_detail("record_change_draft_not_found", "record_change_draft_not_found"))
    try:
        actor = authorize_workspace_action(uow, identity, draft.workspace_id, "record_change_draft.confirm")
        fingerprint = fingerprint_request({"draft_id": str(draft_id), "expected_version": request.expected_version, "user_id": identity.user_id})
        decision = begin_idempotent_operation(
            uow, workspace_id=draft.workspace_id, operation="stage07.s5.draft.confirm",
            idempotency_key=idempotency_key, request_fingerprint=fingerprint,
            trace_id=idempotency_trace_id("stage07.s5.draft.confirm", fingerprint, idempotency_key),
        )
        if decision.status == "replay":
            replay_draft = uow.get_record_change_draft(UUID(str((decision.response_ref or {})["draft_id"])))
            if replay_draft is None or replay_draft.terminal_audit_event_id is None:
                raise PlatformValidationError("record_change_draft_not_found", str(draft_id))
            return _terminal_receipt(replay_draft)
        terminal = confirm_s5_draft(uow, draft_id, expected_version=request.expected_version, actor=actor)
        complete_idempotent_operation(decision.record, response_ref={"draft_id": str(terminal.id)})
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except PlatformValidationError as exc:
        raise _platform_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _terminal_receipt(terminal)


_UNSAFE = object()


def _safe_value(value: object):
    return value if value is None or isinstance(value, (str, int, float, bool)) else _UNSAFE


def _safe_draft_summary(draft) -> SafeDraftSummaryResponse:
    return SafeDraftSummaryResponse(
        id=str(draft.id), base_id=str(draft.base_id), table_id=str(draft.table_id),
        record_id=None if draft.record_id is None else str(draft.record_id),
        draft_type=draft.draft_type, status=draft.status, version=draft.version,
    )


def _terminal_receipt(draft) -> SafeDraftTerminalReceipt:
    if draft.terminal_audit_event_id is None:
        raise RuntimeError("terminal draft missing audit reference")
    return SafeDraftTerminalReceipt(
        id=str(draft.id), status=draft.status, version=draft.version,
        terminal_audit_event_id=str(draft.terminal_audit_event_id),
    )


def _authorization_error(exc: Stage06AuthorizationError) -> HTTPException:
    return HTTPException(
        status_code=404 if exc.code.endswith("_not_found") else 403,
        detail=error_detail(exc.code, exc.code),
    )


def _platform_error(exc: PlatformValidationError) -> HTTPException:
    status_code = 404 if exc.code.endswith("_not_found") else 409 if "conflict" in exc.code or "invalid_state" in exc.code or "idempotency" in exc.code else 422
    return HTTPException(status_code=status_code, detail=error_detail(exc.code, exc.code))


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()
