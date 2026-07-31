"""Authorization-first, bounded Stage12-D hybrid retrieval."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from typing import Literal
from uuid import UUID

from app.schemas.retrieval_v2 import (
    RetrievalCandidateV2,
    RetrievalComponentScoresV2,
    RetrievalRelationEdgeProjectionV2,
    RetrievalRequestV2,
    RetrievalSourceType,
    canonical_retrieval_sha256,
)
from app.services.authorized_query_records import AuthorizedQueryContext
from app.services.retrieval_v2_scope import (
    EffectiveRetrievalScopeError,
    build_effective_retrieval_scope_hash,
    effective_retrieval_scope_hash,
)


_SCHEMA_SOURCE_TYPES = frozenset({"schema_table", "schema_field"})
_RECORD_SOURCE_TYPES = frozenset({"record", "record_field"})


class RetrievalV2Denied(ValueError):
    """Stable fail-closed retrieval refusal."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RawRetrievalHitV2:
    """A server-side index hit; canonical text never crosses this boundary."""

    workspace_id: UUID
    base_id: UUID
    source_type: RetrievalSourceType
    source_id: str
    source_version: int
    table_id: UUID
    record_id: UUID | None
    field_ids: tuple[UUID, ...]
    scope_hash: str
    content_hash: str
    embedding_profile: str | None
    keyword_score: float
    semantic_score: float
    entity_schema_score: float
    freshness_score: float

    def __post_init__(self) -> None:
        if (
            not self.source_id
            or self.source_id != self.source_id.strip()
            or "\n" in self.source_id
            or "\r" in self.source_id
            or self.source_version < 1
            or len(set(self.field_ids)) != len(self.field_ids)
            or self.scope_hash != self.scope_hash.lower()
            or self.content_hash != self.content_hash.lower()
            or len(self.scope_hash) != 64
            or len(self.content_hash) != 64
            or any(character not in "0123456789abcdef" for character in self.scope_hash)
            or any(
                character not in "0123456789abcdef" for character in self.content_hash
            )
            or (self.source_type in _RECORD_SOURCE_TYPES)
            != (self.record_id is not None)
        ):
            raise RetrievalV2Denied("retrieval_hit_contract_invalid")
        scores = (
            self.keyword_score,
            self.semantic_score,
            self.entity_schema_score,
            self.freshness_score,
        )
        if (
            any(not math.isfinite(value) or value < 0.0 for value in scores)
            or self.entity_schema_score > 1.0
            or self.freshness_score > 1.0
        ):
            raise RetrievalV2Denied("retrieval_hit_score_invalid")


@dataclass(frozen=True, slots=True)
class ObjectiveTableQuotaV2:
    table_id: UUID
    schema_candidates: int
    record_candidates: int

    def __post_init__(self) -> None:
        if (
            not 0 <= self.schema_candidates <= 20
            or not 0 <= self.record_candidates <= 20
        ):
            raise RetrievalV2Denied("retrieval_table_quota_invalid")


@dataclass(frozen=True, slots=True)
class AuthorizedRetrievalResultV2:
    candidates: tuple[RetrievalCandidateV2, ...]
    primary_candidates: tuple[RetrievalCandidateV2, ...]
    relation_edges: tuple[RetrievalRelationEdgeProjectionV2, ...]
    truncated: bool

    def __post_init__(self) -> None:
        candidate_ids = tuple(item.candidate_id for item in self.candidates)
        primary_ids = tuple(item.candidate_id for item in self.primary_candidates)
        if (
            len(set(candidate_ids)) != len(candidate_ids)
            or len(set(primary_ids)) != len(primary_ids)
            or not set(primary_ids).issubset(candidate_ids)
            or any(item.priority_band == "linked" for item in self.primary_candidates)
        ):
            raise RetrievalV2Denied("retrieval_result_contract_invalid")


RerankerV2 = Callable[[tuple[str, ...]], tuple[str, ...]]


