"""Authorization-preserving record source and pure single-table operators."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from typing import Any
from uuid import UUID

from app.schemas.agent_task_spec_v2 import (
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    _OPERATORS_BY_FIELD_TYPE,
)
from app.schemas.authorized_query_plan import (
    AuthorizedRelationSpec,
    QueryPredicateGroup,
    QueryPredicateLeaf,
    QueryPredicateNode,
    StructuredFieldValue,
)
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    list_view_records,
    read_record_for_actor,
)
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)


class AuthorizedQueryDenied(ValueError):
    """Stable fail-closed refusal without resource labels or record values."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AuthorizedQueryContext:
    uow: Stage06PlatformUnitOfWork
    actor: Actor
    workspace_id: UUID
    base_id: UUID
    employee_id: UUID
    snapshot: AuthorizedSchemaSnapshot
    employee_table_ids: frozenset[UUID]
    employee_view_ids: frozenset[UUID]
    scope_view_ids: tuple[UUID, ...]
    allow_whole_table: bool


@dataclass(frozen=True, slots=True)
class AuthorizedRecord:
    record_id: UUID
    table_id: UUID
    values: tuple[StructuredFieldValue, ...]
    version: int
    source_view_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class AuthorizedRecordSet:
    table_id: UUID
    records: tuple[AuthorizedRecord, ...]
    scanned_record_count: int
    source_view_ids: tuple[UUID, ...]
    complete: bool = True


@dataclass(frozen=True, slots=True)
class AuthorizedEntityResolution:
    selector: str
    status: str
    record_ids: tuple[UUID, ...]


def build_authorized_query_context(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    base_id: UUID,
    employee_id: UUID,
    actor: Actor,
    snapshot: AuthorizedSchemaSnapshot,
    chat_authorized_view_ids: tuple[UUID, ...] | None,
    allow_whole_table: bool,
) -> AuthorizedQueryContext:
    workspace = uow.get_workspace(workspace_id)
    base = uow.get_base(base_id)
    employee = uow.get_digital_employee(employee_id)
    active_member = actor.actor_type == "user" and any(
        item.user_id == actor.actor_id and item.status == "active"
        for item in uow.list_workspace_members(workspace_id)
    )
    if (
        workspace is None
        or workspace.status != "active"
        or base is None
        or base.status != "active"
        or base.workspace_id != workspace_id
        or employee is None
        or employee.status != "active"
        or employee.workspace_id != workspace_id
        or employee.base_id != base_id
        or not active_member
        or not is_member_eligible_for_employee(uow, employee, actor.actor_id)
        or snapshot.workspace_id != workspace_id
        or snapshot.employee_id != employee_id
    ):
        raise AuthorizedQueryDenied("authorized_query_context_scope_denied")

    employee_table_ids = _strict_uuid_set(
        employee.accessible_tables,
        code="authorized_query_context_scope_denied",
    )
    employee_view_ids = _strict_uuid_set(
        employee.accessible_views,
        code="authorized_query_context_scope_denied",
    )
    snapshot_table_ids = {item.table_id for item in snapshot.tables}
    if snapshot_table_ids != employee_table_ids:
        raise AuthorizedQueryDenied("authorized_query_context_scope_denied")
    if allow_whole_table and chat_authorized_view_ids is not None:
        raise AuthorizedQueryDenied("authorized_query_view_scope_denied")

    if chat_authorized_view_ids is not None:
        if len(set(chat_authorized_view_ids)) != len(chat_authorized_view_ids):
            raise AuthorizedQueryDenied("authorized_query_view_scope_denied")
        if not set(chat_authorized_view_ids).issubset(employee_view_ids):
            raise AuthorizedQueryDenied("authorized_query_view_scope_denied")
        scope_view_ids = chat_authorized_view_ids
    elif allow_whole_table:
        scope_view_ids = ()
    else:
        scope_view_ids = tuple(sorted(employee_view_ids, key=str))

    for view_id in scope_view_ids:
        view = uow.get_view(view_id)
        if (
            view is None
            or view.status != "active"
            or view.base_id != base_id
            or view.table_id not in employee_table_ids
        ):
            raise AuthorizedQueryDenied("authorized_query_view_scope_denied")

    return AuthorizedQueryContext(
        uow=uow,
        actor=actor,
        workspace_id=workspace_id,
        base_id=base_id,
        employee_id=employee_id,
        snapshot=snapshot,
        employee_table_ids=frozenset(employee_table_ids),
        employee_view_ids=frozenset(employee_view_ids),
        scope_view_ids=scope_view_ids,
        allow_whole_table=allow_whole_table,
    )


