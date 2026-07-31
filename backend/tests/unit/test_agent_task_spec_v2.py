from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.agent_task_spec_v2 import (
    ActionAssignment,
    ActionSlotV1,
    ActionTargetSelector,
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    BoundPredicate,
    DependencyEdgeV2,
    PlannerCostEstimate,
    QueryAggregationIntentV1,
    QueryExecutionIntentV1,
    QueryHavingIntentV1,
    QueryIntentSpec,
    QueryPredicateGroupIntentV1,
    QueryPredicateLeafIntentV1,
    QuerySortIntentV1,
    SourceSpan,
    TaskObjectiveV2,
    TaskOutputSpec,
    TaskSpecArtifact,
    TaskSpecV2,
    authorized_schema_sha256,
    task_spec_sha256,
)


WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("00000000-0000-4000-8000-000000000002")
BASE_ID = UUID("00000000-0000-4000-8000-000000000003")
TABLE_ID = UUID("00000000-0000-4000-8000-000000000004")
FIELD_ID = UUID("00000000-0000-4000-8000-000000000005")
SCOPE_HASH = "1" * 64


def _field() -> AuthorizedFieldSpec:
    return AuthorizedFieldSpec(
        field_id=FIELD_ID,
        table_id=TABLE_ID,
        key="status",
        name="状态",
        field_type="status",
        aliases=("进度",),
        choices=("planned", "in_progress", "done", "blocked"),
        writable=True,
    )


def _table() -> AuthorizedTableSpec:
    return AuthorizedTableSpec(
        table_id=TABLE_ID,
        base_id=BASE_ID,
        key="work_items",
        name="工作项",
        aliases=("事项",),
        fields=(_field(),),
    )


def _snapshot() -> AuthorizedSchemaSnapshot:
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": SCOPE_HASH,
        "tables": (_table(),),
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _spec() -> TaskSpecV2:
    span = SourceSpan(start=0, end=4, text="修改状态")
    predicate = BoundPredicate(
        table_id=TABLE_ID,
        field_id=FIELD_ID,
        field_key="status",
        field_type="status",
        operator="eq",
        value="planned",
        source_span=span,
    )
    query_intent = QueryIntentSpec(
        query_intent_id="query-01",
        root_table_id=TABLE_ID,
        entity_codes=("MT-017",),
        predicates=(predicate,),
        aggregation_kinds=(),
        group_by_field_ids=(),
        sort_field_ids=(),
        limit=None,
    )
    fact = TaskObjectiveV2(
        objective_id="obj-01",
        kind="fact_query",
        required=True,
        entity_codes=("MT-017",),
        query_spec_ref="query-intent:query-01",
        output_contract="structured_facts",
        planning_outcome="planned",
        denial_reason=None,
        source_spans=(span,),
    )
    change = TaskObjectiveV2(
        objective_id="obj-02",
        kind="record_change",
        required=True,
        entity_codes=("MT-017",),
        query_spec_ref=None,
        output_contract="action_slot",
        planning_outcome="planned",
        denial_reason=None,
        source_spans=(span,),
    )
    slot = ActionSlotV1(
        slot_id="slot-01",
        objective_id="obj-02",
        action_kind="record.update",
        target=ActionTargetSelector(
            table_id=TABLE_ID,
            record_codes=("MT-017",),
            source_entity_codes=(),
            resolution_status="resolved",
        ),
        assignments=(
            ActionAssignment(
                field_id=FIELD_ID,
                field_key="status",
                value="planned",
                source_span=span,
            ),
        ),
        required_field_keys=("status",),
        confirmation_policy="required",
        deadline_start_utc=None,
        deadline_end_utc=None,
        conflict_group_id=None,
        planning_outcome="planned",
        denial_reason=None,
    )
    return TaskSpecV2(
        version="task-spec.v2",
        authorized_schema_hash=_snapshot().schema_hash,
        query_intents=(query_intent,),
        objectives=(fact, change),
        dependency_edges=(
            DependencyEdgeV2(
                from_objective_id="obj-01",
                to_objective_id="obj-02",
                required=True,
            ),
        ),
        action_slots=(slot,),
        conflict_groups=(),
        output=TaskOutputSpec(
            language="zh-Hans",
            format="conversational",
            include_evidence=True,
        ),
        cost=PlannerCostEstimate(
            lexical_token_count=2,
            bound_field_count=1,
            objective_count=2,
            action_slot_count=1,
            ambiguity_count=0,
            planned_provider_calls=0,
        ),
        provider_call_count=0,
    )


