from __future__ import annotations

from uuid import UUID

import pytest

from app.schemas.agent_task_spec_v2 import (
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    BoundPredicate,
    PlannerCostEstimate,
    QueryAggregationIntentV1,
    QueryExecutionIntentV1,
    QueryHavingIntentV1,
    QueryJoinIntentV1,
    QueryIntentSpec,
    QueryPredicateGroupIntentV1,
    QueryPredicateLeafIntentV1,
    QuerySortIntentV1,
    SourceSpan,
    TaskObjectiveV2,
    TaskOutputSpec,
    TaskSpecV2,
    authorized_schema_sha256,
)
from app.schemas.authorized_query_plan import AuthorizedRelationSpec
from app.services.authorized_query_compiler import (
    AuthorizedQueryCompileError,
    compile_authorized_query_plan,
)


WORKSPACE_ID = UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("30000000-0000-4000-8000-000000000002")
BASE_ID = UUID("30000000-0000-4000-8000-000000000003")
PROJECTS_ID = UUID("30000000-0000-4000-8000-000000000010")
WORK_ITEMS_ID = UUID("30000000-0000-4000-8000-000000000020")
RISKS_ID = UUID("30000000-0000-4000-8000-000000000030")
PROJECT_NAME_ID = UUID("30000000-0000-4000-8000-000000000101")
WORK_TITLE_ID = UUID("30000000-0000-4000-8000-000000000201")
WORK_STATUS_ID = UUID("30000000-0000-4000-8000-000000000202")
WORK_PRIORITY_ID = UUID("30000000-0000-4000-8000-000000000203")
WORK_PROJECT_ID = UUID("30000000-0000-4000-8000-000000000204")
WORK_ALT_PROJECT_ID = UUID("30000000-0000-4000-8000-000000000205")
RISK_LEVEL_ID = UUID("30000000-0000-4000-8000-000000000301")
RISK_WORK_ITEM_ID = UUID("30000000-0000-4000-8000-000000000302")
SAFE_VIEW_ID = UUID("30000000-0000-4000-8000-000000000401")


def _field(
    table_id: UUID,
    field_id: UUID,
    key: str,
    field_type: str,
    *,
    choices: tuple[str, ...] = (),
) -> AuthorizedFieldSpec:
    return AuthorizedFieldSpec(
        field_id=field_id,
        table_id=table_id,
        key=key,
        name=key,
        field_type=field_type,
        aliases=(),
        choices=choices,
        writable=True,
    )


def _snapshot() -> AuthorizedSchemaSnapshot:
    tables = (
        AuthorizedTableSpec(
            table_id=PROJECTS_ID,
            base_id=BASE_ID,
            key="projects",
            name="项目",
            aliases=(),
            fields=(_field(PROJECTS_ID, PROJECT_NAME_ID, "name", "text"),),
            identity_field_id=PROJECT_NAME_ID,
        ),
        AuthorizedTableSpec(
            table_id=WORK_ITEMS_ID,
            base_id=BASE_ID,
            key="work_items",
            name="事项",
            aliases=(),
            fields=(
                _field(WORK_ITEMS_ID, WORK_TITLE_ID, "title", "text"),
                _field(
                    WORK_ITEMS_ID,
                    WORK_STATUS_ID,
                    "status",
                    "status",
                    choices=("planned", "in_progress", "done", "blocked"),
                ),
                _field(
                    WORK_ITEMS_ID,
                    WORK_PRIORITY_ID,
                    "priority",
                    "single_select",
                    choices=("high", "medium", "low"),
                ),
                _field(
                    WORK_ITEMS_ID,
                    WORK_PROJECT_ID,
                    "project_link",
                    "linked_record",
                ),
                _field(
                    WORK_ITEMS_ID,
                    WORK_ALT_PROJECT_ID,
                    "alternate_project_link",
                    "linked_record",
                ),
            ),
            identity_field_id=WORK_TITLE_ID,
        ),
        AuthorizedTableSpec(
            table_id=RISKS_ID,
            base_id=BASE_ID,
            key="risks",
            name="风险",
            aliases=(),
            fields=(
                _field(
                    RISKS_ID,
                    RISK_LEVEL_ID,
                    "level",
                    "single_select",
                    choices=("low", "medium", "high"),
                ),
                _field(
                    RISKS_ID,
                    RISK_WORK_ITEM_ID,
                    "work_item_link",
                    "linked_record",
                ),
            ),
            identity_field_id=RISK_LEVEL_ID,
        ),
    )
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": "c" * 64,
        "tables": tables,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _span() -> SourceSpan:
    return SourceSpan(start=0, end=4, text="查询条件")