def scan_authorized_records(
    *,
    context: AuthorizedQueryContext,
    table_id: UUID,
    required_field_ids: tuple[UUID, ...],
    max_scan_rows: int = 5000,
) -> AuthorizedRecordSet:
    if max_scan_rows < 1 or max_scan_rows > 5000:
        raise AuthorizedQueryDenied("authorized_query_scan_budget_invalid")
    table_spec = next(
        (item for item in context.snapshot.tables if item.table_id == table_id),
        None,
    )
    table = context.uow.get_table(table_id)
    if (
        table_spec is None
        or table_id not in context.employee_table_ids
        or table is None
        or table.status != "active"
        or table.base_id != context.base_id
    ):
        raise AuthorizedQueryDenied("authorized_query_table_scope_denied")
    if len(set(required_field_ids)) != len(required_field_ids):
        raise AuthorizedQueryDenied("authorized_query_field_scope_denied")
    fields_by_id = {item.field_id: item for item in table_spec.fields}
    if not set(required_field_ids).issubset(fields_by_id):
        raise AuthorizedQueryDenied("authorized_query_field_scope_denied")

    candidate_views = tuple(
        view_id
        for view_id in context.scope_view_ids
        if _view_table_id(context.uow, view_id) == table_id
    )
    if context.scope_view_ids and not candidate_views:
        raise AuthorizedQueryDenied("authorized_query_view_scope_denied")
    if candidate_views:
        source_views_by_record = _view_record_sources(context, candidate_views)
        candidate_ids = tuple(source_views_by_record)
    elif context.allow_whole_table:
        source_views_by_record = {}
        candidate_ids = tuple(item.id for item in context.uow.list_records(table_id))
    else:
        raise AuthorizedQueryDenied("authorized_query_view_scope_denied")

    records: list[AuthorizedRecord] = []
    for record_id in sorted(set(candidate_ids), key=str):
        raw = context.uow.get_record(record_id)
        if raw is None or raw.table_id != table_id or raw.record_status != "active":
            continue
        try:
            safe = read_record_for_actor(
                context.uow,
                record_id,
                actor=context.actor,
            )
        except PlatformValidationError as exc:
            raise AuthorizedQueryDenied("authorized_query_record_scope_denied") from exc
        if (
            safe.get("record_status") != "active"
            or safe.get("table_id") != str(table_id)
            or safe.get("version") != raw.version
            or not isinstance(safe.get("values"), dict)
        ):
            raise AuthorizedQueryDenied("authorized_query_record_scope_denied")
        values = safe["values"]
        projected = tuple(
            sorted(
                (
                    StructuredFieldValue(
                        field_id=field_id,
                        value=values.get(fields_by_id[field_id].key),
                    )
                    for field_id in required_field_ids
                ),
                key=lambda item: str(item.field_id),
            )
        )
        records.append(
            AuthorizedRecord(
                record_id=record_id,
                table_id=table_id,
                values=projected,
                version=raw.version,
                source_view_ids=tuple(
                    sorted(source_views_by_record.get(record_id, ()), key=str)
                ),
            )
        )
        if len(records) > max_scan_rows:
            raise AuthorizedQueryDenied("authorized_query_scan_budget_exceeded")
    return AuthorizedRecordSet(
        table_id=table_id,
        records=tuple(records),
        scanned_record_count=len(records),
        source_view_ids=tuple(sorted(candidate_views, key=str)),
        complete=True,
    )


def resolve_authorized_entities(
    records: AuthorizedRecordSet,
    *,
    selectors: tuple[str, ...],
    code_field_id: UUID,
    display_field_id: UUID,
    alias_field_ids: tuple[UUID, ...] = (),
) -> tuple[AuthorizedEntityResolution, ...]:
    if len(set(selectors)) != len(selectors):
        raise AuthorizedQueryDenied("authorized_query_entity_selector_duplicate")
    values_by_record = {
        item.record_id: _record_values(item) for item in records.records
    }
    resolutions: list[AuthorizedEntityResolution] = []
    for selector in selectors:
        normalized = selector.casefold()
        exact_codes = tuple(
            record_id
            for record_id, values in values_by_record.items()
            if _scalar_text(values.get(code_field_id)) == normalized
        )
        if exact_codes:
            matches = exact_codes
        else:
            matches = tuple(
                record_id
                for record_id, values in values_by_record.items()
                if _scalar_text(values.get(display_field_id)) == normalized
                or any(
                    normalized in _alias_values(values.get(field_id))
                    for field_id in alias_field_ids
                )
            )
        ordered = tuple(sorted(set(matches), key=str))
        resolutions.append(
            AuthorizedEntityResolution(
                selector=selector,
                status=(
                    "unresolved"
                    if not ordered
                    else "resolved" if len(ordered) == 1 else "ambiguous"
                ),
                record_ids=ordered,
            )
        )
    return tuple(resolutions)