def test_contracts_are_strict_frozen_and_forbid_extra_fields() -> None:
    field = _field()

    with pytest.raises(ValidationError):
        AuthorizedFieldSpec.model_validate({**field.model_dump(), "extra": True})
    with pytest.raises(ValidationError):
        AuthorizedFieldSpec.model_validate({**field.model_dump(), "writable": 1})
    with pytest.raises(ValidationError):
        field.key = "changed"  # type: ignore[misc]


def test_authorized_schema_hash_and_nested_identity_must_be_valid() -> None:
    snapshot = _snapshot()

    assert snapshot.schema_hash == authorized_schema_sha256(
        version=snapshot.version,
        workspace_id=snapshot.workspace_id,
        employee_id=snapshot.employee_id,
        scope_hash=snapshot.scope_hash,
        tables=snapshot.tables,
    )
    with pytest.raises(ValidationError, match="authorized_schema_hash_mismatch"):
        AuthorizedSchemaSnapshot.model_validate(
            {**snapshot.model_dump(), "schema_hash": "2" * 64}
        )

    duplicate_field_table = _table().model_copy(update={"fields": (_field(), _field())})
    with pytest.raises(ValidationError, match="authorized_schema_field_duplicate"):
        AuthorizedTableSpec.model_validate(duplicate_field_table.model_dump())


def test_task_spec_rejects_unknown_references_cycles_and_duplicate_ids() -> None:
    spec = _spec()
    unknown_edge = DependencyEdgeV2(
        from_objective_id="obj-unknown",
        to_objective_id="obj-02",
        required=True,
    )
    with pytest.raises(ValidationError, match="task_spec_dependency_reference_invalid"):
        TaskSpecV2.model_validate(
            {**spec.model_dump(), "dependency_edges": (unknown_edge.model_dump(),)}
        )

    reverse = DependencyEdgeV2(
        from_objective_id="obj-02",
        to_objective_id="obj-01",
        required=True,
    )
    with pytest.raises(ValidationError, match="task_spec_dependency_cycle"):
        TaskSpecV2.model_validate(
            {
                **spec.model_dump(),
                "dependency_edges": (
                    *[item.model_dump() for item in spec.dependency_edges],
                    reverse.model_dump(),
                ),
            }
        )

    with pytest.raises(ValidationError, match="task_spec_objective_duplicate"):
        TaskSpecV2.model_validate(
            {**spec.model_dump(), "objectives": (spec.objectives[0].model_dump(),) * 2}
        )


def test_predicate_operator_and_action_assignment_are_typed() -> None:
    spec = _spec()
    predicate = spec.query_intents[0].predicates[0]

    with pytest.raises(ValidationError, match="task_spec_predicate_operator_invalid"):
        BoundPredicate.model_validate({**predicate.model_dump(), "operator": "before"})
    slot = spec.action_slots[0]
    duplicate_assignment = slot.assignments[0].model_copy(update={"value": "done"})
    with pytest.raises(ValidationError, match="action_slot_assignment_duplicate"):
        ActionSlotV1.model_validate(
            {
                **slot.model_dump(),
                "assignments": (
                    slot.assignments[0].model_dump(),
                    duplicate_assignment.model_dump(),
                ),
            }
        )


def test_unresolved_action_target_may_be_empty_but_resolved_target_may_not() -> None:
    unresolved = ActionTargetSelector(
        table_id=None,
        record_codes=(),
        source_entity_codes=(),
        resolution_status="ambiguous",
    )

    assert unresolved.resolution_status == "ambiguous"
    with pytest.raises(ValidationError, match="action_slot_target_empty"):
        ActionTargetSelector(
            table_id=None,
            record_codes=(),
            source_entity_codes=(),
            resolution_status="resolved",
        )


