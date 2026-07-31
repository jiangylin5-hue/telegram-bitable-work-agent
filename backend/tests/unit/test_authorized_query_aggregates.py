from __future__ import annotations

from uuid import UUID

import pytest

from app.schemas.agent_task_spec_v2 import (
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    authorized_schema_sha256,
)
from app.schemas.authorized_query_plan import (
    QueryAggregateSpec,
    QueryHavingSpec,
    QuerySortSpec,
    StructuredFieldValue,
)
from app.services.authorized_query_aggregates import (
    execute_authorized_aggregates,
)
from app.services.authorized_query_records import (
    AuthorizedQueryDenied,
    AuthorizedRecord,
    AuthorizedRecordSet,
)


WORKSPACE_ID = UUID("40000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("40000000-0000-4000-8000-000000000002")
BASE_ID = UUID("40000000-0000-4000-8000-000000000003")
TABLE_ID = UUID("40000000-0000-4000-8000-000000000010")
CATEGORY_ID = UUID("40000000-0000-4000-8000-000000000101")
VALUE_ID = UUID("40000000-0000-4000-8000-000000000102")
LABEL_ID = UUID("40000000-0000-4000-8000-000000000103")
PRIORITY_ID = UUID("40000000-0000-4000-8000-000000000104")
PROJECT_LINK_ID = UUID("40000000-0000-4000-8000-000000000105")


def _field(
    field_id: UUID,
    key: str,
    field_type: str,
    *,
    choices: tuple[str, ...] = (),
) -> AuthorizedFieldSpec:
    return AuthorizedFieldSpec(
        field_id=field_id,
        table_id=TABLE_ID,
        key=key,
        name=key,
        field_type=field_type,
        aliases=(),
        choices=choices,
        writable=True,
    )


def _snapshot() -> AuthorizedSchemaSnapshot:
    table = AuthorizedTableSpec(
        table_id=TABLE_ID,
        base_id=BASE_ID,
        key="metrics",
        name="Metrics",
        aliases=(),
        fields=(
            _field(CATEGORY_ID, "category", "single_select", choices=("A", "B")),
            _field(VALUE_ID, "value", "number"),
            _field(LABEL_ID, "label", "text"),
            _field(
                PRIORITY_ID,
                "priority",
                "single_select",
                choices=("high", "medium", "low"),
            ),
            _field(PROJECT_LINK_ID, "project_link", "linked_record"),
        ),
    )
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": "d" * 64,
        "tables": (table,),
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _record(index: int, values: dict[UUID, object]) -> AuthorizedRecord:
    return AuthorizedRecord(
        record_id=UUID(f"40000000-0000-4000-8000-{index:012d}"),
        table_id=TABLE_ID,
        values=tuple(
            StructuredFieldValue(field_id=field_id, value=value)
            for field_id, value in sorted(values.items(), key=lambda item: str(item[0]))
        ),
        version=1,
        source_view_ids=(),
    )


def _records() -> AuthorizedRecordSet:
    records = (
        _record(
            1,
            {
                CATEGORY_ID: "A",
                VALUE_ID: 10,
                LABEL_ID: "阿尔法",
                PRIORITY_ID: "high",
            },
        ),
        _record(
            2,
            {
                CATEGORY_ID: "A",
                VALUE_ID: 10,
                LABEL_ID: "Beta",
                PRIORITY_ID: "low",
            },
        ),
        _record(
            3,
            {
                CATEGORY_ID: "B",
                VALUE_ID: None,
                LABEL_ID: "éclair",
                PRIORITY_ID: "medium",
            },
        ),
        _record(
            4,
            {
                CATEGORY_ID: "B",
                VALUE_ID: 20,
                LABEL_ID: None,
                PRIORITY_ID: "high",
            },
        ),
    )
    return AuthorizedRecordSet(
        table_id=TABLE_ID,
        records=records,
        scanned_record_count=4,
        source_view_ids=(),
        complete=True,
    )


def _aggregate(
    function: str,
    *,
    aggregate_id: str = "aggregate-value",
    field_id: UUID | None = VALUE_ID,
    group_by: tuple[UUID, ...] = (),
    having: QueryHavingSpec | None = None,
) -> QueryAggregateSpec:
    return QueryAggregateSpec(
        aggregate_id=aggregate_id,
        output_key=aggregate_id.replace("aggregate-", ""),
        function=function,
        table_id=TABLE_ID,
        field_id=None if function == "count" else field_id,
        filter_predicate=None,
        group_by_field_ids=group_by,
        having=having,
    )


@pytest.mark.parametrize(
    ("function", "expected"),
    (
        ("count", 4),
        ("count_non_null", 3),
        ("count_distinct", 2),
    ),
)
def test_count_functions_are_not_conflated(function: str, expected: int) -> None:
    result = execute_authorized_aggregates(
        records=_records(),
        group_by_field_ids=(),
        aggregates=(_aggregate(function),),
        sort_rules=(),
        limit=None,
        snapshot=_snapshot(),
    )

    assert result.aggregates[0].value == expected


@pytest.mark.parametrize(
    ("function", "expected"),
    (
        ("sum", 40),
        ("average", 40 / 3),
        ("minimum", 10),
        ("maximum", 20),
    ),
)
def test_numeric_aggregates_use_non_null_values(
    function: str, expected: object
) -> None:
    result = execute_authorized_aggregates(
        records=_records(),
        group_by_field_ids=(),
        aggregates=(_aggregate(function),),
        sort_rules=(),
        limit=None,
        snapshot=_snapshot(),
    )

    assert result.aggregates[0].value == pytest.approx(expected)


def test_numeric_count_distinct_normalizes_integer_and_float_equivalents() -> None:
    records = AuthorizedRecordSet(
        table_id=TABLE_ID,
        records=(
            _record(1, {VALUE_ID: 1}),
            _record(2, {VALUE_ID: 1.0}),
        ),
        scanned_record_count=2,
        source_view_ids=(),
        complete=True,
    )

    result = execute_authorized_aggregates(
        records=records,
        group_by_field_ids=(),
        aggregates=(_aggregate("count_distinct"),),
        sort_rules=(),
        limit=None,
        snapshot=_snapshot(),
    )

    assert result.aggregates[0].value == 1


def test_empty_input_uses_sql_like_null_semantics() -> None:
    empty = AuthorizedRecordSet(
        table_id=TABLE_ID,
        records=(),
        scanned_record_count=0,
        source_view_ids=(),
        complete=True,
    )
    result = execute_authorized_aggregates(
        records=empty,
        group_by_field_ids=(),
        aggregates=(
            _aggregate("count", aggregate_id="aggregate-count"),
            _aggregate("sum", aggregate_id="aggregate-sum"),
            _aggregate("average", aggregate_id="aggregate-average"),
            _aggregate("minimum", aggregate_id="aggregate-min"),
            _aggregate("maximum", aggregate_id="aggregate-max"),
        ),
        sort_rules=(),
        limit=None,
        snapshot=_snapshot(),
    )

    assert {item.aggregate_id: item.value for item in result.aggregates} == {
        "aggregate-count": 0,
        "aggregate-sum": None,
        "aggregate-average": None,
        "aggregate-min": None,
        "aggregate-max": None,
    }


def test_multi_group_order_and_record_ids_are_stable() -> None:
    result = execute_authorized_aggregates(
        records=_records(),
        group_by_field_ids=(CATEGORY_ID, PRIORITY_ID),
        aggregates=(
            _aggregate(
                "count",
                aggregate_id="aggregate-count",
                group_by=(CATEGORY_ID, PRIORITY_ID),
            ),
        ),
        sort_rules=(),
        limit=None,
        snapshot=_snapshot(),
    )

    assert [item.group_key for item in result.groups] == [
        ("A", "high"),
        ("A", "low"),
        ("B", "high"),
        ("B", "medium"),
    ]
    assert all(
        item.record_ids == tuple(sorted(item.record_ids, key=str))
        for item in result.groups
    )


def test_linked_record_group_key_uses_canonical_json_not_python_hashability() -> None:
    project_id = "40000000-0000-4000-8000-000000000901"
    records = AuthorizedRecordSet(
        table_id=TABLE_ID,
        records=(
            _record(1, {PROJECT_LINK_ID: [{"id": project_id, "label": "Atlas"}]}),
            _record(2, {PROJECT_LINK_ID: [{"label": "Atlas", "id": project_id}]}),
        ),
        scanned_record_count=2,
        source_view_ids=(),
        complete=True,
    )

    result = execute_authorized_aggregates(
        records=records,
        group_by_field_ids=(PROJECT_LINK_ID,),
        aggregates=(
            _aggregate(
                "count",
                aggregate_id="aggregate-linked-count",
                group_by=(PROJECT_LINK_ID,),
            ),
        ),
        sort_rules=(),
        limit=None,
        snapshot=_snapshot(),
    )

    assert len(result.groups) == 1
    assert result.aggregates[0].value == 2


def test_having_is_applied_after_group_aggregate() -> None:
    result = execute_authorized_aggregates(
        records=_records(),
        group_by_field_ids=(CATEGORY_ID,),
        aggregates=(
            _aggregate(
                "count_non_null",
                aggregate_id="aggregate-non-null",
                group_by=(CATEGORY_ID,),
                having=QueryHavingSpec(operator="gte", value=2),
            ),
        ),
        sort_rules=(),
        limit=None,
        snapshot=_snapshot(),
    )

    assert [(item.group_key, item.value) for item in result.aggregates] == [(["A"], 2)]
    assert {_value(item, CATEGORY_ID) for item in result.records} == {"A"}


def test_unicode_field_sort_and_explicit_null_placement_are_stable() -> None:
    ascending = QuerySortSpec(
        sort_id="sort-label-asc",
        table_id=TABLE_ID,
        field_id=LABEL_ID,
        aggregate_id=None,
        mode="natural",
        direction="asc",
        nulls="last",
    )
    descending = ascending.model_copy(
        update={"sort_id": "sort-label-desc", "direction": "desc", "nulls": "first"}
    )

    asc = execute_authorized_aggregates(
        records=_records(),
        group_by_field_ids=(),
        aggregates=(),
        sort_rules=(ascending,),
        limit=None,
        snapshot=_snapshot(),
    )
    desc = execute_authorized_aggregates(
        records=_records(),
        group_by_field_ids=(),
        aggregates=(),
        sort_rules=(descending,),
        limit=None,
        snapshot=_snapshot(),
    )

    assert [_value(item, LABEL_ID) for item in asc.records] == [
        "Beta",
        "éclair",
        "阿尔法",
        None,
    ]
    assert [_value(item, LABEL_ID) for item in desc.records] == [
        None,
        "阿尔法",
        "éclair",
        "Beta",
    ]


def test_enum_field_order_is_not_lexicographic() -> None:
    sort = QuerySortSpec(
        sort_id="sort-priority",
        table_id=TABLE_ID,
        field_id=PRIORITY_ID,
        aggregate_id=None,
        mode="field_order",
        direction="asc",
        nulls="last",
    )

    result = execute_authorized_aggregates(
        records=_records(),
        group_by_field_ids=(),
        aggregates=(),
        sort_rules=(sort,),
        limit=None,
        snapshot=_snapshot(),
    )

    assert [_value(item, PRIORITY_ID) for item in result.records] == [
        "high",
        "high",
        "medium",
        "low",
    ]


def test_number_sort_uses_numeric_not_string_order() -> None:
    records = AuthorizedRecordSet(
        table_id=TABLE_ID,
        records=(
            _record(1, {VALUE_ID: 10}),
            _record(2, {VALUE_ID: 2}),
        ),
        scanned_record_count=2,
        source_view_ids=(),
        complete=True,
    )
    sort = QuerySortSpec(
        sort_id="sort-number",
        table_id=TABLE_ID,
        field_id=VALUE_ID,
        aggregate_id=None,
        mode="natural",
        direction="asc",
        nulls="last",
    )

    result = execute_authorized_aggregates(
        records=records,
        group_by_field_ids=(),
        aggregates=(),
        sort_rules=(sort,),
        limit=None,
        snapshot=_snapshot(),
    )

    assert [_value(item, VALUE_ID) for item in result.records] == [2, 10]


def test_missing_sort_field_fails_closed() -> None:
    records = AuthorizedRecordSet(
        table_id=TABLE_ID,
        records=(_record(1, {VALUE_ID: 10}), _record(2, {LABEL_ID: "Beta"})),
        scanned_record_count=2,
        source_view_ids=(),
        complete=True,
    )
    sort = QuerySortSpec(
        sort_id="sort-number",
        table_id=TABLE_ID,
        field_id=VALUE_ID,
        aggregate_id=None,
        mode="natural",
        direction="asc",
        nulls="last",
    )

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_sort_field_unavailable$",
    ):
        execute_authorized_aggregates(
            records=records,
            group_by_field_ids=(),
            aggregates=(),
            sort_rules=(sort,),
            limit=None,
            snapshot=_snapshot(),
        )


