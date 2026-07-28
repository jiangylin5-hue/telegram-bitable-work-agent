from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
import hashlib
import json
from time import sleep
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage08_collaboration import (
    _require_current_query_scope,
    _safe_view_from_replay,
    complete_assistant_query,
    prepare_assistant_query,
)
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.errors import error_detail
from app.runtime.stage08_collaboration_contracts import validate_assistant_query_safe_view
from app.models.agent_event_runtime import AgentPrivateInput
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.schemas.agent_event_runtime import (
    AgentPrivateInputPayload,
    AgentRunCreateRequest,
    AgentRunCreateResponse,
)
from app.schemas.stage08_collaboration import AssistantQueryRequest
from app.services.agent_event_runtime import (
    AgentEventRuntimeUnitOfWork,
    RuntimeNotFound,
    RuntimeScopeDrift,
    SqlAlchemyAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_orchestrator import (
    SpecialistSafeResult,
    build_authorization_hash,
    dispatch_specialist_command,
    execute_read_only_specialist,
    fail_specialist_command,
)
from app.services.agent_private_inputs import seal_agent_private_input
from app.services.stage06_idempotency import fail_idempotent_operation
from app.services.agent_sse_projection import project_safe_run_events
from app.services.stage06_authorization import Stage06AuthorizationError, authorize_workspace_action
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import PlatformValidationError, Stage06PlatformUnitOfWork


router = APIRouter(prefix="/api/stage10/agent-runs", tags=["stage10-agent-runs"])
_STAGE08_OPERATION = "stage08.assistant.query"


class AgentRunProjectionError(RuntimeError):
    """Safe stored result exists but cannot be validated for projection."""


def get_agent_event_runtime_uow(
    session: Session = Depends(get_session),
) -> AgentEventRuntimeUnitOfWork:
    return SqlAlchemyAgentEventRuntimeUnitOfWork(session)


@router.post("", response_model=AgentRunCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_agent_run_endpoint(
    request: AgentRunCreateRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    platform_uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
    runtime_uow: AgentEventRuntimeUnitOfWork = Depends(get_agent_event_runtime_uow),
) -> AgentRunCreateResponse:
    settings = _require_enabled(request.workspace_id)
    failed_command_id: UUID | None = None
    failed_authorization_hash: str | None = None
    failed_reservation = None
    assistant_request = AssistantQueryRequest.model_validate(
        {
            "workspace_id": str(request.workspace_id),
            "employee_id": str(request.employee_id),
            "intent": request.intent,
            "query": request.query,
            "requested_action": "read_only",
            "target_record_id": (
                None if request.target_record_id is None else str(request.target_record_id)
            ),
            "idempotency_key": request.idempotency_key,
            "skill_id": request.skill_id,
        }
    )
    try:
        prepared = prepare_assistant_query(assistant_request, identity, platform_uow)
        authorization_hash = build_authorization_hash(
            workspace_id=request.workspace_id,
            employee_id=request.employee_id,
            target_record_id=request.target_record_id,
            actor_user_id=prepared.actor.actor_id,
        )
        run_key_hash = hashlib.sha256(
            (
                f"stage10:{request.workspace_id}:{prepared.actor.actor_id}:"
                f"{request.idempotency_key}"
            ).encode("utf-8")
        ).hexdigest()
        now = datetime.now(UTC)
        creation = create_agent_run(
            runtime_uow,
            workspace_id=request.workspace_id,
            root_employee_id=request.employee_id,
            target_record_id=request.target_record_id,
            scope_hash=authorization_hash,
            idempotency_key_hash=run_key_hash,
            deadline_at=now + timedelta(seconds=90),
            now=now,
        )
        run = creation.run
        if creation.replayed and run.status in {"completed", "degraded", "failed", "cancelled"}:
            _commit(runtime_uow)
            return AgentRunCreateResponse(run_id=run.id, status=run.status, replayed=True)

        idempotency_record = prepared.reservation or platform_uow.get_idempotency_record(
            request.workspace_id,
            _STAGE08_OPERATION,
            request.idempotency_key,
        )
        if idempotency_record is None:
            raise RuntimeError("agent_run_safe_storage_ref_unavailable")
        result_storage_ref = f"stage08-idempotency:{idempotency_record.id}"
        command_id = uuid4()
        private_input_id = uuid4()
        command_storage_ref = (
            f"agent-private-input:{private_input_id}"
            if settings.agent_event_runtime_mode == "redis_worker"
            else result_storage_ref
        )
        command = dispatch_specialist_command(
            runtime_uow,
            run_id=run.id,
            target_capability="platform.tabular.analyse",
            payload_ref=command_storage_ref,
            authorization_hash=authorization_hash,
            now=now,
            command_id=command_id,
        )
        if settings.agent_event_runtime_mode == "redis_worker":
            if settings.agent_runtime_input_key is None:
                raise RuntimeError("agent_private_input_key_unavailable")
            sealed = seal_agent_private_input(
                AgentPrivateInputPayload(
                    actor_user_id=prepared.actor.actor_id,
                    workspace_id=request.workspace_id,
                    employee_id=request.employee_id,
                    intent=request.intent,
                    query=request.query,
                    target_record_id=request.target_record_id,
                    idempotency_key=request.idempotency_key,
                    skill_id=request.skill_id,
                ),
                key_b64=settings.agent_runtime_input_key,
                key_version=settings.agent_runtime_input_key_version,
                run_id=run.id,
                command_id=command.id,
                scope_hash=authorization_hash,
                expires_at=min(
                    run.deadline_at,
                    now + timedelta(seconds=settings.agent_runtime_input_ttl_seconds),
                ),
            )
            runtime_uow.add_private_input(
                AgentPrivateInput(
                    id=private_input_id,
                    run_id=run.id,
                    command_id=command.id,
                    ciphertext=sealed.ciphertext,
                    nonce=sealed.nonce,
                    key_version=sealed.key_version,
                    aad_hash=sealed.aad_hash,
                    scope_hash=sealed.scope_hash,
                    expires_at=sealed.expires_at,
                    consumed_at=None,
                )
            )
        failed_command_id = command.id
        failed_authorization_hash = authorization_hash
        failed_reservation = idempotency_record
        # Persist the accepted run and queued command before invoking the
        # private Stage08 graph.  A worker/process failure can therefore be
        # recovered or safely failed instead of erasing the durable receipt.
        _commit(runtime_uow)

        if settings.agent_event_runtime_mode == "redis_worker":
            return AgentRunCreateResponse(
                run_id=run.id,
                status=run.status,
                replayed=creation.replayed,
            )

        def execute() -> SpecialistSafeResult:
            safe_view = validate_assistant_query_safe_view(
                complete_assistant_query(prepared, platform_uow)
            )
            safe_payload = json.dumps(
                safe_view.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            return SpecialistSafeResult(
                storage_ref=result_storage_ref,
                content_hash=hashlib.sha256(safe_payload.encode("utf-8")).hexdigest(),
                safe_summary=_bounded_summary(safe_view.answer),
                metrics={"citations": len(safe_view.citations)},
            )

        result = execute_read_only_specialist(
            runtime_uow,
            command_id=command.id,
            authorization_hash=authorization_hash,
            worker_id="embedded-stage10-tabular-worker",
            now=datetime.now(UTC),
            execute=execute,
        )
        _commit(runtime_uow)
        return AgentRunCreateResponse(
            run_id=result.run.id,
            status=result.run.status,
            replayed=result.replayed,
        )
    except (Stage06AuthorizationError, PlatformValidationError, ValueError) as exc:
        _rollback(runtime_uow)
        raise _http_error(exc) from exc
    except HTTPException:
        _rollback(runtime_uow)
        raise
    except Exception as exc:
        _rollback(runtime_uow)
        if failed_command_id is not None and failed_authorization_hash is not None:
            try:
                fail_specialist_command(
                    runtime_uow,
                    command_id=failed_command_id,
                    authorization_hash=failed_authorization_hash,
                    worker_id="embedded-stage10-tabular-worker",
                    now=datetime.now(UTC),
                )
                if failed_reservation is not None:
                    fail_idempotent_operation(
                        failed_reservation,
                        failure_code="agent_run_internal_failure",
                    )
                _commit(runtime_uow)
            except Exception:
                _rollback(runtime_uow)
        raise HTTPException(
            status_code=500,
            detail=error_detail("agent_run_internal_failure", "agent_run_internal_failure"),
        ) from exc


@router.get("/{run_id}/events")
def get_agent_run_events(
    run_id: UUID,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    platform_uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
    runtime_uow: AgentEventRuntimeUnitOfWork = Depends(get_agent_event_runtime_uow),
) -> StreamingResponse:
    _require_enabled()
    try:
        after_sequence = _parse_cursor(last_event_id)
        run = runtime_uow.get_run(run_id)
        if run is None:
            raise RuntimeNotFound("agent_run_not_found")
        _require_enabled(run.workspace_id)
        actor = authorize_workspace_action(
            platform_uow,
            identity,
            run.workspace_id,
            "digital_employee.invoke",
        )
        _require_current_query_scope(
            platform_uow,
            workspace_id=run.workspace_id,
            employee_id=run.root_employee_id,
            target_record_id=run.target_record_id,
            requested_action="read_only",
            actor=actor,
        )
        authorization_hash = build_authorization_hash(
            workspace_id=run.workspace_id,
            employee_id=run.root_employee_id,
            target_record_id=run.target_record_id,
            actor_user_id=actor.actor_id,
        )
        events = project_safe_run_events(
            runtime_uow,
            run_id=run.id,
            authorization_hash=authorization_hash,
            after_sequence=after_sequence,
            resolve_safe_view=lambda artifact_ref: _resolve_safe_view(
                runtime_uow,
                platform_uow,
                artifact_ref,
            ),
        )
        return StreamingResponse(
            _encode_live_events(
                events,
                run_id=run.id,
                after_sequence=after_sequence,
                identity=identity,
                platform_uow=platform_uow,
                runtime_uow=runtime_uow,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )
    except (Stage06AuthorizationError, PlatformValidationError, RuntimeScopeDrift) as exc:
        raise HTTPException(
            status_code=403,
            detail=error_detail("agent_run_scope_denied", "agent_run_scope_denied"),
        ) from exc
    except RuntimeNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=error_detail("agent_run_not_found", "agent_run_not_found"),
        ) from exc
    except AgentRunProjectionError as exc:
        raise HTTPException(
            status_code=500,
            detail=error_detail(
                "agent_run_projection_failure",
                "agent_run_projection_failure",
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=error_detail("agent_event_cursor_invalid", "agent_event_cursor_invalid"),
        ) from exc


def _encode_events(events: list[object]) -> Iterator[str]:
    for event in events:
        payload = event.model_dump_json()  # type: ignore[attr-defined]
        yield (
            f"id: {event.sequence}\n"  # type: ignore[attr-defined]
            f"event: {event.event}\n"  # type: ignore[attr-defined]
            f"data: {payload}\n\n"
        )


def _encode_live_events(
    initial_events: list[object],
    *,
    run_id: UUID,
    after_sequence: int,
    identity: Stage06RequestIdentity,
    platform_uow: Stage06PlatformUnitOfWork,
    runtime_uow: AgentEventRuntimeUnitOfWork,
) -> Iterator[str]:
    events = initial_events
    cursor = after_sequence
    while True:
        for encoded in _encode_events(events):
            yield encoded
        if events:
            cursor = max(int(event.sequence) for event in events)  # type: ignore[attr-defined]
        if any(getattr(event, "event", None) == "done" for event in events):
            return
        run = runtime_uow.get_run(run_id)
        if run is None or datetime.now(UTC) >= run.deadline_at + timedelta(seconds=5):
            return
        sleep(0.25)
        _refresh_read_session(runtime_uow)
        try:
            run = runtime_uow.get_run(run_id)
            if run is None:
                return
            actor = authorize_workspace_action(
                platform_uow,
                identity,
                run.workspace_id,
                "digital_employee.invoke",
            )
            _require_current_query_scope(
                platform_uow,
                workspace_id=run.workspace_id,
                employee_id=run.root_employee_id,
                target_record_id=run.target_record_id,
                requested_action="read_only",
                actor=actor,
            )
            authorization_hash = build_authorization_hash(
                workspace_id=run.workspace_id,
                employee_id=run.root_employee_id,
                target_record_id=run.target_record_id,
                actor_user_id=actor.actor_id,
            )
            events = project_safe_run_events(
                runtime_uow,
                run_id=run.id,
                authorization_hash=authorization_hash,
                after_sequence=cursor,
                resolve_safe_view=lambda artifact_ref: _resolve_safe_view(
                    runtime_uow,
                    platform_uow,
                    artifact_ref,
                ),
            )
        except (Stage06AuthorizationError, PlatformValidationError, RuntimeScopeDrift):
            return


def _refresh_read_session(uow: AgentEventRuntimeUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.rollback()
        session.expire_all()


def _parse_cursor(value: str | None) -> int:
    if value is None:
        return 0
    if not value.isascii() or not value.isdigit():
        raise ValueError("agent_event_cursor_invalid")
    cursor = int(value)
    if cursor < 0:
        raise ValueError("agent_event_cursor_invalid")
    return cursor


def _bounded_summary(answer: str) -> str:
    normalized = " ".join(answer.split())
    return normalized[:240] if normalized else "只读分析已完成"


def _resolve_safe_view(
    runtime_uow: AgentEventRuntimeUnitOfWork,
    platform_uow: Stage06PlatformUnitOfWork,
    artifact_ref: UUID,
):
    artifact = runtime_uow.get_artifact(artifact_ref)
    if artifact is None or artifact.validation_status != "validated":
        raise RuntimeNotFound("agent_result_artifact_missing")
    prefix = "stage08-idempotency:"
    if not artifact.storage_ref.startswith(prefix):
        raise RuntimeNotFound("agent_result_storage_ref_invalid")
    try:
        record_id = UUID(artifact.storage_ref.removeprefix(prefix))
    except ValueError as exc:
        raise RuntimeNotFound("agent_result_storage_ref_invalid") from exc
    records = getattr(platform_uow, "idempotency_records", None)
    record = (
        next((item for item in records if item.id == record_id), None)
        if isinstance(records, list)
        else None
    )
    if record is None:
        session = getattr(platform_uow, "session", None)
        if session is not None:
            record = session.get(Stage06IdempotencyRecord, record_id)
    if record is None or record.status != "completed" or record.response_ref is None:
        raise RuntimeNotFound("agent_result_projection_missing")
    try:
        return _safe_view_from_replay(record.response_ref)
    except PlatformValidationError as exc:
        raise AgentRunProjectionError("agent_run_projection_failure") from exc


def _require_enabled(workspace_id: UUID | None = None) -> Settings:
    settings = get_settings()
    if not settings.agent_event_runtime_enabled or (
        workspace_id is not None
        and settings.agent_event_runtime_allowed_workspace_ids
        and str(workspace_id) not in settings.agent_event_runtime_allowed_workspace_ids
    ):
        raise HTTPException(
            status_code=404,
            detail=error_detail("agent_event_runtime_disabled", "agent_event_runtime_disabled"),
        )
    return settings


def _commit(uow: AgentEventRuntimeUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _rollback(uow: AgentEventRuntimeUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.rollback()


def _http_error(exc: Exception) -> HTTPException:
    code = getattr(exc, "code", "agent_run_request_invalid")
    if isinstance(exc, Stage06AuthorizationError):
        return HTTPException(
            status_code=403,
            detail=error_detail("agent_run_scope_denied", "agent_run_scope_denied"),
        )
    if code in {
        "stage08_collaboration_employee_scope_denied",
        "stage08_collaboration_target_scope_denied",
    }:
        return HTTPException(
            status_code=403,
            detail=error_detail("agent_run_scope_denied", "agent_run_scope_denied"),
        )
    if code in {"idempotency_conflict", "idempotency_in_progress"}:
        return HTTPException(status_code=409, detail=error_detail(code, code))
    return HTTPException(
        status_code=422,
        detail=error_detail("agent_run_request_invalid", "agent_run_request_invalid"),
    )


__all__ = ["get_agent_event_runtime_uow", "router"]