def filter_records(
    records: AuthorizedRecordSet,
    *,
    predicate: QueryPredicateNode | None,
    snapshot: AuthorizedSchemaSnapshot,
) -> AuthorizedRecordSet:
    if predicate is None:
        return records
    fields_by_id = {
        field.field_id: field for table in snapshot.tables for field in table.fields
    }
    filtered = tuple(
        item
        for item in records.records
        if _matches_predicate(
            item,
            predicate,
            table_id=records.table_id,
            fields_by_id=fields_by_id,
        )
    )
    return AuthorizedRecordSet(
        table_id=records.table_id,
        records=filtered,
        scanned_record_count=records.scanned_record_count,
        source_view_ids=records.source_view_ids,
        complete=records.complete,
    )


def project_records(
    records: AuthorizedRecordSet,
    field_ids: tuple[UUID, ...],
) -> AuthorizedRecordSet:
    if len(set(field_ids)) != len(field_ids):
        raise AuthorizedQueryDenied("authorized_query_projection_duplicate")
    allowed = set(field_ids)
    projected: list[AuthorizedRecord] = []
    for record in records.records:
        available = {item.field_id for item in record.values}
        if not allowed.issubset(available):
            raise AuthorizedQueryDenied("authorized_query_projection_unavailable")
        projected.append(
            AuthorizedRecord(
                record_id=record.record_id,
                table_id=record.table_id,
                values=tuple(
                    item for item in record.values if item.field_id in allowed
                ),
                version=record.version,
                source_view_ids=record.source_view_ids,
            )
        )
    return AuthorizedRecordSet(
        table_id=records.table_id,
        records=tuple(projected),
        scanned_record_count=records.scanned_record_count,
        source_view_ids=records.source_view_ids,
        complete=records.complete,
    )


def _view_record_sources(
    context: AuthorizedQueryContext,
    view_ids: tuple[UUID, ...],
) -> dict[UUID, set[UUID]]:
    values: dict[UUID, set[UUID]] = {}
    for view_id in view_ids:
        for record_id in _single_view_record_ids(context, view_id):
            values.setdefault(record_id, set()).add(view_id)
    return values


def _single_view_record_ids(
    context: AuthorizedQueryContext,
    view_id: UUID,
) -> tuple[UUID, ...]:
    cursor: str | None = None
    values: list[UUID] = []
    while True:
        try:
            page = list_view_records(
                context.uow,
                view_id,
                actor=context.actor,
                limit=200,
                cursor=cursor,
            )
        except (PlatformValidationError, ValueError) as exc:
            raise AuthorizedQueryDenied("authorized_query_view_scope_denied") from exc
        for item in page.get("records", []):
            try:
                values.append(UUID(str(item["id"])))
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                raise AuthorizedQueryDenied(
                    "authorized_query_view_scope_denied"
                ) from exc
        if not page.get("has_more"):
            break
        cursor = page.get("next_cursor")
        if not isinstance(cursor, str) or not cursor:
            raise AuthorizedQueryDenied("authorized_query_view_scope_denied")
    return tuple(values)


def _view_table_id(
    uow: Stage06PlatformUnitOfWork,
    view_id: UUID,
) -> UUID | None:
    view = uow.get_view(view_id)
    return None if view is None else view.table_id


