from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.runtime.stage08_retrieval_contracts import (
    KnowledgeChunkProjection,
    KnowledgeSourceProjection,
    RetrievalSafeSourceView,
    RetrievalSafeView,
    validate_retrieval_safe_view,
)


HASH = "a" * 64


def _source_projection(**overrides: object) -> KnowledgeSourceProjection:
    values: dict[str, object] = {
        "source_type": "memory_item",
        "status": "active",
        "source_ref": {"entity_kind": "memory_item", "version": 1},
        "scope": {"scope_category": "business"},
        "logical_source_fingerprint": HASH,
        "projection_hash": "b" * 64,
        "projection_text": "approved projection",
        "content_version": 1,
    }
    values.update(overrides)
    return KnowledgeSourceProjection.model_validate(values)


def _chunk_projection(**overrides: object) -> KnowledgeChunkProjection:
    values: dict[str, object] = {
        "source_version": 1,
        "ordinal": 0,
        "chunk_text": "approved projection",
        "chunk_hash": HASH,
        "keyword_terms": ("approved", "projection"),
        "embedding_profile": "stage08.test-hash-v1",
        "embedding_version": 1,
        "status": "indexed",
    }
    values.update(overrides)
    return KnowledgeChunkProjection.model_validate(values)


@pytest.mark.parametrize(
    "status",
    ["pending", "active", "replaced", "revoked", "expired", "deleted"],
)
def test_source_projection_accepts_only_exact_source_status_shape(status: str) -> None:
    projection_text = "approved projection" if status == "active" else None
    assert _source_projection(status=status, projection_text=projection_text).status == status


@pytest.mark.parametrize(
    "status",
    ["pending", "indexed", "stale", "deleted", "failed"],
)
def test_chunk_projection_accepts_only_exact_chunk_status_shape(status: str) -> None:
    chunk_text = "approved projection" if status == "indexed" else None
    assert _chunk_projection(status=status, chunk_text=chunk_text).status == status


@pytest.mark.parametrize("status", ["ready", "superseded", "error", "INDEXED", ""])
def test_source_projection_rejects_unknown_status(status: str) -> None:
    with pytest.raises(ValidationError):
        _source_projection(status=status)


@pytest.mark.parametrize("status", ["active", "ready", "error", "INDEXED", ""])
def test_chunk_projection_rejects_unknown_status(status: str) -> None:
    with pytest.raises(ValidationError):
        _chunk_projection(status=status)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("logical_source_fingerprint", "A" * 64),
        ("projection_hash", "g" * 64),
        ("projection_hash", "a" * 63),
        ("content_version", 0),
        ("content_version", True),
    ],
)
def test_source_projection_rejects_invalid_hash_or_version(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        _source_projection(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chunk_hash", "A" * 64),
        ("chunk_hash", "z" * 64),
        ("source_version", 0),
        ("source_version", True),
        ("ordinal", -1),
        ("embedding_version", 0),
    ],
)
def test_chunk_projection_rejects_invalid_hash_version_or_ordinal(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        _chunk_projection(**{field: value})


def test_active_source_and_indexed_chunk_require_nonempty_text() -> None:
    with pytest.raises(ValidationError):
        _source_projection(projection_text="  ")
    with pytest.raises(ValidationError):
        _chunk_projection(chunk_text="")


def test_retrieval_safe_view_accepts_only_fixed_safe_categories() -> None:
    view = RetrievalSafeView.model_validate(
        {
            "contract_version": "stage08.retrieval-safe.v1",
            "status": "degraded",
            "sources": (
                {
                    "source_type_category": "business_memory",
                    "scope_category": "business",
                    "count": 2,
                    "available": True,
                },
            ),
            "result_count": 2,
            "has_results": True,
            "degradation_code": "keyword_only",
            "error_code": "none",
        }
    )

    assert validate_retrieval_safe_view(view) == view
    assert "approved projection" not in repr(view)


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "text",
        "content",
        "source_id",
        "chunk_id",
        "record_id",
        "field_id",
        "source_ref",
        "scope",
        "projection_hash",
        "chunk_hash",
        "embedding_profile",
        "embedding",
        "query",
        "score",
        "actor",
        "authority",
        "renderer",
        "exception",
        "diagnostic",
    ],
)
def test_retrieval_safe_view_rejects_forbidden_public_fields(
    forbidden_field: str,
) -> None:
    payload = {
        "contract_version": "stage08.retrieval-safe.v1",
        "status": "ready",
        "sources": (),
        "result_count": 0,
        "has_results": False,
        "degradation_code": "none",
        "error_code": "none",
        forbidden_field: str(uuid4()),
    }
    with pytest.raises(ValidationError):
        RetrievalSafeView.model_validate(payload)


def test_safe_view_deep_validation_rejects_nested_model_construct_escape() -> None:
    nested = RetrievalSafeSourceView.model_construct(
        source_type_category="memory_item",
        scope_category="business",
        count="2",
        available=1,
    )
    bypassed = RetrievalSafeView.model_construct(
        contract_version="stage08.retrieval-safe.v1",
        status="ready",
        sources=(nested,),
        result_count=2,
        has_results=True,
        degradation_code="none",
        error_code="none",
    )

    with pytest.raises(ValidationError):
        validate_retrieval_safe_view(bypassed)


def test_safe_view_deep_validation_rejects_mutated_nested_object() -> None:
    nested = RetrievalSafeSourceView.model_validate(
        {
            "source_type_category": "business_memory",
            "scope_category": "business",
            "count": 1,
            "available": True,
        }
    )
    object.__setattr__(nested, "query", "private search")
    bypassed = RetrievalSafeView.model_construct(
        contract_version="stage08.retrieval-safe.v1",
        status="ready",
        sources=(nested,),
        result_count=1,
        has_results=True,
        degradation_code="none",
        error_code="none",
    )

    with pytest.raises((TypeError, ValueError, ValidationError)):
        validate_retrieval_safe_view(bypassed)


def test_safe_view_has_no_uuid_or_free_text_carrier() -> None:
    assert set(RetrievalSafeView.model_fields) == {
        "contract_version",
        "status",
        "sources",
        "result_count",
        "has_results",
        "degradation_code",
        "error_code",
    }
    assert set(RetrievalSafeSourceView.model_fields) == {
        "source_type_category",
        "scope_category",
        "count",
        "available",
    }
