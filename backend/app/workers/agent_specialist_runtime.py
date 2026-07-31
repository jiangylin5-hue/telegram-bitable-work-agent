from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
import json
import os
from time import sleep
from typing import Callable, Mapping
from uuid import uuid4

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
from app.models.agent_event_runtime import AgentArtifact
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
)
from app.schemas.agent_task_spec_v2 import ActionSlotV1
from app.schemas.authorized_query_plan import StructuredQueryArtifactV1
from app.schemas.retrieval_v2 import EvidenceBundleV2
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
)
from app.services.agent_composer_v2 import compose_claim_graph
from app.services.agent_orchestrator import (
    OrchestratorError,
    SpecialistSafeResult,
    execute_read_only_specialist,
    fail_specialist_command,
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
from app.services.stage06_platform import SqlAlchemyStage06PlatformUnitOfWork
from app.services.stage12_action_runtime import SqlAlchemyStage12ActionRuntimeRepository
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
class TypedSpecialistCommandProcessor:
    typed_handler: SpecialistHandler
    session_factory: Callable[[], Session]
    settings: Settings
    worker_id: str

    def __call__(self, envelope: AgentCommandEnvelope) -> None:
        with self.session_factory() as session:
            command = SqlAlchemyAgentEventRuntimeUnitOfWork(session).get_command(
                envelope.command_id,
                for_update=True,
            )
            if command is None:
                raise RuntimeError("agent_command_not_found")
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
            ),
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
) -> None:
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
    objective = read_typed_artifact_owner_ref(
        artifact_uow,
        storage_ref=command.payload_ref,
        workspace_id=run.workspace_id,
        current_scope_hash=authorization_hash,
        expected_kind="objective_specialist_input",
        payload_type=ObjectiveSpecialistInputV1,
    )
    if (
        objective.capability_id != envelope.target_capability
        or objective.scope_hash != authorization_hash
        or objective.input_artifact_refs != envelope.input_artifact_refs
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
    )
    execute_read_only_specialist(
        runtime,
        command_id=command.id,
        authorization_hash=authorization_hash,
        worker_id=worker_id,
        now=now,
        execute=execute,
        fan_in=fan_in,
    )


def _fan_in_typed_results(
    runtime: object,
    artifact_uow: TypedArtifactUnitOfWork,
    *,
    run_id,
    workspace_id,
    scope_hash: str,
) -> SpecialistSafeResult:
    commands = runtime.list_commands(run_id, for_update=True)
    objective_by_command: dict[object, ObjectiveSpecialistInputV1] = {}
    for command in commands:
        if command.payload_ref is None:
            raise ValueError("typed_specialist_input_ref_missing")
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
    claims: list[ClaimInputV1] = []
    for fact_set in output_facts:
        versions = {
            (item.table_id, item.record_id): item.record_version
            for item in fact_set.source_versions
        }
        aggregate_version = max(versions.values(), default=1)
        for record in fact_set.records:
            version = versions[(record.table_id, record.record_id)]
            for field in record.values:
                claims.append(
                    ClaimInputV1(
                        objective_id=fact_set.objective_id,
                        subject_ref=f"record:{record.record_id}",
                        predicate=f"field:{field.field_id}",
                        value=field.value,
                        evidence_ids=fact_set.evidence_refs,
                        source_version=version,
                    )
                )
        for aggregate in fact_set.aggregates:
            claims.append(
                ClaimInputV1(
                    objective_id=fact_set.objective_id,
                    subject_ref=f"aggregate:{aggregate.aggregate_id}",
                    predicate="value",
                    value=aggregate.value,
                    evidence_ids=fact_set.evidence_refs,
                    source_version=aggregate_version,
                )
            )
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
    composer = compose_claim_graph(graph)
    composer_owner = persist_typed_artifact(
        artifact_uow,
        workspace_id=workspace_id,
        run_id=run_id,
        artifact_kind="composer_result",
        payload=composer,
        scope_hash=scope_hash,
    )
    return SpecialistSafeResult(
        storage_ref=composer_owner.storage_ref,
        content_hash=composer_owner.content_hash,
        safe_summary=composer.answer[:240],
        metrics={"claims": len(graph.claims)},
        artifact_kind="composer_result",
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