def test_deferred_action_target_requires_query_ref_and_expansion_policy() -> None:
    target = ActionTargetSelector(
        table_id=TABLE_ID,
        record_codes=(),
        source_entity_codes=(),
        query_spec_ref="query-intent:query-01",
        expansion_policy="each_distinct_owner",
        resolution_status="deferred_query_result",
    )

    assert target.expansion_policy == "each_distinct_owner"
    with pytest.raises(
        ValidationError, match="action_slot_deferred_query_ref_required"
    ):
        ActionTargetSelector(
            table_id=TABLE_ID,
            record_codes=(),
            source_entity_codes=(),
            query_spec_ref=None,
            expansion_policy="each_result",
            resolution_status="deferred_query_result",
        )
    with pytest.raises(
        ValidationError, match="action_slot_static_target_expansion_invalid"
    ):
        ActionTargetSelector(
            table_id=TABLE_ID,
            record_codes=("MT-001",),
            source_entity_codes=(),
            query_spec_ref="query-intent:query-01",
            expansion_policy="each_result",
            resolution_status="deferred_query_result",
        )


def test_task_spec_accepts_known_deferred_target_ref_and_rejects_unknown_ref() -> None:
    spec = _spec()
    target = ActionTargetSelector(
        table_id=TABLE_ID,
        record_codes=(),
        source_entity_codes=(),
        query_spec_ref="query-intent:query-01",
        expansion_policy="each_result",
        resolution_status="deferred_query_result",
    )
    slot = spec.action_slots[0].model_copy(update={"target": target})

    accepted = TaskSpecV2.model_validate(
        {**spec.model_dump(), "action_slots": (slot.model_dump(),)}
    )
    assert accepted.action_slots[0].planning_outcome == "planned"

    invalid_target = target.model_copy(
        update={"query_spec_ref": "query-intent:missing"}
    )
    invalid_slot = slot.model_copy(update={"target": invalid_target})
    with pytest.raises(
        ValidationError, match="task_spec_action_query_reference_invalid"
    ):
        TaskSpecV2.model_validate(
            {**spec.model_dump(), "action_slots": (invalid_slot.model_dump(),)}
        )


def test_task_spec_enforces_counts_and_timezone_aware_deadlines() -> None:
    spec = _spec()
    with pytest.raises(ValidationError, match="task_spec_objective_limit"):
        TaskSpecV2.model_validate(
            {
                **spec.model_dump(),
                "objectives": tuple(
                    spec.objectives[0]
                    .model_copy(update={"objective_id": f"obj-{index:02d}"})
                    .model_dump()
                    for index in range(1, 10)
                ),
                "dependency_edges": (),
                "action_slots": (),
            }
        )

    slot = spec.action_slots[0]
    with pytest.raises(ValidationError, match="action_slot_deadline_timezone_required"):
        ActionSlotV1.model_validate(
            {
                **slot.model_dump(),
                "deadline_end_utc": datetime(2026, 7, 30, 0, 0),
            }
        )


def test_task_spec_hash_and_artifact_ref_are_stable() -> None:
    spec = _spec()
    first = task_spec_sha256(spec)
    second = task_spec_sha256(spec)
    artifact = TaskSpecArtifact(
        version="task-spec-artifact.v1",
        task_spec=spec,
        content_hash=first,
        storage_ref=f"task-spec:sha256:{first}",
    )

    assert first == second
    assert artifact.content_hash == first

    with pytest.raises(ValidationError, match="task_spec_artifact_hash_mismatch"):
        TaskSpecArtifact.model_validate(
            {**artifact.model_dump(), "content_hash": "3" * 64}
        )


def _predicate(*, operator: str = "eq", value: object = "planned") -> BoundPredicate:
    return BoundPredicate(
        table_id=TABLE_ID,
        field_id=FIELD_ID,
        field_key="status",
        field_type="status",
        operator=operator,
        value=value,
        source_span=SourceSpan(start=0, end=4, text="状态条件"),
    )