def _predicate(*, table_id: UUID = WORK_ITEMS_ID) -> BoundPredicate:
    return BoundPredicate(
        table_id=table_id,
        field_id=WORK_STATUS_ID,
        field_key="status",
        field_type="status",
        operator="ne",
        value="done",
        source_span=_span(),
    )


def _execution(
    *,
    projection_field_ids: tuple[UUID, ...] = (WORK_TITLE_ID,),
    predicate_expression=None,
    aggregations: tuple[QueryAggregationIntentV1, ...] = (),
    sorts: tuple[QuerySortIntentV1, ...] = (),
    join_intents: tuple[QueryJoinIntentV1, ...] = (),
    limit: int | None = None,
) -> QueryExecutionIntentV1:
    return QueryExecutionIntentV1(
        projection_field_ids=projection_field_ids,
        predicate_expression=predicate_expression,
        aggregations=aggregations,
        sorts=sorts,
        join_intents=join_intents,
        limit=limit,
    )


def _query_intent(
    *,
    root_table_id: UUID = WORK_ITEMS_ID,
    predicates: tuple[BoundPredicate, ...] = (),
    execution_spec: QueryExecutionIntentV1 | None = None,
    aggregation_kinds: tuple[str, ...] = (),
    group_by_field_ids: tuple[UUID, ...] = (),
    sort_field_ids: tuple[UUID, ...] = (),
    limit: int | None = None,
) -> QueryIntentSpec:
    return QueryIntentSpec(
        query_intent_id="query-01",
        root_table_id=root_table_id,
        entity_codes=("PRJ-ATLAS",),
        predicates=predicates,
        aggregation_kinds=aggregation_kinds,
        group_by_field_ids=group_by_field_ids,
        sort_field_ids=sort_field_ids,
        limit=limit,
        execution_spec=execution_spec,
    )


def _task_spec(intent: QueryIntentSpec) -> TaskSpecV2:
    objective = TaskObjectiveV2(
        objective_id="obj-01",
        kind="fact_query",
        required=True,
        entity_codes=intent.entity_codes,
        query_spec_ref="query-intent:query-01",
        output_contract="structured_facts",
        planning_outcome="planned",
        denial_reason=None,
        source_spans=(_span(),),
    )
    return TaskSpecV2(
        version="task-spec.v2",
        authorized_schema_hash=_snapshot().schema_hash,
        query_intents=(intent,),
        objectives=(objective,),
        dependency_edges=(),
        action_slots=(),
        conflict_groups=(),
        output=TaskOutputSpec(
            language="zh-Hans",
            format="structured",
            include_evidence=True,
        ),
        cost=PlannerCostEstimate(
            lexical_token_count=1,
            bound_field_count=1,
            objective_count=1,
            action_slot_count=0,
            ambiguity_count=0,
            planned_provider_calls=0,
        ),
        provider_call_count=0,
    )


def _relation(*, alternate: bool = False) -> AuthorizedRelationSpec:
    return AuthorizedRelationSpec(
        relation_id="rel-work-alt-project" if alternate else "rel-work-project",
        link_source_table_id=WORK_ITEMS_ID,
        link_field_id=WORK_ALT_PROJECT_ID if alternate else WORK_PROJECT_ID,
        link_target_table_id=PROJECTS_ID,
    )


def _risk_relation() -> AuthorizedRelationSpec:
    return AuthorizedRelationSpec(
        relation_id="rel-risk-work",
        link_source_table_id=RISKS_ID,
        link_field_id=RISK_WORK_ITEM_ID,
        link_target_table_id=WORK_ITEMS_ID,
    )


