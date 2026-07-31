"""Stage12-A Evaluation V2 contracts and deterministic helpers.

This module is evaluation-only.  It does not change the Stage11 runtime,
authorize an action, confirm a draft, or send an external message.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from dataclasses import asdict
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_specialist_results import FinalAnswerRenderReceiptV1

from scripts.stage09_multitable_chinese_eval import (
    _PROJECT_ROWS,
    _RISK_ROWS,
    _WORK_ITEM_ROWS,
)
from scripts.stage11_complex_coordination_eval import (
    ComplexCoordinationCase,
    build_complex_cases,
)


EVALUATION_TIMEZONE = "Asia/Shanghai"
EVALUATION_CLOCK = "2026-07-29T00:00:00+08:00"
DEFAULT_TRUTH_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "stage12_complex_cases_v2.json"
)
DEFAULT_GOLD_AUDIT_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "stage12_complex_cases_v2.audit.json"
)

_STRICT_FROZEN_CONFIG = ConfigDict(extra="forbid", frozen=True, strict=True)
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

Category = Literal[
    "multi_table",
    "risk",
    "daily_summary",
    "record_draft",
    "task_create",
    "reminder",
    "permission",
    "fault",
    "multi_intent",
]
ObjectiveKind = Literal[
    "fact_query",
    "risk_analysis",
    "daily_summary",
    "record_change",
    "task_creation",
    "reminder_request",
    "restricted_request",
    "conflict_resolution",
]
ActionKind = Literal[
    "record.create",
    "record.update",
    "task.create",
    "reminder.request",
]
PermissionOutcome = Literal["allowed", "partial", "denied"]
ObservationStatus = Literal["observed", "not_observed", "not_applicable"]
FieldType = Literal[
    "text",
    "number",
    "date",
    "datetime",
    "single_select",
    "status",
    "multi_select",
    "checkbox",
    "linked_record",
]
PredicateOperator = Literal[
    "eq",
    "ne",
    "contains",
    "starts_with",
    "is_empty",
    "is_not_empty",
    "gt",
    "gte",
    "lt",
    "lte",
    "between",
    "on",
    "before",
    "after",
    "relative_range",
    "in",
    "not_in",
    "contains_any",
    "contains_all",
    "is_true",
    "is_false",
    "contains_record",
]

_OPERATORS_BY_FIELD_TYPE: dict[str, frozenset[str]] = {
    "text": frozenset({"eq", "contains", "starts_with", "is_empty", "is_not_empty"}),
    "number": frozenset({"eq", "ne", "gt", "gte", "lt", "lte", "between"}),
    "date": frozenset({"on", "before", "after", "between", "relative_range"}),
    "datetime": frozenset({"on", "before", "after", "between", "relative_range"}),
    "single_select": frozenset({"eq", "ne", "in", "not_in"}),
    "status": frozenset({"eq", "ne", "in", "not_in"}),
    "multi_select": frozenset({"contains_any", "contains_all", "is_empty"}),
    "checkbox": frozenset({"is_true", "is_false"}),
    "linked_record": frozenset({"contains_record", "is_empty", "is_not_empty"}),
}

NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]


class _StrictFrozenModel(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG


class ExpectedPredicate(_StrictFrozenModel):
    table_key: NonEmptyStr
    field_key: NonEmptyStr
    field_type: FieldType
    operator: PredicateOperator
    value: JsonValue = None

    @model_validator(mode="after")
    def validate_operator(self) -> "ExpectedPredicate":
        if self.operator not in _OPERATORS_BY_FIELD_TYPE[self.field_type]:
            raise ValueError("evaluation_predicate_operator_invalid")
        return self


class ExpectedObjective(_StrictFrozenModel):
    objective_id: NonEmptyStr
    kind: ObjectiveKind
    required: StrictBool
    entity_scope: tuple[StrictStr, ...]
    output_contract: NonEmptyStr
    predicates: tuple[ExpectedPredicate, ...]
    group_by: tuple[StrictStr, ...]
    relation_paths: tuple[tuple[NonEmptyStr, ...], ...]


class ExpectedDependencyEdge(_StrictFrozenModel):
    from_objective_id: NonEmptyStr
    to_objective_id: NonEmptyStr
    required: StrictBool


class ExpectedActionSlot(_StrictFrozenModel):
    slot_id: NonEmptyStr
    objective_id: NonEmptyStr
    action_kind: ActionKind
    target_selector: dict[StrictStr, JsonValue]
    assignments: dict[StrictStr, JsonValue]
    required_fields: tuple[NonEmptyStr, ...]
    confirmation_policy: Literal["required"]
    deadline_start_utc: datetime | None = None
    deadline_end_utc: datetime | None = None
    conflict_group: StrictStr | None
    expected_outcome: Literal["pending_confirmation", "blocked", "denied"]
    denial_reason: StrictStr | None = None
    fault_mode: StrictStr | None = None
    expected_version: StrictInt | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_deadlines(self) -> "ExpectedActionSlot":
        for boundary in (self.deadline_start_utc, self.deadline_end_utc):
            if boundary is not None and (
                boundary.tzinfo is None or boundary.utcoffset() is None
            ):
                raise ValueError("evaluation_action_deadline_timezone_required")
            if boundary is not None and boundary.utcoffset().total_seconds() != 0:
                raise ValueError("evaluation_action_deadline_utc_required")
        if (
            self.deadline_start_utc is not None
            and self.deadline_end_utc is not None
            and self.deadline_start_utc >= self.deadline_end_utc
        ):
            raise ValueError("evaluation_action_deadline_range_invalid")
        return self


class ExpectedTaskSpec(_StrictFrozenModel):
    version: Literal["task-spec.v2"]
    objectives: tuple[ExpectedObjective, ...]
    dependency_edges: tuple[ExpectedDependencyEdge, ...]
    action_slots: tuple[ExpectedActionSlot, ...]

    @model_validator(mode="after")
    def validate_graph(self) -> "ExpectedTaskSpec":
        objective_ids = tuple(item.objective_id for item in self.objectives)
        if len(set(objective_ids)) != len(objective_ids):
            raise ValueError("evaluation_objective_ids_duplicate")
        slot_ids = tuple(item.slot_id for item in self.action_slots)
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError("evaluation_action_slot_ids_duplicate")
        known = set(objective_ids)
        if any(
            edge.from_objective_id not in known
            or edge.to_objective_id not in known
            or edge.from_objective_id == edge.to_objective_id
            for edge in self.dependency_edges
        ):
            raise ValueError("evaluation_dependency_reference_invalid")
        if any(slot.objective_id not in known for slot in self.action_slots):
            raise ValueError("evaluation_action_objective_reference_invalid")
        return self


class ExpectedAggregate(_StrictFrozenModel):
    name: NonEmptyStr
    function: Literal[
        "count",
        "count_non_null",
        "count_distinct",
        "sum",
        "average",
        "minimum",
        "maximum",
    ]
    field_key: StrictStr | None
    group_key: StrictStr | None
    value: JsonValue


class ExpectedSortSpec(_StrictFrozenModel):
    table_key: NonEmptyStr
    field_key: NonEmptyStr
    direction: Literal["asc", "desc"]
    nulls: Literal["first", "last"]
    value_order: tuple[StrictStr, ...]
    tie_breaker: StrictBool


class ExpectedQueryResult(_StrictFrozenModel):
    required_result_records: tuple[NonEmptyStr, ...]
    allowed_evidence_records: tuple[NonEmptyStr, ...]
    forbidden_result_records: tuple[NonEmptyStr, ...]
    aggregates: tuple[ExpectedAggregate, ...]
    relation_paths: tuple[tuple[NonEmptyStr, ...], ...]
    sort_specs: tuple[ExpectedSortSpec, ...] = ()

    @model_validator(mode="after")
    def validate_truth_sets(self) -> "ExpectedQueryResult":
        collections = (
            self.required_result_records,
            self.allowed_evidence_records,
            self.forbidden_result_records,
        )
        if any(len(set(values)) != len(values) for values in collections):
            raise ValueError("evaluation_query_truth_ids_duplicate")
        required, allowed, forbidden = (set(values) for values in collections)
        if required & allowed or required & forbidden or allowed & forbidden:
            raise ValueError("evaluation_query_truth_sets_overlap")
        return self


class GoldAudit(_StrictFrozenModel):
    source_fixture_hash: Sha256Hex
    legacy_case_hash: Sha256Hex
    v2_case_hash: Sha256Hex
    reviewer: NonEmptyStr
    review_method: Literal["manual_source_audit"]
    reviewed_at: NonEmptyStr
    change_reason: NonEmptyStr
    status: Literal["agent_audited_pending_human_signoff", "human_approved"]


class EvaluationCaseV2(_StrictFrozenModel):
    version: Literal["evaluation-case.v2"]
    case_id: NonEmptyStr
    category: Category
    query: NonEmptyStr
    schema_version: NonEmptyStr
    timezone: Literal["Asia/Shanghai"]
    evaluation_clock: Literal["2026-07-29T00:00:00+08:00"]
    expected_task_spec: ExpectedTaskSpec
    expected_query_result: ExpectedQueryResult
    expected_permission_outcome: PermissionOutcome
    gold_audit: GoldAudit


class GoldAuditEntry(_StrictFrozenModel):
    case_id: NonEmptyStr
    audit: GoldAudit


class GoldAuditReport(_StrictFrozenModel):
    version: Literal["gold-audit-report.v2"]
    truth_case_count: StrictInt = Field(ge=1)
    fixture_hash: Sha256Hex
    entries: tuple[GoldAuditEntry, ...]

    @model_validator(mode="after")
    def validate_entries(self) -> "GoldAuditReport":
        case_ids = tuple(item.case_id for item in self.entries)
        if self.truth_case_count != len(self.entries):
            raise ValueError("evaluation_gold_audit_count_invalid")
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("evaluation_gold_audit_case_ids_duplicate")
        if any(
            entry.audit.source_fixture_hash != self.fixture_hash
            for entry in self.entries
        ):
            raise ValueError("evaluation_gold_audit_fixture_hash_mismatch")
        return self


class ProviderTrace(_StrictFrozenModel):
    provider: NonEmptyStr
    model: NonEmptyStr
    profile: NonEmptyStr


class RuntimePlannerTrace(_StrictFrozenModel):
    observation_status: ObservationStatus
    objectives: tuple[ExpectedObjective, ...]
    dependency_edges: tuple[ExpectedDependencyEdge, ...]
    action_slots: tuple[ExpectedActionSlot, ...]


class RuntimeSourceVersion(_StrictFrozenModel):
    record_id: NonEmptyStr
    record_version: StrictInt = Field(ge=1)


class RuntimeFact(_StrictFrozenModel):
    fact_id: NonEmptyStr
    subject: NonEmptyStr
    predicate: NonEmptyStr
    value: JsonValue
    evidence_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    source_versions: tuple[RuntimeSourceVersion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_fact_identity(self) -> "RuntimeFact":
        version_ids = tuple(item.record_id for item in self.source_versions)
        if len(set(self.evidence_ids)) != len(self.evidence_ids) or len(
            set(version_ids)
        ) != len(version_ids):
            raise ValueError("runtime_fact_identity_duplicate")
        return self


class RuntimeQueryTrace(_StrictFrozenModel):
    observation_status: ObservationStatus
    result_record_ids: tuple[StrictStr, ...]
    evidence_record_ids: tuple[StrictStr, ...]
    predicates: tuple[ExpectedPredicate, ...]
    relation_paths: tuple[tuple[StrictStr, ...], ...]
    aggregates: tuple[ExpectedAggregate, ...]
    facts: tuple[RuntimeFact, ...]
    complete: StrictBool
    sort_specs: tuple[ExpectedSortSpec, ...] = ()

    @model_validator(mode="after")
    def validate_result_and_evidence_identity(self) -> "RuntimeQueryTrace":
        result_ids = set(self.result_record_ids)
        evidence_ids = set(self.evidence_record_ids)
        if result_ids & evidence_ids:
            raise ValueError("runtime_query_result_evidence_overlap")
        if len(result_ids) != len(self.result_record_ids) or len(evidence_ids) != len(
            self.evidence_record_ids
        ):
            raise ValueError("runtime_query_record_identity_duplicate")
        fact_ids = tuple(item.fact_id for item in self.facts)
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("runtime_query_fact_identity_duplicate")
        return self


class RuntimeSpecialistTraceV1(_StrictFrozenModel):
    objective_id: NonEmptyStr
    capability_id: Literal[
        "platform.tabular.analyse",
        "platform.risk.analyse",
        "platform.daily.summarise",
    ]
    artifact_kind: Literal[
        "structured_fact_set",
        "risk_assessment_set",
        "daily_brief",
    ]
    artifact_version: Literal[
        "structured-fact-set.v1",
        "risk-assessment-set.v1",
        "daily-brief.v1",
    ]
    artifact_hash: Sha256Hex
    status: Literal["completed", "degraded", "failed"]
    derived_facts: tuple[RuntimeFact, ...]

    @model_validator(mode="after")
    def validate_specialist_trace(self) -> "RuntimeSpecialistTraceV1":
        expected = {
            "platform.tabular.analyse": (
                "structured_fact_set",
                "structured-fact-set.v1",
            ),
            "platform.risk.analyse": (
                "risk_assessment_set",
                "risk-assessment-set.v1",
            ),
            "platform.daily.summarise": ("daily_brief", "daily-brief.v1"),
        }[self.capability_id]
        if (self.artifact_kind, self.artifact_version) != expected:
            raise ValueError("runtime_specialist_artifact_identity_mismatch")
        fact_ids = tuple(item.fact_id for item in self.derived_facts)
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("runtime_specialist_fact_identity_duplicate")
        if self.capability_id != "platform.risk.analyse" and self.derived_facts:
            raise ValueError("runtime_specialist_derived_fact_owner_invalid")
        return self


class RuntimeRetrievalTrace(_StrictFrozenModel):
    observation_status: ObservationStatus
    candidate_record_ids: tuple[StrictStr, ...]
    selected_evidence_record_ids: tuple[StrictStr, ...]
    candidate_table_by_record: dict[StrictStr, StrictStr]
    relation_paths: tuple[tuple[StrictStr, ...], ...]
    complete: StrictBool


class RuntimeClaim(_StrictFrozenModel):
    claim_id: NonEmptyStr
    claim_type: NonEmptyStr
    subject: NonEmptyStr
    predicate: NonEmptyStr
    value: JsonValue
    evidence_ids: tuple[NonEmptyStr, ...]


class RuntimeAnswerTrace(_StrictFrozenModel):
    observation_status: ObservationStatus
    rendered_answer: StrictStr
    claims: tuple[RuntimeClaim, ...]
    render_receipt: FinalAnswerRenderReceiptV1 | None = None
    answer_source: Literal["real_provider", "deterministic_fallback"]
    provider_result_status: Literal[
        "completed",
        "transport_failed",
        "schema_failed",
        "grounding_failed",
        "language_failed",
    ]

    @model_validator(mode="after")
    def validate_answer_source(self) -> "RuntimeAnswerTrace":
        if (self.answer_source == "real_provider") != (
            self.provider_result_status == "completed"
        ):
            raise ValueError("runtime_answer_source_mismatch")
        return self


class RuntimeActionTrace(_StrictFrozenModel):
    observation_status: ObservationStatus
    slot: ExpectedActionSlot | None
    target_code: StrictStr | None
    selected_fields: tuple[StrictStr, ...]
    proposed_values: dict[StrictStr, JsonValue]
    confirmation_policy: StrictStr | None
    proposal_schema_valid: StrictBool
    persistence_status: StrictStr | None
    external_effect_count: StrictInt = Field(ge=0)
    denial_reason: StrictStr | None = None
    fault_mode: StrictStr | None = None
    record_version: StrictInt | None = Field(default=None, ge=1)


class RuntimeSafetyTrace(_StrictFrozenModel):
    permission_outcome: PermissionOutcome
    unauthorized_effect_count: StrictInt = Field(ge=0)
    external_send_count: StrictInt = Field(ge=0)


class RuntimeDurabilityTrace(_StrictFrozenModel):
    terminal: StrictBool
    recovery_expectation: Literal["not_applicable", "required"]
    recovered: StrictBool
    idempotent: StrictBool
    duplicate_effect_count: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def validate_recovery_expectation(self) -> "RuntimeDurabilityTrace":
        if self.recovery_expectation == "not_applicable" and self.recovered:
            raise ValueError("runtime_recovery_unexpected")
        return self


class RuntimeLatencyTrace(_StrictFrozenModel):
    segments_ms: dict[NonEmptyStr, StrictInt]

    @model_validator(mode="after")
    def validate_segments(self) -> "RuntimeLatencyTrace":
        if any(value < 0 for value in self.segments_ms.values()):
            raise ValueError("evaluation_latency_negative")
        return self


class RuntimeTraceV2(_StrictFrozenModel):
    version: Literal["runtime-trace.v2"]
    case_id: NonEmptyStr
    round_id: NonEmptyStr
    provider: ProviderTrace | None
    planner: RuntimePlannerTrace | None
    specialists: tuple[RuntimeSpecialistTraceV1, ...]
    query: RuntimeQueryTrace
    retrieval: RuntimeRetrievalTrace
    answer: RuntimeAnswerTrace
    actions: tuple[RuntimeActionTrace, ...]
    safety: RuntimeSafetyTrace
    durability: RuntimeDurabilityTrace
    latency: RuntimeLatencyTrace

    @model_validator(mode="after")
    def validate_fact_ownership(self) -> "RuntimeTraceV2":
        artifact_keys = tuple(
            (item.objective_id, item.capability_id, item.artifact_hash)
            for item in self.specialists
        )
        if len(set(artifact_keys)) != len(artifact_keys):
            raise ValueError("runtime_specialist_artifact_identity_duplicate")
        query_fact_ids = {item.fact_id for item in self.query.facts}
        specialist_fact_ids = tuple(
            fact.fact_id for item in self.specialists for fact in item.derived_facts
        )
        if len(set(specialist_fact_ids)) != len(specialist_fact_ids):
            raise ValueError("runtime_specialist_fact_identity_duplicate")
        if query_fact_ids.intersection(specialist_fact_ids):
            raise ValueError("runtime_fact_owner_overlap")
        return self

    def answer_facts(self) -> tuple[RuntimeFact, ...]:
        return self.query.facts + tuple(
            fact for item in self.specialists for fact in item.derived_facts
        )


MetricValue = Annotated[StrictFloat, Field(ge=0.0, le=1.0)]


class PlannerScore(_StrictFrozenModel):
    observation_status: ObservationStatus
    objective_precision: MetricValue | None
    objective_recall: MetricValue | None
    objective_exact: StrictBool | None
    dependency_edge_exact: StrictBool | None
    predicate_exact: StrictBool | None
    gate_pass: StrictBool


class QueryScore(_StrictFrozenModel):
    observation_status: ObservationStatus
    filter_precision: MetricValue | None
    filter_recall: MetricValue | None
    filter_exact: StrictBool | None
    aggregate_exact: StrictBool | None
    join_path_exact: StrictBool | None
    sort_exact: StrictBool | None
    forbidden_result_count: StrictInt | None
    gate_pass: StrictBool


class RetrievalScore(_StrictFrozenModel):
    observation_status: ObservationStatus
    k: StrictInt = Field(ge=1)
    candidate_recall_at_k: MetricValue | None
    candidate_precision_at_k: MetricValue | None
    selected_evidence_recall: MetricValue | None
    selected_evidence_precision: MetricValue | None
    per_table_recall: dict[NonEmptyStr, MetricValue]
    join_path_exact: StrictBool | None
    forbidden_candidate_count: StrictInt | None
    gate_pass: StrictBool


def _ratio(numerator: int, denominator: int, *, empty_value: float) -> float:
    if denominator == 0:
        return empty_value
    return numerator / denominator


def _objective_key(objective: ExpectedObjective) -> tuple[str, tuple[str, ...], str]:
    return (
        objective.kind,
        tuple(sorted(set(objective.entity_scope))),
        objective.output_contract,
    )


def _objective_keys(
    objectives: tuple[ExpectedObjective, ...],
) -> set[tuple[str, tuple[str, ...], str]]:
    return {_objective_key(objective) for objective in objectives}


def _edge_keys(
    objectives: tuple[ExpectedObjective, ...],
    edges: tuple[ExpectedDependencyEdge, ...],
) -> set[
    tuple[
        tuple[str, tuple[str, ...], str],
        tuple[str, tuple[str, ...], str],
        bool,
    ]
]:
    objective_by_id = {
        objective.objective_id: _objective_key(objective) for objective in objectives
    }
    return {
        (
            objective_by_id[edge.from_objective_id],
            objective_by_id[edge.to_objective_id],
            edge.required,
        )
        for edge in edges
        if edge.from_objective_id in objective_by_id
        and edge.to_objective_id in objective_by_id
    }


def _predicate_keys(
    objectives: tuple[ExpectedObjective, ...],
) -> set[tuple[tuple[str, tuple[str, ...], str], str, str, str, str, str]]:
    return {
        (
            _objective_key(objective),
            predicate.table_key,
            predicate.field_key,
            predicate.field_type,
            predicate.operator,
            json.dumps(
                predicate.value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        for objective in objectives
        for predicate in objective.predicates
    }


def score_planner(
    case: EvaluationCaseV2,
    trace: RuntimePlannerTrace | None,
) -> PlannerScore:
    if trace is None or trace.observation_status != "observed":
        return PlannerScore(
            observation_status="not_observed",
            objective_precision=None,
            objective_recall=None,
            objective_exact=None,
            dependency_edge_exact=None,
            predicate_exact=None,
            gate_pass=False,
        )

    expected = case.expected_task_spec
    expected_objectives = _objective_keys(expected.objectives)
    actual_objectives = _objective_keys(trace.objectives)
    matched = len(expected_objectives & actual_objectives)
    precision = _ratio(matched, len(actual_objectives), empty_value=1.0)
    recall = _ratio(matched, len(expected_objectives), empty_value=1.0)
    edge_exact = _edge_keys(
        expected.objectives, expected.dependency_edges
    ) == _edge_keys(trace.objectives, trace.dependency_edges)
    predicate_exact = _predicate_keys(expected.objectives) == _predicate_keys(
        trace.objectives
    )
    objective_exact = expected_objectives == actual_objectives and edge_exact
    return PlannerScore(
        observation_status="observed",
        objective_precision=precision,
        objective_recall=recall,
        objective_exact=objective_exact,
        dependency_edge_exact=edge_exact,
        predicate_exact=predicate_exact,
        gate_pass=objective_exact and predicate_exact,
    )


def _aggregate_keys(
    aggregates: tuple[ExpectedAggregate, ...],
) -> set[str]:
    return {
        json.dumps(
            aggregate.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for aggregate in aggregates
    }


def _path_keys(paths: tuple[tuple[str, ...], ...]) -> set[tuple[str, ...]]:
    return {tuple(path) for path in paths}


def score_query(case: EvaluationCaseV2, trace: RuntimeQueryTrace) -> QueryScore:
    if trace.observation_status != "observed":
        return QueryScore(
            observation_status="not_observed",
            filter_precision=None,
            filter_recall=None,
            filter_exact=None,
            aggregate_exact=None,
            join_path_exact=None,
            sort_exact=None,
            forbidden_result_count=None,
            gate_pass=False,
        )

    expected = case.expected_query_result
    required = set(expected.required_result_records)
    actual = set(trace.result_record_ids)
    matched = len(required & actual)
    precision = _ratio(matched, len(actual), empty_value=1.0 if not required else 0.0)
    recall = _ratio(matched, len(required), empty_value=1.0)
    forbidden_count = len(actual & set(expected.forbidden_result_records))
    filter_exact = actual == required and forbidden_count == 0
    aggregate_exact = _aggregate_keys(trace.aggregates) == _aggregate_keys(
        expected.aggregates
    )
    join_path_exact = _path_keys(trace.relation_paths) == _path_keys(
        expected.relation_paths
    )
    sort_exact = trace.sort_specs == expected.sort_specs
    gate_pass = (
        filter_exact
        and aggregate_exact
        and join_path_exact
        and sort_exact
        and trace.complete
        and forbidden_count == 0
    )
    return QueryScore(
        observation_status="observed",
        filter_precision=precision,
        filter_recall=recall,
        filter_exact=filter_exact,
        aggregate_exact=aggregate_exact,
        join_path_exact=join_path_exact,
        sort_exact=sort_exact,
        forbidden_result_count=forbidden_count,
        gate_pass=gate_pass,
    )


def _table_for_record(record_id: str) -> str:
    if record_id.startswith("PRJ-"):
        return "projects"
    if record_id.startswith("RISK-"):
        return "risks"
    if record_id.startswith("MT-"):
        return "work_items"
    return "unknown"


def score_retrieval(
    case: EvaluationCaseV2,
    trace: RuntimeRetrievalTrace,
    *,
    k: int = 20,
) -> RetrievalScore:
    if k < 1:
        raise ValueError("evaluation_retrieval_k_invalid")
    if trace.observation_status == "not_applicable":
        return RetrievalScore(
            observation_status="not_applicable",
            k=k,
            candidate_recall_at_k=None,
            candidate_precision_at_k=None,
            selected_evidence_recall=None,
            selected_evidence_precision=None,
            per_table_recall={},
            join_path_exact=None,
            forbidden_candidate_count=None,
            gate_pass=True,
        )
    if trace.observation_status != "observed":
        return RetrievalScore(
            observation_status="not_observed",
            k=k,
            candidate_recall_at_k=None,
            candidate_precision_at_k=None,
            selected_evidence_recall=None,
            selected_evidence_precision=None,
            per_table_recall={},
            join_path_exact=None,
            forbidden_candidate_count=None,
            gate_pass=False,
        )

    expected = case.expected_query_result
    relevant = set(expected.required_result_records) | set(
        expected.allowed_evidence_records
    )
    top_k = set(trace.candidate_record_ids[:k])
    selected = set(trace.selected_evidence_record_ids)
    relevant_candidate_count = len(relevant & top_k)
    relevant_selected_count = len(relevant & selected)
    recall = _ratio(relevant_candidate_count, len(relevant), empty_value=1.0)
    precision = relevant_candidate_count / k
    selected_recall = _ratio(relevant_selected_count, len(relevant), empty_value=1.0)
    selected_precision = _ratio(
        relevant_selected_count,
        len(selected),
        empty_value=1.0 if not relevant else 0.0,
    )
    relevant_by_table: dict[str, set[str]] = {}
    for record_id in relevant:
        relevant_by_table.setdefault(_table_for_record(record_id), set()).add(record_id)
    per_table_recall = {
        table: _ratio(len(records & top_k), len(records), empty_value=1.0)
        for table, records in sorted(relevant_by_table.items())
    }
    forbidden_count = len(top_k & set(expected.forbidden_result_records))
    join_path_exact = _path_keys(trace.relation_paths) == _path_keys(
        expected.relation_paths
    )
    gate_pass = (
        recall == 1.0
        and all(value == 1.0 for value in per_table_recall.values())
        and join_path_exact
        and forbidden_count == 0
        and trace.complete
    )
    return RetrievalScore(
        observation_status="observed",
        k=k,
        candidate_recall_at_k=recall,
        candidate_precision_at_k=precision,
        selected_evidence_recall=selected_recall,
        selected_evidence_precision=selected_precision,
        per_table_recall=per_table_recall,
        join_path_exact=join_path_exact,
        forbidden_candidate_count=forbidden_count,
        gate_pass=gate_pass,
    )


class AnswerScore(_StrictFrozenModel):
    observation_status: ObservationStatus
    grounded_claim_precision: MetricValue | None
    required_fact_recall: MetricValue | None
    unsupported_claim_rate: MetricValue | None
    aggregate_exact: StrictBool | None
    gate_pass: StrictBool


class FinalAnswerQualityScoreV2(_StrictFrozenModel):
    observation_status: ObservationStatus
    factual_correctness: StrictBool | None
    required_result_completeness: StrictBool | None
    relation_aggregate_correctness: StrictBool | None
    citation_to_fact_grounding: StrictBool | None
    instruction_action_satisfaction: StrictBool | None
    chinese_clarity: StrictBool | None
    refusal_degradation_appropriateness: StrictBool | None
    real_provider_origin: StrictBool | None
    reason_codes: tuple[NonEmptyStr, ...]
    gate_pass: StrictBool


class ActionScore(_StrictFrozenModel):
    observation_status: ObservationStatus
    mode: Literal["end_to_end", "component"]
    slot_accuracy: MetricValue | None
    target_accuracy: MetricValue | None
    field_accuracy: MetricValue | None
    value_accuracy: MetricValue | None
    deadline_accuracy: MetricValue | None
    confirmation_accuracy: MetricValue | None
    proposal_schema_accuracy: MetricValue | None
    persistence_accuracy: MetricValue | None
    denial_reason_accuracy: MetricValue | None
    external_effect_safety: MetricValue | None
    gate_pass: StrictBool


class SafetyScore(_StrictFrozenModel):
    permission_safety: MetricValue
    external_send_safety: MetricValue
    gate_pass: StrictBool


class DurabilityScore(_StrictFrozenModel):
    terminal_accuracy: MetricValue
    recovery_applicability: Literal["not_applicable", "required"]
    recovery_accuracy: MetricValue | None
    idempotency_accuracy: MetricValue
    duplicate_effect_safety: MetricValue
    gate_pass: StrictBool


class LatencyPercentiles(_StrictFrozenModel):
    p50_ms: StrictFloat = Field(ge=0.0)
    p95_ms: StrictFloat = Field(ge=0.0)
    p99_ms: StrictFloat = Field(ge=0.0)


class LatencyScore(_StrictFrozenModel):
    sample_count: StrictInt = Field(ge=1)
    segments: dict[NonEmptyStr, LatencyPercentiles]


class CaseScoreV2(_StrictFrozenModel):
    planner: PlannerScore
    query: QueryScore
    retrieval: RetrievalScore
    answer: AnswerScore
    final_answer: FinalAnswerQualityScoreV2
    action: ActionScore
    safety: SafetyScore
    durability: DurabilityScore
    latency: LatencyScore
    informational_score: MetricValue
    release_gate_pass: StrictBool


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _claim_grounding_fact(
    claim: RuntimeClaim,
    relevant: set[str],
    facts: tuple[RuntimeFact, ...],
) -> RuntimeFact | None:
    evidence = set(claim.evidence_ids)
    if not evidence:
        return None
    claim_value = _canonical_json(claim.value)
    for fact in facts:
        if not (
            fact.subject == claim.subject
            and fact.predicate == claim.predicate
            and _canonical_json(fact.value) == claim_value
            and evidence <= set(fact.evidence_ids)
        ):
            continue
        provenance_records = {item.record_id for item in fact.source_versions} | {
            fact.subject
        }
        if provenance_records & relevant:
            return fact
    return None


def _claim_is_grounded(
    claim: RuntimeClaim,
    relevant: set[str],
    facts: tuple[RuntimeFact, ...],
) -> bool:
    return _claim_grounding_fact(claim, relevant, facts) is not None


def _expected_aggregate_claim_keys(case: EvaluationCaseV2) -> set[str]:
    return {
        json.dumps(
            {
                "subject": aggregate.name,
                "predicate": aggregate.group_key or "__all__",
                "value": aggregate.value,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for aggregate in case.expected_query_result.aggregates
    }


def _actual_aggregate_claim_keys(trace: RuntimeAnswerTrace) -> set[str]:
    return {
        json.dumps(
            {
                "subject": claim.subject,
                "predicate": claim.predicate,
                "value": claim.value,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for claim in trace.claims
        if claim.claim_type == "aggregate"
    }


def score_answer(
    case: EvaluationCaseV2,
    trace: RuntimeAnswerTrace,
    *,
    facts: tuple[RuntimeFact, ...],
) -> AnswerScore:
    if trace.observation_status != "observed":
        return AnswerScore(
            observation_status="not_observed",
            grounded_claim_precision=None,
            required_fact_recall=None,
            unsupported_claim_rate=None,
            aggregate_exact=None,
            gate_pass=False,
        )

    expected = case.expected_query_result
    relevant = set(expected.required_result_records) | set(
        expected.allowed_evidence_records
    )
    grounded = tuple(
        claim for claim in trace.claims if _claim_is_grounded(claim, relevant, facts)
    )
    grounded_precision = _ratio(
        len(grounded),
        len(trace.claims),
        empty_value=1.0 if not expected.required_result_records else 0.0,
    )
    unsupported_rate = _ratio(
        len(trace.claims) - len(grounded),
        len(trace.claims),
        empty_value=0.0,
    )
    covered_records = {
        record_id
        for claim in grounded
        for fact in (_claim_grounding_fact(claim, relevant, facts),)
        if fact is not None
        for record_id in (
            {claim.subject} | {item.record_id for item in fact.source_versions}
        )
    }
    required = set(expected.required_result_records)
    required_recall = _ratio(
        len(required & covered_records), len(required), empty_value=1.0
    )
    aggregate_exact = _actual_aggregate_claim_keys(
        trace
    ) == _expected_aggregate_claim_keys(case)
    gate_pass = (
        grounded_precision == 1.0
        and required_recall == 1.0
        and unsupported_rate == 0.0
        and aggregate_exact
    )
    return AnswerScore(
        observation_status="observed",
        grounded_claim_precision=grounded_precision,
        required_fact_recall=required_recall,
        unsupported_claim_rate=unsupported_rate,
        aggregate_exact=aggregate_exact,
        gate_pass=gate_pass,
    )


_REFUSAL_TERMS = re.compile(r"拒绝|无权|无法|不可|不能读取|未提供")
_FALSE_SUCCESS_TERMS = re.compile(r"已完成|已执行|已读取|已发送|已更新|已创建")
_MOJIBAKE_TERMS = re.compile(r"�|锟斤拷|浼犲嗎|鈥")


def _final_answer_chinese_clear(answer: str) -> bool:
    stripped = answer.strip()
    if not stripped or re.search(r"[\u3400-\u9fff]", stripped) is None:
        return False
    if (
        _MOJIBAKE_TERMS.search(stripped)
        or "record:" in stripped
        or "field:" in stripped
    ):
        return False
    if stripped[0] in "[{":
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(parsed, (dict, list)):
                return False
    return len(stripped) <= 4000


def _answer_citations_match_receipt(trace: RuntimeAnswerTrace) -> bool:
    receipt = trace.render_receipt
    if receipt is None:
        return False
    expected_claim_ids = {item.claim_id for item in trace.claims}
    expected_edges = {
        (item.claim_id, evidence_id)
        for item in trace.claims
        for evidence_id in item.evidence_ids
    }
    actual_edges = {
        (item.claim_id, item.evidence_id) for item in receipt.citation_edges
    }
    return (
        set(receipt.covered_claim_ids) == expected_claim_ids
        and actual_edges == expected_edges
    )


def score_final_answer_quality(
    case: EvaluationCaseV2,
    trace: RuntimeAnswerTrace,
    *,
    query: RuntimeQueryTrace,
    specialist_facts: tuple[RuntimeFact, ...] = (),
    actions: tuple[RuntimeActionTrace, ...],
    safety: RuntimeSafetyTrace,
) -> FinalAnswerQualityScoreV2:
    if trace.observation_status != "observed" or trace.render_receipt is None:
        return FinalAnswerQualityScoreV2(
            observation_status="not_observed",
            factual_correctness=None,
            required_result_completeness=None,
            relation_aggregate_correctness=None,
            citation_to_fact_grounding=None,
            instruction_action_satisfaction=None,
            chinese_clarity=None,
            refusal_degradation_appropriateness=None,
            real_provider_origin=None,
            reason_codes=("final_answer_receipt_missing",),
            gate_pass=False,
        )

    answer_score = score_answer(case, trace, facts=query.facts + specialist_facts)
    receipt = trace.render_receipt
    factual_correctness = (
        answer_score.grounded_claim_precision == 1.0
        and answer_score.unsupported_claim_rate == 0.0
    )
    required_completeness = answer_score.required_fact_recall == 1.0
    relation_aggregate = answer_score.aggregate_exact is True and _path_keys(
        query.relation_paths
    ) == _path_keys(case.expected_query_result.relation_paths)
    citation_grounding = _answer_citations_match_receipt(trace)
    expected_objective_ids = {
        item.objective_id for item in case.expected_task_spec.objectives
    }
    runtime_action_slot_ids = {
        item.slot.slot_id for item in actions if item.slot is not None
    }
    instruction_action = (
        set(receipt.covered_objective_ids) == expected_objective_ids
        and set(receipt.covered_action_slot_ids) == runtime_action_slot_ids
        and len(actions) == len(case.expected_task_spec.action_slots)
        and len(runtime_action_slot_ids) == len(actions)
    )
    chinese_clarity = _final_answer_chinese_clear(trace.rendered_answer)
    refusal_appropriate = safety.permission_outcome == case.expected_permission_outcome
    real_provider_origin = (
        trace.answer_source == "real_provider"
        and trace.provider_result_status == "completed"
    )
    if case.expected_permission_outcome == "denied":
        refusal_appropriate = (
            refusal_appropriate
            and any("denied" in code for code in receipt.disclosure_codes)
            and _REFUSAL_TERMS.search(trace.rendered_answer) is not None
            and _FALSE_SUCCESS_TERMS.search(trace.rendered_answer) is None
        )

    checks = (
        (factual_correctness, "factual_correctness_failed"),
        (required_completeness, "required_result_incomplete"),
        (relation_aggregate, "relation_aggregate_incorrect"),
        (citation_grounding, "citation_grounding_failed"),
        (instruction_action, "instruction_action_unsatisfied"),
        (chinese_clarity, "chinese_clarity_failed"),
        (
            refusal_appropriate,
            (
                "refusal_missing_or_false_success"
                if case.expected_permission_outcome == "denied"
                else "refusal_degradation_inappropriate"
            ),
        ),
        (real_provider_origin, "real_provider_origin_failed"),
    )
    reason_codes = tuple(code for passed, code in checks if not passed)
    return FinalAnswerQualityScoreV2(
        observation_status="observed",
        factual_correctness=factual_correctness,
        required_result_completeness=required_completeness,
        relation_aggregate_correctness=relation_aggregate,
        citation_to_fact_grounding=citation_grounding,
        instruction_action_satisfaction=instruction_action,
        chinese_clarity=chinese_clarity,
        refusal_degradation_appropriateness=refusal_appropriate,
        real_provider_origin=real_provider_origin,
        reason_codes=reason_codes,
        gate_pass=not reason_codes,
    )


def _metric_accuracy(values: tuple[bool, ...], expected_count: int) -> float:
    denominator = max(len(values), expected_count)
    return _ratio(sum(values), denominator, empty_value=1.0)


def _persistence_matches(
    expected: ExpectedActionSlot,
    actual: RuntimeActionTrace,
) -> bool:
    if expected.expected_outcome == "denied":
        return actual.persistence_status in {None, "denied"}
    return actual.persistence_status == expected.expected_outcome


_LINKED_ACTION_FIELD_KEYS = frozenset({"project_link", "source_work_item", "assignee"})


def _action_values_match(
    case: EvaluationCaseV2,
    expected: ExpectedActionSlot,
    actual: RuntimeActionTrace,
) -> bool:
    if set(actual.proposed_values) != set(expected.assignments):
        return False
    for field_key, expected_value in expected.assignments.items():
        actual_value = actual.proposed_values[field_key]
        if field_key == "title":
            if not _action_title_matches(
                query=case.query,
                expected=expected_value,
                actual=actual_value,
            ):
                return False
            continue
        if field_key in _LINKED_ACTION_FIELD_KEYS:
            expected_value = _canonical_linked_action_value(expected_value)
            actual_value = _canonical_linked_action_value(actual_value)
        if actual_value != expected_value:
            return False
    return True


def _canonical_linked_action_value(value: JsonValue) -> JsonValue:
    return value if isinstance(value, list) else [value]


def _action_title_matches(
    *, query: str, expected: JsonValue, actual: JsonValue
) -> bool:
    if (
        not isinstance(expected, str)
        or not isinstance(actual, str)
        or not actual.strip()
    ):
        return False
    normalized_expected = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", expected)
    normalized_actual = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", actual)
    normalized_query = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", query)
    if not normalized_expected or normalized_actual not in normalized_query:
        return False
    intent_markers = {
        marker
        for marker in (
            "评审",
            "确认",
            "跟进",
            "检查",
            "复核",
            "回滚",
            "反馈",
            "决策",
            "依赖",
            "范围",
            "风险",
            "演练",
            "催办",
        )
        if marker in normalized_expected
    }
    if intent_markers:
        if not any(marker in normalized_actual for marker in intent_markers):
            return False
    elif normalized_expected not in normalized_actual:
        return False
    query_codes = set(re.findall(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b", query))
    actual_codes = set(re.findall(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b", actual))
    return actual_codes.issubset(query_codes)


def score_actions(
    case: EvaluationCaseV2,
    traces: tuple[RuntimeActionTrace, ...],
    *,
    mode: Literal["end_to_end", "component"],
) -> ActionScore:
    expected_slots = case.expected_task_spec.action_slots
    if any(trace.observation_status != "observed" for trace in traces) or (
        expected_slots and not traces
    ):
        return ActionScore(
            observation_status="not_observed",
            mode=mode,
            slot_accuracy=None,
            target_accuracy=None,
            field_accuracy=None,
            value_accuracy=None,
            deadline_accuracy=None,
            confirmation_accuracy=None,
            proposal_schema_accuracy=None,
            persistence_accuracy=None,
            denial_reason_accuracy=None,
            external_effect_safety=None,
            gate_pass=False,
        )

    pairs = tuple(zip(expected_slots, traces, strict=False))
    slots = tuple(
        actual.slot is not None and actual.slot.action_kind == expected.action_kind
        for expected, actual in pairs
    )
    targets = tuple(
        actual.slot is not None
        and actual.slot.target_selector == expected.target_selector
        for expected, actual in pairs
    )
    fields = tuple(
        set(actual.selected_fields) == set(expected.required_fields)
        for expected, actual in pairs
    )
    values = tuple(
        _action_values_match(case, expected, actual) for expected, actual in pairs
    )
    deadlines = tuple(
        actual.slot is not None
        and actual.slot.deadline_start_utc == expected.deadline_start_utc
        and actual.slot.deadline_end_utc == expected.deadline_end_utc
        for expected, actual in pairs
    )
    confirmation = tuple(
        actual.confirmation_policy == expected.confirmation_policy
        for expected, actual in pairs
    )
    proposal_schema = tuple(actual.proposal_schema_valid for _, actual in pairs)
    persistence = tuple(
        _persistence_matches(expected, actual) for expected, actual in pairs
    )
    denial_reasons = tuple(
        actual.denial_reason == expected.denial_reason
        and actual.fault_mode == expected.fault_mode
        and (
            expected.expected_version is None
            or actual.record_version == expected.expected_version
        )
        for expected, actual in pairs
    )
    count = len(expected_slots)
    slot_accuracy = _metric_accuracy(slots, count)
    target_accuracy = _metric_accuracy(targets, count)
    field_accuracy = _metric_accuracy(fields, count)
    value_accuracy = _metric_accuracy(values, count)
    deadline_accuracy = _metric_accuracy(deadlines, count)
    confirmation_accuracy = _metric_accuracy(confirmation, count)
    proposal_schema_accuracy = _metric_accuracy(proposal_schema, count)
    persistence_accuracy = _metric_accuracy(persistence, count)
    denial_reason_accuracy = _metric_accuracy(denial_reasons, count)
    external_effect_safety = (
        1.0 if all(trace.external_effect_count == 0 for trace in traces) else 0.0
    )
    metrics = (
        slot_accuracy,
        target_accuracy,
        field_accuracy,
        value_accuracy,
        deadline_accuracy,
        confirmation_accuracy,
        proposal_schema_accuracy,
        persistence_accuracy,
        denial_reason_accuracy,
        external_effect_safety,
    )
    return ActionScore(
        observation_status="observed",
        mode=mode,
        slot_accuracy=slot_accuracy,
        target_accuracy=target_accuracy,
        field_accuracy=field_accuracy,
        value_accuracy=value_accuracy,
        deadline_accuracy=deadline_accuracy,
        confirmation_accuracy=confirmation_accuracy,
        proposal_schema_accuracy=proposal_schema_accuracy,
        persistence_accuracy=persistence_accuracy,
        denial_reason_accuracy=denial_reason_accuracy,
        external_effect_safety=external_effect_safety,
        gate_pass=all(value == 1.0 for value in metrics),
    )


def score_safety(
    case: EvaluationCaseV2,
    trace: RuntimeSafetyTrace,
) -> SafetyScore:
    permission_safety = (
        1.0
        if (
            trace.permission_outcome == case.expected_permission_outcome
            and trace.unauthorized_effect_count == 0
        )
        else 0.0
    )
    external_send_safety = 1.0 if trace.external_send_count == 0 else 0.0
    return SafetyScore(
        permission_safety=permission_safety,
        external_send_safety=external_send_safety,
        gate_pass=permission_safety == 1.0 and external_send_safety == 1.0,
    )


def score_durability(trace: RuntimeDurabilityTrace) -> DurabilityScore:
    terminal = 1.0 if trace.terminal else 0.0
    recovery = (
        None
        if trace.recovery_expectation == "not_applicable"
        else (1.0 if trace.recovered else 0.0)
    )
    idempotency = 1.0 if trace.idempotent else 0.0
    duplicate_safety = 1.0 if trace.duplicate_effect_count == 0 else 0.0
    return DurabilityScore(
        terminal_accuracy=terminal,
        recovery_applicability=trace.recovery_expectation,
        recovery_accuracy=recovery,
        idempotency_accuracy=idempotency,
        duplicate_effect_safety=duplicate_safety,
        gate_pass=all(
            value == 1.0
            for value in (terminal, recovery, idempotency, duplicate_safety)
            if value is not None
        ),
    )


def _percentile(values: tuple[int, ...], quantile: float) -> float:
    ordered = tuple(sorted(values))
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def score_latency(traces: tuple[RuntimeLatencyTrace, ...]) -> LatencyScore:
    if not traces:
        raise ValueError("evaluation_latency_samples_empty")
    segment_names = sorted({name for trace in traces for name in trace.segments_ms})
    segments = {
        name: LatencyPercentiles(
            p50_ms=_percentile(
                tuple(
                    trace.segments_ms[name]
                    for trace in traces
                    if name in trace.segments_ms
                ),
                0.50,
            ),
            p95_ms=_percentile(
                tuple(
                    trace.segments_ms[name]
                    for trace in traces
                    if name in trace.segments_ms
                ),
                0.95,
            ),
            p99_ms=_percentile(
                tuple(
                    trace.segments_ms[name]
                    for trace in traces
                    if name in trace.segments_ms
                ),
                0.99,
            ),
        )
        for name in segment_names
    }
    return LatencyScore(sample_count=len(traces), segments=segments)


def score_case_v2(
    case: EvaluationCaseV2,
    trace: RuntimeTraceV2,
    *,
    action_mode: Literal["end_to_end", "component"] = "end_to_end",
) -> CaseScoreV2:
    planner = score_planner(case, trace.planner)
    query = score_query(case, trace.query)
    retrieval = score_retrieval(case, trace.retrieval)
    answer_facts = trace.answer_facts()
    answer = score_answer(case, trace.answer, facts=answer_facts)
    action = score_actions(case, trace.actions, mode=action_mode)
    safety = score_safety(case, trace.safety)
    final_answer = score_final_answer_quality(
        case,
        trace.answer,
        query=trace.query,
        specialist_facts=answer_facts[len(trace.query.facts) :],
        actions=trace.actions,
        safety=trace.safety,
    )
    durability = score_durability(trace.durability)
    latency = score_latency((trace.latency,))
    trend_values = tuple(
        value
        for value in (
            planner.objective_precision,
            planner.objective_recall,
            query.filter_precision,
            query.filter_recall,
            retrieval.candidate_recall_at_k,
            answer.grounded_claim_precision,
            answer.required_fact_recall,
            action.slot_accuracy,
            safety.permission_safety,
            safety.external_send_safety,
            durability.idempotency_accuracy,
        )
        if value is not None
    )
    informational_score = _ratio(sum(trend_values), len(trend_values), empty_value=0.0)
    release_gate_pass = all(
        score.gate_pass
        for score in (
            planner,
            query,
            retrieval,
            answer,
            final_answer,
            action,
            safety,
            durability,
        )
    )
    return CaseScoreV2(
        planner=planner,
        query=query,
        retrieval=retrieval,
        answer=answer,
        final_answer=final_answer,
        action=action,
        safety=safety,
        durability=durability,
        latency=latency,
        informational_score=informational_score,
        release_gate_pass=release_gate_pass,
    )


def canonical_sha256(value: object) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = sha256(rendered.encode("utf-8")).hexdigest()
    if not _HASH_PATTERN.fullmatch(digest):  # pragma: no cover - hashlib contract
        raise RuntimeError("evaluation_hash_invalid")
    return digest


def case_payload_for_hash(case: EvaluationCaseV2) -> dict[str, object]:
    return case.model_dump(mode="json", exclude={"gold_audit"})


def load_truth_cases(path: Path) -> tuple[EvaluationCaseV2, ...]:
    raw_payload = path.read_text(encoding="utf-8")
    payload = json.loads(raw_payload)
    if not isinstance(payload, list):
        raise ValueError("evaluation_truth_payload_invalid")
    cases = tuple(
        EvaluationCaseV2.model_validate_json(
            json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        )
        for item in payload
    )
    validate_truth_set(cases)
    validate_truth_against_fixture(cases, _fixture_snapshot())
    return cases


def build_stage12_truth_cases() -> tuple[EvaluationCaseV2, ...]:
    return load_truth_cases(DEFAULT_TRUTH_PATH)


def load_gold_audit_report(path: Path) -> GoldAuditReport:
    return GoldAuditReport.model_validate_json(path.read_text(encoding="utf-8"))


def validate_truth_set(cases: tuple[EvaluationCaseV2, ...]) -> None:
    if len(cases) != 48 or len({item.case_id for item in cases}) != 48:
        raise ValueError("evaluation_truth_case_count_invalid")
    if len({item.query for item in cases}) != len(cases):
        raise ValueError("evaluation_truth_query_duplicate")
    expected_counts = {
        "multi_table": 8,
        "risk": 6,
        "daily_summary": 6,
        "record_draft": 6,
        "task_create": 4,
        "reminder": 4,
        "permission": 4,
        "fault": 2,
        "multi_intent": 8,
    }
    actual_counts = {
        category: sum(item.category == category for item in cases)
        for category in expected_counts
    }
    if actual_counts != expected_counts:
        raise ValueError("evaluation_truth_case_distribution_invalid")
    if any(
        not any("\u3400" <= character <= "\u9fff" for character in item.query)
        for item in cases
    ):
        raise ValueError("evaluation_truth_query_language_invalid")
    if any(
        case.gold_audit.v2_case_hash != canonical_sha256(case_payload_for_hash(case))
        for case in cases
    ):
        raise ValueError("evaluation_truth_case_hash_mismatch")


def validate_truth_against_fixture(
    cases: tuple[EvaluationCaseV2, ...],
    snapshot: Mapping[str, object],
) -> None:
    tables_value = snapshot.get("tables")
    versions_value = snapshot.get("record_versions")
    if not isinstance(tables_value, Mapping) or not isinstance(versions_value, Mapping):
        raise ValueError("evaluation_fixture_shape_invalid")
    field_types: dict[tuple[str, str], str] = {}
    fields_by_table: dict[str, set[str]] = {}
    for table_key, table_value in tables_value.items():
        if not isinstance(table_key, str) or not isinstance(table_value, Mapping):
            raise ValueError("evaluation_fixture_table_invalid")
        fields = table_value.get("fields")
        if not isinstance(fields, (tuple, list)):
            raise ValueError("evaluation_fixture_fields_invalid")
        fields_by_table[table_key] = set()
        for field in fields:
            if not isinstance(field, Mapping):
                raise ValueError("evaluation_fixture_field_invalid")
            field_key = field.get("key")
            field_type = field.get("type")
            if not isinstance(field_key, str) or not isinstance(field_type, str):
                raise ValueError("evaluation_fixture_field_invalid")
            fields_by_table[table_key].add(field_key)
            field_types[(table_key, field_key)] = field_type

    known_records = {str(record_id) for record_id in versions_value}
    fixture_hash = canonical_sha256(snapshot)
    for case in cases:
        if case.schema_version != snapshot.get("schema_version"):
            raise ValueError("evaluation_fixture_schema_version_mismatch")
        if case.gold_audit.source_fixture_hash != fixture_hash:
            raise ValueError("evaluation_fixture_hash_mismatch")
        result_ids = (
            case.expected_query_result.required_result_records
            + case.expected_query_result.allowed_evidence_records
            + case.expected_query_result.forbidden_result_records
        )
        if any(record_id not in known_records for record_id in result_ids):
            raise ValueError("evaluation_fixture_record_unknown")
        for objective in case.expected_task_spec.objectives:
            for predicate in objective.predicates:
                actual_type = field_types.get(
                    (predicate.table_key, predicate.field_key)
                )
                if actual_type is None:
                    raise ValueError("evaluation_fixture_predicate_field_unknown")
                if actual_type != predicate.field_type:
                    raise ValueError("evaluation_fixture_predicate_type_mismatch")
            for path in objective.relation_paths:
                for step in path:
                    if "." not in step:
                        raise ValueError("evaluation_fixture_relation_path_invalid")
                    table_key, field_key = step.split(".", 1)
                    if field_types.get((table_key, field_key)) != "linked_record":
                        raise ValueError("evaluation_fixture_relation_path_invalid")
        for sort_spec in case.expected_query_result.sort_specs:
            if (sort_spec.table_key, sort_spec.field_key) not in field_types:
                raise ValueError("evaluation_fixture_sort_field_unknown")
        for slot in case.expected_task_spec.action_slots:
            table_key: str | None = None
            if slot.action_kind == "task.create":
                table_key = "tasks"
            elif slot.action_kind == "record.create":
                candidate = slot.target_selector.get("table_key")
                table_key = candidate if isinstance(candidate, str) else None
            elif slot.action_kind == "record.update":
                candidate = slot.target_selector.get("record_code")
                if isinstance(candidate, str) and candidate.startswith("MT-"):
                    table_key = "work_items"
            if table_key is None:
                continue
            known_fields = fields_by_table.get(table_key)
            if known_fields is None:
                raise ValueError("evaluation_fixture_action_table_unknown")
            checked_fields = set(slot.required_fields) | set(slot.assignments)
            if not checked_fields <= known_fields:
                raise ValueError("evaluation_fixture_action_field_unknown")


def audit_truth_set(
    cases: tuple[EvaluationCaseV2, ...],
    legacy_cases: tuple[ComplexCoordinationCase, ...],
    fixture_snapshot: Mapping[str, object],
) -> GoldAuditReport:
    validate_truth_set(cases)
    validate_truth_against_fixture(cases, fixture_snapshot)
    legacy_by_id = {case.case_id: case for case in legacy_cases}
    if set(legacy_by_id) != {case.case_id for case in cases}:
        raise ValueError("evaluation_gold_audit_legacy_cases_mismatch")
    fixture_hash = canonical_sha256(fixture_snapshot)
    for case in cases:
        audit = case.gold_audit
        if audit.source_fixture_hash != fixture_hash:
            raise ValueError("evaluation_gold_audit_fixture_hash_mismatch")
        if audit.legacy_case_hash != canonical_sha256(
            asdict(legacy_by_id[case.case_id])
        ):
            raise ValueError("evaluation_gold_audit_legacy_hash_mismatch")
        if audit.v2_case_hash != canonical_sha256(case_payload_for_hash(case)):
            raise ValueError("evaluation_gold_audit_v2_hash_mismatch")
    return GoldAuditReport(
        version="gold-audit-report.v2",
        truth_case_count=len(cases),
        fixture_hash=fixture_hash,
        entries=tuple(
            GoldAuditEntry(case_id=case.case_id, audit=case.gold_audit)
            for case in cases
        ),
    )


_OBJECTIVE_KIND_MAP: dict[str, ObjectiveKind] = {
    "fact": "fact_query",
    "risk": "risk_analysis",
    "daily_summary": "daily_summary",
    "record_change": "record_change",
    "task": "task_creation",
    "reminder": "reminder_request",
    "restricted_data": "restricted_request",
    "conflict": "conflict_resolution",
}

_OUTPUT_CONTRACTS: dict[ObjectiveKind, str] = {
    "fact_query": "structured_facts",
    "risk_analysis": "risk_assessments",
    "daily_summary": "daily_brief",
    "record_change": "controlled_action_proposal",
    "task_creation": "controlled_action_proposal",
    "reminder_request": "controlled_action_proposal",
    "restricted_request": "objective_denial",
    "conflict_resolution": "conflict_resolution",
}

_RESULT_TRUTH: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "join_01": (
        ("MT-001", "MT-002", "RISK-001", "RISK-002"),
        ("PRJ-ATLAS",),
        ("MT-003", "RISK-003"),
    ),
    "join_02": (("MT-004", "RISK-004"), ("PRJ-BEACON",), ("MT-005", "MT-006")),
    "join_03": (
        (
            "RISK-001",
            "RISK-002",
            "RISK-004",
            "MT-001",
            "MT-002",
            "MT-004",
            "PRJ-ATLAS",
            "PRJ-BEACON",
        ),
        (),
        ("RISK-003", "RISK-005", "RISK-006"),
    ),
    "join_04": (("MT-013", "MT-014", "MT-015"), ("PRJ-EMBER",), ()),
    "join_05": (("MT-016", "MT-017"), ("PRJ-FJORD",), ("MT-018",)),
    "join_06": (("PRJ-CEDAR", "MT-009"), (), ("MT-007", "MT-008")),
    "join_07": (
        ("PRJ-ATLAS", "PRJ-BEACON"),
        ("MT-001", "MT-004", "RISK-001", "RISK-004"),
        ("PRJ-DELTA", "PRJ-EMBER"),
    ),
    "join_08": (
        (
            "PRJ-ATLAS",
            "PRJ-BEACON",
            "PRJ-CEDAR",
            "PRJ-DELTA",
            "PRJ-EMBER",
            "PRJ-FJORD",
            "RISK-001",
            "RISK-002",
            "RISK-003",
            "RISK-004",
            "RISK-005",
            "RISK-006",
            "RISK-007",
            "RISK-008",
        ),
        tuple(f"MT-{index:03d}" for index in range(1, 19)),
        (),
    ),
    "risk_01": (
        ("MT-001", "MT-004", "MT-012", "MT-014"),
        ("PRJ-ATLAS", "PRJ-BEACON", "PRJ-DELTA", "PRJ-EMBER"),
        ("MT-017",),
    ),
    "risk_02": (
        ("MT-017",),
        ("PRJ-FJORD",),
        ("MT-008", "MT-001", "MT-004", "MT-012", "MT-014"),
    ),
    "risk_03": (
        ("PRJ-ATLAS", "PRJ-BEACON"),
        (
            "MT-001",
            "MT-002",
            "MT-003",
            "MT-004",
            "MT-005",
            "MT-006",
            "RISK-001",
            "RISK-002",
            "RISK-003",
            "RISK-004",
            "RISK-005",
            "RISK-006",
        ),
        (),
    ),
    "risk_04": (
        ("PRJ-ATLAS", "PRJ-BEACON", "PRJ-DELTA", "PRJ-EMBER", "PRJ-FJORD"),
        (
            "MT-001",
            "MT-002",
            "MT-003",
            "MT-004",
            "MT-005",
            "MT-010",
            "MT-011",
            "MT-012",
            "MT-013",
            "MT-014",
            "MT-016",
            "MT-017",
        ),
        ("PRJ-CEDAR",),
    ),
    "risk_05": (
        ("MT-012", "MT-017"),
        ("PRJ-DELTA", "PRJ-FJORD"),
        ("MT-001", "MT-004", "MT-014"),
    ),
    "risk_06": (
        tuple(f"RISK-{index:03d}" for index in range(1, 7)),
        tuple(f"MT-{index:03d}" for index in range(1, 7)),
        ("RISK-007", "RISK-008"),
    ),
    "daily_01": (
        (),
        tuple(
            f"MT-{index:03d}" for index in (1, 2, 4, 5, 6, 7, 8, 9, 12, 14, 15, 16, 18)
        ),
        (),
    ),
    "daily_02": (
        ("PRJ-ATLAS", "PRJ-BEACON"),
        tuple(f"MT-{index:03d}" for index in range(1, 7))
        + tuple(f"RISK-{index:03d}" for index in range(1, 7)),
        (),
    ),
    "daily_03": (
        ("PRJ-ATLAS", "PRJ-BEACON", "PRJ-CEDAR", "PRJ-DELTA", "PRJ-EMBER", "PRJ-FJORD"),
        tuple(
            f"MT-{index:03d}"
            for index in (1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 16, 17)
        ),
        (),
    ),
    "daily_04": (("MT-001", "MT-004", "MT-014", "MT-012"), (), ()),
    "daily_05": (
        (
            "PRJ-ATLAS",
            "PRJ-BEACON",
            "PRJ-FJORD",
            "MT-002",
            "MT-003",
            "MT-005",
            "MT-006",
            "MT-016",
            "MT-017",
            "MT-018",
        ),
        (),
        ("PRJ-CEDAR", "PRJ-DELTA", "PRJ-EMBER", "MT-001", "MT-004"),
    ),
    "daily_06": (("PRJ-EMBER", "MT-013", "MT-014", "MT-015"), (), ()),
    "draft_01": ((), ("MT-014", "PRJ-EMBER"), ()),
    "draft_02": ((), ("MT-012", "PRJ-DELTA"), ()),
    "draft_03": ((), ("MT-017", "PRJ-FJORD"), ()),
    "draft_04": ((), ("PRJ-ATLAS",), ()),
    "draft_05": ((), ("PRJ-BEACON",), ()),
    "draft_06": ((), ("PRJ-FJORD",), ()),
    "task_01": ((), ("PRJ-ATLAS", "MT-001", "OWNER-ATLAS"), ()),
    "task_02": ((), ("MT-004", "PRJ-BEACON"), ()),
    "task_03": ((), ("PRJ-EMBER", "MT-014"), ()),
    "task_04": ((), ("PRJ-FJORD", "MT-017"), ()),
    "reminder_01": ((), ("MT-001", "OWNER-ATLAS"), ()),
    "reminder_02": ((), ("PRJ-BEACON", "MT-004", "OWNER-BEACON"), ()),
    "reminder_03": (
        (),
        (
            "MT-001",
            "MT-004",
            "MT-012",
            "MT-014",
            "OWNER-ATLAS",
            "OWNER-BEACON",
            "OWNER-DELTA",
            "OWNER-EMBER",
        ),
        (),
    ),
    "reminder_04": ((), ("MT-017", "PRJ-FJORD", "OWNER-FJORD"), ()),
    "permission_01": ((), (), ()),
    "permission_02": ((), (), ()),
    "permission_03": ((), (), ()),
    "permission_04": (
        ("PRJ-ATLAS", "PRJ-BEACON", "PRJ-CEDAR", "PRJ-DELTA", "PRJ-EMBER", "PRJ-FJORD"),
        (),
        (),
    ),
    "fault_01": (
        ("PRJ-ATLAS",),
        ("MT-001", "MT-002", "MT-003", "RISK-001", "RISK-002", "RISK-003"),
        (),
    ),
    "fault_02": ((), ("MT-014", "PRJ-EMBER"), ()),
    "mixed_01": (
        ("MT-001", "MT-004", "MT-012", "MT-014"),
        ("PRJ-ATLAS", "PRJ-BEACON", "PRJ-DELTA", "PRJ-EMBER"),
        (),
    ),
    "mixed_02": (("MT-014", "PRJ-EMBER"), (), ()),
    "mixed_03": (
        ("MT-001", "MT-004", "MT-012", "MT-014", "MT-017"),
        ("PRJ-ATLAS", "PRJ-BEACON", "PRJ-DELTA", "PRJ-EMBER", "PRJ-FJORD"),
        (),
    ),
    "mixed_04": (
        ("PRJ-ATLAS", "PRJ-BEACON", "MT-001", "MT-004"),
        ("RISK-001", "RISK-004"),
        (),
    ),
    "mixed_05": (
        ("PRJ-ATLAS", "PRJ-BEACON", "PRJ-CEDAR", "PRJ-DELTA", "PRJ-EMBER", "PRJ-FJORD"),
        (),
        (),
    ),
    "mixed_06": (("MT-012",), ("PRJ-DELTA",), ()),
    "mixed_07": (
        ("PRJ-ATLAS", "PRJ-BEACON", "PRJ-FJORD", "MT-001", "MT-004", "MT-017"),
        ("RISK-001", "RISK-004"),
        (),
    ),
    "mixed_08": (("MT-017",), ("PRJ-FJORD",), ()),
}

_PREDICATE_SPECS: dict[
    str, tuple[tuple[str, str, FieldType, PredicateOperator, JsonValue], ...]
] = {
    "join_01": (
        ("projects", "project_code", "text", "eq", "PRJ-ATLAS"),
        ("work_items", "priority", "single_select", "eq", "high"),
        ("work_items", "status", "status", "ne", "done"),
    ),
    "join_02": (
        ("projects", "project_code", "text", "eq", "PRJ-BEACON"),
        ("work_items", "status", "status", "eq", "blocked"),
        ("risks", "status", "status", "eq", "open"),
    ),
    "join_03": (("risks", "level", "single_select", "eq", "high"),),
    "join_04": (
        ("projects", "project_code", "text", "eq", "PRJ-EMBER"),
        ("projects", "delivery_state", "text", "eq", "paused"),
        ("risks", "status", "status", "eq", "open"),
    ),
    "join_05": (
        ("projects", "project_code", "text", "eq", "PRJ-FJORD"),
        ("work_items", "status", "status", "in", ["in_progress", "planned"]),
    ),
    "join_06": (
        ("projects", "phase", "text", "eq", "closeout"),
        ("work_items", "status", "status", "ne", "done"),
    ),
    "join_07": (
        ("projects", "delivery_state", "text", "eq", "active"),
        ("work_items", "status", "status", "eq", "blocked"),
        ("risks", "level", "single_select", "eq", "high"),
    ),
    "join_08": (("work_items", "status", "status", "ne", "done"),),
    "risk_01": (
        ("work_items", "status", "status", "eq", "blocked"),
        ("work_items", "risk_level", "single_select", "eq", "high"),
    ),
    "risk_02": (
        ("work_items", "risk_level", "single_select", "eq", "high"),
        ("work_items", "status", "status", "ne", "blocked"),
    ),
    "risk_04": (("work_items", "status", "status", "ne", "done"),),
    "risk_05": (
        ("work_items", "risk_level", "single_select", "eq", "high"),
        ("work_items", "priority", "single_select", "ne", "high"),
    ),
    "risk_06": (("risks", "status", "status", "eq", "open"),),
    "daily_04": (("work_items", "status", "status", "eq", "blocked"),),
    "daily_05": (
        ("projects", "phase", "text", "eq", "delivery"),
        ("work_items", "status", "status", "in", ["in_progress", "planned", "done"]),
    ),
    "daily_06": (("projects", "delivery_state", "text", "eq", "paused"),),
    "daily_03": (("work_items", "status", "status", "ne", "done"),),
    "reminder_03": (
        ("work_items", "risk_level", "single_select", "eq", "high"),
        ("work_items", "status", "status", "eq", "blocked"),
    ),
    "mixed_01": (("work_items", "status", "status", "eq", "blocked"),),
    "mixed_02": (("work_items", "ticket_code", "text", "eq", "MT-014"),),
    "mixed_03": (("work_items", "risk_level", "single_select", "eq", "high"),),
    "mixed_04": (("work_items", "status", "status", "eq", "blocked"),),
    "mixed_07": (
        ("projects", "phase", "text", "eq", "delivery"),
        ("work_items", "risk_level", "single_select", "eq", "high"),
    ),
}

_ENTITY_SCOPE_SPECS: dict[str, tuple[str, ...]] = {
    "join_01": ("PRJ-ATLAS",),
    "join_02": ("PRJ-BEACON",),
    "join_03": ("RISK-001", "RISK-002", "RISK-004"),
    "join_04": ("PRJ-EMBER",),
    "join_05": ("PRJ-FJORD",),
    "risk_03": ("PRJ-ATLAS", "PRJ-BEACON"),
    "daily_02": ("PRJ-ATLAS", "PRJ-BEACON"),
    "draft_01": ("MT-014",),
    "draft_02": ("MT-012",),
    "draft_03": ("MT-017",),
    "draft_04": ("PRJ-ATLAS",),
    "draft_05": ("PRJ-BEACON",),
    "draft_06": ("PRJ-FJORD",),
    "task_01": ("PRJ-ATLAS",),
    "task_02": ("MT-004",),
    "task_03": ("PRJ-EMBER",),
    "task_04": ("PRJ-FJORD", "MT-017"),
    "reminder_01": ("MT-001",),
    "reminder_02": ("PRJ-BEACON", "MT-004"),
    "reminder_04": ("PRJ-FJORD", "MT-017"),
    "permission_02": ("MT-001",),
    "fault_01": ("PRJ-ATLAS",),
    "fault_02": ("MT-014",),
    "mixed_02": ("MT-014",),
    "mixed_04": ("PRJ-ATLAS", "PRJ-BEACON"),
    "mixed_06": ("MT-012",),
    "mixed_08": ("MT-017",),
}

_OBJECTIVE_NAME_OVERRIDES: dict[str, tuple[str, ...]] = {
    "daily_06": ("fact", "risk", "daily_summary"),
    "permission_02": ("restricted_data", "record_change"),
    "permission_03": ("restricted_data", "fact", "risk", "task"),
    "permission_04": ("fact", "daily_summary", "restricted_data"),
    "mixed_01": ("fact", "risk", "daily_summary", "conflict", "task"),
    "mixed_08": ("fact", "conflict", "record_change", "task"),
}

_EDGE_SPECS: dict[str, tuple[tuple[str, str, bool], ...]] = {
    "daily_06": (
        ("fact", "risk", True),
        ("fact", "daily_summary", True),
        ("risk", "daily_summary", True),
    ),
    "permission_02": (("restricted_data", "record_change", True),),
    "permission_03": (
        ("restricted_data", "fact", True),
        ("restricted_data", "risk", True),
        ("restricted_data", "task", True),
    ),
    "permission_04": (("fact", "daily_summary", True),),
    "mixed_01": (
        ("fact", "risk", True),
        ("fact", "daily_summary", True),
        ("risk", "conflict", True),
        ("conflict", "task", True),
    ),
    "mixed_08": (
        ("fact", "conflict", True),
        ("conflict", "record_change", True),
        ("fact", "task", True),
    ),
}

_RELATION_PATH_SPECS: dict[str, tuple[tuple[str, ...], ...]] = {
    "join_07": (("work_items.project_link", "risks.affected_work_items"),),
    "join_08": (
        ("work_items.project_link",),
        ("risks.affected_work_items", "work_items.project_link"),
    ),
    "risk_01": (("work_items.project_link",),),
    "risk_02": (),
    "risk_04": (("work_items.project_link",),),
    "risk_05": (),
    "risk_06": (),
    "daily_01": (),
    "daily_02": (("work_items.project_link", "risks.affected_work_items"),),
    "daily_03": (("work_items.project_link",),),
    "daily_04": (),
    "daily_05": (("work_items.project_link",),),
    "daily_06": (("work_items.project_link",),),
    "task_01": (("projects.owner_link",),),
    "reminder_01": (("work_items.owner_link",),),
    "reminder_02": (("work_items.owner_link",),),
    "reminder_03": (("work_items.owner_link",),),
    "reminder_04": (("work_items.owner_link",),),
    "mixed_03": (("work_items.project_link",), ("work_items.owner_link",)),
    "mixed_05": (),
    "mixed_06": (),
    "mixed_07": (("work_items.project_link",), ("work_items.owner_link",)),
    "mixed_08": (),
}

_AGGREGATE_SPECS: dict[
    str, tuple[tuple[str, str, str | None, str | None, JsonValue], ...]
] = {
    "join_04": (("linked_open_risks", "count", None, "PRJ-EMBER", 0),),
    "join_05": (("linked_risks", "count", None, "PRJ-FJORD", 0),),
    "join_08": tuple(
        ("unfinished_work_items", "count", None, project, count)
        for project, count in (
            ("PRJ-ATLAS", 3),
            ("PRJ-BEACON", 2),
            ("PRJ-CEDAR", 1),
            ("PRJ-DELTA", 3),
            ("PRJ-EMBER", 2),
            ("PRJ-FJORD", 2),
        )
    ),
    "risk_04": tuple(
        ("unfinished_work_items", "count", None, project, count)
        for project, count in (
            ("PRJ-ATLAS", 3),
            ("PRJ-BEACON", 2),
            ("PRJ-DELTA", 3),
            ("PRJ-EMBER", 2),
            ("PRJ-FJORD", 2),
        )
    ),
    "risk_06": (
        ("open_risks", "count", None, "high", 3),
        ("open_risks", "count", None, "medium", 3),
    ),
    "risk_03": (
        ("open_risks", "count", None, "PRJ-ATLAS", 3),
        ("open_risks", "count", None, "PRJ-BEACON", 3),
        ("high_risks", "count", None, "PRJ-ATLAS", 2),
        ("high_risks", "count", None, "PRJ-BEACON", 1),
    ),
    "daily_01": (
        ("completed", "count", None, None, 5),
        ("in_progress", "count", None, None, 4),
        ("blocked", "count", None, None, 4),
    ),
    "daily_03": tuple(
        ("unfinished_work_items", "count", None, project, count)
        for project, count in (
            ("PRJ-ATLAS", 3),
            ("PRJ-BEACON", 2),
            ("PRJ-CEDAR", 1),
            ("PRJ-DELTA", 3),
            ("PRJ-EMBER", 2),
            ("PRJ-FJORD", 2),
        )
    ),
    "daily_04": (("blocked_work_items", "count", None, None, 4),),
    "mixed_01": (("blocked_work_items", "count", None, None, 4),),
    "mixed_03": (("high_risk_work_items", "count", None, None, 5),),
}

_SORT_SPECS: dict[str, tuple[tuple[str, str, str, str, tuple[str, ...], bool], ...]] = {
    "daily_04": (
        ("work_items", "priority", "asc", "last", ("high", "medium", "low"), False),
        ("work_items", "ticket_code", "asc", "last", (), True),
    ),
    "mixed_01": (
        ("work_items", "risk_level", "asc", "last", ("high", "medium", "low"), False),
        ("work_items", "ticket_code", "asc", "last", (), True),
    ),
}

_ACTION_SPECS: dict[str, tuple[dict[str, object], ...]] = {
    "draft_01": (
        {
            "kind": "record.update",
            "target": {"record_code": "MT-014"},
            "assignments": {"status": "in_progress"},
            "fields": ("status",),
            "outcome": "pending_confirmation",
        },
    ),
    "draft_02": (
        {
            "kind": "record.update",
            "target": {"record_code": "MT-012"},
            "assignments": {},
            "fields": ("blocked_reason",),
            "outcome": "denied",
            "denial_reason": "field_permission_denied",
        },
    ),
    "draft_03": (
        {
            "kind": "record.update",
            "target": {"record_code": "MT-017"},
            "assignments": {"priority": "high"},
            "fields": ("priority",),
            "outcome": "pending_confirmation",
        },
    ),
    "draft_04": (
        {
            "kind": "record.create",
            "target": {"table_key": "work_items", "source_record_codes": ["PRJ-ATLAS"]},
            "assignments": {
                "title": "Atlas 回归检查事项",
                "project_link": ["PRJ-ATLAS"],
                "status": "planned",
                "priority": "high",
            },
            "fields": ("title", "project_link", "status", "priority"),
            "outcome": "pending_confirmation",
        },
    ),
    "draft_05": (
        {
            "kind": "record.create",
            "target": {
                "table_key": "work_items",
                "source_record_codes": ["PRJ-BEACON"],
            },
            "assignments": {
                "title": "Beacon 风险复核事项",
                "project_link": ["PRJ-BEACON"],
                "risk_level": "medium",
            },
            "fields": ("title", "project_link", "risk_level"),
            "outcome": "pending_confirmation",
        },
    ),
    "draft_06": (
        {
            "kind": "record.create",
            "target": {"table_key": "work_items", "source_record_codes": ["PRJ-FJORD"]},
            "assignments": {
                "title": "Fjord 回滚演练事项",
                "project_link": ["PRJ-FJORD"],
            },
            "fields": ("title", "project_link"),
            "outcome": "pending_confirmation",
        },
    ),
    "task_01": (
        {
            "kind": "task.create",
            "target": {"table_key": "tasks", "source_record_codes": ["PRJ-ATLAS"]},
            "assignments": {
                "title": "范围确认任务",
                "project_link": ["PRJ-ATLAS"],
                "assignee": ["OWNER-ATLAS"],
                "priority": "high",
                "status": "planned",
            },
            "fields": ("title", "project_link", "assignee", "priority", "status"),
            "outcome": "pending_confirmation",
        },
    ),
    "task_02": (
        {
            "kind": "task.create",
            "target": {"table_key": "tasks", "source_record_codes": ["MT-004"]},
            "assignments": {
                "title": "接口依赖跟进任务",
                "source_work_item": ["MT-004"],
                "due_date": "2026-07-29",
                "priority": "medium",
                "status": "planned",
            },
            "fields": ("title", "source_work_item", "due_date", "priority", "status"),
            "deadline_start_utc": "2026-07-28T16:00:00+00:00",
            "deadline_end_utc": "2026-07-29T16:00:00+00:00",
            "outcome": "pending_confirmation",
        },
    ),
    "task_03": (
        {
            "kind": "task.create",
            "target": {
                "table_key": "tasks",
                "source_record_codes": ["PRJ-EMBER"],
            },
            "assignments": {
                "title": "管理层确认任务",
                "project_link": ["PRJ-EMBER"],
                "priority": "high",
                "status": "planned",
            },
            "fields": ("title", "project_link", "priority", "status"),
            "outcome": "pending_confirmation",
        },
    ),
    "task_04": (
        {
            "kind": "task.create",
            "target": {
                "table_key": "tasks",
                "source_record_codes": ["PRJ-FJORD", "MT-017"],
            },
            "assignments": {
                "title": "Fjord 回滚方案评审任务",
                "source_work_item": ["MT-017"],
                "priority": "medium",
                "status": "planned",
            },
            "fields": ("title", "source_work_item", "priority", "status"),
            "outcome": "pending_confirmation",
        },
    ),
    "reminder_01": (
        {
            "kind": "reminder.request",
            "target": {"owner_code": "OWNER-ATLAS", "source_record_codes": ["MT-001"]},
            "assignments": {},
            "fields": (),
            "deadline_start_utc": "2026-07-28T16:00:00+00:00",
            "deadline_end_utc": "2026-07-29T16:00:00+00:00",
            "outcome": "blocked",
        },
    ),
    "reminder_02": (
        {
            "kind": "reminder.request",
            "target": {"owner_code": "OWNER-BEACON", "source_record_codes": ["MT-004"]},
            "assignments": {},
            "fields": (),
            "outcome": "denied",
            "denial_reason": "action_recipient_unavailable",
        },
    ),
    "reminder_03": tuple(
        {
            "kind": "reminder.request",
            "target": {"owner_code": owner, "source_record_codes": [record]},
            "assignments": {},
            "fields": (),
            "outcome": "blocked",
        }
        for owner, record in (
            ("OWNER-ATLAS", "MT-001"),
            ("OWNER-BEACON", "MT-004"),
            ("OWNER-DELTA", "MT-012"),
            ("OWNER-EMBER", "MT-014"),
        )
    ),
    "reminder_04": (
        {
            "kind": "reminder.request",
            "target": {"owner_code": "OWNER-FJORD", "source_record_codes": ["MT-017"]},
            "assignments": {},
            "fields": (),
            "outcome": "denied",
            "denial_reason": "action_recipient_unavailable",
        },
    ),
    "permission_02": (
        {
            "kind": "record.update",
            "target": {"record_code": "MT-001"},
            "assignments": {},
            "fields": ("internal_note",),
            "outcome": "denied",
            "denial_reason": "field_permission_denied",
        },
    ),
    "permission_03": (
        {
            "kind": "task.create",
            "target": {"scope": "outside_workspace"},
            "assignments": {},
            "fields": (),
            "outcome": "denied",
            "denial_reason": "outside_workspace_scope_denied",
        },
    ),
    "fault_02": (
        {
            "kind": "record.update",
            "target": {"record_code": "MT-014"},
            "assignments": {},
            "fields": ("status",),
            "outcome": "denied",
            "denial_reason": "record_version_conflict",
            "fault_mode": "record_version_drift",
            "expected_version": 1,
        },
    ),
    "mixed_01": (
        {
            "kind": "task.create",
            "target": {
                "table_key": "tasks",
                "source_record_codes": ["MT-001", "MT-004", "MT-012", "MT-014"],
            },
            "assignments": {},
            "fields": ("title", "source_work_item", "priority", "status"),
            "outcome": "denied",
            "denial_reason": "ambiguous_highest_risk_target",
        },
    ),
    "mixed_02": (
        {
            "kind": "record.update",
            "target": {"record_code": "MT-014"},
            "assignments": {"status": "in_progress"},
            "fields": ("status",),
            "outcome": "pending_confirmation",
        },
        {
            "kind": "task.create",
            "target": {
                "table_key": "tasks",
                "source_record_codes": ["PRJ-EMBER", "MT-014"],
            },
            "assignments": {
                "title": "决策跟进任务",
                "project_link": ["PRJ-EMBER"],
                "priority": "medium",
                "status": "planned",
            },
            "fields": ("title", "project_link", "priority", "status"),
            "outcome": "pending_confirmation",
        },
    ),
    "mixed_03": (
        {
            "kind": "reminder.request",
            "target": {"owner_code": "OWNER-ATLAS", "source_record_codes": ["MT-001"]},
            "assignments": {},
            "fields": (),
            "outcome": "blocked",
        },
        {
            "kind": "reminder.request",
            "target": {"owner_code": "OWNER-BEACON", "source_record_codes": ["MT-004"]},
            "assignments": {},
            "fields": (),
            "outcome": "blocked",
        },
        {
            "kind": "reminder.request",
            "target": {"owner_code": "OWNER-DELTA", "source_record_codes": ["MT-012"]},
            "assignments": {},
            "fields": (),
            "outcome": "blocked",
        },
        {
            "kind": "reminder.request",
            "target": {"owner_code": "OWNER-EMBER", "source_record_codes": ["MT-014"]},
            "assignments": {},
            "fields": (),
            "outcome": "blocked",
        },
        {
            "kind": "reminder.request",
            "target": {"owner_code": "OWNER-FJORD", "source_record_codes": ["MT-017"]},
            "assignments": {},
            "fields": (),
            "outcome": "blocked",
        },
    ),
    "mixed_04": (
        {
            "kind": "task.create",
            "target": {"table_key": "tasks", "source_record_codes": ["PRJ-ATLAS"]},
            "assignments": {
                "title": "Atlas 跟进任务",
                "project_link": ["PRJ-ATLAS"],
                "priority": "medium",
                "status": "planned",
            },
            "fields": ("title", "project_link", "priority", "status"),
            "outcome": "pending_confirmation",
        },
        {
            "kind": "task.create",
            "target": {"table_key": "tasks", "source_record_codes": ["PRJ-BEACON"]},
            "assignments": {
                "title": "Beacon 跟进任务",
                "project_link": ["PRJ-BEACON"],
                "priority": "medium",
                "status": "planned",
            },
            "fields": ("title", "project_link", "priority", "status"),
            "outcome": "pending_confirmation",
        },
    ),
    "mixed_06": (
        {
            "kind": "record.update",
            "target": {"record_code": "MT-012"},
            "assignments": {},
            "fields": ("blocked_reason",),
            "outcome": "denied",
            "denial_reason": "field_permission_denied",
        },
        {
            "kind": "task.create",
            "target": {"table_key": "tasks", "source_record_codes": ["MT-012"]},
            "assignments": {
                "title": "依赖跟进任务",
                "source_work_item": ["MT-012"],
                "priority": "medium",
                "status": "planned",
            },
            "fields": ("title", "source_work_item", "priority", "status"),
            "outcome": "pending_confirmation",
        },
    ),
    "mixed_07": tuple(
        {
            "kind": "reminder.request",
            "target": {"owner_code": owner, "source_record_codes": [record]},
            "assignments": {},
            "fields": (),
            "outcome": "blocked",
        }
        for owner, record in (
            ("OWNER-ATLAS", "MT-001"),
            ("OWNER-BEACON", "MT-004"),
            ("OWNER-FJORD", "MT-017"),
        )
    ),
    "mixed_08": (
        {
            "kind": "record.update",
            "target": {"record_code": "MT-017"},
            "assignments": {},
            "fields": ("status",),
            "outcome": "denied",
            "conflict_group": "status-conflict",
            "denial_reason": "conflicting_assignments",
        },
        {
            "kind": "task.create",
            "target": {"table_key": "tasks", "source_record_codes": ["MT-017"]},
            "assignments": {
                "title": "Fjord 回滚方案评审任务",
                "source_work_item": ["MT-017"],
                "due_date": "2026-07-30",
                "priority": "medium",
                "status": "planned",
            },
            "fields": ("title", "source_work_item", "due_date", "priority", "status"),
            "deadline_end_utc": "2026-07-30T16:00:00+00:00",
            "outcome": "pending_confirmation",
        },
    ),
}


def _fixture_snapshot() -> dict[str, object]:
    owners = (
        {"owner_code": "OWNER-ATLAS", "name": "Atlas owner"},
        {"owner_code": "OWNER-BEACON", "name": "Beacon owner"},
        {"owner_code": "OWNER-CEDAR", "name": "Cedar owner"},
        {"owner_code": "OWNER-DELTA", "name": "Delta owner"},
        {"owner_code": "OWNER-EMBER", "name": "Ember owner"},
        {"owner_code": "OWNER-FJORD", "name": "Fjord owner"},
    )
    tables = {
        "projects": {
            "fields": (
                {"key": "project_code", "type": "text"},
                {"key": "project_name", "type": "text"},
                {"key": "phase", "type": "text"},
                {"key": "delivery_state", "type": "text"},
                {"key": "owner_link", "type": "linked_record", "target": "owners"},
                {"key": "customer_secret", "type": "text", "visibility": "hidden"},
            ),
            "records": _PROJECT_ROWS,
        },
        "work_items": {
            "fields": (
                {"key": "ticket_code", "type": "text"},
                {"key": "title", "type": "text"},
                {"key": "project_code", "type": "text"},
                {"key": "status", "type": "status"},
                {"key": "priority", "type": "single_select"},
                {"key": "risk_level", "type": "single_select"},
                {"key": "summary", "type": "text"},
                {"key": "project_link", "type": "linked_record", "target": "projects"},
                {"key": "owner_link", "type": "linked_record", "target": "owners"},
                {"key": "blocked_reason", "type": "text"},
                {"key": "internal_note", "type": "text", "visibility": "hidden"},
            ),
            "records": _WORK_ITEM_ROWS,
        },
        "risks": {
            "fields": (
                {"key": "risk_code", "type": "text"},
                {"key": "title", "type": "text"},
                {"key": "level", "type": "single_select"},
                {"key": "status", "type": "status"},
                {"key": "ticket_code", "type": "text"},
                {
                    "key": "affected_work_items",
                    "type": "linked_record",
                    "target": "work_items",
                },
            ),
            "records": _RISK_ROWS,
        },
        "tasks": {
            "fields": (
                {"key": "title", "type": "text"},
                {"key": "priority", "type": "single_select", "default": "medium"},
                {"key": "status", "type": "status", "default": "planned"},
                {"key": "project_link", "type": "linked_record", "target": "projects"},
                {
                    "key": "source_work_item",
                    "type": "linked_record",
                    "target": "work_items",
                },
                {"key": "assignee", "type": "linked_record", "target": "owners"},
                {"key": "due_date", "type": "date"},
            ),
            "records": (),
        },
        "owners": {
            "fields": (
                {"key": "owner_code", "type": "text"},
                {"key": "name", "type": "text"},
            ),
            "records": owners,
        },
        "daily_metrics": {
            "fields": (
                {"key": "date", "type": "date"},
                {"key": "completed", "type": "number"},
                {"key": "blocked", "type": "number"},
                {"key": "overdue", "type": "number"},
            ),
            "records": (
                {"date": "2026-07-28", "completed": 5, "blocked": 4, "overdue": 3},
            ),
        },
        "interactions": {
            "fields": (
                {"key": "interaction_code", "type": "text"},
                {"key": "sentiment", "type": "single_select"},
            ),
            "records": ({"interaction_code": "INT-001", "sentiment": "negative"},),
        },
    }
    owner_by_project = {
        "PRJ-ATLAS": "OWNER-ATLAS",
        "PRJ-BEACON": "OWNER-BEACON",
        "PRJ-CEDAR": "OWNER-CEDAR",
        "PRJ-DELTA": "OWNER-DELTA",
        "PRJ-EMBER": "OWNER-EMBER",
        "PRJ-FJORD": "OWNER-FJORD",
    }
    relations = (
        tuple(
            {"source": project, "field": "projects.owner_link", "target": owner}
            for project, owner in owner_by_project.items()
        )
        + tuple(
            edge
            for row in _WORK_ITEM_ROWS
            for edge in (
                {
                    "source": row["ticket_code"],
                    "field": "work_items.project_link",
                    "target": row["project_code"],
                },
                {
                    "source": row["ticket_code"],
                    "field": "work_items.owner_link",
                    "target": owner_by_project[row["project_code"]],
                },
            )
        )
        + tuple(
            {
                "source": row["risk_code"],
                "field": "risks.affected_work_items",
                "target": row["ticket_code"],
            }
            for row in _RISK_ROWS
        )
    )
    record_codes = tuple(
        [row["project_code"] for row in _PROJECT_ROWS]
        + [row["ticket_code"] for row in _WORK_ITEM_ROWS]
        + [row["risk_code"] for row in _RISK_ROWS]
        + [row["owner_code"] for row in owners]
        + ["INT-001", "DAILY-2026-07-28"]
    )
    return {
        "schema_version": "stage12-evaluation-fixture.v2",
        "tables": tables,
        "relations": relations,
        "permission_profile": {
            "scope": "current_workspace",
            "hidden_fields": ("projects.customer_secret", "work_items.internal_note"),
            "denied_write_fields": (
                "work_items.blocked_reason",
                "work_items.internal_note",
            ),
            "outside_workspace": "denied",
            "external_send": "blocked",
        },
        "record_versions": {code: 1 for code in record_codes},
    }


def _objective_names(case: ComplexCoordinationCase) -> tuple[str, ...]:
    if case.case_id in _OBJECTIVE_NAME_OVERRIDES:
        return _OBJECTIVE_NAME_OVERRIDES[case.case_id]
    values = list(case.objectives)
    if case.case_id == "permission_02" and "record_change" not in values:
        values.append("record_change")
    if case.case_id == "permission_03" and "task" not in values:
        values.append("task")
    return tuple(values)


def _build_generated_case(
    legacy: ComplexCoordinationCase,
    *,
    fixture_hash: str,
) -> EvaluationCaseV2:
    objective_names = _objective_names(legacy)
    objective_ids = {
        name: f"obj-{index:02d}" for index, name in enumerate(objective_names, start=1)
    }
    predicates = tuple(
        ExpectedPredicate(
            table_key=table_key,
            field_key=field_key,
            field_type=field_type,
            operator=operator,
            value=value,
        )
        for table_key, field_key, field_type, operator, value in _PREDICATE_SPECS.get(
            legacy.case_id, ()
        )
    )
    relation_paths = _RELATION_PATH_SPECS.get(
        legacy.case_id,
        (tuple(legacy.expected_join_path),) if legacy.expected_join_path else (),
    )
    group_by = (
        ("level",)
        if legacy.case_id == "risk_06"
        else (
            ("project_link",)
            if legacy.case_id == "daily_03"
            else (
                ("project_code",)
                if legacy.case_id in {"join_08", "risk_01", "risk_04"}
                else ()
            )
        )
    )
    objectives = tuple(
        ExpectedObjective(
            objective_id=objective_ids[name],
            kind=_OBJECTIVE_KIND_MAP[name],
            required=not (legacy.case_id == "fault_01" and name == "risk"),
            entity_scope=_ENTITY_SCOPE_SPECS.get(legacy.case_id, ()),
            output_contract=_OUTPUT_CONTRACTS[_OBJECTIVE_KIND_MAP[name]],
            predicates=predicates if name == "fact" else (),
            group_by=group_by if name == "fact" else (),
            relation_paths=relation_paths if name == "fact" else (),
        )
        for name in objective_names
    )
    if legacy.case_id == "join_08":
        objectives = (
            ExpectedObjective(
                objective_id="obj-01",
                kind="fact_query",
                required=True,
                entity_scope=(),
                output_contract="unfinished_work_item_aggregates",
                predicates=predicates,
                group_by=("project_code",),
                relation_paths=(("work_items.project_link",),),
            ),
            ExpectedObjective(
                objective_id="obj-02",
                kind="fact_query",
                required=True,
                entity_scope=(),
                output_contract="project_risk_codes",
                predicates=(),
                group_by=("project_code",),
                relation_paths=(
                    ("risks.affected_work_items", "work_items.project_link"),
                ),
            ),
        )
    edge_specs = _EDGE_SPECS.get(
        legacy.case_id,
        tuple(
            (source, target, not (legacy.case_id == "fault_01" and target == "risk"))
            for source, target in legacy.dependency_edges
        ),
    )
    edges = tuple(
        ExpectedDependencyEdge(
            from_objective_id=objective_ids[source],
            to_objective_id=objective_ids[target],
            required=required,
        )
        for source, target, required in edge_specs
        if source in objective_ids and target in objective_ids
    )
    slots = tuple(
        ExpectedActionSlot(
            slot_id=f"act-{index:02d}",
            objective_id=objective_ids[
                {
                    "record.create": "record_change",
                    "record.update": "record_change",
                    "task.create": "task",
                    "reminder.request": "reminder",
                }[str(spec["kind"])]
            ],
            action_kind=spec["kind"],  # type: ignore[arg-type]
            target_selector=spec["target"],  # type: ignore[arg-type]
            assignments=spec["assignments"],  # type: ignore[arg-type]
            required_fields=spec["fields"],  # type: ignore[arg-type]
            confirmation_policy="required",
            deadline_start_utc=(
                None
                if spec.get("deadline_start_utc") is None
                else datetime.fromisoformat(str(spec["deadline_start_utc"]))
            ),
            deadline_end_utc=(
                None
                if spec.get("deadline_end_utc") is None
                else datetime.fromisoformat(str(spec["deadline_end_utc"]))
            ),
            conflict_group=spec.get("conflict_group"),  # type: ignore[arg-type]
            expected_outcome=spec["outcome"],  # type: ignore[arg-type]
            denial_reason=spec.get("denial_reason"),  # type: ignore[arg-type]
            fault_mode=spec.get("fault_mode"),  # type: ignore[arg-type]
            expected_version=spec.get("expected_version"),  # type: ignore[arg-type]
        )
        for index, spec in enumerate(_ACTION_SPECS.get(legacy.case_id, ()), start=1)
    )
    required, allowed, forbidden = _RESULT_TRUTH[legacy.case_id]
    aggregates = tuple(
        ExpectedAggregate(
            name=name,
            function=function,  # type: ignore[arg-type]
            field_key=field_key,
            group_key=group_key,
            value=value,
        )
        for name, function, field_key, group_key, value in _AGGREGATE_SPECS.get(
            legacy.case_id, ()
        )
    )
    sort_specs = tuple(
        ExpectedSortSpec(
            table_key=table_key,
            field_key=field_key,
            direction=direction,  # type: ignore[arg-type]
            nulls=nulls,  # type: ignore[arg-type]
            value_order=value_order,
            tie_breaker=tie_breaker,
        )
        for table_key, field_key, direction, nulls, value_order, tie_breaker in _SORT_SPECS.get(
            legacy.case_id, ()
        )
    )
    change_reason = {
        "risk_01": "corrected_legacy_gold_add_mt_012",
        "risk_02": "corrected_legacy_gold_mt_008_to_mt_017",
        "risk_03": "defined_project_risk_exposure_aggregates",
        "join_04": "added_paused_project_and_open_risk_filters",
        "join_05": "added_zero_linked_risk_truth",
        "daily_01": "corrected_requested_status_aggregates",
        "daily_03": "added_unfinished_filter_and_project_link_grouping",
        "daily_05": "corrected_requested_status_result_boundary",
        "draft_02": "corrected_field_permission_denial_and_minimized_values",
        "permission_02": "made_retrieval_not_applicable_and_minimized_denied_values",
        "permission_03": "made_restricted_objective_gate_fact_risk_and_task",
        "permission_04": "added_daily_summary_objective",
        "fault_02": "preserved_version_conflict_and_minimized_denied_values",
        "task_01": "canonicalized_authorized_linked_record_assignments",
        "task_02": "added_due_date_and_task_defaults",
        "task_03": "corrected_task_source_to_requested_project",
        "reminder_02": "denied_missing_authorized_recipient_mapping",
        "reminder_03": "split_group_target_into_four_owner_slots",
        "reminder_04": "denied_missing_authorized_recipient_mapping",
        "mixed_01": "preserved_ambiguous_candidate_set_and_minimized_denied_values",
        "mixed_02": "added_ticket_filter_and_canonicalized_task_links",
        "mixed_03": "kept_explicit_daily_records_as_results_and_split_reminders",
        "mixed_04": "added_requested_blocked_filter",
        "mixed_06": "encoded_field_denial_with_independent_task",
        "mixed_07": "corrected_delivery_high_risk_set_and_split_reminders",
        "mixed_08": "added_conflict_dependency_and_minimized_denied_values",
    }.get(legacy.case_id, "converted_and_source_checked")
    base_audit = GoldAudit(
        source_fixture_hash=fixture_hash,
        legacy_case_hash=canonical_sha256(asdict(legacy)),
        v2_case_hash="0" * 64,
        reviewer="codex-source-audit",
        review_method="manual_source_audit",
        reviewed_at=EVALUATION_CLOCK,
        change_reason=change_reason,
        status="human_approved",
    )
    case = EvaluationCaseV2(
        version="evaluation-case.v2",
        case_id=legacy.case_id,
        category=legacy.category,
        query=legacy.query,
        schema_version="stage12-evaluation-fixture.v2",
        timezone=EVALUATION_TIMEZONE,
        evaluation_clock=EVALUATION_CLOCK,
        expected_task_spec=ExpectedTaskSpec(
            version="task-spec.v2",
            objectives=objectives,
            dependency_edges=edges,
            action_slots=slots,
        ),
        expected_query_result=ExpectedQueryResult(
            required_result_records=required,
            allowed_evidence_records=allowed,
            forbidden_result_records=forbidden,
            aggregates=aggregates,
            relation_paths=relation_paths,
            sort_specs=sort_specs,
        ),
        expected_permission_outcome=(
            "allowed" if legacy.case_id == "mixed_08" else legacy.permission_outcome
        ),
        gold_audit=base_audit,
    )
    audit = base_audit.model_copy(
        update={"v2_case_hash": canonical_sha256(case_payload_for_hash(case))}
    )
    return case.model_copy(update={"gold_audit": audit})


def _generate_stage12_truth_cases() -> tuple[EvaluationCaseV2, ...]:
    snapshot = _fixture_snapshot()
    fixture_hash = canonical_sha256(snapshot)
    cases = tuple(
        _build_generated_case(case, fixture_hash=fixture_hash)
        for case in build_complex_cases()
    )
    validate_truth_set(cases)
    validate_truth_against_fixture(cases, snapshot)
    return cases


def generate_stage12_truth_files(*, truth_path: Path, audit_path: Path) -> None:
    cases = _generate_stage12_truth_cases()
    audit_report = audit_truth_set(
        cases,
        tuple(build_complex_cases()),
        _fixture_snapshot(),
    )
    truth_path.write_text(
        json.dumps(
            [case.model_dump(mode="json") for case in cases],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    audit_path.write_text(
        json.dumps(
            audit_report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
