from datetime import UTC, datetime
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.runtime.stage08_collaboration_contracts import (
    AssistantQuerySafeCitation,
    AssistantQuerySafeView,
    Stage08CollaborationContractFactory,
    validate_assistant_query_safe_view,
)
from app.schemas.stage08_collaboration import (
    AssistantQueryRequest,
    AssistantQueryResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
)
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    read_record_for_actor,
)
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)
from app.services.stage08_collaboration import run_stage08_collaboration


_OPERATION = "stage08.assistant.query"
_REPLAY_PROJECTION_VERSION = "stage08-assistant-query-replay.v1"
_INVALID_CODE = "stage08_collaboration_request_invalid"
_INTERNAL_CODE = "stage08_collaboration_internal_failure"


class _RedactedCollaborationValidationRoute(APIRoute):
    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def redacted_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=error_detail(_INVALID_CODE, _INVALID_CODE),
                ) from exc

        return redacted_route_handler


router = APIRouter(
    prefix="/api/stage08/assistant",
    tags=["stage08-assistant"],
    route_class=_RedactedCollaborationValidationRoute,
)


@router.post("/query", response_model=AssistantQueryResponse)
def query_assistant(
    request: AssistantQueryRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> AssistantQuerySafeView:
    reservation = None
    try:
        workspace_id = UUID(request.workspace_id)
        employee_id = UUID(request.employee_id)
        target_record_id = (
            None if request.target_record_id is None else UUID(request.target_record_id)
        )
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.invoke",
        )
        _require_current_query_scope(
            uow,
            workspace_id=workspace_id,
            employee_id=employee_id,
            target_record_id=target_record_id,
            requested_action=request.requested_action,
            actor=actor,
        )
        fingerprint = _query_fingerprint(request, identity.user_id)
        decision = _begin_query_idempotency(
            uow,
            workspace_id=workspace_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=fingerprint,
        )
        reservation = decision.record if decision.status == "started" else None
        if decision.status == "replay":
            safe_view = _safe_view_from_replay(decision.response_ref)
            _commit_if_sqlalchemy(uow)
            return safe_view
        command = Stage08CollaborationContractFactory.command(
            workspace_id=workspace_id,
            employee_id=employee_id,
            actor_user_id=identity.user_id,
            intent=request.intent,
            query=request.query,
            requested_action=request.requested_action,
            target_record_id=target_record_id,
            idempotency_key=request.idempotency_key,
        )
    except (Stage06AuthorizationError, PlatformValidationError, ValueError) as exc:
        _rollback_if_sqlalchemy(uow)
        _discard_in_memory_reservation(uow, reservation)
        raise _collaboration_http_error(exc) from exc
    except Exception as exc:
        _rollback_if_sqlalchemy(uow)
        _discard_in_memory_reservation(uow, reservation)
        raise HTTPException(
            status_code=500,
            detail=error_detail(_INTERNAL_CODE, _INTERNAL_CODE),
        ) from exc

    try:
        result = run_stage08_collaboration(
            uow,
            command,
            actor,
            now=datetime.now(UTC),
        )
        safe_view = validate_assistant_query_safe_view(result)
        complete_idempotent_operation(
            decision.record,
            response_ref=_safe_replay_projection(safe_view),
        )
        _commit_if_sqlalchemy(uow)
        return safe_view
    except Exception as exc:
        _rollback_if_sqlalchemy(uow)
        _discard_in_memory_reservation(uow, reservation)
        raise HTTPException(
            status_code=500,
            detail=error_detail(_INTERNAL_CODE, _INTERNAL_CODE),
        ) from exc