def retrieve_authorized_candidates(
    *,
    request: RetrievalRequestV2,
    context: AuthorizedQueryContext,
    exact_entity_hits: tuple[RawRetrievalHitV2, ...],
    fuzzy_hits: tuple[RawRetrievalHitV2, ...],
    relation_edges: tuple[RetrievalRelationEdgeProjectionV2, ...],
    relation_target_hits: tuple[RawRetrievalHitV2, ...],
    active_embedding_profile: str,
    table_quotas: tuple[ObjectiveTableQuotaV2, ...],
    reranker: RerankerV2 | None = None,
) -> AuthorizedRetrievalResultV2:
    """Filter before score, then rank only the current authorized candidate set."""

    authorized_fields = _validate_request_context(request, context)
    quotas = _validate_quotas(request, table_quotas)
    exact_authorized = _filter_hits(
        exact_entity_hits,
        request=request,
        authorized_fields=authorized_fields,
        active_embedding_profile=active_embedding_profile,
        band="exact",
    )
    fuzzy_authorized = _filter_hits(
        fuzzy_hits,
        request=request,
        authorized_fields=authorized_fields,
        active_embedding_profile=active_embedding_profile,
        band="fuzzy",
    )
    relation_targets = _filter_hits(
        relation_target_hits,
        request=request,
        authorized_fields=authorized_fields,
        active_embedding_profile=active_embedding_profile,
        band="linked",
    )

    exact_candidates = tuple(
        _candidate_from_hit(
            request,
            hit,
            band="exact",
            scores=RetrievalComponentScoresV2(
                keyword=0.0,
                semantic=0.0,
                entity_schema=1.0,
                freshness=hit.freshness_score,
                total=1.0,
            ),
            reason="exact_identifier",
        )
        for hit in exact_authorized
        if hit.record_id in set(request.exact_record_ids)
    )
    exact_candidates = tuple(
        sorted(exact_candidates, key=lambda item: (item.source_id, item.source_version))
    )

    fuzzy_scored = _score_fuzzy_hits(request, fuzzy_authorized)
    fuzzy_quota_selected = _apply_table_quotas(fuzzy_scored, quotas)
    quota_cut = len(fuzzy_quota_selected) < len(fuzzy_scored)

    remaining = max(0, request.max_primary_candidates - len(exact_candidates))
    selected_exact = exact_candidates[: request.max_primary_candidates]
    exact_cut = len(selected_exact) < len(exact_candidates)
    selected_fuzzy = fuzzy_quota_selected[:remaining]
    primary_cut = len(selected_fuzzy) < len(fuzzy_quota_selected)
    if reranker is not None and selected_fuzzy:
        selected_fuzzy = _rerank_existing(selected_fuzzy, reranker)
    primary = (*selected_exact, *selected_fuzzy)

    linked_candidates, selected_edges, relation_cut = _expand_relations(
        request=request,
        primary=primary,
        relation_targets=relation_targets,
        relation_edges=relation_edges,
    )
    return AuthorizedRetrievalResultV2(
        candidates=(*primary, *linked_candidates),
        primary_candidates=primary,
        relation_edges=selected_edges,
        truncated=exact_cut or quota_cut or primary_cut or relation_cut,
    )


def _validate_request_context(
    request: RetrievalRequestV2,
    context: AuthorizedQueryContext,
) -> dict[UUID, frozenset[UUID]]:
    try:
        current_retrieval_scope_hash = effective_retrieval_scope_hash(context)
    except EffectiveRetrievalScopeError as exc:
        raise RetrievalV2Denied("retrieval_request_scope_denied") from exc
    if (
        request.workspace_id != context.workspace_id
        or request.base_id != context.base_id
        or request.scope_hash != current_retrieval_scope_hash
        or request.schema_hash != context.snapshot.schema_hash
        or not set(request.table_ids).issubset(context.employee_table_ids)
    ):
        raise RetrievalV2Denied("retrieval_request_scope_denied")
    table_map = {table.table_id: table for table in context.snapshot.tables}
    if any(table_id not in table_map for table_id in request.table_ids):
        raise RetrievalV2Denied("retrieval_request_scope_denied")
    return {
        table_id: frozenset(field.field_id for field in table_map[table_id].fields)
        for table_id in request.table_ids
    }


def _validate_quotas(
    request: RetrievalRequestV2,
    table_quotas: tuple[ObjectiveTableQuotaV2, ...],
) -> dict[UUID, ObjectiveTableQuotaV2]:
    quota_by_table = {item.table_id: item for item in table_quotas}
    if len(quota_by_table) != len(table_quotas) or set(quota_by_table) != set(
        request.table_ids
    ):
        raise RetrievalV2Denied("retrieval_table_quota_invalid")
    return quota_by_table


