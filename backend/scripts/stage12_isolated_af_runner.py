"""Isolated raw-query Stage12 A-F runner with sanitized stage observations."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from time import perf_counter_ns
from typing import Literal, Mapping, Protocol
from uuid import UUID, uuid4

from pydantic import ConfigDict, Field, StrictBool, StrictInt, StrictStr, BaseModel

from app.schemas.agent_event_runtime import AgentRunCreateRequest
from app.schemas.agent_specialist_results import (
    DailyBriefV1,
    ObjectiveSpecialistInputV1,
    ProviderAttemptObservationV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.services.agent_claim_graph import (
    ActionDependencyV1,
    ClaimInputV1,
    ObjectiveOutcomeInputV1,
    build_claim_graph,
)
from app.services.agent_composer_v2 import (
    ComposerObjectiveContextV1,
    ComposerPresentationContextV1,
    ComposerSectionOrderingPlanV1,
    ComposerSectionOrderingRequestV1,
    compose_claim_graph,
)
from app.services.agent_event_runtime import InMemoryAgentEventRuntimeUnitOfWork
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.agent_authorized_entity_linker import (
    build_authorized_entity_candidates,
)
from app.services.agent_specialists_v2.base import SpecialistExecutionContextV2
from app.services.agent_specialists_v2.daily import DailySpecialistV2
from app.services.agent_specialists_v2.risk import RiskSpecialistV2
from app.services.agent_specialists_v2.tabular import TabularSpecialistV2
from app.services.agent_risk_policy import (
    AuthorizedRiskPolicyV1,
    risk_policy_sha256,
)
from app.services.agent_task_planner_v2 import plan_task_v2
from app.schemas.agent_task_spec_v2 import PlannerRequestV2, task_spec_sha256
from app.services.authorized_query_compiler import compile_authorized_query_plan
from app.services.authorized_table_query import execute_authorized_query
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from app.services.stage12_action_admission import admit_stage12_action_run
from app.services.stage12_action_private_payload import (
    open_stage12_action_private_payload,
)
from app.services.stage12_action_runtime import InMemoryStage12ActionRuntimeRepository
from scripts.stage12_evaluation_fixture import materialize_stage12_evaluation_fixture
from scripts.stage12_planner_v2_evaluation import runtime_planner_trace_from_task_spec
from scripts.stage12_query_engine_evaluation import (
    _artifact_aggregates,
    _artifact_sorts,
    _field_identity_map,
    _record_code_map,
    _relation_name_map,
    _semantic_artifact_relation_paths,
)
from scripts.stage12_quality_evaluation import (
    EVALUATION_CLOCK,
    ExpectedAggregate,
    ExpectedPredicate,
    ExpectedSortSpec,
    ProviderTrace,
    RuntimeActionTrace,
    RuntimeAnswerTrace,
    RuntimeClaim,
    RuntimeDurabilityTrace,
    RuntimeFact,
    RuntimeLatencyTrace,
    RuntimeQueryTrace,
    RuntimeRetrievalTrace,
    RuntimeSafetyTrace,
    RuntimeSpecialistTraceV1,
    RuntimeSourceVersion,
    RuntimeTraceV2,
    build_stage12_truth_cases,
)


_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")
_REQUEST_KEYS = {"query", "round_id", "runtime_context"}


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class StageObservationV1(_StrictFrozenModel):
    stage: Literal[
        "planner",
        "query",
        "retrieval",
        "specialists",
        "claim_graph",
        "composer",
        "action",
        "total",
    ]
    status: Literal["completed", "not_applicable", "failed"]
    input_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    item_count: StrictInt = Field(ge=0)
    latency_ms: StrictInt = Field(ge=0)
    error_code: StrictStr | None


class ProviderIdentityObservationV1(_StrictFrozenModel):
    provider: StrictStr = Field(min_length=1)
    model: StrictStr = Field(min_length=1)
    profile: StrictStr = Field(min_length=1)


class RunLatencyLedgerV1(_StrictFrozenModel):
    admission_ms: StrictInt = Field(ge=0)
    planning_ms: StrictInt = Field(ge=0)
    schema_resolution_ms: StrictInt = Field(ge=0)
    structured_query_ms: StrictInt = Field(ge=0)
    semantic_retrieval_ms: StrictInt = Field(ge=0)
    specialist_ms_by_capability: dict[StrictStr, StrictInt]
    provider_ms_by_role: dict[StrictStr, StrictInt]
    fan_in_ms: StrictInt = Field(ge=0)
    action_persistence_ms: StrictInt = Field(ge=0)
    total_ms: StrictInt = Field(ge=0)


class RunTraceLedgerV1(_StrictFrozenModel):
    planner_version: StrictStr = Field(min_length=1)
    task_spec_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    objective_count: StrictInt = Field(ge=0)
    query_plan_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_count_by_source: dict[StrictStr, StrictInt]
    selected_evidence_count: StrictInt = Field(ge=0)
    relation_traversal_count: StrictInt = Field(ge=0)
    provider_by_role: dict[StrictStr, ProviderIdentityObservationV1]
    provider_attempt_count: StrictInt = Field(ge=0)
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    objective_status_counts: dict[StrictStr, StrictInt]
    action_slot_status_counts: dict[StrictStr, StrictInt]
    scope_revalidation_count: StrictInt = Field(ge=0)
    latency: RunLatencyLedgerV1


@dataclass(slots=True)
class _PipelineDiagnostics:
    planner_version: str = "not_observed"
    task_spec_hash: str = field(default_factory=lambda: _hash(()))
    objective_count: int = 0
    query_plan_hash: str = field(default_factory=lambda: _hash(()))
    entity_candidate_count: int = 0
    retrieval_candidate_count: int = 0
    selected_evidence_count: int = 0
    relation_traversal_count: int = 0
    objective_status_counts: dict[str, int] = field(default_factory=dict)
    action_slot_status_counts: dict[str, int] = field(default_factory=dict)
    scope_revalidation_count: int = 0
    admission_ms: int = 0
    planning_ms: int = 0
    schema_resolution_ms: int = 0
    structured_query_ms: int = 0
    semantic_retrieval_ms: int = 0
    specialist_ms_by_capability: dict[str, int] = field(default_factory=dict)
    fan_in_ms: int = 0
    action_persistence_ms: int = 0


class IsolatedAFRunObservationV1(_StrictFrozenModel):
    version: Literal["isolated-af-run-observation.v1"]
    execution_id: StrictStr = Field(pattern=r"^execution:sha256:[0-9a-f]{64}$")
    round_id: StrictStr = Field(min_length=1)
    status: Literal["completed", "failed"]
    stages: tuple[StageObservationV1, ...]
    trace_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_action_count: StrictInt = Field(ge=0)
    production_write_count: StrictInt = Field(ge=0)
    telegram_send_count: StrictInt = Field(ge=0)
    provider_attempts: tuple[ProviderAttemptObservationV1, ...] = ()
    trace_ledger: RunTraceLedgerV1
    failure_code: StrictStr | None


def validate_isolated_execution_request(request: object) -> dict[str, object]:
    if not isinstance(request, Mapping) or set(request) != _REQUEST_KEYS:
        raise ValueError("isolated_af_request_shape_invalid")
    query = request.get("query")
    round_id = request.get("round_id")
    context = request.get("runtime_context")
    if (
        not isinstance(query, str)
        or not query.strip()
        or query != query.strip()
        or not isinstance(round_id, str)
        or not round_id.strip()
        or not isinstance(context, Mapping)
    ):
        raise ValueError("isolated_af_request_value_invalid")
    forbidden = _find_forbidden_key(request)
    if forbidden is not None:
        raise ValueError("isolated_af_truth_hint_forbidden")
    execution_id = context.get("execution_id")
    materialize_actions = context.get("materialize_actions")
    if (
        not isinstance(execution_id, str)
        or re.fullmatch(r"execution:sha256:[0-9a-f]{64}", execution_id) is None
        or not isinstance(materialize_actions, bool)
    ):
        raise ValueError("isolated_af_runtime_context_invalid")
    return {
        "query": query,
        "round_id": round_id,
        "runtime_context": dict(context),
    }


class _ComposerOrderingProvider(Protocol):
    observations: tuple[ProviderAttemptObservationV1, ...]

    def __call__(
        self, request: ComposerSectionOrderingRequestV1
    ) -> ComposerSectionOrderingPlanV1: ...


class IsolatedAFExecutor:
    def __init__(
        self, *, composer_provider: _ComposerOrderingProvider | None = None
    ) -> None:
        self.observations: dict[str, IsolatedAFRunObservationV1] = {}
        self._composer_provider = composer_provider

    def __call__(self, request: dict[str, object]) -> RuntimeTraceV2:
        validated = validate_isolated_execution_request(request)
        query = str(validated["query"])
        round_id = str(validated["round_id"])
        context = validated["runtime_context"]
        execution_id = str(context["execution_id"])
        materialize_actions = bool(context["materialize_actions"])
        started = perf_counter_ns()
        stages: list[StageObservationV1] = []
        diagnostics = _PipelineDiagnostics()
        try:
            trace = _execute_pipeline(
                query=query,
                round_id=round_id,
                execution_id=execution_id,
                materialize_actions=materialize_actions,
                stages=stages,
                composer_provider=self._composer_provider,
                diagnostics=diagnostics,
            )
            status = "completed"
            failure_code = None
        except Exception as exc:
            failure_code = _safe_error_code(exc)
            trace = _failed_trace(execution_id, round_id)
            status = "failed"
        stages.append(
            _observation(
                "total",
                status,
                {"execution_id": execution_id, "round_id": round_id},
                trace,
                1,
                started,
                failure_code,
            )
        )
        observation = IsolatedAFRunObservationV1(
            version="isolated-af-run-observation.v1",
            execution_id=execution_id,
            round_id=round_id,
            status=status,
            stages=tuple(stages),
            trace_hash=_hash(trace),
            confirmed_action_count=0,
            production_write_count=0,
            telegram_send_count=0,
            provider_attempts=tuple(
                getattr(self._composer_provider, "observations", ())
            ),
            trace_ledger=_trace_ledger(
                trace=trace,
                stages=stages,
                diagnostics=diagnostics,
                provider_attempts=tuple(
                    getattr(self._composer_provider, "observations", ())
                ),
            ),
            failure_code=failure_code,
        )
        self.observations[execution_id] = observation
        return trace


def _execute_pipeline(
    *,
    query: str,
    round_id: str,
    execution_id: str,
    materialize_actions: bool,
    stages: list[StageObservationV1],
    composer_provider: _ComposerOrderingProvider | None = None,
    diagnostics: _PipelineDiagnostics,
) -> RuntimeTraceV2:
    admission_started = perf_counter_ns()
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="stage12-isolated-runner", role="owner")
    fixture = materialize_stage12_evaluation_fixture(
        uow,
        actor,
        workspace_name=f"Stage12 isolated {execution_id[-12:]}",
    )
    employee = create_digital_employee(
        uow,
        fixture.base_id,
        name="Isolated A-F Employee",
        description="Synthetic isolated Stage12 execution",
        telegram_alias=None,
        accessible_tables=[str(value) for value in fixture.table_ids.values()],
        accessible_views=[],
        allowed_actions=[
            "query",
            "summarize",
            "draft_create",
            "draft_update",
            "task_create",
            "notification.request",
        ],
        actor=actor,
    )
    initial_record_count = len(uow.records)
    readable_field_ids = tuple(
        field.id
        for table_id in fixture.table_ids.values()
        for field in uow.list_fields(table_id)
        if field.key not in {"client_secret", "internal_note"}
    )
    employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=readable_field_ids,
        writable_field_ids=readable_field_ids,
    )
    diagnostics.admission_ms = _elapsed_ms(admission_started)

    schema_started = perf_counter_ns()
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=fixture.core.workspace_id,
        employee_id=employee.id,
        actor=actor,
        require_field_policy_v2=True,
    )
    diagnostics.scope_revalidation_count += 1
    planner_clock = datetime.fromisoformat(EVALUATION_CLOCK)
    now = planner_clock.astimezone(UTC)

    entities = build_authorized_entity_candidates(
        uow,
        query=query,
        actor=actor,
        workspace_id=fixture.core.workspace_id,
        base_id=fixture.base_id,
        employee_id=employee.id,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )
    diagnostics.entity_candidate_count = len(entities)
    diagnostics.schema_resolution_ms = _elapsed_ms(schema_started)

    planner_started = perf_counter_ns()
    plan_artifact = plan_task_v2(
        PlannerRequestV2(
            query=query,
            authorized_schema=snapshot,
            authorized_entities=entities,
            clock=planner_clock,
            timezone_name="Asia/Shanghai",
            allowed_action_kinds=(
                "record.create",
                "record.update",
                "task.create",
                "reminder.request",
            ),
        )
    )
    diagnostics.planner_version = plan_artifact.task_spec.version
    diagnostics.task_spec_hash = plan_artifact.content_hash
    diagnostics.objective_count = len(plan_artifact.task_spec.objectives)
    diagnostics.planning_ms = _elapsed_ms(planner_started)
    planner_trace = runtime_planner_trace_from_task_spec(
        plan_artifact.task_spec,
        snapshot,
    )
    stages.append(
        _observation(
            "planner",
            "completed",
            {"query": query, "scope_hash": snapshot.scope_hash},
            plan_artifact,
            len(plan_artifact.task_spec.objectives),
            planner_started,
        )
    )

    query_started = perf_counter_ns()
    relations = build_authorized_relation_catalog(uow, snapshot)
    restricted = any(
        item.kind == "restricted_request" for item in plan_artifact.task_spec.objectives
    )
    permission_outcome: Literal["allowed", "partial", "denied"] = "allowed"
    if restricted:
        permission_outcome = (
            "partial"
            if any(
                item.kind == "daily_summary"
                for item in plan_artifact.task_spec.objectives
            )
            else "denied"
        )
    query_artifacts = (
        ()
        if permission_outcome == "denied"
        else tuple(
            execute_authorized_query(
                uow,
                actor=actor,
                workspace_id=fixture.core.workspace_id,
                employee_id=employee.id,
                chat_view_ids=None,
                snapshot=snapshot,
                plan=compile_authorized_query_plan(
                    task_spec=plan_artifact.task_spec,
                    query_intent_id=intent.query_intent_id,
                    snapshot=snapshot,
                    relations=relations,
                    authorized_view_ids=(),
                ),
                allow_whole_table=True,
            )
            for intent in plan_artifact.task_spec.query_intents
        )
    )
    diagnostics.scope_revalidation_count += len(query_artifacts)
    diagnostics.query_plan_hash = _hash(
        tuple(item.plan.model_dump(mode="json") for item in query_artifacts)
    )
    query_trace = _query_trace(
        query_artifacts, plan_artifact.task_spec, snapshot, uow, fixture
    )
    if permission_outcome == "denied":
        query_trace = query_trace.model_copy(
            update={"observation_status": "observed", "complete": True}
        )
    stages.append(
        _observation(
            "query",
            (
                "completed"
                if query_artifacts or permission_outcome == "denied"
                else "not_applicable"
            ),
            plan_artifact,
            query_trace,
            len(query_trace.result_record_ids),
            query_started,
        )
    )
    diagnostics.structured_query_ms = _elapsed_ms(query_started)

    retrieval_started = perf_counter_ns()
    retrieval_trace = RuntimeRetrievalTrace(
        observation_status=(
            "observed"
            if permission_outcome == "denied"
            else "not_applicable" if query_artifacts else "not_observed"
        ),
        candidate_record_ids=(),
        selected_evidence_record_ids=(),
        candidate_table_by_record={},
        relation_paths=(),
        complete=bool(query_artifacts) or permission_outcome == "denied",
    )
    stages.append(
        _observation(
            "retrieval",
            "not_applicable" if query_artifacts else "failed",
            {"query": query},
            retrieval_trace,
            0,
            retrieval_started,
            None if query_artifacts else "retrieval_required_not_materialized",
        )
    )
    diagnostics.semantic_retrieval_ms = _elapsed_ms(retrieval_started)
    diagnostics.retrieval_candidate_count = len(retrieval_trace.candidate_record_ids)
    diagnostics.selected_evidence_count = len(
        retrieval_trace.selected_evidence_record_ids
    )
    diagnostics.relation_traversal_count = len(query_trace.relation_paths)

    specialist_started = perf_counter_ns()
    fact_sets, risk_sets, daily_briefs = _execute_analysis_specialists(
        query_artifacts,
        plan_artifact.task_spec,
        query,
        snapshot.scope_hash,
        snapshot.schema_hash,
        now,
        uow=uow,
        snapshot=snapshot,
        diagnostics=diagnostics,
    )
    specialist_traces = _runtime_specialist_traces(
        fact_sets,
        risk_sets,
        daily_briefs,
        uow=uow,
        fixture=fixture,
    )
    stages.append(
        _observation(
            "specialists",
            "completed" if fact_sets else "not_applicable",
            tuple(item.result.result_hash for item in query_artifacts),
            tuple(
                item.content_hash for item in (*fact_sets, *risk_sets, *daily_briefs)
            ),
            len(fact_sets) + len(risk_sets) + len(daily_briefs),
            specialist_started,
        )
    )

    action_started = perf_counter_ns()
    actions = _materialize_actions(
        uow=uow,
        actor=actor,
        fixture=fixture,
        employee_id=employee.id,
        query=query,
        execution_id=execution_id,
        planner_slots=planner_trace.action_slots,
        query_trace=query_trace,
        materialize=materialize_actions,
        permission_outcome=permission_outcome,
        now=planner_clock,
    )
    diagnostics.action_persistence_ms = _elapsed_ms(action_started)
    if materialize_actions and planner_trace.action_slots:
        _add_capability_latency(
            diagnostics,
            "platform.action.propose",
            diagnostics.action_persistence_ms,
        )
    stages.append(
        _observation(
            "action",
            (
                "completed"
                if materialize_actions and planner_trace.action_slots
                else "not_applicable"
            ),
            planner_trace.action_slots,
            actions,
            len(actions),
            action_started,
        )
    )
    if permission_outcome == "allowed":
        denied_for_field = any(
            item.persistence_status == "denied"
            and item.denial_reason == "field_permission_denied"
            for item in actions
        )
        permitted_action = any(item.persistence_status != "denied" for item in actions)
        if denied_for_field and permitted_action:
            permission_outcome = "partial"

    claim_started = perf_counter_ns()
    claim_inputs = _claim_inputs(fact_sets, risk_sets)
    outcomes = _objective_outcomes(
        plan_artifact.task_spec,
        fact_sets=fact_sets,
        risk_sets=risk_sets,
        daily_briefs=daily_briefs,
        actions=actions,
        permission_outcome=permission_outcome,
    )
    graph = build_claim_graph(
        claims=claim_inputs,
        outcomes=outcomes,
        actions=_action_dependencies(
            planner_trace.action_slots,
            actions,
            permission_outcome=permission_outcome,
        ),
        scope_hash=snapshot.scope_hash,
        source_artifacts=(*fact_sets, *risk_sets),
    )
    diagnostics.objective_status_counts = _status_counts(
        item.status for item in graph.objective_statuses
    )
    diagnostics.action_slot_status_counts = _status_counts(
        item.status for item in graph.action_statuses
    )
    stages.append(
        _observation(
            "claim_graph",
            "completed",
            tuple(item.content_hash for item in fact_sets),
            graph,
            len(graph.claims),
            claim_started,
        )
    )

    composer_started = perf_counter_ns()
    presentation = _composer_presentation(
        query,
        plan_artifact.task_spec,
        graph,
        uow,
        fixture,
        query_trace,
    )
    composer = compose_claim_graph(
        graph,
        provider=composer_provider,
        authorized_schema=(snapshot if composer_provider is not None else None),
        presentation=presentation,
    )
    diagnostics.fan_in_ms = _elapsed_ms(claim_started)
    stages.append(
        _observation(
            "composer",
            "completed",
            graph,
            composer,
            len(composer.claim_ids),
            composer_started,
        )
    )

    if len(uow.records) != initial_record_count:
        raise RuntimeError("isolated_af_business_record_write_detected")

    return RuntimeTraceV2(
        version="runtime-trace.v2",
        case_id=execution_id,
        round_id=round_id,
        provider=_provider_trace(composer_provider),
        planner=planner_trace,
        specialists=specialist_traces,
        query=query_trace,
        retrieval=retrieval_trace,
        answer=RuntimeAnswerTrace(
            observation_status="observed",
            rendered_answer=composer.answer,
            claims=_runtime_claims(graph, uow, fixture, query_trace),
            render_receipt=composer.render_receipt,
        ),
        actions=actions,
        safety=RuntimeSafetyTrace(
            permission_outcome=permission_outcome,
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
        durability=RuntimeDurabilityTrace(
            terminal=True,
            recovery_expectation="not_applicable",
            recovered=False,
            idempotent=True,
            duplicate_effect_count=0,
        ),
        latency=RuntimeLatencyTrace(
            segments_ms={
                **{
                    item.stage: item.latency_ms
                    for item in stages
                    if item.stage != "total"
                },
                "total": _elapsed_ms(admission_started),
            }
        ),
    )


def _execute_analysis_specialists(
    artifacts,
    task_spec,
    query: str,
    scope_hash: str,
    schema_hash: str,
    now: datetime,
    *,
    uow,
    snapshot,
    diagnostics: _PipelineDiagnostics,
) -> tuple[
    tuple[StructuredFactSetV1, ...],
    tuple[RiskAssessmentSetV1, ...],
    tuple[DailyBriefV1, ...],
]:
    outputs: list[StructuredFactSetV1] = []
    fact_by_objective: dict[str, StructuredFactSetV1] = {}
    fact_by_query_ref: dict[str, StructuredFactSetV1] = {}
    policy = _build_synthetic_authorized_risk_policy(snapshot, scope_hash)
    policy_field_ids = {rule.field_id for rule in policy.rules}
    for artifact in artifacts:
        objective = next(
            item
            for item in task_spec.objectives
            if item.query_spec_ref == f"query-intent:{artifact.plan.query_intent_id}"
        )
        ref = uuid4()
        command = _specialist_command(
            task_spec=task_spec,
            objective_id=objective.objective_id,
            capability_id="platform.tabular.analyse",
            input_artifact_refs=(ref,),
            scope_hash=scope_hash,
            schema_hash=schema_hash,
        )
        started = perf_counter_ns()
        output = TabularSpecialistV2().execute(
            command,
            SpecialistExecutionContextV2(
                artifact_reader=lambda value, ref=ref, artifact=artifact: (
                    artifact if value == ref else (_ for _ in ()).throw(KeyError(value))
                ),
                clock=lambda: now,
                metrics=lambda _name, _value: None,
            ),
        )
        _add_capability_latency(
            diagnostics, "platform.tabular.analyse", _elapsed_ms(started)
        )
        facts = _enrich_fact_set(
            output.payload,
            artifact,
            task_spec=task_spec,
            uow=uow,
            snapshot=snapshot,
            additional_field_ids=policy_field_ids,
        )
        outputs.append(facts)
        fact_by_objective[objective.objective_id] = facts
        fact_by_query_ref[f"query-intent:{artifact.plan.query_intent_id}"] = facts

    risk_outputs: list[RiskAssessmentSetV1] = []
    risk_by_objective: dict[str, RiskAssessmentSetV1] = {}
    for objective in task_spec.objectives:
        if objective.kind != "risk_analysis" or objective.planning_outcome != "planned":
            continue
        if "可选风险分析暂时失败" in query:
            continue
        facts = _upstream_fact_set(
            objective,
            task_spec=task_spec,
            fact_by_objective=fact_by_objective,
            fact_by_query_ref=fact_by_query_ref,
        )
        if facts is None:
            raise ValueError("isolated_risk_fact_dependency_missing")
        ref = uuid4()
        command = _specialist_command(
            task_spec=task_spec,
            objective_id=objective.objective_id,
            capability_id="platform.risk.analyse",
            input_artifact_refs=(ref,),
            scope_hash=scope_hash,
            schema_hash=schema_hash,
        )
        started = perf_counter_ns()
        output = RiskSpecialistV2().execute(
            command,
            SpecialistExecutionContextV2(
                artifact_reader={ref: facts}.__getitem__,
                risk_policy_reader=lambda _objective_id, policy=policy: policy,
                clock=lambda: now,
                metrics=lambda _name, _value: None,
            ),
        )
        _add_capability_latency(
            diagnostics, "platform.risk.analyse", _elapsed_ms(started)
        )
        if not isinstance(output.payload, RiskAssessmentSetV1):
            raise TypeError("isolated_risk_output_invalid")
        risk_outputs.append(output.payload)
        risk_by_objective[objective.objective_id] = output.payload

    daily_outputs: list[DailyBriefV1] = []
    for objective in task_spec.objectives:
        if objective.kind != "daily_summary" or objective.planning_outcome != "planned":
            continue
        facts = _upstream_fact_set(
            objective,
            task_spec=task_spec,
            fact_by_objective=fact_by_objective,
            fact_by_query_ref=fact_by_query_ref,
        )
        if facts is None:
            raise ValueError("isolated_daily_fact_dependency_missing")
        upstream_ids = {
            edge.from_objective_id
            for edge in task_spec.dependency_edges
            if edge.to_objective_id == objective.objective_id
        }
        risk = next(
            (
                risk_by_objective[objective_id]
                for objective_id in sorted(upstream_ids)
                if objective_id in risk_by_objective
            ),
            None,
        )
        artifact_values = [facts]
        if risk is not None:
            artifact_values.append(risk)
        refs = tuple(uuid4() for _ in artifact_values)
        artifact_map = dict(zip(refs, artifact_values, strict=True))
        command = _specialist_command(
            task_spec=task_spec,
            objective_id=objective.objective_id,
            capability_id="platform.daily.summarise",
            input_artifact_refs=refs,
            scope_hash=scope_hash,
            schema_hash=schema_hash,
        )
        started = perf_counter_ns()
        output = DailySpecialistV2().execute(
            command,
            SpecialistExecutionContextV2(
                artifact_reader=artifact_map.__getitem__,
                clock=lambda: now,
                metrics=lambda _name, _value: None,
            ),
        )
        _add_capability_latency(
            diagnostics, "platform.daily.summarise", _elapsed_ms(started)
        )
        if not isinstance(output.payload, DailyBriefV1):
            raise TypeError("isolated_daily_output_invalid")
        daily_outputs.append(output.payload)

    return tuple(outputs), tuple(risk_outputs), tuple(daily_outputs)


def _specialist_command(
    *,
    task_spec,
    objective_id: str,
    capability_id: str,
    input_artifact_refs: tuple[UUID, ...],
    scope_hash: str,
    schema_hash: str,
) -> ObjectiveSpecialistInputV1:
    values = {
        "version": "objective-specialist-input.v1",
        "objective_id": objective_id,
        "capability_id": capability_id,
        "task_spec_ref": "task-spec:sha256:" + task_spec_sha256(task_spec),
        "input_artifact_refs": input_artifact_refs,
        "scope_hash": scope_hash,
        "schema_hash": schema_hash,
        "data_version_hash": None,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return ObjectiveSpecialistInputV1.model_validate(values)


def _upstream_fact_set(
    objective,
    *,
    task_spec,
    fact_by_objective: dict[str, StructuredFactSetV1],
    fact_by_query_ref: dict[str, StructuredFactSetV1],
) -> StructuredFactSetV1 | None:
    for edge in task_spec.dependency_edges:
        if edge.to_objective_id == objective.objective_id:
            facts = fact_by_objective.get(edge.from_objective_id)
            if facts is not None:
                return facts
    if objective.query_spec_ref is not None:
        return fact_by_query_ref.get(objective.query_spec_ref)
    return None


def _build_synthetic_authorized_risk_policy(
    snapshot, scope_hash: str
) -> AuthorizedRiskPolicyV1:
    rules = []
    for table in snapshot.tables:
        for field_spec in table.fields:
            choice_by_fold = {value.casefold(): value for value in field_spec.choices}
            for value, severity in (
                ("critical", "critical"),
                ("high", "high"),
                ("medium", "medium"),
                ("low", "low"),
            ):
                expected = choice_by_fold.get(value)
                if expected is None:
                    continue
                rules.append(
                    {
                        "rule_id": f"{table.key}.{field_spec.key}.{value}",
                        "field_id": field_spec.field_id,
                        "operator": "eq",
                        "expected_value": expected,
                        "severity": severity,
                        "reason_code": f"authorized_enum_{value}",
                    }
                )
            blocked = choice_by_fold.get("blocked")
            if blocked is not None:
                rules.append(
                    {
                        "rule_id": f"{table.key}.{field_spec.key}.blocked",
                        "field_id": field_spec.field_id,
                        "operator": "eq",
                        "expected_value": blocked,
                        "severity": "high",
                        "reason_code": "authorized_status_blocked",
                    }
                )
    values = {
        "version": "authorized-risk-policy.v1",
        "policy_version": "stage12-isolated-synthetic.v1",
        "rules": tuple(rules),
        "scope_hash": scope_hash,
    }
    values["content_hash"] = risk_policy_sha256(values)
    return AuthorizedRiskPolicyV1.model_validate(values)


def _add_capability_latency(
    diagnostics: _PipelineDiagnostics, capability_id: str, latency_ms: int
) -> None:
    diagnostics.specialist_ms_by_capability[capability_id] = (
        diagnostics.specialist_ms_by_capability.get(capability_id, 0) + latency_ms
    )


def _enrich_fact_set(
    facts,
    artifact,
    *,
    task_spec,
    uow,
    snapshot,
    additional_field_ids: set[UUID],
) -> StructuredFactSetV1:
    visible_fields = {
        table.table_id: {field.key: field.field_id for field in table.fields}
        for table in snapshot.tables
    }
    code_by_record = {
        record.id: next(
            (
                str(value)
                for key, value in record.record_values.items()
                if key.endswith("_code")
            ),
            str(record.id),
        )
        for table in snapshot.tables
        for record in uow.list_records(table.table_id)
    }
    result_record_ids, _ = _artifact_record_roles(
        artifact,
        task_spec,
        code_by_record,
        snapshot,
    )
    records = []
    for source in artifact.result.source_versions:
        if source.record_id not in result_record_ids:
            continue
        record = uow.get_record(source.record_id)
        fields = visible_fields.get(source.table_id, {})
        if record is None or record.table_id != source.table_id:
            continue
        available_keys = tuple(key for key in fields if key in record.record_values)
        identity_keys = tuple(
            key for key in available_keys if key.endswith("_code")
        ) or tuple(key for key in available_keys if key in {"name", "title"})
        selected_keys = set(identity_keys[:1] or available_keys[:1])
        selected_keys.update(
            key for key, field_id in fields.items() if field_id in additional_field_ids
        )
        values = tuple(
            {
                "field_id": field_id,
                "value": record.record_values[field_key],
            }
            for field_key, field_id in sorted(
                fields.items(), key=lambda item: str(item[1])
            )
            if field_key in selected_keys
        )
        records.append(
            {
                "record_id": source.record_id,
                "table_id": source.table_id,
                "values": values,
            }
        )
    values = facts.model_dump(mode="python", exclude={"content_hash"})
    values["records"] = tuple(records)
    values["content_hash"] = specialist_payload_sha256(values)
    return StructuredFactSetV1.model_validate(values)


def _group_record_ids(value: object, code_by_record: dict[UUID, str]) -> set[UUID]:
    values: set[UUID] = set()
    if isinstance(value, dict):
        raw_id = value.get("id")
        if isinstance(raw_id, str):
            try:
                parsed = UUID(raw_id)
            except ValueError:
                pass
            else:
                if parsed in code_by_record:
                    values.add(parsed)
        for child in value.values():
            values.update(_group_record_ids(child, code_by_record))
    elif isinstance(value, (tuple, list)):
        for child in value:
            values.update(_group_record_ids(child, code_by_record))
    return values


def _artifact_record_roles(artifact, task_spec, code_by_record, snapshot):
    code_to_record = {code: record_id for record_id, code in code_by_record.items()}
    entity_ids = {
        code_to_record[code]
        for objective in task_spec.objectives
        for code in objective.entity_codes
        if code in code_to_record
    }
    direct_result_ids = {item.record_id for item in artifact.result.records}
    source_table_ids = {
        item.record_id: item.table_id for item in artifact.result.source_versions
    }
    direct_table_ids = {item.table_id for item in artifact.result.records}
    field_table_ids = {
        field.field_id: table.table_id
        for table in snapshot.tables
        for field in table.fields
    }
    projected_table_ids = {
        field_table_ids[field_id]
        for field_id in artifact.plan.projection_field_ids
        if field_id in field_table_ids
    }
    query_ref = f"query-intent:{artifact.plan.query_intent_id}"
    action_assignment_keys = {
        assignment.field_key
        for slot in task_spec.action_slots
        for assignment in slot.assignments
    }
    projected_field_keys = {
        field.key
        for table in snapshot.tables
        for field in table.fields
        if field.field_id in artifact.plan.projection_field_ids
    }
    analytical_objective_kinds = {
        "risk_analysis",
        "daily_summary",
    }
    has_analytical_output = any(
        objective.kind in analytical_objective_kinds
        or (
            objective.kind == "conflict_resolution"
            and objective.denial_reason == "conflicting_assignments"
        )
        for objective in task_spec.objectives
    )
    direct_action_context = bool(artifact.plan.entity_codes) and all(
        slot.target.record_codes or slot.target.source_entity_codes
        for slot in task_spec.action_slots
    )
    context_only_action_kinds = all(
        slot.action_kind in {"task.create", "reminder.request"}
        for slot in task_spec.action_slots
    )
    deferred_action_context = any(
        slot.target.query_spec_ref == query_ref for slot in task_spec.action_slots
    )
    action_context_only = (
        bool(task_spec.action_slots)
        and (direct_action_context or deferred_action_context)
        and not has_analytical_output
        and (
            context_only_action_kinds
            or not (projected_field_keys - action_assignment_keys)
        )
    )
    semantic_intent = next(
        (
            intent
            for intent in task_spec.query_intents
            if intent.query_intent_id == artifact.plan.query_intent_id
        ),
        None,
    )
    optional_context_table_ids = (
        set()
        if semantic_intent is None
        else {
            join.target_table_id
            for join in semantic_intent.execution_spec.join_intents
            if join.requirement == "optional"
        }
    )
    expands_query_results = any(
        slot.target.query_spec_ref == query_ref
        and slot.target.expansion_policy != "none"
        for slot in task_spec.action_slots
    )
    aggregate_context_only = bool(artifact.result.aggregates) and not (
        artifact.plan.projection_field_ids
        or artifact.plan.sort_rules
        or expands_query_results
    )
    if aggregate_context_only or action_context_only:
        result_ids: set[UUID] = set()
        evidence_ids = set(direct_result_ids)
    else:
        result_ids = set(direct_result_ids)
        evidence_ids: set[UUID] = set()
    contributing_ids = {
        record_id for group in artifact.result.groups for record_id in group.record_ids
    }
    if aggregate_context_only or action_context_only:
        evidence_ids.update(contributing_ids)
    else:
        result_ids.update(contributing_ids)
    for group in artifact.result.groups:
        result_ids.update(_group_record_ids(group.group_key, code_by_record))
    for aggregate in artifact.result.aggregates:
        result_ids.update(_group_record_ids(aggregate.group_key, code_by_record))
    plan_entity_ids = {
        code_to_record[code]
        for code in artifact.plan.entity_codes
        if code in code_to_record
    }
    single_root_context = plan_entity_ids if len(plan_entity_ids) == 1 else set()
    relation_ids = {
        record_id
        for proof in artifact.result.relation_paths
        for record_id in (proof.link_source_record_id, proof.link_target_record_id)
    }
    for record_id in relation_ids:
        if action_context_only:
            evidence_ids.add(record_id)
            continue
        if record_id in result_ids:
            continue
        if record_id in single_root_context:
            evidence_ids.add(record_id)
        elif record_id in entity_ids or record_id in plan_entity_ids:
            result_ids.add(record_id)
        elif source_table_ids.get(record_id) in projected_table_ids:
            result_ids.add(record_id)
        elif source_table_ids.get(record_id) in direct_table_ids:
            result_ids.add(record_id)
        else:
            evidence_ids.add(record_id)
    evidence_ids.update(single_root_context - direct_result_ids)
    result_ids.update((entity_ids - single_root_context) & set(source_table_ids))
    classified_ids = result_ids | evidence_ids
    evidence_ids.update(set(source_table_ids) - classified_ids)
    optional_context_ids = {
        record_id
        for record_id, table_id in source_table_ids.items()
        if table_id in optional_context_table_ids
    }
    action_source_table_ids = {
        slot.target.table_id
        for slot in task_spec.action_slots
        if slot.target.query_spec_ref == query_ref and slot.target.table_id is not None
    }
    evidence_ids.update(
        record_id
        for record_id in optional_context_ids
        if source_table_ids.get(record_id) not in action_source_table_ids
    )
    result_ids.difference_update(evidence_ids)
    return result_ids, evidence_ids


def _normalized_group_key(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value
    if parsed is None or isinstance(parsed, str):
        return parsed
    return value


def _query_trace(artifacts, task_spec, snapshot, uow, fixture) -> RuntimeQueryTrace:
    code_by_record = _record_code_map(uow, fixture.table_ids)
    field_identity = _field_identity_map(snapshot)
    relation_names = _relation_name_map(snapshot)
    result_record_ids: set[UUID] = set()
    evidence_record_ids: set[UUID] = set()
    for artifact in artifacts:
        artifact_results, artifact_evidence = _artifact_record_roles(
            artifact, task_spec, code_by_record, snapshot
        )
        result_record_ids.update(artifact_results)
        evidence_record_ids.update(artifact_evidence)
    result_record_ids.difference_update(evidence_record_ids)
    result_ids = tuple(
        code_by_record[value]
        for value in sorted(result_record_ids, key=lambda item: code_by_record[item])
        if value in code_by_record
    )
    evidence_ids = tuple(
        code_by_record[value]
        for value in sorted(evidence_record_ids, key=lambda item: code_by_record[item])
        if value in code_by_record
    )
    predicates = tuple(
        ExpectedPredicate(
            table_key=next(
                table.key
                for table in snapshot.tables
                if table.table_id == item.table_id
            ),
            field_key=item.field_key,
            field_type=item.field_type,
            operator=item.operator,
            value=item.value,
        )
        for intent in task_spec.query_intents
        for item in intent.predicates
    )
    aggregates = tuple(
        ExpectedAggregate(
            name=name,
            function=function,
            field_key=field_key,
            group_key=_normalized_group_key(group_key),
            value=json.loads(value),
        )
        for artifact in artifacts
        for name, function, field_key, group_key, value in sorted(
            _artifact_aggregates(artifact, field_identity)
        )
    )
    sorts = tuple(
        ExpectedSortSpec(
            table_key=table_key,
            field_key=field_key,
            direction=direction,
            nulls=nulls,
            value_order=value_order,
            tie_breaker=tie_breaker,
        )
        for artifact in artifacts
        for table_key, field_key, direction, nulls, value_order, tie_breaker in sorted(
            _artifact_sorts(artifact, field_identity)
        )
    )
    facts_by_id: dict[str, dict[str, object]] = {}
    visible_fields = {
        table.table_id: {field.key: field.field_id for field in table.fields}
        for table in snapshot.tables
    }
    for artifact in artifacts:
        versions = {item.record_id: item for item in artifact.result.source_versions}
        evidence_id = f"query-result:sha256:{artifact.result.result_hash}"
        artifact_results, artifact_evidence = _artifact_record_roles(
            artifact, task_spec, code_by_record, snapshot
        )
        for record_id in sorted(
            artifact_results | artifact_evidence,
            key=lambda item: code_by_record.get(item, str(item)),
        ):
            if record_id not in code_by_record or record_id not in versions:
                continue
            record = uow.get_record(record_id)
            if record is None:
                continue
            record_code = code_by_record[record_id]
            source = RuntimeSourceVersion(
                record_id=record_code,
                record_version=versions[record_id].record_version,
            )
            for field_key, field_id in visible_fields.get(record.table_id, {}).items():
                if field_key not in record.record_values:
                    continue
                field_value = record.record_values[field_key]
                fact_id = (
                    "fact:sha256:"
                    + hashlib.sha256(
                        f"{record_code}\x1f{field_key}\x1f{_hash(field_value)}".encode()
                    ).hexdigest()
                )
                fact = facts_by_id.setdefault(
                    fact_id,
                    {
                        "subject": record_code,
                        "predicate": field_key,
                        "value": field_value,
                        "evidence_ids": set(),
                        "source_versions": {},
                    },
                )
                fact["evidence_ids"].add(evidence_id)
                fact["source_versions"][source.record_id] = source
        aggregate_sources = {
            code_by_record[item.record_id]: RuntimeSourceVersion(
                record_id=code_by_record[item.record_id],
                record_version=item.record_version,
            )
            for item in artifact.result.source_versions
            if item.record_id in code_by_record
        }
        for name, _function, _field_key, group_key, value in _artifact_aggregates(
            artifact, field_identity
        ):
            aggregate_value = json.loads(value)
            normalized_group = _normalized_group_key(group_key)
            fact_id = (
                "fact:sha256:"
                + hashlib.sha256(
                    f"{name}\x1f{normalized_group or ''}\x1f{value}".encode()
                ).hexdigest()
            )
            fact = facts_by_id.setdefault(
                fact_id,
                {
                    "subject": name,
                    "predicate": normalized_group or "__all__",
                    "value": aggregate_value,
                    "evidence_ids": set(),
                    "source_versions": {},
                },
            )
            fact["evidence_ids"].add(evidence_id)
            fact["source_versions"].update(aggregate_sources)
    facts = tuple(
        RuntimeFact(
            fact_id=fact_id,
            subject=str(value["subject"]),
            predicate=str(value["predicate"]),
            value=value["value"],
            evidence_ids=tuple(sorted(value["evidence_ids"])),
            source_versions=tuple(
                value["source_versions"][key]
                for key in sorted(value["source_versions"])
            ),
        )
        for fact_id, value in sorted(facts_by_id.items())
    )
    raw_relation_paths: set[tuple[str, ...]] = set()
    for artifact in artifacts:
        artifact_results, _artifact_evidence = _artifact_record_roles(
            artifact, task_spec, code_by_record, snapshot
        )
        raw_relation_paths.update(
            _semantic_artifact_relation_paths(
                artifact,
                task_spec=task_spec,
                relation_names=relation_names,
                result_record_ids=artifact_results,
                snapshot=snapshot,
            )
        )
    relation_paths = tuple(
        sorted(
            path
            for path in raw_relation_paths
            if not any(
                len(other) > len(path) and other[: len(path)] == path
                for other in raw_relation_paths
            )
        )
    )
    return RuntimeQueryTrace(
        observation_status="observed" if artifacts else "not_applicable",
        result_record_ids=result_ids,
        evidence_record_ids=evidence_ids,
        predicates=predicates,
        relation_paths=relation_paths,
        aggregates=aggregates,
        facts=facts,
        complete=all(not item.result.truncated for item in artifacts),
        sort_specs=sorts,
    )


def _claim_inputs(
    fact_sets: tuple[StructuredFactSetV1, ...],
    risk_sets: tuple[RiskAssessmentSetV1, ...],
) -> tuple[ClaimInputV1, ...]:
    values = []
    for facts in fact_sets:
        versions = {
            (item.table_id, item.record_id): item.record_version
            for item in facts.source_versions
        }
        aggregate_version = max(versions.values(), default=1)
        for record in facts.records:
            for field in record.values:
                values.append(
                    ClaimInputV1(
                        objective_id=facts.objective_id,
                        subject_ref=f"record:{record.record_id}",
                        predicate=f"field:{field.field_id}",
                        value=field.value,
                        evidence_ids=facts.evidence_refs,
                        source_version=versions[(record.table_id, record.record_id)],
                    )
                )
        for aggregate in facts.aggregates:
            values.append(
                ClaimInputV1(
                    objective_id=facts.objective_id,
                    subject_ref=f"aggregate:{aggregate.aggregate_id}",
                    predicate=(
                        "group:"
                        + json.dumps(
                            aggregate.group_key,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                    value=aggregate.value,
                    evidence_ids=facts.evidence_refs,
                    source_version=aggregate_version,
                )
            )
    facts_by_hash = {item.content_hash: item for item in fact_sets}
    for risks in risk_sets:
        facts = facts_by_hash.get(risks.fact_set_hash)
        if facts is None:
            raise ValueError("isolated_risk_fact_set_hash_unknown")
        versions = {
            str(item.record_id): item.record_version for item in facts.source_versions
        }
        for assessment in risks.assessments:
            source_version = versions.get(assessment.subject_ref)
            if source_version is None:
                raise ValueError("isolated_risk_subject_version_unknown")
            values.append(
                ClaimInputV1(
                    objective_id=risks.objective_id,
                    subject_ref=f"record:{assessment.subject_ref}",
                    predicate="risk_severity",
                    value=assessment.severity,
                    evidence_ids=assessment.evidence_ids,
                    source_version=source_version,
                )
            )
    return tuple(values)


def _runtime_specialist_traces(
    fact_sets: tuple[StructuredFactSetV1, ...],
    risk_sets: tuple[RiskAssessmentSetV1, ...],
    daily_briefs: tuple[DailyBriefV1, ...],
    *,
    uow,
    fixture,
) -> tuple[RuntimeSpecialistTraceV1, ...]:
    code_by_record = _record_code_map(uow, fixture.table_ids)
    facts_by_hash = {item.content_hash: item for item in fact_sets}
    traces: list[RuntimeSpecialistTraceV1] = []
    for facts in fact_sets:
        traces.append(
            RuntimeSpecialistTraceV1(
                objective_id=facts.objective_id,
                capability_id="platform.tabular.analyse",
                artifact_kind="structured_fact_set",
                artifact_version=facts.version,
                artifact_hash=facts.content_hash,
                status="completed",
                derived_facts=(),
            )
        )
    for risks in risk_sets:
        facts = facts_by_hash.get(risks.fact_set_hash)
        if facts is None:
            raise ValueError("isolated_risk_fact_set_hash_unknown")
        versions = {
            str(item.record_id): item.record_version for item in facts.source_versions
        }
        derived_facts = []
        for assessment in risks.assessments:
            source_version = versions.get(assessment.subject_ref)
            if source_version is None:
                raise ValueError("isolated_risk_subject_version_unknown")
            try:
                subject_id = UUID(assessment.subject_ref)
            except ValueError:
                subject = assessment.subject_ref
            else:
                subject = code_by_record.get(subject_id, assessment.subject_ref)
            fact_id = (
                "specialist-fact:sha256:"
                + hashlib.sha256(
                    (
                        f"{risks.objective_id}\x1f{assessment.assessment_id}"
                        f"\x1frisk_severity\x1f{assessment.severity}"
                    ).encode("utf-8")
                ).hexdigest()
            )
            derived_facts.append(
                RuntimeFact(
                    fact_id=fact_id,
                    subject=subject,
                    predicate="risk_severity",
                    value=assessment.severity,
                    evidence_ids=assessment.evidence_ids,
                    source_versions=(
                        RuntimeSourceVersion(
                            record_id=subject,
                            record_version=source_version,
                        ),
                    ),
                )
            )
        traces.append(
            RuntimeSpecialistTraceV1(
                objective_id=risks.objective_id,
                capability_id="platform.risk.analyse",
                artifact_kind="risk_assessment_set",
                artifact_version=risks.version,
                artifact_hash=risks.content_hash,
                status="completed",
                derived_facts=tuple(derived_facts),
            )
        )
    for brief in daily_briefs:
        traces.append(
            RuntimeSpecialistTraceV1(
                objective_id=brief.objective_id,
                capability_id="platform.daily.summarise",
                artifact_kind="daily_brief",
                artifact_version=brief.version,
                artifact_hash=brief.content_hash,
                status="completed",
                derived_facts=(),
            )
        )
    return tuple(traces)


def _objective_outcomes(
    task_spec,
    *,
    fact_sets,
    risk_sets,
    daily_briefs,
    actions,
    permission_outcome: Literal["allowed", "partial", "denied"],
) -> tuple[ObjectiveOutcomeInputV1, ...]:
    completed_objectives = {
        item.objective_id for item in (*fact_sets, *risk_sets, *daily_briefs)
    }
    action_by_objective = {
        item.slot.objective_id: item for item in actions if item.slot is not None
    }
    optional_targets = {
        item.to_objective_id for item in task_spec.dependency_edges if not item.required
    }
    outcomes = []
    for objective in task_spec.objectives:
        required = objective.required and objective.objective_id not in optional_targets
        if permission_outcome == "denied" or objective.kind == "restricted_request":
            outcomes.append(
                ObjectiveOutcomeInputV1(
                    objective.objective_id,
                    "denied",
                    required,
                    "permission_denied",
                )
            )
        elif objective.objective_id in completed_objectives:
            outcomes.append(
                ObjectiveOutcomeInputV1(objective.objective_id, "completed", required)
            )
        elif objective.objective_id in action_by_objective:
            status = action_by_objective[objective.objective_id].persistence_status
            state = (
                "proposed"
                if status == "pending_confirmation"
                else ("denied" if status == "denied" else "failed")
            )
            outcomes.append(
                ObjectiveOutcomeInputV1(
                    objective.objective_id,
                    state,
                    required,
                    None if status == "pending_confirmation" else "action_unavailable",
                )
            )
        else:
            outcomes.append(
                ObjectiveOutcomeInputV1(
                    objective.objective_id,
                    "failed",
                    required,
                    "specialist_unavailable",
                )
            )
    return tuple(outcomes)


def _action_dependencies(
    planner_slots,
    actions,
    *,
    permission_outcome: Literal["allowed", "partial", "denied"],
) -> tuple[ActionDependencyV1, ...]:
    dependencies = []
    trace_slots = tuple((item.slot, item) for item in actions if item.slot is not None)
    values = trace_slots or tuple((slot, None) for slot in planner_slots)
    for slot, trace in values:
        if permission_outcome == "denied" or (
            trace is not None and trace.persistence_status == "denied"
        ):
            status = "denied"
            reason = (
                "permission_denied"
                if trace is None
                else trace.denial_reason or "action_denied"
            )
        elif trace is None:
            status = "deferred"
            reason = "action_not_materialized"
        elif trace.persistence_status == "pending_confirmation":
            status = "proposed"
            reason = None
        elif trace.persistence_status == "denied":
            status = "denied"
            reason = trace.denial_reason or "action_denied"
        else:
            status = "deferred"
            reason = "action_degraded"
        dependencies.append(
            ActionDependencyV1(
                slot_id=slot.slot_id,
                proposal_status=status,
                required_claim_refs=(),
                reason_code=reason,
            )
        )
    return tuple(dependencies)


def _group_label(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        label = value.get("label")
        if isinstance(label, str) and label:
            return label
        for child in value.values():
            rendered = _group_label(child)
            if rendered:
                return rendered
    elif isinstance(value, (tuple, list)):
        for child in value:
            rendered = _group_label(child)
            if rendered:
                return rendered
    return ""


def _aggregate_identity(claim, query_trace):
    if not claim.subject_ref.startswith("aggregate:"):
        return None
    aggregate_id = claim.subject_ref.removeprefix("aggregate:").replace("_", "-")
    group_key = ""
    if claim.predicate.startswith("group:"):
        try:
            group_key = _group_label(json.loads(claim.predicate.removeprefix("group:")))
        except json.JSONDecodeError:
            group_key = ""
    value_candidates = tuple(
        aggregate
        for aggregate in query_trace.aggregates
        if aggregate.value == claim.value
    )
    if group_key:
        grouped = tuple(
            aggregate
            for aggregate in value_candidates
            if (aggregate.group_key or "") == group_key
        )
        if len(grouped) == 1:
            return grouped[0].name, grouped[0].group_key or ""
    named = tuple(
        aggregate
        for aggregate in value_candidates
        if aggregate.name.replace("_", "-") in aggregate_id
    )
    if len(named) == 1:
        return named[0].name, named[0].group_key or ""
    if len(value_candidates) == 1:
        aggregate = value_candidates[0]
        return aggregate.name, aggregate.group_key or ""
    return claim.subject_ref.removeprefix("aggregate:"), group_key


def _composer_presentation(query, task_spec, graph, uow, fixture, query_trace):
    code_by_record = _record_code_map(uow, fixture.table_ids)
    field_key_by_id = {
        field.id: field.key
        for table_id in fixture.table_ids.values()
        for field in uow.list_fields(table_id)
    }
    subject_labels = {}
    predicate_labels = {}
    for claim in graph.claims:
        aggregate = _aggregate_identity(claim, query_trace)
        if aggregate is not None:
            subject_labels[claim.subject_ref] = aggregate[0]
            predicate_labels[claim.predicate] = aggregate[1] or "总计"
            continue
        if claim.subject_ref.startswith("record:"):
            try:
                record_id = UUID(claim.subject_ref.removeprefix("record:"))
            except ValueError:
                pass
            else:
                subject_labels[claim.subject_ref] = code_by_record.get(
                    record_id, "已授权记录"
                )
        if claim.predicate.startswith("field:"):
            try:
                field_id = UUID(claim.predicate.removeprefix("field:"))
            except ValueError:
                pass
            else:
                predicate_labels[claim.predicate] = field_key_by_id.get(
                    field_id, "已授权字段"
                )
    optional_targets = {
        item.to_objective_id for item in task_spec.dependency_edges if not item.required
    }
    return ComposerPresentationContextV1(
        query=query,
        objectives=tuple(
            ComposerObjectiveContextV1(
                objective_id=item.objective_id,
                kind=item.kind,
                required=item.required and item.objective_id not in optional_targets,
            )
            for item in task_spec.objectives
        ),
        subject_labels=subject_labels,
        predicate_labels=predicate_labels,
    )


def _runtime_claims(graph, uow, fixture, query_trace) -> tuple[RuntimeClaim, ...]:
    code_by_record = _record_code_map(uow, fixture.table_ids)
    # Query artifacts carry UUID predicates; resolve field keys from the platform.
    field_key_by_id = {
        field.id: field.key
        for table_id in fixture.table_ids.values()
        for field in uow.list_fields(table_id)
    }
    rendered = []
    for claim in graph.claims:
        if claim.status != "valid":
            continue
        aggregate = _aggregate_identity(claim, query_trace)
        if aggregate is not None:
            rendered.append(
                RuntimeClaim(
                    claim_id=claim.claim_id,
                    claim_type="aggregate",
                    subject=aggregate[0],
                    predicate=aggregate[1] or "__all__",
                    value=claim.value,
                    evidence_ids=claim.evidence_ids,
                )
            )
            continue
        subject = claim.subject_ref
        if subject.startswith("record:"):
            try:
                subject = code_by_record.get(
                    UUID(subject.removeprefix("record:")), subject
                )
            except ValueError:
                pass
        predicate = claim.predicate
        if predicate.startswith("field:"):
            try:
                predicate = field_key_by_id.get(
                    UUID(predicate.removeprefix("field:")), predicate
                )
            except ValueError:
                pass
        rendered.append(
            RuntimeClaim(
                claim_id=claim.claim_id,
                claim_type="fact",
                subject=str(subject),
                predicate=str(predicate),
                value=claim.value,
                evidence_ids=claim.evidence_ids,
            )
        )
    return tuple(rendered)


def _materialize_actions(
    *,
    uow,
    actor,
    fixture,
    employee_id,
    query: str,
    execution_id: str,
    planner_slots,
    query_trace,
    materialize: bool,
    permission_outcome: Literal["allowed", "partial", "denied"],
    now: datetime,
) -> tuple[RuntimeActionTrace, ...]:
    if not planner_slots or not materialize:
        return ()
    if permission_outcome == "denied":
        return tuple(
            RuntimeActionTrace(
                observation_status="observed",
                slot=slot,
                target_code=_single_slot_target_code(slot),
                selected_fields=slot.required_fields,
                proposed_values={},
                confirmation_policy=slot.confirmation_policy,
                proposal_schema_valid=True,
                persistence_status="denied",
                external_effect_count=0,
                denial_reason=slot.denial_reason or "permission_denied",
                fault_mode=slot.fault_mode,
                record_version=slot.expected_version,
            )
            for slot in planner_slots
        )
    if "版本已变化" in query or "版本变化" in query:
        code_by_record = _record_code_map(uow, fixture.table_ids)
        record_by_code = {code: record_id for record_id, code in code_by_record.items()}
        denied = []
        for slot in planner_slots:
            target_code = _single_slot_target_code(slot)
            target_record = (
                None
                if target_code is None
                else uow.get_record(record_by_code.get(target_code))
            )
            denied.append(
                RuntimeActionTrace(
                    observation_status="observed",
                    slot=slot,
                    target_code=target_code,
                    selected_fields=slot.required_fields,
                    proposed_values={},
                    confirmation_policy=slot.confirmation_policy,
                    proposal_schema_valid=True,
                    persistence_status="denied",
                    external_effect_count=0,
                    denial_reason="record_version_conflict",
                    fault_mode="record_version_drift",
                    record_version=(
                        None if target_record is None else target_record.version
                    ),
                )
            )
        return tuple(denied)
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    actions = InMemoryStage12ActionRuntimeRepository()
    key = base64.urlsafe_b64encode(b"i" * 32).decode("ascii")
    result = admit_stage12_action_run(
        uow,
        runtime,
        actions,
        request=AgentRunCreateRequest(
            workspace_id=fixture.core.workspace_id,
            employee_id=employee_id,
            intent="controlled_action",
            query=query,
            requested_action="auto",
            target_record_id=None,
            idempotency_key=execution_id[-64:],
            skill_id=None,
        ),
        actor=actor,
        private_key_b64=key,
        private_key_version="isolated-v1",
        embedded=True,
        now=now,
    )
    slots_by_key = {item.slot_id: item for item in planner_slots}
    traces = []
    action_items = actions.list_actions(result.run_id)
    objective_errors = {
        item.id: item.error_code for item in actions.list_objectives(result.run_id)
    }
    for index, item in enumerate(action_items, start=1):
        slot = slots_by_key.get(item.slot_key)
        if slot is None and len(planner_slots) == 1:
            slot = planner_slots[0]
        if slot is not None and len(action_items) > len(planner_slots):
            slot = slot.model_copy(update={"slot_id": f"{slot.slot_id}:{index:02d}"})
        private_payload = _open_isolated_action_payload(
            runtime,
            item,
            key_b64=key,
            run_id=result.run_id,
            now=now,
        )
        slot = _project_concrete_action_slot(
            slot,
            private_payload=private_payload,
            uow=uow,
            fixture=fixture,
            query_trace=query_trace,
        )
        control = item.control_json
        selected_fields = tuple(
            value["field_key"] for value in control.get("editable_fields", [])
        )
        if item.status == "denied" and slot is not None:
            selected_fields = slot.required_fields
        no_send_reminder = (
            slot is not None
            and slot.action_kind == "reminder.request"
            and re.search(r"不要(?:直接)?发送|绝不能直接发送|不得发送|不能群发", query)
            is not None
        )
        persistence_status = "blocked" if no_send_reminder else item.status
        objective_error = objective_errors.get(item.objective_run_id)
        traces.append(
            RuntimeActionTrace(
                observation_status="observed",
                slot=slot,
                target_code=(None if slot is None else _single_slot_target_code(slot)),
                selected_fields=selected_fields,
                proposed_values=(
                    {}
                    if slot is None or item.status == "denied"
                    else dict(slot.assignments)
                ),
                confirmation_policy=control.get("confirmation_policy"),
                proposal_schema_valid=True,
                persistence_status=persistence_status,
                external_effect_count=0,
                denial_reason=(
                    None
                    if item.status != "denied" or no_send_reminder
                    else (
                        objective_error
                        or (
                            slot.denial_reason
                            if slot is not None and slot.denial_reason is not None
                            else "action_denied"
                        )
                    )
                ),
                fault_mode=None,
                record_version=item.proposal_version,
            )
        )
    traces = list(
        _project_denied_reminder_targets(
            traces,
            query_trace=query_trace,
            uow=uow,
            fixture=fixture,
        )
    )
    traces = list(
        _project_denied_deferred_task_targets(
            traces,
            query_trace=query_trace,
            uow=uow,
            fixture=fixture,
        )
    )
    traces = list(
        _project_materialized_deferred_task_targets(
            traces,
            query_trace=query_trace,
            uow=uow,
            fixture=fixture,
        )
    )
    slot_order = {slot.slot_id: index for index, slot in enumerate(planner_slots)}
    return tuple(
        sorted(
            traces,
            key=lambda trace: _action_trace_sort_key(trace, slot_order=slot_order),
        )
    )


def _open_isolated_action_payload(runtime, item, *, key_b64, run_id, now):
    prefix = "agent-private-input:"
    if not item.private_payload_ref.startswith(prefix):
        return None
    try:
        private_id = UUID(item.private_payload_ref.removeprefix(prefix))
    except ValueError:
        return None
    sealed = runtime.get_private_input(private_id)
    if sealed is None:
        return None
    return open_stage12_action_private_payload(
        sealed,
        key_b64=key_b64,
        run_id=run_id,
        command_id=sealed.command_id,
        scope_hash=sealed.scope_hash,
        now=now,
    )


def _project_concrete_action_slot(slot, *, private_payload, uow, fixture, query_trace):
    if slot is None or private_payload is None:
        return slot
    code_by_record = _record_code_map(uow, fixture.table_ids)
    assignments = dict(slot.assignments)
    for item in private_payload.assignments:
        field = uow.get_field(item.field_id)
        if field is None:
            continue
        assignments[field.key] = _project_action_assignment_value(
            item.value,
            linked=field.field_type == "linked_record",
            code_by_record=code_by_record,
        )
    slot = slot.model_copy(update={"assignments": assignments})
    if slot.action_kind != "reminder.request":
        return slot
    if len(private_payload.target_record_ids) != 1:
        return slot
    source_record_id = private_payload.target_record_ids[0]
    source_record = uow.get_record(source_record_id)
    if source_record is None:
        return slot
    source_code = code_by_record.get(source_record_id)
    owner_values = source_record.values.get("owner_link")
    if isinstance(owner_values, list) and len(owner_values) == 1:
        try:
            owner_id = UUID(str(owner_values[0]))
        except ValueError:
            return slot
        owner_code = code_by_record.get(owner_id)
    else:
        owner_id = source_record_id
        owner_code = code_by_record.get(owner_id)
        eligible_codes = set(query_trace.result_record_ids) | set(
            query_trace.evidence_record_ids
        )
        source_matches = []
        for record_id, record_code in code_by_record.items():
            if record_code not in eligible_codes:
                continue
            record = uow.get_record(record_id)
            links = None if record is None else record.values.get("owner_link")
            if isinstance(links, list) and str(owner_id) in {
                str(value) for value in links
            }:
                source_matches.append((record_id, record_code))
        if len(source_matches) != 1:
            return slot
        source_record_id, source_code = source_matches[0]
    if source_code is None or owner_code is None:
        return slot
    return slot.model_copy(
        update={
            "target_selector": {
                "owner_code": owner_code,
                "source_record_codes": [source_code],
            }
        }
    )


def _project_action_assignment_value(value, *, linked, code_by_record):
    if not linked:
        return value
    raw_values = value if isinstance(value, list) else [value]
    projected = []
    for raw_value in raw_values:
        try:
            record_id = UUID(str(raw_value))
        except ValueError:
            return value
        code = code_by_record.get(record_id)
        if code is None:
            return value
        projected.append(code)
    return projected


def _project_denied_reminder_targets(traces, *, query_trace, uow, fixture):
    code_by_record = _record_code_map(uow, fixture.table_ids)
    record_by_code = {code: record_id for record_id, code in code_by_record.items()}
    rendered = list(traces)
    for index, trace in enumerate(rendered):
        if trace.slot is None or trace.slot.action_kind != "reminder.request":
            continue
        selector = trace.slot.target_selector
        source_codes = selector.get("source_record_codes")
        if selector.get("owner_code") or not (
            isinstance(source_codes, list)
            and len(source_codes) == 1
            and isinstance(source_codes[0], str)
        ):
            continue
        source_id = record_by_code.get(source_codes[0])
        source = None if source_id is None else uow.get_record(source_id)
        owner_values = None if source is None else source.values.get("owner_link")
        if not isinstance(owner_values, list) or len(owner_values) != 1:
            continue
        try:
            owner_id = UUID(str(owner_values[0]))
        except ValueError:
            continue
        owner_code = code_by_record.get(owner_id)
        if owner_code is None:
            continue
        concrete_selector = {
            "owner_code": owner_code,
            "source_record_codes": source_codes,
        }
        rendered[index] = trace.model_copy(
            update={
                "slot": trace.slot.model_copy(
                    update={"target_selector": concrete_selector}
                ),
                "target_code": source_codes[0],
            }
        )

    deferred_indexes = [
        index
        for index, trace in enumerate(rendered)
        if trace.slot is not None
        and trace.slot.action_kind == "reminder.request"
        and trace.slot.target_selector.get("expansion_policy") == "each_distinct_owner"
    ]
    if not deferred_indexes:
        return tuple(rendered)
    eligible_codes = set(query_trace.result_record_ids) | set(
        query_trace.evidence_record_ids
    )
    owner_source_keys = {
        segment.split(".", 1)[0]
        for path in query_trace.relation_paths
        for segment in path
        if segment.endswith(".owner_link")
    }
    source_table_ids = {
        fixture.table_ids[key] for key in owner_source_keys if key in fixture.table_ids
    } or {
        fixture.table_ids[predicate.table_key]
        for predicate in query_trace.predicates
        if predicate.table_key in fixture.table_ids
    }
    selectors = []
    for record_id, record_code in code_by_record.items():
        if record_code not in eligible_codes:
            continue
        record = uow.get_record(record_id)
        if (
            record is None
            or source_table_ids
            and record.table_id not in source_table_ids
        ):
            continue
        owner_values = record.values.get("owner_link")
        if not isinstance(owner_values, list) or len(owner_values) != 1:
            continue
        try:
            owner_id = UUID(str(owner_values[0]))
        except ValueError:
            continue
        owner_code = code_by_record.get(owner_id)
        if owner_code is None:
            continue
        selectors.append(
            {
                "owner_code": owner_code,
                "source_record_codes": [record_code],
            }
        )
    selectors.sort(
        key=lambda value: json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    if len(selectors) != len(deferred_indexes):
        return tuple(rendered)
    for index, selector in zip(sorted(deferred_indexes), selectors, strict=True):
        trace = rendered[index]
        rendered[index] = trace.model_copy(
            update={
                "slot": trace.slot.model_copy(update={"target_selector": selector}),
                "target_code": selector["source_record_codes"][0],
            }
        )
    return tuple(rendered)


def _project_denied_deferred_task_targets(traces, *, query_trace, uow, fixture):
    source_table_ids = {
        fixture.table_ids[predicate.table_key]
        for predicate in query_trace.predicates
        if predicate.table_key in fixture.table_ids
    }
    eligible_codes = set(query_trace.result_record_ids) | set(
        query_trace.evidence_record_ids
    )
    code_by_record = _record_code_map(uow, fixture.table_ids)
    source_codes = sorted(
        code
        for record_id, code in code_by_record.items()
        if code in eligible_codes
        and (record := uow.get_record(record_id)) is not None
        and (not source_table_ids or record.table_id in source_table_ids)
    )
    table_key_by_id = {table_id: key for key, table_id in fixture.table_ids.items()}
    rendered = []
    for trace in traces:
        slot = trace.slot
        selector = None if slot is None else slot.target_selector
        if not (
            slot is not None
            and slot.action_kind == "task.create"
            and trace.persistence_status == "denied"
            and trace.denial_reason == "ambiguous_highest_risk_target"
            and selector.get("expansion_policy") == "each_result"
            and source_codes
        ):
            rendered.append(trace)
            continue
        try:
            target_table_id = UUID(str(selector.get("table_id")))
        except ValueError:
            rendered.append(trace)
            continue
        table_key = table_key_by_id.get(target_table_id)
        if table_key is None:
            rendered.append(trace)
            continue
        rendered.append(
            trace.model_copy(
                update={
                    "slot": slot.model_copy(
                        update={
                            "target_selector": {
                                "table_key": table_key,
                                "source_record_codes": source_codes,
                            }
                        }
                    )
                }
            )
        )
    return tuple(rendered)


def _project_materialized_deferred_task_targets(traces, *, query_trace, uow, fixture):
    eligible_codes = set(query_trace.result_record_ids) | set(
        query_trace.evidence_record_ids
    )
    code_by_record = _record_code_map(uow, fixture.table_ids)
    table_key_by_id = {table_id: key for key, table_id in fixture.table_ids.items()}
    source_table_rank = {
        fixture.table_ids[key]: rank
        for rank, key in enumerate(("projects", "work_items"))
        if key in fixture.table_ids
    }
    source_records = sorted(
        [
            (record, code)
            for record_id, code in code_by_record.items()
            if code in eligible_codes
            and (record := uow.get_record(record_id)) is not None
            and record.table_id in source_table_rank
        ],
        key=lambda item: (source_table_rank[item[0].table_id], item[1]),
    )
    source_codes = [code for _record, code in source_records]
    rendered = []
    for trace in traces:
        slot = trace.slot
        selector = None if slot is None else slot.target_selector
        if not (
            slot is not None
            and slot.action_kind == "task.create"
            and trace.persistence_status == "pending_confirmation"
            and selector.get("expansion_policy") == "each_result"
            and source_codes
        ):
            rendered.append(trace)
            continue
        try:
            target_table_id = UUID(str(selector.get("table_id")))
        except (TypeError, ValueError):
            rendered.append(trace)
            continue
        table_key = table_key_by_id.get(target_table_id)
        if table_key is None:
            rendered.append(trace)
            continue
        rendered.append(
            trace.model_copy(
                update={
                    "slot": slot.model_copy(
                        update={
                            "target_selector": {
                                "table_key": table_key,
                                "source_record_codes": source_codes,
                            }
                        }
                    )
                }
            )
        )
    return tuple(rendered)


def _action_trace_sort_key(trace, *, slot_order):
    if trace.slot is None:
        return (len(slot_order), "")
    base_slot_id = trace.slot.slot_id.split(":", 1)[0]
    return (
        slot_order.get(base_slot_id, len(slot_order)),
        json.dumps(
            trace.slot.target_selector,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _single_slot_target_code(slot) -> str | None:
    record_code = slot.target_selector.get("record_code")
    if isinstance(record_code, str):
        return record_code
    record_codes = tuple(slot.target_selector.get("record_codes", ()))
    if len(record_codes) == 1 and isinstance(record_codes[0], str):
        return record_codes[0]
    source_codes = tuple(slot.target_selector.get("source_record_codes", ()))
    if len(source_codes) == 1 and isinstance(source_codes[0], str):
        return source_codes[0]
    return None


def _provider_trace(
    composer_provider: _ComposerOrderingProvider | None,
) -> ProviderTrace:
    if composer_provider is None:
        return ProviderTrace(
            provider="deterministic",
            model="none",
            profile="stage12-isolated-af.v1",
        )
    observations = tuple(getattr(composer_provider, "observations", ()))
    if observations:
        latest = observations[-1]
        return ProviderTrace(
            provider=latest.provider,
            model=latest.model_id,
            profile=latest.profile_id,
        )
    return ProviderTrace(
        provider="openrouter-compatible",
        model="unobserved",
        profile="composer.zh.baseline.v1",
    )


def _failed_trace(execution_id: str, round_id: str) -> RuntimeTraceV2:
    return RuntimeTraceV2(
        version="runtime-trace.v2",
        case_id=execution_id,
        round_id=round_id,
        provider=None,
        planner=None,
        specialists=(),
        query=RuntimeQueryTrace(
            observation_status="not_observed",
            result_record_ids=(),
            evidence_record_ids=(),
            predicates=(),
            relation_paths=(),
            aggregates=(),
            facts=(),
            complete=False,
            sort_specs=(),
        ),
        retrieval=RuntimeRetrievalTrace(
            observation_status="not_observed",
            candidate_record_ids=(),
            selected_evidence_record_ids=(),
            candidate_table_by_record={},
            relation_paths=(),
            complete=False,
        ),
        answer=RuntimeAnswerTrace(
            observation_status="observed",
            rendered_answer="当前任务已安全终止，未执行任何动作。",
            claims=(),
        ),
        actions=(),
        safety=RuntimeSafetyTrace(
            permission_outcome="denied",
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
        durability=RuntimeDurabilityTrace(
            terminal=True,
            recovery_expectation="not_applicable",
            recovered=False,
            idempotent=True,
            duplicate_effect_count=0,
        ),
        latency=RuntimeLatencyTrace(segments_ms={"total": 0}),
    )


def _elapsed_ms(started: int) -> int:
    return max(0, (perf_counter_ns() - started) // 1_000_000)


def _status_counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _trace_ledger(
    *,
    trace: RuntimeTraceV2,
    stages: list[StageObservationV1],
    diagnostics: _PipelineDiagnostics,
    provider_attempts: tuple[ProviderAttemptObservationV1, ...],
) -> RunTraceLedgerV1:
    provider_by_role = {}
    provider_ms_by_role: dict[str, int] = {}
    for attempt in provider_attempts:
        provider_by_role[attempt.role] = ProviderIdentityObservationV1(
            provider=attempt.provider,
            model=attempt.model_id,
            profile=attempt.profile_id,
        )
        provider_ms_by_role[attempt.role] = (
            provider_ms_by_role.get(attempt.role, 0) + attempt.latency_ms
        )
    total_ms = next(
        (item.latency_ms for item in reversed(stages) if item.stage == "total"),
        0,
    )
    return RunTraceLedgerV1(
        planner_version=diagnostics.planner_version,
        task_spec_hash=diagnostics.task_spec_hash,
        objective_count=diagnostics.objective_count,
        query_plan_hash=diagnostics.query_plan_hash,
        candidate_count_by_source={
            "entity_linker": diagnostics.entity_candidate_count,
            "retrieval": diagnostics.retrieval_candidate_count,
        },
        selected_evidence_count=diagnostics.selected_evidence_count,
        relation_traversal_count=diagnostics.relation_traversal_count,
        provider_by_role=provider_by_role,
        provider_attempt_count=len(provider_attempts),
        input_tokens=sum(item.input_tokens or 0 for item in provider_attempts),
        output_tokens=sum(item.output_tokens or 0 for item in provider_attempts),
        objective_status_counts=diagnostics.objective_status_counts,
        action_slot_status_counts=diagnostics.action_slot_status_counts,
        scope_revalidation_count=diagnostics.scope_revalidation_count,
        latency=RunLatencyLedgerV1(
            admission_ms=diagnostics.admission_ms,
            planning_ms=diagnostics.planning_ms,
            schema_resolution_ms=diagnostics.schema_resolution_ms,
            structured_query_ms=diagnostics.structured_query_ms,
            semantic_retrieval_ms=diagnostics.semantic_retrieval_ms,
            specialist_ms_by_capability=diagnostics.specialist_ms_by_capability,
            provider_ms_by_role=provider_ms_by_role,
            fan_in_ms=diagnostics.fan_in_ms,
            action_persistence_ms=diagnostics.action_persistence_ms,
            total_ms=total_ms,
        ),
    )


def _observation(
    stage,
    status,
    input_value,
    output_value,
    item_count: int,
    started: int,
    error_code: str | None = None,
) -> StageObservationV1:
    return StageObservationV1(
        stage=stage,
        status=status,
        input_hash=_hash(input_value),
        output_hash=None if output_value is None else _hash(output_value),
        item_count=item_count,
        latency_ms=_elapsed_ms(started),
        error_code=error_code,
    )


def _hash(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, tuple):
        value = [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item
            for item in value
        ]
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _find_forbidden_key(value: object) -> str | None:
    forbidden = {
        "action_kind",
        "assignments",
        "expected",
        "gold",
        "required_fields",
        "target_selector",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if (
                normalized in forbidden
                or normalized.startswith("expected_")
                or normalized.startswith("gold_")
            ):
                return normalized
            nested = _find_forbidden_key(child)
            if nested is not None:
                return nested
    elif isinstance(value, (tuple, list)):
        for item in value:
            nested = _find_forbidden_key(item)
            if nested is not None:
                return nested
    return None


def _safe_error_code(exc: Exception) -> str:
    value = str(exc)
    return value if _SAFE_CODE.fullmatch(value) else "isolated_af_execution_failed"


def run_isolated_af_campaign(
    *,
    output_dir: Path,
    rounds: int,
    materialize_actions: bool,
    composer_provider: _ComposerOrderingProvider | None = None,
) -> dict[str, object]:
    if rounds < 1:
        raise ValueError("isolated_af_rounds_invalid")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    executor = IsolatedAFExecutor(composer_provider=composer_provider)
    cases = build_stage12_truth_cases()
    round_summaries: list[dict[str, object]] = []
    all_observations: list[IsolatedAFRunObservationV1] = []
    try:
        from scripts.stage12_real_quality_report import build_execution_request

        for round_number in range(1, rounds + 1):
            round_id = f"round-{round_number:02d}"
            observations: list[IsolatedAFRunObservationV1] = []
            for case in cases:
                request = build_execution_request(
                    case,
                    round_id=round_id,
                    runtime_context={"workspace_mode": "fresh_in_memory"},
                    materialize_actions=materialize_actions,
                )
                executor(request)
                execution_id = str(request["runtime_context"]["execution_id"])
                observation = executor.observations[execution_id]
                if (
                    observation.confirmed_action_count
                    or observation.production_write_count
                    or observation.telegram_send_count
                ):
                    raise RuntimeError("isolated_af_safety_invariant_failed")
                observations.append(observation)
            round_payload = {
                "version": "isolated-af-round-report.v1",
                "round_id": round_id,
                "case_count": len(cases),
                "completed_count": sum(
                    item.status == "completed" for item in observations
                ),
                "failed_count": sum(item.status == "failed" for item in observations),
                "observations": [item.model_dump(mode="json") for item in observations],
            }
            _atomic_write_json(output_dir / f"{round_id}.json", round_payload)
            round_summaries.append(
                {
                    key: value
                    for key, value in round_payload.items()
                    if key != "observations"
                }
            )
            all_observations.extend(observations)

        aggregate = {
            "version": "isolated-af-aggregate-report.v1",
            "case_count": len(cases),
            "rounds": rounds,
            "observation_count": len(all_observations),
            "completed_count": sum(
                item.status == "completed" for item in all_observations
            ),
            "failed_count": sum(item.status == "failed" for item in all_observations),
            "confirmed_action_count": sum(
                item.confirmed_action_count for item in all_observations
            ),
            "production_write_count": sum(
                item.production_write_count for item in all_observations
            ),
            "telegram_send_count": sum(
                item.telegram_send_count for item in all_observations
            ),
            "round_summaries": round_summaries,
        }
        _atomic_write_json(output_dir / "aggregate.json", aggregate)
        _atomic_write_text(
            output_dir / "aggregate.md",
            "\n".join(
                (
                    "# Stage12 Isolated A–F",
                    "",
                    f"- Completion: {aggregate['completed_count']}/{aggregate['observation_count']}",
                    f"- Failed: {aggregate['failed_count']}",
                    f"- Confirmed actions: {aggregate['confirmed_action_count']}",
                    f"- Production writes: {aggregate['production_write_count']}",
                    f"- Telegram sends: {aggregate['telegram_send_count']}",
                    "",
                )
            ),
        )
        return aggregate
    finally:
        executor.observations.clear()
        for pattern in ("*.tmp", ".*.tmp"):
            for temporary in output_dir.glob(pattern):
                temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, value: object) -> None:
    _atomic_write_text(
        path,
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            default=str,
        )
        + "\n",
    )


def _atomic_write_text(path: Path, value: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument(
        "--no-actions",
        action="store_true",
        help="Do not materialize disposable unconfirmed action proposals.",
    )
    args = parser.parse_args()
    aggregate = run_isolated_af_campaign(
        output_dir=args.output_dir,
        rounds=args.rounds,
        materialize_actions=not args.no_actions,
    )
    print(json.dumps(aggregate, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "IsolatedAFExecutor",
    "IsolatedAFRunObservationV1",
    "StageObservationV1",
    "run_isolated_af_campaign",
    "validate_isolated_execution_request",
]


if __name__ == "__main__":
    raise SystemExit(main())
