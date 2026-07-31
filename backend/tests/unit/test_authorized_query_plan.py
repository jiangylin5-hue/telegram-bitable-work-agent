from __future__ import annotations

from hashlib import sha256
import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.agent_task_spec_v2 import (
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    authorized_schema_sha256,
)
from app.schemas.authorized_query_plan import (
    AuthorizedQueryPlanV1,
    AuthorizedRelationSpec,
    QueryAggregateSpec,
    QueryHavingSpec,
    QueryPredicateGroup,
    QueryPredicateLeaf,
    QuerySortSpec,
    QueryTraversalSpec,
    SourceRecordVersion,
    StructuredAggregate,
    StructuredFieldValue,
    StructuredQueryResultV1,
    StructuredQueryArtifactV1,
    StructuredRecord,
    authorized_query_plan_sha256,
)
from app.services.authorized_query_validation import validate_authorized_query_plan


WORKSPACE_ID = UUID("20000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("20000000-0000-4000-8000-000000000002")
BASE_ID = UUID("20000000-0000-4000-8000-000000000003")
PROJECTS_ID = UUID("20000000-0000-4000-8000-000000000010")
WORK_ITEMS_ID = UUID("20000000-0000-4000-8000-000000000020")
RISKS_ID = UUID("20000000-0000-4000-8000-000000000030")
OWNERS_ID = UUID("20000000-0000-4000-8000-000000000040")
PROJECT_NAME_ID = UUID("20000000-0000-4000-8000-000000000101")
WORK_TITLE_ID = UUID("20000000-0000-4000-8000-000000000201")
WORK_AMOUNT_ID = UUID("20000000-0000-4000-8000-000000000202")
WORK_STATUS_ID = UUID("20000000-0000-4000-8000-000000000203")
WORK_PROJECT_ID = UUID("20000000-0000-4000-8000-000000000204")
RISK_CODE_ID = UUID("20000000-0000-4000-8000-000000000301")
RISK_WORK_ITEM_ID = UUID("20000000-0000-4000-8000-000000000302")
OWNER_NAME_ID = UUID("20000000-0000-4000-8000-000000000401")
OWNER_RISK_ID = UUID("20000000-0000-4000-8000-000000000402")
SAFE_VIEW_ID = UUID("20000000-0000-4000-8000-000000000501")
OTHER_VIEW_ID = UUID("20000000-0000-4000-8000-000000000502")
WORK_RECORD_ID = UUID("20000000-0000-4000-8000-000000000601")


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
        ),
        AuthorizedTableSpec(
            table_id=WORK_ITEMS_ID,
            base_id=BASE_ID,
            key="work_items",
            name="工作项",
            aliases=(),
            fields=(
                _field(WORK_ITEMS_ID, WORK_TITLE_ID, "title", "text"),
                _field(WORK_ITEMS_ID, WORK_AMOUNT_ID, "amount", "number"),
                _field(
                    WORK_ITEMS_ID,
                    WORK_STATUS_ID,
                    "status",
                    "status",
                    choices=("planned", "done"),
                ),
                _field(
                    WORK_ITEMS_ID,
                    WORK_PROJECT_ID,
                    "project_link",
                    "linked_record",
                ),
            ),
        ),
        AuthorizedTableSpec(
            table_id=RISKS_ID,
            base_id=BASE_ID,
            key="risks",
            name="风险",
            aliases=(),
            fields=(
                _field(RISKS_ID, RISK_CODE_ID, "risk_code", "text"),
                _field(
                    RISKS_ID,
                    RISK_WORK_ITEM_ID,
                    "work_item_link",
                    "linked_record",
                ),
            ),
        ),
        AuthorizedTableSpec(
            table_id=OWNERS_ID,
            base_id=BASE_ID,
            key="owners",
            name="负责人",
            aliases=(),
            fields=(
                _field(OWNERS_ID, OWNER_NAME_ID, "name", "text"),
                _field(OWNERS_ID, OWNER_RISK_ID, "risk_link", "linked_record"),
            ),
        ),
    )
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": "a" * 64,
        "tables": tables,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _catalog() -> tuple[AuthorizedRelationSpec, ...]:
    return (
        AuthorizedRelationSpec(
            relation_id="rel-work-project",
            link_source_table_id=WORK_ITEMS_ID,
            link_field_id=WORK_PROJECT_ID,
            link_target_table_id=PROJECTS_ID,
        ),
        AuthorizedRelationSpec(
            relation_id="rel-risk-work",
            link_source_table_id=RISKS_ID,
            link_field_id=RISK_WORK_ITEM_ID,
            link_target_table_id=WORK_ITEMS_ID,
        ),
        AuthorizedRelationSpec(
            relation_id="rel-owner-risk",
            link_source_table_id=OWNERS_ID,
            link_field_id=OWNER_RISK_ID,
            link_target_table_id=RISKS_ID,
        ),
    )


