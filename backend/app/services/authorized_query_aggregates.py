"""Deterministic grouping, aggregation, sorting and presentation limit."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import cmp_to_key
import json
import math
import unicodedata
from uuid import UUID

from app.schemas.agent_task_spec_v2 import AuthorizedFieldSpec, AuthorizedSchemaSnapshot
from app.schemas.authorized_query_plan import (
    QueryAggregateSpec,
    QueryHavingSpec,
    QueryPredicateGroup,
    QueryPredicateLeaf,
    QueryPredicateNode,
    QuerySortSpec,
    StructuredAggregate,
    StructuredGroup,
)
from app.services.authorized_query_records import (
    AuthorizedQueryDenied,
    AuthorizedRecord,
    AuthorizedRecordSet,
    filter_records,
)


@dataclass(frozen=True, slots=True)
class AuthorizedAggregateResult:
    records: tuple[AuthorizedRecord, ...]
    groups: tuple[StructuredGroup, ...]
    aggregates: tuple[StructuredAggregate, ...]
    input_record_count: int
    truncated: bool


def execute_authorized_aggregates(
    *,
    records: AuthorizedRecordSet,
    group_by_field_ids: tuple[UUID, ...],
    aggregates: tuple[QueryAggregateSpec, ...],
    sort_rules: tuple[QuerySortSpec, ...],
    limit: int | None,
    snapshot: AuthorizedSchemaSnapshot,
) -> AuthorizedAggregateResult:
    if not records.complete:
        raise AuthorizedQueryDenied("authorized_query_incomplete_input")
    if limit is not None and (limit < 1 or limit > 5000):
        raise AuthorizedQueryDenied("authorized_query_limit_invalid")
    fields_by_id = {
        field.field_id: field for table in snapshot.tables for field in table.fields
    }
    _validate_group_fields(records, group_by_field_ids, fields_by_id)
    grouped_records = _group_records(records.records, group_by_field_ids)
    groups = _structured_groups(grouped_records) if group_by_field_ids else ()

    aggregate_values: list[StructuredAggregate] = []
    having_key_sets: list[set[str]] = []
    contributing_record_ids: set[UUID] = set()
    for spec in aggregates:
        if spec.table_id != records.table_id:
            raise AuthorizedQueryDenied("authorized_query_aggregate_scope_denied")
        _validate_aggregate_inputs(records, spec, fields_by_id)
        filtered = (
            records
            if spec.filter_predicate is None
            else filter_records(
                records,
                predicate=spec.filter_predicate,
                snapshot=snapshot,
            )
        )
        spec_groups = _group_records(
            filtered.records,
            spec.group_by_field_ids,
        )
        if not spec.group_by_field_ids:
            spec_groups = {_canonical_group_key(()): ((), filtered.records)}
        accepted_having_keys: set[str] = set()
        for canonical_group_key in sorted(spec_groups):
            group_key, grouped_items = spec_groups[canonical_group_key]
            value = _aggregate_value(spec, grouped_items, fields_by_id)
            if spec.having is not None and not _having_matches(value, spec.having):
                continue
            accepted_having_keys.add(canonical_group_key)
            contributing_record_ids.update(item.record_id for item in grouped_items)
            aggregate_values.append(
                StructuredAggregate(
                    aggregate_id=spec.aggregate_id,
                    group_key=None if not group_key else list(group_key),
                    value=value,
                )
            )
        if spec.having is not None:
            having_key_sets.append(accepted_having_keys)

    eligible_group_keys: set[str] | None = None
    if having_key_sets:
        eligible_group_keys = set.intersection(*having_key_sets)
        groups = tuple(
            item
            for item in groups
            if _canonical_group_key(item.group_key) in eligible_group_keys
        )
        aggregate_values = [
            item
            for item in aggregate_values
            if item.group_key is None
            or _canonical_group_key(tuple(item.group_key)) in eligible_group_keys
        ]

    ordered_records = (
        tuple(
            item
            for item in records.records
            if item.record_id in contributing_record_ids
        )
        if aggregates
        else tuple(records.records)
    )
    if eligible_group_keys is not None and group_by_field_ids:
        ordered_records = tuple(
            item
            for item in ordered_records
            if _canonical_group_key(_record_group_key(item, group_by_field_ids))
            in eligible_group_keys
        )
    aggregate_sorts = tuple(
        item for item in sort_rules if item.aggregate_id is not None
    )
    field_sorts = tuple(item for item in sort_rules if item.field_id is not None)
    if aggregate_sorts and field_sorts:
        raise AuthorizedQueryDenied("authorized_query_sort_target_mixed")
    truncated = False
    if aggregate_sorts:
        groups = _sort_groups_by_aggregates(
            groups,
            tuple(aggregate_values),
            aggregate_sorts,
        )
        if limit is not None and len(groups) > limit:
            groups = groups[:limit]
            truncated = True
        selected_keys = {_canonical_group_key(item.group_key) for item in groups}
        aggregate_values = [
            item
            for item in aggregate_values
            if item.group_key is None
            or _canonical_group_key(tuple(item.group_key)) in selected_keys
        ]
        ordered_records = tuple(
            item
            for item in ordered_records
            if _canonical_group_key(_record_group_key(item, group_by_field_ids))
            in selected_keys
        )
    else:
        if field_sorts:
            ordered_records = _sort_records(
                ordered_records,
                field_sorts,
                fields_by_id,
            )
        if limit is not None:
            if group_by_field_ids and not field_sorts:
                if len(groups) > limit:
                    groups = groups[:limit]
                    truncated = True
                selected_keys = {
                    _canonical_group_key(item.group_key) for item in groups
                }
                aggregate_values = [
                    item
                    for item in aggregate_values
                    if item.group_key is None
                    or _canonical_group_key(tuple(item.group_key)) in selected_keys
                ]
                ordered_records = tuple(
                    item
                    for item in ordered_records
                    if _canonical_group_key(_record_group_key(item, group_by_field_ids))
                    in selected_keys
                )
            elif len(ordered_records) > limit:
                ordered_records = ordered_records[:limit]
                truncated = True

    return AuthorizedAggregateResult(
        records=ordered_records,
        groups=groups,
        aggregates=tuple(
            sorted(
                aggregate_values,
                key=lambda item: (
                    item.aggregate_id,
                    _canonical_group_key(
                        () if item.group_key is None else tuple(item.group_key)
                    ),
                ),
            )
        ),
        input_record_count=len(records.records),
        truncated=truncated,
    )


def _validate_group_fields(
    records: AuthorizedRecordSet,
    field_ids: tuple[UUID, ...],
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
) -> None:
    if len(set(field_ids)) != len(field_ids):
        raise AuthorizedQueryDenied("authorized_query_group_field_duplicate")
    for field_id in field_ids:
        field = fields_by_id.get(field_id)
        if field is None or field.table_id != records.table_id:
            raise AuthorizedQueryDenied("authorized_query_group_field_unavailable")
    for record in records.records:
        available = {item.field_id for item in record.values}
        if not set(field_ids).issubset(available):
            raise AuthorizedQueryDenied("authorized_query_group_field_unavailable")


def _validate_aggregate_inputs(
    records: AuthorizedRecordSet,
    spec: QueryAggregateSpec,
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
) -> None:
    _validate_group_fields(records, spec.group_by_field_ids, fields_by_id)
    required: set[UUID] = set(spec.group_by_field_ids)
    if spec.field_id is not None:
        field = fields_by_id.get(spec.field_id)
        if field is None or field.table_id != records.table_id:
            raise AuthorizedQueryDenied("authorized_query_aggregate_field_unavailable")
        required.add(spec.field_id)
    if spec.filter_predicate is not None:
        required.update(_predicate_field_ids(spec.filter_predicate))
    for record in records.records:
        available = {item.field_id for item in record.values}
        if not required.issubset(available):
            raise AuthorizedQueryDenied("authorized_query_aggregate_field_unavailable")


def _predicate_field_ids(predicate: QueryPredicateNode) -> set[UUID]:
    if isinstance(predicate, QueryPredicateLeaf):
        return {predicate.field_id}
    if not isinstance(predicate, QueryPredicateGroup):
        raise AuthorizedQueryDenied("authorized_query_predicate_invalid")
    return {
        field_id
        for child in predicate.children
        for field_id in _predicate_field_ids(child)
    }


def _group_records(
    records: tuple[AuthorizedRecord, ...],
    field_ids: tuple[UUID, ...],
) -> dict[str, tuple[tuple[object, ...], tuple[AuthorizedRecord, ...]]]:
    if not field_ids:
        return {}
    grouped: dict[str, tuple[tuple[object, ...], list[AuthorizedRecord]]] = {}
    for record in records:
        key = _record_group_key(record, field_ids)
        canonical = _canonical_group_key(key)
        if canonical not in grouped:
            grouped[canonical] = (key, [])
        grouped[canonical][1].append(record)
    return {
        canonical: (
            key,
            tuple(sorted(items, key=lambda item: str(item.record_id))),
        )
        for canonical, (key, items) in grouped.items()
    }


def _record_group_key(
    record: AuthorizedRecord,
    field_ids: tuple[UUID, ...],
) -> tuple[object, ...]:
    values = {item.field_id: item.value for item in record.values}
    return tuple(values[field_id] for field_id in field_ids)


def _structured_groups(
    grouped: dict[str, tuple[tuple[object, ...], tuple[AuthorizedRecord, ...]]],
) -> tuple[StructuredGroup, ...]:
    return tuple(
        StructuredGroup(
            group_key=grouped[canonical][0],
            record_ids=tuple(item.record_id for item in grouped[canonical][1]),
        )
        for canonical in sorted(grouped)
    )


def _aggregate_value(
    spec: QueryAggregateSpec,
    records: tuple[AuthorizedRecord, ...],
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
) -> object:
    if spec.function == "count":
        return len(records)
    if spec.field_id is None:
        raise AuthorizedQueryDenied("authorized_query_aggregate_field_unavailable")
    values = [
        value
        for record in records
        if (value := _record_value(record, spec.field_id)) is not None
    ]
    if spec.function == "count_non_null":
        return len(values)
    if spec.function == "count_distinct":
        field = fields_by_id[spec.field_id]
        return len(
            {
                (
                    _decimal(item)
                    if field.field_type == "number"
                    else _canonical_value(item)
                )
                for item in values
            }
        )
    if not values:
        return None
    if spec.function in {"sum", "average"}:
        decimals = tuple(_decimal(item) for item in values)
        total = sum(decimals, Decimal(0))
        result = total if spec.function == "sum" else total / Decimal(len(decimals))
        return _json_number(result)
    if spec.function in {"minimum", "maximum"}:
        field = fields_by_id[spec.field_id]
        ordered = sorted(values, key=lambda item: _aggregate_order_value(item, field))
        return ordered[0] if spec.function == "minimum" else ordered[-1]
    raise AuthorizedQueryDenied("authorized_query_aggregate_function_unsupported")


def _record_value(record: AuthorizedRecord, field_id: UUID) -> object:
    return next(item.value for item in record.values if item.field_id == field_id)


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise AuthorizedQueryDenied("authorized_query_aggregate_value_invalid")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AuthorizedQueryDenied("authorized_query_aggregate_value_invalid") from exc
    if not result.is_finite():
        raise AuthorizedQueryDenied("authorized_query_aggregate_value_invalid")
    return result


def _json_number(value: Decimal) -> int | float | str:
    if value == value.to_integral_value():
        return int(value)
    result = float(value)
    return result if math.isfinite(result) else format(value, "f")


def _aggregate_order_value(value: object, field: AuthorizedFieldSpec) -> object:
    if field.field_type == "number":
        return _decimal(value)
    return _canonical_sort_value(value)


def _having_matches(value: object, having: QueryHavingSpec) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    expected = having.value
    if having.operator == "eq":
        return value == expected
    if having.operator == "ne":
        return value != expected
    if having.operator == "gt":
        return value > expected
    if having.operator == "gte":
        return value >= expected
    if having.operator == "lt":
        return value < expected
    return value <= expected


def _sort_records(
    records: tuple[AuthorizedRecord, ...],
    rules: tuple[QuerySortSpec, ...],
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
) -> tuple[AuthorizedRecord, ...]:
    for rule in rules:
        if rule.field_id is None:
            raise AuthorizedQueryDenied("authorized_query_sort_field_unavailable")
        field = fields_by_id.get(rule.field_id)
        if field is None or field.table_id != rule.table_id:
            raise AuthorizedQueryDenied("authorized_query_sort_field_unavailable")
        if records and rule.table_id != records[0].table_id:
            raise AuthorizedQueryDenied("authorized_query_sort_field_unavailable")
        if any(
            rule.field_id not in {item.field_id for item in record.values}
            for record in records
        ):
            raise AuthorizedQueryDenied("authorized_query_sort_field_unavailable")

    def compare(left: AuthorizedRecord, right: AuthorizedRecord) -> int:
        for rule in rules:
            if rule.field_id is None or rule.table_id != left.table_id:
                raise AuthorizedQueryDenied("authorized_query_sort_field_unavailable")
            field = fields_by_id.get(rule.field_id)
            if field is None or field.table_id != left.table_id:
                raise AuthorizedQueryDenied("authorized_query_sort_field_unavailable")
            left_value = _record_value(left, rule.field_id)
            right_value = _record_value(right, rule.field_id)
            result = _compare_values(left_value, right_value, rule, field)
            if result:
                return result
        return (str(left.record_id) > str(right.record_id)) - (
            str(left.record_id) < str(right.record_id)
        )

    return tuple(sorted(records, key=cmp_to_key(compare)))


def _sort_groups_by_aggregates(
    groups: tuple[StructuredGroup, ...],
    aggregates: tuple[StructuredAggregate, ...],
    rules: tuple[QuerySortSpec, ...],
) -> tuple[StructuredGroup, ...]:
    values = {
        (
            item.aggregate_id,
            _canonical_group_key(tuple(item.group_key or ())),
        ): item.value
        for item in aggregates
    }

    def compare(left: StructuredGroup, right: StructuredGroup) -> int:
        left_key = _canonical_group_key(left.group_key)
        right_key = _canonical_group_key(right.group_key)
        for rule in rules:
            if rule.aggregate_id is None:
                raise AuthorizedQueryDenied("authorized_query_sort_aggregate_unknown")
            result = _compare_values(
                values.get((rule.aggregate_id, left_key)),
                values.get((rule.aggregate_id, right_key)),
                rule,
                None,
            )
            if result:
                return result
        return (left_key > right_key) - (left_key < right_key)

    return tuple(sorted(groups, key=cmp_to_key(compare)))


def _compare_values(
    left: object,
    right: object,
    rule: QuerySortSpec,
    field: AuthorizedFieldSpec | None,
) -> int:
    left_null = left is None
    right_null = right is None
    if left_null != right_null:
        if rule.nulls == "first":
            return -1 if left_null else 1
        return 1 if left_null else -1
    if left_null:
        return 0
    if rule.mode == "field_order":
        if field is None or not field.choices:
            raise AuthorizedQueryDenied("authorized_query_sort_mode_invalid")
        try:
            left_value = field.choices.index(left)
            right_value = field.choices.index(right)
        except ValueError as exc:
            raise AuthorizedQueryDenied("authorized_query_sort_value_invalid") from exc
    else:
        if (field is not None and field.field_type == "number") or (
            field is None
            and isinstance(left, (int, float))
            and not isinstance(left, bool)
            and isinstance(right, (int, float))
            and not isinstance(right, bool)
        ):
            left_value = _decimal(left)
            right_value = _decimal(right)
        else:
            left_value = _canonical_sort_value(left)
            right_value = _canonical_sort_value(right)
    result = (left_value > right_value) - (left_value < right_value)
    return -result if rule.direction == "desc" else result


def _canonical_sort_value(value: object) -> tuple[str, str]:
    if isinstance(value, bool):
        return "bool", "1" if value else "0"
    if isinstance(value, (int, float)):
        return "number", format(_decimal(value), "f")
    if isinstance(value, str):
        return "text", unicodedata.normalize("NFC", value).casefold()
    return "json", _canonical_value(value)


def _canonical_group_key(value: tuple[object, ...]) -> str:
    return _canonical_value(list(value))


def _canonical_value(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


__all__ = [
    "AuthorizedAggregateResult",
    "execute_authorized_aggregates",
]