def _strict_uuid_set(values: object, *, code: str) -> set[UUID]:
    if not isinstance(values, list):
        raise AuthorizedQueryDenied(code)
    parsed: list[UUID] = []
    try:
        for value in values:
            if not isinstance(value, str):
                raise ValueError
            parsed.append(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AuthorizedQueryDenied(code) from exc
    if len(parsed) != len(set(parsed)):
        raise AuthorizedQueryDenied(code)
    return set(parsed)


def _record_values(record: AuthorizedRecord) -> dict[UUID, Any]:
    return {item.field_id: item.value for item in record.values}


def _matches_predicate(
    record: AuthorizedRecord,
    predicate: QueryPredicateNode,
    *,
    table_id: UUID,
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
) -> bool:
    if isinstance(predicate, QueryPredicateGroup):
        matches = (
            _matches_predicate(
                record,
                child,
                table_id=table_id,
                fields_by_id=fields_by_id,
            )
            for child in predicate.children
        )
        return all(matches) if predicate.operator == "and" else any(matches)
    if not isinstance(predicate, QueryPredicateLeaf):
        raise AuthorizedQueryDenied("authorized_query_predicate_invalid")
    field = fields_by_id.get(predicate.field_id)
    if field is None or field.table_id != table_id or predicate.table_id != table_id:
        raise AuthorizedQueryDenied("authorized_query_predicate_scope_denied")
    if predicate.operator not in _OPERATORS_BY_FIELD_TYPE[field.field_type]:
        raise AuthorizedQueryDenied("authorized_query_operator_type_invalid")
    value = _record_values(record).get(predicate.field_id)
    return _typed_match(
        value,
        operator=predicate.operator,
        expected=predicate.value,
        field_type=field.field_type,
    )


def _typed_match(
    value: object,
    *,
    operator: str,
    expected: object,
    field_type: str,
) -> bool:
    empty = value is None or value == "" or value == [] or value == {}
    if operator == "is_empty":
        return empty
    if operator == "is_not_empty":
        return not empty
    if operator == "is_true":
        return value is True
    if operator == "is_false":
        return value is False
    if empty:
        return False
    if operator == "contains_record":
        return _contains_record(value, expected)
    if field_type in {"date", "datetime"}:
        return _date_match(value, operator, expected)
    if operator == "between":
        bounds = _two_values(expected)
        return (
            bounds is not None
            and _ordered_compare(bounds[0], value, "lte")
            and _ordered_compare(value, bounds[1], "lte")
        )
    if operator in {"gt", "gte", "lt", "lte"}:
        return _ordered_compare(value, expected, operator)
    if operator == "contains":
        if isinstance(value, str) and isinstance(expected, str):
            return expected.casefold() in value.casefold()
        if isinstance(value, (list, tuple, set)):
            return expected in value
        if isinstance(value, dict):
            return expected in value or expected in value.values()
        return (
            isinstance(expected, str)
            and expected.casefold()
            in json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            ).casefold()
        )
    if operator == "starts_with":
        return (
            isinstance(value, str)
            and isinstance(expected, str)
            and value.casefold().startswith(expected.casefold())
        )
    if operator in {"in", "not_in"}:
        expected_values = _sequence(expected)
        matched = any(_equal(value, item) for item in expected_values)
        return matched if operator == "in" else not matched
    if operator in {"contains_any", "contains_all"}:
        actual = _sequence(value)
        wanted = _sequence(expected)
        matched = (
            any(any(_equal(item, candidate) for candidate in actual) for item in wanted)
            if operator == "contains_any"
            else all(
                any(_equal(item, candidate) for candidate in actual) for item in wanted
            )
        )
        return matched
    if operator in {"eq", "ne"}:
        matched = _equal(value, expected)
        return matched if operator == "eq" else not matched
    raise AuthorizedQueryDenied("authorized_query_operator_unsupported")


def _date_match(value: object, operator: str, expected: object) -> bool:
    actual = _parse_temporal(value)
    if actual is None:
        return False
    if operator in {"on", "eq", "ne", "before", "after"}:
        target = _parse_temporal(expected)
        if target is None:
            return False
        if operator in {"on", "eq"}:
            return actual == target
        if operator == "ne":
            return actual != target
        return actual < target if operator == "before" else actual > target
    if operator in {"between", "relative_range"}:
        bounds = _range_values(expected)
        if bounds is None:
            return False
        start = _parse_temporal(bounds[0])
        end = _parse_temporal(bounds[1])
        return start is not None and end is not None and start <= actual <= end
    raise AuthorizedQueryDenied("authorized_query_operator_unsupported")


def _parse_temporal(value: object) -> datetime | date | None:
    if not isinstance(value, str):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return (
            datetime.fromisoformat(normalized)
            if "T" in normalized
            else date.fromisoformat(normalized)
        )
    except ValueError:
        return None


def _range_values(value: object) -> tuple[object, object] | None:
    if isinstance(value, dict):
        start = value.get("start_utc", value.get("start"))
        end = value.get("end_utc", value.get("end"))
        return None if start is None or end is None else (start, end)
    return _two_values(value)


def _two_values(value: object) -> tuple[object, object] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[0], value[1]
    return None


def _ordered_compare(left: object, right: object, operator: str) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if not (
        isinstance(left, (int, float, str))
        and isinstance(right, (int, float, str))
        and type(left) is type(right)
    ):
        return False
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    if operator == "lt":
        return left < right
    return left <= right


def _equal(left: object, right: object) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    return left == right


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return ()


def _contains_record(value: object, expected: object) -> bool:
    expected_id = str(expected)
    return any(
        (isinstance(item, dict) and str(item.get("id")) == expected_id)
        or str(item) == expected_id
        for item in _sequence(value)
    )


def _scalar_text(value: object) -> str | None:
    return value.casefold() if isinstance(value, str) else None


def _alias_values(value: object) -> frozenset[str]:
    return frozenset(
        item.casefold() for item in _sequence(value) if isinstance(item, str)
    )


__all__ = [
    "AuthorizedEntityResolution",
    "AuthorizedQueryContext",
    "AuthorizedQueryDenied",
    "AuthorizedRecord",
    "AuthorizedRecordSet",
    "build_authorized_query_context",
    "build_authorized_relation_catalog",
    "filter_records",
    "project_records",
    "resolve_authorized_entities",
    "scan_authorized_records",
]
