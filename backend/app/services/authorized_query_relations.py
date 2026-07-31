"""Permission-preserving linked-record traversal for Stage12-C."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.schemas.authorized_query_plan import (
    AuthorizedRelationSpec,
    QueryTraversalSpec,
    RelationPathProof,
    SourceRecordVersion,
)
from app.services.authorized_query_records import (
    AuthorizedQueryContext,
    AuthorizedQueryDenied,
    AuthorizedRecord,
    AuthorizedRecordSet,
    scan_authorized_records,
)


@dataclass(frozen=True, slots=True)
class AuthorizedTraversalResult:
    record_set: AuthorizedRecordSet
    relation_paths: tuple[RelationPathProof, ...]
    traversed_edge_count: int
    source_versions: tuple[SourceRecordVersion, ...]


def traverse_authorized_links(
    *,
    context: AuthorizedQueryContext,
    source_records: AuthorizedRecordSet,
    traversals: tuple[QueryTraversalSpec, ...],
    catalog: tuple[AuthorizedRelationSpec, ...],
    max_relation_expansions: int = 1000,
    max_scan_rows: int = 5000,
    required_field_ids_by_table: dict[UUID, tuple[UUID, ...]] | None = None,
) -> AuthorizedTraversalResult:
    if len(traversals) > 2:
        raise AuthorizedQueryDenied("authorized_query_traversal_depth_exceeded")
    if max_relation_expansions < 1 or max_relation_expansions > 1000:
        raise AuthorizedQueryDenied("authorized_query_relation_budget_invalid")
    relations_by_id = {item.relation_id: item for item in catalog}
    if len(relations_by_id) != len(catalog):
        raise AuthorizedQueryDenied("authorized_query_relation_not_authorized")

    current = source_records
    proofs: list[RelationPathProof] = []
    source_versions: dict[tuple[UUID, UUID], SourceRecordVersion] = {
        (item.table_id, item.record_id): SourceRecordVersion(
            table_id=item.table_id,
            record_id=item.record_id,
            record_version=item.version,
        )
        for item in source_records.records
    }
    seen_record_identities = set(source_versions)
    visited_edges: set[tuple[UUID, UUID, UUID, UUID, str]] = set()
    for traversal in traversals:
        relation = relations_by_id.get(traversal.relation_id)
        if relation is None or not _traversal_matches_relation(traversal, relation):
            raise AuthorizedQueryDenied("authorized_query_relation_not_authorized")
        _validate_relation_scope(context, relation)
        origin_table_id, destination_table_id = _direction_tables(
            relation,
            traversal.direction,
        )
        if current.table_id != origin_table_id:
            raise AuthorizedQueryDenied("authorized_query_traversal_not_contiguous")

        destination = scan_authorized_records(
            context=context,
            table_id=destination_table_id,
            required_field_ids=(
                _all_table_field_ids(context, destination_table_id)
                if required_field_ids_by_table is None
                else required_field_ids_by_table.get(destination_table_id, ())
            ),
            max_scan_rows=max_scan_rows,
        )
        authorized_destination = {item.record_id: item for item in destination.records}
        accepted_destination_ids: set[UUID] = set()
        hop_proofs: list[RelationPathProof] = []
        hop_edge_count = 0
        if traversal.direction == "forward":
            for source in current.records:
                for target_record_id in _forward_target_ids(
                    source,
                    relation.link_field_id,
                ):
                    target = authorized_destination.get(target_record_id)
                    if target is None:
                        continue
                    edge_key = (
                        relation.link_source_table_id,
                        source.record_id,
                        relation.link_field_id,
                        target.record_id,
                        traversal.direction,
                    )
                    if edge_key in visited_edges:
                        continue
                    _reject_record_cycle(
                        target,
                        seen_record_identities=seen_record_identities,
                    )
                    visited_edges.add(edge_key)
                    accepted_destination_ids.add(target.record_id)
                    hop_edge_count += 1
                    _enforce_edge_budget(
                        total=len(visited_edges),
                        hop=hop_edge_count,
                        global_limit=max_relation_expansions,
                        hop_limit=traversal.max_expansion,
                    )
                    hop_proofs.append(
                        _proof(
                            traversal,
                            source_record_id=source.record_id,
                            target_record_id=target.record_id,
                        )
                    )
        else:
            for target in current.records:
                for link in context.uow.list_record_links_to(target.record_id):
                    if not _reverse_link_matches(link, relation, target.record_id):
                        continue
                    source = authorized_destination.get(link.source_record_id)
                    if source is None:
                        continue
                    edge_key = (
                        relation.link_source_table_id,
                        source.record_id,
                        relation.link_field_id,
                        target.record_id,
                        traversal.direction,
                    )
                    if edge_key in visited_edges:
                        continue
                    _reject_record_cycle(
                        source,
                        seen_record_identities=seen_record_identities,
                    )
                    visited_edges.add(edge_key)
                    accepted_destination_ids.add(source.record_id)
                    hop_edge_count += 1
                    _enforce_edge_budget(
                        total=len(visited_edges),
                        hop=hop_edge_count,
                        global_limit=max_relation_expansions,
                        hop_limit=traversal.max_expansion,
                    )
                    hop_proofs.append(
                        _proof(
                            traversal,
                            source_record_id=source.record_id,
                            target_record_id=target.record_id,
                        )
                    )

        current = _subset_record_set(destination, accepted_destination_ids)
        for item in current.records:
            source_versions[(item.table_id, item.record_id)] = SourceRecordVersion(
                table_id=item.table_id,
                record_id=item.record_id,
                record_version=item.version,
            )
        seen_record_identities.update(
            (item.table_id, item.record_id) for item in current.records
        )
        proofs.extend(hop_proofs)

    return AuthorizedTraversalResult(
        record_set=current,
        relation_paths=tuple(sorted(proofs, key=_proof_sort_key)),
        traversed_edge_count=len(visited_edges),
        source_versions=tuple(
            source_versions[key]
            for key in sorted(
                source_versions,
                key=lambda item: (str(item[0]), str(item[1])),
            )
        ),
    )


def _validate_relation_scope(
    context: AuthorizedQueryContext,
    relation: AuthorizedRelationSpec,
) -> None:
    tables = {item.table_id: item for item in context.snapshot.tables}
    source = tables.get(relation.link_source_table_id)
    if source is None or relation.link_target_table_id not in tables:
        raise AuthorizedQueryDenied("authorized_query_relation_scope_denied")
    field = next(
        (item for item in source.fields if item.field_id == relation.link_field_id),
        None,
    )
    if field is None or field.field_type != "linked_record":
        raise AuthorizedQueryDenied("authorized_query_relation_scope_denied")


def _traversal_matches_relation(
    traversal: QueryTraversalSpec,
    relation: AuthorizedRelationSpec,
) -> bool:
    return (
        traversal.link_source_table_id == relation.link_source_table_id
        and traversal.link_field_id == relation.link_field_id
        and traversal.link_target_table_id == relation.link_target_table_id
    )


def _direction_tables(
    relation: AuthorizedRelationSpec,
    direction: str,
) -> tuple[UUID, UUID]:
    if direction == "forward":
        return relation.link_source_table_id, relation.link_target_table_id
    return relation.link_target_table_id, relation.link_source_table_id


def _all_table_field_ids(
    context: AuthorizedQueryContext,
    table_id: UUID,
) -> tuple[UUID, ...]:
    table = next(
        (item for item in context.snapshot.tables if item.table_id == table_id),
        None,
    )
    if table is None:
        raise AuthorizedQueryDenied("authorized_query_relation_scope_denied")
    return tuple(item.field_id for item in table.fields)


def _forward_target_ids(
    source: AuthorizedRecord,
    link_field_id: UUID,
) -> tuple[UUID, ...]:
    value = next(
        (item.value for item in source.values if item.field_id == link_field_id),
        None,
    )
    if value is None:
        raise AuthorizedQueryDenied("authorized_query_link_field_unavailable")
    if not isinstance(value, list):
        raise AuthorizedQueryDenied("authorized_query_link_value_invalid")
    parsed: list[UUID] = []
    for cell in value:
        raw_id = cell.get("id") if isinstance(cell, dict) else cell
        try:
            parsed.append(UUID(str(raw_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise AuthorizedQueryDenied("authorized_query_link_value_invalid") from exc
    return tuple(dict.fromkeys(parsed))


def _reverse_link_matches(
    link: object,
    relation: AuthorizedRelationSpec,
    target_record_id: UUID,
) -> bool:
    return (
        getattr(link, "source_table_id", None) == relation.link_source_table_id
        and getattr(link, "source_field_id", None) == relation.link_field_id
        and getattr(link, "target_table_id", None) == relation.link_target_table_id
        and getattr(link, "target_record_id", None) == target_record_id
    )


def _reject_record_cycle(
    record: AuthorizedRecord,
    *,
    seen_record_identities: set[tuple[UUID, UUID]],
) -> None:
    if (record.table_id, record.record_id) in seen_record_identities:
        raise AuthorizedQueryDenied("authorized_query_relation_cycle")


def _enforce_edge_budget(
    *,
    total: int,
    hop: int,
    global_limit: int,
    hop_limit: int,
) -> None:
    if total > global_limit or hop > hop_limit:
        raise AuthorizedQueryDenied("authorized_query_relation_budget_exceeded")


def _proof(
    traversal: QueryTraversalSpec,
    *,
    source_record_id: UUID,
    target_record_id: UUID,
) -> RelationPathProof:
    return RelationPathProof(
        traversal_id=traversal.traversal_id,
        relation_id=traversal.relation_id,
        direction=traversal.direction,
        link_source_table_id=traversal.link_source_table_id,
        link_source_record_id=source_record_id,
        link_field_id=traversal.link_field_id,
        link_target_table_id=traversal.link_target_table_id,
        link_target_record_id=target_record_id,
    )


def _subset_record_set(
    values: AuthorizedRecordSet,
    record_ids: set[UUID],
) -> AuthorizedRecordSet:
    return AuthorizedRecordSet(
        table_id=values.table_id,
        records=tuple(item for item in values.records if item.record_id in record_ids),
        scanned_record_count=values.scanned_record_count,
        source_view_ids=values.source_view_ids,
        complete=values.complete,
    )


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


__all__ = [
    "AuthorizedTraversalResult",
    "traverse_authorized_links",
]
