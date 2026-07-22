from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.runtime.stage08_contracts import ExecutionPlan, ExecutionTicketState
from app.runtime.stage08_tool_gateway import Stage08ToolGateway, Stage08ToolGatewayError
from app.schemas.stage08_runtime import (
    RuntimeExecutionPlanRequest,
    RuntimeExecutionPlanResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import PlatformValidationError, Stage06PlatformUnitOfWork
from app.services.stage08_runtime import begin_execution_plan


class _RedactedRuntimeValidationRoute(APIRoute):
    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def redacted_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=error_detail(
                        "stage08_runtime_request_invalid",
                        "stage08_runtime_request_invalid",
                    ),
                ) from exc

        return redacted_route_handler


router = APIRouter(
    prefix="/api/stage08/runtime",
    tags=["stage08-runtime"],
    route_class=_RedactedRuntimeValidationRoute,
)
_TERMINAL_RESPONSE_STATES = frozenset({"succeeded", "failed", "denied"})


@router.post(
    "/execute-plan",
    response_model=RuntimeExecutionPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def execute_runtime_plan(
    request: RuntimeExecutionPlanRequest,
    response: Response,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> RuntimeExecutionPlanResponse:
    try:
        workspace_id = UUID(request.workspace_id)
        authorize_workspace_action(uow, identity, workspace_id, "digital_employee.invoke")
        plan = ExecutionPlan(
            ticket_id=str(uuid4()),
            workspace_id=request.workspace_id,
            employee_id=request.employee_id,
            actor=f"user:{identity.user_id}",
            action=request.action,
            trace_id=request.trace_id,
            idempotency_key=request.idempotency_key,
            state=ExecutionTicketState.planned,
            budget=request.budget,
            invocations=request.invocations,
        )
        ticket = begin_execution_plan(uow, plan)
        if ticket.status == ExecutionTicketState.planned.value:
            ticket = Stage08ToolGateway().execute_plan(uow, ticket, request.invocations)
        else:
            response.status_code = status.HTTP_200_OK
        _commit_if_sqlalchemy(uow)
    except (PlatformValidationError, Stage06AuthorizationError, ValueError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _runtime_http_error(exc) from exc
    except Stage08ToolGatewayError as exc:
        _rollback_if_sqlalchemy(uow)
        raise HTTPException(
            status_code=422,
            detail=error_detail(exc.code, exc.code),
        ) from exc

    if ticket.status not in _TERMINAL_RESPONSE_STATES:
        raise HTTPException(
            status_code=409,
            detail=error_detail("stage08_ticket_not_terminal", "stage08_ticket_not_terminal"),
        )
    return RuntimeExecutionPlanResponse(
        ticket_id=str(ticket.id),
        status=ticket.status,
        tool_summary=ticket.tool_summary,
    )


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _rollback_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.rollback()


def _runtime_http_error(
    exc: PlatformValidationError | Stage06AuthorizationError | ValueError,
) -> HTTPException:
    if isinstance(exc, Stage06AuthorizationError):
        status_code = 404 if exc.code.endswith("_not_found") else 403
    elif isinstance(exc, PlatformValidationError) and exc.code in {
        "idempotency_conflict",
        "idempotency_in_progress",
        "stage08_trace_conflict",
    }:
        status_code = 409
    else:
        status_code = 422
    code = getattr(exc, "code", "stage08_runtime_invalid")
    return HTTPException(status_code=status_code, detail=error_detail(code, code))
