from __future__ import annotations

import json
from pathlib import Path

from app.schemas.retrieval_v2 import (
    EmbeddingProfileV1,
    RetrievalBenchmarkCorpusV2,
    canonical_retrieval_sha256,
)
from scripts.stage12_retrieval_v2_evaluation import (
    Stage12RetrievalEvaluationReportV1,
    main as evaluation_main,
    run_stage12_retrieval_v2_evaluation,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "stage12_retrieval_benchmark_v2.json"
)


class _PerfectMappedProvider:
    def __init__(self, corpus: RetrievalBenchmarkCorpusV2) -> None:
        dimension = len(corpus.candidates)
        self.profile = EmbeddingProfileV1(
            version="embedding-profile.v1",
            profile_name="stage12.openrouter-bge-m3-v1",
            model_revision="baai/bge-m3-20251117",
            dimension=dimension,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
        )
        self.consumed_input_tokens = 0
        self.estimated_cost_usd = 0.0
        self._document_vectors = {
            candidate.canonical_text: tuple(
                1.0 if index == ordinal else 0.0 for index in range(dimension)
            )
            for ordinal, candidate in enumerate(corpus.candidates)
        }
        candidate_position = {
            candidate.candidate_id: index
            for index, candidate in enumerate(corpus.candidates)
        }
        self._query_vectors: dict[str, tuple[float, ...]] = {}
        for case in corpus.cases:
            vector = [0.0] * dimension
            for candidate_id in case.relevant_candidate_ids:
                vector[candidate_position[candidate_id]] = 1.0
            magnitude = sum(value * value for value in vector) ** 0.5
            self._query_vectors[case.query] = tuple(
                value / magnitude for value in vector
            )

    def embed_documents(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        return tuple(self._document_vectors[text] for text in texts)

    def embed_queries(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        return tuple(self._query_vectors[text] for text in texts)


def test_focused_evaluation_reports_recall_rank_truncation_and_zero_side_effects() -> (
    None
):
    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )

    report = run_stage12_retrieval_v2_evaluation(
        corpus,
        provider=_PerfectMappedProvider(corpus),
        rounds=1,
    )

    assert isinstance(report, Stage12RetrievalEvaluationReportV1)
    assert report.completed_rounds == 1
    assert report.recall_at_20 == 1.0
    assert report.mrr_at_20 == 1.0
    assert report.forbidden_candidate_count == 0
    assert report.truncated_case_count == len(corpus.cases)
    assert report.provider_call_count == 4
    assert report.action_expansion_count == 0
    assert report.record_write_count == 0
    assert report.external_send_count == 0
    assert report.passed is True
    assert report.report_hash == canonical_retrieval_sha256(
        report.model_dump(mode="json", exclude={"report_hash"})
    )
    rendered = report.model_dump_json()
    assert not any(case.query in rendered for case in corpus.cases)
    assert not any(
        candidate.canonical_text in rendered for candidate in corpus.candidates
    )


def test_cli_writes_sanitized_machine_and_human_evidence(
    tmp_path: Path,
) -> None:
    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )
    json_path = tmp_path / "retrieval.json"
    markdown_path = tmp_path / "retrieval.md"

    exit_code = evaluation_main(
        [
            "--rounds",
            "1",
            "--corpus-json",
            str(FIXTURE),
            "--output-json",
            str(json_path),
            "--output-md",
            str(markdown_path),
        ],
        provider_factory=lambda _profile_name, _profile: _PerfectMappedProvider(corpus),
    )

    assert exit_code == 0
    report = Stage12RetrievalEvaluationReportV1.model_validate_json(
        json_path.read_text(encoding="utf-8")
    )
    assert report.passed is True
    machine = json.loads(json_path.read_text(encoding="utf-8"))
    human = markdown_path.read_text(encoding="utf-8")
    assert machine["report_hash"] in human
    combined = json_path.read_text(encoding="utf-8") + human
    assert not any(case.query in combined for case in corpus.cases)
    assert not any(
        candidate.canonical_text in combined for candidate in corpus.candidates
    )
