"""Run the small Stage12-D retrieval profile benchmark without raw-data reports."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable
import json
import math
import os
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Callable, Protocol

from app.schemas.retrieval_v2 import (
    EmbeddingProfileV1,
    RetrievalBenchmarkCorpusV2,
    RetrievalBenchmarkMetricV1,
    RetrievalBenchmarkProfileSummaryV1,
    RetrievalProfileBenchmarkReportV1,
    canonical_retrieval_sha256,
)
from app.services.retrieval_v2_embeddings import (
    EmbeddingProviderError,
    LocalBgeM3EmbeddingProviderV2,
    OpenRouterEmbeddingProviderV2,
)


class EmbeddingProviderV2(Protocol):
    profile: EmbeddingProfileV1
    consumed_input_tokens: int
    estimated_cost_usd: float

    def embed_documents(
        self, texts: tuple[str, ...]
    ) -> tuple[tuple[float, ...], ...]: ...


NamedProviderFactory = Callable[
    [str, EmbeddingProfileV1],
    EmbeddingProviderV2,
]

LOCAL_BGE_M3_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
OPENROUTER_BGE_M3_REVISION = "baai/bge-m3-20251117"
OPENROUTER_E5_REVISION = "intfloat/multilingual-e5-large-20251117"
NAMED_PROFILES = (
    "local-bge-m3",
    "openrouter-bge-m3",
    "openrouter-multilingual-e5-large",
)


def get_stage12_benchmark_profile(profile_name: str) -> EmbeddingProfileV1:
    if profile_name == "local-bge-m3":
        return EmbeddingProfileV1(
            version="embedding-profile.v1",
            profile_name="stage12.local-bge-m3-v1",
            model_revision=LOCAL_BGE_M3_REVISION,
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=8,
            provider_location="local",
            data_residency="local-cpu-benchmark-only",
        )
    if profile_name == "openrouter-bge-m3":
        return EmbeddingProfileV1(
            version="embedding-profile.v1",
            profile_name="stage12.openrouter-bge-m3-v1",
            model_revision=OPENROUTER_BGE_M3_REVISION,
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-benchmark-openrouter-deny-zdr",
        )
    if profile_name == "openrouter-multilingual-e5-large":
        return EmbeddingProfileV1(
            version="embedding-profile.v1",
            profile_name="stage12.openrouter-multilingual-e5-large-v1",
            model_revision=OPENROUTER_E5_REVISION,
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=384,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-benchmark-openrouter-deny-zdr",
        )
    raise ValueError("retrieval_benchmark_profile_unknown")


def _create_named_provider(
    profile_name: str,
    profile: EmbeddingProfileV1,
) -> EmbeddingProviderV2:
    if profile_name == "local-bge-m3":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise EmbeddingProviderError(
                "embedding_local_runtime_unavailable"
            ) from None
        cache_folder = os.getenv("STAGE12_BGE_M3_CACHE_DIR") or None
        try:
            model = SentenceTransformer(
                "BAAI/bge-m3",
                revision=LOCAL_BGE_M3_REVISION,
                cache_folder=cache_folder,
                device="cpu",
                trust_remote_code=False,
            )
        except Exception:
            raise EmbeddingProviderError("embedding_local_model_unavailable") from None
        return LocalBgeM3EmbeddingProviderV2(
            profile=profile,
            model=model,
        )

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise EmbeddingProviderError("embedding_provider_auth_failed")
    if profile_name == "openrouter-bge-m3":
        return OpenRouterEmbeddingProviderV2(
            profile=profile,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            model_id="baai/bge-m3",
            expected_canonical_slug=OPENROUTER_BGE_M3_REVISION,
            timeout_seconds=20.0,
        )
    if profile_name == "openrouter-multilingual-e5-large":
        return OpenRouterEmbeddingProviderV2(
            profile=profile,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            model_id="intfloat/multilingual-e5-large",
            expected_canonical_slug=OPENROUTER_E5_REVISION,
            query_prefix="query: ",
            document_prefix="passage: ",
            timeout_seconds=20.0,
        )
    raise ValueError("retrieval_benchmark_profile_unknown")

    def embed_queries(
        self, texts: tuple[str, ...]
    ) -> tuple[tuple[float, ...], ...]: ...


def _batched(values: tuple[str, ...], size: int) -> Iterable[tuple[str, ...]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _embed_batched(
    values: tuple[str, ...],
    *,
    batch_size: int,
    operation: object,
) -> tuple[tuple[float, ...], ...]:
    vectors: list[tuple[float, ...]] = []
    for batch in _batched(values, batch_size):
        vectors.extend(operation(batch))  # type: ignore[operator]
    return tuple(vectors)


def _metric(
    category: str,
    values: list[tuple[float, float, int]],
    *,
    case_count: int,
) -> RetrievalBenchmarkMetricV1:
    divisor_values = values or [(0.0, 0.0, 0)]
    return RetrievalBenchmarkMetricV1(
        category=category,
        case_count=case_count,
        recall_at_20=float(mean(value[0] for value in divisor_values)),
        mrr_at_20=float(mean(value[1] for value in divisor_values)),
        forbidden_candidate_count=sum(value[2] for value in values),
    )


def _percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return float(ordered[index])


def run_retrieval_profile_benchmark(
    corpus: RetrievalBenchmarkCorpusV2,
    *,
    provider: EmbeddingProviderV2,
    rounds: int,
    top_k: int = 20,
) -> RetrievalProfileBenchmarkReportV1:
    if isinstance(rounds, bool) or rounds < 1 or rounds > 3:
        raise ValueError("retrieval_benchmark_rounds_invalid")
    if isinstance(top_k, bool) or top_k != 20:
        raise ValueError("retrieval_benchmark_top_k_invalid")

    candidate_ids = tuple(candidate.candidate_id for candidate in corpus.candidates)
    candidate_texts = tuple(candidate.canonical_text for candidate in corpus.candidates)
    query_texts = tuple(case.query for case in corpus.cases)
    scores_by_category: dict[str, list[tuple[float, float, int]]] = defaultdict(list)
    overall_scores: list[tuple[float, float, int]] = []
    latencies: list[float] = []
    completed_rounds = 0
    failed_rounds = 0

    # One untimed warm-up uses the same complete corpus and provider policy.
    try:
        _embed_batched(
            candidate_texts,
            batch_size=provider.profile.batch_size,
            operation=provider.embed_documents,
        )
        _embed_batched(
            query_texts,
            batch_size=provider.profile.batch_size,
            operation=provider.embed_queries,
        )
    except Exception:
        failed_rounds = rounds

    for _ in range(0 if failed_rounds else rounds):
        started = perf_counter()
        round_scores: list[tuple[str, tuple[float, float, int]]] = []
        try:
            document_vectors = _embed_batched(
                candidate_texts,
                batch_size=provider.profile.batch_size,
                operation=provider.embed_documents,
            )
            query_vectors = _embed_batched(
                query_texts,
                batch_size=provider.profile.batch_size,
                operation=provider.embed_queries,
            )
            if len(document_vectors) != len(candidate_ids) or len(query_vectors) != len(
                corpus.cases
            ):
                raise ValueError("retrieval_benchmark_vector_count_invalid")

            for case, query_vector in zip(corpus.cases, query_vectors, strict=True):
                ranked = sorted(
                    zip(candidate_ids, document_vectors, strict=True),
                    key=lambda item: (
                        -sum(
                            query_value * document_value
                            for query_value, document_value in zip(
                                query_vector, item[1], strict=True
                            )
                        ),
                        item[0],
                    ),
                )
                retrieved = tuple(item[0] for item in ranked[:top_k])
                relevant = set(case.relevant_candidate_ids)
                recall = len(relevant & set(retrieved)) / len(relevant)
                first_rank = next(
                    (
                        index
                        for index, candidate_id in enumerate(retrieved, 1)
                        if candidate_id in relevant
                    ),
                    None,
                )
                reciprocal_rank = 0.0 if first_rank is None else 1.0 / first_rank
                forbidden_count = len(
                    set(retrieved) & set(case.forbidden_candidate_ids)
                )
                value = (float(recall), float(reciprocal_rank), forbidden_count)
                round_scores.append((case.category, value))
        except Exception:
            failed_rounds += 1
        else:
            for category, value in round_scores:
                scores_by_category[category].append(value)
                overall_scores.append(value)
            completed_rounds += 1
            latencies.append((perf_counter() - started) * 1000.0)

    category_order = ("schema", "entity_alias", "non_structured")
    categories = tuple(
        _metric(
            category,
            scores_by_category[category],
            case_count=sum(case.category == category for case in corpus.cases),
        )
        for category in category_order
    )
    overall = _metric("overall", overall_scores, case_count=len(corpus.cases))
    profile = provider.profile
    profile_summary = RetrievalBenchmarkProfileSummaryV1(
        profile_name=profile.profile_name,
        model_revision=profile.model_revision,
        dimension=profile.dimension,
        normalization=profile.normalization,
        distance_metric=profile.distance_metric,
        max_input_tokens=profile.max_input_tokens,
        batch_size=profile.batch_size,
        provider_location=profile.provider_location,
        data_residency=profile.data_residency,
    )
    payload: dict[str, object] = {
        "version": "retrieval-profile-benchmark.v1",
        "profile": profile_summary.model_dump(mode="json"),
        "corpus_hash": corpus.corpus_hash,
        "requested_rounds": rounds,
        "completed_rounds": completed_rounds,
        "failed_rounds": failed_rounds,
        "categories": tuple(metric.model_dump(mode="json") for metric in categories),
        "overall": overall.model_dump(mode="json"),
        "mean_latency_ms": float(mean(latencies)) if latencies else 0.0,
        "p95_latency_ms": _percentile_95(latencies),
        "consumed_input_tokens": int(getattr(provider, "consumed_input_tokens", 0)),
        "estimated_cost_usd": float(getattr(provider, "estimated_cost_usd", 0.0)),
    }
    payload["report_hash"] = canonical_retrieval_sha256(payload)
    return RetrievalProfileBenchmarkReportV1.model_validate(payload)


def _default_corpus_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "stage12_retrieval_benchmark_v2.json"
    )


def _write_report_atomically(
    report: RetrievalProfileBenchmarkReportV1,
    *,
    output_path: Path,
) -> None:
    resolved = output_path.expanduser().resolve()
    if not resolved.parent.is_dir():
        raise ValueError("retrieval_benchmark_output_parent_missing")
    temporary = resolved.with_name(f".{resolved.name}.tmp")
    temporary.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, resolved)


def main(
    argv: list[str] | None = None,
    *,
    provider_factory: NamedProviderFactory | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run the focused Stage12-D profile benchmark.",
    )
    parser.add_argument("--profile", choices=NAMED_PROFILES, required=True)
    parser.add_argument("--rounds", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument(
        "--corpus-json",
        type=Path,
        default=_default_corpus_path(),
    )
    args = parser.parse_args(argv)

    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        args.corpus_json.read_text(encoding="utf-8")
    )
    profile = get_stage12_benchmark_profile(args.profile)
    factory = provider_factory or _create_named_provider
    provider = factory(args.profile, profile)
    try:
        report = run_retrieval_profile_benchmark(
            corpus,
            provider=provider,
            rounds=args.rounds,
            top_k=20,
        )
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()
    _write_report_atomically(report, output_path=args.output_json)
    print(
        json.dumps(
            {
                "completed_rounds": report.completed_rounds,
                "failed_rounds": report.failed_rounds,
                "profile_name": report.profile.profile_name,
                "report_hash": report.report_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
