from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_stage06_request_identity
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.agents.stage06_skills import (
    STAGE06_SKILL_MANIFEST_VERSION,
    get_stage06_skill_manifest,
)
from app.agents.stage06_skill_matching import build_stage06_skill_evidence
from app.core.config import Settings, get_settings
from app.core.errors import error_detail
from app.runtime.stage08_collaboration_contracts import (
    AssistantQueryCommand,
    AssistantQuerySafeCitation,
    AssistantQuerySafeView,
    AssistantSkillSafeSummary,
    Stage08CollaborationContractFactory,
    validate_assistant_query_safe_view,
)
from app.schemas.stage08_collaboration import (
    AssistantQueryRequest,
    AssistantQueryResponse,
    AssistantSkillCatalogItem,
    AssistantSkillCatalogResponse,
    AssistantStreamAnswerDelta,
    AssistantStreamDone,
    AssistantStreamError,
    AssistantStreamEvent,
    AssistantStreamResult,
    AssistantStreamStatus,
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
from app.services.stage08_collaboration import (
    Stage08CollaborationDependencies,
    create_stage08_runtime_control,
    remaining_stage08_runtime_seconds,
    run_stage08_collaboration,
)
from app.services.stage08_openrouter_analysis_provider import (
    OpenRouterStage08AnalysisProvider,
)
from app.services.stage09_skill_launcher import resolve_stage09_skill_catalog


_OPERATION = "stage08.assistant.query"
_REPLAY_PROJECTION_VERSION = "stage08-assistant-query-replay.v1"
_INVALID_CODE = "stage08_collaboration_request_invalid"
_INTERNAL_CODE = "stage08_collaboration_internal_failure"
_SCOPE_CODE = "stage08_collaboration_scope_denied"
_ANSWER_BOUNDARY_RE = re.compile(r"\n{2,}|(?<=[.!?。！？])\s+")
_AUTO_SKILL_INTENTS = {
    "platform-base": frozenset(
        {"business_fact", "memory_lookup", "mixed", "general_advice"}
    ),
    "platform-tabular-analysis": frozenset({"business_fact", "mixed"}),
    "platform-task": frozenset({"business_fact", "mixed"}),
    "platform-telegram-im": frozenset({"mixed"}),
}


@dataclass(frozen=True, slots=True)
class PreparedAssistantQuery:
    command: AssistantQueryCommand | None
    actor: Actor
    reservation: object | None
    replay_safe_view: AssistantQuerySafeView | None


class _AssistantQueryCompletionError(RuntimeError):
    pass


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


@router.get("/skills", response_model=AssistantSkillCatalogResponse)
def get_assistant_skill_catalog(
    workspace_id: UUID,
    employee_id: UUID,
    target_record_id: UUID | None = None,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> AssistantSkillCatalogResponse:
    try:
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "digital_employee.invoke",
        )
        catalog = resolve_stage09_skill_catalog(
            uow,
            workspace_id=workspace_id,
            employee_id=employee_id,
            target_record_id=target_record_id,
            actor=actor,
        )
        return AssistantSkillCatalogResponse(
            manifest_version=catalog.manifest_version,
            default_selection=catalog.default_selection,
            skills=tuple(
                AssistantSkillCatalogItem(
                    skill_id=item.skill_id,
                    label=item.label,
                    description=item.description,
                    enabled=item.enabled,
                    disabled_reason=item.disabled_reason,
                    supported_intents=item.supported_intents,
                    supported_actions=item.supported_actions,
                    confirmation_policy=item.confirmation_policy,
                )
                for item in catalog.skills
            ),
        )
    except (Stage06AuthorizationError, PlatformValidationError, ValueError) as exc:
        raise _collaboration_http_error(exc) from exc


@router.post("/query", response_model=AssistantQueryResponse)
def query_assistant(
    request: AssistantQueryRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> AssistantQuerySafeView:
    try:
        return execute_assistant_query(request, identity, uow)
    except (Stage06AuthorizationError, PlatformValidationError, ValueError) as exc:
        raise _collaboration_http_error(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=error_detail(_INTERNAL_CODE, _INTERNAL_CODE),
        ) from exc


@router.post("/query-stream")
def query_assistant_stream(
    request: AssistantQueryRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> StreamingResponse:
    request_id = uuid4().hex
    return StreamingResponse(
        encode_sse_events(
            iter_assistant_stream_events(
                request,
                identity,
                uow,
                request_id,
            )
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


def prepare_assistant_query(
    request: AssistantQueryRequest,
    identity: Stage06RequestIdentity,
    uow: Stage06PlatformUnitOfWork,
) -> PreparedAssistantQuery:
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
        skill_profile = _resolve_assistant_skill_profile(
            request,
            uow,
            workspace_id=workspace_id,
            employee_id=employee_id,
            target_record_id=target_record_id,
            actor=actor,
        )
        fingerprint = _query_fingerprint(
            request,
            identity.user_id,
            skill_profile=skill_profile,
        )
        decision = _begin_query_idempotency(
            uow,
            workspace_id=workspace_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=fingerprint,
        )
        reservation = decision.record if decision.status == "started" else None
        if decision.status == "replay":
            safe_view = _safe_view_from_replay(decision.response_ref)
            return PreparedAssistantQuery(
                command=None,
                actor=actor,
                reservation=None,
                replay_safe_view=safe_view,
            )
        command = Stage08CollaborationContractFactory.command(
            workspace_id=workspace_id,
            employee_id=employee_id,
            actor_user_id=identity.user_id,
            intent=request.intent,
            query=request.query,
            requested_action=request.requested_action,
            target_record_id=target_record_id,
            idempotency_key=request.idempotency_key,
            skill_profile=skill_profile,
        )
        return PreparedAssistantQuery(
            command=command,
            actor=actor,
            reservation=reservation,
            replay_safe_view=None,
        )
    except Exception:
        _rollback_if_sqlalchemy(uow)
        _discard_in_memory_reservation(uow, reservation)
        raise


def complete_assistant_query(
    prepared: PreparedAssistantQuery,
    uow: Stage06PlatformUnitOfWork,
) -> AssistantQuerySafeView:
    try:
        if prepared.replay_safe_view is not None:
            safe_view = validate_assistant_query_safe_view(
                prepared.replay_safe_view
            )
            _commit_if_sqlalchemy(uow)
            return safe_view
        if prepared.command is None or prepared.reservation is None:
            raise RuntimeError(_INTERNAL_CODE)
        dependencies, runtime_control = _stage08_runtime_dependencies(get_settings())
        result = run_stage08_collaboration(
            uow,
            prepared.command,
            prepared.actor,
            deps=dependencies,
            now=datetime.now(UTC),
            runtime_control=runtime_control,
        )
        safe_view = validate_assistant_query_safe_view(result)
        skill_summary = Stage08CollaborationContractFactory.safe_skill_summary(
            prepared.command
        )
        if skill_summary is not None:
            safe_view = safe_view.model_copy(update={"skill": skill_summary})
        complete_idempotent_operation(
            prepared.reservation,
            response_ref=_safe_replay_projection(safe_view),
        )
        _commit_if_sqlalchemy(uow)
        return safe_view
    except Exception as exc:
        _rollback_if_sqlalchemy(uow)
        _discard_in_memory_reservation(uow, prepared.reservation)
        raise _AssistantQueryCompletionError(_INTERNAL_CODE) from exc


def execute_assistant_query(
    request: AssistantQueryRequest,
    identity: Stage06RequestIdentity,
    uow: Stage06PlatformUnitOfWork,
) -> AssistantQuerySafeView:
    return complete_assistant_query(
        prepare_assistant_query(request, identity, uow),
        uow,
    )


def iter_assistant_stream_events(
    request: AssistantQueryRequest,
    identity: Stage06RequestIdentity,
    uow: Stage06PlatformUnitOfWork,
    request_id: str,
) -> Iterator[AssistantStreamEvent]:
    sequence = 1
    prepared: PreparedAssistantQuery | None = None
    completion_started = False
    yield AssistantStreamStatus(
        event="status",
        sequence=sequence,
        request_id=request_id,
        phase="authorizing",
    )
    sequence += 1
    try:
        prepared = prepare_assistant_query(request, identity, uow)
        if prepared.replay_safe_view is None:
            yield AssistantStreamStatus(
                event="status",
                sequence=sequence,
                request_id=request_id,
                phase="analysing",
            )
            sequence += 1
        completion_started = True
        safe_view = complete_assistant_query(prepared, uow)
        for chunk in _split_safe_answer(safe_view.answer):
            yield AssistantStreamAnswerDelta(
                event="answer_delta",
                sequence=sequence,
                request_id=request_id,
                text=chunk,
            )
            sequence += 1
        yield AssistantStreamResult(
            event="result",
            sequence=sequence,
            request_id=request_id,
            safe_view=safe_view,
        )
        sequence += 1
        yield AssistantStreamStatus(
            event="status",
            sequence=sequence,
            request_id=request_id,
            phase="completed",
        )
        sequence += 1
        yield AssistantStreamDone(
            event="done",
            sequence=sequence,
            request_id=request_id,
        )
    except (Stage06AuthorizationError, PlatformValidationError, ValueError) as exc:
        code = _stream_error_code(exc)
        yield AssistantStreamError(
            event="error",
            sequence=sequence,
            request_id=request_id,
            code=code,
            message=code,
        )
    except Exception:
        yield AssistantStreamError(
            event="error",
            sequence=sequence,
            request_id=request_id,
            code=_INTERNAL_CODE,
            message=_INTERNAL_CODE,
        )
    finally:
        if prepared is not None and not completion_started:
            _rollback_if_sqlalchemy(uow)
            _discard_in_memory_reservation(uow, prepared.reservation)


def encode_sse_events(
    events: Iterator[AssistantStreamEvent],
) -> Iterator[bytes]:
    try:
        for event in events:
            payload = json.dumps(
                event.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"data: {payload}\n\n".encode("utf-8")
    finally:
        close = getattr(events, "close", None)
        if callable(close):
            close()


def _split_safe_answer(answer: str | None) -> Iterator[str]:
    if not answer:
        return
    start = 0
    while len(answer) - start > 512:
        limit = start + 512
        split_at = max(
            (
                match.end()
                for match in _ANSWER_BOUNDARY_RE.finditer(answer, start, limit)
                if match.end() > start
            ),
            default=limit,
        )
        yield answer[start:split_at]
        start = split_at
    if start < len(answer):
        yield answer[start:]


def _stream_error_code(
    exc: Stage06AuthorizationError | PlatformValidationError | ValueError,
) -> str:
    mapped = _collaboration_http_error(exc)
    if mapped.status_code == 403:
        return _SCOPE_CODE
    detail = mapped.detail
    if (
        isinstance(detail, dict)
        and isinstance(detail.get("code"), str)
        and detail["code"]
    ):
        return detail["code"]
    return _INVALID_CODE


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


def _query_fingerprint(
    request: AssistantQueryRequest,
    actor_user_id: str,
    *,
    skill_profile: object | None = None,
) -> str:
    normalized_query = " ".join(request.query.split())
    payload: dict[str, object] = {
        "workspace_id": request.workspace_id,
        "employee_id": request.employee_id,
        "actor_hash": hashlib.sha256(actor_user_id.encode("utf-8")).hexdigest(),
        "intent": request.intent,
        "query_hash": hashlib.sha256(normalized_query.encode("utf-8")).hexdigest(),
        "requested_action": request.requested_action,
        "target_record_id": request.target_record_id,
    }
    if skill_profile is not None:
        payload.update(
            {
                "primary_skill_id": skill_profile.primary_skill_id,
                "skill_selection_mode": skill_profile.selection_mode,
                "skill_manifest_version": skill_profile.manifest_version,
            }
        )
    return fingerprint_request(
        payload
    )


def _resolve_assistant_skill_profile(
    request: AssistantQueryRequest,
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    target_record_id: UUID | None,
    actor: Actor,
) -> object:
    catalog = resolve_stage09_skill_catalog(
        uow,
        workspace_id=workspace_id,
        employee_id=employee_id,
        target_record_id=target_record_id,
        actor=actor,
    )
    if request.skill_id is None:
        skill_id = _auto_primary_skill_id(catalog, request)
        selection_mode = "auto"
        profile_intents = (request.intent,)
        profile_actions = (
            ("general_advice", "deny")
            if request.intent == "general_advice"
            else (request.requested_action, "deny")
        )
    else:
        skill_id = request.skill_id
        selection_mode = "explicit"
        profile_intents = (request.intent,)
        profile_actions = None
    item = next((value for value in catalog.skills if value.skill_id == skill_id), None)
    if (
        item is None
        or not item.enabled
        or (selection_mode == "explicit" and request.intent not in item.supported_intents)
        or request.requested_action not in item.supported_actions
    ):
        raise PlatformValidationError(
            "stage09_skill_resolution_denied",
            "stage09_skill_resolution_denied",
        )
    manifest = get_stage06_skill_manifest(item.skill_id)
    if (
        manifest.status != "active"
        or manifest.skill_id != item.skill_id
        or catalog.manifest_version != STAGE06_SKILL_MANIFEST_VERSION
    ):
        raise PlatformValidationError(
            "stage09_skill_resolution_denied",
            "stage09_skill_resolution_denied",
        )
    supporting = {
        "platform-base": ("platform-shared-policy",),
        "platform-tabular-analysis": ("platform-base", "platform-shared-policy"),
        "platform-task": ("platform-base", "platform-shared-policy"),
        "platform-telegram-im": ("platform-base", "platform-shared-policy"),
    }[item.skill_id]
    if request.requested_action == "draft_update":
        supporting = (*supporting, "platform-approval")
    return Stage08CollaborationContractFactory.resolved_skill_profile(
        manifest_version=catalog.manifest_version,
        primary_skill_id=item.skill_id,
        source_skill=manifest.source_skill,
        selection_mode=selection_mode,
        supporting_skill_ids=supporting,
        allowed_intents=profile_intents,
        allowed_provider_actions=(
            (*item.supported_actions, "deny")
            if profile_actions is None
            else profile_actions
        ),
        manifest_allowed_actions=manifest.allowed_actions,
        output_contract=manifest.output_contract,
        confirmation_policy=manifest.confirmation_policy,
        safe_label=item.label,
    )


def _auto_primary_skill_id(catalog: object, request: AssistantQueryRequest) -> str:
    evidence = build_stage06_skill_evidence(
        action=(
            "draft_update"
            if request.requested_action == "draft_update"
            else "query"
        ),
        source_text=request.query,
        source_context={"base_id": "server_resolved"},
    )
    selected = evidence.get("selected_skills")
    if type(selected) is not list:
        raise PlatformValidationError(
            "stage09_skill_resolution_denied",
            "stage09_skill_resolution_denied",
        )
    catalog_by_id = {item.skill_id: item for item in catalog.skills}
    compatible: list[tuple[float, str]] = []
    for candidate in selected:
        if type(candidate) is not dict:
            continue
        skill_id = candidate.get("skill_id")
        confidence = candidate.get("confidence")
        item = catalog_by_id.get(skill_id)
        if item is None:
            continue
        if request.requested_action not in item.supported_actions:
            continue
        if request.intent not in _AUTO_SKILL_INTENTS.get(skill_id, frozenset()):
            continue
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(confidence_value):
            continue
        compatible.append((confidence_value, skill_id))
    if compatible:
        highest = max(confidence for confidence, _ in compatible)
        winners = {
            skill_id for confidence, skill_id in compatible if confidence == highest
        }
        if len(winners) == 1:
            winner = next(iter(winners))
            if catalog_by_id[winner].enabled:
                return winner
    raise PlatformValidationError(
        "stage09_skill_resolution_denied",
        "stage09_skill_resolution_denied",
    )


def _stage08_runtime_dependencies(
    settings: Settings,
) -> tuple[Stage08CollaborationDependencies, object]:
    runtime_control = create_stage08_runtime_control()
    if not (
        settings.llm_enabled
        and settings.agent_workflow_mode == "real_openrouter"
    ):
        return Stage08CollaborationDependencies(), runtime_control
    return (
        Stage08CollaborationDependencies(
            analysis_provider=OpenRouterStage08AnalysisProvider(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model_name=settings.openrouter_model,
                remaining_deadline_seconds=lambda: remaining_stage08_runtime_seconds(
                    runtime_control
                ),
            )
        ),
        runtime_control,
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
        "skill",
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
    skill_value = response_ref.get("skill")
    if (
        type(status_value) is not str
        or (answer_value is not None and type(answer_value) is not str)
        or type(citations_value) is not list
        or type(degradation_value) is not list
        or not all(type(value) is str for value in degradation_value)
        or (draft_value is not None and type(draft_value) is not str)
        or type(skill_value) is not dict
        or set(skill_value) != {
            "skill_id",
            "label",
            "manifest_version",
            "selection_mode",
        }
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
        skill = AssistantSkillSafeSummary(
            skill_id=skill_value["skill_id"],
            label=skill_value["label"],
            manifest_version=skill_value["manifest_version"],
            selection_mode=skill_value["selection_mode"],
        )
        return validate_assistant_query_safe_view(
            AssistantQuerySafeView(
                status=status_value,
                answer=answer_value,
                citations=tuple(citations),
                degradation_codes=tuple(degradation_value),
                draft_id=draft_id,
                skill=skill,
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
        "skill": None
        if safe_view.skill is None
        else safe_view.skill.model_dump(mode="json"),
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
        "stage09_skill_catalog_scope_denied",
    }:
        status_code = 403
        code = _SCOPE_CODE
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


__all__ = [
    "PreparedAssistantQuery",
    "complete_assistant_query",
    "execute_assistant_query",
    "iter_assistant_stream_events",
    "prepare_assistant_query",
    "router",
]
