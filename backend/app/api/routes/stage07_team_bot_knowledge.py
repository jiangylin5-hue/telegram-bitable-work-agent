from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.schemas.stage07_team_bot_knowledge import (
    TeamBotCitationResponse,
    TeamBotContactPageResponse,
    TeamBotContactResponse,
    TeamBotEmployeeResponse,
    TeamBotKnowledgeContextPageResponse,
    TeamBotKnowledgeContextViewResponse,
    TeamBotSelectedViewResponse,
    TeamBotSummaryRequest,
    TeamBotSummaryResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_pagination import (
    Stage06PaginationError,
    paginate_items,
)
from app.services.stage06_platform import PlatformValidationError, Stage06PlatformUnitOfWork
from app.services.stage07_team_bot_knowledge import (
    list_team_bot_contacts,
    resolve_team_bot_context,
    resolve_team_bot_selected_view,
    summarize_team_bot_knowledge,
)


router = APIRouter(tags=["stage07-team-bot-knowledge"])


@router.get(
    "/mini-app/workspaces/{workspace_id}/team-bot-contacts",
    response_model=TeamBotContactPageResponse,
)
def get_team_bot_contacts(
    workspace_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> TeamBotContactPageResponse:
    try:
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.invoke",
        )
        page = paginate_items(
            list_team_bot_contacts(uow, workspace_id=workspace_id, actor=actor),
            limit=limit,
            cursor=cursor,
        )
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except Stage06PaginationError as exc:
        raise HTTPException(
            status_code=422,
            detail=error_detail("team_bot_invalid_cursor", "team_bot_invalid_cursor"),
        ) from exc
    return TeamBotContactPageResponse(
        workspace_id=str(workspace_id),
        contacts=[
            TeamBotContactResponse(
                id=str(employee.id),
                base_id=str(employee.base_id),
                name=employee.name,
                description=employee.description,
                available_intents=["summarize"],
            )
            for employee in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get(
    "/mini-app/team-bots/{employee_id}/knowledge-contexts",
    response_model=TeamBotKnowledgeContextPageResponse,
)
def get_team_bot_knowledge_contexts(
    employee_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> TeamBotKnowledgeContextPageResponse:
    try:
        employee = uow.get_digital_employee(employee_id)
        if employee is None:
            raise PlatformValidationError("team_bot_not_found", str(employee_id))
        actor = authorize_workspace_action(
            uow,
            identity,
            employee.workspace_id,
            "digital_employee.invoke",
        )
        employee, views = resolve_team_bot_context(
            uow,
            employee_id=employee_id,
            actor=actor,
        )
        page = paginate_items(views, limit=limit, cursor=cursor)
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except Stage06PaginationError as exc:
        raise HTTPException(
            status_code=422,
            detail=error_detail("team_bot_invalid_cursor", "team_bot_invalid_cursor"),
        ) from exc
    except PlatformValidationError as exc:
        raise _platform_error(exc) from exc
    return TeamBotKnowledgeContextPageResponse(
        employee=TeamBotEmployeeResponse(
            id=str(employee.id),
            name=employee.name,
            description=employee.description,
            base_id=str(employee.base_id),
        ),
        views=[
            TeamBotKnowledgeContextViewResponse(
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
    "/mini-app/team-bots/{employee_id}/knowledge-contexts/{view_id}",
    response_model=TeamBotSelectedViewResponse,
)
def get_team_bot_selected_view(
    employee_id: UUID,
    view_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> TeamBotSelectedViewResponse:
    try:
        employee = uow.get_digital_employee(employee_id)
        if employee is None:
            raise PlatformValidationError("team_bot_not_found", str(employee_id))
        actor = authorize_workspace_action(
            uow,
            identity,
            employee.workspace_id,
            "digital_employee.invoke",
        )
        employee, view = resolve_team_bot_selected_view(
            uow,
            employee_id=employee_id,
            view_id=view_id,
            actor=actor,
        )
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except PlatformValidationError as exc:
        raise _platform_error(exc) from exc
    return TeamBotSelectedViewResponse(
        id=str(view.id),
        name=view.name,
        view_type=view.view_type,
        base_id=str(employee.base_id),
    )


@router.post(
    "/mini-app/team-bots/{employee_id}/summaries",
    response_model=TeamBotSummaryResponse,
)
def summarize_team_bot(
    employee_id: UUID,
    request: TeamBotSummaryRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> TeamBotSummaryResponse:
    try:
        base_id = UUID(request.base_id)
        view_id = UUID(request.view_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=error_detail("invalid_uuid", "invalid_uuid"),
        ) from exc
    try:
        employee = uow.get_digital_employee(employee_id)
        if employee is None:
            raise PlatformValidationError("team_bot_not_found", str(employee_id))
        actor = authorize_workspace_action(
            uow,
            identity,
            employee.workspace_id,
            "digital_employee.invoke",
        )
        receipt = summarize_team_bot_knowledge(
            uow,
            employee_id=employee_id,
            base_id=base_id,
            view_id=view_id,
            actor=actor,
            instruction=request.instruction,
            idempotency_key=idempotency_key,
        )
    except Stage06AuthorizationError as exc:
        raise _authorization_error(exc) from exc
    except PlatformValidationError as exc:
        raise _platform_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return TeamBotSummaryResponse(
        kind=receipt.kind,
        employee_id=str(receipt.employee_id),
        base_id=str(receipt.base_id),
        view_id=str(receipt.view_id),
        answer=receipt.answer,
        citations=[
            TeamBotCitationResponse(record_id=record_id)
            for record_id in receipt.citation_record_ids
        ],
        knowledge_window_truncated=receipt.knowledge_window_truncated,
        audit_event_id=str(receipt.audit_event_id),
    )


def _authorization_error(exc: Stage06AuthorizationError) -> HTTPException:
    return HTTPException(
        status_code=404 if exc.code.endswith("_not_found") else 403,
        detail=error_detail(exc.code, exc.code),
    )


def _platform_error(exc: PlatformValidationError) -> HTTPException:
    if exc.code in {"team_bot_not_found", "team_bot_context_not_found"}:
        status_code = 404
    elif "conflict" in exc.code or "idempotency" in exc.code:
        status_code = 409
    else:
        status_code = 422
    return HTTPException(status_code=status_code, detail=error_detail(exc.code, exc.code))


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()

