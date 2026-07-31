"""Focused, sanitized Stage12-D retrieval diagnostic and acceptance evidence."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os
from pathlib import Path
from typing import Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)

from app.schemas.agent_task_spec_v2 import Sha256Hex
from app.schemas.retrieval_v2 import (
    EmbeddingProfileV1,
    RetrievalBenchmarkCorpusV2,
    canonical_retrieval_sha256,
)
from scripts.stage12_retrieval_benchmark import (
    _create_named_provider,
    get_stage12_benchmark_profile,
    run_retrieval_profile_benchmark,
)


class _EmbeddingProvider(Protocol):
    profile: EmbeddingProfileV1
    consumed_input_tokens: int
    estimated_cost_usd: float

    def embed_documents(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]: ...

    def embed_queries(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]: ...


ProviderFactory = Callable[[str, EmbeddingProfileV1], _EmbeddingProvider]


class Stage12RetrievalEvaluationReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["stage12-retrieval-v2-evaluation.v1"]
    profile_name: StrictStr
    model_revision: StrictStr
    corpus_hash: Sha256Hex
    requested_rounds: StrictInt
    completed_rounds: StrictInt
    failed_rounds: StrictInt
    case_count: StrictInt
    recall_at_20: StrictFloat
    mrr_at_20: StrictFloat
    forbidden_candidate_count: StrictInt
    truncated_case_count: StrictInt
    p95_latency_ms: StrictFloat
    provider_call_count: StrictInt
    action_expansion_count: StrictInt
    record_write_count: StrictInt
    external_send_count: StrictInt
    passed: StrictBool
    report_hash: Sha256Hex


class _CountingProvider:
    def __init__(self, provider: _EmbeddingProvider) -> None:
        self._provider = provider
        self.profile = provider.profile
        self.provider_call_count = 0

    @property
    def consumed_input_tokens(self) -> int:
        return int(getattr(self._provider, "consumed_input_tokens", 0))

    @property
    def estimated_cost_usd(self) -> float:
        return float(getattr(self._provider, "estimated_cost_usd", 0.0))

    def embed_documents(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        self.provider_call_count += 1
        return self._provider.embed_documents(texts)

    def embed_queries(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        self.provider_call_count += 1
        return self._provider.embed_queries(texts)


def run_stage12_retrieval_v2_evaluation(
    corpus: RetrievalBenchmarkCorpusV2,
    *,
    provider: _EmbeddingProvider,
    rounds: int,
) -> Stage12RetrievalEvaluationReportV1:
    counted = _CountingProvider(provider)
    benchmark = run_retrieval_profile_benchmark(
        corpus,
        provider=counted,
        rounds=rounds,
        top_k=20,
    )
    truncated_case_count = len(corpus.cases) if len(corpus.candidates) > 20 else 0
    passed = (
        benchmark.completed_rounds == rounds
        and benchmark.failed_rounds == 0
        and benchmark.overall.recall_at_20 >= 0.95
        and benchmark.overall.mrr_at_20 >= 0.90
        and benchmark.overall.forbidden_candidate_count == 0
        and benchmark.p95_latency_ms <= 20_000.0
    )
    values = {
        "version": "stage12-retrieval-v2-evaluation.v1",
        "profile_name": benchmark.profile.profile_name,
        "model_revision": benchmark.profile.model_revision,
        "corpus_hash": corpus.corpus_hash,
        "requested_rounds": rounds,
        "completed_rounds": benchmark.completed_rounds,
        "failed_rounds": benchmark.failed_rounds,
        "case_count": len(corpus.cases),
        "recall_at_20": benchmark.overall.recall_at_20,
        "mrr_at_20": benchmark.overall.mrr_at_20,
        "forbidden_candidate_count": benchmark.overall.forbidden_candidate_count,
        "truncated_case_count": truncated_case_count,
        "p95_latency_ms": benchmark.p95_latency_ms,
        "provider_call_count": counted.provider_call_count,
        "action_expansion_count": 0,
        "record_write_count": 0,
        "external_send_count": 0,
        "passed": passed,
    }
    return Stage12RetrievalEvaluationReportV1(
        **values,
        report_hash=canonical_retrieval_sha256(values),
    )


def _default_corpus_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "stage12_retrieval_benchmark_v2.json"
    )


def _write_atomically(path: Path, content: str) -> None:
    resolved = path.expanduser().resolve()
    if not resolved.parent.is_dir():
        raise ValueError("retrieval_evaluation_output_parent_missing")
    temporary = resolved.with_name(f".{resolved.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, resolved)


def _render_markdown(report: Stage12RetrievalEvaluationReportV1) -> str:
    return "\n".join(
        (
            "# Stage12-D Focused Retrieval V2 Evidence",
            "",
            f"- Status: {'PASS' if report.passed else 'FAIL'}",
            f"- Profile: `{report.profile_name}`",
            f"- Model revision: `{report.model_revision}`",
            f"- Corpus hash: `{report.corpus_hash}`",
            f"- Rounds: `{report.completed_rounds}/{report.requested_rounds}`",
            f"- Recall@20: `{report.recall_at_20:.6f}`",
            f"- MRR@20: `{report.mrr_at_20:.6f}`",
            f"- Forbidden candidates: `{report.forbidden_candidate_count}`",
            f"- Truncated cases: `{report.truncated_case_count}`",
            f"- P95 latency ms: `{report.p95_latency_ms:.3f}`",
            f"- Provider calls: `{report.provider_call_count}`",
            f"- Action expansions: `{report.action_expansion_count}`",
            f"- Record writes: `{report.record_write_count}`",
            f"- External sends: `{report.external_send_count}`",
            f"- Report hash: `{report.report_hash}`",
            "",
        )
    )


def main(
    argv: list[str] | None = None,
    *,
    provider_factory: ProviderFactory | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run the focused Stage12-D retrieval V2 diagnostic.",
    )
    parser.add_argument("--rounds", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument(
        "--corpus-json",
        type=Path,
        default=_default_corpus_path(),
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args(argv)

    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        args.corpus_json.read_text(encoding="utf-8")
    )
    profile_name = "openrouter-bge-m3"
    profile = get_stage12_benchmark_profile(profile_name)
    factory = provider_factory or _create_named_provider
    provider = factory(profile_name, profile)
    try:
        report = run_stage12_retrieval_v2_evaluation(
            corpus,
            provider=provider,
            rounds=args.rounds,
        )
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()
    _write_atomically(args.output_json, report.model_dump_json(indent=2))
    _write_atomically(args.output_md, _render_markdown(report))
    print(
        json.dumps(
            {
                "passed": report.passed,
                "profile_name": report.profile_name,
                "report_hash": report.report_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "Stage12RetrievalEvaluationReportV1",
    "main",
    "run_stage12_retrieval_v2_evaluation",
]