def test_authorized_relation_catalog_allows_same_table_links() -> None:
    relation = AuthorizedRelationSpec(
        relation_id="relation:parent",
        link_source_table_id=WORK_ITEMS_ID,
        link_field_id=UUID("30000000-0000-4000-8000-000000000099"),
        link_target_table_id=WORK_ITEMS_ID,
    )

    assert relation.link_source_table_id == relation.link_target_table_id


def _leaf(
    *,
    field_id: UUID = WORK_STATUS_ID,
    table_id: UUID = WORK_ITEMS_ID,
    operator: str = "eq",
    value: object = "planned",
    predicate_id: str = "predicate-01",
) -> QueryPredicateLeaf:
    return QueryPredicateLeaf(
        predicate_id=predicate_id,
        table_id=table_id,
        field_id=field_id,
        operator=operator,
        value=value,
    )


def _plan(**updates: object) -> AuthorizedQueryPlanV1:
    values: dict[str, object] = {
        "version": "authorized-query-plan.v1",
        "query_intent_id": "query-01",
        "root_table_id": WORK_ITEMS_ID,
        "authorized_view_ids": (SAFE_VIEW_ID,),
        "entity_codes": (),
        "predicate": _leaf(),
        "traversals": (),
        "projection_field_ids": (WORK_TITLE_ID,),
        "group_by_field_ids": (),
        "aggregates": (),
        "sort_rules": (),
        "limit": None,
        "max_scan_rows": 5000,
        "max_relation_expansions": 1000,
        "scope_hash": "a" * 64,
        "schema_hash": _snapshot().schema_hash,
    }
    values.update(updates)
    return AuthorizedQueryPlanV1(**values)


def _validate(
    plan: AuthorizedQueryPlanV1,
    *,
    allowed_view_ids: tuple[UUID, ...] = (SAFE_VIEW_ID,),
) -> None:
    validate_authorized_query_plan(
        plan,
        snapshot=_snapshot(),
        catalog=_catalog(),
        allowed_view_ids=allowed_view_ids,
    )


def test_valid_single_table_plan_is_accepted() -> None:
    _validate(_plan())


def test_unknown_root_table_is_rejected_without_exposing_a_name() -> None:
    unknown = UUID("20000000-0000-4000-8000-000000009999")

    with pytest.raises(ValueError, match="^authorized_query_table_not_authorized$"):
        _validate(_plan(root_table_id=unknown))


def test_unknown_field_is_rejected() -> None:
    unknown = UUID("20000000-0000-4000-8000-000000009998")

    with pytest.raises(ValueError, match="^authorized_query_field_not_authorized$"):
        _validate(_plan(projection_field_ids=(unknown,)))


def test_field_table_mismatch_is_rejected() -> None:
    mismatched = _leaf(field_id=PROJECT_NAME_ID, table_id=WORK_ITEMS_ID)

    with pytest.raises(ValueError, match="^authorized_query_field_table_mismatch$"):
        _validate(_plan(predicate=mismatched))


def test_predicate_table_must_be_reachable_from_root() -> None:
    related = _leaf(
        field_id=PROJECT_NAME_ID,
        table_id=PROJECTS_ID,
        operator="contains",
        value="Atlas",
    )

    with pytest.raises(ValueError, match="^authorized_query_field_table_unreachable$"):
        _validate(_plan(predicate=related, traversals=()))


