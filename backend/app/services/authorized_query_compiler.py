"""Compile Stage12-B TaskSpec intents into the restricted Stage12-C QueryPlan."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
from uuid import UUID

from pydantic import ValidationError

from app.schemas.agent_task_spec_v2 import (
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    BoundPredicate,
    QueryExecutionIntentV1,
    QueryIntentSpec,
    QueryJoinIntentV1,
    QueryPredicateExpressionV1,
    QueryPredicateGroupIntentV1,
    QueryPredicateLeafIntentV1,
    TaskSpecV2,
)
from app.schemas.authorized_query_plan import (
    AuthorizedQueryPlanV1,
    AuthorizedRelationSpec,
    QueryAggregateSpec,
    QueryHavingSpec,
    QueryPredicateGroup,
    QueryPredicateLeaf,
    QueryPredicateNode,
    QuerySortSpec,
    QueryTraversalPathSpec,
    QueryTraversalSpec,
)
from app.services.authorized_query_validation import validate_authorized_query_plan


class AuthorizedQueryCompileError(ValueError):
    """Stable, non-sensitive compilation refusal."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class _PathStep:
    relation: AuthorizedRelationSpec
    direction: str
    origin_table_id: UUID
    destination_table_id: UUID

    @property
    def identity(self) -> tuple[str, str, str, str, str]:
        return (
            str(self.relation.link_source_table_id),
            str(self.relation.link_field_id),
            self.direction,
            str(self.relation.link_target_table_id),
            self.relation.relation_id,
        )


def compile_authorized_query_plan(
    *,
    task_spec: TaskSpecV2,
    query_intent_id: str,
    snapshot: AuthorizedSchemaSnapshot,
    relations: tuple[AuthorizedRelationSpec, ...],
    authorized_view_ids: tuple[UUID, ...],
) -> AuthorizedQueryPlanV1:
    if task_spec.authorized_schema_hash != snapshot.schema_hash:
        raise AuthorizedQueryCompileError("authorized_query_scope_or_schema_mismatch")
    intent = next(
        (
            item
            for item in task_spec.query_intents
            if item.query_intent_id == query_intent_id
        ),
        None,
    )
    if intent is None:
        raise AuthorizedQueryCompileError("authorized_query_intent_not_found")
    if intent.root_table_id is None:
        raise AuthorizedQueryCompileError("authorized_query_root_table_required")

    execution = intent.execution_spec
    if execution is None and (
        intent.aggregation_kinds or intent.group_by_field_ids or intent.sort_field_ids
    ):
        raise AuthorizedQueryCompileError("authorized_query_execution_detail_required")

    predicate = _compile_global_predicate(intent, execution)
    aggregates = _compile_aggregates(execution)
    sorts = _compile_sorts(execution)
    projection_field_ids = () if execution is None else execution.projection_field_ids
    if (
        not projection_field_ids
        and not aggregates
        and _intent_has_user_result_objective(task_spec, intent)
    ):
        projection_field_ids = _default_projection_field_ids(
            root_table_id=intent.root_table_id,
            predicate=predicate,
            snapshot=snapshot,
        )
    group_by_field_ids = tuple(
        dict.fromkeys(
            field_id
            for aggregate in aggregates
            for field_id in aggregate.group_by_field_ids
        )
    )
    limit = intent.limit if execution is None else execution.limit

    fields_by_id = {
        field.field_id: field for table in snapshot.tables for field in table.fields
    }
    referenced_tables = _referenced_table_ids(
        intent.root_table_id,
        predicate=predicate,
        projection_field_ids=projection_field_ids,
        aggregates=aggregates,
        sorts=sorts,
        fields_by_id=fields_by_id,
    )
    join_intents = () if execution is None else execution.join_intents
    referenced_tables.update(item.target_table_id for item in join_intents)
    if join_intents:
        path_predicate_targets = {
            item.target_table_id
            for item in join_intents
            if item.requirement == "optional" or item.purpose == "exists"
        }
        predicate, optional_predicates = _extract_optional_path_predicates(
            predicate,
            optional_target_table_ids=path_predicate_targets,
        )
        traversal_paths = _compile_traversal_paths(
            root_table_id=intent.root_table_id,
            target_table_ids=referenced_tables - {intent.root_table_id},
            join_intents=join_intents,
            optional_predicates=optional_predicates,
            relations=relations,
        )
        traversals = ()
    else:
        traversal_paths = ()
        traversals = _compile_traversals(
            root_table_id=intent.root_table_id,
            target_table_ids=referenced_tables - {intent.root_table_id},
            relations=relations,
        )

    try:
        plan = AuthorizedQueryPlanV1(
            version="authorized-query-plan.v1",
            query_intent_id=intent.query_intent_id,
            root_table_id=intent.root_table_id,
            authorized_view_ids=authorized_view_ids,
            entity_codes=intent.entity_codes,
            predicate=predicate,
            traversals=traversals,
            projection_field_ids=projection_field_ids,
            group_by_field_ids=group_by_field_ids,
            aggregates=aggregates,
            sort_rules=sorts,
            limit=limit,
            max_scan_rows=5000,
            max_relation_expansions=1000,
            scope_hash=snapshot.scope_hash,
            schema_hash=snapshot.schema_hash,
            traversal_paths=traversal_paths,
        )
        validate_authorized_query_plan(
            plan,
            snapshot=snapshot,
            catalog=relations,
            allowed_view_ids=authorized_view_ids,
        )
    except (ValidationError, ValueError) as exc:
        if isinstance(exc, AuthorizedQueryCompileError):
            raise
        raise AuthorizedQueryCompileError(_stable_validation_code(exc)) from exc
    return plan


