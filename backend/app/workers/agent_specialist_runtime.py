from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
import json
import os
from time import sleep
from typing import Callable, Mapping
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import (
    Settings,
    durable_action_v1_enabled,
    validate_runtime_settings,
)
from app.core.database import get_session_factory
from app.queues.redis_streams import RedisStreams, RedisStreamsClient
from app.schemas.agent_event_runtime import AgentCommandEnvelope
from app.schemas.agent_event_runtime import AgentPrivateInputPayload
from app.services.stage06_identity import Stage06RequestIdentity
from app.models.agent_event_runtime import AgentArtifact, AgentPrivateInput
from app.schemas.agent_specialist_results import (
    AuthorizedCandidateSetV1,
    ClaimGraphV1,
    ComposerResultV1,
    ControlledActionProposalV1,
    CurrentVersionProofV1,
    DailyBriefV1,
    ObjectiveSpecialistInputV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.schemas.agent_task_spec_v2 import ActionSlotV1, AuthorizedSchemaSnapshot
from app.schemas.authorized_query_plan import StructuredQueryArtifactV1
from app.schemas.retrieval_v2 import EvidenceBundleV2
from app.schemas.retrieval_v2 import canonical_retrieval_sha256
from app.schemas.agent_stage12_runtime import Stage12ObjectiveDispatchV1
from app.workers.agent_tabular_runtime import (
    AgentTabularStreamWorker,
    AgentTabularWorkerResult,
    process_agent_tabular_command,
)
from app.services.agent_event_runtime import SqlAlchemyAgentEventRuntimeUnitOfWork
from app.services.agent_claim_graph import (
    ActionDependencyV1,
    ClaimInputV1,
    ObjectiveOutcomeInputV1,
    build_claim_graph,
    claim_inputs_from_fact_set,
)
from app.services.agent_composer_v2 import compose_claim_graph
from app.services.agent_orchestrator import (
    OrchestratorError,
    SpecialistSafeResult,
    dispatch_unlocked_specialist_command,
    execute_read_only_specialist,
    fail_specialist_command,
)
from app.services.agent_private_inputs import (
    PrivateInputError,
    open_agent_private_input,
    seal_agent_private_input,
)
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.agent_stage12_runtime_activation import (
    build_stage12_runtime_profile,
    stage12_runtime_enabled,
)
from app.services.agent_risk_policy import AuthorizedRiskPolicyV1
from app.services.agent_specialist_registry_v2 import (
    default_specialist_factories,
    validate_specialist_readiness,
)
from app.services.agent_specialists_v2.base import SpecialistHandler
from app.services.agent_specialists_v2.base import SpecialistExecutionContextV2
from app.services.agent_typed_artifacts import (
    TypedArtifactUnitOfWork,
    persist_typed_artifact,
    read_typed_artifact,
    read_typed_artifact_owner_ref,
)
from app.services.agent_specialist_shadow_v2 import typed_specialists_shadow_enabled
from app.services.agent_stage12_grounded_fan_in import (
    GroundedProvider,
    build_stage12_grounded_provider,
    build_stage12_presentation,
    compose_stage12_grounded_result,
)
from app.services.stage06_platform import SqlAlchemyStage06PlatformUnitOfWork
from app.services.stage06_authorization import authorize_workspace_action
from app.services.stage12_action_runtime import SqlAlchemyStage12ActionRuntimeRepository
from app.schemas.stage12_action_runtime import DurableTaskSpecV2
from app.workers.stage12_action_runtime import process_stage12_action_command


SPECIALIST_CAPABILITIES = (
    "platform.tabular.analyse",
    "platform.risk.analyse",
    "platform.daily.summarise",
    "platform.action.propose",
)
_TYPED_ARTIFACT_TYPES: Mapping[str, type[BaseModel]] = {
    "structured_query_artifact": StructuredQueryArtifactV1,
    "evidence_bundle": EvidenceBundleV2,
    "structured_fact_set": StructuredFactSetV1,
    "risk_assessment_set": RiskAssessmentSetV1,
    "daily_brief": DailyBriefV1,
    "action_slot": ActionSlotV1,
    "authorized_candidate_set": AuthorizedCandidateSetV1,
    "current_version_proof": CurrentVersionProofV1,
    "authorized_risk_policy": AuthorizedRiskPolicyV1,
    "controlled_action_proposal": ControlledActionProposalV1,
}
_OUTPUT_KIND_BY_CAPABILITY = {
    "platform.tabular.analyse": "structured_fact_set",
    "platform.risk.analyse": "risk_assessment_set",
    "platform.daily.summarise": "daily_brief",
    "platform.action.propose": "controlled_action_proposal",
}


@dataclass(frozen=True, slots=True)
class AgentSpecialistPoolResult:
    processed: int = 0
    recovered: int = 0
    dead_lettered: int = 0


@dataclass(frozen=True, slots=True)
class LoadedStage12ObjectiveDispatch:
    dispatch: Stage12ObjectiveDispatchV1
    private_input: object
    sealed_input: object


def load_stage12_objective_dispatch(
    runtime: object,
    artifact_uow: TypedArtifactUnitOfWork,
    *,
    run: object,
    command: object,
    envelope: AgentCommandEnvelope,
    settings: Settings,
    now: datetime,
) -> LoadedStage12ObjectiveDispatch:
    """Load one isolated command only from its durable owner and sealed input."""

    persisted = runtime.get_outbox_event_by_event_id(command.id)
    if persisted is None:
        raise OrchestratorError("agent_command_outbox_missing")
    try:
        durable_envelope = AgentCommandEnvelope.model_validate_json(
            json.dumps(persisted.payload_json)
        )
    except Exception as exc:
        raise OrchestratorError("agent_command_envelope_invalid") from exc
    authorization_hash = envelope.scope_proof_ref.removeprefix("scope:sha256:")
    if (
        durable_envelope != envelope
        or command.run_id != run.id
        or run.id != envelope.run_id
        or run.workflow_version != "stage12.quality-v2.runtime.v1"
        or run.scope_hash != authorization_hash
        or command.target_capability != envelope.target_capability
        or command.command_type != envelope.command_type
        or command.idempotency_key_hash != envelope.idempotency_key_hash
        or command.deadline_at != envelope.deadline_at
        or now >= command.deadline_at
    ):
        raise OrchestratorError("agent_command_envelope_mismatch")
    prefix = "agent-private-input:"
    if command.payload_ref is None or not command.payload_ref.startswith(prefix):
        raise OrchestratorError("agent_private_input_ref_invalid")
    try:
        private_input_id = UUID(command.payload_ref.removeprefix(prefix))
    except ValueError as exc:
        raise OrchestratorError("agent_private_input_ref_invalid") from exc
    sealed_input = runtime.get_private_input(private_input_id, for_update=True)
    if (
        sealed_input is None
        or sealed_input.run_id != run.id
        or sealed_input.command_id != command.id
        or sealed_input.consumed_at is not None
        or settings.agent_runtime_input_key is None
    ):
        raise OrchestratorError("agent_private_input_unavailable")
    try:
        private_input = open_agent_private_input(
            sealed_input,
            key_b64=settings.agent_runtime_input_key,
            run_id=run.id,
            command_id=command.id,
            scope_hash=authorization_hash,
            now=now,
        )
    except PrivateInputError as exc:
        raise OrchestratorError(str(exc)) from exc
    if (
        private_input.workspace_id != run.workspace_id
        or private_input.employee_id != run.root_employee_id
        or private_input.target_record_id != run.target_record_id
    ):
        raise OrchestratorError("agent_private_input_scope_mismatch")

    referenced = tuple(
        runtime.get_artifact(ref) for ref in envelope.input_artifact_refs
    )
    if any(
        item is None
        or item.run_id != run.id
        or item.visibility_scope_hash != authorization_hash
        or item.validation_status != "validated"
        or (item.expires_at is not None and item.expires_at <= now)
        for item in referenced
    ):
        raise OrchestratorError("typed_specialist_artifact_invalid")
    owners = tuple(
        item for item in referenced if item.kind == "objective_specialist_input"
    )
    if len(owners) != 1:
        raise OrchestratorError("typed_specialist_objective_owner_invalid")
    owner = owners[0]
    dependencies = tuple(item.id for item in referenced if item.id != owner.id)
    objective = read_typed_artifact(
        artifact_uow,
        artifact=owner,
        workspace_id=run.workspace_id,
        current_scope_hash=authorization_hash,
        expected_kind="objective_specialist_input",
        payload_type=ObjectiveSpecialistInputV1,
    )
    if (
        objective.capability_id != envelope.target_capability
        or objective.scope_hash != authorization_hash
        or objective.input_artifact_refs != dependencies
    ):
        raise OrchestratorError("typed_specialist_input_mismatch")
    dispatch = Stage12ObjectiveDispatchV1(
        objective=objective,
        objective_artifact_id=owner.id,
        dependency_artifact_ids=dependencies,
        private_input_ref=command.payload_ref,
    )
    return LoadedStage12ObjectiveDispatch(
        dispatch=dispatch,
        private_input=private_input,
        sealed_input=sealed_input,
    )


@dataclass(frozen=True, slots=True)
class TypedSpecialistCommandProcessor:
    typed_handler: SpecialistHandler
    session_factory: Callable[[], Session]
    settings: Settings
    worker_id: str

    def __call__(self, envelope: AgentCommandEnvelope) -> None:
        with self.session_factory() as session:
            runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
            command = runtime.get_command(
                envelope.command_id,
                for_update=True,
            )
            if command is None:
                raise RuntimeError("agent_command_not_found")
            run = runtime.get_run(envelope.run_id)
            if (
                run is not None
                and run.workflow_version == "stage12.quality-v2.runtime.v1"
                and command.payload_ref
                and command.payload_ref.startswith("agent-private-input:")
            ):
                profile = build_stage12_runtime_profile(self.settings)
                if not stage12_runtime_enabled(
                    profile,
                    workspace_id=run.workspace_id,
                ):
                    raise RuntimeError("stage12_isolated_runtime_disabled")
                process_stage12_typed_specialist_command(
                    session,
                    envelope,
                    handler=self.typed_handler,
                    settings=self.settings,
                    worker_id=self.worker_id,
                )
                return
            if command.payload_ref and command.payload_ref.startswith(
                "stage08-idempotency:"
            ):
                process_typed_specialist_command(
                    session,
                    envelope,
                    handler=self.typed_handler,
                    settings=self.settings,
                    worker_id=self.worker_id,
                )
                return
            if envelope.target_capability == "platform.tabular.analyse":
                process_agent_tabular_command(
                    session,
                    envelope,
                    settings=self.settings,
                    worker_id=self.worker_id,
                )
                return
            if envelope.target_capability == "platform.action.propose":
                _process_legacy_action(
                    session,
                    envelope,
                    settings=self.settings,
                    worker_id=self.worker_id,
                )
                return
            raise RuntimeError("typed_specialist_input_required")


def build_typed_specialist_process_registry(
    *,
    session_factory: Callable[[], Session],
    settings: Settings,
    consumer_name: str,
) -> Mapping[str, TypedSpecialistCommandProcessor]:
    handlers = validate_specialist_readiness(default_specialist_factories())
    return {
        handler.capability_id: TypedSpecialistCommandProcessor(
            typed_handler=handler,
            session_factory=session_factory,
            settings=settings,
            worker_id=f"{consumer_name}-{handler.capability_id}",
        )
        for handler in handlers
    }


def process_typed_specialist_command(
    session: Session,
    envelope: AgentCommandEnvelope,
    *,
    handler: SpecialistHandler,
    settings: Settings,
    worker_id: str,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(UTC)
    runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
    platform = SqlAlchemyStage06PlatformUnitOfWork(session)
    run = runtime.get_run(envelope.run_id, for_update=True)
    if run is None:
        raise OrchestratorError("agent_run_not_found")
    if not typed_specialists_shadow_enabled(settings, run.workspace_id):
        raise OrchestratorError("typed_specialist_runtime_disabled")
    try:
        execute_typed_specialist_command(
            runtime,
            platform,
            envelope,
            handler=handler,
            worker_id=worker_id,
            now=now,
        )
        session.commit()
    except Exception:
        session.rollback()
        failure_runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
        command = failure_runtime.get_command(envelope.command_id, for_update=True)
        failure_run = failure_runtime.get_run(envelope.run_id, for_update=True)
        if command is None or failure_run is None:
            raise
        fail_specialist_command(
            failure_runtime,
            command_id=command.id,
            authorization_hash=failure_run.scope_hash,
            worker_id=worker_id,
            now=now,
            fan_in=partial(
                _fan_in_typed_results,
                failure_runtime,
                SqlAlchemyStage06PlatformUnitOfWork(session),
                run_id=failure_run.id,
                workspace_id=failure_run.workspace_id,
                scope_hash=failure_run.scope_hash,
                now=now,
            ),
        )
        session.commit()


def process_stage12_typed_specialist_command(
    session: Session,
    envelope: AgentCommandEnvelope,
    *,
    handler: SpecialistHandler,
    settings: Settings,
    worker_id: str,
    now: datetime | None = None,
    stage12_provider: GroundedProvider | None = None,
) -> None:
    now = now or datetime.now(UTC)
    private_input: AgentPrivateInputPayload | None = None
    snapshot: AuthorizedSchemaSnapshot | None = None
    runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
    platform = SqlAlchemyStage06PlatformUnitOfWork(session)
    objectives = SqlAlchemyStage12ActionRuntimeRepository(session)
    run = runtime.get_run(envelope.run_id, for_update=True)
    command = runtime.get_command(envelope.command_id, for_update=True)
    if run is None or command is None:
        raise OrchestratorError("agent_command_not_found")
    if handler.capability_id != envelope.target_capability:
        raise OrchestratorError("agent_command_envelope_mismatch")
    authorization_hash = envelope.scope_proof_ref.removeprefix("scope:sha256:")
    if command.status == "completed":
        objective = _stage12_objective_from_envelope(
            runtime,
            platform,
            run=run,
            command=command,
            envelope=envelope,
            authorization_hash=authorization_hash,
            now=now,
            allow_expired=True,
        )
        execute_typed_specialist_command(
            runtime,
            platform,
            envelope,
            handler=handler,
            worker_id=worker_id,
            now=now,
            objective_override=objective,
        )
        session.commit()
        return
    try:
        loaded = load_stage12_objective_dispatch(
            runtime,
            platform,
            run=run,
            command=command,
            envelope=envelope,
            settings=settings,
            now=now,
        )
        private_input = loaded.private_input
        actor = authorize_workspace_action(
            platform,
            Stage06RequestIdentity(
                user_id=private_input.actor_user_id,
                source="verified_adapter",
            ),
            run.workspace_id,
            "digital_employee.invoke",
        )
        snapshot = build_authorized_schema_snapshot(
            platform,
            workspace_id=run.workspace_id,
            employee_id=run.root_employee_id,
            actor=actor,
            require_field_policy_v2=True,
        )
        if snapshot.scope_hash != run.scope_hash:
            raise OrchestratorError("agent_command_scope_drift")
        objective_run = objectives.get_objective_by_command(run.id, command.id)
        if (
            objective_run is None
            or objective_run.objective_key != loaded.dispatch.objective.objective_id
            or objective_run.status not in {"queued", "running"}
        ):
            raise OrchestratorError("stage12_objective_command_mismatch")
        objective_run.status = "running"
        execution = execute_typed_specialist_command(
            runtime,
            platform,
            envelope,
            handler=handler,
            worker_id=worker_id,
            now=now,
            objective_override=loaded.dispatch.objective,
            stage12_query=private_input.query,
            stage12_schema=snapshot,
            stage12_settings=settings,
            stage12_provider=stage12_provider,
            after_command_completed=partial(
                _advance_stage12_objective_dag,
                runtime,
                platform,
                objectives,
                run=run,
                command=command,
                current_objective=objective_run,
                objective_input=loaded.dispatch.objective,
                private_input=private_input,
                settings=settings,
                worker_id=worker_id,
                now=now,
            ),
        )
        if objective_run.result_artifact_id != execution.artifact.id:
            raise OrchestratorError("stage12_objective_result_mismatch")
        loaded.sealed_input.consumed_at = now
        session.commit()
    except Exception:
        session.rollback()
        failure_runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
        failure_objectives = SqlAlchemyStage12ActionRuntimeRepository(session)
        failure_run = failure_runtime.get_run(envelope.run_id, for_update=True)
        failure_command = failure_runtime.get_command(
            envelope.command_id,
            for_update=True,
        )
        if failure_run is None or failure_command is None:
            raise
        if failure_command.payload_ref and failure_command.payload_ref.startswith(
            "agent-private-input:"
        ):
            try:
                input_id = UUID(
                    failure_command.payload_ref.removeprefix("agent-private-input:")
                )
            except ValueError:
                input_id = None
            sealed = (
                None
                if input_id is None
                else failure_runtime.get_private_input(input_id, for_update=True)
            )
            if sealed is not None:
                sealed.consumed_at = now
        objective_run = failure_objectives.get_objective_by_command(
            failure_run.id,
            failure_command.id,
        )
        if objective_run is not None:
            objective_run.status = "failed"
            objective_run.error_code = "specialist_failed"
        objective_rows = failure_objectives.list_objectives(failure_run.id)
        required_command_ids = frozenset(
            item.command_id
            for item in objective_rows
            if item.command_id is not None and item.required
        )
        optional_command_ids = frozenset(
            item.command_id
            for item in objective_rows
            if item.command_id is not None and not item.required
        )
        fail_specialist_command(
            failure_runtime,
            command_id=failure_command.id,
            authorization_hash=failure_run.scope_hash,
            worker_id=worker_id,
            now=now,
            fan_in=(
                None
                if private_input is None or snapshot is None
                else partial(
                    _fan_in_typed_results,
                    failure_runtime,
                    SqlAlchemyStage06PlatformUnitOfWork(session),
                    run_id=failure_run.id,
                    workspace_id=failure_run.workspace_id,
                    scope_hash=failure_run.scope_hash,
                    now=now,
                    stage12_query=private_input.query,
                    stage12_schema=snapshot,
                    stage12_settings=settings,
                    stage12_provider=stage12_provider,
                )
            ),
            required_command_ids=required_command_ids,
            optional_command_ids=optional_command_ids,
        )
        session.commit()


def execute_typed_specialist_command(
    runtime: object,
    artifact_uow: TypedArtifactUnitOfWork,
    envelope: AgentCommandEnvelope,
    *,
    handler: SpecialistHandler,
    worker_id: str,
    now: datetime,
    objective_override: ObjectiveSpecialistInputV1 | None = None,
    after_command_completed: Callable[[AgentArtifact], None] | None = None,
    stage12_query: str | None = None,
    stage12_schema: AuthorizedSchemaSnapshot | None = None,
    stage12_settings: Settings | None = None,
    stage12_provider: GroundedProvider | None = None,
):
    command = runtime.get_command(envelope.command_id, for_update=True)
    if command is None or command.run_id != envelope.run_id:
        raise OrchestratorError("agent_command_not_found")
    run = runtime.get_run(envelope.run_id, for_update=True)
    if run is None:
        raise OrchestratorError("agent_run_not_found")
    persisted = runtime.get_outbox_event_by_event_id(command.id)
    if persisted is None:
        raise OrchestratorError("agent_command_outbox_missing")
    try:
        durable_envelope = AgentCommandEnvelope.model_validate_json(
            json.dumps(persisted.payload_json)
        )
    except Exception as exc:
        raise OrchestratorError("agent_command_envelope_invalid") from exc
    authorization_hash = envelope.scope_proof_ref.removeprefix("scope:sha256:")
    if (
        durable_envelope != envelope
        or run.scope_hash != authorization_hash
        or command.target_capability != envelope.target_capability
        or command.command_type != envelope.command_type
        or command.idempotency_key_hash != envelope.idempotency_key_hash
        or command.deadline_at != envelope.deadline_at
        or handler.capability_id != envelope.target_capability
        or command.payload_ref is None
    ):
        raise OrchestratorError("agent_command_envelope_mismatch")
    objective = objective_override or read_typed_artifact_owner_ref(
        artifact_uow,
        storage_ref=command.payload_ref,
        workspace_id=run.workspace_id,
        current_scope_hash=authorization_hash,
        expected_kind="objective_specialist_input",
        payload_type=ObjectiveSpecialistInputV1,
    )
    expected_envelope_refs = (
        objective.input_artifact_refs
        if objective_override is None
        else envelope.input_artifact_refs[1:]
    )
    if (
        objective.capability_id != envelope.target_capability
        or objective.scope_hash != authorization_hash
        or objective.input_artifact_refs != expected_envelope_refs
    ):
        raise OrchestratorError("typed_specialist_input_mismatch")

    cache: dict[object, BaseModel] = {}

    def artifact_reader(artifact_ref):
        if artifact_ref not in objective.input_artifact_refs:
            raise ValueError("typed_specialist_artifact_ref_unknown")
        if artifact_ref in cache:
            return cache[artifact_ref]
        metadata = runtime.get_artifact(artifact_ref)
        if metadata is None or metadata.run_id != run.id:
            raise ValueError("typed_specialist_artifact_missing")
        payload_type = _TYPED_ARTIFACT_TYPES.get(metadata.kind)
        if payload_type is None:
            raise ValueError("typed_specialist_artifact_kind_invalid")
        payload = read_typed_artifact(
            artifact_uow,
            artifact=metadata,
            workspace_id=run.workspace_id,
            current_scope_hash=authorization_hash,
            expected_kind=metadata.kind,
            payload_type=payload_type,
        )
        cache[artifact_ref] = payload
        return payload

    def risk_policy_reader(_objective_id: str) -> AuthorizedRiskPolicyV1:
        policies = tuple(
            item
            for ref in objective.input_artifact_refs
            if isinstance((item := artifact_reader(ref)), AuthorizedRiskPolicyV1)
        )
        if len(policies) != 1:
            raise ValueError("typed_specialist_risk_policy_invalid")
        return policies[0]

    context = SpecialistExecutionContextV2(
        artifact_reader=artifact_reader,
        risk_policy_reader=risk_policy_reader,
        clock=lambda: now,
        metrics=lambda _name, _value: None,
    )

    def execute() -> SpecialistSafeResult:
        result = handler.execute(objective, context)
        output_kind = _OUTPUT_KIND_BY_CAPABILITY[handler.capability_id]
        owner = persist_typed_artifact(
            artifact_uow,
            workspace_id=run.workspace_id,
            run_id=run.id,
            artifact_kind=output_kind,
            payload=result.payload,
            scope_hash=authorization_hash,
        )
        return SpecialistSafeResult(
            storage_ref=owner.storage_ref,
            content_hash=owner.content_hash,
            safe_summary=result.safe_summary,
            metrics=dict(result.metrics),
            artifact_kind=output_kind,
        )

    fan_in = partial(
        _fan_in_typed_results,
        runtime,
        artifact_uow,
        run_id=run.id,
        workspace_id=run.workspace_id,
        scope_hash=authorization_hash,
        now=now,
        stage12_query=stage12_query,
        stage12_schema=stage12_schema,
        stage12_settings=stage12_settings,
        stage12_provider=stage12_provider,
    )
    return execute_read_only_specialist(
        runtime,
        command_id=command.id,
        authorization_hash=authorization_hash,
        worker_id=worker_id,
        now=now,
        execute=execute,
        fan_in=fan_in,
        after_command_completed=after_command_completed,
    )


def _advance_stage12_objective_dag(
    runtime: object,
    artifact_uow: TypedArtifactUnitOfWork,
    objectives: SqlAlchemyStage12ActionRuntimeRepository,
    result_artifact: AgentArtifact,
    *,
    run: object,
    command: object,
    current_objective: object,
    objective_input: ObjectiveSpecialistInputV1,
    private_input: object,
    settings: Settings,
    worker_id: str,
    now: datetime,
) -> None:
    current_objective.status = "completed"
    current_objective.result_artifact_id = result_artifact.id
    task_owner = read_typed_artifact_owner_ref(
        artifact_uow,
        storage_ref=objective_input.task_spec_ref,
        workspace_id=run.workspace_id,
        current_scope_hash=run.scope_hash,
        expected_kind="task_spec_v2",
        payload_type=DurableTaskSpecV2,
    )
    task_spec = task_owner.task_spec
    objective_specs = {item.objective_id: item for item in task_spec.objectives}
    objective_runs = {
        item.objective_key: item for item in objectives.list_objectives(run.id)
    }
    for candidate in objective_runs.values():
        if candidate.command_id is not None or candidate.status != "queued":
            continue
        dependency_runs = tuple(
            objective_runs[key] for key in candidate.dependency_keys
        )
        if not dependency_runs or any(
            item.status not in {"completed", "proposed", "denied", "failed", "degraded"}
            for item in dependency_runs
        ):
            continue
        edges = tuple(
            edge
            for edge in task_spec.dependency_edges
            if edge.to_objective_id == candidate.objective_key
        )
        required_failed = any(
            edge.required
            and objective_runs[edge.from_objective_id].status in {"failed", "degraded"}
            for edge in edges
        )
        if required_failed:
            candidate.status = "failed"
            candidate.error_code = "required_dependency_failed"
            continue
        specification = objective_specs[candidate.objective_key]
        capability = {
            "risk_analysis": "platform.risk.analyse",
            "daily_summary": "platform.daily.summarise",
            "record_change": "platform.action.propose",
            "task_creation": "platform.action.propose",
            "reminder_request": "platform.action.propose",
        }.get(candidate.kind)
        if capability is None:
            raise OrchestratorError("stage12_downstream_capability_invalid")
        dependency_artifact_ids = _stage12_dependency_artifacts(
            runtime,
            objective_runs=objective_runs,
            objective_key=candidate.objective_key,
            capability=capability,
        )
        if capability == "platform.action.propose":
            dependency_artifact_ids = _materialize_stage12_action_dependencies(
                runtime,
                artifact_uow,
                run=run,
                task_spec=task_spec,
                objective_id=candidate.objective_key,
                dependency_artifact_ids=dependency_artifact_ids,
                now=now,
            )
        objective_values = {
            "version": "objective-specialist-input.v1",
            "objective_id": specification.objective_id,
            "capability_id": capability,
            "task_spec_ref": objective_input.task_spec_ref,
            "input_artifact_refs": dependency_artifact_ids,
            "scope_hash": objective_input.scope_hash,
            "schema_hash": objective_input.schema_hash,
            "data_version_hash": objective_input.data_version_hash,
        }
        downstream_input = ObjectiveSpecialistInputV1(
            **objective_values,
            content_hash=specialist_payload_sha256(objective_values),
        )
        owner = persist_typed_artifact(
            artifact_uow,
            workspace_id=run.workspace_id,
            run_id=run.id,
            artifact_kind="objective_specialist_input",
            payload=downstream_input,
            scope_hash=run.scope_hash,
        )
        objective_metadata = AgentArtifact(
            id=uuid4(),
            run_id=run.id,
            kind="objective_specialist_input",
            storage_ref=owner.storage_ref,
            content_hash=owner.content_hash,
            visibility_scope_hash=run.scope_hash,
            validation_status="validated",
            expires_at=run.deadline_at,
        )
        runtime.add_artifact(objective_metadata)
        runtime.flush()
        private_id = uuid4()
        command_id = uuid4()
        private_ref = f"agent-private-input:{private_id}"
        downstream_command = dispatch_unlocked_specialist_command(
            runtime,
            run_id=run.id,
            parent_command_id=command.id,
            target_capability=capability,
            payload_ref=private_ref,
            input_artifact_refs=(objective_metadata.id, *dependency_artifact_ids),
            authorization_hash=run.scope_hash,
            worker_id=worker_id,
            now=now,
            command_id=command_id,
        )
        if settings.agent_runtime_input_key is None:
            raise OrchestratorError("agent_private_input_key_unavailable")
        sealed = seal_agent_private_input(
            private_input,
            key_b64=settings.agent_runtime_input_key,
            key_version=settings.agent_runtime_input_key_version,
            run_id=run.id,
            command_id=downstream_command.id,
            scope_hash=run.scope_hash,
            expires_at=min(
                run.deadline_at,
                now + timedelta(seconds=settings.agent_runtime_input_ttl_seconds),
            ),
        )
        runtime.add_private_input(
            AgentPrivateInput(
                id=private_id,
                run_id=run.id,
                command_id=downstream_command.id,
                ciphertext=sealed.ciphertext,
                nonce=sealed.nonce,
                key_version=sealed.key_version,
                aad_hash=sealed.aad_hash,
                scope_hash=sealed.scope_hash,
                expires_at=sealed.expires_at,
                consumed_at=None,
            )
        )
        candidate.command_id = downstream_command.id


def _stage12_dependency_artifacts(
    runtime: object,
    *,
    objective_runs: Mapping[str, object],
    objective_key: str,
    capability: str,
) -> tuple[UUID, ...]:
    visited: set[str] = set()
    artifacts: list[AgentArtifact] = []

    def collect(key: str) -> None:
        if key in visited:
            return
        visited.add(key)
        value = objective_runs[key]
        for dependency_key in value.dependency_keys:
            collect(dependency_key)
        if value.result_artifact_id is not None:
            metadata = runtime.get_artifact(value.result_artifact_id)
            if metadata is None:
                raise OrchestratorError("stage12_dependency_artifact_missing")
            artifacts.append(metadata)

    for dependency_key in objective_runs[objective_key].dependency_keys:
        collect(dependency_key)
    allowed_kinds = {
        "platform.risk.analyse": {"structured_fact_set"},
        "platform.daily.summarise": {
            "structured_fact_set",
            "risk_assessment_set",
        },
        "platform.action.propose": {
            "structured_fact_set",
            "risk_assessment_set",
            "daily_brief",
        },
    }[capability]
    selected = [item for item in artifacts if item.kind in allowed_kinds]
    if capability == "platform.risk.analyse":
        policies = [
            item
            for item in runtime.list_artifacts(
                next(iter(objective_runs.values())).run_id
            )
            if item.kind == "authorized_risk_policy"
        ]
        if len(policies) != 1:
            raise OrchestratorError("stage12_risk_policy_missing")
        selected.extend(policies)
    identities = tuple(dict.fromkeys(item.id for item in selected))
    if not identities:
        raise OrchestratorError("stage12_dependency_artifact_missing")
    return identities


def _materialize_stage12_action_dependencies(
    runtime: object,
    artifact_uow: TypedArtifactUnitOfWork,
    *,
    run: object,
    task_spec: object,
    objective_id: str,
    dependency_artifact_ids: tuple[UUID, ...],
    now: datetime,
) -> tuple[UUID, ...]:
    slots = tuple(
        item for item in task_spec.action_slots if item.objective_id == objective_id
    )
    if len(slots) != 1:
        raise OrchestratorError("stage12_action_slot_cardinality_invalid")
    slot = slots[0]
    facts: list[StructuredFactSetV1] = []
    for artifact_id in dependency_artifact_ids:
        metadata = runtime.get_artifact(artifact_id)
        if metadata is None or metadata.kind != "structured_fact_set":
            continue
        facts.append(
            read_typed_artifact(
                artifact_uow,
                artifact=metadata,
                workspace_id=run.workspace_id,
                current_scope_hash=run.scope_hash,
                expected_kind="structured_fact_set",
                payload_type=StructuredFactSetV1,
            )
        )
    if not facts:
        raise OrchestratorError("stage12_action_fact_dependency_missing")
    table = next(
        (
            item
            for item in _stage12_schema_for_run(
                runtime,
                artifact_uow,
                run=run,
                now=now,
            ).tables
            if item.table_id == slot.target.table_id
        ),
        None,
    )
    if table is None:
        raise OrchestratorError("stage12_action_target_table_invalid")
    assignment_field_ids = tuple(
        item.field_id for item in slot.assignments if item.field_id is not None
    )
    writable_ids = {item.field_id for item in table.fields if item.writable}
    authorized_assignments = len(assignment_field_ids) == len(slot.assignments) and set(
        assignment_field_ids
    ).issubset(writable_ids)
    create_action = slot.action_kind in {"record.create", "task.create"}
    fact_records = tuple(
        record
        for facts_item in facts
        for record in facts_item.records
        if record.table_id == table.table_id
    )
    versions = {
        (item.table_id, item.record_id): item.record_version
        for facts_item in facts
        for item in facts_item.source_versions
    }
    selected_records = () if create_action else fact_records
    complete = (
        slot.planning_outcome == "planned"
        and authorized_assignments
        and all(item.complete and not item.truncated for item in facts)
        and (create_action or bool(selected_records))
        and len(selected_records) <= 24
    )
    candidate_values = {
        "version": "authorized-candidate-set.v1",
        "objective_id": objective_id,
        "slot_id": slot.slot_id,
        "candidates": tuple(
            {
                "table_id": record.table_id,
                "record_id": record.record_id,
                "record_version": versions[(record.table_id, record.record_id)],
                "writable_field_ids": tuple(sorted(assignment_field_ids, key=str)),
            }
            for record in selected_records
            if (record.table_id, record.record_id) in versions
        ),
        "scope_hash": run.scope_hash,
        "complete": complete,
    }
    candidate_values["candidate_set_hash"] = specialist_payload_sha256(candidate_values)
    candidates = AuthorizedCandidateSetV1.model_validate(candidate_values)
    evidence_values = {
        "version": "evidence-bundle.v2",
        "objective_id": objective_id,
        "query_result_ref": None,
        "nodes": tuple(
            {
                "evidence_id": f"action-record-{record.record_id}",
                "kind": "record",
                "source_id": f"record:{record.record_id}",
                "source_version": versions[(record.table_id, record.record_id)],
                "table_id": record.table_id,
                "record_id": record.record_id,
                "fields": tuple(
                    {
                        "field_id": value.field_id,
                        "field_key": next(
                            field.key
                            for field in table.fields
                            if field.field_id == value.field_id
                        ),
                        "value": value.value,
                    }
                    for value in record.values
                    if any(field.field_id == value.field_id for field in table.fields)
                ),
                "content_hash": specialist_payload_sha256(
                    {
                        "table_id": str(record.table_id),
                        "record_id": str(record.record_id),
                        "record_version": versions[(record.table_id, record.record_id)],
                        "values": tuple(
                            value.model_dump(mode="json") for value in record.values
                        ),
                    }
                ),
            }
            for record in selected_records[:24]
            if (record.table_id, record.record_id) in versions
        ),
        "relations": (),
        "aggregates": (),
        "scope_hash": run.scope_hash,
        "complete": complete,
        "truncated": not complete,
    }
    evidence_values["bundle_hash"] = canonical_retrieval_sha256(evidence_values)
    evidence = EvidenceBundleV2.model_validate(evidence_values)
    current_versions = []
    for candidate in candidates.candidates:
        record = artifact_uow.get_record(candidate.record_id)
        if record is None or record.table_id != candidate.table_id:
            raise OrchestratorError("stage12_action_current_version_missing")
        current_versions.append(
            {
                "table_id": record.table_id,
                "record_id": record.id,
                "record_version": record.version,
            }
        )
    proof_values = {
        "version": "current-version-proof.v1",
        "record_versions": tuple(current_versions),
        "scope_hash": run.scope_hash,
    }
    proof_values["content_hash"] = specialist_payload_sha256(proof_values)
    proof = CurrentVersionProofV1.model_validate(proof_values)
    generated = (
        ("action_slot", slot),
        ("authorized_candidate_set", candidates),
        ("evidence_bundle", evidence),
        ("current_version_proof", proof),
    )
    generated_ids = tuple(
        _persist_stage12_runtime_dependency(
            runtime,
            artifact_uow,
            run=run,
            kind=kind,
            payload=payload,
            now=now,
        )
        for kind, payload in generated
    )
    return (*dependency_artifact_ids, *generated_ids)


def _stage12_schema_for_run(
    runtime: object,
    artifact_uow: TypedArtifactUnitOfWork,
    *,
    run: object,
    now: datetime,
) -> AuthorizedSchemaSnapshot:
    artifacts = tuple(
        item
        for item in runtime.list_artifacts(run.id)
        if item.kind == "authorized_schema_snapshot"
        and item.validation_status == "validated"
        and (item.expires_at is None or item.expires_at > now)
    )
    if len(artifacts) != 1:
        raise OrchestratorError("stage12_authorized_schema_artifact_invalid")
    return read_typed_artifact(
        artifact_uow,
        artifact=artifacts[0],
        workspace_id=run.workspace_id,
        current_scope_hash=run.scope_hash,
        expected_kind="authorized_schema_snapshot",
        payload_type=AuthorizedSchemaSnapshot,
    )


def _persist_stage12_runtime_dependency(
    runtime: object,
    artifact_uow: TypedArtifactUnitOfWork,
    *,
    run: object,
    kind: str,
    payload: BaseModel,
    now: datetime,
) -> UUID:
    owner = persist_typed_artifact(
        artifact_uow,
        workspace_id=run.workspace_id,
        run_id=run.id,
        artifact_kind=kind,
        payload=payload,
        scope_hash=run.scope_hash,
    )
    metadata = AgentArtifact(
        id=uuid4(),
        run_id=run.id,
        kind=kind,
        storage_ref=owner.storage_ref,
        content_hash=owner.content_hash,
        visibility_scope_hash=run.scope_hash,
        validation_status="validated",
        expires_at=run.deadline_at,
    )
    runtime.add_artifact(metadata)
    runtime.flush()
    return metadata.id


def _stage12_objective_from_envelope(
    runtime: object,
    artifact_uow: TypedArtifactUnitOfWork,
    *,
    run: object,
    command: object,
    envelope: AgentCommandEnvelope,
    authorization_hash: str,
    now: datetime,
    allow_expired: bool = False,
) -> ObjectiveSpecialistInputV1:
    referenced = tuple(
        runtime.get_artifact(ref) for ref in envelope.input_artifact_refs
    )
    owners = tuple(
        item
        for item in referenced
        if item is not None
        and item.run_id == run.id
        and item.kind == "objective_specialist_input"
        and item.visibility_scope_hash == authorization_hash
        and item.validation_status == "validated"
        and (allow_expired or item.expires_at is None or item.expires_at > now)
    )
    if len(owners) != 1:
        raise OrchestratorError("typed_specialist_objective_owner_invalid")
    return read_typed_artifact(
        artifact_uow,
        artifact=owners[0],
        workspace_id=run.workspace_id,
        current_scope_hash=authorization_hash,
        expected_kind="objective_specialist_input",
        payload_type=ObjectiveSpecialistInputV1,
    )


def _durable_envelope_for_command(
    runtime: object,
    command: object,
) -> AgentCommandEnvelope:
    persisted = runtime.get_outbox_event_by_event_id(command.id)
    if persisted is None:
        raise ValueError("agent_command_outbox_missing")
    try:
        return AgentCommandEnvelope.model_validate_json(
            json.dumps(persisted.payload_json)
        )
    except Exception as exc:
        raise ValueError("agent_command_envelope_invalid") from exc


def _authorized_record_labels(
    artifact_uow: TypedArtifactUnitOfWork,
    *,
    schema: AuthorizedSchemaSnapshot,
    fact_sets: tuple[StructuredFactSetV1, ...],
) -> dict[UUID, str]:
    get_record = getattr(artifact_uow, "get_record", None)
    if not callable(get_record):
        return {}
    tables = {table.table_id: table for table in schema.tables}
    labels: dict[UUID, str] = {}
    for fact_set in fact_sets:
        for fact_record in fact_set.records:
            table = tables.get(fact_record.table_id)
            record = get_record(fact_record.record_id)
            if (
                table is None
                or record is None
                or record.table_id != fact_record.table_id
            ):
                continue
            fields = {field.field_id: field for field in table.fields}
            for field_id in (table.label_field_id, table.identity_field_id):
                field = fields.get(field_id)
                if field is None:
                    continue
                value = record.values.get(field.key)
                if isinstance(value, (str, int, float)) and str(value).strip():
                    labels[fact_record.record_id] = str(value).strip()[:120]
                    break
    return labels


def _fan_in_typed_results(
    runtime: object,
    artifact_uow: TypedArtifactUnitOfWork,
    *,
    run_id,
    workspace_id,
    scope_hash: str,
    now: datetime | None = None,
    stage12_query: str | None = None,
    stage12_schema: AuthorizedSchemaSnapshot | None = None,
    stage12_settings: Settings | None = None,
    stage12_provider: GroundedProvider | None = None,
) -> SpecialistSafeResult:
    effective_now = now or datetime.now(UTC)
    commands = runtime.list_commands(run_id, for_update=True)
    objective_by_command: dict[object, ObjectiveSpecialistInputV1] = {}
    for command in commands:
        if command.payload_ref is None:
            raise ValueError("typed_specialist_input_ref_missing")
        if command.payload_ref.startswith("agent-private-input:"):
            durable = _durable_envelope_for_command(runtime, command)
            run = runtime.get_run(run_id)
            if run is None:
                raise ValueError("typed_specialist_run_missing")
            objective_by_command[command.id] = _stage12_objective_from_envelope(
                runtime,
                artifact_uow,
                run=run,
                command=command,
                envelope=durable,
                authorization_hash=scope_hash,
                now=effective_now,
            )
        else:
            objective_by_command[command.id] = read_typed_artifact_owner_ref(
                artifact_uow,
                storage_ref=command.payload_ref,
                workspace_id=workspace_id,
                current_scope_hash=scope_hash,
                expected_kind="objective_specialist_input",
                payload_type=ObjectiveSpecialistInputV1,
            )

    output_by_command: dict[object, BaseModel] = {}
    for event in runtime.list_events(run_id):
        if event.event_type != "agent.completed" or event.artifact_ref is None:
            continue
        metadata = runtime.get_artifact(event.artifact_ref)
        if metadata is None or metadata.kind not in _TYPED_ARTIFACT_TYPES:
            continue
        output_by_command[event.command_id] = read_typed_artifact(
            artifact_uow,
            artifact=metadata,
            workspace_id=workspace_id,
            current_scope_hash=scope_hash,
            expected_kind=metadata.kind,
            payload_type=_TYPED_ARTIFACT_TYPES[metadata.kind],
        )

    upstream_payloads: list[BaseModel] = []
    for objective in objective_by_command.values():
        for artifact_ref in objective.input_artifact_refs:
            metadata = runtime.get_artifact(artifact_ref)
            if metadata is None or metadata.kind not in _TYPED_ARTIFACT_TYPES:
                raise ValueError("typed_fan_in_upstream_artifact_missing")
            upstream_payloads.append(
                read_typed_artifact(
                    artifact_uow,
                    artifact=metadata,
                    workspace_id=workspace_id,
                    current_scope_hash=scope_hash,
                    expected_kind=metadata.kind,
                    payload_type=_TYPED_ARTIFACT_TYPES[metadata.kind],
                )
            )

    required_ids: set[object] = set()
    optional_ids: set[object] = set()
    for checkpoint in reversed(runtime.list_checkpoints(run_id)):
        control = checkpoint.control_json
        if control.get("required_command_ids") or control.get("optional_command_ids"):
            required_ids = {str(value) for value in control["required_command_ids"]}
            optional_ids = {str(value) for value in control["optional_command_ids"]}
            break
    if not required_ids and not optional_ids:
        required_ids = {
            str(item.id)
            for item in commands
            if item.target_capability
            in {"platform.tabular.analyse", "platform.action.propose"}
        }
        optional_ids = {str(item.id) for item in commands} - required_ids
    stage12_run = runtime.get_run(run_id)
    runtime_session = getattr(runtime, "session", None)
    objective_rows = ()
    stage12_task_spec = None
    if (
        stage12_run is not None
        and stage12_run.workflow_version == "stage12.quality-v2.runtime.v1"
        and runtime_session is not None
    ):
        objective_rows = SqlAlchemyStage12ActionRuntimeRepository(
            runtime_session
        ).list_objectives(run_id)
        required_ids = {
            str(item.command_id)
            for item in objective_rows
            if item.command_id is not None and item.required
        }
        optional_ids = {
            str(item.command_id)
            for item in objective_rows
            if item.command_id is not None and not item.required
        }
        task_spec_refs = {
            objective.task_spec_ref for objective in objective_by_command.values()
        }
        if len(task_spec_refs) != 1:
            raise ValueError("stage12_grounded_task_spec_mismatch")
        stage12_task_spec = read_typed_artifact_owner_ref(
            artifact_uow,
            storage_ref=next(iter(task_spec_refs)),
            workspace_id=workspace_id,
            current_scope_hash=scope_hash,
            expected_kind="task_spec_v2",
            payload_type=DurableTaskSpecV2,
        ).task_spec

    output_facts = tuple(
        item
        for item in output_by_command.values()
        if isinstance(item, StructuredFactSetV1)
    )
    output_risks = tuple(
        item
        for item in output_by_command.values()
        if isinstance(item, RiskAssessmentSetV1)
    )
    output_dailies = tuple(
        item for item in output_by_command.values() if isinstance(item, DailyBriefV1)
    )
    facts = tuple(
        {
            item.content_hash: item
            for item in (*upstream_payloads, *output_facts)
            if isinstance(item, StructuredFactSetV1)
        }.values()
    )
    risks = tuple(
        {
            item.content_hash: item
            for item in (*upstream_payloads, *output_risks)
            if isinstance(item, RiskAssessmentSetV1)
        }.values()
    )
    dailies = tuple(
        {
            item.content_hash: item
            for item in (*upstream_payloads, *output_dailies)
            if isinstance(item, DailyBriefV1)
        }.values()
    )
    claims: list[ClaimInputV1] = []
    for fact_set in output_facts:
        claims.extend(claim_inputs_from_fact_set(fact_set))
    fact_version_by_hash = {
        item.content_hash: max(
            (version.record_version for version in item.source_versions),
            default=1,
        )
        for item in facts
    }
    for risk_set in output_risks:
        version = fact_version_by_hash.get(risk_set.fact_set_hash)
        if version is None:
            raise ValueError("typed_fan_in_risk_fact_missing")
        for assessment in risk_set.assessments:
            subject_ref = (
                assessment.subject_ref
                if ":" in assessment.subject_ref
                else f"record:{assessment.subject_ref}"
            )
            claims.append(
                ClaimInputV1(
                    objective_id=risk_set.objective_id,
                    subject_ref=subject_ref,
                    predicate="risk_severity",
                    value=assessment.severity,
                    evidence_ids=assessment.evidence_ids,
                    source_version=version,
                )
            )

    outcomes: list[ObjectiveOutcomeInputV1] = []
    actions: list[ActionDependencyV1] = []
    for command in commands:
        objective = objective_by_command[command.id]
        output = output_by_command.get(command.id)
        required = str(command.id) in required_ids
        if command.status == "failed":
            state = "failed"
            reason = "specialist_failed"
        elif isinstance(output, ControlledActionProposalV1):
            state = "denied" if output.status == "deferred" else output.status
            reason = output.denial_reason
            actions.append(
                ActionDependencyV1(
                    slot_id=output.slot_id,
                    proposal_status=output.status,
                    required_claim_refs=(),
                    reason_code=output.denial_reason,
                )
            )
        else:
            state = "completed"
            reason = None
        outcomes.append(
            ObjectiveOutcomeInputV1(
                objective.objective_id,
                state,
                required,
                reason,
            )
        )
    command_objective_ids = {
        objective.objective_id for objective in objective_by_command.values()
    }
    for objective_row in objective_rows:
        if objective_row.objective_key in command_objective_ids:
            continue
        if objective_row.status not in {"denied", "failed", "degraded"}:
            raise ValueError("typed_fan_in_objective_not_terminal")
        outcomes.append(
            ObjectiveOutcomeInputV1(
                objective_row.objective_key,
                "denied" if objective_row.status == "denied" else "failed",
                objective_row.required,
                objective_row.error_code,
            )
        )
    represented_action_slots = {item.slot_id for item in actions}
    if stage12_task_spec is not None:
        objective_rows_by_key = {item.objective_key: item for item in objective_rows}
        for slot in stage12_task_spec.action_slots:
            if slot.slot_id in represented_action_slots:
                continue
            objective_row = objective_rows_by_key.get(slot.objective_id)
            if slot.planning_outcome == "planned" and (
                objective_row is None or objective_row.status != "denied"
            ):
                raise ValueError("typed_fan_in_action_result_missing")
            actions.append(
                ActionDependencyV1(
                    slot_id=slot.slot_id,
                    proposal_status="denied",
                    required_claim_refs=(),
                    reason_code=(
                        slot.denial_reason
                        or (None if objective_row is None else objective_row.error_code)
                        or "action_denied"
                    ),
                )
            )

    graph = build_claim_graph(
        claims=tuple(claims),
        outcomes=tuple(outcomes),
        actions=tuple(actions),
        scope_hash=scope_hash,
        source_artifacts=(*facts, *risks),
    )
    graph_owner = persist_typed_artifact(
        artifact_uow,
        workspace_id=workspace_id,
        run_id=run_id,
        artifact_kind="claim_graph",
        payload=graph,
        scope_hash=scope_hash,
    )
    runtime.add_artifact(
        AgentArtifact(
            id=uuid4(),
            run_id=run_id,
            kind="claim_graph",
            storage_ref=graph_owner.storage_ref,
            content_hash=graph_owner.content_hash,
            visibility_scope_hash=scope_hash,
            validation_status="validated",
            expires_at=None,
        )
    )
    if stage12_run is not None and stage12_run.workflow_version == (
        "stage12.quality-v2.runtime.v1"
    ):
        if (
            stage12_query is None
            or stage12_schema is None
            or (stage12_settings is None and stage12_provider is None)
        ):
            raise ValueError("stage12_grounded_fan_in_context_missing")
        if stage12_task_spec is None:
            raise ValueError("stage12_grounded_task_spec_mismatch")
        task_spec = stage12_task_spec
        if (
            stage12_schema.scope_hash != scope_hash
            or stage12_schema.schema_hash != task_spec.authorized_schema_hash
        ):
            raise ValueError("stage12_grounded_schema_mismatch")
        findings = (*facts, *risks, *dailies)
        presentation = build_stage12_presentation(
            query=stage12_query,
            task_spec=task_spec,
            claim_graph=graph,
            authorized_schema=stage12_schema,
            specialist_findings=findings,
            record_labels=_authorized_record_labels(
                artifact_uow,
                schema=stage12_schema,
                fact_sets=facts,
            ),
        )
        provider = stage12_provider
        if provider is None:
            if stage12_settings is None:
                raise ValueError("stage12_grounded_provider_settings_missing")
            provider = build_stage12_grounded_provider(stage12_settings)
        composer = compose_stage12_grounded_result(
            query=stage12_query,
            task_spec=task_spec,
            claim_graph=graph,
            authorized_schema=stage12_schema,
            presentation=presentation,
            specialist_findings=findings,
            provider=provider,
        )
        composer_kind = "grounded_composer_result"
    else:
        composer = compose_claim_graph(graph)
        composer_kind = "composer_result"
    composer_owner = persist_typed_artifact(
        artifact_uow,
        workspace_id=workspace_id,
        run_id=run_id,
        artifact_kind=composer_kind,
        payload=composer,
        scope_hash=scope_hash,
    )
    return SpecialistSafeResult(
        storage_ref=composer_owner.storage_ref,
        content_hash=composer_owner.content_hash,
        safe_summary=composer.answer[:240],
        metrics={"claims": len(graph.claims)},
        artifact_kind=composer_kind,
    )


def _process_legacy_action(
    session: Session,
    envelope: AgentCommandEnvelope,
    *,
    settings: Settings,
    worker_id: str,
) -> None:
    if settings.agent_runtime_input_key is None:
        raise RuntimeError("agent_private_input_key_unavailable")
    runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
    run = runtime.get_run(envelope.run_id)
    if run is None or not durable_action_v1_enabled(settings, run.workspace_id):
        raise RuntimeError("durable_action_runtime_disabled")
    process_stage12_action_command(
        runtime,
        SqlAlchemyStage12ActionRuntimeRepository(session),
        SqlAlchemyStage06PlatformUnitOfWork(session),
        envelope,
        private_key_b64=settings.agent_runtime_input_key,
        worker_id=worker_id,
    )
    session.commit()


class AgentSpecialistWorkerPool:
    def __init__(
        self,
        *,
        streams: RedisStreams,
        consumer_name: str,
        process_by_capability: Mapping[str, Callable[[AgentCommandEnvelope], None]],
        pending_min_idle_ms: int = 30_000,
    ) -> None:
        if set(process_by_capability) != set(SPECIALIST_CAPABILITIES):
            raise RuntimeError("specialist_process_registry_incomplete")
        self.workers = tuple(
            AgentTabularStreamWorker(
                streams=streams,
                consumer_name=f"{consumer_name}-{capability.split('.')[1]}",
                process=process_by_capability[capability],
                stream_name=f"agent.commands.{capability}",
                group_name=f"stage11-{capability.replace('.', '-')}-workers",
                pending_min_idle_ms=pending_min_idle_ms,
            )
            for capability in SPECIALIST_CAPABILITIES
        )

    def run_once(self, limit_per_capability: int = 4) -> AgentSpecialistPoolResult:
        results: list[AgentTabularWorkerResult] = [
            worker.run_once(limit=limit_per_capability) for worker in self.workers
        ]
        return AgentSpecialistPoolResult(
            processed=sum(item.processed for item in results),
            recovered=sum(item.recovered for item in results),
            dead_lettered=sum(item.dead_lettered for item in results),
        )

    def run_continuously(self) -> None:
        while True:
            if self.run_once() == AgentSpecialistPoolResult():
                sleep(0.25)


def main() -> None:
    settings = validate_runtime_settings()
    if settings.agent_event_runtime_mode != "redis_worker":
        raise RuntimeError("Stage11 specialist worker requires redis_worker mode")
    streams = RedisStreamsClient.from_url(settings.redis_url)
    session_factory = get_session_factory()
    consumer_name = os.getenv("AGENT_SPECIALIST_CONSUMER_NAME", "stage11-specialist-1")

    AgentSpecialistWorkerPool(
        streams=streams,
        consumer_name=consumer_name,
        process_by_capability=build_typed_specialist_process_registry(
            session_factory=session_factory,
            settings=settings,
            consumer_name=consumer_name,
        ),
    ).run_continuously()


__all__ = [
    "AgentSpecialistPoolResult",
    "AgentSpecialistWorkerPool",
    "SPECIALIST_CAPABILITIES",
    "TypedSpecialistCommandProcessor",
    "build_typed_specialist_process_registry",
    "process_typed_specialist_command",
]


if __name__ == "__main__":
    main()
