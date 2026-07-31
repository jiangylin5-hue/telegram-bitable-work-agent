"""End-to-end authorized deterministic table-query coordination."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable
from uuid import UUID

from app.schemas.agent_task_spec_v2 import AuthorizedSchemaSnapshot
from app.schemas.authorized_query_plan import (
    AuthorizedQueryPlanV1,
    QueryPredicateGroup,
    QueryPredicateLeaf,
    QueryPredicateNode,
    QueryTraversalPathSpec,
    QueryTraversalSpec,
    RelationPathProof,
    SourceRecordVersion,
    StructuredAggregate,
    StructuredGroup,
    StructuredQueryArtifactV1,
    StructuredQueryResultV1,
    StructuredRecord,
    authorized_query_plan_sha256,
    structured_query_result_sha256,
)
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.authorized_query_aggregates import execute_authorized_aggregates
from app.services.authorized_query_records import (
    AuthorizedQueryContext,
    AuthorizedQueryDenied,
    AuthorizedRecord,
    AuthorizedRecordSet,
    build_authorized_query_context,
    filter_records,
    project_records,
    resolve_authorized_entities,
    scan_authorized_records,
)
from app.services.authorized_query_relations import traverse_authorized_links
from app.services.authorized_query_validation import validate_authorized_query_plan
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
)


@dataclass(frozen=True, slots=True)
class JoinedFactRowV1:
    """Internal immutable joined fact; never persisted or exposed over API/SSE."""

    root_record_id: UUID
    records_by_table: tuple[AuthorizedRecord, ...]
    relation_path_proofs: tuple[RelationPathProof, ...]
    source_versions: tuple[SourceRecordVersion, ...]


def execute_authorized_query(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    workspace_id: UUID,
    employee_id: UUID,
    chat_view_ids: tuple[UUID, ...] | None,
    snapshot: AuthorizedSchemaSnapshot,
    plan: AuthorizedQueryPlanV1,
    allow_whole_table: bool = False,
) -> StructuredQueryArtifactV1:
    """Execute one validated read-only plan and return a replayable artifact."""

    current = _current_snapshot(
        uow,
        actor=actor,
        workspace_id=workspace_id,
        employee_id=employee_id,
        require_field_policy_v2=snapshot.field_policy_version is not None,
    )
    _require_current_hashes(snapshot=snapshot, plan=plan, current=current)
    employee = uow.get_digital_employee(employee_id)
    if employee is None:
        raise AuthorizedQueryDenied("authorized_query_context_scope_denied")
    employee_view_ids = _employee_view_ids(employee.accessible_views)
    allowed_view_ids = chat_view_ids if chat_view_ids is not None else employee_view_ids
    catalog = build_authorized_relation_catalog(uow, current)
    try:
        validate_authorized_query_plan(
            plan,
            snapshot=current,
            catalog=catalog,
            allowed_view_ids=allowed_view_ids,
        )
    except ValueError as exc:
        raise AuthorizedQueryDenied(str(exc)) from exc

    scoped_view_ids: tuple[UUID, ...] | None
    scoped_whole_table: bool
    if plan.authorized_view_ids:
        scoped_view_ids = plan.authorized_view_ids
        scoped_whole_table = False
    elif chat_view_ids is not None:
        scoped_view_ids = chat_view_ids
        scoped_whole_table = False
    else:
        scoped_view_ids = None
        scoped_whole_table = allow_whole_table
    context = build_authorized_query_context(
        uow,
        workspace_id=workspace_id,
        base_id=employee.base_id,
        employee_id=employee_id,
        actor=actor,
        snapshot=current,
        chat_authorized_view_ids=scoped_view_ids,
        allow_whole_table=scoped_whole_table,
    )

    required_fields = _required_fields_by_table(plan, current)
    if plan.entity_codes:
        code_field_id = _entity_code_field_id(current, plan.root_table_id)
        required_fields.setdefault(plan.root_table_id, set()).add(code_field_id)
    root_records = scan_authorized_records(
        context=context,
        table_id=plan.root_table_id,
        required_field_ids=_ordered_ids(required_fields.get(plan.root_table_id, set())),
        max_scan_rows=plan.max_scan_rows,
    )
    scanned_record_count = root_records.scanned_record_count
    if plan.entity_codes:
        root_records = _select_entity_records(
            root_records,
            selectors=plan.entity_codes,
            code_field_id=_entity_code_field_id(current, plan.root_table_id),
        )

    root_rows = tuple(_root_row(record) for record in root_records.records)
    traversed_edge_count = 0
    if plan.traversal_paths:
        path_results: list[tuple[str, tuple[JoinedFactRowV1, ...]]] = []
        for path in plan.traversal_paths:
            if _is_lazy_optional_context_path(path, plan=plan, snapshot=current):
                path_results.append((path.join_mode, root_rows))
                continue
            path_rows, scanned_record_count, traversed_edge_count, _ = (
                _expand_traversal_chain(
                    rows=root_rows,
                    root_table_id=plan.root_table_id,
                    traversals=path.steps,
                    terminal_predicate=path.predicate,
                    preserve_terminal_unmatched=path.join_mode == "left",
                    context=context,
                    catalog=catalog,
                    required_fields=required_fields,
                    snapshot=current,
                    scanned_record_count=scanned_record_count,
                    traversed_edge_count=traversed_edge_count,
                    max_scan_rows=plan.max_scan_rows,
                    max_relation_expansions=plan.max_relation_expansions,
                )
            )
            if path.join_mode == "semi":
                path_rows = _semi_witness_rows(path_rows, snapshot=current)
            path_results.append((path.join_mode, path_rows))
        semi_root_sets = [
            {row.root_record_id for row in path_rows}
            for join_mode, path_rows in path_results
            if join_mode == "semi"
        ]
        eligible_root_ids = (
            None if not semi_root_sets else set.intersection(*semi_root_sets)
        )
        rows = _merge_independent_path_rows(
            root_rows,
            tuple(
                (join_mode, path_rows)
                for join_mode, path_rows in path_results
                if join_mode != "semi"
            ),
            eligible_root_ids=eligible_root_ids,
        )
        default_table_id = plan.root_table_id
    else:
        rows, scanned_record_count, traversed_edge_count, default_table_id = (
            _expand_traversal_chain(
                rows=root_rows,
                root_table_id=plan.root_table_id,
                traversals=plan.traversals,
                terminal_predicate=None,
                preserve_terminal_unmatched=False,
                context=context,
                catalog=catalog,
                required_fields=required_fields,
                snapshot=current,
                scanned_record_count=scanned_record_count,
                traversed_edge_count=traversed_edge_count,
                max_scan_rows=plan.max_scan_rows,
                max_relation_expansions=plan.max_relation_expansions,
            )
        )

    matched_rows = tuple(
        row
        for row in rows
        if _row_matches_predicate(row, plan.predicate, snapshot=current)
    )
    (
        selected_rows,
        primary_records,
        groups,
        aggregates,
        truncated,
        primary_table_id,
    ) = _apply_presentation(plan, matched_rows, default_table_id, current)
    records = _project_result_records(
        selected_rows,
        primary_records=primary_records,
        primary_table_id=primary_table_id,
        projection_field_ids=plan.projection_field_ids,
        snapshot=current,
    )
    relation_paths = _selected_relation_paths(selected_rows)
    source_versions = _selected_source_versions(selected_rows)

    after = _current_snapshot(
        uow,
        actor=actor,
        workspace_id=workspace_id,
        employee_id=employee_id,
        require_field_policy_v2=snapshot.field_policy_version is not None,
    )
    _require_current_hashes(snapshot=snapshot, plan=plan, current=after)
    plan_hash = authorized_query_plan_sha256(plan)
    result_values = {
        "version": "structured-query-result.v1",
        "query_plan_version": plan.version,
        "plan_hash": plan_hash,
        "records": records,
        "groups": groups,
        "aggregates": aggregates,
        "relation_paths": relation_paths,
        "source_versions": source_versions,
        "scope_hash": current.scope_hash,
        "schema_hash": current.schema_hash,
        "scanned_record_count": scanned_record_count,
        "traversed_edge_count": traversed_edge_count,
        "truncated": truncated,
    }
    result = StructuredQueryResultV1(
        **result_values,
        result_hash=structured_query_result_sha256(
            StructuredQueryResultV1.model_construct(
                **result_values,
                result_hash="0" * 64,
            ).model_dump(mode="json", exclude={"result_hash"})
        ),
    )
    return StructuredQueryArtifactV1(
        version="structured-query-artifact.v1",
        plan=plan,
        plan_hash=plan_hash,
        result=result,
    )


def _current_snapshot(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    workspace_id: UUID,
    employee_id: UUID,
    require_field_policy_v2: bool,
) -> AuthorizedSchemaSnapshot:
    try:
        return build_authorized_schema_snapshot(
            uow,
            workspace_id=workspace_id,
            employee_id=employee_id,
            actor=actor,
            require_field_policy_v2=require_field_policy_v2,
        )
    except PlatformValidationError as exc:
        raise AuthorizedQueryDenied("authorized_query_scope_drift") from exc


def _require_current_hashes(
    *,
    snapshot: AuthorizedSchemaSnapshot,
    plan: AuthorizedQueryPlanV1,
    current: AuthorizedSchemaSnapshot,
) -> None:
    if (
        current.scope_hash != snapshot.scope_hash
        or current.scope_hash != plan.scope_hash
    ):
        raise AuthorizedQueryDenied("authorized_query_scope_drift")
    if (
        current.schema_hash != snapshot.schema_hash
        or current.schema_hash != plan.schema_hash
    ):
        raise AuthorizedQueryDenied("authorized_query_schema_drift")


def _employee_view_ids(values: object) -> tuple[UUID, ...]:
    if not isinstance(values, list):
        raise AuthorizedQueryDenied("authorized_query_view_scope_denied")
    try:
        parsed = tuple(UUID(item) for item in values if isinstance(item, str))
    except ValueError as exc:
        raise AuthorizedQueryDenied("authorized_query_view_scope_denied") from exc
    if len(parsed) != len(values) or len(set(parsed)) != len(parsed):
        raise AuthorizedQueryDenied("authorized_query_view_scope_denied")
    return parsed


def _required_fields_by_table(
    plan: AuthorizedQueryPlanV1,
    snapshot: AuthorizedSchemaSnapshot,
) -> dict[UUID, set[UUID]]:
    fields_by_id = {
        field.field_id: field for table in snapshot.tables for field in table.fields
    }
    required: dict[UUID, set[UUID]] = {
        table.table_id: set() for table in snapshot.tables
    }
    for table in snapshot.tables:
        identity = table.identity_field_id or next(
            (
                field.field_id
                for field in table.fields
                if field.key == "code" or field.key.endswith("_code")
            ),
            None,
        )
        if identity is not None:
            required[table.table_id].add(identity)

    def add(field_id: UUID) -> None:
        field = fields_by_id.get(field_id)
        if field is None:
            raise AuthorizedQueryDenied("authorized_query_field_not_authorized")
        required[field.table_id].add(field_id)

    for field_id in plan.projection_field_ids:
        add(field_id)
    for field_id in plan.group_by_field_ids:
        add(field_id)
    if plan.predicate is not None:
        for leaf in _predicate_leaves(plan.predicate):
            add(leaf.field_id)
    for aggregate in plan.aggregates:
        if aggregate.field_id is not None:
            add(aggregate.field_id)
        for field_id in aggregate.group_by_field_ids:
            add(field_id)
        if aggregate.filter_predicate is not None:
            for leaf in _predicate_leaves(aggregate.filter_predicate):
                add(leaf.field_id)
    for sort in plan.sort_rules:
        if sort.field_id is not None:
            add(sort.field_id)
    traversals = (
        plan.traversals
        if not plan.traversal_paths
        else tuple(step for path in plan.traversal_paths for step in path.steps)
    )
    for traversal in traversals:
        if traversal.direction == "forward":
            add(traversal.link_field_id)
    for path in plan.traversal_paths:
        if path.predicate is not None:
            for leaf in _predicate_leaves(path.predicate):
                add(leaf.field_id)
    return required


def _predicate_leaves(predicate: QueryPredicateNode) -> tuple[QueryPredicateLeaf, ...]:
    if isinstance(predicate, QueryPredicateLeaf):
        return (predicate,)
    if not isinstance(predicate, QueryPredicateGroup):
        raise AuthorizedQueryDenied("authorized_query_predicate_invalid")
    return tuple(
        leaf for child in predicate.children for leaf in _predicate_leaves(child)
    )


def _is_lazy_optional_context_path(
    path: QueryTraversalPathSpec,
    *,
    plan: AuthorizedQueryPlanV1,
    snapshot: AuthorizedSchemaSnapshot,
) -> bool:
    if (
        path.join_mode != "left"
        or path.purpose != "project"
        or path.predicate is not None
    ):
        return False
    target = path.target_table_id
    if any(
        _field_table_id(snapshot, field_id) == target
        for field_id in plan.projection_field_ids
    ):
        return False
    if plan.predicate is not None and any(
        leaf.table_id == target for leaf in _predicate_leaves(plan.predicate)
    ):
        return False
    if any(aggregate.table_id == target for aggregate in plan.aggregates):
        return False
    if any(sort.table_id == target for sort in plan.sort_rules):
        return False
    return True


def _entity_code_field_id(
    snapshot: AuthorizedSchemaSnapshot,
    table_id: UUID,
) -> UUID:
    table = next((item for item in snapshot.tables if item.table_id == table_id), None)
    if table is None:
        raise AuthorizedQueryDenied("authorized_query_table_scope_denied")
    if table.identity_field_id is not None:
        return table.identity_field_id
    exact = [item for item in table.fields if item.key == "code"]
    if len(exact) == 1:
        return exact[0].field_id
    singular = table.key[:-1] if table.key.endswith("s") else table.key
    conventional = [item for item in table.fields if item.key == f"{singular}_code"]
    if len(conventional) == 1:
        return conventional[0].field_id
    candidates = [item for item in table.fields if item.key.endswith("_code")]
    if len(candidates) != 1:
        raise AuthorizedQueryDenied("authorized_query_entity_code_field_unavailable")
    return candidates[0].field_id


def _select_entity_records(
    records: AuthorizedRecordSet,
    *,
    selectors: tuple[str, ...],
    code_field_id: UUID,
) -> AuthorizedRecordSet:
    resolutions = resolve_authorized_entities(
        records,
        selectors=selectors,
        code_field_id=code_field_id,
        display_field_id=code_field_id,
    )
    selected: set[UUID] = set()
    for resolution in resolutions:
        if resolution.status == "unresolved":
            raise AuthorizedQueryDenied("authorized_query_entity_not_found")
        if resolution.status == "ambiguous":
            raise AuthorizedQueryDenied("authorized_query_entity_ambiguous")
        selected.update(resolution.record_ids)
    return AuthorizedRecordSet(
        table_id=records.table_id,
        records=tuple(item for item in records.records if item.record_id in selected),
        scanned_record_count=records.scanned_record_count,
        source_view_ids=records.source_view_ids,
        complete=records.complete,
    )


def _root_row(record: AuthorizedRecord) -> JoinedFactRowV1:
    return JoinedFactRowV1(
        root_record_id=record.record_id,
        records_by_table=(record,),
        relation_path_proofs=(),
        source_versions=(_source_version(record),),
    )


def _expand_traversal_chain(
    *,
    rows: tuple[JoinedFactRowV1, ...],
    root_table_id: UUID,
    traversals: tuple[QueryTraversalSpec, ...],
    terminal_predicate: QueryPredicateNode | None,
    preserve_terminal_unmatched: bool,
    context: AuthorizedQueryContext,
    catalog,
    required_fields: dict[UUID, set[UUID]],
    snapshot: AuthorizedSchemaSnapshot,
    scanned_record_count: int,
    traversed_edge_count: int,
    max_scan_rows: int,
    max_relation_expansions: int,
) -> tuple[tuple[JoinedFactRowV1, ...], int, int, UUID]:
    current_table_id = root_table_id
    for index, traversal in enumerate(traversals):
        if not rows:
            break
        remaining_scan_rows = max_scan_rows - scanned_record_count
        if remaining_scan_rows < 1:
            raise AuthorizedQueryDenied("authorized_query_scan_budget_exceeded")
        remaining_edges = max_relation_expansions - traversed_edge_count
        if remaining_edges < 1:
            raise AuthorizedQueryDenied("authorized_query_relation_budget_exceeded")
        source_set = _row_record_set(rows, current_table_id)
        traversal_result = traverse_authorized_links(
            context=context,
            source_records=source_set,
            traversals=(traversal,),
            catalog=catalog,
            max_relation_expansions=remaining_edges,
            max_scan_rows=remaining_scan_rows,
            required_field_ids_by_table={
                table_id: _ordered_ids(field_ids)
                for table_id, field_ids in required_fields.items()
            },
        )
        scanned_record_count += traversal_result.record_set.scanned_record_count
        traversed_edge_count += traversal_result.traversed_edge_count
        if scanned_record_count > max_scan_rows:
            raise AuthorizedQueryDenied("authorized_query_scan_budget_exceeded")
        destination = traversal_result.record_set
        is_terminal = index == len(traversals) - 1
        if is_terminal and terminal_predicate is not None:
            destination = filter_records(
                destination,
                predicate=terminal_predicate,
                snapshot=snapshot,
            )
        rows = _expand_rows(
            rows,
            traversal=traversal,
            destination=destination,
            proofs=traversal_result.relation_paths,
            preserve_unmatched=is_terminal and preserve_terminal_unmatched,
        )
        current_table_id = traversal_result.record_set.table_id
    return rows, scanned_record_count, traversed_edge_count, current_table_id


def _row_record_set(
    rows: tuple[JoinedFactRowV1, ...],
    table_id: UUID,
) -> AuthorizedRecordSet:
    by_id: dict[UUID, AuthorizedRecord] = {}
    source_view_ids: set[UUID] = set()
    for row in rows:
        record = _row_record(row, table_id)
        by_id[record.record_id] = record
        source_view_ids.update(record.source_view_ids)
    return AuthorizedRecordSet(
        table_id=table_id,
        records=tuple(by_id[key] for key in sorted(by_id, key=str)),
        scanned_record_count=len(by_id),
        source_view_ids=tuple(sorted(source_view_ids, key=str)),
        complete=True,
    )


def _expand_rows(
    rows: tuple[JoinedFactRowV1, ...],
    *,
    traversal: QueryTraversalSpec,
    destination: AuthorizedRecordSet,
    proofs: tuple[RelationPathProof, ...],
    preserve_unmatched: bool = False,
) -> tuple[JoinedFactRowV1, ...]:
    destination_by_id = {item.record_id: item for item in destination.records}
    origin_table_id = (
        traversal.link_source_table_id
        if traversal.direction == "forward"
        else traversal.link_target_table_id
    )
    proofs_by_origin: dict[UUID, list[tuple[RelationPathProof, UUID]]] = {}
    for proof in proofs:
        if traversal.direction == "forward":
            origin_id = proof.link_source_record_id
            destination_id = proof.link_target_record_id
        else:
            origin_id = proof.link_target_record_id
            destination_id = proof.link_source_record_id
        proofs_by_origin.setdefault(origin_id, []).append((proof, destination_id))

    expanded: list[JoinedFactRowV1] = []
    for row in rows:
        origin = _row_record(row, origin_table_id)
        matches = sorted(
            proofs_by_origin.get(origin.record_id, ()),
            key=lambda item: _proof_sort_key(item[0]),
        )
        accepted = False
        for proof, destination_id in matches:
            record = destination_by_id.get(destination_id)
            if record is None:
                continue
            if any(item.table_id == record.table_id for item in row.records_by_table):
                raise AuthorizedQueryDenied("authorized_query_relation_cycle")
            records = tuple(
                sorted(
                    (*row.records_by_table, record), key=lambda item: str(item.table_id)
                )
            )
            versions = _unique_versions((*row.source_versions, _source_version(record)))
            expanded.append(
                JoinedFactRowV1(
                    root_record_id=row.root_record_id,
                    records_by_table=records,
                    relation_path_proofs=tuple(
                        sorted(
                            (*row.relation_path_proofs, proof),
                            key=_proof_sort_key,
                        )
                    ),
                    source_versions=versions,
                )
            )
            accepted = True
        if preserve_unmatched and not accepted:
            expanded.append(row)
    return _deduplicate_rows(expanded)


def _deduplicate_rows(rows: Iterable[JoinedFactRowV1]) -> tuple[JoinedFactRowV1, ...]:
    unique: dict[tuple[tuple[str, str], ...], JoinedFactRowV1] = {}
    for row in rows:
        key = tuple(
            (str(item.table_id), str(item.record_id)) for item in row.records_by_table
        )
        existing = unique.get(key)
        if existing is None:
            unique[key] = row
            continue
        unique[key] = JoinedFactRowV1(
            root_record_id=existing.root_record_id,
            records_by_table=existing.records_by_table,
            relation_path_proofs=tuple(
                sorted(
                    {
                        _proof_sort_key(item): item
                        for item in (
                            *existing.relation_path_proofs,
                            *row.relation_path_proofs,
                        )
                    }.values(),
                    key=_proof_sort_key,
                )
            ),
            source_versions=_unique_versions(
                (*existing.source_versions, *row.source_versions)
            ),
        )
    return tuple(unique[key] for key in sorted(unique))


def _merge_independent_path_rows(
    root_rows: tuple[JoinedFactRowV1, ...],
    path_results: tuple[tuple[str, tuple[JoinedFactRowV1, ...]], ...],
    *,
    eligible_root_ids: set[UUID] | None,
) -> tuple[JoinedFactRowV1, ...]:
    """Join independent traversal branches on their common root identity."""

    merged = tuple(
        row
        for row in root_rows
        if eligible_root_ids is None or row.root_record_id in eligible_root_ids
    )
    for join_mode, path_rows in path_results:
        by_root: dict[UUID, list[JoinedFactRowV1]] = {}
        for row in path_rows:
            by_root.setdefault(row.root_record_id, []).append(row)
        next_rows: list[JoinedFactRowV1] = []
        for row in merged:
            candidates = by_root.get(row.root_record_id, ())
            if not candidates:
                if join_mode == "left":
                    next_rows.append(row)
                continue
            compatible = tuple(
                candidate
                for candidate in candidates
                if _joined_rows_are_compatible(row, candidate)
            )
            if not compatible:
                if join_mode == "left":
                    next_rows.append(row)
                continue
            next_rows.extend(
                _merge_joined_rows(row, candidate) for candidate in compatible
            )
        merged = _deduplicate_rows(next_rows)
    return _deduplicate_rows(merged)


def _joined_rows_are_compatible(
    left: JoinedFactRowV1,
    right: JoinedFactRowV1,
) -> bool:
    if left.root_record_id != right.root_record_id:
        return False
    left_by_table = {item.table_id: item.record_id for item in left.records_by_table}
    return all(
        left_by_table.get(item.table_id, item.record_id) == item.record_id
        for item in right.records_by_table
    )


def _merge_joined_rows(
    left: JoinedFactRowV1,
    right: JoinedFactRowV1,
) -> JoinedFactRowV1:
    records = {item.table_id: item for item in left.records_by_table}
    records.update({item.table_id: item for item in right.records_by_table})
    proofs = {
        _proof_sort_key(item): item
        for item in (*left.relation_path_proofs, *right.relation_path_proofs)
    }
    return JoinedFactRowV1(
        root_record_id=left.root_record_id,
        records_by_table=tuple(records[key] for key in sorted(records, key=str)),
        relation_path_proofs=tuple(proofs[key] for key in sorted(proofs)),
        source_versions=_unique_versions(
            (*left.source_versions, *right.source_versions)
        ),
    )


def _semi_witness_rows(
    rows: tuple[JoinedFactRowV1, ...],
    *,
    snapshot: AuthorizedSchemaSnapshot,
) -> tuple[JoinedFactRowV1, ...]:
    by_root: dict[UUID, JoinedFactRowV1] = {}
    for row in sorted(rows, key=lambda item: _joined_row_sort_key(item, snapshot)):
        by_root.setdefault(row.root_record_id, row)
    return tuple(by_root[key] for key in sorted(by_root, key=str))


def _joined_row_sort_key(
    row: JoinedFactRowV1,
    snapshot: AuthorizedSchemaSnapshot,
) -> tuple[tuple[str, tuple[tuple[int, str, str], ...], str], ...]:
    table_keys = {item.table_id: item.key for item in snapshot.tables}
    field_keys = {
        field.field_id: field.key for table in snapshot.tables for field in table.fields
    }
    return tuple(
        (
            table_keys[record.table_id],
            tuple(
                sorted(
                    (
                        0 if field_keys[value.field_id].endswith("code") else 1,
                        field_keys[value.field_id],
                        _canonical_row_value(value.value),
                    )
                    for value in record.values
                )
            ),
            str(record.record_id),
        )
        for record in sorted(
            row.records_by_table,
            key=lambda item: table_keys[item.table_id],
        )
    )


def _canonical_row_value(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _row_matches_predicate(
    row: JoinedFactRowV1,
    predicate: QueryPredicateNode | None,
    *,
    snapshot: AuthorizedSchemaSnapshot,
) -> bool:
    if predicate is None:
        return True
    if isinstance(predicate, QueryPredicateGroup):
        matches = (
            _row_matches_predicate(row, child, snapshot=snapshot)
            for child in predicate.children
        )
        return all(matches) if predicate.operator == "and" else any(matches)
    if not isinstance(predicate, QueryPredicateLeaf):
        raise AuthorizedQueryDenied("authorized_query_predicate_invalid")
    record = next(
        (item for item in row.records_by_table if item.table_id == predicate.table_id),
        None,
    )
    if record is None:
        return False
    filtered = filter_records(
        AuthorizedRecordSet(
            table_id=record.table_id,
            records=(record,),
            scanned_record_count=1,
            source_view_ids=record.source_view_ids,
            complete=True,
        ),
        predicate=predicate,
        snapshot=snapshot,
    )
    return bool(filtered.records)


def _apply_presentation(
    plan: AuthorizedQueryPlanV1,
    rows: tuple[JoinedFactRowV1, ...],
    final_table_id: UUID,
    snapshot: AuthorizedSchemaSnapshot,
) -> tuple[
    tuple[JoinedFactRowV1, ...],
    tuple[AuthorizedRecord, ...],
    tuple[StructuredGroup, ...],
    tuple[StructuredAggregate, ...],
    bool,
    UUID,
]:
    aggregate_table_ids = {item.table_id for item in plan.aggregates}
    group_table_ids = {
        _field_table_id(snapshot, field_id) for field_id in plan.group_by_field_ids
    }
    field_sort_table_ids = {
        item.table_id for item in plan.sort_rules if item.field_id is not None
    }
    selected_tables = aggregate_table_ids | group_table_ids | field_sort_table_ids
    if len(selected_tables) > 1:
        return _apply_joined_aggregate_presentation(plan, rows, snapshot)
    primary_table_id = next(iter(selected_tables), final_table_id)
    if aggregate_table_ids and aggregate_table_ids != {primary_table_id}:
        raise AuthorizedQueryDenied(
            "authorized_query_joined_aggregate_scope_unsupported"
        )
    for aggregate in plan.aggregates:
        if any(
            leaf.table_id != aggregate.table_id
            for leaf in (
                ()
                if aggregate.filter_predicate is None
                else _predicate_leaves(aggregate.filter_predicate)
            )
        ):
            raise AuthorizedQueryDenied(
                "authorized_query_joined_aggregate_scope_unsupported"
            )

    records = _records_from_rows(rows, primary_table_id)
    aggregate_result = execute_authorized_aggregates(
        records=AuthorizedRecordSet(
            table_id=primary_table_id,
            records=records,
            scanned_record_count=len(records),
            source_view_ids=(),
            complete=True,
        ),
        group_by_field_ids=plan.group_by_field_ids,
        aggregates=plan.aggregates,
        sort_rules=plan.sort_rules,
        limit=plan.limit,
        snapshot=snapshot,
    )
    selected_ids = {item.record_id for item in aggregate_result.records}
    optional_primary = any(
        path.target_table_id == primary_table_id and path.join_mode == "left"
        for path in plan.traversal_paths
    )
    selected_rows = (
        rows
        if not selected_ids and optional_primary
        else tuple(
            row
            for row in rows
            if (
                (record := _row_record_or_none(row, primary_table_id)) is not None
                and record.record_id in selected_ids
            )
        )
    )
    return (
        selected_rows,
        aggregate_result.records,
        aggregate_result.groups,
        aggregate_result.aggregates,
        aggregate_result.truncated,
        primary_table_id,
    )


def _apply_joined_aggregate_presentation(
    plan: AuthorizedQueryPlanV1,
    rows: tuple[JoinedFactRowV1, ...],
    snapshot: AuthorizedSchemaSnapshot,
) -> tuple[
    tuple[JoinedFactRowV1, ...],
    tuple[AuthorizedRecord, ...],
    tuple[StructuredGroup, ...],
    tuple[StructuredAggregate, ...],
    bool,
    UUID,
]:
    aggregate_table_ids = {item.table_id for item in plan.aggregates}
    if len(aggregate_table_ids) != 1 or plan.sort_rules:
        raise AuthorizedQueryDenied(
            "authorized_query_joined_aggregate_scope_unsupported"
        )
    primary_table_id = next(iter(aggregate_table_ids))
    aggregate_values: list[StructuredAggregate] = []
    rows_by_group: dict[str, list[JoinedFactRowV1]] = {}
    keys_by_group: dict[str, tuple[object, ...]] = {}
    record_ids_by_group: dict[str, set[UUID]] = {}
    having_key_sets: list[set[str]] = []

    for aggregate in plan.aggregates:
        grouped: dict[str, list[JoinedFactRowV1]] = {}
        group_keys: dict[str, tuple[object, ...]] = {}
        for row in rows:
            if _row_record_or_none(row, aggregate.table_id) is None:
                continue
            if aggregate.filter_predicate is not None and not _row_matches_predicate(
                row,
                aggregate.filter_predicate,
                snapshot=snapshot,
            ):
                continue
            key = tuple(
                _row_field_value(row, field_id, snapshot=snapshot)
                for field_id in aggregate.group_by_field_ids
            )
            canonical = _canonical_group_key(key)
            group_keys[canonical] = key
            grouped.setdefault(canonical, []).append(row)
        if not aggregate.group_by_field_ids:
            grouped = {_canonical_group_key(()): list(rows)}
            group_keys = {_canonical_group_key(()): ()}

        accepted_keys: set[str] = set()
        for canonical in sorted(grouped):
            group_rows = tuple(grouped[canonical])
            records = _unique_records_from_rows(group_rows, aggregate.table_id)
            scalar_spec = aggregate.model_copy(
                update={
                    "filter_predicate": None,
                    "group_by_field_ids": (),
                    "having": None,
                }
            )
            scalar = execute_authorized_aggregates(
                records=AuthorizedRecordSet(
                    table_id=aggregate.table_id,
                    records=records,
                    scanned_record_count=len(records),
                    source_view_ids=(),
                    complete=True,
                ),
                group_by_field_ids=(),
                aggregates=(scalar_spec,),
                sort_rules=(),
                limit=None,
                snapshot=snapshot,
            ).aggregates[0]
            if aggregate.having is not None and not _joined_having_matches(
                scalar.value,
                aggregate.having.operator,
                aggregate.having.value,
            ):
                continue
            accepted_keys.add(canonical)
            key = group_keys[canonical]
            aggregate_values.append(
                StructuredAggregate(
                    aggregate_id=aggregate.aggregate_id,
                    group_key=None if not key else list(key),
                    value=scalar.value,
                )
            )
            keys_by_group[canonical] = key
            rows_by_group.setdefault(canonical, []).extend(group_rows)
            record_ids_by_group.setdefault(canonical, set()).update(
                item.record_id for item in records
            )
        if aggregate.having is not None:
            having_key_sets.append(accepted_keys)

    eligible_keys = set(rows_by_group)
    if having_key_sets:
        eligible_keys &= set.intersection(*having_key_sets)
    ordered_keys = sorted(eligible_keys)
    truncated = plan.limit is not None and len(ordered_keys) > plan.limit
    if plan.limit is not None:
        ordered_keys = ordered_keys[: plan.limit]
    selected_keys = set(ordered_keys)
    aggregate_values = [
        item
        for item in aggregate_values
        if _canonical_group_key(() if item.group_key is None else tuple(item.group_key))
        in selected_keys
    ]
    selected_rows = _deduplicate_rows(
        row for key in ordered_keys for row in rows_by_group[key]
    )
    primary_records = _unique_records_from_rows(selected_rows, primary_table_id)
    groups = tuple(
        StructuredGroup(
            group_key=keys_by_group[key],
            record_ids=tuple(sorted(record_ids_by_group[key], key=str)),
        )
        for key in ordered_keys
        if keys_by_group[key]
    )
    return (
        selected_rows,
        primary_records,
        groups,
        tuple(
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
        truncated,
        primary_table_id,
    )


def _project_result_records(
    rows: tuple[JoinedFactRowV1, ...],
    *,
    primary_records: tuple[AuthorizedRecord, ...],
    primary_table_id: UUID,
    projection_field_ids: tuple[UUID, ...],
    snapshot: AuthorizedSchemaSnapshot,
) -> tuple[StructuredRecord, ...]:
    projection_by_table: dict[UUID, list[UUID]] = {}
    for field_id in projection_field_ids:
        projection_by_table.setdefault(_field_table_id(snapshot, field_id), []).append(
            field_id
        )
    output_tables = set(projection_by_table)
    if not output_tables:
        output_tables.add(primary_table_id)
        projection_by_table[primary_table_id] = []

    result: list[StructuredRecord] = []
    emitted: set[tuple[UUID, UUID]] = set()

    def emit(record: AuthorizedRecord) -> None:
        identity = (record.table_id, record.record_id)
        if identity in emitted or record.table_id not in output_tables:
            return
        fields = tuple(projection_by_table[record.table_id])
        projected = project_records(
            AuthorizedRecordSet(
                table_id=record.table_id,
                records=(record,),
                scanned_record_count=1,
                source_view_ids=record.source_view_ids,
                complete=True,
            ),
            fields,
        ).records[0]
        result.append(
            StructuredRecord(
                record_id=projected.record_id,
                table_id=projected.table_id,
                values=projected.values,
            )
        )
        emitted.add(identity)

    for record in primary_records:
        emit(record)
    for row in rows:
        for record in sorted(
            row.records_by_table,
            key=lambda item: (str(item.table_id), str(item.record_id)),
        ):
            emit(record)
    return tuple(result)


def _records_from_rows(
    rows: tuple[JoinedFactRowV1, ...],
    table_id: UUID,
) -> tuple[AuthorizedRecord, ...]:
    values: dict[UUID, AuthorizedRecord] = {}
    for row in rows:
        record = _row_record_or_none(row, table_id)
        if record is not None:
            values[record.record_id] = record
    return tuple(values[key] for key in sorted(values, key=str))


def _unique_records_from_rows(
    rows: tuple[JoinedFactRowV1, ...],
    table_id: UUID,
) -> tuple[AuthorizedRecord, ...]:
    return _records_from_rows(rows, table_id)


def _row_field_value(
    row: JoinedFactRowV1,
    field_id: UUID,
    *,
    snapshot: AuthorizedSchemaSnapshot,
) -> object:
    record = _row_record(row, _field_table_id(snapshot, field_id))
    value = next(
        (item.value for item in record.values if item.field_id == field_id), None
    )
    if value is None:
        raise AuthorizedQueryDenied("authorized_query_group_field_unavailable")
    return value


def _canonical_group_key(value: tuple[object, ...]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _joined_having_matches(value: object, operator: str, expected: object) -> bool:
    if operator == "eq":
        return value == expected
    if operator == "ne":
        return value != expected
    try:
        if operator == "gt":
            return value > expected
        if operator == "gte":
            return value >= expected
        if operator == "lt":
            return value < expected
        if operator == "lte":
            return value <= expected
    except TypeError as exc:
        raise AuthorizedQueryDenied("authorized_query_having_type_invalid") from exc
    raise AuthorizedQueryDenied("authorized_query_having_operator_invalid")


def _row_record(row: JoinedFactRowV1, table_id: UUID) -> AuthorizedRecord:
    record = _row_record_or_none(row, table_id)
    if record is None:
        raise AuthorizedQueryDenied("authorized_query_joined_row_incomplete")
    return record


def _row_record_or_none(
    row: JoinedFactRowV1,
    table_id: UUID,
) -> AuthorizedRecord | None:
    return next(
        (item for item in row.records_by_table if item.table_id == table_id),
        None,
    )


def _field_table_id(snapshot: AuthorizedSchemaSnapshot, field_id: UUID) -> UUID:
    for table in snapshot.tables:
        if any(field.field_id == field_id for field in table.fields):
            return table.table_id
    raise AuthorizedQueryDenied("authorized_query_field_not_authorized")


def _source_version(record: AuthorizedRecord) -> SourceRecordVersion:
    return SourceRecordVersion(
        table_id=record.table_id,
        record_id=record.record_id,
        record_version=record.version,
    )


def _unique_versions(
    values: Iterable[SourceRecordVersion],
) -> tuple[SourceRecordVersion, ...]:
    unique = {(item.table_id, item.record_id): item for item in values}
    return tuple(
        unique[key]
        for key in sorted(unique, key=lambda item: (str(item[0]), str(item[1])))
    )


def _selected_relation_paths(
    rows: tuple[JoinedFactRowV1, ...],
) -> tuple[RelationPathProof, ...]:
    unique = {
        _proof_sort_key(proof): proof
        for row in rows
        for proof in row.relation_path_proofs
    }
    return tuple(unique[key] for key in sorted(unique))


def _selected_source_versions(
    rows: tuple[JoinedFactRowV1, ...],
) -> tuple[SourceRecordVersion, ...]:
    return _unique_versions(version for row in rows for version in row.source_versions)


def _proof_sort_key(proof: RelationPathProof) -> tuple[str, ...]:
    return (
        proof.traversal_id,
        str(proof.link_source_table_id),
        str(proof.link_source_record_id),
        str(proof.link_field_id),
        str(proof.link_target_table_id),
        str(proof.link_target_record_id),
        proof.direction,
    )


def _ordered_ids(values: Iterable[UUID]) -> tuple[UUID, ...]:
    return tuple(sorted(set(values), key=str))


__all__ = ["JoinedFactRowV1", "execute_authorized_query"]