def _intent_has_user_result_objective(
    task_spec: TaskSpecV2,
    intent: QueryIntentSpec,
) -> bool:
    query_ref = f"query-intent:{intent.query_intent_id}"
    objectives = tuple(
        item
        for item in task_spec.objectives
        if item.query_spec_ref == query_ref and item.planning_outcome == "planned"
    )
    fact_objectives = tuple(item for item in objectives if item.kind == "fact_query")
    if not fact_objectives:
        return False
    action_span_sets = {
        tuple((span.start, span.end, span.text) for span in item.source_spans)
        for item in task_spec.objectives
        if item.kind in {"record_change", "task_creation", "reminder_request"}
    }
    return any(
        tuple((span.start, span.end, span.text) for span in item.source_spans)
        not in action_span_sets
        for item in fact_objectives
    )


def _default_projection_field_ids(
    *,
    root_table_id: UUID,
    predicate: QueryPredicateNode | None,
    snapshot: AuthorizedSchemaSnapshot,
) -> tuple[UUID, ...]:
    root_table = next(
        (table for table in snapshot.tables if table.table_id == root_table_id),
        None,
    )
    if root_table is None:
        raise AuthorizedQueryCompileError("authorized_query_root_table_not_authorized")
    predicate_field_ids = (
        ()
        if predicate is None
        else tuple(
            leaf.field_id
            for leaf in _predicate_leaves(predicate)
            if leaf.table_id == root_table_id
        )
    )
    return tuple(
        dict.fromkeys(
            (
                *(
                    ()
                    if root_table.identity_field_id is None
                    else (root_table.identity_field_id,)
                ),
                *predicate_field_ids,
            )
        )
    )


def _compile_global_predicate(
    intent: QueryIntentSpec,
    execution: QueryExecutionIntentV1 | None,
) -> QueryPredicateNode | None:
    if execution is not None:
        if execution.predicate_expression is None:
            return None
        return _compile_predicate_expression(
            execution.predicate_expression,
            namespace="predicate-global",
        )
    if not intent.predicates:
        return None
    leaves = tuple(
        _compile_bound_predicate(item, predicate_id=f"predicate-global-{index:02d}")
        for index, item in enumerate(intent.predicates, start=1)
    )
    if len(leaves) == 1:
        return leaves[0]
    return QueryPredicateGroup(
        predicate_id="predicate-global",
        operator="and",
        children=leaves,
    )


