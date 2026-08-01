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
from app.agents.agent_capability_registry import get_capability
from app.core.config import Settings, durable_action_v1_enabled, get_settings
from app.core.database import get_session
from app.core.errors import error_detail
from app.runtime.stage08_collaboration_contracts import (
    validate_assistant_query_safe_view,
)
from app.models.agent_event_runtime import AgentPrivateInput
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.schemas.agent_event_runtime import (
    AgentPrivateInputPayload,
    AgentRunCreateRequest,
    AgentRunCreateResponse,
)
from app.schemas.agent_grounded_answer_v2 import GroundedComposerResultV2
from app.schemas.agent_task_spec_v2 import PlannerRequestV2
from app.schemas.agent_stage12_runtime import Stage12RuntimeAdmissionRequest
from app.schemas.stage08_collaboration import AssistantQueryRequest
from app.services.agent_event_runtime import (
    AgentEventRuntimeUnitOfWork,
    RuntimeNotFound,
    RuntimeScopeDrift,
    SqlAlchemyAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_field_policy_v2 import build_stage12_action_scope_hash
from app.services.agent_orchestrator import (
    SpecialistCommandDispatch,
    SpecialistSafeResult,
    build_authorization_hash,
    dispatch_specialist_command,
    dispatch_specialist_commands,
    execute_read_only_specialist,
    fail_specialist_command,
)
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.agent_authorized_entity_linker import (
    build_authorized_entity_candidates,
)
from app.services.agent_task_gateway import (
    TaskGatewayRequest,
    TaskPlan,
    TaskPlanNode,
    build_task_plan,
)
from app.services.agent_task_planner_shadow import (
    PlannerShadowObservation,
    planner_shadow_enabled,
    run_task_planner_shadow_with_artifact,
)
from app.services.agent_specialist_shadow_v2 import (
    SpecialistShadowMetricsV1,
    run_typed_specialists_shadow,
    typed_specialists_shadow_enabled,
)
from app.services.authorized_query_shadow import (
    authorized_query_shadow_enabled,
    run_authorized_query_shadow,
)
from app.services.retrieval_v2_shadow import (
    RetrievalShadowCandidateSetV1,
    retrieval_v2_shadow_enabled,
    run_retrieval_v2_shadow,
)
from app.services.retrieval_v2_runtime import (
    build_stage12_query_embedding_provider,
    load_authorized_retrieval_v2,
)
from app.services.agent_private_inputs import seal_agent_private_input
from app.services.agent_stage12_runtime_activation import (
    build_stage12_runtime_profile,
    stage12_runtime_enabled,
)
from app.services.agent_stage12_runtime_admission import admit_stage12_runtime_run
from app.services.audit import record_audit_event
from app.services.stage06_idempotency import fail_idempotent_operation
from app.services.agent_sse_projection import (
    project_grounded_safe_view,
    project_safe_run_events,
)
from app.services.agent_typed_artifacts import read_typed_artifact
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
)
from app.services.stage12_action_runtime import (
    SqlAlchemyStage12ActionRuntimeRepository,
    Stage12ActionRuntimeRepository,
)
from app.services.stage12_action_admission import admit_stage12_action_run


router = APIRouter(prefix="/api/stage10/agent-runs", tags=["stage10-agent-runs"])
_STAGE08_OPERATION = "stage08.assistant.query"
_PLANNER_V2_EMPLOYEE_ACTIONS = {
    "draft_create": "record.create",
    "draft_update": "record.update",
    "task_create": "task.create",
    "reminder_request": "reminder.request",
}


class AgentRunProjectionError(RuntimeError):
    """Safe stored result exists but cannot be validated for projection."""


def get_agent_event_runtime_uow(
    session: Session = Depends(get_session),
) -> AgentEventRuntimeUnitOfWork:
    return SqlAlchemyAgentEventRuntimeUnitOfWork(session)


def get_stage12_action_repository(
    session: Session = Depends(get_session),
) -> Stage12ActionRuntimeRepository:
    return SqlAlchemyStage12ActionRuntimeRepository(session)


