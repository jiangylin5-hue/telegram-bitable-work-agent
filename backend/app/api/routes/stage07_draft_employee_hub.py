from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.schemas.stage07_draft_employee_hub import (
    DigitalEmployeeContactPageResponse,
    DigitalEmployeeContactResponse,
    SafeAssistantContextEmployeeResponse,
    SafeAssistantContextPageResponse,
    SafeAssistantContextViewResponse,
    SafeAssistantSelectedViewResponse,
    SafeDraftActionsResponse,
    SafeDraftDetailResponse,
    SafeDraftFieldResponse,
    SafeDraftPageResponse,
    SafeDraftSummaryResponse,
    SafeDraftTerminalReceipt,
    SafeDraftTerminalRequest,
    SafeCitationResponse,
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
from app.services.permissions import Actor
from app.services.stage06_pagination import (
    Stage06PaginationError,
    bounded_page_size,
    decode_page_cursor,
    encode_page_cursor,
    paginate_items,
)
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    can_actor_write_record_fields,
    get_view_presentation,
    get_table_schema,
    list_bases_for_workspace,
    list_views_for_base,
    list_view_records,
    read_record_for_actor,
)
from app.services.stage07_draft_employee_hub import confirm_s5_draft, reject_s5_draft
from app.services.stage06_digital_employees import invoke_digital_employee
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)


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
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.read",
        )
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
        if employee.status == "active"
        and employee.workspace_id == workspace_id
        and is_member_eligible_for_employee(uow, employee, actor.actor_id)
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


