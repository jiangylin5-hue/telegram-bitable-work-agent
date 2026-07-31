"""Fresh-authority EvidenceBundle assembly for Stage12-D."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from app.schemas.authorized_query_plan import StructuredQueryResultV1
from app.schemas.retrieval_v2 import (
    EvidenceAggregateV2,
    EvidenceBundleV2,
    EvidenceFieldValueV2,
    EvidenceNodeV2,
    RetrievalCandidateV2,
    RetrievalRelationEdgeProjectionV2,
    RetrievalRelationV2,
    RetrievalRequestV2,
    canonical_retrieval_sha256,
)
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.authorized_query_records import (
    AuthorizedQueryContext,
    AuthorizedQueryDenied,
    build_authorized_query_context,
)
from app.services.retrieval_v2_hybrid import (
    AuthorizedRetrievalResultV2,
    RetrievalV2Denied,
)
from app.services.retrieval_v2_scope import effective_retrieval_scope_hash
from app.services.stage06_platform import PlatformValidationError, read_record_for_actor


@dataclass(frozen=True, slots=True)
class EvidenceCitationV2:
    """Backend-owned safe citation target; it contains no record field values."""

    evidence_id: str
    kind: str
    table_id: UUID
    record_id: UUID | None
    source_version: int


@dataclass(frozen=True, slots=True)
class EvidenceAssemblyV2:
    bundle: EvidenceBundleV2
    citations: tuple[EvidenceCitationV2, ...]

    def __post_init__(self) -> None:
        if {item.evidence_id for item in self.citations} != {
            item.evidence_id for item in self.bundle.nodes
        }:
            raise RetrievalV2Denied("retrieval_citation_mapping_invalid")


def assemble_evidence_bundle(
    *,
    request: RetrievalRequestV2,
    context: AuthorizedQueryContext,
    retrieval: AuthorizedRetrievalResultV2,
    structured_query_result: StructuredQueryResultV1 | None,
    active_source_versions: Mapping[str, int],
    aggregate_output_keys: Mapping[str, str] | None = None,
) -> EvidenceAssemblyV2:
    """Revalidate effective authority and source versions before releasing evidence."""

    current = _current_context(request, context)
    _validate_query_result(request, current, structured_query_result)
    _validate_candidates(request, retrieval, active_source_versions)

    selected = retrieval.candidates[: request.max_evidence_nodes]
    budget_cut = len(selected) < len(retrieval.candidates)
    nodes = tuple(
        _build_node(
            candidate,
            current,
            objective_id=request.objective_id,
        )
        for candidate in selected
    )
    evidence_by_record = {
        node.record_id: node for node in nodes if node.record_id is not None
    }
    relations = _build_relations(
        request=request,
        context=current,
        edges=retrieval.relation_edges,
        evidence_by_record=evidence_by_record,
    )
    aggregates = _build_aggregates(
        request,
        structured_query_result,
        aggregate_output_keys=aggregate_output_keys,
    )
    truncated = (
        retrieval.truncated
        or budget_cut
        or (structured_query_result is not None and structured_query_result.truncated)
    )
    values = {
        "version": "evidence-bundle.v2",
        "objective_id": request.objective_id,
        "query_result_ref": request.query_result_ref,
        "nodes": nodes,
        "relations": relations,
        "aggregates": aggregates,
        "scope_hash": request.scope_hash,
        "complete": not truncated,
        "truncated": truncated,
    }
    bundle = EvidenceBundleV2(
        **values,
        bundle_hash=canonical_retrieval_sha256(values),
    )
    citations = tuple(
        EvidenceCitationV2(
            evidence_id=node.evidence_id,
            kind=node.kind,
            table_id=node.table_id,
            record_id=node.record_id,
            source_version=node.source_version,
        )
        for node in nodes
    )
    return EvidenceAssemblyV2(bundle=bundle, citations=citations)


def _current_context(
    request: RetrievalRequestV2,
    context: AuthorizedQueryContext,
) -> AuthorizedQueryContext:
    if (
        request.workspace_id != context.workspace_id
        or request.base_id != context.base_id
        or request.scope_hash != effective_retrieval_scope_hash(context)
        or request.schema_hash != context.snapshot.schema_hash
    ):
        raise RetrievalV2Denied("retrieval_evidence_scope_denied")
    try:
        snapshot = build_authorized_schema_snapshot(
            context.uow,
            workspace_id=context.workspace_id,
            employee_id=context.employee_id,
            actor=context.actor,
        )
        current = build_authorized_query_context(
            context.uow,
            workspace_id=context.workspace_id,
            base_id=context.base_id,
            employee_id=context.employee_id,
            actor=context.actor,
            snapshot=snapshot,
            chat_authorized_view_ids=(
                None if context.allow_whole_table else context.scope_view_ids
            ),
            allow_whole_table=context.allow_whole_table,
        )
    except (PlatformValidationError, AuthorizedQueryDenied) as exc:
        raise RetrievalV2Denied("retrieval_evidence_scope_denied") from exc
    if (
        effective_retrieval_scope_hash(current) != request.scope_hash
        or current.snapshot.schema_hash != request.schema_hash
        or not set(request.table_ids).issubset(current.employee_table_ids)
    ):
        raise RetrievalV2Denied("retrieval_evidence_scope_drift")
    return current


def _validate_query_result(
    request: RetrievalRequestV2,
    context: AuthorizedQueryContext,
    result: StructuredQueryResultV1 | None,
) -> None:
    if result is None:
        return
    if (
        request.query_result_ref is None
        or result.scope_hash != context.snapshot.scope_hash
        or result.schema_hash != request.schema_hash
    ):
        raise RetrievalV2Denied("retrieval_query_result_scope_denied")


def _validate_candidates(
    request: RetrievalRequestV2,
    retrieval: AuthorizedRetrievalResultV2,
    active_source_versions: Mapping[str, int],
) -> None:
    for candidate in retrieval.candidates:
        if (
            candidate.scope_hash != request.scope_hash
            or candidate.table_id not in set(request.table_ids)
            or active_source_versions.get(candidate.source_id)
            != candidate.source_version
        ):
            raise RetrievalV2Denied("retrieval_evidence_source_stale")


def _build_node(
    candidate: RetrievalCandidateV2,
    context: AuthorizedQueryContext,
    *,
    objective_id: str,
) -> EvidenceNodeV2:
    table = next(
        (
            item
            for item in context.snapshot.tables
            if item.table_id == candidate.table_id
        ),
        None,
    )
    if table is None:
        raise RetrievalV2Denied("retrieval_evidence_scope_denied")
    fields_by_id = {field.field_id: field for field in table.fields}
    if not set(candidate.field_ids).issubset(fields_by_id):
        raise RetrievalV2Denied("retrieval_evidence_field_denied")

    if candidate.record_id is None:
        fields = tuple(
            EvidenceFieldValueV2(
                field_id=field_id,
                field_key=fields_by_id[field_id].key,
                value={
                    "name": fields_by_id[field_id].name,
                    "field_type": fields_by_id[field_id].field_type,
                    "aliases": list(fields_by_id[field_id].aliases),
                    "choices": list(fields_by_id[field_id].choices),
                },
            )
            for field_id in candidate.field_ids
        )
        kind = "schema"
    else:
        try:
            record = read_record_for_actor(
                context.uow,
                candidate.record_id,
                actor=context.actor,
            )
        except PlatformValidationError as exc:
            raise RetrievalV2Denied("retrieval_evidence_source_stale") from exc
        if (
            record["table_id"] != str(candidate.table_id)
            or record["version"] != candidate.source_version
        ):
            raise RetrievalV2Denied("retrieval_evidence_source_stale")
        safe_values = record["values"]
        fields = tuple(
            EvidenceFieldValueV2(
                field_id=field_id,
                field_key=fields_by_id[field_id].key,
                value=safe_values[fields_by_id[field_id].key],
            )
            for field_id in candidate.field_ids
            if fields_by_id[field_id].key in safe_values
        )
        kind = "record"

    evidence_identity = {
        "objective_id": objective_id,
        "scope_hash": effective_retrieval_scope_hash(context),
        "source_id": candidate.source_id,
        "source_version": candidate.source_version,
        "content_hash": candidate.content_hash,
    }
    return EvidenceNodeV2(
        evidence_id=f"ev-{canonical_retrieval_sha256(evidence_identity)[:32]}",
        kind=kind,
        source_id=candidate.source_id,
        source_version=candidate.source_version,
        table_id=candidate.table_id,
        record_id=candidate.record_id,
        fields=fields,
        content_hash=candidate.content_hash,
    )


def _build_relations(
    *,
    request: RetrievalRequestV2,
    context: AuthorizedQueryContext,
    edges: tuple[RetrievalRelationEdgeProjectionV2, ...],
    evidence_by_record: dict[UUID, EvidenceNodeV2],
) -> tuple[RetrievalRelationV2, ...]:
    visible_fields = {
        field.field_id: field
        for table in context.snapshot.tables
        for field in table.fields
    }
    relations: list[RetrievalRelationV2] = []
    for edge in edges:
        source = evidence_by_record.get(edge.source_record_id)
        target = evidence_by_record.get(edge.target_record_id)
        link_field = visible_fields.get(edge.link_field_id)
        if source is None or target is None:
            continue
        if (
            edge.scope_hash != request.scope_hash
            or link_field is None
            or link_field.field_type != "linked_record"
            or link_field.table_id != edge.source_table_id
            or source.table_id != edge.source_table_id
            or target.table_id != edge.target_table_id
            or source.source_version != edge.source_version
            or target.source_version != edge.target_version
        ):
            raise RetrievalV2Denied("retrieval_relation_proof_invalid")
        relations.append(
            RetrievalRelationV2(
                relation_id=edge.relation_id,
                from_evidence_id=source.evidence_id,
                to_evidence_id=target.evidence_id,
                link_field_id=edge.link_field_id,
                direction=edge.direction,
                source_version=edge.source_version,
                target_version=edge.target_version,
                scope_hash=edge.scope_hash,
            )
        )
    return tuple(
        sorted(
            relations,
            key=lambda item: (
                item.relation_id,
                item.from_evidence_id,
                item.to_evidence_id,
            ),
        )
    )


def _build_aggregates(
    request: RetrievalRequestV2,
    result: StructuredQueryResultV1 | None,
    *,
    aggregate_output_keys: Mapping[str, str] | None,
) -> tuple[EvidenceAggregateV2, ...]:
    if result is None:
        if aggregate_output_keys:
            raise RetrievalV2Denied("retrieval_aggregate_binding_invalid")
        return ()
    assert request.query_result_ref is not None
    output_keys = {} if aggregate_output_keys is None else dict(aggregate_output_keys)
    aggregate_ids = {item.aggregate_id for item in result.aggregates}
    if (
        set(output_keys) != aggregate_ids
        or any(
            not isinstance(value, str) or not value or value != value.strip()
            for value in output_keys.values()
        )
        or len(set(output_keys.values())) != len(output_keys)
    ):
        raise RetrievalV2Denied("retrieval_aggregate_binding_invalid")
    return tuple(
        EvidenceAggregateV2(
            aggregate_id=item.aggregate_id,
            output_key=output_keys[item.aggregate_id],
            group_key=item.group_key,
            value=item.value,
            query_result_ref=request.query_result_ref,
        )
        for item in result.aggregates
    )


__all__ = [
    "EvidenceAssemblyV2",
    "EvidenceCitationV2",
    "assemble_evidence_bundle",
]