def test_view_outside_explicit_execution_scope_is_rejected() -> None:
    with pytest.raises(ValueError, match="^authorized_query_view_not_authorized$"):
        _validate(
            _plan(authorized_view_ids=(OTHER_VIEW_ID,)),
            allowed_view_ids=(SAFE_VIEW_ID,),
        )


def test_text_field_rejects_numeric_operator() -> None:
    invalid = _leaf(
        field_id=WORK_TITLE_ID,
        table_id=WORK_ITEMS_ID,
        operator="gt",
        value=3,
    )

    with pytest.raises(ValueError, match="^authorized_query_operator_type_invalid$"):
        _validate(_plan(predicate=invalid))


def test_raw_sql_is_rejected_by_strict_schema() -> None:
    payload = _plan().model_dump(mode="python")
    payload["raw_sql"] = "select 1"

    with pytest.raises(ValidationError):
        AuthorizedQueryPlanV1.model_validate(payload)


def test_three_relation_hops_are_rejected() -> None:
    traversals = (
        QueryTraversalSpec(
            traversal_id="traversal-01",
            relation_id="rel-work-project",
            link_source_table_id=WORK_ITEMS_ID,
            link_field_id=WORK_PROJECT_ID,
            link_target_table_id=PROJECTS_ID,
            direction="reverse",
            max_expansion=100,
        ),
        QueryTraversalSpec(
            traversal_id="traversal-02",
            relation_id="rel-risk-work",
            link_source_table_id=RISKS_ID,
            link_field_id=RISK_WORK_ITEM_ID,
            link_target_table_id=WORK_ITEMS_ID,
            direction="reverse",
            max_expansion=100,
        ),
        QueryTraversalSpec(
            traversal_id="traversal-03",
            relation_id="rel-owner-risk",
            link_source_table_id=OWNERS_ID,
            link_field_id=OWNER_RISK_ID,
            link_target_table_id=RISKS_ID,
            direction="reverse",
            max_expansion=100,
        ),
    )

    with pytest.raises(ValueError, match="^authorized_query_traversal_depth_exceeded$"):
        _validate(
            _plan(root_table_id=PROJECTS_ID, predicate=None, traversals=traversals)
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (("max_scan_rows", 5001), ("max_relation_expansions", 1001)),
)
def test_plan_budgets_cannot_exceed_synchronous_limits(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        _plan(**{field: value})


def test_sum_rejects_text_input_field() -> None:
    aggregate = QueryAggregateSpec(
        aggregate_id="aggregate-01",
        output_key="sum_title",
        function="sum",
        table_id=WORK_ITEMS_ID,
        field_id=WORK_TITLE_ID,
        filter_predicate=None,
        group_by_field_ids=(),
        having=None,
    )

    with pytest.raises(ValueError, match="^authorized_query_aggregate_type_invalid$"):
        _validate(_plan(aggregates=(aggregate,)))


def test_count_without_input_field_is_valid() -> None:
    aggregate = QueryAggregateSpec(
        aggregate_id="aggregate-01",
        output_key="record_count",
        function="count",
        table_id=WORK_ITEMS_ID,
        field_id=None,
        filter_predicate=None,
        group_by_field_ids=(),
        having=None,
    )

    _validate(_plan(aggregates=(aggregate,)))


def test_duplicate_operator_ids_across_predicate_tree_are_rejected() -> None:
    predicate = QueryPredicateGroup(
        predicate_id="predicate-root",
        operator="and",
        children=(
            _leaf(predicate_id="predicate-duplicate"),
            _leaf(
                field_id=WORK_AMOUNT_ID,
                operator="gte",
                value=10,
                predicate_id="predicate-duplicate",
            ),
        ),
    )

    with pytest.raises(ValueError, match="^authorized_query_operator_id_duplicate$"):
        _validate(_plan(predicate=predicate))


def test_predicate_tree_deeper_than_four_nodes_is_rejected() -> None:
    predicate: QueryPredicateLeaf | QueryPredicateGroup = _leaf()
    for depth in range(5):
        predicate = QueryPredicateGroup(
            predicate_id=f"group-{depth}",
            operator="and",
            children=(predicate,),
        )

    with pytest.raises(ValueError, match="^authorized_query_predicate_depth_exceeded$"):
        _validate(_plan(predicate=predicate))


def test_predicate_tree_larger_than_sixty_four_nodes_is_rejected() -> None:
    groups = tuple(
        QueryPredicateGroup(
            predicate_id=f"group-{group_index}",
            operator="or",
            children=tuple(
                _leaf(
                    predicate_id=f"leaf-{group_index}-{leaf_index}",
                )
                for leaf_index in range(13)
            ),
        )
        for group_index in range(5)
    )
    predicate = QueryPredicateGroup(
        predicate_id="predicate-root",
        operator="and",
        children=groups,
    )

    with pytest.raises(ValueError, match="^authorized_query_predicate_node_limit$"):
        _validate(_plan(predicate=predicate))


def test_traversal_must_exactly_match_authorized_relation_catalog() -> None:
    traversal = QueryTraversalSpec(
        traversal_id="traversal-01",
        relation_id="rel-work-project",
        link_source_table_id=WORK_ITEMS_ID,
        link_field_id=WORK_PROJECT_ID,
        link_target_table_id=RISKS_ID,
        direction="forward",
        max_expansion=100,
    )

    with pytest.raises(ValueError, match="^authorized_query_relation_not_authorized$"):
        _validate(_plan(predicate=None, traversals=(traversal,)))


def test_sort_field_must_be_authorized_and_type_bound() -> None:
    sort = QuerySortSpec(
        sort_id="sort-01",
        table_id=PROJECTS_ID,
        field_id=WORK_TITLE_ID,
        aggregate_id=None,
        mode="natural",
        direction="asc",
        nulls="last",
    )

    with pytest.raises(ValueError, match="^authorized_query_field_table_mismatch$"):
        _validate(_plan(sort_rules=(sort,)))


def test_aggregate_supports_local_filter_group_having_and_stable_output_key() -> None:
    aggregate = QueryAggregateSpec(
        aggregate_id="aggregate-unfinished",
        output_key="unfinished_work_item_count",
        function="count",
        table_id=WORK_ITEMS_ID,
        field_id=None,
        filter_predicate=_leaf(operator="ne", value="done", predicate_id="local-01"),
        group_by_field_ids=(WORK_PROJECT_ID,),
        having=QueryHavingSpec(operator="gte", value=2),
    )

    _validate(
        _plan(
            predicate=None,
            aggregates=(aggregate,),
            group_by_field_ids=(WORK_PROJECT_ID,),
        )
    )


def test_plan_group_summary_must_match_aggregate_groups() -> None:
    aggregate = QueryAggregateSpec(
        aggregate_id="aggregate-grouped",
        output_key="grouped_count",
        function="count",
        table_id=WORK_ITEMS_ID,
        field_id=None,
        filter_predicate=None,
        group_by_field_ids=(WORK_PROJECT_ID,),
        having=None,
    )

    with pytest.raises(ValueError, match="^authorized_query_group_summary_mismatch$"):
        _validate(
            _plan(
                predicate=None,
                aggregates=(aggregate,),
                group_by_field_ids=(),
            )
        )


def test_sort_may_target_aggregate_but_not_field_and_aggregate_together() -> None:
    aggregate = QueryAggregateSpec(
        aggregate_id="aggregate-count",
        output_key="record_count",
        function="count",
        table_id=WORK_ITEMS_ID,
        field_id=None,
        filter_predicate=None,
        group_by_field_ids=(),
        having=None,
    )
    aggregate_sort = QuerySortSpec(
        sort_id="sort-count",
        table_id=None,
        field_id=None,
        aggregate_id="aggregate-count",
        mode="natural",
        direction="desc",
        nulls="last",
    )

    _validate(
        _plan(predicate=None, aggregates=(aggregate,), sort_rules=(aggregate_sort,))
    )

    with pytest.raises(ValidationError, match="authorized_query_sort_target_invalid"):
        QuerySortSpec(
            sort_id="sort-invalid",
            table_id=WORK_ITEMS_ID,
            field_id=WORK_STATUS_ID,
            aggregate_id="aggregate-count",
            mode="natural",
            direction="desc",
            nulls="last",
        )


def test_field_order_sort_requires_authorized_choice_field() -> None:
    invalid = QuerySortSpec(
        sort_id="sort-title",
        table_id=WORK_ITEMS_ID,
        field_id=WORK_TITLE_ID,
        aggregate_id=None,
        mode="field_order",
        direction="asc",
        nulls="last",
    )

    with pytest.raises(ValueError, match="authorized_query_sort_mode_invalid"):
        _validate(_plan(sort_rules=(invalid,)))


def test_result_hash_mismatch_is_rejected() -> None:
    values = {
        "version": "structured-query-result.v1",
        "query_plan_version": "authorized-query-plan.v1",
        "plan_hash": "b" * 64,
        "records": (
            StructuredRecord(
                record_id=WORK_RECORD_ID,
                table_id=WORK_ITEMS_ID,
                values=(StructuredFieldValue(field_id=WORK_TITLE_ID, value="Review"),),
            ),
        ),
        "groups": (),
        "aggregates": (
            StructuredAggregate(
                aggregate_id="aggregate-01",
                group_key=None,
                value=1,
            ),
        ),
        "relation_paths": (),
        "source_versions": (
            SourceRecordVersion(
                table_id=WORK_ITEMS_ID,
                record_id=WORK_RECORD_ID,
                record_version=2,
            ),
        ),
        "scope_hash": "a" * 64,
        "schema_hash": _snapshot().schema_hash,
        "scanned_record_count": 1,
        "traversed_edge_count": 0,
        "truncated": False,
    }
    canonical = json.dumps(
        {key: _jsonable(value) for key, value in values.items()},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    expected_hash = sha256(canonical).hexdigest()

    valid = StructuredQueryResultV1(**values, result_hash=expected_hash)
    assert valid.result_hash == expected_hash

    with pytest.raises(ValueError, match="structured_query_result_hash_mismatch"):
        StructuredQueryResultV1(**values, result_hash="0" * 64)


def test_structured_record_values_are_immutable_and_unique() -> None:
    record = StructuredRecord(
        record_id=WORK_RECORD_ID,
        table_id=WORK_ITEMS_ID,
        values=(StructuredFieldValue(field_id=WORK_TITLE_ID, value="Review"),),
    )

    with pytest.raises((AttributeError, TypeError, ValidationError)):
        record.values[0].value = "Changed"

    with pytest.raises(ValueError, match="structured_record_field_duplicate"):
        StructuredRecord(
            record_id=WORK_RECORD_ID,
            table_id=WORK_ITEMS_ID,
            values=(
                StructuredFieldValue(field_id=WORK_TITLE_ID, value="A"),
                StructuredFieldValue(field_id=WORK_TITLE_ID, value="B"),
            ),
        )


def test_query_artifact_requires_hand_verified_plan_and_result_identity() -> None:
    plan = _plan()
    expected_plan_hash = _manual_hash(plan.model_dump(mode="json"))
    result_values = {
        "version": "structured-query-result.v1",
        "query_plan_version": "authorized-query-plan.v1",
        "plan_hash": expected_plan_hash,
        "records": (),
        "groups": (),
        "aggregates": (),
        "relation_paths": (),
        "source_versions": (),
        "scope_hash": "a" * 64,
        "schema_hash": _snapshot().schema_hash,
        "scanned_record_count": 0,
        "traversed_edge_count": 0,
        "truncated": False,
    }
    result = StructuredQueryResultV1(
        **result_values,
        result_hash=_manual_hash(
            {key: _jsonable(value) for key, value in result_values.items()}
        ),
    )

    artifact = StructuredQueryArtifactV1(
        version="structured-query-artifact.v1",
        plan=plan,
        plan_hash=expected_plan_hash,
        result=result,
    )

    assert authorized_query_plan_sha256(plan) == expected_plan_hash
    assert artifact.result.result_hash == result.result_hash

    with pytest.raises(ValueError, match="authorized_query_plan_hash_mismatch"):
        StructuredQueryArtifactV1(
            version="structured-query-artifact.v1",
            plan=plan,
            plan_hash="0" * 64,
            result=result,
        )


def _jsonable(value: object) -> object:
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _manual_hash(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
