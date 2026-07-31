"""Semantic validation for the restricted Stage12-C QueryPlan AST."""

from __future__ import annotations

from uuid import UUID

from app.schemas.agent_task_spec_v2 import (
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    _OPERATORS_BY_FIELD_TYPE,
)
from app.schemas.authorized_query_plan import (
    AuthorizedQueryPlanV1,
    AuthorizedRelationSpec,
    QueryAggregateSpec,
    QueryPredicateGroup,
    QueryPredicateLeaf,
    QueryPredicateNode,
)


def validate_authorized_query_plan(
    plan: AuthorizedQueryPlanV1,
    *,
    snapshot: AuthorizedSchemaSnapshot,
    catalog: tuple[AuthorizedRelationSpec, ...],
    allowed_view_ids: tuple[UUID, ...],
) -> None:
    tables_by_id = {item.table_id: item for item in snapshot.tables}
    fields_by_id = {
        field.field_id: field for table in snapshot.tables for field in table.fields
    }
    if (
        plan.schema_hash != snapshot.schema_hash
        or plan.scope_hash != snapshot.scope_hash
    ):
        raise ValueError("authorized_query_scope_or_schema_mismatch")
    if plan.root_table_id not in tables_by_id:
        raise ValueError("authorized_query_table_not_authorized")
    if not set(plan.authorized_view_ids).issubset(set(allowed_view_ids)):
        raise ValueError("authorized_query_view_not_authorized")

    operator_ids: list[str] = []
    reachable_table_ids = {plan.root_table_id}
    predicate_node_count = [0]
    if plan.predicate is not None:
        _validate_predicate(
            plan.predicate,
            fields_by_id=fields_by_id,
            operator_ids=operator_ids,
            depth=1,
            node_count=predicate_node_count,
        )

    relations_by_id = _validated_catalog(catalog, fields_by_id, tables_by_id)
    if plan.traversal_paths:
        for path in plan.traversal_paths:
            operator_ids.append(path.path_id)
            path_reachable, final_table_id = _validate_traversal_chain(
                root_table_id=plan.root_table_id,
                traversals=path.steps,
                relations_by_id=relations_by_id,
                operator_ids=operator_ids,
            )
            if final_table_id != path.target_table_id:
                raise ValueError("authorized_query_traversal_target_mismatch")
            reachable_table_ids.update(path_reachable)
            if path.predicate is not None:
                _validate_predicate(
                    path.predicate,
                    fields_by_id=fields_by_id,
                    operator_ids=operator_ids,
                    depth=1,
                    node_count=predicate_node_count,
                )
                for predicate in _predicate_leaves(path.predicate):
                    if predicate.table_id != path.target_table_id:
                        raise ValueError(
                            "authorized_query_path_predicate_scope_invalid"
                        )
    else:
        legacy_reachable, _ = _validate_traversal_chain(
            root_table_id=plan.root_table_id,
            traversals=plan.traversals,
            relations_by_id=relations_by_id,
            operator_ids=operator_ids,
        )
        reachable_table_ids.update(legacy_reachable)

    if plan.predicate is not None:
        for predicate in _predicate_leaves(plan.predicate):
            _require_reachable(predicate.table_id, reachable_table_ids)
    for field_id in plan.projection_field_ids:
        field = _authorized_field(field_id, fields_by_id)
        _require_reachable(field.table_id, reachable_table_ids)
    for field_id in plan.group_by_field_ids:
        field = _authorized_field(field_id, fields_by_id)
        _require_reachable(field.table_id, reachable_table_ids)
    for aggregate in plan.aggregates:
        operator_ids.append(aggregate.aggregate_id)
        _validate_aggregate(
            aggregate,
            fields_by_id=fields_by_id,
            reachable_table_ids=reachable_table_ids,
            operator_ids=operator_ids,
            predicate_node_count=predicate_node_count,
        )
    expected_group_by_field_ids = tuple(
        dict.fromkeys(
            field_id
            for aggregate in plan.aggregates
            for field_id in aggregate.group_by_field_ids
        )
    )
    if plan.group_by_field_ids != expected_group_by_field_ids:
        raise ValueError("authorized_query_group_summary_mismatch")
    aggregate_ids = {item.aggregate_id for item in plan.aggregates}
    for sort in plan.sort_rules:
        operator_ids.append(sort.sort_id)
        if sort.aggregate_id is not None:
            if sort.aggregate_id not in aggregate_ids:
                raise ValueError("authorized_query_sort_aggregate_unknown")
            continue
        if sort.field_id is None or sort.table_id is None:
            raise ValueError("authorized_query_sort_target_invalid")
        field = _authorized_field(sort.field_id, fields_by_id)
        if field.table_id != sort.table_id:
            raise ValueError("authorized_query_field_table_mismatch")
        _require_reachable(field.table_id, reachable_table_ids)
        if sort.mode == "field_order" and not field.choices:
            raise ValueError("authorized_query_sort_mode_invalid")
    if len(set(operator_ids)) != len(operator_ids):
        raise ValueError("authorized_query_operator_id_duplicate")