def _compile_predicate_expression(
    expression: QueryPredicateExpressionV1,
    *,
    namespace: str,
) -> QueryPredicateNode:
    if isinstance(expression, QueryPredicateLeafIntentV1):
        return _compile_bound_predicate(
            expression.predicate,
            predicate_id=namespace,
        )
    if not isinstance(expression, QueryPredicateGroupIntentV1):
        raise AuthorizedQueryCompileError("authorized_query_predicate_invalid")
    return QueryPredicateGroup(
        predicate_id=namespace,
        operator=expression.operator,
        children=tuple(
            _compile_predicate_expression(
                child,
                namespace=f"{namespace}-{index:02d}",
            )
            for index, child in enumerate(expression.children, start=1)
        ),
    )


def _compile_bound_predicate(
    predicate: BoundPredicate,
    *,
    predicate_id: str,
) -> QueryPredicateLeaf:
    return QueryPredicateLeaf(
        predicate_id=predicate_id,
        table_id=predicate.table_id,
        field_id=predicate.field_id,
        operator=predicate.operator,
        value=predicate.value,
    )


def _compile_aggregates(
    execution: QueryExecutionIntentV1 | None,
) -> tuple[QueryAggregateSpec, ...]:
    if execution is None:
        return ()
    return tuple(
        QueryAggregateSpec(
            aggregate_id=item.aggregate_id,
            output_key=item.output_key,
            function=item.function,
            table_id=item.table_id,
            field_id=item.field_id,
            filter_predicate=(
                None
                if item.filter_expression is None
                else _compile_predicate_expression(
                    item.filter_expression,
                    namespace=f"predicate-{item.aggregate_id}",
                )
            ),
            group_by_field_ids=item.group_by_field_ids,
            having=(
                None
                if item.having is None
                else QueryHavingSpec(
                    operator=item.having.operator,
                    value=item.having.value,
                )
            ),
        )
        for item in execution.aggregations
    )


def _compile_sorts(
    execution: QueryExecutionIntentV1 | None,
) -> tuple[QuerySortSpec, ...]:
    if execution is None:
        return ()
    return tuple(
        QuerySortSpec(
            sort_id=item.sort_id,
            table_id=item.table_id,
            field_id=item.field_id,
            aggregate_id=item.aggregate_id,
            mode=item.mode,
            direction=item.direction,
            nulls=item.nulls,
        )
        for item in execution.sorts
    )


def _referenced_table_ids(
    root_table_id: UUID,
    *,
    predicate: QueryPredicateNode | None,
    projection_field_ids: tuple[UUID, ...],
    aggregates: tuple[QueryAggregateSpec, ...],
    sorts: tuple[QuerySortSpec, ...],
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
) -> set[UUID]:
    table_ids = {root_table_id}
    if predicate is not None:
        table_ids.update(item.table_id for item in _predicate_leaves(predicate))
    for field_id in projection_field_ids:
        table_ids.add(_field_table_id(field_id, fields_by_id))
    for aggregate in aggregates:
        table_ids.add(aggregate.table_id)
        if aggregate.field_id is not None:
            table_ids.add(_field_table_id(aggregate.field_id, fields_by_id))
        for field_id in aggregate.group_by_field_ids:
            table_ids.add(_field_table_id(field_id, fields_by_id))
        if aggregate.filter_predicate is not None:
            table_ids.update(
                item.table_id for item in _predicate_leaves(aggregate.filter_predicate)
            )
    for sort in sorts:
        if sort.field_id is not None:
            table_ids.add(_field_table_id(sort.field_id, fields_by_id))
    return table_ids


