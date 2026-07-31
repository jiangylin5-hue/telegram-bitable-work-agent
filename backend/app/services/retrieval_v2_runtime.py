"""Current-scope loader for materialized Stage12 Retrieval V2 candidates."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core.config import Settings
from app.models.stage12_retrieval import (
    Stage12RelationEdge,
    Stage12RetrievalChunk,
    Stage12RetrievalSource,
)
from app.schemas.retrieval_v2 import (
    EmbeddingProfileV1,
    RetrievalProjectionV2,
    RetrievalRelationEdgeProjectionV2,
    RetrievalRequestV2,
)
from app.services.agent_authorized_entity_linker import (
    build_authorized_entity_candidates,
)
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.authorized_query_records import (
    AuthorizedQueryContext,
    build_authorized_query_context,
    scan_authorized_records,
)
from app.services.permissions import Actor
from app.services.retrieval_v2_hybrid import (
    AuthorizedRetrievalResultV2,
    ObjectiveTableQuotaV2,
    RawRetrievalHitV2,
    RetrievalV2Denied,
    retrieve_authorized_candidates,
)
from app.services.retrieval_v2_embeddings import OpenRouterEmbeddingProviderV2
from app.services.retrieval_v2_indexing import (
    MemoryRetrievalIndexUnitOfWork,
    SqlAlchemyRetrievalIndexUnitOfWork,
    request_retrieval_scope_bootstrap,
)
from app.services.retrieval_v2_projection import (
    build_record_field_projections,
    build_record_projection,
    build_relation_projections,
    build_schema_projections,
)
from app.services.retrieval_v2_scope import effective_retrieval_scope_hash
from app.services.retrieval_v2_registration import (
    build_registered_source_projections,
    register_authorized_retrieval_scope,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    SqlAlchemyStage06PlatformUnitOfWork,
    Stage06PlatformUnitOfWork,
)


_MAX_AUTHORIZED_SOURCES = 512
_MAX_AUTHORIZED_RELATION_EDGES = 512
_PROFILE_NAME = "stage12.openrouter-bge-m3-v1"
_MODEL_ID = "baai/bge-m3"
_MODEL_REVISION = "baai/bge-m3-20251117"


def build_stage12_query_embedding_provider(
    settings: Settings,
) -> OpenRouterEmbeddingProviderV2:
    if settings.retrieval_v2_active_profile != _PROFILE_NAME:
        raise RetrievalV2Denied("retrieval_active_profile_unavailable")
    return OpenRouterEmbeddingProviderV2(
        profile=EmbeddingProfileV1(
            version="embedding-profile.v1",
            profile_name=_PROFILE_NAME,
            model_revision=_MODEL_REVISION,
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="openrouter-deny-zdr",
        ),
        api_key=settings.openrouter_api_key or "",
        base_url=settings.openrouter_base_url,
        model_id=_MODEL_ID,
        expected_canonical_slug=_MODEL_REVISION,
    )


def load_authorized_retrieval_v2(
    platform_uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    query: str,
    actor: Actor,
    active_embedding_profile: str,
    query_embedding: tuple[float, ...] | None,
) -> AuthorizedRetrievalResultV2:
    """Release only indexed candidates that still match current authorization/data."""

    if not query or query != query.strip() or not active_embedding_profile:
        raise RetrievalV2Denied("retrieval_runtime_request_invalid")
    snapshot = build_authorized_schema_snapshot(
        platform_uow,
        workspace_id=workspace_id,
        employee_id=employee_id,
        actor=actor,
        require_field_policy_v2=True,
    )
    employee = platform_uow.get_digital_employee(employee_id)
    if employee is None:
        raise RetrievalV2Denied("retrieval_runtime_employee_unavailable")
    table_ids = tuple(item.table_id for item in snapshot.tables if item.fields)
    if not table_ids:
        raise RetrievalV2Denied("retrieval_runtime_table_scope_empty")
    view_ids = tuple(
        sorted((UUID(value) for value in employee.accessible_views), key=str)
    )
    context = build_authorized_query_context(
        platform_uow,
        workspace_id=workspace_id,
        base_id=employee.base_id,
        employee_id=employee_id,
        actor=actor,
        snapshot=snapshot,
        chat_authorized_view_ids=view_ids or None,
        allow_whole_table=not view_ids,
    )
    retrieval_scope_hash = effective_retrieval_scope_hash(context)
    index_uow = _retrieval_index_uow(platform_uow)
    register_authorized_retrieval_scope(
        index_uow,
        context=context,
        now=datetime.now(UTC),
    )
    profile = index_uow.get_profile(active_embedding_profile)
    if (
        profile is None
        or profile.status != "active"
        or profile.retired_at is not None
        or profile.profile_name != _PROFILE_NAME
        or profile.model_revision != _MODEL_REVISION
        or profile.dimension != 1024
        or profile.normalization != "l2"
        or profile.distance_metric != "cosine"
    ):
        raise RetrievalV2Denied("retrieval_active_profile_unavailable")
    if query_embedding is not None:
        _validate_query_embedding(query_embedding, profile.dimension)
    entities = build_authorized_entity_candidates(
        platform_uow,
        query=query,
        actor=actor,
        workspace_id=workspace_id,
        base_id=employee.base_id,
        employee_id=employee_id,
        snapshot=snapshot,
        chat_authorized_view_ids=view_ids or None,
        allow_whole_table=not view_ids,
    )
    exact_record_ids = tuple(sorted({item.entity_id for item in entities}, key=str))
    request = RetrievalRequestV2(
        version="retrieval-request.v2",
        objective_id="runtime-retrieval-01",
        query=query,
        workspace_id=workspace_id,
        base_id=employee.base_id,
        table_ids=table_ids,
        exact_record_ids=exact_record_ids,
        query_result_ref=None,
        scope_hash=retrieval_scope_hash,
        schema_hash=snapshot.schema_hash,
        max_primary_candidates=20,
        max_relation_expansions_per_primary=10,
        max_evidence_nodes=24,
    )
    sources = _authorized_sources(
        index_uow,
        workspace_id=workspace_id,
        base_id=employee.base_id,
        table_ids=table_ids,
        scope_hash=retrieval_scope_hash,
        embedding_profile=active_embedding_profile,
    )
    hits = tuple(
        hit
        for source in sources
        if (
            hit := _current_source_hit(
                platform_uow,
                index_uow=index_uow,
                source=source,
                context=context,
                query=query,
                query_embedding=query_embedding,
            )
        )
        is not None
    )
    exact_set = set(exact_record_ids)
    exact_hits = tuple(item for item in hits if item.record_id in exact_set)
    fuzzy_hits = tuple(
        item
        for item in hits
        if item.record_id not in exact_set and _has_primary_discovery_signal(item)
    )
    relation_edges = _current_authorized_relation_edges(
        platform_uow,
        index_uow=index_uow,
        context=context,
        workspace_id=workspace_id,
        table_ids=table_ids,
    )
    relation_record_ids = {
        record_id
        for edge in relation_edges
        for record_id in (edge.source_record_id, edge.target_record_id)
    }
    relation_target_hits = tuple(
        item for item in hits if item.record_id in relation_record_ids
    )
    quotas = tuple(
        ObjectiveTableQuotaV2(
            table_id=table_id,
            schema_candidates=4,
            record_candidates=8,
        )
        for table_id in table_ids
    )
    return retrieve_authorized_candidates(
        request=request,
        context=context,
        exact_entity_hits=exact_hits,
        fuzzy_hits=fuzzy_hits,
        relation_edges=relation_edges,
        relation_target_hits=relation_target_hits,
        active_embedding_profile=active_embedding_profile,
        table_quotas=quotas,
    )


def _retrieval_index_uow(platform_uow):
    if isinstance(platform_uow, InMemoryStage06PlatformUnitOfWork):
        return platform_uow.stage12_retrieval_uow
    if isinstance(platform_uow, SqlAlchemyStage06PlatformUnitOfWork):
        return SqlAlchemyRetrievalIndexUnitOfWork(platform_uow.session)
    raise RetrievalV2Denied("retrieval_runtime_uow_unsupported")


def _authorized_sources(
    index_uow,
    *,
    workspace_id,
    base_id,
    table_ids,
    scope_hash,
    embedding_profile,
):
    if isinstance(index_uow, SqlAlchemyRetrievalIndexUnitOfWork):
        statement = (
            select(Stage12RetrievalSource)
            .where(
                Stage12RetrievalSource.workspace_id == workspace_id,
                Stage12RetrievalSource.base_id == base_id,
                Stage12RetrievalSource.table_id.in_(table_ids),
                Stage12RetrievalSource.scope_hash == scope_hash,
                Stage12RetrievalSource.embedding_profile == embedding_profile,
                Stage12RetrievalSource.status == "indexed",
                Stage12RetrievalSource.is_active.is_(True),
                Stage12RetrievalSource.revoked_at.is_(None),
            )
            .order_by(Stage12RetrievalSource.updated_at.desc())
            .limit(_MAX_AUTHORIZED_SOURCES + 1)
        )
        sources = list(index_uow.session.scalars(statement))
    elif isinstance(index_uow, MemoryRetrievalIndexUnitOfWork):
        table_set = set(table_ids)
        sources = [
            item
            for item in index_uow.list_sources(
                workspace_id=workspace_id,
                embedding_profile=embedding_profile,
            )
            if item.base_id == base_id
            and item.table_id in table_set
            and item.scope_hash == scope_hash
            and item.status == "indexed"
            and item.is_active
            and item.revoked_at is None
        ]
    else:
        raise RetrievalV2Denied("retrieval_runtime_uow_unsupported")
    if len(sources) > _MAX_AUTHORIZED_SOURCES:
        raise RetrievalV2Denied("retrieval_runtime_candidate_budget_exceeded")
    return tuple(sources)


def _current_source_hit(
    platform_uow,
    *,
    index_uow,
    source,
    context,
    query,
    query_embedding,
):
    projection = _current_projection(platform_uow, context, source)
    if (
        projection is None
        or projection.source_version != source.source_version
        or projection.content_hash != source.content_hash
        or projection.visibility_profile_hash != source.visibility_profile_hash
        or projection.scope_hash != source.scope_hash
        or tuple(source.field_ids) != projection.field_ids
    ):
        return None
    chunks = tuple(
        item
        for item in index_uow.list_chunks(source.id)
        if item.status == "indexed"
        and item.revoked_at is None
        and item.scope_hash == source.scope_hash
        and item.visibility_profile_hash == source.visibility_profile_hash
        and item.embedding_profile == source.embedding_profile
        and item.source_version == source.source_version
    )
    if not chunks:
        return None
    query_terms = set(_keyword_terms(query))
    keyword_score = max(
        (float(len(query_terms & set(item.keyword_terms))) for item in chunks),
        default=0.0,
    )
    semantic_score = max(
        (
            _semantic_similarity(query_embedding, item.embedding)
            for item in chunks
            if query_embedding is not None and item.embedding is not None
        ),
        default=0.0,
    )
    return RawRetrievalHitV2(
        workspace_id=source.workspace_id,
        base_id=source.base_id,
        source_type=source.source_type,
        source_id=source.source_identity,
        source_version=source.source_version,
        table_id=source.table_id,
        record_id=source.record_id,
        field_ids=tuple(source.field_ids),
        scope_hash=source.scope_hash,
        content_hash=source.content_hash,
        embedding_profile=source.embedding_profile,
        keyword_score=keyword_score,
        semantic_score=semantic_score,
        entity_schema_score=_entity_schema_score(context, source.table_id, query),
        freshness_score=1.0,
    )


def _current_projection(
    platform_uow: Stage06PlatformUnitOfWork,
    context: AuthorizedQueryContext,
    source: Stage12RetrievalSource,
) -> RetrievalProjectionV2 | None:
    retrieval_scope_hash = effective_retrieval_scope_hash(context)
    table = next(
        (item for item in context.snapshot.tables if item.table_id == source.table_id),
        None,
    )
    if table is None:
        return None
    visible_ids = frozenset(item.field_id for item in table.fields)
    positions = {
        field.id: field.order_index
        for field in platform_uow.list_fields(table.table_id)
    }
    long_text_ids = frozenset(
        field.id
        for field in platform_uow.list_fields(table.table_id)
        if (field.options or {}).get("retrieval_mode") == "long_text"
        and field.id in visible_ids
    )
    if source.source_type in {"record", "record_field"}:
        if source.record_id is None:
            return None
        records = scan_authorized_records(
            context=context,
            table_id=table.table_id,
            required_field_ids=tuple(sorted(visible_ids, key=str)),
        ).records
        record = next(
            (item for item in records if item.record_id == source.record_id),
            None,
        )
        if record is None or record.version != source.source_version:
            return None
        if source.source_type == "record":
            return build_record_projection(
                context.snapshot,
                record,
                retrieval_scope_hash=retrieval_scope_hash,
                retrievable_field_ids=visible_ids,
                long_text_field_ids=long_text_ids,
                field_positions=positions,
            )
        candidates = build_record_field_projections(
            context.snapshot,
            record,
            retrieval_scope_hash=retrieval_scope_hash,
            retrievable_field_ids=visible_ids,
            long_text_field_ids=long_text_ids,
        )
    else:
        current_version = (platform_uow.get_table(table.table_id).settings or {}).get(
            "stage12_schema_version",
            1,
        )
        if current_version != source.source_version:
            return None
        candidates = build_schema_projections(
            context.snapshot,
            retrieval_scope_hash=retrieval_scope_hash,
            field_positions=positions,
            retrievable_field_ids=visible_ids,
            source_version=current_version,
        )
    return next(
        (
            item
            for item in candidates
            if _normalized_source_id(item.source_id)
            == _normalized_source_id(source.source_identity)
            and item.table_id == source.table_id
        ),
        None,
    )


def _current_authorized_relation_edges(
    platform_uow: Stage06PlatformUnitOfWork,
    *,
    index_uow,
    context: AuthorizedQueryContext,
    workspace_id: UUID,
    table_ids: tuple[UUID, ...],
) -> tuple[RetrievalRelationEdgeProjectionV2, ...]:
    catalog = build_authorized_relation_catalog(platform_uow, context.snapshot)
    if not catalog:
        return ()
    records = tuple(
        record
        for table in context.snapshot.tables
        for record in scan_authorized_records(
            context=context,
            table_id=table.table_id,
            required_field_ids=tuple(
                sorted((field.field_id for field in table.fields), key=str)
            ),
        ).records
    )
    current_edges = build_relation_projections(
        context.snapshot,
        retrieval_scope_hash=effective_retrieval_scope_hash(context),
        records=records,
        catalog=catalog,
    )
    current_by_hash = {edge.edge_hash: edge for edge in current_edges}
    persisted = _authorized_relation_rows(
        index_uow,
        workspace_id=workspace_id,
        table_ids=table_ids,
        scope_hash=effective_retrieval_scope_hash(context),
    )
    selected: dict[str, RetrievalRelationEdgeProjectionV2] = {}
    for row in persisted:
        try:
            projected = RetrievalRelationEdgeProjectionV2(
                version="retrieval-relation-edge.v2",
                relation_id=row.relation_id,
                source_table_id=row.source_table_id,
                source_record_id=row.source_record_id,
                link_field_id=row.link_field_id,
                target_table_id=row.target_table_id,
                target_record_id=row.target_record_id,
                direction=row.direction,
                source_version=row.source_version,
                target_version=row.target_version,
                visibility_profile_hash=row.visibility_profile_hash,
                scope_hash=row.scope_hash,
                edge_hash=row.edge_hash,
            )
        except (TypeError, ValueError):
            continue
        if current_by_hash.get(projected.edge_hash) == projected:
            selected[projected.edge_hash] = projected
    return tuple(
        selected[key]
        for key in sorted(
            selected,
            key=lambda edge_hash: (
                selected[edge_hash].relation_id,
                str(selected[edge_hash].source_record_id),
                str(selected[edge_hash].target_record_id),
            ),
        )
    )


def _authorized_relation_rows(
    index_uow,
    *,
    workspace_id: UUID,
    table_ids: tuple[UUID, ...],
    scope_hash: str,
) -> tuple[Stage12RelationEdge, ...]:
    table_set = set(table_ids)
    if isinstance(index_uow, SqlAlchemyRetrievalIndexUnitOfWork):
        statement = (
            select(Stage12RelationEdge)
            .where(
                Stage12RelationEdge.workspace_id == workspace_id,
                Stage12RelationEdge.source_table_id.in_(table_ids),
                Stage12RelationEdge.target_table_id.in_(table_ids),
                Stage12RelationEdge.scope_hash == scope_hash,
                Stage12RelationEdge.status == "active",
                Stage12RelationEdge.revoked_at.is_(None),
            )
            .order_by(Stage12RelationEdge.relation_id, Stage12RelationEdge.id)
            .limit(_MAX_AUTHORIZED_RELATION_EDGES + 1)
        )
        rows = tuple(index_uow.session.scalars(statement))
    elif isinstance(index_uow, MemoryRetrievalIndexUnitOfWork):
        rows = tuple(
            edge
            for edge in index_uow.relation_edges
            if edge.workspace_id == workspace_id
            and edge.source_table_id in table_set
            and edge.target_table_id in table_set
            and edge.scope_hash == scope_hash
            and edge.status == "active"
            and edge.revoked_at is None
        )
    else:
        raise RetrievalV2Denied("retrieval_runtime_uow_unsupported")
    if len(rows) > _MAX_AUTHORIZED_RELATION_EDGES:
        raise RetrievalV2Denied("retrieval_runtime_relation_budget_exceeded")
    return rows


def _normalized_source_id(value: str) -> str:
    return (
        value.replace("schema-table:", "schema_table:")
        .replace("schema-field:", "schema_field:")
        .replace("record-field:", "record_field:")
    )


def _keyword_terms(text: str) -> tuple[str, ...]:
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z0-9_-]+|[\u3400-\u9fff]+", text.casefold()):
        if re.fullmatch(r"[\u3400-\u9fff]+", token):
            terms.extend(token[index : index + 2] for index in range(len(token) - 1))
        else:
            terms.append(token[:64])
    return tuple(dict.fromkeys(item for item in terms if item))


def _validate_query_embedding(value: tuple[float, ...], dimension: int) -> None:
    if len(value) != dimension or any(
        isinstance(item, bool) or not math.isfinite(item) for item in value
    ):
        raise RetrievalV2Denied("retrieval_query_embedding_invalid")
    magnitude = math.sqrt(sum(item * item for item in value))
    if not 0.999 <= magnitude <= 1.001:
        raise RetrievalV2Denied("retrieval_query_embedding_invalid")


def _semantic_similarity(query_embedding, embedding) -> float:
    if len(query_embedding) != len(embedding):
        return 0.0
    score = sum(
        float(left) * float(right)
        for left, right in zip(query_embedding, embedding, strict=True)
    )
    return max(0.0, min(1.0, score))


def _entity_schema_score(context, table_id, query) -> float:
    normalized = query.casefold()
    table = next(item for item in context.snapshot.tables if item.table_id == table_id)
    mentions = (table.key, table.name, *table.aliases)
    if any(item.casefold() in normalized for item in mentions):
        return 1.0
    if any(
        value.casefold() in normalized
        for field in table.fields
        for value in (field.key, field.name, *field.aliases)
    ):
        return 0.75
    return 0.0


def _has_primary_discovery_signal(hit: RawRetrievalHitV2) -> bool:
    return (
        hit.keyword_score > 0.0
        or hit.semantic_score > 0.0
        or hit.entity_schema_score > 0.0
    )


__all__ = [
    "build_stage12_query_embedding_provider",
    "load_authorized_retrieval_v2",
]