def _observe_task_planner_v2_shadow(
    *,
    settings: Settings,
    request: AgentRunCreateRequest,
    actor: object,
    platform_uow: Stage06PlatformUnitOfWork,
    v1_plan: TaskPlan,
) -> PlannerShadowObservation | None:
    if not planner_shadow_enabled(settings, request.workspace_id):
        return None
    try:
        snapshot = build_authorized_schema_snapshot(
            platform_uow,
            workspace_id=request.workspace_id,
            employee_id=request.employee_id,
            actor=actor,
        )
        employee = platform_uow.get_digital_employee(request.employee_id)
        if employee is None:
            return None
        allowed = set(employee.allowed_actions)
        action_kinds = tuple(
            action_kind
            for employee_action, action_kind in _PLANNER_V2_EMPLOYEE_ACTIONS.items()
            if employee_action in allowed
        )
        view_ids = tuple(
            sorted((UUID(value) for value in employee.accessible_views), key=str)
        )
        authorized_entities = build_authorized_entity_candidates(
            platform_uow,
            query=request.query,
            actor=actor,
            workspace_id=request.workspace_id,
            base_id=employee.base_id,
            employee_id=request.employee_id,
            snapshot=snapshot,
            chat_authorized_view_ids=view_ids or None,
            allow_whole_table=not view_ids,
        )
        planner_request = PlannerRequestV2(
            query=request.query,
            authorized_schema=snapshot,
            authorized_entities=authorized_entities,
            clock=datetime.now(UTC),
            timezone_name="Asia/Shanghai",
            allowed_action_kinds=action_kinds,
        )
        trace_suffix = hashlib.sha256(
            (
                f"{request.workspace_id}:{request.employee_id}:"
                f"{request.idempotency_key}"
            ).encode("utf-8")
        ).hexdigest()[:32]

        def observe(observation: PlannerShadowObservation) -> None:
            record_audit_event(
                platform_uow,
                trace_id=f"stage12-shadow:{trace_suffix}",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                event_type="stage12.planner_shadow_observed",
                entity_type="digital_employee",
                entity_id=request.employee_id,
                after_state=observation.model_dump(mode="json"),
            )

        planner_run = run_task_planner_shadow_with_artifact(
            v1_plan,
            planner_request,
            snapshot,
            observer=observe,
        )
        if (
            planner_run.observation.status == "observed"
            and planner_run.task_artifact is not None
            and authorized_query_shadow_enabled(settings, request.workspace_id)
        ):
            query_observation = run_authorized_query_shadow(
                platform_uow,
                actor=actor,
                workspace_id=request.workspace_id,
                employee_id=request.employee_id,
                snapshot=snapshot,
                task_artifact=planner_run.task_artifact,
                authorized_view_ids=view_ids,
            )
            record_audit_event(
                platform_uow,
                trace_id=f"stage12-query-shadow:{trace_suffix}",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                event_type="stage12.authorized_query_shadow_observed",
                entity_type="digital_employee",
                entity_id=request.employee_id,
                after_state=query_observation.model_dump(mode="json"),
            )
        return planner_run.observation
    except Exception:
        # Shadow is observational. Authorization and V1 dispatch remain authoritative.
        return None


def _load_retrieval_v2_shadow_candidates(
    *,
    settings: Settings,
    request: AgentRunCreateRequest,
    actor: object,
    platform_uow: Stage06PlatformUnitOfWork,
) -> RetrievalShadowCandidateSetV1:
    provider = build_stage12_query_embedding_provider(settings)
    try:
        query_embedding = provider.embed_queries((request.query,))[0]
    finally:
        provider.close()
    result = load_authorized_retrieval_v2(
        platform_uow,
        workspace_id=request.workspace_id,
        employee_id=request.employee_id,
        query=request.query,
        actor=actor,
        active_embedding_profile=settings.retrieval_v2_active_profile or "",
        query_embedding=query_embedding,
    )
    return RetrievalShadowCandidateSetV1(
        v1_candidate_ids=(),
        v2_result=result,
    )