def _field_table_id(
    field_id: UUID,
    fields_by_id: dict[UUID, AuthorizedFieldSpec],
) -> UUID:
    field = fields_by_id.get(field_id)
    if field is None:
        raise AuthorizedQueryCompileError("authorized_query_field_not_authorized")
    return field.table_id


def _predicate_leaves(
    predicate: QueryPredicateNode,
) -> tuple[QueryPredicateLeaf, ...]:
    if isinstance(predicate, QueryPredicateLeaf):
        return (predicate,)
    return tuple(
        leaf for child in predicate.children for leaf in _predicate_leaves(child)
    )


def _compile_traversals(
    *,
    root_table_id: UUID,
    target_table_ids: set[UUID],
    relations: tuple[AuthorizedRelationSpec, ...],
) -> tuple[QueryTraversalSpec, ...]:
    if not target_table_ids:
        return ()
    paths = tuple(
        _unique_shortest_path(root_table_id, target, relations)
        for target in sorted(target_table_ids, key=str)
    )
    longest = max(paths, key=len)
    if any(longest[: len(path)] != path for path in paths):
        raise AuthorizedQueryCompileError("authorized_query_join_path_unavailable")
    return tuple(
        QueryTraversalSpec(
            traversal_id=f"traversal-{index:02d}",
            relation_id=step.relation.relation_id,
            link_source_table_id=step.relation.link_source_table_id,
            link_field_id=step.relation.link_field_id,
            link_target_table_id=step.relation.link_target_table_id,
            direction=step.direction,
            max_expansion=1000,
        )
        for index, step in enumerate(longest, start=1)
    )


def _compile_traversal_paths(
    *,
    root_table_id: UUID,
    target_table_ids: set[UUID],
    join_intents: tuple[QueryJoinIntentV1, ...],
    optional_predicates: dict[UUID, QueryPredicateNode],
    relations: tuple[AuthorizedRelationSpec, ...],
) -> tuple[QueryTraversalPathSpec, ...]:
    intents_by_target = {item.target_table_id: item for item in join_intents}
    if root_table_id in intents_by_target:
        raise AuthorizedQueryCompileError("authorized_query_join_target_invalid")
    values: list[QueryTraversalPathSpec] = []
    ordered_targets = sorted(
        target_table_ids,
        key=lambda table_id: (
            intents_by_target.get(table_id).join_intent_id
            if table_id in intents_by_target
            else f"zz-{table_id}"
        ),
    )
    for target_table_id in ordered_targets:
        intent = intents_by_target.get(target_table_id)
        purpose = "filter" if intent is None else intent.purpose
        requirement = "required" if intent is None else intent.requirement
        path_id = (
            f"path-implicit-{str(target_table_id)}"
            if intent is None
            else f"path-{intent.join_intent_id}"
        )
        path = _unique_shortest_path(root_table_id, target_table_id, relations)
        join_mode = (
            "semi"
            if purpose == "exists"
            else "left" if requirement == "optional" else "inner"
        )
        values.append(
            QueryTraversalPathSpec(
                path_id=path_id,
                target_table_id=target_table_id,
                purpose=purpose,
                join_mode=join_mode,
                steps=tuple(
                    QueryTraversalSpec(
                        traversal_id=f"{path_id}-step-{index:02d}",
                        relation_id=step.relation.relation_id,
                        link_source_table_id=step.relation.link_source_table_id,
                        link_field_id=step.relation.link_field_id,
                        link_target_table_id=step.relation.link_target_table_id,
                        direction=step.direction,
                        max_expansion=1000,
                    )
                    for index, step in enumerate(path, start=1)
                ),
                predicate=optional_predicates.get(target_table_id),
            )
        )
    return tuple(values)