def _require_current_query_scope(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    target_record_id: UUID | None,
    requested_action: str,
    actor: Actor,
) -> None:
    workspace = uow.get_workspace(workspace_id)
    if workspace is None:
        raise PlatformValidationError(
            "stage08_collaboration_workspace_not_found",
            "stage08_collaboration_workspace_not_found",
        )
    employee = uow.get_digital_employee(employee_id)
    if employee is None or employee.workspace_id != workspace_id:
        raise PlatformValidationError(
            "stage08_collaboration_employee_not_found",
            "stage08_collaboration_employee_not_found",
        )
    employee_base = uow.get_base(employee.base_id)
    active_members = [
        member
        for member in uow.list_workspace_members(workspace_id)
        if member.user_id == actor.actor_id and member.status == "active"
    ]
    actions = employee.allowed_actions
    required_action = "draft_update" if requested_action == "draft_update" else None
    if (
        workspace.status != "active"
        or employee.status != "active"
        or employee_base is None
        or employee_base.status != "active"
        or employee_base.workspace_id != workspace_id
        or len(active_members) != 1
        or not is_member_eligible_for_employee(uow, employee, actor.actor_id)
        or not isinstance(actions, list)
        or not all(isinstance(value, str) for value in actions)
        or len(actions) != len(set(actions))
        or not isinstance(employee.accessible_tables, list)
        or not all(isinstance(value, str) for value in employee.accessible_tables)
        or (
            required_action is None
            and not {"query", "summarize"}.intersection(actions)
        )
        or (required_action is not None and required_action not in actions)
    ):
        raise PlatformValidationError(
            "stage08_collaboration_employee_scope_denied",
            "stage08_collaboration_employee_scope_denied",
        )
    if target_record_id is None:
        return
    record = uow.get_record(target_record_id)
    if record is None:
        raise PlatformValidationError(
            "stage08_collaboration_target_not_found",
            "stage08_collaboration_target_not_found",
        )
    table = uow.get_table(record.table_id)
    base = None if table is None else uow.get_base(table.base_id)
    if (
        record.record_status != "active"
        or table is None
        or table.status != "active"
        or base is None
        or base.status != "active"
        or base.workspace_id != workspace_id
        or str(table.id) not in set(employee.accessible_tables)
    ):
        raise PlatformValidationError(
            "stage08_collaboration_target_scope_denied",
            "stage08_collaboration_target_scope_denied",
        )
    try:
        visible = read_record_for_actor(uow, target_record_id, actor=actor)
    except PlatformValidationError as exc:
        raise PlatformValidationError(
            "stage08_collaboration_target_scope_denied",
            "stage08_collaboration_target_scope_denied",
        ) from exc
    if visible.get("record_status") != "active":
        raise PlatformValidationError(
            "stage08_collaboration_target_scope_denied",
            "stage08_collaboration_target_scope_denied",
        )


def _query_fingerprint(request: AssistantQueryRequest, actor_user_id: str) -> str:
    normalized_query = " ".join(request.query.split())
    return fingerprint_request(
        {
            "workspace_id": request.workspace_id,
            "employee_id": request.employee_id,
            "actor_hash": hashlib.sha256(actor_user_id.encode("utf-8")).hexdigest(),
            "intent": request.intent,
            "query_hash": hashlib.sha256(
                normalized_query.encode("utf-8")
            ).hexdigest(),
            "requested_action": request.requested_action,
            "target_record_id": request.target_record_id,
        }
    )


def _begin_query_idempotency(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    idempotency_key: str,
    request_fingerprint: str,
):
    trace_id = idempotency_trace_id(
        _OPERATION,
        request_fingerprint,
        idempotency_key,
    )
    try:
        decision = begin_idempotent_operation(
            uow,
            workspace_id=workspace_id,
            operation=_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            trace_id=trace_id,
        )
        session = getattr(uow, "session", None)
        if session is not None and decision.status == "started":
            session.flush()
        return decision
    except IntegrityError:
        session = getattr(uow, "session", None)
        if session is None:
            raise
        session.rollback()
        return begin_idempotent_operation(
            uow,
            workspace_id=workspace_id,
            operation=_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            trace_id=trace_id,
        )