def test_compiler_emits_independent_required_and_optional_traversal_paths() -> None:
    work_predicate = _predicate()
    risk_predicate = BoundPredicate(
        table_id=RISKS_ID,
        field_id=RISK_LEVEL_ID,
        field_key="level",
        field_type="single_select",
        operator="eq",
        value="high",
        source_span=_span(),
    )
    expression = QueryPredicateGroupIntentV1(
        operator="and",
        children=(
            QueryPredicateLeafIntentV1(predicate=work_predicate),
            QueryPredicateLeafIntentV1(predicate=risk_predicate),
        ),
    )
    execution = _execution(
        projection_field_ids=(WORK_TITLE_ID, RISK_LEVEL_ID),
        predicate_expression=expression,
        join_intents=(
            QueryJoinIntentV1(
                join_intent_id="join-work",
                target_table_id=WORK_ITEMS_ID,
                purpose="filter",
                requirement="required",
            ),
            QueryJoinIntentV1(
                join_intent_id="join-risk",
                target_table_id=RISKS_ID,
                purpose="project",
                requirement="optional",
            ),
        ),
    )
    intent = _query_intent(
        root_table_id=PROJECTS_ID,
        predicates=(work_predicate, risk_predicate),
        execution_spec=execution,
    )

    plan = compile_authorized_query_plan(
        task_spec=_task_spec(intent),
        query_intent_id=intent.query_intent_id,
        snapshot=_snapshot(),
        relations=(_relation(), _risk_relation()),
        authorized_view_ids=(),
    )

    assert plan.traversals == ()
    assert [item.path_id for item in plan.traversal_paths] == [
        "path-join-risk",
        "path-join-work",
    ]
    by_id = {item.path_id: item for item in plan.traversal_paths}
    assert by_id["path-join-work"].join_mode == "inner"
    assert len(by_id["path-join-work"].steps) == 1
    assert by_id["path-join-work"].predicate is None
    assert by_id["path-join-risk"].join_mode == "left"
    assert len(by_id["path-join-risk"].steps) == 2
    assert by_id["path-join-risk"].predicate is not None
    assert plan.predicate is not None
    assert {
        item.table_id
        for item in (
            plan.predicate.children
            if hasattr(plan.predicate, "children")
            else (plan.predicate,)
        )
    } == {WORK_ITEMS_ID}


def _compile(
    intent: QueryIntentSpec,
    *,
    relations: tuple[AuthorizedRelationSpec, ...] = (_relation(),),
):
    return compile_authorized_query_plan(
        task_spec=_task_spec(intent),
        query_intent_id="query-01",
        snapshot=_snapshot(),
        relations=relations,
        authorized_view_ids=(SAFE_VIEW_ID,),
    )


def test_compiler_preserves_explicit_projection_and_recursive_predicate() -> None:
    left = QueryPredicateLeafIntentV1(predicate=_predicate())
    right = QueryPredicateLeafIntentV1(
        predicate=_predicate().model_copy(update={"operator": "eq", "value": "blocked"})
    )
    expression = QueryPredicateGroupIntentV1(operator="or", children=(left, right))
    intent = _query_intent(
        predicates=(left.predicate, right.predicate),
        execution_spec=_execution(predicate_expression=expression),
    )

    plan = _compile(intent)

    assert plan.projection_field_ids == (WORK_TITLE_ID,)
    assert plan.predicate is not None
    assert plan.predicate.kind == "group"
    assert plan.predicate.operator == "or"
    assert plan.traversals == ()


def test_compiler_defaults_empty_projection_to_root_identity_and_predicate_fields() -> (
    None
):
    predicate = _predicate()
    intent = _query_intent(
        predicates=(predicate,),
        execution_spec=_execution(
            projection_field_ids=(),
            predicate_expression=QueryPredicateLeafIntentV1(predicate=predicate),
        ),
    )

    plan = _compile(intent)

    assert plan.projection_field_ids == (WORK_TITLE_ID, WORK_STATUS_ID)


def test_compiler_uses_unique_reverse_path_for_related_aggregate() -> None:
    predicate = _predicate()
    aggregate = QueryAggregationIntentV1(
        aggregate_id="aggregate-unfinished",
        output_key="unfinished_work_item_count",
        function="count",
        table_id=WORK_ITEMS_ID,
        field_id=None,
        filter_expression=QueryPredicateLeafIntentV1(predicate=predicate),
        group_by_field_ids=(WORK_PROJECT_ID,),
        having=QueryHavingIntentV1(operator="gte", value=2),
    )
    execution = _execution(
        projection_field_ids=(PROJECT_NAME_ID,),
        aggregations=(aggregate,),
    )
    intent = _query_intent(
        root_table_id=PROJECTS_ID,
        execution_spec=execution,
        aggregation_kinds=("count",),
        group_by_field_ids=(WORK_PROJECT_ID,),
    )

    plan = _compile(intent)

    assert [
        (item.link_source_table_id, item.link_target_table_id, item.direction)
        for item in plan.traversals
    ] == [(WORK_ITEMS_ID, PROJECTS_ID, "reverse")]
    assert plan.aggregates[0].output_key == "unfinished_work_item_count"
    assert plan.aggregates[0].having is not None
    assert plan.aggregates[0].having.value == 2


