from __future__ import annotations

import json
from pathlib import Path
import re

from app.schemas.retrieval_v2 import (
    RetrievalBenchmarkCorpusV2,
    canonical_retrieval_sha256,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "stage12_retrieval_benchmark_v2.json"
)
EXACT_CODE = re.compile(r"\b(?:MT|RISK|PRJ|OWNER|INT)-[A-Z0-9-]+\b")


def test_focused_retrieval_corpus_is_frozen_and_semantic() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )
    payload = corpus.model_dump(mode="json", exclude={"corpus_hash"})

    assert corpus.corpus_hash == canonical_retrieval_sha256(payload)
    assert corpus.source_fixture_hash == (
        "eac654ca303bd9438515aceffd87204de8f8f9e64caab1e384ffa4f47dee4252"
    )
    assert {case.category for case in corpus.cases} == {
        "schema",
        "entity_alias",
        "non_structured",
    }
    assert len(corpus.cases) >= 12
    assert len(corpus.candidates) > 20
    assert all(not EXACT_CODE.search(case.query) for case in corpus.cases)
    assert all(case.relevant_candidate_ids for case in corpus.cases)
    assert all(case.negative_candidate_ids for case in corpus.cases)
    assert all(case.forbidden_candidate_ids for case in corpus.cases)


def test_corpus_references_only_known_candidates_without_truth_overlap() -> None:
    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )
    known = {candidate.candidate_id for candidate in corpus.candidates}

    for case in corpus.cases:
        relevant = set(case.relevant_candidate_ids)
        negative = set(case.negative_candidate_ids)
        forbidden = set(case.forbidden_candidate_ids)
        assert relevant <= known
        assert negative <= known
        assert forbidden.isdisjoint(known)
        assert relevant.isdisjoint(negative)
        assert relevant.isdisjoint(forbidden)
        assert negative.isdisjoint(forbidden)


def test_corpus_contains_no_hidden_fixture_markers() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    assert "customer_secret" not in text
    assert "internal_note" not in text
    assert "hidden-secret" not in text
