from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.errors import error_detail
from app.schemas.stage08_retrieval import (
    KnowledgeReindexRequest,
    KnowledgeReindexResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
)
from app.services.stage08_retrieval import request_knowledge_reindex


class _RedactedRetrievalValidationRoute(APIRoute):
    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def redacted_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=error_detail(
                        "stage08_retrieval_request_invalid",
                        "stage08_retrieval_request_invalid",
                    ),
                ) from exc

        return redacted_route_handler


router = APIRouter(
    prefix="/api/stage08/knowledge",
    tags=["stage08-retrieval"],
    route_class=_RedactedRetrievalValidationRoute,
)


@router.post(
    "/reindex",
    response_model=KnowledgeReindexResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def reindex_knowledge_source(
    request: KnowledgeReindexRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> KnowledgeReindexResponse:
    try:
        workspace_id = UUID(request.workspace_id)
        source_id = UUID(request.knowledge_source_id)
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "member.manage",
        )
        receipt = request_knowledge_reindex(
            uow,
            workspace_id,
            source_id,
            actor=actor,
            idempotency_key=request.idempotency_key,
            trace_id=request.trace_id,
            now=datetime.now(UTC),
        )
        _commit_if_sqlalchemy(uow)
        return KnowledgeReindexResponse(
            ticket_id=str(receipt.ticket_id),
            status="accepted",
        )
    except (PlatformValidationError, Stage06AuthorizationError, ValueError) as exc:
        _rollback_if_sqlalchemy(uow)
        raise _retrieval_http_error(exc) from exc


def _commit_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _rollback_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.rollback()


def _retrieval_http_error(
    exc: PlatformValidationError | Stage06AuthorizationError | ValueError,
) -> HTTPException:
    code = getattr(exc, "code", "stage08_retrieval_request_invalid")
    if isinstance(exc, Stage06AuthorizationError) or code == "knowledge_reindex_forbidden":
        status_code = 403
        code = "knowledge_reindex_forbidden"
    elif code in {
        "idempotency_conflict",
        "idempotency_in_progress",
        "knowledge_reindex_source_invalid",
        "knowledge_reindex_replay_invalid",
    }:
        status_code = 409
    else:
        status_code = 422
        code = "stage08_retrieval_request_invalid"
    return HTTPException(status_code=status_code, detail=error_detail(code, code))