def test_compiler_uses_unique_authorized_two_hop_path() -> None:
    risk_predicate = BoundPredicate(
        table_id=RISKS_ID,
        field_id=RISK_LEVEL_ID,
        field_key="level",
        field_type="single_select",
        operator="eq",
        value="high",
        source_span=_span(),
    )
    execution = _execution(
        projection_field_ids=(PROJECT_NAME_ID,),
        predicate_expression=QueryPredicateLeafIntentV1(predicate=risk_predicate),
    )
    intent = _query_intent(
        root_table_id=PROJECTS_ID,
        predicates=(risk_predicate,),
        execution_spec=execution,
    )

    plan = _compile(intent, relations=(_relation(), _risk_relation()))

    assert [(item.relation_id, item.direction) for item in plan.traversals] == [
        ("rel-work-project", "reverse"),
        ("rel-risk-work", "reverse"),
    ]


def test_compiler_refuses_equal_shortest_authorized_paths() -> None:
    execution = _execution(
        projection_field_ids=(PROJECT_NAME_ID,),
        predicate_expression=QueryPredicateLeafIntentV1(predicate=_predicate()),
    )
    intent = _query_intent(
        root_table_id=PROJECTS_ID,
        predicates=(_predicate(),),
        execution_spec=execution,
    )

    with pytest.raises(
        AuthorizedQueryCompileError,
        match="^authorized_query_join_path_ambiguous$",
    ):
        _compile(intent, relations=(_relation(), _relation(alternate=True)))


def test_compiler_refuses_missing_authorized_path() -> None:
    execution = _execution(
        projection_field_ids=(PROJECT_NAME_ID,),
        predicate_expression=QueryPredicateLeafIntentV1(predicate=_predicate()),
    )
    intent = _query_intent(
        root_table_id=PROJECTS_ID,
        predicates=(_predicate(),),
        execution_spec=execution,
    )

    with pytest.raises(
        AuthorizedQueryCompileError,
        match="^authorized_query_join_path_unavailable$",
    ):
        _compile(intent, relations=())


def test_compiler_refuses_legacy_aggregate_without_execution_detail() -> None:
    intent = _query_intent(aggregation_kinds=("count",))

    with pytest.raises(
        AuthorizedQueryCompileError,
        match="^authorized_query_execution_detail_required$",
    ):
        _compile(intent)


def test_compiler_accepts_legacy_simple_predicate_as_implicit_and() -> None:
    first = _predicate()
    second = first.model_copy(update={"operator": "eq", "value": "blocked"})
    intent = _query_intent(predicates=(first, second))

    plan = _compile(intent)

    assert plan.predicate is not None
    assert plan.predicate.kind == "group"
    assert plan.predicate.operator == "and"
    assert len(plan.predicate.children) == 2


def test_compiler_keeps_entity_codes_as_selectors_without_resolution() -> None:
    plan = _compile(_query_intent(execution_spec=_execution()))

    assert plan.entity_codes == ("PRJ-ATLAS",)


def test_compiler_preserves_aggregate_sort_target() -> None:
    aggregate = QueryAggregationIntentV1(
        aggregate_id="aggregate-count",
        output_key="record_count",
        function="count",
        table_id=WORK_ITEMS_ID,
        field_id=None,
        filter_expression=None,
        group_by_field_ids=(),
        having=None,
    )
    sort = QuerySortIntentV1(
        sort_id="sort-count",
        table_id=None,
        field_id=None,
        aggregate_id="aggregate-count",
        mode="natural",
        direction="desc",
        nulls="last",
    )
    intent = _query_intent(
        execution_spec=_execution(aggregations=(aggregate,), sorts=(sort,)),
        aggregation_kinds=("count",),
    )

    plan = _compile(intent)

    assert plan.sort_rules[0].aggregate_id == "aggregate-count"
    assert plan.sort_rules[0].field_id is None
