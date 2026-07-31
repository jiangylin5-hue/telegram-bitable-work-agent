from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.retrieval_v2 import (
    EvidenceBundleV2,
    RetrievalCandidateV2,
    RetrievalRelationEdgeProjectionV2,
    RetrievalRequestV2,
    canonical_retrieval_sha256,
)


WORKSPACE_ID = UUID("00000000-0000-0000-0000-000000000001")
BASE_ID = UUID("00000000-0000-0000-0000-000000000002")
TABLE_ID = UUID("00000000-0000-0000-0000-000000000003")
RECORD_ID = UUID("00000000-0000-0000-0000-000000000004")
FIELD_ID = UUID("00000000-0000-0000-0000-000000000005")
HASH = "a" * 64


def _request_payload() -> dict[str, object]:
    return {
        "version": "retrieval-request.v2",
        "objective_id": "obj-01",
        "query": "等待范围确认的事项",
        "workspace_id": WORKSPACE_ID,
        "base_id": BASE_ID,
        "table_ids": (TABLE_ID,),
        "exact_record_ids": (),
        "query_result_ref": None,
        "scope_hash": HASH,
        "schema_hash": HASH,
        "max_primary_candidates": 20,
        "max_relation_expansions_per_primary": 10,
        "max_evidence_nodes": 24,
    }


def _candidate_payload(candidate_id: str = "candidate-01") -> dict[str, object]:
    return {
        "version": "retrieval-candidate.v2",
        "candidate_id": candidate_id,
        "source_type": "record",
        "source_id": "record:mt-001",
        "source_version": 3,
        "table_id": TABLE_ID,
        "record_id": RECORD_ID,
        "field_ids": (FIELD_ID,),
        "priority_band": "fuzzy",
        "retrieval_reason": "hybrid",
        "scores": {
            "keyword": 0.2,
            "semantic": 0.8,
            "entity_schema": 0.5,
            "freshness": 0.5,
            "total": 0.5,
        },
        "scope_hash": HASH,
        "content_hash": HASH,
        "embedding_profile": "stage12.bge-m3-1024-v1",
    }


def _bundle_payload() -> dict[str, object]:
    values: dict[str, object] = {
        "version": "evidence-bundle.v2",
        "objective_id": "obj-01",
        "query_result_ref": None,
        "nodes": (
            {
                "evidence_id": "ev-01",
                "kind": "record",
                "source_id": "record:mt-001",
                "source_version": 3,
                "table_id": TABLE_ID,
                "record_id": RECORD_ID,
                "fields": (
                    {
                        "field_id": FIELD_ID,
                        "field_key": "summary",
                        "value": "等待范围确认",
                    },
                ),
                "content_hash": HASH,
            },
        ),
        "relations": (),
        "aggregates": (),
        "scope_hash": HASH,
        "complete": True,
        "truncated": False,
    }
    values["bundle_hash"] = canonical_retrieval_sha256(values)
    return values


def test_request_enforces_fixed_stage12_budgets() -> None:
    request = RetrievalRequestV2.model_validate(_request_payload())
    assert request.max_primary_candidates == 20
    assert request.max_relation_expansions_per_primary == 10
    assert request.max_evidence_nodes == 24

    for key, value in (
        ("max_primary_candidates", 21),
        ("max_relation_expansions_per_primary", 11),
        ("max_evidence_nodes", 25),
    ):
        with pytest.raises(ValidationError):
            RetrievalRequestV2.model_validate({**_request_payload(), key: value})


def test_candidate_rejects_non_finite_or_out_of_range_score() -> None:
    for value in (float("nan"), float("inf"), -0.01, 1.01):
        payload = _candidate_payload()
        payload["scores"] = {**payload["scores"], "semantic": value}
        with pytest.raises(ValidationError):
            RetrievalCandidateV2.model_validate(payload)


def test_relation_projection_allows_distinct_records_in_the_same_table() -> None:
    values: dict[str, object] = {
        "version": "retrieval-relation-edge.v2",
        "relation_id": "relation:parent",
        "source_table_id": TABLE_ID,
        "source_record_id": RECORD_ID,
        "link_field_id": FIELD_ID,
        "target_table_id": TABLE_ID,
        "target_record_id": UUID("00000000-0000-0000-0000-000000000006"),
        "direction": "forward",
        "source_version": 3,
        "target_version": 2,
        "visibility_profile_hash": HASH,
        "scope_hash": HASH,
    }
    values["edge_hash"] = canonical_retrieval_sha256(values)

    edge = RetrievalRelationEdgeProjectionV2.model_validate(values)

    assert edge.source_table_id == edge.target_table_id
    assert edge.source_record_id != edge.target_record_id


def test_exact_candidate_requires_exact_reason_and_no_profile() -> None:
    payload = _candidate_payload()
    payload.update(
        priority_band="exact",
        retrieval_reason="exact_identifier",
        embedding_profile=None,
    )
    assert RetrievalCandidateV2.model_validate(payload).priority_band == "exact"

    payload["retrieval_reason"] = "semantic"
    with pytest.raises(ValidationError, match="retrieval_candidate_band_invalid"):
        RetrievalCandidateV2.model_validate(payload)


def test_evidence_bundle_rejects_vector_payload() -> None:
    payload = _bundle_payload()
    payload["nodes"][0]["embedding"] = [0.1, 0.2]
    with pytest.raises(ValidationError):
        EvidenceBundleV2.model_validate(payload)


def test_truncated_bundle_cannot_be_complete() -> None:
    payload = _bundle_payload()
    payload.update(complete=True, truncated=True)
    payload["bundle_hash"] = canonical_retrieval_sha256(
        {key: value for key, value in payload.items() if key != "bundle_hash"}
    )
    with pytest.raises(ValidationError, match="retrieval_completeness_invalid"):
        EvidenceBundleV2.model_validate(payload)


def test_bundle_rejects_duplicate_evidence_ids_and_hash_drift() -> None:
    payload = _bundle_payload()
    payload["nodes"] = (*payload["nodes"], dict(payload["nodes"][0]))
    payload["bundle_hash"] = canonical_retrieval_sha256(
        {key: value for key, value in payload.items() if key != "bundle_hash"}
    )
    with pytest.raises(ValidationError, match="retrieval_evidence_id_duplicate"):
        EvidenceBundleV2.model_validate(payload)

    payload = _bundle_payload()
    payload["bundle_hash"] = "b" * 64
    with pytest.raises(ValidationError, match="retrieval_bundle_hash_mismatch"):
        EvidenceBundleV2.model_validate(payload)