def _extract_optional_path_predicates(
    predicate: QueryPredicateNode | None,
    *,
    optional_target_table_ids: set[UUID],
) -> tuple[QueryPredicateNode | None, dict[UUID, QueryPredicateNode]]:
    if predicate is None or not optional_target_table_ids:
        return predicate, {}
    candidates = (
        predicate.children
        if isinstance(predicate, QueryPredicateGroup) and predicate.operator == "and"
        else (predicate,)
    )
    retained: list[QueryPredicateNode] = []
    extracted: dict[UUID, list[QueryPredicateNode]] = {}
    for candidate in candidates:
        if (
            isinstance(candidate, QueryPredicateLeaf)
            and candidate.table_id in optional_target_table_ids
        ):
            extracted.setdefault(candidate.table_id, []).append(candidate)
        else:
            retained.append(candidate)
    global_predicate = _predicate_group_or_single(
        retained,
        predicate_id=(
            predicate.predicate_id
            if isinstance(predicate, QueryPredicateGroup)
            else "predicate-global"
        ),
    )
    path_predicates = {
        table_id: _predicate_group_or_single(
            values,
            predicate_id=f"predicate-path-{str(table_id)}",
        )
        for table_id, values in extracted.items()
    }
    return global_predicate, {
        table_id: value
        for table_id, value in path_predicates.items()
        if value is not None
    }


def _predicate_group_or_single(
    values: list[QueryPredicateNode],
    *,
    predicate_id: str,
) -> QueryPredicateNode | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return QueryPredicateGroup(
        predicate_id=predicate_id,
        operator="and",
        children=tuple(values),
    )


def _unique_shortest_path(
    root_table_id: UUID,
    target_table_id: UUID,
    relations: tuple[AuthorizedRelationSpec, ...],
    *,
    max_depth: int = 2,
) -> tuple[_PathStep, ...]:
    queue: deque[tuple[UUID, tuple[_PathStep, ...], frozenset[UUID]]] = deque(
        [(root_table_id, (), frozenset({root_table_id}))]
    )
    shortest: list[tuple[_PathStep, ...]] = []
    shortest_depth: int | None = None
    while queue:
        table_id, path, visited = queue.popleft()
        if shortest_depth is not None and len(path) >= shortest_depth:
            continue
        for step in _ordered_steps_from(table_id, relations):
            if step.destination_table_id in visited:
                continue
            candidate = (*path, step)
            if step.destination_table_id == target_table_id:
                shortest_depth = len(candidate)
                shortest.append(candidate)
            elif len(candidate) < max_depth:
                queue.append(
                    (
                        step.destination_table_id,
                        candidate,
                        visited | {step.destination_table_id},
                    )
                )
    unique = {tuple(item.identity for item in path): path for path in shortest}
    if not unique:
        raise AuthorizedQueryCompileError("authorized_query_join_path_unavailable")
    if len(unique) != 1:
        raise AuthorizedQueryCompileError("authorized_query_join_path_ambiguous")
    return next(iter(unique.values()))


def _ordered_steps_from(
    table_id: UUID,
    relations: tuple[AuthorizedRelationSpec, ...],
) -> tuple[_PathStep, ...]:
    steps: list[_PathStep] = []
    for relation in relations:
        if relation.link_source_table_id == table_id:
            steps.append(
                _PathStep(
                    relation=relation,
                    direction="forward",
                    origin_table_id=table_id,
                    destination_table_id=relation.link_target_table_id,
                )
            )
        if relation.link_target_table_id == table_id:
            steps.append(
                _PathStep(
                    relation=relation,
                    direction="reverse",
                    origin_table_id=table_id,
                    destination_table_id=relation.link_source_table_id,
                )
            )
    return tuple(sorted(steps, key=lambda item: item.identity))


def _stable_validation_code(exc: ValidationError | ValueError) -> str:
    if isinstance(exc, ValueError) and not isinstance(exc, ValidationError):
        value = str(exc)
        if value.startswith("authorized_query_"):
            return value
    message = str(exc)
    match = re.search(r"authorized_query_[a-z0-9_]+", message)
    return "authorized_query_contract_invalid" if match is None else match.group(0)


__all__ = [
    "AuthorizedQueryCompileError",
    "compile_authorized_query_plan",
]