@router.get(
    "/mini-app/digital-employees/{employee_id}/assistant-context",
    response_model=SafeAssistantContextPageResponse,
)
def list_assistant_context(
    employee_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> SafeAssistantContextPageResponse:
    try:
        employee, _actor, views = _resolve_assistant_context(uow, employee_id, identity)
        page = paginate_items(views, limit=limit, cursor=cursor)
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except Stage06PaginationError as exc:
        raise HTTPException(
            status_code=422,
            detail=error_detail("assistant_context_invalid_cursor", "assistant_context_invalid_cursor"),
        ) from exc
    return SafeAssistantContextPageResponse(
        employee=SafeAssistantContextEmployeeResponse(
            id=str(employee.id),
            name=employee.name,
            description=employee.description,
            base_id=str(employee.base_id),
        ),
        views=[
            SafeAssistantContextViewResponse(
                id=str(view.id),
                name=view.name,
                view_type=view.view_type,
            )
            for view in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get(
    "/mini-app/digital-employees/{employee_id}/assistant-context/views/{view_id}",
    response_model=SafeAssistantSelectedViewResponse,
)
def read_assistant_context_view(
    employee_id: UUID,
    view_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> SafeAssistantSelectedViewResponse:
    try:
        employee, _actor, views = _resolve_assistant_context(uow, employee_id, identity)
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    view = next((item for item in views if item.id == view_id), None)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail=error_detail("assistant_context_not_found", "assistant_context_not_found"),
        )
    return SafeAssistantSelectedViewResponse(
        id=str(view.id),
        name=view.name,
        view_type=view.view_type,
        base_id=str(employee.base_id),
    )


@router.post(
    "/mini-app/digital-employees/{employee_id}/invocations",
    response_model=SafeEmployeeInvocationResponse,
)
def invoke_safe_digital_employee(
    employee_id: UUID,
    request: SafeEmployeeInvocationRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=160),
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
    if not is_member_eligible_for_employee(uow, employee, actor.actor_id):
        raise HTTPException(
            status_code=404,
            detail=error_detail("digital_employee_not_found", "digital_employee_not_found"),
        )
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
    if request.intent == "draft_update" and idempotency_key is None:
        raise HTTPException(status_code=422, detail=error_detail("idempotency_key_required", "idempotency_key_required"))
    invocation_decision = None
    try:
        if view_id is not None:
            view_payload = list_view_records(
                uow,
                view_id,
                actor=actor,
                limit=None if request.intent == "draft_update" else 1,
            )
            _validate_safe_invocation_context(
                uow,
                employee=employee,
                selected_base_id=base_id,
                view_id=view_id,
                record_id=record_id,
                intent=request.intent,
                actor=actor,
                view_payload=view_payload,
            )
        if request.intent == "draft_update":
            assert idempotency_key is not None
            fingerprint = fingerprint_request({
                "employee_id": str(employee_id),
                "intent": request.intent,
                "base_id": request.base_id,
                "view_id": request.view_id,
                "record_id": request.record_id,
                "instruction": request.instruction,
                "user_id": identity.user_id,
            })
            invocation_decision = _begin_s5_idempotent_operation(
                uow,
                workspace_id=employee.workspace_id,
                operation="stage07.s5.digital_employee.draft_update",
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
            )
            if invocation_decision.status == "replay":
                replay_ref = invocation_decision.response_ref or {}
                replay_draft_id = replay_ref.get("draft_id")
                if not isinstance(replay_draft_id, str):
                    raise PlatformValidationError("safe_draft_result_unavailable", str(employee_id))
                return SafeEmployeeInvocationResponse(
                    kind="draft",
                    draft_id=replay_draft_id,
                    status="pending_confirmation",
                )
        result = invoke_digital_employee(
            uow,
            employee_id,
            action=request.intent,
            view_id=view_id,
            record_id=record_id,
            runtime_mode="live_openrouter",
            prompt=request.instruction,
            actor=actor,
        )
        if request.intent == "draft_update":
            draft_id = result.get("draft_id")
            if (
                not isinstance(draft_id, str)
                or result.get("status") != "pending_confirmation"
            ):
                raise PlatformValidationError(
                    "safe_draft_result_unavailable",
                    str(employee_id),
                )
            assert invocation_decision is not None
            complete_idempotent_operation(
                invocation_decision.record,
                response_ref={"draft_id": draft_id},
            )
    except PlatformValidationError as exc:
        if invocation_decision is not None and invocation_decision.status == "started":
            _discard_s5_idempotency_reservation(uow, invocation_decision.record)
        raise _platform_error(exc) from exc
    except Exception:
        if invocation_decision is not None and invocation_decision.status == "started":
            _discard_s5_idempotency_reservation(uow, invocation_decision.record)
        raise
    if request.intent == "draft_update":
        draft_id = result["draft_id"]
        assert invocation_decision is not None
        _commit_if_sqlalchemy(uow)
        return SafeEmployeeInvocationResponse(kind="draft", draft_id=draft_id, status="pending_confirmation")
    answer = result.get("answer")
    if not isinstance(answer, str):
        raise HTTPException(status_code=422, detail=error_detail("safe_summary_result_unavailable", "safe_summary_result_unavailable"))
    _commit_if_sqlalchemy(uow)
    assert view_id is not None
    return SafeEmployeeInvocationResponse(
        kind="summary",
        answer=answer,
        citations=_safe_summary_citations(uow, view_id=view_id, actor=actor, citations=result.get("citations")),
    )


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
        page_size = bounded_page_size(limit)
        after = None
        if cursor is not None:
            try:
                after_id = UUID(decode_page_cursor(cursor))
            except ValueError as exc:
                raise Stage06PaginationError("invalid_page_cursor") from exc
            after = uow.get_record_change_draft(after_id)
            if (
                after is None
                or after.base_id != base_id
                or after.status != "pending_confirmation"
            ):
                raise Stage06PaginationError("invalid_page_cursor")
        window = uow.list_pending_record_change_drafts(
            base_id,
            after=after,
            limit=page_size + 1,
        )
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except Stage06PaginationError as exc:
        raise HTTPException(status_code=422, detail=error_detail("draft_invalid_cursor", "draft_invalid_cursor")) from exc
    drafts = window[:page_size]
    has_more = len(window) > page_size
    return SafeDraftPageResponse(
        base_id=str(base_id),
        drafts=[_safe_draft_summary(draft) for draft in drafts],
        next_cursor=encode_page_cursor(str(drafts[-1].id)) if has_more and drafts else None,
        has_more=has_more,
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
    fields: list[SafeDraftFieldResponse] = []
    for key, field in fields_by_key.items():
        if key not in draft.proposed_values:
            continue
        proposed_value = _safe_value(draft.proposed_values.get(key))
        if proposed_value is _UNSAFE:
            continue
        before_value = _safe_value((draft.before_values or {}).get(key))
        fields.append(
            SafeDraftFieldResponse(
                key=key,
                label=field["name"],
                field_type=field["field_type"],
                before_value=None if before_value is _UNSAFE else before_value,
                proposed_value=proposed_value,
            )
        )
    pending = draft.status == "pending_confirmation"
    record = None if draft.record_id is None else uow.get_record(draft.record_id)
    can_confirm = (
        pending
        and record is not None
        and record.table_id == draft.table_id
        and action_allowed_for_role(actor.role, "record_change_draft.confirm")
        and can_actor_write_record_fields(
            uow,
            draft.table_id,
            draft.proposed_values.keys(),
            actor=actor,
        )
    )
    return SafeDraftDetailResponse(
        **_safe_draft_summary(draft).model_dump(),
        fields=fields,
        actions=SafeDraftActionsResponse(
            can_confirm=can_confirm,
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


_SAFE_ASSISTANT_VIEW_TYPES = {"grid", "kanban", "calendar", "form"}


def _resolve_assistant_context(
    uow: Stage06PlatformUnitOfWork,
    employee_id: UUID,
    identity: Stage06RequestIdentity,
):
    employee = uow.get_digital_employee(employee_id)
    if (
        employee is None
        or employee.status != "active"
        or "summarize" not in set(employee.allowed_actions)
    ):
        raise HTTPException(
            status_code=404,
            detail=error_detail("assistant_context_not_found", "assistant_context_not_found"),
        )
    actor = authorize_workspace_action(
        uow,
        identity,
        employee.workspace_id,
        "digital_employee.invoke",
    )
    if not is_member_eligible_for_employee(uow, employee, actor.actor_id):
        raise HTTPException(
            status_code=404,
            detail=error_detail("assistant_context_not_found", "assistant_context_not_found"),
        )
    if employee.base_id not in {base.id for base in list_bases_for_workspace(uow, employee.workspace_id)}:
        raise HTTPException(
            status_code=404,
            detail=error_detail("assistant_context_not_found", "assistant_context_not_found"),
        )
    allowed_view_ids = set(employee.accessible_views)
    allowed_table_ids = set(employee.accessible_tables)
    views = []
    for view in list_views_for_base(uow, employee.base_id, actor=actor):
        if (
            str(view.id) not in allowed_view_ids
            or view.table_id is None
            or str(view.table_id) not in allowed_table_ids
            or view.view_type not in _SAFE_ASSISTANT_VIEW_TYPES
        ):
            continue
        try:
            get_view_presentation(uow, view.id, actor=actor)
        except PlatformValidationError:
            continue
        views.append(view)
    views.sort(key=lambda view: (view.name.casefold(), str(view.id)))
    return employee, actor, views


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


def _safe_summary_citations(
    uow: Stage06PlatformUnitOfWork,
    *,
    view_id: UUID,
    actor: Actor,
    citations: object,
) -> list[SafeCitationResponse]:
    if not isinstance(citations, list):
        return []
    visible_record_ids = {
        record["id"]
        for record in list_view_records(uow, view_id, actor=actor).get("records", [])
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    safe_citations: list[SafeCitationResponse] = []
    seen_record_ids: set[str] = set()
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        record_id = citation.get("record_id")
        if not isinstance(record_id, str) or record_id not in visible_record_ids or record_id in seen_record_ids:
            continue
        safe_citations.append(SafeCitationResponse(record_id=record_id))
        seen_record_ids.add(record_id)
    return safe_citations


def _discard_s5_idempotency_reservation(uow: Stage06PlatformUnitOfWork, record: object) -> None:
    """Release a draft-invocation key only when no safe terminal result was produced."""
    session = getattr(uow, "session", None)
    if session is not None:
        state = inspect(record)
        if state.pending:
            session.expunge(record)
        elif state.persistent:
            session.delete(record)
        session.commit()
        return
    records = getattr(uow, "idempotency_records", None)
    if isinstance(records, list) and record in records:
        records.remove(record)


def _begin_s5_idempotent_operation(
    uow: Stage06PlatformUnitOfWork,
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


def _authorization_error(exc: Stage06AuthorizationError) -> HTTPException:
    return HTTPException(
        status_code=404 if exc.code.endswith("_not_found") else 403,
        detail=error_detail(exc.code, exc.code),
    )


def _platform_error(exc: PlatformValidationError) -> HTTPException:
    status_code = 404 if exc.code.endswith("_not_found") else 409 if "conflict" in exc.code or "invalid_state" in exc.code or "idempotency" in exc.code else 422
    return HTTPException(status_code=status_code, detail=error_detail(exc.code, exc.code))


def _validate_safe_invocation_context(
    uow: Stage06PlatformUnitOfWork,
    *,
    employee,
    selected_base_id: UUID,
    view_id: UUID,
    record_id: UUID | None,
    intent: str,
    actor: Actor,
    view_payload: dict,
) -> None:
    """Fail closed before reserving a draft invocation or reaching the runtime."""
    view = uow.get_view(view_id)
    if view is None:
        raise PlatformValidationError("view_not_found", str(view_id))
    if str(view_id) not in set(employee.accessible_views):
        raise PlatformValidationError("digital_employee_scope_denied", str(view_id))
    if view.base_id != selected_base_id or view.base_id != employee.base_id or view.table_id is None:
        raise PlatformValidationError("resource_scope_mismatch", "view")
    if intent not in set(employee.allowed_actions):
        raise PlatformValidationError("digital_employee_action_denied", intent)
    if intent != "draft_update":
        return

    assert record_id is not None
    record_payload = read_record_for_actor(uow, record_id, actor=actor)
    if record_payload["table_id"] != str(view.table_id):
        raise PlatformValidationError("resource_scope_mismatch", "record")
    if record_payload["table_id"] not in set(employee.accessible_tables):
        raise PlatformValidationError("digital_employee_scope_denied", record_payload["table_id"])
    visible_record_ids = {
        record["id"]
        for record in view_payload.get("records", [])
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    if str(record_id) not in visible_record_ids:
        raise PlatformValidationError("digital_employee_record_not_visible", str(record_id))


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()