def _observe_retrieval_v2_shadow(
    *,
    settings: Settings,
    request: AgentRunCreateRequest,
    actor: object,
    platform_uow: Stage06PlatformUnitOfWork,
) -> None:
    if not retrieval_v2_shadow_enabled(settings, request.workspace_id):
        return
    try:
        observation = run_retrieval_v2_shadow(
            settings=settings,
            workspace_id=request.workspace_id,
            candidate_loader=lambda: _load_retrieval_v2_shadow_candidates(
                settings=settings,
                request=request,
                actor=actor,
                platform_uow=platform_uow,
            ),
        )
        if observation is None:
            return
        trace_suffix = hashlib.sha256(
            (
                f"{request.workspace_id}:{request.employee_id}:"
                f"{request.idempotency_key}"
            ).encode("utf-8")
        ).hexdigest()[:32]
        record_audit_event(
            platform_uow,
            trace_id=f"stage12-retrieval-shadow:{trace_suffix}",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            event_type="stage12.retrieval_v2_shadow_observed",
            entity_type="digital_employee",
            entity_id=request.employee_id,
            after_state=observation.model_dump(mode="json"),
        )
    except Exception:
        # D shadow is audit-only and cannot affect V1 dispatch or response.
        return


def _load_typed_specialists_v2_shadow_metrics(
    *,
    request: AgentRunCreateRequest,
    actor: object,
    platform_uow: Stage06PlatformUnitOfWork,
) -> SpecialistShadowMetricsV1:
    """Injection seam; business runtime materialization remains closed."""

    del request, actor, platform_uow
    raise RuntimeError("typed_specialists_v2_shadow_source_unavailable")


def _observe_typed_specialists_v2_shadow(
    *,
    settings: Settings,
    request: AgentRunCreateRequest,
    actor: object,
    platform_uow: Stage06PlatformUnitOfWork,
) -> None:
    if not typed_specialists_shadow_enabled(settings, request.workspace_id):
        return
    try:
        observation = run_typed_specialists_shadow(
            settings=settings,
            workspace_id=request.workspace_id,
            execute_pipeline=lambda: _load_typed_specialists_v2_shadow_metrics(
                request=request,
                actor=actor,
                platform_uow=platform_uow,
            ),
        )
        if observation is None:
            return
        trace_suffix = hashlib.sha256(
            (
                f"{request.workspace_id}:{request.employee_id}:"
                f"{request.idempotency_key}"
            ).encode("utf-8")
        ).hexdigest()[:32]
        record_audit_event(
            platform_uow,
            trace_id=f"stage12-specialists-shadow:{trace_suffix}",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            event_type="stage12.typed_specialists_v2_shadow_observed",
            entity_type="digital_employee",
            entity_id=request.employee_id,
            after_state=observation.model_dump(mode="json"),
        )
    except Exception:
        # E shadow is audit-only and cannot affect V1 dispatch or response.
        return