def test_query_execution_intent_preserves_recursive_predicate_semantics() -> None:
    planned = QueryPredicateLeafIntentV1(predicate=_predicate(value="planned"))
    blocked = QueryPredicateLeafIntentV1(predicate=_predicate(value="blocked"))
    expression = QueryPredicateGroupIntentV1(
        operator="or",
        children=(planned, blocked),
    )

    execution = QueryExecutionIntentV1(
        projection_field_ids=(FIELD_ID,),
        predicate_expression=expression,
        aggregations=(),
        sorts=(),
        limit=25,
    )

    assert execution.predicate_expression == expression
    assert execution.limit == 25


def test_query_execution_predicate_depth_is_bounded() -> None:
    expression = QueryPredicateLeafIntentV1(predicate=_predicate())
    for _ in range(4):
        expression = QueryPredicateGroupIntentV1(
            operator="and",
            children=(expression,),
        )

    with pytest.raises(ValidationError, match="task_spec_predicate_depth_exceeded"):
        QueryExecutionIntentV1(
            projection_field_ids=(),
            predicate_expression=expression,
            aggregations=(),
            sorts=(),
            limit=None,
        )


def test_conditional_aggregate_contract_has_identity_group_and_having() -> None:
    aggregate = QueryAggregationIntentV1(
        aggregate_id="aggregate-unfinished-by-status",
        output_key="unfinished_work_item_count",
        function="count",
        table_id=TABLE_ID,
        field_id=None,
        filter_expression=QueryPredicateLeafIntentV1(
            predicate=_predicate(operator="ne", value="done")
        ),
        group_by_field_ids=(FIELD_ID,),
        having=QueryHavingIntentV1(operator="gte", value=2),
    )

    assert aggregate.output_key == "unfinished_work_item_count"
    assert aggregate.having is not None
    assert aggregate.having.value == 2


def test_query_sort_target_is_exactly_one_field_or_aggregate() -> None:
    field_sort = QuerySortIntentV1(
        sort_id="sort-priority",
        table_id=TABLE_ID,
        field_id=FIELD_ID,
        aggregate_id=None,
        mode="field_order",
        direction="asc",
        nulls="last",
    )
    aggregate_sort = QuerySortIntentV1(
        sort_id="sort-count",
        table_id=None,
        field_id=None,
        aggregate_id="aggregate-count",
        mode="natural",
        direction="desc",
        nulls="last",
    )

    assert field_sort.field_id == FIELD_ID
    assert aggregate_sort.aggregate_id == "aggregate-count"
    with pytest.raises(ValidationError, match="task_spec_sort_target_invalid"):
        QuerySortIntentV1(
            sort_id="sort-invalid",
            table_id=TABLE_ID,
            field_id=FIELD_ID,
            aggregate_id="aggregate-count",
            mode="natural",
            direction="desc",
            nulls="last",
        )


def test_query_intent_requires_execution_summary_consistency() -> None:
    predicate = _predicate()
    execution = QueryExecutionIntentV1(
        projection_field_ids=(FIELD_ID,),
        predicate_expression=QueryPredicateLeafIntentV1(predicate=predicate),
        aggregations=(
            QueryAggregationIntentV1(
                aggregate_id="aggregate-count",
                output_key="record_count",
                function="count",
                table_id=TABLE_ID,
                field_id=None,
                filter_expression=None,
                group_by_field_ids=(FIELD_ID,),
                having=None,
            ),
        ),
        sorts=(
            QuerySortIntentV1(
                sort_id="sort-status",
                table_id=TABLE_ID,
                field_id=FIELD_ID,
                aggregate_id=None,
                mode="field_order",
                direction="asc",
                nulls="last",
            ),
        ),
        limit=10,
    )

    accepted = QueryIntentSpec(
        query_intent_id="query-typed",
        root_table_id=TABLE_ID,
        entity_codes=(),
        predicates=(predicate,),
        aggregation_kinds=("count",),
        group_by_field_ids=(FIELD_ID,),
        sort_field_ids=(FIELD_ID,),
        limit=10,
        execution_spec=execution,
    )
    assert accepted.execution_spec == execution

    with pytest.raises(ValidationError, match="task_spec_execution_summary_mismatch"):
        QueryIntentSpec.model_validate(
            {**accepted.model_dump(), "aggregation_kinds": ("sum",)}
        )
