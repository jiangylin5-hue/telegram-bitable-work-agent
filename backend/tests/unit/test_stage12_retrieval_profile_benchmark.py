from __future__ import annotations

import json
from pathlib import Path

from app.schemas.retrieval_v2 import (
    EmbeddingProfileV1,
    RetrievalBenchmarkCorpusV2,
    RetrievalProfileBenchmarkReportV1,
    canonical_retrieval_sha256,
)
from scripts.stage12_retrieval_benchmark import run_retrieval_profile_benchmark
from scripts.stage12_retrieval_benchmark import (
    get_stage12_benchmark_profile,
    main as benchmark_main,
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
            profile_name="stage12.test-perfect-map-v1",
            model_revision="synthetic-perfect-map-001",
            dimension=dimension,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=384,
            batch_size=64,
            provider_location="local",
            data_residency="synthetic-test-only",
        )
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
        self._query_vectors = {}
        self.document_call_count = 0
        self.query_call_count = 0
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
        self.document_call_count += 1
        return tuple(self._document_vectors[text] for text in texts)

    def embed_queries(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        self.query_call_count += 1
        return tuple(self._query_vectors[text] for text in texts)


def test_benchmark_runner_reports_perfect_focused_metrics_without_raw_data() -> None:
    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )
    provider = _PerfectMappedProvider(corpus)
    report = run_retrieval_profile_benchmark(
        corpus,
        provider=provider,
        rounds=3,
        top_k=20,
    )

    assert isinstance(report, RetrievalProfileBenchmarkReportV1)
    assert report.completed_rounds == 3
    assert report.failed_rounds == 0
    assert report.overall.recall_at_20 == 1.0
    assert report.overall.mrr_at_20 == 1.0
    assert report.overall.forbidden_candidate_count == 0
    assert {score.category for score in report.categories} == {
        "schema",
        "entity_alias",
        "non_structured",
    }
    assert report.report_hash == canonical_retrieval_sha256(
        report.model_dump(mode="json", exclude={"report_hash"})
    )
    assert provider.document_call_count == 4
    assert provider.query_call_count == 4

    rendered = report.model_dump_json()
    assert not any(case.query in rendered for case in corpus.cases)
    assert not any(
        candidate.canonical_text in rendered for candidate in corpus.candidates
    )
    assert "embedding" not in rendered.casefold()


def test_benchmark_report_roundtrips_as_sanitized_json() -> None:
    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )
    report = run_retrieval_profile_benchmark(
        corpus,
        provider=_PerfectMappedProvider(corpus),
        rounds=1,
        top_k=20,
    )
    payload = json.loads(report.model_dump_json())

    assert (
        RetrievalProfileBenchmarkReportV1.model_validate_json(json.dumps(payload))
        == report
    )
    assert payload["corpus_hash"] == corpus.corpus_hash
    assert payload["profile"]["dimension"] == len(corpus.candidates)


def test_benchmark_warmup_failure_marks_every_requested_round_failed() -> None:
    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )
    provider = _PerfectMappedProvider(corpus)

    def fail_warmup(texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        raise RuntimeError("sensitive-provider-detail")

    provider.embed_documents = fail_warmup  # type: ignore[method-assign]
    report = run_retrieval_profile_benchmark(
        corpus,
        provider=provider,
        rounds=3,
        top_k=20,
    )

    assert report.completed_rounds == 0
    assert report.failed_rounds == 3
    assert "sensitive-provider-detail" not in report.model_dump_json()


def test_named_profiles_freeze_exact_candidate_boundary() -> None:
    local = get_stage12_benchmark_profile("local-bge-m3")
    remote_bge = get_stage12_benchmark_profile("openrouter-bge-m3")
    remote_e5 = get_stage12_benchmark_profile("openrouter-multilingual-e5-large")

    assert local.model_revision == "5617a9f61b028005a4858fdac845db406aefb181"
    assert local.provider_location == "local"
    assert remote_bge.model_revision == "baai/bge-m3-20251117"
    assert remote_bge.max_input_tokens == 8192
    assert remote_e5.model_revision == ("intfloat/multilingual-e5-large-20251117")
    assert remote_e5.max_input_tokens == 384
    assert {local.dimension, remote_bge.dimension, remote_e5.dimension} == {1024}


def test_cli_writes_only_sanitized_report_with_injected_provider(
    tmp_path: Path,
    capsys: object,
) -> None:
    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )
    output_path = tmp_path / "report.json"

    exit_code = benchmark_main(
        [
            "--profile",
            "openrouter-bge-m3",
            "--rounds",
            "1",
            "--output-json",
            str(output_path),
        ],
        provider_factory=lambda profile_name, profile: _PerfectMappedProvider(corpus),
    )

    assert exit_code == 0
    report = RetrievalProfileBenchmarkReportV1.model_validate_json(
        output_path.read_text(encoding="utf-8")
    )
    assert report.completed_rounds == 1
    rendered = output_path.read_text(encoding="utf-8")
    assert not any(case.query in rendered for case in corpus.cases)
    assert not any(
        candidate.canonical_text in rendered for candidate in corpus.candidates
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert report.report_hash in captured.out