def _validate_traversal_chain(
    *,
    root_table_id: UUID,
    traversals,
    relations_by_id: dict[str, AuthorizedRelationSpec],
    operator_ids: list[str],
) -> tuple[set[UUID], UUID]:
    if len(traversals) > 2:
        raise ValueError("authorized_query_traversal_depth_exceeded")
    reachable = {root_table_id}
    current_table_id = root_table_id
    for traversal in traversals:
        operator_ids.append(traversal.traversal_id)
        relation = relations_by_id.get(traversal.relation_id)
        if relation is None or (
            traversal.link_source_table_id != relation.link_source_table_id
            or traversal.link_field_id != relation.link_field_id
            or traversal.link_target_table_id != relation.link_target_table_id
        ):
            raise ValueError("authorized_query_relation_not_authorized")
        if traversal.direction == "forward":
            origin = traversal.link_source_table_id
            destination = traversal.link_target_table_id
        else:
            origin = traversal.link_target_table_id
            destination = traversal.link_source_table_id
        if origin != current_table_id:
            raise ValueError("authorized_query_traversal_not_contiguous")
        if destination in reachable:
            raise ValueError("authorized_query_traversal_cycle")
        reachable.add(destination)
        current_table_id = destination
    return reachable, current_table_id


def _validate_predicate(
    predicate: QueryPredicateNode,
    *,
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
    operator_ids: list[str],
    depth: int,
    node_count: list[int],
) -> None:
    if depth > 4:
        raise ValueError("authorized_query_predicate_depth_exceeded")
    node_count[0] += 1
    if node_count[0] > 64:
        raise ValueError("authorized_query_predicate_node_limit")
    operator_ids.append(predicate.predicate_id)
    if isinstance(predicate, QueryPredicateGroup):
        for child in predicate.children:
            _validate_predicate(
                child,
                fields_by_id=fields_by_id,
                operator_ids=operator_ids,
                depth=depth + 1,
                node_count=node_count,
            )
        return
    if not isinstance(predicate, QueryPredicateLeaf):
        raise ValueError("authorized_query_predicate_invalid")
    field = _authorized_field(predicate.field_id, fields_by_id)
    if field.table_id != predicate.table_id:
        raise ValueError("authorized_query_field_table_mismatch")
    if predicate.operator not in _OPERATORS_BY_FIELD_TYPE[field.field_type]:
        raise ValueError("authorized_query_operator_type_invalid")


def _validated_catalog(
    catalog: tuple[AuthorizedRelationSpec, ...],
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
    tables_by_id: dict[UUID, object],
) -> dict[str, AuthorizedRelationSpec]:
    relations_by_id = {item.relation_id: item for item in catalog}
    if len(relations_by_id) != len(catalog):
        raise ValueError("authorized_query_relation_duplicate")
    for relation in catalog:
        field = _authorized_field(relation.link_field_id, fields_by_id)
        if (
            field.table_id != relation.link_source_table_id
            or field.field_type != "linked_record"
            or relation.link_source_table_id not in tables_by_id
            or relation.link_target_table_id not in tables_by_id
        ):
            raise ValueError("authorized_query_relation_not_authorized")
    return relations_by_id


def _validate_aggregate(
    aggregate: QueryAggregateSpec,
    *,
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
    reachable_table_ids: set[UUID],
    operator_ids: list[str],
    predicate_node_count: list[int],
) -> None:
    if aggregate.table_id not in reachable_table_ids:
        raise ValueError("authorized_query_field_table_unreachable")
    if aggregate.function != "count":
        if aggregate.field_id is None:
            raise ValueError("authorized_query_aggregate_field_required")
        field = _authorized_field(aggregate.field_id, fields_by_id)
        if field.table_id != aggregate.table_id:
            raise ValueError("authorized_query_field_table_mismatch")
        if aggregate.function in {"sum", "average"} and field.field_type != "number":
            raise ValueError("authorized_query_aggregate_type_invalid")
        if aggregate.function in {"minimum", "maximum"} and field.field_type not in {
            "number",
            "date",
            "datetime",
            "text",
        }:
            raise ValueError("authorized_query_aggregate_type_invalid")
    for field_id in aggregate.group_by_field_ids:
        field = _authorized_field(field_id, fields_by_id)
        _require_reachable(field.table_id, reachable_table_ids)
    if aggregate.filter_predicate is not None:
        _validate_predicate(
            aggregate.filter_predicate,
            fields_by_id=fields_by_id,
            operator_ids=operator_ids,
            depth=1,
            node_count=predicate_node_count,
        )
        for predicate in _predicate_leaves(aggregate.filter_predicate):
            _require_reachable(predicate.table_id, reachable_table_ids)


def _predicate_leaves(
    predicate: QueryPredicateNode,
) -> tuple[QueryPredicateLeaf, ...]:
    if isinstance(predicate, QueryPredicateLeaf):
        return (predicate,)
    return tuple(
        leaf for child in predicate.children for leaf in _predicate_leaves(child)
    )


def _authorized_field(
    field_id: UUID,
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
) -> AuthorizedFieldSpec:
    field = fields_by_id.get(field_id)
    if field is None:
        raise ValueError("authorized_query_field_not_authorized")
    return field


def _require_reachable(table_id: UUID, reachable_table_ids: set[UUID]) -> None:
    if table_id not in reachable_table_ids:
        raise ValueError("authorized_query_field_table_unreachable")