def _filter_hits(
    hits: tuple[RawRetrievalHitV2, ...],
    *,
    request: RetrievalRequestV2,
    authorized_fields: dict[UUID, frozenset[UUID]],
    active_embedding_profile: str,
    band: Literal["exact", "fuzzy", "linked"],
) -> tuple[RawRetrievalHitV2, ...]:
    selected: list[RawRetrievalHitV2] = []
    seen: set[tuple[str, int]] = set()
    for hit in hits:
        required_profile = band in {"fuzzy", "linked"}
        if (
            hit.workspace_id != request.workspace_id
            or hit.base_id != request.base_id
            or hit.scope_hash != request.scope_hash
            or hit.table_id not in authorized_fields
            or not set(hit.field_ids).issubset(authorized_fields[hit.table_id])
            or (required_profile and hit.embedding_profile != active_embedding_profile)
            or (band == "exact" and hit.source_type not in _RECORD_SOURCE_TYPES)
        ):
            continue
        identity = (hit.source_id, hit.source_version)
        if identity in seen:
            raise RetrievalV2Denied("retrieval_hit_duplicate")
        seen.add(identity)
        selected.append(hit)
    return tuple(selected)


def _score_fuzzy_hits(
    request: RetrievalRequestV2,
    hits: tuple[RawRetrievalHitV2, ...],
) -> tuple[RetrievalCandidateV2, ...]:
    keyword_max = max((hit.keyword_score for hit in hits), default=0.0)
    semantic_max = max((hit.semantic_score for hit in hits), default=0.0)
    scored: list[RetrievalCandidateV2] = []
    for hit in hits:
        keyword = _normalized(hit.keyword_score, keyword_max)
        semantic = _normalized(hit.semantic_score, semantic_max)
        total = (
            0.35 * keyword
            + 0.35 * semantic
            + 0.20 * hit.entity_schema_score
            + 0.10 * hit.freshness_score
        )
        scores = RetrievalComponentScoresV2(
            keyword=float(keyword),
            semantic=float(semantic),
            entity_schema=float(hit.entity_schema_score),
            freshness=float(hit.freshness_score),
            total=float(total),
        )
        scored.append(
            _candidate_from_hit(
                request,
                hit,
                band="fuzzy",
                scores=scores,
                reason=_reason(scores),
            )
        )
    return tuple(
        sorted(
            scored,
            key=lambda item: (-item.scores.total, item.source_id, item.source_version),
        )
    )


def _normalized(value: float, maximum: float) -> float:
    return 0.0 if maximum <= 0.0 else min(1.0, value / maximum)


def _reason(scores: RetrievalComponentScoresV2) -> str:
    substantive = sum(
        value > 0.0 for value in (scores.keyword, scores.semantic, scores.entity_schema)
    )
    if substantive > 1:
        return "hybrid"
    if scores.keyword > 0.0:
        return "keyword"
    if scores.semantic > 0.0:
        return "semantic"
    if scores.entity_schema > 0.0:
        return "schema_match"
    return "hybrid"


def _apply_table_quotas(
    candidates: tuple[RetrievalCandidateV2, ...],
    quotas: dict[UUID, ObjectiveTableQuotaV2],
) -> tuple[RetrievalCandidateV2, ...]:
    counts: dict[tuple[UUID, str], int] = {}
    selected: list[RetrievalCandidateV2] = []
    for candidate in candidates:
        kind = "schema" if candidate.source_type in _SCHEMA_SOURCE_TYPES else "record"
        quota = quotas[candidate.table_id]
        limit = quota.schema_candidates if kind == "schema" else quota.record_candidates
        key = (candidate.table_id, kind)
        if counts.get(key, 0) >= limit:
            continue
        counts[key] = counts.get(key, 0) + 1
        selected.append(candidate)
    return tuple(selected)


def _rerank_existing(
    candidates: tuple[RetrievalCandidateV2, ...],
    reranker: RerankerV2,
) -> tuple[RetrievalCandidateV2, ...]:
    candidate_by_id = {item.candidate_id: item for item in candidates}
    proposed = reranker(tuple(candidate_by_id))
    if (
        type(proposed) is not tuple
        or len(set(proposed)) != len(proposed)
        or set(proposed) != set(candidate_by_id)
    ):
        raise RetrievalV2Denied("retrieval_reranker_candidate_invalid")
    return tuple(candidate_by_id[candidate_id] for candidate_id in proposed)