@router.post(
    "", response_model=AgentRunCreateResponse, status_code=status.HTTP_202_ACCEPTED
)
def create_agent_run_endpoint(
    request: AgentRunCreateRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    platform_uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
    runtime_uow: AgentEventRuntimeUnitOfWork = Depends(get_agent_event_runtime_uow),
    action_repository: Stage12ActionRuntimeRepository = Depends(
        get_stage12_action_repository
    ),
) -> AgentRunCreateResponse:
    settings = _require_enabled(request.workspace_id)
    stage12_profile = build_stage12_runtime_profile(settings)
    if stage12_runtime_enabled(stage12_profile, workspace_id=request.workspace_id):
        try:
            actor = authorize_workspace_action(
                platform_uow,
                identity,
                request.workspace_id,
                "digital_employee.invoke",
            )
            now = datetime.now(UTC)
            admission = admit_stage12_runtime_run(
                platform_uow,
                runtime_uow,
                action_repository,
                request=Stage12RuntimeAdmissionRequest(
                    run_id=uuid4(),
                    actor_user_id=actor.actor_id,
                    workspace_id=request.workspace_id,
                    digital_employee_id=request.employee_id,
                    intent=_stage08_intent(request.intent),
                    query=request.query,
                    target_record_id=request.target_record_id,
                    idempotency_key=request.idempotency_key,
                    skill_id=request.skill_id,
                    authorization_hash=build_authorization_hash(
                        workspace_id=request.workspace_id,
                        employee_id=request.employee_id,
                        target_record_id=request.target_record_id,
                        actor_user_id=actor.actor_id,
                    ),
                    deadline_at=now + timedelta(seconds=90),
                ),
                settings=settings,
                actor=actor,
            )
            _commit(runtime_uow)
            return AgentRunCreateResponse(
                run_id=admission.run_id,
                status=admission.status,
                replayed=admission.replayed,
            )
        except (Stage06AuthorizationError, PlatformValidationError, ValueError) as exc:
            _rollback(runtime_uow)
            raise _http_error(exc) from exc
        except Exception as exc:
            _rollback(runtime_uow)
            raise HTTPException(
                status_code=500,
                detail=error_detail(
                    "agent_run_internal_failure",
                    "agent_run_internal_failure",
                ),
            ) from exc
    if request.requested_action != "read_only" and durable_action_v1_enabled(
        settings,
        request.workspace_id,
    ):
        try:
            if settings.agent_runtime_input_key is None:
                raise PlatformValidationError(
                    "agent_private_input_key_unavailable",
                    "agent_private_input_key_unavailable",
                )
            actor = authorize_workspace_action(
                platform_uow,
                identity,
                request.workspace_id,
                "digital_employee.invoke",
            )
            result = admit_stage12_action_run(
                platform_uow,
                runtime_uow,
                action_repository,
                request=request,
                actor=actor,
                private_key_b64=settings.agent_runtime_input_key,
                private_key_version=settings.agent_runtime_input_key_version,
                embedded=settings.agent_event_runtime_mode == "embedded",
            )
            _commit(runtime_uow)
            return AgentRunCreateResponse(
                run_id=result.run_id,
                status=result.status,
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
            raise HTTPException(
                status_code=500,
                detail=error_detail(
                    "agent_run_internal_failure", "agent_run_internal_failure"
                ),
            ) from exc
    task_plan = build_task_plan(
        TaskGatewayRequest(
            workspace_id=request.workspace_id,
            employee_id=request.employee_id,
            actor_user_id=identity.user_id,
            intent=request.intent,
            requested_action=request.requested_action,
            query=request.query,
            target_record_id=request.target_record_id,
            idempotency_key=request.idempotency_key,
            skill_id=request.skill_id,
        )
    )
    read_nodes = tuple(
        item
        for item in task_plan.nodes
        if item.capability_id != "platform.action.propose"
    )
    if len(read_nodes) > 1:
        try:
            return _create_multi_specialist_run(
                request=request,
                identity=identity,
                platform_uow=platform_uow,
                runtime_uow=runtime_uow,
                settings=settings,
                task_plan=task_plan,
                nodes=read_nodes,
            )
        except (Stage06AuthorizationError, PlatformValidationError, ValueError) as exc:
            _rollback(runtime_uow)
            raise _http_error(exc) from exc
        except HTTPException:
            _rollback(runtime_uow)
            raise
        except Exception as exc:
            _rollback(runtime_uow)
            raise HTTPException(
                status_code=500,
                detail=error_detail(
                    "agent_run_internal_failure",
                    "agent_run_internal_failure",
                ),
            ) from exc
    failed_command_id: UUID | None = None
    failed_authorization_hash: str | None = None
    failed_reservation = None
    assistant_request = AssistantQueryRequest.model_validate(
        {
            "workspace_id": str(request.workspace_id),
            "employee_id": str(request.employee_id),
            "intent": _stage08_intent(request.intent),
            "query": request.query,
            "requested_action": "read_only",
            "target_record_id": (
                None
                if request.target_record_id is None
                else str(request.target_record_id)
            ),
            "idempotency_key": request.idempotency_key,
            "skill_id": request.skill_id
            or get_capability("platform.tabular.analyse").execution_skill_id,
        }
    )
    try:
        prepared = prepare_assistant_query(assistant_request, identity, platform_uow)
        _observe_task_planner_v2_shadow(
            settings=settings,
            request=request,
            actor=prepared.actor,
            platform_uow=platform_uow,
            v1_plan=task_plan,
        )
        _observe_retrieval_v2_shadow(
            settings=settings,
            request=request,
            actor=prepared.actor,
            platform_uow=platform_uow,
        )
        _observe_typed_specialists_v2_shadow(
            settings=settings,
            request=request,
            actor=prepared.actor,
            platform_uow=platform_uow,
        )
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
        if creation.replayed and run.status in {
            "completed",
            "degraded",
            "failed",
            "cancelled",
        }:
            _commit(runtime_uow)
            return AgentRunCreateResponse(
                run_id=run.id, status=run.status, replayed=True
            )

        idempotency_record = (
            prepared.reservation
            or platform_uow.get_idempotency_record(
                request.workspace_id,
                _STAGE08_OPERATION,
                request.idempotency_key,
            )
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
                    intent=_stage08_intent(request.intent),
                    query=request.query,
                    target_record_id=request.target_record_id,
                    idempotency_key=request.idempotency_key,
                    skill_id=assistant_request.skill_id,
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
            detail=error_detail(
                "agent_run_internal_failure", "agent_run_internal_failure"
            ),
        ) from exc


def _create_multi_specialist_run(
    *,
    request: AgentRunCreateRequest,
    identity: Stage06RequestIdentity,
    platform_uow: Stage06PlatformUnitOfWork,
    runtime_uow: AgentEventRuntimeUnitOfWork,
    settings: Settings,
    task_plan: TaskPlan,
    nodes: tuple[TaskPlanNode, ...],
) -> AgentRunCreateResponse:
    prepared_items: list[tuple[TaskPlanNode, object, AssistantQueryRequest]] = []
    for node in nodes:
        suffix = node.capability_id.removeprefix("platform.").replace(".", "-")
        idempotency_key = (
            request.idempotency_key
            if node.capability_id == "platform.tabular.analyse"
            else f"{request.idempotency_key[:96]}:{suffix}"
        )
        assistant_request = AssistantQueryRequest.model_validate(
            {
                "workspace_id": str(request.workspace_id),
                "employee_id": str(request.employee_id),
                "intent": _stage08_intent(request.intent),
                "query": request.query,
                "requested_action": "read_only",
                "target_record_id": (
                    None
                    if request.target_record_id is None
                    else str(request.target_record_id)
                ),
                "idempotency_key": idempotency_key,
                "skill_id": (
                    request.skill_id
                    if node.capability_id == "platform.tabular.analyse"
                    and request.skill_id is not None
                    else get_capability(node.capability_id).execution_skill_id
                ),
            }
        )
        prepared = prepare_assistant_query(assistant_request, identity, platform_uow)
        prepared_items.append((node, prepared, assistant_request))

    primary_prepared = next(
        prepared
        for node, prepared, _assistant_request in prepared_items
        if node.capability_id == "platform.tabular.analyse"
    )
    _observe_task_planner_v2_shadow(
        settings=settings,
        request=request,
        actor=primary_prepared.actor,
        platform_uow=platform_uow,
        v1_plan=task_plan,
    )
    _observe_retrieval_v2_shadow(
        settings=settings,
        request=request,
        actor=primary_prepared.actor,
        platform_uow=platform_uow,
    )
    _observe_typed_specialists_v2_shadow(
        settings=settings,
        request=request,
        actor=primary_prepared.actor,
        platform_uow=platform_uow,
    )
    authorization_hash = build_authorization_hash(
        workspace_id=request.workspace_id,
        employee_id=request.employee_id,
        target_record_id=request.target_record_id,
        actor_user_id=primary_prepared.actor.actor_id,
    )
    run_key_hash = hashlib.sha256(
        (
            f"stage11:{request.workspace_id}:{primary_prepared.actor.actor_id}:"
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
        workflow_version="stage11.coordination.v1",
    )
    run = creation.run
    if creation.replayed:
        _commit(runtime_uow)
        return AgentRunCreateResponse(run_id=run.id, status=run.status, replayed=True)

    command_specs: list[
        tuple[TaskPlanNode, object, AssistantQueryRequest, UUID, UUID, str]
    ] = []
    dispatches: list[SpecialistCommandDispatch] = []
    for node, prepared, assistant_request in prepared_items:
        reservation = prepared.reservation or platform_uow.get_idempotency_record(
            request.workspace_id,
            _STAGE08_OPERATION,
            assistant_request.idempotency_key,
        )
        if reservation is None:
            raise RuntimeError("agent_run_safe_storage_ref_unavailable")
        command_id = uuid4()
        private_input_id = uuid4()
        storage_ref = f"stage08-idempotency:{reservation.id}"
        payload_ref = (
            f"agent-private-input:{private_input_id}"
            if settings.agent_event_runtime_mode == "redis_worker"
            else storage_ref
        )
        dispatches.append(
            SpecialistCommandDispatch(
                target_capability=node.capability_id,
                payload_ref=payload_ref,
                required=node.required,
                command_id=command_id,
            )
        )
        command_specs.append(
            (
                node,
                prepared,
                assistant_request,
                command_id,
                private_input_id,
                storage_ref,
            )
        )
    commands = dispatch_specialist_commands(
        runtime_uow,
        run_id=run.id,
        dispatches=tuple(dispatches),
        authorization_hash=authorization_hash,
        now=now,
    )

    if settings.agent_event_runtime_mode == "redis_worker":
        if settings.agent_runtime_input_key is None:
            raise RuntimeError("agent_private_input_key_unavailable")
        for command, spec in zip(commands, command_specs, strict=True):
            (
                _node,
                _prepared,
                assistant_request,
                _command_id,
                private_input_id,
                _storage_ref,
            ) = spec
            sealed = seal_agent_private_input(
                AgentPrivateInputPayload(
                    actor_user_id=primary_prepared.actor.actor_id,
                    workspace_id=request.workspace_id,
                    employee_id=request.employee_id,
                    intent=_stage08_intent(request.intent),
                    query=request.query,
                    target_record_id=request.target_record_id,
                    idempotency_key=assistant_request.idempotency_key,
                    skill_id=assistant_request.skill_id,
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
        _commit(runtime_uow)
        return AgentRunCreateResponse(
            run_id=run.id,
            status=run.status,
            replayed=False,
        )

    # Advisory specialists complete first; the primary tabular specialist is
    # deliberately completed last so the user-facing artifact remains a normal
    # AssistantQuerySafeView while Supervisor still waits for every child.
    ordered = sorted(
        zip(commands, command_specs, strict=True),
        key=lambda item: item[0].target_capability == "platform.tabular.analyse",
    )
    result = None
    for command, spec in ordered:
        (
            _node,
            prepared,
            _assistant_request,
            _command_id,
            _private_input_id,
            storage_ref,
        ) = spec

        def execute(
            prepared_query=prepared,
            result_storage_ref=storage_ref,
        ) -> SpecialistSafeResult:
            safe_view = validate_assistant_query_safe_view(
                complete_assistant_query(prepared_query, platform_uow)
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
            worker_id=f"embedded-{command.target_capability}",
            now=datetime.now(UTC),
            execute=execute,
        )
    _commit(runtime_uow)
    if result is None:
        raise RuntimeError("agent_run_result_missing")
    return AgentRunCreateResponse(
        run_id=result.run.id,
        status=result.run.status,
        replayed=result.replayed,
    )


@router.get("/{run_id}/events")
def get_agent_run_events(
    run_id: UUID,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    platform_uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
    runtime_uow: AgentEventRuntimeUnitOfWork = Depends(get_agent_event_runtime_uow),
    action_repository: Stage12ActionRuntimeRepository = Depends(
        get_stage12_action_repository
    ),
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
        _require_agent_event_scope(platform_uow, run=run, actor=actor)
        authorization_hash = _current_run_authorization_hash(
            platform_uow,
            run=run,
            actor=actor,
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
            resolve_objective=lambda reference_id: (
                action_repository.get_objective_by_command(run.id, reference_id)
                or action_repository.get_objective(reference_id)
            ),
            resolve_action=lambda command_id: action_repository.get_action_by_command(
                run.id, command_id
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
                action_repository=action_repository,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )
    except (
        Stage06AuthorizationError,
        PlatformValidationError,
        RuntimeScopeDrift,
    ) as exc:
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
            detail=error_detail(
                "agent_event_cursor_invalid", "agent_event_cursor_invalid"
            ),
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
    action_repository: Stage12ActionRuntimeRepository,
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
        if (
            run is None
            or run.status == "waiting_approval"
            or datetime.now(UTC) >= run.deadline_at + timedelta(seconds=5)
        ):
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
            _require_agent_event_scope(platform_uow, run=run, actor=actor)
            authorization_hash = _current_run_authorization_hash(
                platform_uow,
                run=run,
                actor=actor,
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
                resolve_objective=lambda reference_id: (
                    action_repository.get_objective_by_command(run.id, reference_id)
                    or action_repository.get_objective(reference_id)
                ),
                resolve_action=lambda command_id: action_repository.get_action_by_command(
                    run.id, command_id
                ),
            )
        except (Stage06AuthorizationError, PlatformValidationError, RuntimeScopeDrift):
            return


def _refresh_read_session(uow: AgentEventRuntimeUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.rollback()
        session.expire_all()


def _require_agent_event_scope(platform_uow, *, run, actor) -> None:
    if run.workflow_version in {
        "stage12.quality-v2.action.v1",
        "stage12.quality-v2.runtime.v1",
    }:
        build_authorized_schema_snapshot(
            platform_uow,
            workspace_id=run.workspace_id,
            employee_id=run.root_employee_id,
            actor=actor,
            require_field_policy_v2=True,
        )
        return
    _require_current_query_scope(
        platform_uow,
        workspace_id=run.workspace_id,
        employee_id=run.root_employee_id,
        target_record_id=run.target_record_id,
        requested_action="read_only",
        actor=actor,
    )


def _current_run_authorization_hash(platform_uow, *, run, actor) -> str:
    if run.workflow_version in {
        "stage12.quality-v2.action.v1",
        "stage12.quality-v2.runtime.v1",
    }:
        snapshot = build_authorized_schema_snapshot(
            platform_uow,
            workspace_id=run.workspace_id,
            employee_id=run.root_employee_id,
            actor=actor,
            require_field_policy_v2=True,
        )
        if run.workflow_version == "stage12.quality-v2.action.v1":
            return build_stage12_action_scope_hash(
                schema_scope_hash=snapshot.scope_hash,
                target_record_id=run.target_record_id,
            )
        return snapshot.scope_hash
    return build_authorization_hash(
        workspace_id=run.workspace_id,
        employee_id=run.root_employee_id,
        target_record_id=run.target_record_id,
        actor_user_id=actor.actor_id,
    )


def _parse_cursor(value: str | None) -> int:
    if value is None:
        return 0
    if not value.isascii() or not value.isdigit():
        raise ValueError("agent_event_cursor_invalid")
    cursor = int(value)
    if cursor < 0:
        raise ValueError("agent_event_cursor_invalid")
    return cursor


def _stage08_intent(value: str) -> str:
    if value in {"risk_review", "daily_summary", "controlled_action"}:
        return "mixed"
    return value


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
    if artifact.kind == "grounded_composer_result":
        run = runtime_uow.get_run(artifact.run_id)
        if run is None or artifact.visibility_scope_hash != run.scope_hash:
            raise RuntimeNotFound("agent_result_projection_missing")
        try:
            result = read_typed_artifact(
                platform_uow,
                artifact=artifact,
                workspace_id=run.workspace_id,
                current_scope_hash=run.scope_hash,
                expected_kind="grounded_composer_result",
                payload_type=GroundedComposerResultV2,
            )
            return project_grounded_safe_view(result)
        except ValueError as exc:
            raise AgentRunProjectionError("agent_run_projection_failure") from exc
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
            detail=error_detail(
                "agent_event_runtime_disabled", "agent_event_runtime_disabled"
            ),
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


__all__ = [
    "get_agent_event_runtime_uow",
    "get_stage12_action_repository",
    "router",
]
