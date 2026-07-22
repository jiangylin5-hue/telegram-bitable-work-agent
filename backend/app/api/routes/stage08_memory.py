from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.schemas.stage08_memory import (
    MemoryCandidateRevokeRequest,
    MemoryCandidateRevokeResponse,
    MemoryListResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import PlatformValidationError, Stage06PlatformUnitOfWork
from app.services.stage08_memory import list_memory_projections, revoke_memory_candidate


class _RedactedMemoryValidationRoute(APIRoute):
    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def redacted_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=error_detail(
                        "stage08_memory_request_invalid",
                        "stage08_memory_request_invalid",
                    ),
                ) from exc

        return redacted_route_handler


router = APIRouter(
    prefix="/api/stage08/memory",
    tags=["stage08-memory"],
    route_class=_RedactedMemoryValidationRoute,
)


@router.get("", response_model=MemoryListResponse)
def list_memory(
    workspace_id: str = Query(min_length=1, max_length=120),
    status: Literal["active"] = Query(default="active"),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> MemoryListResponse:
    try:
        parsed_workspace_id = UUID(workspace_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            parsed_workspace_id,
            "workspace.read",
        )
        items = list_memory_projections(
            uow,
            parsed_workspace_id,
            actor=actor,
            now=datetime.now(UTC),
        )
        _commit_if_sqlalchemy(uow)
        return MemoryListResponse(items=items)
    except (PlatformValidationError, Stage06AuthorizationError, ValueError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _memory_http_error(exc) from exc


@router.post(
    "/extractions/{candidate_id}/revoke",
    response_model=MemoryCandidateRevokeResponse,
)
def revoke_memory_extraction(
    candidate_id: UUID,
    request: MemoryCandidateRevokeRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> MemoryCandidateRevokeResponse:
    try:
        candidate = uow.get_memory_extraction_candidate(candidate_id)
        if candidate is None:
            raise PlatformValidationError(
                "memory_candidate_not_found",
                "memory_candidate_not_found",
            )
        actor = authorize_workspace_action(
            uow,
            identity,
            candidate.workspace_id,
            "member.manage",
        )
        result = revoke_memory_candidate(
            uow,
            candidate_id,
            actor=actor,
            expected_version=request.expected_version,
            now=datetime.now(UTC),
        )
        _commit_if_sqlalchemy(uow)
        return MemoryCandidateRevokeResponse(
            candidate_status=result.candidate_status,
            candidate_version=result.candidate_version,
            memory_status=result.memory_status,
        )
    except (PlatformValidationError, Stage06AuthorizationError, ValueError) as exc:
        if (
            isinstance(exc, PlatformValidationError)
            and exc.code in {
                "memory_candidate_source_invalid",
                "memory_candidate_expired",
            }
        ):
            _commit_if_sqlalchemy(uow)
        else:
            _rollback_if_sqlalchemy(uow)
        raise _memory_http_error(exc) from exc


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _rollback_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.rollback()


def _memory_http_error(
    exc: PlatformValidationError | Stage06AuthorizationError | ValueError,
) -> HTTPException:
    code = getattr(exc, "code", "stage08_memory_request_invalid")
    if isinstance(exc, Stage06AuthorizationError):
        status_code = 404 if exc.code == "workspace_not_found" else 403
    elif code == "memory_candidate_not_found":
        status_code = 404
    elif code in {
        "actor_not_workspace_member",
        "memory_candidate_revoke_forbidden",
        "memory_candidate_workspace_denied",
        "memory_candidate_workspace_inactive",
    }:
        status_code = 403
    elif code in {
        "memory_candidate_invalid_state",
        "memory_candidate_version_conflict",
        "memory_candidate_source_invalid",
        "memory_candidate_expired",
        "memory_candidate_related_item_missing",
        "memory_candidate_related_item_not_revocable",
    }:
        status_code = 409
    else:
        status_code = 422
        code = "stage08_memory_request_invalid"
    return HTTPException(status_code=status_code, detail=error_detail(code, code))
