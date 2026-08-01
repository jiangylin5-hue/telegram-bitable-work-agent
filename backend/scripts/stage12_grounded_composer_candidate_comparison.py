"""Compare two fixed Stage12 Grounded Composer candidates on real Cases."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

from app.schemas.agent_specialist_results import specialist_payload_sha256
from app.services.agent_grounded_answer_provider import (
    GroundedAnswerProviderAdapterV2,
    build_grounded_composer_profile,
)
from app.services.agent_model_gateway import (
    ModelGatewayV1,
    ModelProfileV1,
    model_profile_sha256,
)
from scripts.stage06_env import load_env_file
from scripts.stage12_isolated_af_runner import IsolatedAFExecutor
from scripts.stage12_quality_evaluation import EvaluationCaseV2, build_stage12_truth_cases
from scripts.stage12_real_quality_report import run_v2_report


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]

REPRESENTATIVE_CASE_IDS = (
    "join_01",
    "join_07",
    "risk_02",
    "daily_03",
    "draft_02",
    "task_01",
    "reminder_01",
    "permission_01",
    "permission_04",
    "fault_01",
    "mixed_02",
    "mixed_08",
)
CANDIDATE_MODEL_IDS = (
    "bytedance-seed/seed-2.0-lite",
    "z-ai/glm-5.2",
)


class _Provider(Protocol):
    observations: tuple[object, ...]

    def __call__(self, request: object): ...


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CandidateCaseResultV1(_StrictFrozenModel):
    case_id: NonEmptyStr
    answer_source: Literal["real_provider", "deterministic_fallback"]
    provider_result_status: NonEmptyStr
    final_answer_gate_pass: StrictBool
    release_gate_pass: StrictBool
    reason_codes: tuple[NonEmptyStr, ...]


class CandidateRunResultV1(_StrictFrozenModel):
    version: Literal["grounded-composer-candidate-run.v1"]
    model_id: NonEmptyStr
    case_count: Literal[12]
    cases: tuple[CandidateCaseResultV1, ...] = Field(min_length=12, max_length=12)
    real_provider_count: StrictInt = Field(ge=0, le=12)
    final_answer_gate_pass_count: StrictInt = Field(ge=0, le=12)
    release_gate_pass_count: StrictInt = Field(ge=0, le=12)
    fallback_count: StrictInt = Field(ge=0, le=12)
    provider_attempt_count: StrictInt = Field(ge=0)
    provider_mean_latency_ms: StrictInt = Field(ge=0)
    provider_p95_latency_ms: StrictInt = Field(ge=0)
    failure_counts: dict[NonEmptyStr, StrictInt]
    unauthorized_effect_count: StrictInt = Field(ge=0)
    production_write_count: StrictInt = Field(ge=0)
    telegram_send_count: StrictInt = Field(ge=0)
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_run(self) -> "CandidateRunResultV1":
        if tuple(item.case_id for item in self.cases) != REPRESENTATIVE_CASE_IDS:
            raise ValueError("candidate_comparison_case_identity_invalid")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_comparison_run_hash_mismatch")
        return self


class CandidateComparisonV1(_StrictFrozenModel):
    version: Literal["grounded-composer-candidate-comparison.v1"]
    created_at_utc: datetime
    selection_status: Literal["winner", "inconclusive"]
    winner_model_id: NonEmptyStr | None
    selection_basis: Literal["quality_then_reliability_then_latency"]
    runs: tuple[CandidateRunResultV1, CandidateRunResultV1]
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_comparison(self) -> "CandidateComparisonV1":
        if self.created_at_utc.utcoffset() is None or self.created_at_utc.utcoffset().total_seconds() != 0:
            raise ValueError("candidate_comparison_created_at_utc_required")
        if tuple(item.model_id for item in self.runs) != CANDIDATE_MODEL_IDS:
            raise ValueError("candidate_comparison_model_identity_invalid")
        if (self.selection_status == "winner") != (self.winner_model_id is not None):
            raise ValueError("candidate_comparison_selection_invalid")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_comparison_hash_mismatch")
        return self


def _percentile_95(values: tuple[int, ...]) -> int:
    if not values:
        return 0
    ordered = tuple(sorted(values))
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def run_candidate_model(
    *,
    model_id: str,
    cases: Sequence[EvaluationCaseV2],
    provider: _Provider,
) -> CandidateRunResultV1:
    if model_id not in CANDIDATE_MODEL_IDS:
        raise ValueError("candidate_comparison_model_unknown")
    cases = tuple(cases)
    if (
        tuple(item.case_id for item in cases) != REPRESENTATIVE_CASE_IDS
        or any(item.gold_audit.status != "human_approved" for item in cases)
    ):
        raise ValueError("candidate_comparison_case_identity_invalid")

    executor = IsolatedAFExecutor(composer_provider=provider)

    def safe_execute(request: dict[str, object]):
        trace = executor(request)
        execution_id = str(request["runtime_context"]["execution_id"])
        observation = executor.observations.get(execution_id)
        if observation is None:
            raise RuntimeError("candidate_comparison_observation_missing")
        if (
            observation.confirmed_action_count
            or observation.production_write_count
            or observation.telegram_send_count
            or trace.safety.unauthorized_effect_count
            or trace.safety.external_send_count
            or any(item.external_effect_count for item in trace.actions)
        ):
            raise RuntimeError("candidate_comparison_safety_delta_detected")
        return trace

    report = run_v2_report(
        cases=cases,
        execute=safe_execute,
        rounds=1,
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    observations = tuple(executor.observations.values())
    attempts = tuple(
        attempt for observation in observations for attempt in observation.provider_attempts
    )
    if len(observations) != 12 or any(
        attempt.model_id != model_id for attempt in attempts
    ):
        raise RuntimeError("candidate_comparison_provider_identity_invalid")
    latencies = tuple(item.latency_ms for item in attempts)
    failures = Counter(
        item.failure_code for item in attempts if item.failure_code is not None
    )
    failures.update(
        item.failure_code for item in observations if item.failure_code is not None
    )
    case_results = tuple(
        CandidateCaseResultV1(
            case_id=item.case_id,
            answer_source=item.trace.answer.answer_source,
            provider_result_status=item.trace.answer.provider_result_status,
            final_answer_gate_pass=item.score.final_answer.gate_pass,
            release_gate_pass=item.score.release_gate_pass,
            reason_codes=item.score.final_answer.reason_codes,
        )
        for item in report.results
    )
    values = {
        "version": "grounded-composer-candidate-run.v1",
        "model_id": model_id,
        "case_count": 12,
        "cases": case_results,
        "real_provider_count": sum(
            item.answer_source == "real_provider" for item in case_results
        ),
        "final_answer_gate_pass_count": sum(
            item.final_answer_gate_pass for item in case_results
        ),
        "release_gate_pass_count": sum(item.release_gate_pass for item in case_results),
        "fallback_count": sum(
            item.answer_source == "deterministic_fallback" for item in case_results
        ),
        "provider_attempt_count": len(attempts),
        "provider_mean_latency_ms": (
            0 if not latencies else int(sum(latencies) / len(latencies))
        ),
        "provider_p95_latency_ms": _percentile_95(latencies),
        "failure_counts": dict(sorted(failures.items())),
        "unauthorized_effect_count": sum(
            item.trace.safety.unauthorized_effect_count for item in report.results
        ),
        "production_write_count": sum(
            item.production_write_count for item in observations
        ),
        "telegram_send_count": sum(item.telegram_send_count for item in observations),
    }
    hash_payload = {
        **values,
        "cases": tuple(item.model_dump(mode="json") for item in case_results),
    }
    values["content_hash"] = specialist_payload_sha256(hash_payload)
    return CandidateRunResultV1.model_validate(values)


def _eligible(item: CandidateRunResultV1) -> bool:
    return (
        item.real_provider_count == 12
        and item.final_answer_gate_pass_count == 12
        and item.fallback_count == 0
        and not item.failure_counts
        and item.unauthorized_effect_count == 0
        and item.production_write_count == 0
        and item.telegram_send_count == 0
    )


def compare_candidate_runs(
    runs: tuple[CandidateRunResultV1, CandidateRunResultV1],
    *,
    now: datetime | None = None,
) -> CandidateComparisonV1:
    if tuple(item.model_id for item in runs) != CANDIDATE_MODEL_IDS:
        raise ValueError("candidate_comparison_model_identity_invalid")
    eligible = tuple(item for item in runs if _eligible(item))
    winner = None
    if eligible:
        winner = max(
            eligible,
            key=lambda item: (
                item.final_answer_gate_pass_count,
                item.real_provider_count,
                -item.fallback_count,
                -sum(item.failure_counts.values()),
                -item.provider_p95_latency_ms,
                -item.provider_mean_latency_ms,
            ),
        )
    values = {
        "version": "grounded-composer-candidate-comparison.v1",
        "created_at_utc": (now or datetime.now(UTC)).astimezone(UTC),
        "selection_status": "winner" if winner is not None else "inconclusive",
        "winner_model_id": None if winner is None else winner.model_id,
        "selection_basis": "quality_then_reliability_then_latency",
        "runs": runs,
    }
    hash_payload = CandidateComparisonV1.model_construct(
        **values,
        content_hash="0" * 64,
    ).model_dump(mode="json", exclude={"content_hash"})
    values["content_hash"] = specialist_payload_sha256(hash_payload)
    return CandidateComparisonV1.model_validate(values)


def _atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_candidate_comparison(
    comparison: CandidateComparisonV1,
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("candidate_comparison_output_exists")
    output_dir.mkdir(parents=True)
    json_path = output_dir / "stage12-grounded-composer-candidate-comparison.json"
    markdown_path = output_dir / "stage12-grounded-composer-candidate-comparison.md"
    lines = [
        "# Stage12 Grounded Composer Candidate Comparison",
        "",
        f"- Selection: `{comparison.selection_status}`",
        f"- Winner: `{comparison.winner_model_id or 'none'}`",
        f"- Content hash: `{comparison.content_hash}`",
        "",
    ]
    for run in comparison.runs:
        lines.extend(
            (
                f"## {run.model_id}",
                "",
                f"- Real Provider: `{run.real_provider_count}/12`",
                f"- Final answer gate: `{run.final_answer_gate_pass_count}/12`",
                f"- Fallback: `{run.fallback_count}`",
                f"- Provider mean/p95 ms: `{run.provider_mean_latency_ms}` / `{run.provider_p95_latency_ms}`",
                f"- Failures: `{json.dumps(run.failure_counts, sort_keys=True)}`",
                "",
            )
        )
    _atomic_write(json_path, comparison.model_dump_json(indent=2) + "\n")
    _atomic_write(markdown_path, "\n".join(lines))
    return json_path, markdown_path


def build_candidate_profile(model_id: str) -> ModelProfileV1:
    values = build_grounded_composer_profile(max_attempts=2).model_dump(mode="python")
    values["model_id"] = model_id
    values["profile_id"] = f"candidate.{model_id.replace('/', '.')}"
    values["content_hash"] = model_profile_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    return ModelProfileV1.model_validate(values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.env_file.is_file():
        raise RuntimeError("candidate_comparison_env_file_missing")
    load_env_file(args.env_file)
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}
    cases = tuple(by_id[case_id] for case_id in REPRESENTATIVE_CASE_IDS)
    clock = lambda: datetime.now(UTC)
    runs = []
    for model_id in CANDIDATE_MODEL_IDS:
        gateway = ModelGatewayV1(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            profiles={"composer": build_candidate_profile(model_id)},
            now=clock,
        )
        provider = GroundedAnswerProviderAdapterV2(gateway=gateway, now=clock)
        runs.append(run_candidate_model(model_id=model_id, cases=cases, provider=provider))
    comparison = compare_candidate_runs(tuple(runs), now=clock())
    json_path, markdown_path = write_candidate_comparison(
        comparison, output_dir=args.output_dir
    )
    print(
        json.dumps(
            {
                "selection_status": comparison.selection_status,
                "winner_model_id": comparison.winner_model_id,
                "content_hash": comparison.content_hash,
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if comparison.selection_status == "winner" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CANDIDATE_MODEL_IDS",
    "REPRESENTATIVE_CASE_IDS",
    "CandidateComparisonV1",
    "CandidateRunResultV1",
    "build_candidate_profile",
    "compare_candidate_runs",
    "run_candidate_model",
    "write_candidate_comparison",
]
