from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from app.core.config import Settings
from app.schemas.retrieval_v2 import (
    RetrievalCandidateV2,
    RetrievalComponentScoresV2,
)
from app.services.retrieval_v2_hybrid import AuthorizedRetrievalResultV2
from app.services.retrieval_v2_shadow import (
    RetrievalShadowCandidateSetV1,
    retrieval_v2_shadow_enabled,
    run_retrieval_v2_shadow,
)


WORKSPACE_ID = UUID("40000000-0000-0000-0000-000000000001")
TABLE_ID = UUID("40000000-0000-0000-0000-000000000010")
FIELD_ID = UUID("40000000-0000-0000-0000-000000000101")
PROFILE = "stage12.openrouter-bge-m3-v1"


def _settings(
    *, allowlisted: bool = True, api_key: str | None = "test-key"
) -> Settings:
    return Settings(
        openrouter_api_key=api_key,
        retrieval_v2_mode="shadow",
        retrieval_v2_workspace_allowlist=(str(WORKSPACE_ID),) if allowlisted else (),
        retrieval_v2_active_profile=PROFILE,
    )


def _candidate(source_id: str) -> RetrievalCandidateV2:
    return RetrievalCandidateV2(
        version="retrieval-candidate.v2",
        candidate_id=f"candidate:{source_id}",
        source_type="record",
        source_id=source_id,
        source_version=1,
        table_id=TABLE_ID,
        record_id=UUID(int=int(sha256(source_id.encode()).hexdigest()[:32], 16)),
        field_ids=(FIELD_ID,),
        priority_band="fuzzy",
        retrieval_reason="semantic",
        scores=RetrievalComponentScoresV2(
            keyword=0.0,
            semantic=1.0,
            entity_schema=0.0,
            freshness=0.0,
            total=0.35,
        ),
        scope_hash="a" * 64,
        content_hash=sha256(source_id.encode()).hexdigest(),
        embedding_profile=PROFILE,
    )


def _candidate_set(
    source_ids: tuple[str, ...],
    *,
    truncated: bool = False,
) -> RetrievalShadowCandidateSetV1:
    candidates = tuple(_candidate(source_id) for source_id in source_ids)
    return RetrievalShadowCandidateSetV1(
        v1_candidate_ids=("record:a", "record:b", "record:c"),
        v2_result=AuthorizedRetrievalResultV2(
            candidates=candidates,
            primary_candidates=candidates,
            relation_edges=(),
            truncated=truncated,
        ),
    )


def test_shadow_is_default_off_allowlisted_and_never_invokes_loader_outside_gate() -> (
    None
):
    calls = 0

    def loader() -> RetrievalShadowCandidateSetV1:
        nonlocal calls
        calls += 1
        return _candidate_set(("record:a",))

    assert retrieval_v2_shadow_enabled(Settings(), WORKSPACE_ID) is False
    assert (
        retrieval_v2_shadow_enabled(_settings(allowlisted=False), WORKSPACE_ID) is False
    )
    assert retrieval_v2_shadow_enabled(_settings(api_key=None), WORKSPACE_ID) is False
    assert (
        run_retrieval_v2_shadow(
            settings=Settings(),
            workspace_id=WORKSPACE_ID,
            candidate_loader=loader,
        )
        is None
    )
    assert (
        run_retrieval_v2_shadow(
            settings=_settings(allowlisted=False),
            workspace_id=WORKSPACE_ID,
            candidate_loader=loader,
        )
        is None
    )
    assert calls == 0


def test_shadow_observation_contains_only_sanitized_overlap_rank_and_truncation() -> (
    None
):
    observation = run_retrieval_v2_shadow(
        settings=_settings(),
        workspace_id=WORKSPACE_ID,
        candidate_loader=lambda: _candidate_set(
            ("record:b", "record:a", "record:z"),
            truncated=True,
        ),
    )

    assert observation is not None
    assert observation.status == "observed"
    assert observation.v1_candidate_count == 3
    assert observation.v2_candidate_count == 3
    assert observation.overlap_count == 2
    assert observation.recall_at_20 == 2 / 3
    assert observation.mrr_at_20 == 1.0
    assert observation.mean_absolute_rank_delta == 1.0
    assert observation.truncated is True
    serialized = observation.model_dump_json()
    assert "record:a" not in serialized
    assert "record:z" not in serialized
    assert "query" not in serialized
    assert "vector" not in serialized
    assert "chunk_text" not in serialized


def test_shadow_provider_failure_is_isolated_and_sanitized() -> None:
    def fail() -> RetrievalShadowCandidateSetV1:
        raise RuntimeError("provider leaked-secret@example.com")

    observation = run_retrieval_v2_shadow(
        settings=_settings(),
        workspace_id=WORKSPACE_ID,
        candidate_loader=fail,
    )

    assert observation is not None
    assert observation.status == "shadow_failed"
    assert observation.failure_code == "retrieval_v2_shadow_failure"
    assert "leaked-secret" not in observation.model_dump_json()