def test_top_n_is_applied_after_complete_aggregate_calculation() -> None:
    aggregate = _aggregate(
        "count_non_null",
        aggregate_id="aggregate-non-null",
        group_by=(CATEGORY_ID,),
    )
    sort = QuerySortSpec(
        sort_id="sort-count",
        table_id=None,
        field_id=None,
        aggregate_id=aggregate.aggregate_id,
        mode="natural",
        direction="desc",
        nulls="last",
    )

    result = execute_authorized_aggregates(
        records=_records(),
        group_by_field_ids=(CATEGORY_ID,),
        aggregates=(aggregate,),
        sort_rules=(sort,),
        limit=1,
        snapshot=_snapshot(),
    )

    assert [(item.group_key, item.value) for item in result.aggregates] == [(["A"], 2)]
    assert [item.group_key for item in result.groups] == [("A",)]
    assert len(result.records) == 2
    assert result.input_record_count == 4


def test_missing_group_field_fails_closed_instead_of_becoming_null_group() -> None:
    records = AuthorizedRecordSet(
        table_id=TABLE_ID,
        records=(_record(1, {VALUE_ID: 10}),),
        scanned_record_count=1,
        source_view_ids=(),
        complete=True,
    )

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_group_field_unavailable$",
    ):
        execute_authorized_aggregates(
            records=records,
            group_by_field_ids=(CATEGORY_ID,),
            aggregates=(
                _aggregate(
                    "count",
                    aggregate_id="aggregate-count",
                    group_by=(CATEGORY_ID,),
                ),
            ),
            sort_rules=(),
            limit=None,
            snapshot=_snapshot(),
        )


def _value(record: AuthorizedRecord, field_id: UUID) -> object:
    return next(item.value for item in record.values if item.field_id == field_id)
