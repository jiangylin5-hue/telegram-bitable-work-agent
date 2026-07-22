from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


KnowledgeSourceType: TypeAlias = Literal[
    "memory_item",
    "document_projection",
    "approved_summary",
]
KnowledgeSourceStatus: TypeAlias = Literal[
    "pending",
    "active",
    "replaced",
    "revoked",
    "expired",
    "deleted",
]
KnowledgeChunkStatus: TypeAlias = Literal[
    "pending",
    "indexed",
    "stale",
    "deleted",
    "failed",
]
RetrievalStatus: TypeAlias = Literal[
    "ready",
    "degraded",
    "unavailable",
    "empty",
    "failed",
]
RetrievalSourceTypeCategory: TypeAlias = Literal[
    "business_memory",
    "document",
    "approved_summary",
    "mixed",
    "none",
]
RetrievalScopeCategory: TypeAlias = Literal[
    "workspace",
    "business",
    "base",
    "table",
    "view",
    "field",
    "mixed",
    "none",
]
RetrievalCitationSourceTypeCategory: TypeAlias = Literal[
    "business_memory",
    "document",
    "approved_summary",
]
RetrievalCitationScopeCategory: TypeAlias = Literal[
    "workspace",
    "business",
    "base",
    "table",
    "view",
    "field",
]
RetrievalDegradationCode: TypeAlias = Literal[
    "none",
    "keyword_only",
    "embedding_unavailable",
]
RetrievalErrorCode: TypeAlias = Literal[
    "none",
    "retrieval_unavailable",
    "source_revalidation_failed",
    "authority_changed",
    "scope_mismatch",
    "index_unavailable",
]

Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
KeywordTerm = Annotated[StrictStr, Field(min_length=1, max_length=64)]

_STRICT_FROZEN_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    hide_input_in_errors=True,
)


class KnowledgeSourceProjection(BaseModel):
    """Private server-derived projection contract; never an API response."""

    model_config = _STRICT_FROZEN_CONFIG

    source_type: KnowledgeSourceType
    status: KnowledgeSourceStatus
    source_ref: dict[StrictStr, JsonValue]
    scope: dict[StrictStr, JsonValue]
    logical_source_fingerprint: Sha256Hex
    projection_hash: Sha256Hex
    projection_text: StrictStr | None
    content_version: StrictInt = Field(gt=0)

    @model_validator(mode="after")
    def validate_active_projection(self) -> "KnowledgeSourceProjection":
        if self.status == "active" and (
            self.projection_text is None or not self.projection_text.strip()
        ):
            raise ValueError("knowledge_source_active_projection_required")
        return self


class KnowledgeChunkProjection(BaseModel):
    """Private chunk/index state contract; never an API response."""

    model_config = _STRICT_FROZEN_CONFIG

    source_version: StrictInt = Field(gt=0)
    ordinal: StrictInt = Field(ge=0)
    chunk_text: StrictStr | None
    chunk_hash: Sha256Hex
    keyword_terms: tuple[KeywordTerm, ...] = Field(max_length=256)
    embedding_profile: Annotated[StrictStr, Field(min_length=1, max_length=80)] | None
    embedding_version: StrictInt | None = Field(default=None, gt=0)
    status: KnowledgeChunkStatus

    @model_validator(mode="after")
    def validate_indexed_chunk(self) -> "KnowledgeChunkProjection":
        if self.status == "indexed" and (
            self.chunk_text is None or not self.chunk_text.strip()
        ):
            raise ValueError("knowledge_chunk_indexed_text_required")
        if (self.embedding_profile is None) != (self.embedding_version is None):
            raise ValueError("knowledge_chunk_embedding_profile_version_mismatch")
        return self


class RetrievalSafeSourceView(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG

    source_type_category: RetrievalSourceTypeCategory
    scope_category: RetrievalScopeCategory
    count: StrictInt = Field(ge=0, le=12)
    available: StrictBool


class RetrievalSafeCitation(BaseModel):
    """Public citation marker with no source identity or content carrier."""

    model_config = _STRICT_FROZEN_CONFIG

    display_ordinal: StrictInt = Field(ge=1, le=12)
    label: Literal["retrieved_material"]
    source_type_category: RetrievalCitationSourceTypeCategory
    scope_category: RetrievalCitationScopeCategory


class RetrievalSafeView(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG

    contract_version: Literal["stage08.retrieval-safe.v1"]
    status: RetrievalStatus
    sources: tuple[RetrievalSafeSourceView, ...] = Field(max_length=12)
    result_count: StrictInt = Field(ge=0, le=12)
    has_results: StrictBool
    degradation_code: RetrievalDegradationCode
    error_code: RetrievalErrorCode

    @model_validator(mode="after")
    def validate_counts_and_flags(self) -> "RetrievalSafeView":
        if self.result_count != sum(source.count for source in self.sources):
            raise ValueError("retrieval_safe_view_count_mismatch")
        if self.has_results != (self.result_count > 0):
            raise ValueError("retrieval_safe_view_result_flag_mismatch")
        return self


def validate_retrieval_safe_view(value: object) -> RetrievalSafeView:
    """Deeply reconstruct a safe view, including nested constructed models."""

    if isinstance(value, RetrievalSafeView):
        payload = _exact_model_payload(value, RetrievalSafeView)
        raw_sources = payload["sources"]
    elif isinstance(value, dict):
        payload = dict(value)
        raw_sources = payload.get("sources", ())
    else:
        return RetrievalSafeView.model_validate(value)

    if not isinstance(raw_sources, tuple):
        return RetrievalSafeView.model_validate(payload)

    rebuilt_sources = []
    for source in raw_sources:
        if isinstance(source, RetrievalSafeSourceView):
            source_payload = _exact_model_payload(source, RetrievalSafeSourceView)
        else:
            source_payload = source
        rebuilt_sources.append(RetrievalSafeSourceView.model_validate(source_payload))
    payload["sources"] = tuple(rebuilt_sources)
    return RetrievalSafeView.model_validate(payload)


def validate_retrieval_safe_citation(value: object) -> RetrievalSafeCitation:
    """Reconstruct a citation so `model_construct` cannot smuggle private fields."""

    if isinstance(value, RetrievalSafeCitation):
        payload = _exact_model_payload(
            value,
            RetrievalSafeCitation,
            error_code="retrieval_safe_citation_shape_invalid",
        )
    else:
        payload = value
    return RetrievalSafeCitation.model_validate(payload)


def _exact_model_payload(
    value: BaseModel,
    model_type: type[BaseModel],
    *,
    error_code: str = "retrieval_safe_view_shape_invalid",
) -> dict:
    expected_fields = set(model_type.model_fields)
    actual_fields = set(value.__dict__)
    if actual_fields != expected_fields:
        raise ValueError(error_code)
    return {name: value.__dict__[name] for name in expected_fields}
