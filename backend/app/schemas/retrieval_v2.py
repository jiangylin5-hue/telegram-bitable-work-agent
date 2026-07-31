"""Strict Stage12-D retrieval, embedding and evidence contracts."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_task_spec_v2 import JsonValue


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
UnitScore = Annotated[StrictFloat, Field(ge=0.0, le=1.0)]
RetrievalSourceType = Literal[
    "schema_table",
    "schema_field",
    "record",
    "record_field",
]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class EmbeddingProfileV1(_StrictFrozenModel):
    version: Literal["embedding-profile.v1"]
    profile_name: NonEmptyStr
    model_revision: NonEmptyStr
    dimension: StrictInt = Field(ge=1, le=16_000)
    normalization: Literal["l2"]
    distance_metric: Literal["cosine"]
    max_input_tokens: StrictInt = Field(ge=1, le=1_000_000)
    batch_size: StrictInt = Field(ge=1, le=1_000)
    provider_location: Literal["local", "remote"]
    data_residency: NonEmptyStr


class RetrievalProjectionV2(_StrictFrozenModel):
    version: Literal["retrieval-projection.v2"]
    source_type: RetrievalSourceType
    source_id: NonEmptyStr
    source_version: StrictInt = Field(ge=1)
    workspace_id: UUID
    base_id: UUID
    table_id: UUID
    record_id: UUID | None
    field_ids: tuple[UUID, ...]
    visibility_profile_hash: Sha256Hex
    scope_hash: Sha256Hex
    content_hash: Sha256Hex
    canonical_text: NonEmptyStr

    @model_validator(mode="after")
    def validate_projection(self) -> "RetrievalProjectionV2":
        record_source = self.source_type in {"record", "record_field"}
        if record_source != (self.record_id is not None):
            raise ValueError("retrieval_projection_record_identity_invalid")
        if len(set(self.field_ids)) != len(self.field_ids):
            raise ValueError("retrieval_projection_field_duplicate")
        if self.field_ids != tuple(sorted(self.field_ids, key=str)):
            raise ValueError("retrieval_projection_field_order_invalid")
        expected = sha256(self.canonical_text.encode("utf-8")).hexdigest()
        if self.content_hash != expected:
            raise ValueError("retrieval_projection_content_hash_mismatch")
        return self


class RetrievalChunkV2(_StrictFrozenModel):
    version: Literal["retrieval-chunk.v2"]
    source_type: RetrievalSourceType
    source_id: NonEmptyStr
    source_version: StrictInt = Field(ge=1)
    ordinal: StrictInt = Field(ge=0)
    chunk_kind: Literal["canonical", "long_field"]
    table_id: UUID
    record_id: UUID | None
    field_ids: tuple[UUID, ...]
    start_token: StrictInt = Field(ge=0)
    end_token: StrictInt = Field(ge=1)
    visibility_profile_hash: Sha256Hex
    scope_hash: Sha256Hex
    content_hash: Sha256Hex
    chunk_text: NonEmptyStr
    keyword_terms: tuple[NonEmptyStr, ...] = Field(max_length=256)

    @model_validator(mode="after")
    def validate_chunk(self) -> "RetrievalChunkV2":
        if self.end_token <= self.start_token:
            raise ValueError("retrieval_chunk_token_range_invalid")
        if len(set(self.field_ids)) != len(self.field_ids):
            raise ValueError("retrieval_chunk_field_duplicate")
        if len(set(self.keyword_terms)) != len(self.keyword_terms):
            raise ValueError("retrieval_chunk_keyword_duplicate")
        expected = sha256(self.chunk_text.encode("utf-8")).hexdigest()
        if self.content_hash != expected:
            raise ValueError("retrieval_chunk_content_hash_mismatch")
        return self


class RetrievalRelationEdgeProjectionV2(_StrictFrozenModel):
    version: Literal["retrieval-relation-edge.v2"]
    relation_id: NonEmptyStr
    source_table_id: UUID
    source_record_id: UUID
    link_field_id: UUID
    target_table_id: UUID
    target_record_id: UUID
    direction: Literal["forward", "reverse"]
    source_version: StrictInt = Field(ge=1)
    target_version: StrictInt = Field(ge=1)
    visibility_profile_hash: Sha256Hex
    scope_hash: Sha256Hex
    edge_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_edge(self) -> "RetrievalRelationEdgeProjectionV2":
        if self.source_record_id == self.target_record_id:
            raise ValueError("retrieval_relation_edge_self_reference_invalid")
        expected = canonical_retrieval_sha256(
            self.model_dump(mode="json", exclude={"edge_hash"})
        )
        if self.edge_hash != expected:
            raise ValueError("retrieval_relation_edge_hash_mismatch")
        return self


class RetrievalRequestV2(_StrictFrozenModel):
    version: Literal["retrieval-request.v2"]
    objective_id: NonEmptyStr
    query: NonEmptyStr
    workspace_id: UUID
    base_id: UUID
    table_ids: tuple[UUID, ...] = Field(min_length=1)
    exact_record_ids: tuple[UUID, ...]
    query_result_ref: NonEmptyStr | None
    scope_hash: Sha256Hex
    schema_hash: Sha256Hex
    max_primary_candidates: StrictInt = Field(default=20, ge=1, le=20)
    max_relation_expansions_per_primary: StrictInt = Field(
        default=10,
        ge=1,
        le=10,
    )
    max_evidence_nodes: StrictInt = Field(default=24, ge=1, le=24)

    @model_validator(mode="after")
    def validate_request_identity(self) -> "RetrievalRequestV2":
        if len(set(self.table_ids)) != len(self.table_ids):
            raise ValueError("retrieval_request_table_duplicate")
        if len(set(self.exact_record_ids)) != len(self.exact_record_ids):
            raise ValueError("retrieval_request_record_duplicate")
        return self


class RetrievalComponentScoresV2(_StrictFrozenModel):
    keyword: UnitScore
    semantic: UnitScore
    entity_schema: UnitScore
    freshness: UnitScore
    total: UnitScore

    @model_validator(mode="after")
    def validate_finite(self) -> "RetrievalComponentScoresV2":
        if any(
            not math.isfinite(value)
            for value in (
                self.keyword,
                self.semantic,
                self.entity_schema,
                self.freshness,
                self.total,
            )
        ):
            raise ValueError("retrieval_candidate_score_invalid")
        return self


class RetrievalCandidateV2(_StrictFrozenModel):
    version: Literal["retrieval-candidate.v2"]
    candidate_id: NonEmptyStr
    source_type: RetrievalSourceType
    source_id: NonEmptyStr
    source_version: StrictInt = Field(ge=1)
    table_id: UUID
    record_id: UUID | None
    field_ids: tuple[UUID, ...]
    priority_band: Literal["exact", "fuzzy", "linked"]
    retrieval_reason: Literal[
        "exact_identifier",
        "keyword",
        "semantic",
        "schema_match",
        "hybrid",
        "linked_expansion",
    ]
    scores: RetrievalComponentScoresV2
    scope_hash: Sha256Hex
    content_hash: Sha256Hex
    embedding_profile: NonEmptyStr | None

    @model_validator(mode="after")
    def validate_band(self) -> "RetrievalCandidateV2":
        valid = (
            (
                self.priority_band == "exact"
                and self.retrieval_reason == "exact_identifier"
                and self.embedding_profile is None
            )
            or (
                self.priority_band == "linked"
                and self.retrieval_reason == "linked_expansion"
                and self.embedding_profile is None
            )
            or (
                self.priority_band == "fuzzy"
                and self.retrieval_reason
                in {"keyword", "semantic", "schema_match", "hybrid"}
            )
        )
        if not valid:
            raise ValueError("retrieval_candidate_band_invalid")
        if len(set(self.field_ids)) != len(self.field_ids):
            raise ValueError("retrieval_candidate_field_duplicate")
        return self


class EvidenceFieldValueV2(_StrictFrozenModel):
    field_id: UUID
    field_key: NonEmptyStr
    value: JsonValue


class EvidenceNodeV2(_StrictFrozenModel):
    evidence_id: NonEmptyStr
    kind: Literal["schema", "record"]
    source_id: NonEmptyStr
    source_version: StrictInt = Field(ge=1)
    table_id: UUID
    record_id: UUID | None
    fields: tuple[EvidenceFieldValueV2, ...]
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_node(self) -> "EvidenceNodeV2":
        if (self.kind == "record") != (self.record_id is not None):
            raise ValueError("retrieval_evidence_record_identity_invalid")
        field_ids = tuple(item.field_id for item in self.fields)
        field_keys = tuple(item.field_key for item in self.fields)
        if len(set(field_ids)) != len(field_ids) or len(set(field_keys)) != len(
            field_keys
        ):
            raise ValueError("retrieval_evidence_field_duplicate")
        return self


class RetrievalRelationV2(_StrictFrozenModel):
    relation_id: NonEmptyStr
    from_evidence_id: NonEmptyStr
    to_evidence_id: NonEmptyStr
    link_field_id: UUID
    direction: Literal["forward", "reverse"]
    source_version: StrictInt = Field(ge=1)
    target_version: StrictInt = Field(ge=1)
    scope_hash: Sha256Hex


class EvidenceAggregateV2(_StrictFrozenModel):
    aggregate_id: NonEmptyStr
    output_key: NonEmptyStr
    group_key: JsonValue = None
    value: JsonValue
    query_result_ref: NonEmptyStr


class EvidenceBundleV2(_StrictFrozenModel):
    version: Literal["evidence-bundle.v2"]
    objective_id: NonEmptyStr
    query_result_ref: NonEmptyStr | None
    nodes: tuple[EvidenceNodeV2, ...] = Field(max_length=24)
    relations: tuple[RetrievalRelationV2, ...] = Field(max_length=240)
    aggregates: tuple[EvidenceAggregateV2, ...]
    scope_hash: Sha256Hex
    complete: StrictBool
    truncated: StrictBool
    bundle_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_bundle(self) -> "EvidenceBundleV2":
        if self.complete and self.truncated:
            raise ValueError("retrieval_completeness_invalid")
        evidence_ids = tuple(node.evidence_id for node in self.nodes)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("retrieval_evidence_id_duplicate")
        known = set(evidence_ids)
        if any(
            relation.from_evidence_id not in known
            or relation.to_evidence_id not in known
            for relation in self.relations
        ):
            raise ValueError("retrieval_relation_evidence_unknown")
        expected = canonical_retrieval_sha256(
            self.model_dump(mode="json", exclude={"bundle_hash"})
        )
        if self.bundle_hash != expected:
            raise ValueError("retrieval_bundle_hash_mismatch")
        return self


class RetrievalBenchmarkCandidateV2(_StrictFrozenModel):
    candidate_id: NonEmptyStr
    source_type: Literal["schema_table", "schema_field", "record"]
    table_key: NonEmptyStr
    record_code: NonEmptyStr | None
    canonical_text: NonEmptyStr
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_candidate(self) -> "RetrievalBenchmarkCandidateV2":
        if (self.source_type == "record") != (self.record_code is not None):
            raise ValueError("retrieval_benchmark_record_identity_invalid")
        expected = sha256(self.canonical_text.encode("utf-8")).hexdigest()
        if self.content_hash != expected:
            raise ValueError("retrieval_benchmark_content_hash_mismatch")
        return self


class RetrievalBenchmarkCaseV2(_StrictFrozenModel):
    case_id: NonEmptyStr
    category: Literal["schema", "entity_alias", "non_structured"]
    query: NonEmptyStr
    relevant_candidate_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    negative_candidate_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    forbidden_candidate_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_truth(self) -> "RetrievalBenchmarkCaseV2":
        relevant = set(self.relevant_candidate_ids)
        negative = set(self.negative_candidate_ids)
        forbidden = set(self.forbidden_candidate_ids)
        if (
            len(relevant) != len(self.relevant_candidate_ids)
            or len(negative) != len(self.negative_candidate_ids)
            or len(forbidden) != len(self.forbidden_candidate_ids)
            or relevant & negative
            or relevant & forbidden
            or negative & forbidden
        ):
            raise ValueError("retrieval_benchmark_truth_invalid")
        return self


class RetrievalBenchmarkCorpusV2(_StrictFrozenModel):
    version: Literal["stage12-retrieval-benchmark.v2"]
    source_fixture_hash: Sha256Hex
    candidates: tuple[RetrievalBenchmarkCandidateV2, ...] = Field(min_length=1)
    cases: tuple[RetrievalBenchmarkCaseV2, ...] = Field(min_length=12)
    corpus_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_corpus(self) -> "RetrievalBenchmarkCorpusV2":
        candidate_ids = tuple(item.candidate_id for item in self.candidates)
        case_ids = tuple(item.case_id for item in self.cases)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("retrieval_benchmark_candidate_duplicate")
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("retrieval_benchmark_case_duplicate")
        known = set(candidate_ids)
        if any(
            not set(case.relevant_candidate_ids) <= known
            or not set(case.negative_candidate_ids) <= known
            or bool(set(case.forbidden_candidate_ids) & known)
            for case in self.cases
        ):
            raise ValueError("retrieval_benchmark_candidate_unknown")
        expected = canonical_retrieval_sha256(
            self.model_dump(mode="json", exclude={"corpus_hash"})
        )
        if self.corpus_hash != expected:
            raise ValueError("retrieval_benchmark_corpus_hash_mismatch")
        return self


class RetrievalBenchmarkProfileSummaryV1(_StrictFrozenModel):
    profile_name: NonEmptyStr
    model_revision: NonEmptyStr
    dimension: StrictInt = Field(ge=1, le=16_000)
    normalization: Literal["l2"]
    distance_metric: Literal["cosine"]
    max_input_tokens: StrictInt = Field(ge=1, le=1_000_000)
    batch_size: StrictInt = Field(ge=1, le=1_000)
    provider_location: Literal["local", "remote"]
    data_residency: NonEmptyStr


class RetrievalBenchmarkMetricV1(_StrictFrozenModel):
    category: Literal["overall", "schema", "entity_alias", "non_structured"]
    case_count: StrictInt = Field(ge=0)
    recall_at_20: UnitScore
    mrr_at_20: UnitScore
    forbidden_candidate_count: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def validate_metric(self) -> "RetrievalBenchmarkMetricV1":
        if not math.isfinite(self.recall_at_20) or not math.isfinite(self.mrr_at_20):
            raise ValueError("retrieval_benchmark_metric_invalid")
        return self


class RetrievalProfileBenchmarkReportV1(_StrictFrozenModel):
    version: Literal["retrieval-profile-benchmark.v1"]
    profile: RetrievalBenchmarkProfileSummaryV1
    corpus_hash: Sha256Hex
    requested_rounds: StrictInt = Field(ge=1, le=3)
    completed_rounds: StrictInt = Field(ge=0, le=3)
    failed_rounds: StrictInt = Field(ge=0, le=3)
    categories: tuple[RetrievalBenchmarkMetricV1, ...] = Field(min_length=3)
    overall: RetrievalBenchmarkMetricV1
    mean_latency_ms: StrictFloat = Field(ge=0.0)
    p95_latency_ms: StrictFloat = Field(ge=0.0)
    consumed_input_tokens: StrictInt = Field(ge=0)
    estimated_cost_usd: StrictFloat = Field(ge=0.0)
    report_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_report(self) -> "RetrievalProfileBenchmarkReportV1":
        if self.completed_rounds + self.failed_rounds != self.requested_rounds:
            raise ValueError("retrieval_benchmark_round_count_invalid")
        expected_categories = {"schema", "entity_alias", "non_structured"}
        categories = tuple(metric.category for metric in self.categories)
        if (
            len(categories) != len(set(categories))
            or set(categories) != expected_categories
        ):
            raise ValueError("retrieval_benchmark_category_invalid")
        if self.overall.category != "overall":
            raise ValueError("retrieval_benchmark_overall_invalid")
        if not all(
            math.isfinite(value)
            for value in (
                self.mean_latency_ms,
                self.p95_latency_ms,
                self.estimated_cost_usd,
            )
        ):
            raise ValueError("retrieval_benchmark_measurement_invalid")
        expected_hash = canonical_retrieval_sha256(
            self.model_dump(mode="json", exclude={"report_hash"})
        )
        if self.report_hash != expected_hash:
            raise ValueError("retrieval_benchmark_report_hash_mismatch")
        return self


def canonical_retrieval_sha256(value: BaseModel | dict[str, object]) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    canonical = json.dumps(
        _jsonable_retrieval_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _jsonable_retrieval_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, UUID):
        return str(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("retrieval_hash_value_invalid")
        return value
    if isinstance(value, (tuple, list)):
        return [_jsonable_retrieval_value(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("retrieval_hash_key_invalid")
        return {key: _jsonable_retrieval_value(item) for key, item in value.items()}
    raise ValueError("retrieval_hash_value_invalid")
