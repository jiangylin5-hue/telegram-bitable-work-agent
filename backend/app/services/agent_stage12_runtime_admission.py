"""SQL-only admission boundary for the isolated Stage12 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
from uuid import UUID, uuid4

from app.agents.stage12_runtime_admission import (
    Stage12AdmissionDependencies,
    Stage12AdmissionState,
    build_stage12_admission_graph,
)
from app.core.config import Settings
from app.models.agent_event_runtime import AgentArtifact, AgentPrivateInput
from app.schemas.agent_event_runtime import AgentPrivateInputPayload
from app.schemas.agent_specialist_results import (
    ObjectiveSpecialistInputV1,
    specialist_payload_sha256,
)
from app.schemas.agent_stage12_runtime import (
    Stage12ObjectiveDispatchV1,
    Stage12RuntimeAdmissionRequest,
    Stage12RuntimeAdmissionResult,
)
from app.schemas.agent_task_spec_v2 import PlannerRequestV2
from app.schemas.stage12_action_runtime import DurableTaskSpecV2
from app.services.agent_authorized_entity_linker import (
    build_authorized_entity_candidates,
)
from app.services.agent_event_runtime import (
    AgentEventRuntimeUnitOfWork,
    SqlAlchemyAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_orchestrator import (
    SpecialistCommandDispatch,
    build_authorization_hash,
    dispatch_specialist_commands,
)
from app.services.agent_private_inputs import seal_agent_private_input
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.agent_stage12_fixture_resolution import (
    resolve_stage12_isolated_workspace,
)
from app.services.agent_stage12_risk_policy import (
    build_stage12_isolated_risk_policy,
)
from app.services.agent_task_planner_v2 import plan_task_v2
from app.services.agent_typed_artifacts import (
    persist_typed_artifact,
    stage12_command_input_artifact_ids,
)
from app.services.authorized_query_compiler import compile_authorized_query_plan
from app.services.authorized_table_query import execute_authorized_query
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    Stage06PlatformUnitOfWork,
)
from app.services.stage12_action_runtime import (
    SqlAlchemyStage12ActionRuntimeRepository,
    Stage12ActionRuntimeRepository,
    create_objective_run,
)


_WORKFLOW_VERSION = "stage12.quality-v2.runtime.v1"
_IDEMPOTENCY_OPERATION = "stage12.isolated_runtime.admit"
_CAPABILITY_BY_KIND = {
    "fact_query": "platform.tabular.analyse",
    "risk_analysis": "platform.risk.analyse",
    "daily_summary": "platform.daily.summarise",
    "record_change": "platform.action.propose",
    "task_creation": "platform.action.propose",
    "reminder_request": "platform.action.propose",
}
_ACTION_KIND_BY_PERMISSION = {
    "draft_create": ("record.create", "task.create"),
    "draft_update": ("record.update",),
    "task_create": ("task.create",),
    "notification.request": ("reminder.request",),
}


@dataclass(frozen=True, slots=True)
class Stage12RuntimeRunAdmission:
    run_id: UUID
    status: str
    replayed: bool


@dataclass(slots=True)
class _AdmissionContext:
    platform: SqlAlchemyStage06PlatformUnitOfWork
    runtime: SqlAlchemyAgentEventRuntimeUnitOfWork
    objectives: SqlAlchemyStage12ActionRuntimeRepository
    request: Stage12RuntimeAdmissionRequest
    settings: Settings
    actor: Actor
    now: datetime


def admit_stage12_runtime_run(
    platform_uow: Stage06PlatformUnitOfWork,
    runtime_uow: AgentEventRuntimeUnitOfWork,
    objective_repository: Stage12ActionRuntimeRepository,
    *,
    request: Stage12RuntimeAdmissionRequest,
    settings: Settings | None,
    actor: Actor | None,
    now: datetime | None = None,
) -> Stage12RuntimeRunAdmission:
    if (
        not isinstance(platform_uow, SqlAlchemyStage06PlatformUnitOfWork)
        or not isinstance(runtime_uow, SqlAlchemyAgentEventRuntimeUnitOfWork)
        or not isinstance(
            objective_repository,
            SqlAlchemyStage12ActionRuntimeRepository,
        )
        or platform_uow.session is not runtime_uow.session
        or platform_uow.session is not objective_repository.session
    ):
        raise ValueError("stage12_sql_uow_required")
    if settings is None or actor is None:
        raise ValueError("stage12_admission_dependencies_required")
    effective_now = now or datetime.now(UTC)
    if request.deadline_at <= effective_now:
        raise ValueError("stage12_admission_deadline_exhausted")
    context = _AdmissionContext(
        platform=platform_uow,
        runtime=runtime_uow,
        objectives=objective_repository,
        request=request,
        settings=settings,
        actor=actor,
        now=effective_now,
    )
    dependencies = _build_dependencies(context)
    result = build_stage12_admission_graph(dependencies).invoke(
        {"request": request, "completed_nodes": ()}
    )
    run = result.get("run")
    if run is None:
        raise ValueError("stage12_admission_run_missing")
    return Stage12RuntimeRunAdmission(
        run_id=run.id,
        status=run.status,
        replayed=bool(result.get("replayed", False)),
    )


def _build_dependencies(context: _AdmissionContext) -> Stage12AdmissionDependencies:
    def authorize_schema(state: Stage12AdmissionState) -> dict[str, object]:
        request = context.request
        workspace = resolve_stage12_isolated_workspace(
            context.platform,
            workspace_id=request.workspace_id,
            actor_user_id=request.actor_user_id,
            digital_employee_id=request.digital_employee_id,
        )
        expected_request_hash = build_authorization_hash(
            workspace_id=request.workspace_id,
            employee_id=request.digital_employee_id,
            target_record_id=request.target_record_id,
            actor_user_id=request.actor_user_id,
        )
        if expected_request_hash != request.authorization_hash:
            raise ValueError("stage12_admission_request_scope_mismatch")
        snapshot = build_authorized_schema_snapshot(
            context.platform,
            workspace_id=request.workspace_id,
            employee_id=request.digital_employee_id,
            actor=context.actor,
            require_field_policy_v2=True,
        )
        request_fingerprint = fingerprint_request(
            {
                "actor_user_id": request.actor_user_id,
                "workspace_id": request.workspace_id,
                "digital_employee_id": request.digital_employee_id,
                "intent": request.intent,
                "query": request.query,
                "target_record_id": request.target_record_id,
                "skill_id": request.skill_id,
                "authorization_hash": request.authorization_hash,
            }
        )
        idempotency = begin_idempotent_operation(
            context.platform,
            workspace_id=request.workspace_id,
            operation=_IDEMPOTENCY_OPERATION,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request_fingerprint,
            trace_id=idempotency_trace_id(
                _IDEMPOTENCY_OPERATION,
                request_fingerprint,
                request.idempotency_key,
            ),
        )
        if idempotency.status == "replay":
            response_ref = idempotency.response_ref or {}
            try:
                existing_run_id = UUID(str(response_ref["run_id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("stage12_admission_replay_invalid") from exc
            existing_run = context.runtime.get_run(existing_run_id)
            if (
                existing_run is None
                or existing_run.workflow_version != _WORKFLOW_VERSION
                or existing_run.workspace_id != request.workspace_id
                or existing_run.scope_hash != snapshot.scope_hash
            ):
                raise ValueError("stage12_admission_replay_invalid")
            return {
                "completed_nodes": _completed(state, "authorize_schema"),
                "context": workspace,
                "schema_snapshot": snapshot,
                "run": existing_run,
                "replayed": True,
                "idempotency_record": idempotency.record,
            }
        run_key_hash = hashlib.sha256(
            (
                f"stage12-runtime:{request.workspace_id}:{request.actor_user_id}:"
                f"{request.idempotency_key}"
            ).encode("utf-8")
        ).hexdigest()
        creation = create_agent_run(
            context.runtime,
            workspace_id=request.workspace_id,
            root_employee_id=request.digital_employee_id,
            target_record_id=request.target_record_id,
            scope_hash=snapshot.scope_hash,
            idempotency_key_hash=run_key_hash,
            deadline_at=request.deadline_at,
            now=context.now,
            workflow_version=_WORKFLOW_VERSION,
        )
        if creation.replayed:
            raise ValueError("stage12_admission_idempotency_state_invalid")
        return {
            "completed_nodes": _completed(state, "authorize_schema"),
            "context": workspace,
            "schema_snapshot": snapshot,
            "run": creation.run,
            "replayed": False,
            "idempotency_record": idempotency.record,
        }

    def plan_task(state: Stage12AdmissionState) -> dict[str, object]:
        if state.get("replayed"):
            return {"completed_nodes": _completed(state, "plan_task")}
        workspace = state["context"]
        snapshot = state["schema_snapshot"]
        employee = context.platform.get_digital_employee(
            context.request.digital_employee_id
        )
        if employee is None:
            raise ValueError("stage12_admission_employee_missing")
        entities = build_authorized_entity_candidates(
            context.platform,
            query=context.request.query,
            actor=context.actor,
            workspace_id=context.request.workspace_id,
            base_id=workspace.base_id,
            employee_id=context.request.digital_employee_id,
            snapshot=snapshot,
            chat_authorized_view_ids=None,
            allow_whole_table=True,
        )
        action_kinds = tuple(
            dict.fromkeys(
                action_kind
                for permission in employee.allowed_actions
                for action_kind in _ACTION_KIND_BY_PERMISSION.get(permission, ())
            )
        )
        task_artifact = plan_task_v2(
            PlannerRequestV2(
                query=context.request.query,
                authorized_schema=snapshot,
                authorized_entities=entities,
                clock=context.now,
                timezone_name="Asia/Shanghai",
                allowed_action_kinds=action_kinds,
            )
        )
        return {
            "completed_nodes": _completed(state, "plan_task"),
            "task_artifact": task_artifact,
        }

    def execute_authorized_inputs(
        state: Stage12AdmissionState,
    ) -> dict[str, object]:
        if state.get("replayed"):
            return {
                "completed_nodes": _completed(state, "execute_authorized_inputs")
            }
        task_artifact = state["task_artifact"]
        snapshot = state["schema_snapshot"]
        relations = build_authorized_relation_catalog(context.platform, snapshot)
        query_artifacts = tuple(
            execute_authorized_query(
                context.platform,
                actor=context.actor,
                workspace_id=context.request.workspace_id,
                employee_id=context.request.digital_employee_id,
                chat_view_ids=None,
                snapshot=snapshot,
                plan=compile_authorized_query_plan(
                    task_spec=task_artifact.task_spec,
                    query_intent_id=intent.query_intent_id,
                    snapshot=snapshot,
                    relations=relations,
                    authorized_view_ids=(),
                ),
                allow_whole_table=True,
            )
            for intent in task_artifact.task_spec.query_intents
            if any(
                objective.planning_outcome == "planned"
                and objective.query_spec_ref
                == f"query-intent:{intent.query_intent_id}"
                for objective in task_artifact.task_spec.objectives
            )
        )
        if not query_artifacts:
            raise ValueError("stage12_structured_query_required")
        return {
            "completed_nodes": _completed(state, "execute_authorized_inputs"),
            "query_artifacts": query_artifacts,
        }

    def persist_typed_inputs(state: Stage12AdmissionState) -> dict[str, object]:
        if state.get("replayed"):
            return {"completed_nodes": _completed(state, "persist_typed_inputs")}
        run = state["run"]
        snapshot = state["schema_snapshot"]
        task_artifact = state["task_artifact"]
        query_artifacts = state["query_artifacts"]
        expires_at = context.request.deadline_at
        schema_artifact, schema_owner_ref = _persist_metadata(
            context,
            run_id=run.id,
            kind="authorized_schema_snapshot",
            payload=snapshot,
            scope_hash=snapshot.scope_hash,
            expires_at=expires_at,
        )
        task_payload_values = {
            "version": "stage12-task-spec-owner.v1",
            "task_spec": task_artifact.task_spec,
        }
        task_payload = DurableTaskSpecV2(
            **task_payload_values,
            content_hash=specialist_payload_sha256(
                {
                    "version": task_payload_values["version"],
                    "task_spec": task_artifact.task_spec.model_dump(mode="json"),
                }
            ),
        )
        _task_metadata, task_owner_ref = _persist_metadata(
            context,
            run_id=run.id,
            kind="task_spec_v2",
            payload=task_payload,
            scope_hash=snapshot.scope_hash,
            expires_at=expires_at,
        )
        if any(
            objective.kind == "risk_analysis"
            and objective.planning_outcome == "planned"
            for objective in task_artifact.task_spec.objectives
        ):
            _persist_metadata(
                context,
                run_id=run.id,
                kind="authorized_risk_policy",
                payload=build_stage12_isolated_risk_policy(snapshot),
                scope_hash=snapshot.scope_hash,
                expires_at=expires_at,
            )
        query_metadata_by_id: dict[str, AgentArtifact] = {}
        for artifact in query_artifacts:
            metadata, _owner_ref = _persist_metadata(
                context,
                run_id=run.id,
                kind="structured_query_artifact",
                payload=artifact,
                scope_hash=snapshot.scope_hash,
                expires_at=expires_at,
            )
            query_metadata_by_id[artifact.plan.query_intent_id] = metadata
        data_version_hash = specialist_payload_sha256(
            {
                "query_result_hashes": tuple(
                    item.result.result_hash for item in query_artifacts
                )
            }
        )
        run.data_version_hash = data_version_hash

        incoming: dict[str, tuple[str, ...]] = {}
        for objective in task_artifact.task_spec.objectives:
            incoming[objective.objective_id] = tuple(
                edge.from_objective_id
                for edge in task_artifact.task_spec.dependency_edges
                if edge.to_objective_id == objective.objective_id
            )
            objective_run = create_objective_run(
                context.objectives,
                run_id=run.id,
                objective_key=objective.objective_id,
                kind=objective.kind,
                required=objective.required,
                dependency_keys=incoming[objective.objective_id],
            )
            if objective.planning_outcome != "planned":
                objective_run.status = "denied"
                objective_run.error_code = objective.denial_reason

        dispatches: list[Stage12ObjectiveDispatchV1] = []
        for objective in task_artifact.task_spec.objectives:
            if objective.planning_outcome != "planned" or incoming[objective.objective_id]:
                continue
            capability = _CAPABILITY_BY_KIND.get(objective.kind)
            if capability != "platform.tabular.analyse":
                raise ValueError("stage12_objective_dependency_invalid")
            if objective.query_spec_ref is None:
                raise ValueError("stage12_objective_query_ref_required")
            query_id = objective.query_spec_ref.removeprefix("query-intent:")
            query_metadata = query_metadata_by_id.get(query_id)
            if query_metadata is None:
                raise ValueError("stage12_objective_query_artifact_missing")
            objective_values = {
                "version": "objective-specialist-input.v1",
                "objective_id": objective.objective_id,
                "capability_id": capability,
                "task_spec_ref": task_owner_ref,
                "input_artifact_refs": (query_metadata.id,),
                "scope_hash": snapshot.scope_hash,
                "schema_hash": snapshot.schema_hash,
                "data_version_hash": data_version_hash,
            }
            objective_payload = ObjectiveSpecialistInputV1(
                **objective_values,
                content_hash=specialist_payload_sha256(objective_values),
            )
            objective_metadata, _objective_owner_ref = _persist_metadata(
                context,
                run_id=run.id,
                kind="objective_specialist_input",
                payload=objective_payload,
                scope_hash=snapshot.scope_hash,
                expires_at=expires_at,
            )
            dispatches.append(
                Stage12ObjectiveDispatchV1(
                    objective=objective_payload,
                    objective_artifact_id=objective_metadata.id,
                    dependency_artifact_ids=(query_metadata.id,),
                    private_input_ref=f"agent-private-input:{uuid4()}",
                )
            )
        if not dispatches:
            raise ValueError("stage12_dispatch_ready_objective_required")
        admission_result = Stage12RuntimeAdmissionResult(
            task_spec_ref=task_owner_ref,
            schema_ref=schema_owner_ref,
            objective_dispatches=tuple(dispatches),
            data_version_hash=data_version_hash,
        )
        return {
            "completed_nodes": _completed(state, "persist_typed_inputs"),
            "admission_result": admission_result,
            "schema_artifact": schema_artifact,
        }

    def dispatch_commands(state: Stage12AdmissionState) -> dict[str, object]:
        if state.get("replayed"):
            return {"completed_nodes": _completed(state, "dispatch_commands")}
        run = state["run"]
        admission_result = state["admission_result"]
        if context.settings.agent_runtime_input_key is None:
            raise ValueError("agent_private_input_key_unavailable")
        command_ids = tuple(uuid4() for _ in admission_result.objective_dispatches)
        private_ids = tuple(
            UUID(item.private_input_ref.removeprefix("agent-private-input:"))
            for item in admission_result.objective_dispatches
        )
        specialist_dispatches = tuple(
            SpecialistCommandDispatch(
                target_capability=item.objective.capability_id,
                payload_ref=item.private_input_ref,
                input_artifact_refs=stage12_command_input_artifact_ids(item),
                required=True,
                command_id=command_id,
            )
            for item, command_id in zip(
                admission_result.objective_dispatches,
                command_ids,
                strict=True,
            )
        )
        commands = dispatch_specialist_commands(
            context.runtime,
            run_id=run.id,
            dispatches=specialist_dispatches,
            authorization_hash=run.scope_hash,
            now=context.now,
        )
        for command, private_id, dispatch in zip(
            commands,
            private_ids,
            admission_result.objective_dispatches,
            strict=True,
        ):
            sealed = seal_agent_private_input(
                AgentPrivateInputPayload(
                    actor_user_id=context.request.actor_user_id,
                    workspace_id=context.request.workspace_id,
                    employee_id=context.request.digital_employee_id,
                    intent=context.request.intent,
                    query=context.request.query,
                    target_record_id=context.request.target_record_id,
                    idempotency_key=context.request.idempotency_key,
                    skill_id=context.request.skill_id,
                ),
                key_b64=context.settings.agent_runtime_input_key,
                key_version=context.settings.agent_runtime_input_key_version,
                run_id=run.id,
                command_id=command.id,
                scope_hash=run.scope_hash,
                expires_at=min(
                    run.deadline_at,
                    context.now
                    + timedelta(
                        seconds=context.settings.agent_runtime_input_ttl_seconds
                    ),
                ),
            )
            context.runtime.add_private_input(
                AgentPrivateInput(
                    id=private_id,
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
            objective_run = context.objectives.get_objective_by_key(
                run.id,
                dispatch.objective.objective_id,
            )
            if objective_run is None:
                raise ValueError("stage12_objective_run_missing")
            objective_run.command_id = command.id
        record_audit_event(
            context.platform.session,
            trace_id=state["idempotency_record"].trace_id,
            actor_type=context.actor.actor_type,
            actor_id=context.actor.actor_id,
            event_type="stage12.isolated_runtime_admitted",
            entity_type="digital_employee",
            entity_id=context.request.digital_employee_id,
            after_state={
                "workflow_version": _WORKFLOW_VERSION,
                "run_status": run.status,
                "objective_count": len(
                    context.objectives.list_objectives(run.id)
                ),
                "initial_command_count": len(commands),
            },
            permission_snapshot={"scope_hash": run.scope_hash},
        )
        complete_idempotent_operation(
            state["idempotency_record"],
            response_ref={"run_id": str(run.id), "status": run.status},
        )
        return {"completed_nodes": _completed(state, "dispatch_commands")}

    return Stage12AdmissionDependencies(
        authorize_schema=authorize_schema,
        plan_task=plan_task,
        execute_authorized_inputs=execute_authorized_inputs,
        persist_typed_inputs=persist_typed_inputs,
        dispatch_commands=dispatch_commands,
    )


def _persist_metadata(
    context: _AdmissionContext,
    *,
    run_id: UUID,
    kind: str,
    payload,
    scope_hash: str,
    expires_at: datetime,
) -> tuple[AgentArtifact, str]:
    owner = persist_typed_artifact(
        context.platform,
        workspace_id=context.request.workspace_id,
        run_id=run_id,
        artifact_kind=kind,
        payload=payload,
        scope_hash=scope_hash,
    )
    metadata = AgentArtifact(
        id=uuid4(),
        run_id=run_id,
        kind=kind,
        storage_ref=owner.storage_ref,
        content_hash=owner.content_hash,
        visibility_scope_hash=scope_hash,
        validation_status="validated",
        expires_at=expires_at,
    )
    context.runtime.add_artifact(metadata)
    context.runtime.flush()
    return metadata, owner.storage_ref


def _completed(state: Stage12AdmissionState, node: str) -> tuple[str, ...]:
    return (*state.get("completed_nodes", ()), node)


__all__ = ["Stage12RuntimeRunAdmission", "admit_stage12_runtime_run"]