def _expand_relations(
    *,
    request: RetrievalRequestV2,
    primary: tuple[RetrievalCandidateV2, ...],
    relation_targets: tuple[RawRetrievalHitV2, ...],
    relation_edges: tuple[RetrievalRelationEdgeProjectionV2, ...],
) -> tuple[
    tuple[RetrievalCandidateV2, ...],
    tuple[RetrievalRelationEdgeProjectionV2, ...],
    bool,
]:
    target_by_record = {
        hit.record_id: hit
        for hit in relation_targets
        if hit.record_id is not None and hit.source_type in _RECORD_SOURCE_TYPES
    }
    existing_sources = {item.source_id for item in primary}
    linked: list[RetrievalCandidateV2] = []
    selected_edges: list[RetrievalRelationEdgeProjectionV2] = []
    truncated = False
    for candidate in primary:
        if candidate.record_id is None:
            continue
        eligible: list[tuple[RetrievalRelationEdgeProjectionV2, RawRetrievalHitV2]] = []
        for edge in relation_edges:
            if edge.scope_hash != request.scope_hash:
                continue
            if (
                edge.source_record_id == candidate.record_id
                and edge.source_version == candidate.source_version
            ):
                other_id = edge.target_record_id
                other_version = edge.target_version
            elif (
                edge.target_record_id == candidate.record_id
                and edge.target_version == candidate.source_version
            ):
                other_id = edge.source_record_id
                other_version = edge.source_version
            else:
                continue
            target = target_by_record.get(other_id)
            if target is None or target.source_version != other_version:
                continue
            eligible.append((edge, target))
        eligible.sort(key=lambda item: (item[0].relation_id, item[1].source_id))
        if len(eligible) > request.max_relation_expansions_per_primary:
            truncated = True
        for edge, target in eligible[: request.max_relation_expansions_per_primary]:
            if target.source_id in existing_sources:
                continue
            linked_candidate = _candidate_from_hit(
                request,
                target,
                band="linked",
                scores=RetrievalComponentScoresV2(
                    keyword=0.0,
                    semantic=0.0,
                    entity_schema=0.0,
                    freshness=0.0,
                    total=0.0,
                ),
                reason="linked_expansion",
            )
            existing_sources.add(target.source_id)
            linked.append(linked_candidate)
            selected_edges.append(edge)
    return tuple(linked), tuple(selected_edges), truncated


def _candidate_from_hit(
    request: RetrievalRequestV2,
    hit: RawRetrievalHitV2,
    *,
    band: Literal["exact", "fuzzy", "linked"],
    scores: RetrievalComponentScoresV2,
    reason: Literal[
        "exact_identifier",
        "keyword",
        "semantic",
        "schema_match",
        "hybrid",
        "linked_expansion",
    ],
) -> RetrievalCandidateV2:
    identity = {
        "objective_id": request.objective_id,
        "source_id": hit.source_id,
        "source_version": hit.source_version,
        "priority_band": band,
        "scope_hash": hit.scope_hash,
        "content_hash": hit.content_hash,
    }
    candidate_id = f"cand-{canonical_retrieval_sha256(identity)[:32]}"
    return RetrievalCandidateV2(
        version="retrieval-candidate.v2",
        candidate_id=candidate_id,
        source_type=hit.source_type,
        source_id=hit.source_id,
        source_version=hit.source_version,
        table_id=hit.table_id,
        record_id=hit.record_id,
        field_ids=hit.field_ids,
        priority_band=band,
        retrieval_reason=reason,
        scores=scores,
        scope_hash=hit.scope_hash,
        content_hash=hit.content_hash,
        embedding_profile=hit.embedding_profile if band == "fuzzy" else None,
    )


__all__ = [
    "AuthorizedRetrievalResultV2",
    "ObjectiveTableQuotaV2",
    "RawRetrievalHitV2",
    "RetrievalV2Denied",
    "build_effective_retrieval_scope_hash",
    "effective_retrieval_scope_hash",
    "retrieve_authorized_candidates",
]
