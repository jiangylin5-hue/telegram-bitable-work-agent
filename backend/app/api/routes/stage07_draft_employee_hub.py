from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

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
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    action_allowed_for_role,
    authorize_workspace_action,
    workspace_id_for_base,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_pagination import Stage06PaginationError, paginate_items
from app.services.stage06_platform import (
    Stage06PlatformUnitOfWork,
    get_table_schema,
    list_bases_for_workspace,
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


_UNSAFE = object()


def _safe_value(value: object):
    return value if value is None or isinstance(value, (str, int, float, bool)) else _UNSAFE


def _safe_draft_summary(draft) -> SafeDraftSummaryResponse:
    return SafeDraftSummaryResponse(
        id=str(draft.id), base_id=str(draft.base_id), table_id=str(draft.table_id),
        record_id=None if draft.record_id is None else str(draft.record_id),
        draft_type=draft.draft_type, status=draft.status, version=draft.version,
    )


def _authorization_error(exc: Stage06AuthorizationError) -> HTTPException:
    return HTTPException(
        status_code=404 if exc.code.endswith("_not_found") else 403,
        detail=error_detail(exc.code, exc.code),
    )