def _safe_view_from_replay(response_ref: object) -> AssistantQuerySafeView:
    if type(response_ref) is not dict or set(response_ref) != {
        "version",
        "status",
        "answer",
        "citations",
        "degradation_codes",
        "draft_id",
    }:
        raise PlatformValidationError(
            "stage08_collaboration_replay_invalid",
            "stage08_collaboration_replay_invalid",
        )
    if response_ref.get("version") != _REPLAY_PROJECTION_VERSION:
        raise PlatformValidationError(
            "stage08_collaboration_replay_invalid",
            "stage08_collaboration_replay_invalid",
        )
    status_value = response_ref.get("status")
    answer_value = response_ref.get("answer")
    citations_value = response_ref.get("citations")
    degradation_value = response_ref.get("degradation_codes")
    draft_value = response_ref.get("draft_id")
    if (
        type(status_value) is not str
        or (answer_value is not None and type(answer_value) is not str)
        or type(citations_value) is not list
        or type(degradation_value) is not list
        or not all(type(value) is str for value in degradation_value)
        or (draft_value is not None and type(draft_value) is not str)
    ):
        raise PlatformValidationError(
            "stage08_collaboration_replay_invalid",
            "stage08_collaboration_replay_invalid",
        )
    try:
        citations: list[AssistantQuerySafeCitation] = []
        for citation in citations_value:
            if (
                type(citation) is not dict
                or set(citation) != {"ordinal", "label"}
                or type(citation.get("ordinal")) is not int
                or type(citation.get("label")) is not str
            ):
                raise ValueError("stage08_collaboration_replay_invalid")
            citations.append(
                AssistantQuerySafeCitation(
                    ordinal=citation["ordinal"],
                    label=citation["label"],
                )
            )
        draft_id = None if draft_value is None else UUID(str(draft_value))
        return validate_assistant_query_safe_view(
            AssistantQuerySafeView(
                status=status_value,
                answer=answer_value,
                citations=tuple(citations),
                degradation_codes=tuple(degradation_value),
                draft_id=draft_id,
            )
        )
    except (TypeError, ValueError) as exc:
        raise PlatformValidationError(
            "stage08_collaboration_replay_invalid",
            "stage08_collaboration_replay_invalid",
        ) from exc


def _safe_replay_projection(view: object) -> dict[str, object]:
    safe_view = validate_assistant_query_safe_view(view)
    return {
        "version": _REPLAY_PROJECTION_VERSION,
        "status": safe_view.status,
        "answer": safe_view.answer,
        "citations": [
            {"ordinal": citation.ordinal, "label": citation.label}
            for citation in safe_view.citations
        ],
        "degradation_codes": list(safe_view.degradation_codes),
        "draft_id": None if safe_view.draft_id is None else str(safe_view.draft_id),
    }


def _collaboration_http_error(
    exc: Stage06AuthorizationError | PlatformValidationError | ValueError,
) -> HTTPException:
    code = getattr(exc, "code", _INVALID_CODE)
    if isinstance(exc, Stage06AuthorizationError):
        if exc.code == "workspace_not_found":
            status_code = 404
            code = "stage08_collaboration_workspace_not_found"
        else:
            status_code = 403
            code = "stage08_collaboration_scope_denied"
    elif code in {
        "stage08_collaboration_workspace_not_found",
        "stage08_collaboration_employee_not_found",
        "stage08_collaboration_target_not_found",
    }:
        status_code = 404
    elif code in {
        "stage08_collaboration_employee_scope_denied",
        "stage08_collaboration_target_scope_denied",
    }:
        status_code = 403
    elif code in {
        "idempotency_conflict",
        "idempotency_in_progress",
        "stage08_trace_conflict",
        "stage08_collaboration_replay_invalid",
    }:
        status_code = 409
    else:
        status_code = 422
        code = _INVALID_CODE
    return HTTPException(status_code=status_code, detail=error_detail(code, code))


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _rollback_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.rollback()


def _discard_in_memory_reservation(
    uow: Stage06PlatformUnitOfWork,
    reservation: object | None,
) -> None:
    if getattr(uow, "session", None) is not None or reservation is None:
        return
    records = getattr(uow, "idempotency_records", None)
    if isinstance(records, list) and reservation in records:
        records.remove(reservation)


__all__ = ["router"]
