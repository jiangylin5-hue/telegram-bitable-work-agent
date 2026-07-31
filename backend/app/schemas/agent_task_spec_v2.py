"""Strict Stage12-B planning contracts.

These contracts describe a plan.  They neither authorize nor execute a query
or action, and they intentionally contain no raw database or Provider access.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

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


ObjectiveKindV2 = Literal[
    "fact_query",
    "risk_analysis",
    "daily_summary",
    "record_change",
    "task_creation",
    "reminder_request",
    "restricted_request",
    "conflict_resolution",
]
ActionKindV1 = Literal[
    "record.create",
    "record.update",
    "task.create",
    "reminder.request",
]
PlanningOutcome = Literal["planned", "denied", "clarification_required"]
ActionExpansionPolicy = Literal["none", "each_result", "each_distinct_owner"]
FieldTypeV2 = Literal[
    "text",
    "number",
    "date",
    "datetime",
    "status",
    "single_select",
    "multi_select",
    "checkbox",
    "linked_record",
    "user",
    "url",
    "email",
    "phone",
    "json",
    "lookup",
]
PredicateOperatorV2 = Literal[
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
    "status": frozenset({"eq", "ne", "in", "not_in"}),
    "single_select": frozenset({"eq", "ne", "in", "not_in"}),
    "multi_select": frozenset({"contains_any", "contains_all", "is_empty"}),
    "checkbox": frozenset({"is_true", "is_false"}),
    "linked_record": frozenset({"contains_record", "is_empty", "is_not_empty"}),
    "user": frozenset({"eq", "ne", "in", "not_in", "is_empty", "is_not_empty"}),
    "url": frozenset({"eq", "contains", "is_empty", "is_not_empty"}),
    "email": frozenset({"eq", "contains", "is_empty", "is_not_empty"}),
    "phone": frozenset({"eq", "contains", "is_empty", "is_not_empty"}),
    "json": frozenset({"eq", "contains", "is_empty", "is_not_empty"}),
    "lookup": frozenset({"eq", "ne", "contains", "is_empty", "is_not_empty"}),
}

NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SourceSpan(_StrictFrozenModel):
    start: StrictInt = Field(ge=0)
    end: StrictInt = Field(ge=1)
    text: NonEmptyStr

    @model_validator(mode="after")
    def validate_range(self) -> "SourceSpan":
        if self.end <= self.start or len(self.text) != self.end - self.start:
            raise ValueError("task_spec_source_span_invalid")
        return self


class AuthorizedFieldSpec(_StrictFrozenModel):
    field_id: UUID
    table_id: UUID
    key: NonEmptyStr
    name: NonEmptyStr
    field_type: FieldTypeV2
    aliases: tuple[NonEmptyStr, ...]
    choices: tuple[NonEmptyStr, ...]
    writable: StrictBool
    default_value: JsonValue = None
    linked_target_table_id: UUID | None = None

    @model_validator(mode="after")
    def validate_names(self) -> "AuthorizedFieldSpec":
        if len(set(self.aliases)) != len(self.aliases):
            raise ValueError("authorized_schema_field_alias_duplicate")
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("authorized_schema_field_choice_duplicate")
        if (
            self.field_type not in {"status", "single_select", "multi_select"}
            and self.choices
        ):
            raise ValueError("authorized_schema_field_choices_invalid")
        if self.field_type != "linked_record" and self.linked_target_table_id is not None:
            raise ValueError("authorized_schema_link_target_invalid")
        return self


class AuthorizedTableSpec(_StrictFrozenModel):
    table_id: UUID
    base_id: UUID
    key: NonEmptyStr
    name: NonEmptyStr
    aliases: tuple[NonEmptyStr, ...]
    fields: tuple[AuthorizedFieldSpec, ...]
    identity_field_id: UUID | None = None
    label_field_id: UUID | None = None
    alias_field_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def validate_fields(self) -> "AuthorizedTableSpec":
        field_ids = tuple(item.field_id for item in self.fields)
        field_keys = tuple(item.key for item in self.fields)
        if len(set(field_ids)) != len(field_ids) or len(set(field_keys)) != len(
            field_keys
        ):
            raise ValueError("authorized_schema_field_duplicate")
        if any(item.table_id != self.table_id for item in self.fields):
            raise ValueError("authorized_schema_field_table_mismatch")
        if len(set(self.aliases)) != len(self.aliases):
            raise ValueError("authorized_schema_table_alias_duplicate")
        if self.identity_field_id is not None and self.identity_field_id not in set(
            field_ids
        ):
            raise ValueError("authorized_schema_identity_field_unavailable")
        if self.label_field_id is not None and self.label_field_id not in set(field_ids):
            raise ValueError("authorized_schema_label_field_unavailable")
        if len(set(self.alias_field_ids)) != len(self.alias_field_ids) or not set(
            self.alias_field_ids
        ).issubset(field_ids):
            raise ValueError("authorized_schema_alias_field_unavailable")
        return self


class AuthorizedEntitySpec(_StrictFrozenModel):
    entity_id: UUID
    table_id: UUID
    code: NonEmptyStr
    label: NonEmptyStr
    aliases: tuple[NonEmptyStr, ...]


class AuthorizedSchemaSnapshot(_StrictFrozenModel):
    version: Literal["authorized-schema-snapshot.v1"]
    workspace_id: UUID
    employee_id: UUID
    scope_hash: Sha256Hex
    tables: tuple[AuthorizedTableSpec, ...]
    field_policy_version: Literal["stage12-field-policy.v2"] | None = None
    field_policy_hash: Sha256Hex | None = None
    schema_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_snapshot(self) -> "AuthorizedSchemaSnapshot":
        table_ids = tuple(item.table_id for item in self.tables)
        table_keys = tuple(item.key for item in self.tables)
        if len(set(table_ids)) != len(table_ids) or len(set(table_keys)) != len(
            table_keys
        ):
            raise ValueError("authorized_schema_table_duplicate")
        if (self.field_policy_version is None) != (self.field_policy_hash is None):
            raise ValueError("authorized_schema_field_policy_proof_invalid")
        expected = authorized_schema_sha256(
            version=self.version,
            workspace_id=self.workspace_id,
            employee_id=self.employee_id,
            scope_hash=self.scope_hash,
            tables=self.tables,
            field_policy_version=self.field_policy_version,
            field_policy_hash=self.field_policy_hash,
        )
        if self.schema_hash != expected:
            raise ValueError("authorized_schema_hash_mismatch")
        return self


class BoundPredicate(_StrictFrozenModel):
    table_id: UUID
    field_id: UUID
    field_key: NonEmptyStr
    field_type: FieldTypeV2
    operator: PredicateOperatorV2
    value: JsonValue
    source_span: SourceSpan

    @model_validator(mode="after")
    def validate_operator(self) -> "BoundPredicate":
        if self.operator not in _OPERATORS_BY_FIELD_TYPE[self.field_type]:
            raise ValueError("task_spec_predicate_operator_invalid")
        return self


class QueryPredicateLeafIntentV1(_StrictFrozenModel):
    kind: Literal["leaf"] = "leaf"
    predicate: BoundPredicate


class QueryPredicateGroupIntentV1(_StrictFrozenModel):
    kind: Literal["group"] = "group"
    operator: Literal["and", "or"]
    children: tuple["QueryPredicateExpressionV1", ...] = Field(
        min_length=1,
        max_length=16,
    )


QueryPredicateExpressionV1: TypeAlias = (
    QueryPredicateLeafIntentV1 | QueryPredicateGroupIntentV1
)


class QueryHavingIntentV1(_StrictFrozenModel):
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte"]
    value: StrictInt | StrictFloat


class QueryAggregationIntentV1(_StrictFrozenModel):
    aggregate_id: NonEmptyStr
    output_key: NonEmptyStr
    function: Literal[
        "count",
        "count_non_null",
        "count_distinct",
        "sum",
        "average",
        "minimum",
        "maximum",
    ]
    table_id: UUID
    field_id: UUID | None
    filter_expression: QueryPredicateExpressionV1 | None
    group_by_field_ids: tuple[UUID, ...]
    having: QueryHavingIntentV1 | None

    @model_validator(mode="after")
    def validate_aggregate(self) -> "QueryAggregationIntentV1":
        if self.function == "count" and self.field_id is not None:
            raise ValueError("task_spec_count_field_invalid")
        if self.function != "count" and self.field_id is None:
            raise ValueError("task_spec_aggregate_field_required")
        if len(set(self.group_by_field_ids)) != len(self.group_by_field_ids):
            raise ValueError("task_spec_query_intent_duplicate")
        if self.filter_expression is not None:
            _validate_query_predicate_expression(self.filter_expression)
        return self


class QuerySortIntentV1(_StrictFrozenModel):
    sort_id: NonEmptyStr
    table_id: UUID | None
    field_id: UUID | None
    aggregate_id: NonEmptyStr | None
    mode: Literal["natural", "field_order"]
    direction: Literal["asc", "desc"]
    nulls: Literal["first", "last"]

    @model_validator(mode="after")
    def validate_target(self) -> "QuerySortIntentV1":
        field_target = self.table_id is not None and self.field_id is not None
        aggregate_target = self.aggregate_id is not None
        if (
            field_target == aggregate_target
            or (self.table_id is None) != (self.field_id is None)
            or (aggregate_target and self.mode != "natural")
        ):
            raise ValueError("task_spec_sort_target_invalid")
        return self


class QueryJoinIntentV1(_StrictFrozenModel):
    join_intent_id: NonEmptyStr
    target_table_id: UUID
    purpose: Literal["project", "filter", "exists", "aggregate"]
    requirement: Literal["required", "optional"]

    @model_validator(mode="after")
    def validate_semantics(self) -> "QueryJoinIntentV1":
        if self.purpose == "exists" and self.requirement != "required":
            raise ValueError("task_spec_join_exists_must_be_required")
        return self


class QueryExecutionIntentV1(_StrictFrozenModel):
    version: Literal["query-execution-intent.v1"] = "query-execution-intent.v1"
    projection_field_ids: tuple[UUID, ...]
    predicate_expression: QueryPredicateExpressionV1 | None
    aggregations: tuple[QueryAggregationIntentV1, ...]
    sorts: tuple[QuerySortIntentV1, ...]
    join_intents: tuple[QueryJoinIntentV1, ...] = ()
    limit: StrictInt | None = Field(default=None, ge=1, le=5000)

    @model_validator(mode="after")
    def validate_execution(self) -> "QueryExecutionIntentV1":
        if len(set(self.projection_field_ids)) != len(self.projection_field_ids):
            raise ValueError("task_spec_query_intent_duplicate")
        aggregate_ids = tuple(item.aggregate_id for item in self.aggregations)
        output_keys = tuple(item.output_key for item in self.aggregations)
        sort_ids = tuple(item.sort_id for item in self.sorts)
        join_ids = tuple(item.join_intent_id for item in self.join_intents)
        join_targets = tuple(item.target_table_id for item in self.join_intents)
        if (
            len(set(aggregate_ids)) != len(aggregate_ids)
            or len(set(output_keys)) != len(output_keys)
            or len(set(sort_ids)) != len(sort_ids)
            or len(set(join_ids)) != len(join_ids)
            or len(set(join_targets)) != len(join_targets)
        ):
            raise ValueError("task_spec_query_operator_duplicate")
        known_aggregate_ids = set(aggregate_ids)
        if any(
            item.aggregate_id is not None
            and item.aggregate_id not in known_aggregate_ids
            for item in self.sorts
        ):
            raise ValueError("task_spec_sort_aggregate_unknown")
        if self.predicate_expression is not None:
            _validate_query_predicate_expression(self.predicate_expression)
        return self


class QueryIntentSpec(_StrictFrozenModel):
    query_intent_id: NonEmptyStr
    root_table_id: UUID | None
    entity_codes: tuple[NonEmptyStr, ...]
    predicates: tuple[BoundPredicate, ...]
    aggregation_kinds: tuple[
        Literal[
            "count",
            "count_non_null",
            "count_distinct",
            "sum",
            "average",
            "minimum",
            "maximum",
        ],
        ...,
    ]
    group_by_field_ids: tuple[UUID, ...]
    sort_field_ids: tuple[UUID, ...]
    limit: StrictInt | None = Field(default=None, ge=1, le=5000)
    execution_spec: QueryExecutionIntentV1 | None = None

    @model_validator(mode="after")
    def validate_collections(self) -> "QueryIntentSpec":
        values = (
            self.entity_codes,
            self.group_by_field_ids,
            self.sort_field_ids,
        )
        if any(len(set(items)) != len(items) for items in values):
            raise ValueError("task_spec_query_intent_duplicate")
        if self.execution_spec is not None:
            execution = self.execution_spec
            expected_predicates = (
                ()
                if execution.predicate_expression is None
                else tuple(_query_predicate_leaves(execution.predicate_expression))
            )
            expected_aggregations = tuple(
                dict.fromkeys(item.function for item in execution.aggregations)
            )
            expected_groups = tuple(
                dict.fromkeys(
                    field_id
                    for aggregate in execution.aggregations
                    for field_id in aggregate.group_by_field_ids
                )
            )
            expected_sort_fields = tuple(
                item.field_id for item in execution.sorts if item.field_id is not None
            )
            if (
                self.predicates != expected_predicates
                or self.aggregation_kinds != expected_aggregations
                or self.group_by_field_ids != expected_groups
                or self.sort_field_ids != expected_sort_fields
                or self.limit != execution.limit
            ):
                raise ValueError("task_spec_execution_summary_mismatch")
        return self


class TaskObjectiveV2(_StrictFrozenModel):
    objective_id: NonEmptyStr
    kind: ObjectiveKindV2
    required: StrictBool
    entity_codes: tuple[NonEmptyStr, ...]
    query_spec_ref: StrictStr | None
    output_contract: NonEmptyStr
    planning_outcome: PlanningOutcome
    denial_reason: StrictStr | None
    source_spans: tuple[SourceSpan, ...]

    @model_validator(mode="after")
    def validate_outcome(self) -> "TaskObjectiveV2":
        if self.planning_outcome == "planned" and self.denial_reason is not None:
            raise ValueError("task_spec_objective_denial_invalid")
        if self.planning_outcome != "planned" and not self.denial_reason:
            raise ValueError("task_spec_objective_denial_required")
        return self


class DependencyEdgeV2(_StrictFrozenModel):
    from_objective_id: NonEmptyStr
    to_objective_id: NonEmptyStr
    required: StrictBool


class ActionTargetSelector(_StrictFrozenModel):
    table_id: UUID | None
    record_codes: tuple[NonEmptyStr, ...]
    source_entity_codes: tuple[NonEmptyStr, ...]
    query_spec_ref: NonEmptyStr | None = None
    expansion_policy: ActionExpansionPolicy = "none"
    resolution_status: Literal[
        "resolved",
        "deferred_query_result",
        "unresolved_authorized_lookup_required",
        "ambiguous",
        "denied",
    ]

    @model_validator(mode="after")
    def validate_target(self) -> "ActionTargetSelector":
        if (
            not self.record_codes
            and not self.source_entity_codes
            and self.table_id is None
            and self.resolution_status == "resolved"
        ):
            raise ValueError("action_slot_target_empty")
        if len(set(self.record_codes)) != len(self.record_codes):
            raise ValueError("action_slot_target_duplicate")
        if len(set(self.source_entity_codes)) != len(self.source_entity_codes):
            raise ValueError("action_slot_target_duplicate")
        if self.resolution_status == "deferred_query_result":
            if self.record_codes or self.source_entity_codes:
                raise ValueError("action_slot_static_target_expansion_invalid")
            if self.query_spec_ref is None:
                raise ValueError("action_slot_deferred_query_ref_required")
            if self.expansion_policy == "none":
                raise ValueError("action_slot_deferred_expansion_policy_required")
        elif self.query_spec_ref is not None or self.expansion_policy != "none":
            raise ValueError("action_slot_static_target_expansion_invalid")
        return self


class ActionAssignment(_StrictFrozenModel):
    field_id: UUID | None
    field_key: NonEmptyStr
    value: JsonValue
    source_span: SourceSpan


class ActionSlotV1(_StrictFrozenModel):
    slot_id: NonEmptyStr
    objective_id: NonEmptyStr
    action_kind: ActionKindV1
    target: ActionTargetSelector
    assignments: tuple[ActionAssignment, ...]
    required_field_keys: tuple[NonEmptyStr, ...]
    confirmation_policy: Literal["required"]
    deadline_start_utc: datetime | None
    deadline_end_utc: datetime | None
    conflict_group_id: StrictStr | None
    planning_outcome: PlanningOutcome
    denial_reason: StrictStr | None

    @model_validator(mode="after")
    def validate_slot(self) -> "ActionSlotV1":
        assignment_keys = tuple(item.field_key for item in self.assignments)
        if len(set(assignment_keys)) != len(assignment_keys):
            raise ValueError("action_slot_assignment_duplicate")
        if len(set(self.required_field_keys)) != len(self.required_field_keys):
            raise ValueError("action_slot_required_field_duplicate")
        for boundary in (self.deadline_start_utc, self.deadline_end_utc):
            if boundary is not None and (
                boundary.tzinfo is None or boundary.utcoffset() is None
            ):
                raise ValueError("action_slot_deadline_timezone_required")
            if boundary is not None and boundary.utcoffset().total_seconds() != 0:
                raise ValueError("action_slot_deadline_utc_required")
        if (
            self.deadline_start_utc is not None
            and self.deadline_end_utc is not None
            and self.deadline_start_utc >= self.deadline_end_utc
        ):
            raise ValueError("action_slot_deadline_range_invalid")
        if self.planning_outcome == "planned" and self.denial_reason is not None:
            raise ValueError("action_slot_denial_invalid")
        if self.planning_outcome != "planned" and not self.denial_reason:
            raise ValueError("action_slot_denial_required")
        if (
            self.planning_outcome == "planned"
            and self.target.resolution_status
            not in {"resolved", "deferred_query_result"}
        ):
            raise ValueError("action_slot_target_resolution_required")
        return self


class ConflictAssignment(_StrictFrozenModel):
    target_key: NonEmptyStr
    field_key: NonEmptyStr
    values: tuple[JsonValue, ...] = Field(min_length=2)
    source_spans: tuple[SourceSpan, ...] = Field(min_length=2)


class ConflictGroupV1(_StrictFrozenModel):
    conflict_group_id: NonEmptyStr
    slot_ids: tuple[NonEmptyStr, ...]
    assignments: tuple[ConflictAssignment, ...]
    resolution: Literal["deny_conflicting_slot"]


class TaskOutputSpec(_StrictFrozenModel):
    language: Literal["zh-Hans"]
    format: Literal["conversational", "structured"]
    include_evidence: StrictBool


class PlannerCostEstimate(_StrictFrozenModel):
    lexical_token_count: StrictInt = Field(ge=0, le=600)
    bound_field_count: StrictInt = Field(ge=0)
    objective_count: StrictInt = Field(ge=0, le=8)
    action_slot_count: StrictInt = Field(ge=0, le=8)
    ambiguity_count: StrictInt = Field(ge=0)
    planned_provider_calls: StrictInt = Field(ge=0, le=4)


class PlannerRequestV2(_StrictFrozenModel):
    query: NonEmptyStr = Field(max_length=600)
    authorized_schema: AuthorizedSchemaSnapshot
    authorized_entities: tuple[AuthorizedEntitySpec, ...]
    clock: datetime
    timezone_name: NonEmptyStr
    allowed_action_kinds: tuple[ActionKindV1, ...]

    @model_validator(mode="after")
    def validate_request(self) -> "PlannerRequestV2":
        if self.query != self.query.strip() or "\x00" in self.query:
            raise ValueError("task_planner_query_invalid")
        if self.clock.tzinfo is None or self.clock.utcoffset() is None:
            raise ValueError("task_planner_clock_timezone_required")
        if len(set(self.allowed_action_kinds)) != len(self.allowed_action_kinds):
            raise ValueError("task_planner_action_kind_duplicate")
        if any(
            item.table_id
            not in {table.table_id for table in self.authorized_schema.tables}
            for item in self.authorized_entities
        ):
            raise ValueError("task_planner_entity_scope_invalid")
        return self


class TaskSpecV2(_StrictFrozenModel):
    version: Literal["task-spec.v2"]
    authorized_schema_hash: Sha256Hex
    query_intents: tuple[QueryIntentSpec, ...]
    objectives: tuple[TaskObjectiveV2, ...]
    dependency_edges: tuple[DependencyEdgeV2, ...]
    action_slots: tuple[ActionSlotV1, ...]
    conflict_groups: tuple[ConflictGroupV1, ...]
    output: TaskOutputSpec
    cost: PlannerCostEstimate
    provider_call_count: StrictInt = Field(ge=0, le=4)

    @model_validator(mode="after")
    def validate_plan(self) -> "TaskSpecV2":
        if len(self.objectives) > 8:
            raise ValueError("task_spec_objective_limit")
        if len(self.action_slots) > 8:
            raise ValueError("task_spec_action_slot_limit")
        if self.provider_call_count > 4:
            raise ValueError("task_spec_provider_call_limit")
        objective_ids = tuple(item.objective_id for item in self.objectives)
        if len(set(objective_ids)) != len(objective_ids):
            raise ValueError("task_spec_objective_duplicate")
        query_ids = tuple(item.query_intent_id for item in self.query_intents)
        if len(set(query_ids)) != len(query_ids):
            raise ValueError("task_spec_query_intent_duplicate")
        slot_ids = tuple(item.slot_id for item in self.action_slots)
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError("task_spec_action_slot_duplicate")
        conflict_ids = tuple(item.conflict_group_id for item in self.conflict_groups)
        if len(set(conflict_ids)) != len(conflict_ids):
            raise ValueError("task_spec_conflict_group_duplicate")
        known_objectives = set(objective_ids)
        if any(
            edge.from_objective_id not in known_objectives
            or edge.to_objective_id not in known_objectives
            or edge.from_objective_id == edge.to_objective_id
            for edge in self.dependency_edges
        ):
            raise ValueError("task_spec_dependency_reference_invalid")
        if _has_dependency_cycle(objective_ids, self.dependency_edges):
            raise ValueError("task_spec_dependency_cycle")
        known_query_refs = {f"query-intent:{value}" for value in query_ids}
        if any(
            objective.query_spec_ref is not None
            and objective.query_spec_ref not in known_query_refs
            for objective in self.objectives
        ):
            raise ValueError("task_spec_query_reference_invalid")
        if any(slot.objective_id not in known_objectives for slot in self.action_slots):
            raise ValueError("task_spec_action_objective_reference_invalid")
        if any(
            slot.target.query_spec_ref is not None
            and slot.target.query_spec_ref not in known_query_refs
            for slot in self.action_slots
        ):
            raise ValueError("task_spec_action_query_reference_invalid")
        known_slots = set(slot_ids)
        if any(
            not group.slot_ids
            or any(slot_id not in known_slots for slot_id in group.slot_ids)
            for group in self.conflict_groups
        ):
            raise ValueError("task_spec_conflict_slot_reference_invalid")
        known_conflicts = set(conflict_ids)
        if any(
            slot.conflict_group_id is not None
            and slot.conflict_group_id not in known_conflicts
            for slot in self.action_slots
        ):
            raise ValueError("task_spec_action_conflict_reference_invalid")
        if self.provider_call_count != self.cost.planned_provider_calls:
            raise ValueError("task_spec_provider_cost_mismatch")
        if self.cost.objective_count != len(self.objectives):
            raise ValueError("task_spec_objective_cost_mismatch")
        if self.cost.action_slot_count != len(self.action_slots):
            raise ValueError("task_spec_action_cost_mismatch")
        return self


class TaskSpecArtifact(_StrictFrozenModel):
    version: Literal["task-spec-artifact.v1"]
    task_spec: TaskSpecV2
    content_hash: Sha256Hex
    storage_ref: NonEmptyStr

    @model_validator(mode="after")
    def validate_artifact(self) -> "TaskSpecArtifact":
        expected = task_spec_sha256(self.task_spec)
        if self.content_hash != expected:
            raise ValueError("task_spec_artifact_hash_mismatch")
        if self.storage_ref != f"task-spec:sha256:{expected}":
            raise ValueError("task_spec_artifact_ref_mismatch")
        return self


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def authorized_schema_sha256(
    *,
    version: str,
    workspace_id: UUID,
    employee_id: UUID,
    scope_hash: str,
    tables: tuple[AuthorizedTableSpec, ...],
    field_policy_version: str | None = None,
    field_policy_hash: str | None = None,
) -> str:
    payload = {
        "version": version,
        "workspace_id": str(workspace_id),
        "employee_id": str(employee_id),
        "scope_hash": scope_hash,
        "tables": [item.model_dump(mode="json") for item in tables],
    }
    if field_policy_version is not None or field_policy_hash is not None:
        payload["field_policy_version"] = field_policy_version
        payload["field_policy_hash"] = field_policy_hash
    return _canonical_sha256(payload)


def canonical_task_spec_payload(spec: TaskSpecV2) -> bytes:
    return json.dumps(
        spec.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def task_spec_sha256(spec: TaskSpecV2) -> str:
    return sha256(canonical_task_spec_payload(spec)).hexdigest()


def _query_predicate_leaves(
    expression: QueryPredicateExpressionV1,
) -> tuple[BoundPredicate, ...]:
    if isinstance(expression, QueryPredicateLeafIntentV1):
        return (expression.predicate,)
    return tuple(
        predicate
        for child in expression.children
        for predicate in _query_predicate_leaves(child)
    )


def _validate_query_predicate_expression(
    expression: QueryPredicateExpressionV1,
) -> None:
    node_count = [0]

    def visit(node: QueryPredicateExpressionV1, depth: int) -> None:
        if depth > 4:
            raise ValueError("task_spec_predicate_depth_exceeded")
        node_count[0] += 1
        if node_count[0] > 64:
            raise ValueError("task_spec_predicate_node_limit")
        if isinstance(node, QueryPredicateGroupIntentV1):
            for child in node.children:
                visit(child, depth + 1)

    visit(expression, 1)


def _has_dependency_cycle(
    objective_ids: tuple[str, ...],
    edges: tuple[DependencyEdgeV2, ...],
) -> bool:
    children: dict[str, list[str]] = {item: [] for item in objective_ids}
    indegree = {item: 0 for item in objective_ids}
    for edge in edges:
        children[edge.from_objective_id].append(edge.to_objective_id)
        indegree[edge.to_objective_id] += 1
    ready = [item for item, count in indegree.items() if count == 0]
    visited = 0
    while ready:
        current = ready.pop()
        visited += 1
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    return visited != len(objective_ids)


QueryPredicateGroupIntentV1.model_rebuild()
QueryAggregationIntentV1.model_rebuild()
QueryExecutionIntentV1.model_rebuild()


__all__ = [
    "ActionAssignment",
    "ActionExpansionPolicy",
    "ActionKindV1",
    "ActionSlotV1",
    "ActionTargetSelector",
    "AuthorizedEntitySpec",
    "AuthorizedFieldSpec",
    "AuthorizedSchemaSnapshot",
    "AuthorizedTableSpec",
    "BoundPredicate",
    "ConflictAssignment",
    "ConflictGroupV1",
    "DependencyEdgeV2",
    "FieldTypeV2",
    "ObjectiveKindV2",
    "PlannerCostEstimate",
    "PlannerRequestV2",
    "PlanningOutcome",
    "PredicateOperatorV2",
    "QueryIntentSpec",
    "QueryAggregationIntentV1",
    "QueryExecutionIntentV1",
    "QueryHavingIntentV1",
    "QueryPredicateExpressionV1",
    "QueryPredicateGroupIntentV1",
    "QueryPredicateLeafIntentV1",
    "QuerySortIntentV1",
    "SourceSpan",
    "TaskObjectiveV2",
    "TaskOutputSpec",
    "TaskSpecArtifact",
    "TaskSpecV2",
    "authorized_schema_sha256",
    "canonical_task_spec_payload",
    "task_spec_sha256",
]
