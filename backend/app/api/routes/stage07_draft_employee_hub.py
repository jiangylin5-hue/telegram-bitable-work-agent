from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.schemas.stage07_draft_employee_hub import (
    DigitalEmployeeContactPageResponse,
    DigitalEmployeeContactResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_pagination import Stage06PaginationError, paginate_items
from app.services.stage06_platform import (
    Stage06PlatformUnitOfWork,
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
