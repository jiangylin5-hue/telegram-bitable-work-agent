"""Run the signoff-gated Stage12 48-case x 3 real Provider campaign."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Annotated, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_specialist_results import specialist_payload_sha256
from app.services.agent_grounded_answer_provider import (
    GroundedAnswerProviderAdapterV2,
    build_grounded_composer_profile,
)
from app.services.agent_model_gateway import ModelGatewayV1
from scripts.stage06_env import load_env_file
from scripts.stage12_isolated_af_runner import (
    IsolatedAFExecutor,
    IsolatedAFRunObservationV1,
)
from scripts.stage12_quality_evaluation import (
    EvaluationCaseV2,
    build_stage12_truth_cases,
)
from scripts.stage12_real_quality_report import (
    EvaluationReportV2,
    FinalCampaignSummaryV2,
    run_v2_report,
    summarize_final_campaign,
)
from scripts.stage12_retrieval_benchmark import (
    _create_named_provider,
    get_stage12_benchmark_profile,
)
from scripts.stage12_retrieval_v2_evaluation import (
    Stage12RetrievalEvaluationReportV1,
    run_stage12_retrieval_v2_evaluation,
)
from app.schemas.retrieval_v2 import RetrievalBenchmarkCorpusV2


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
REPRESENTATIVE_P2_CASE_IDS = (
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
_GROUNDED_MODEL_ID = "z-ai/glm-5.2"
_GROUNDED_PROFILE_ID = "composer.zh.grounded.glm-5.2.v3"
_EXPECTED_RETRIEVAL_PROFILE_NAME = get_stage12_benchmark_profile(
    "openrouter-bge-m3"
).profile_name


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _Executor(Protocol):
    def __call__(self, request: dict[str, object]): ...


class ProviderRoundObservationV1(_StrictFrozenModel):
    version: Literal["final-provider-round-observation.v1"]
    round_id: Literal["round-01", "round-02", "round-03"]
    required_count: StrictInt = Field(ge=1)
    unavailable_count: StrictInt = Field(ge=0)
    attempt_count: StrictInt = Field(ge=0)
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    mean_latency_ms: StrictInt = Field(ge=0)
    p95_latency_ms: StrictInt = Field(ge=0)
    failure_counts: dict[NonEmptyStr, StrictInt]
    provider_ids: tuple[NonEmptyStr, ...]
    model_ids: tuple[NonEmptyStr, ...]
    profile_ids: tuple[NonEmptyStr, ...]
    confirmed_action_count: StrictInt = Field(ge=0)
    production_write_count: StrictInt = Field(ge=0)
    telegram_send_count: StrictInt = Field(ge=0)
    observation_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_observation(self) -> "ProviderRoundObservationV1":
        if self.unavailable_count > self.required_count:
            raise ValueError("final_provider_unavailable_count_invalid")
        for values in (self.provider_ids, self.model_ids, self.profile_ids):
            if len(set(values)) != len(values):
                raise ValueError("final_provider_identity_duplicate")
        if any(value < 0 for value in self.failure_counts.values()):
            raise ValueError("final_provider_failure_count_invalid")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"observation_hash"})
        )
        if self.observation_hash != expected:
            raise ValueError("final_provider_observation_hash_mismatch")
        return self


class FinalProviderCampaignBundleV1(_StrictFrozenModel):
    version: Literal["final-provider-campaign-bundle.v1"]
    created_at_utc: datetime
    human_gold_approval_hash: Sha256Hex
    report: EvaluationReportV2
    retrieval_rounds: tuple[
        Stage12RetrievalEvaluationReportV1,
        Stage12RetrievalEvaluationReportV1,
        Stage12RetrievalEvaluationReportV1,
    ]
    provider_rounds: tuple[
        ProviderRoundObservationV1,
        ProviderRoundObservationV1,
        ProviderRoundObservationV1,
    ]
    summary: FinalCampaignSummaryV2
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_bundle(self) -> "FinalProviderCampaignBundleV1":
        if (
            self.created_at_utc.tzinfo is None
            or self.created_at_utc.utcoffset() is None
        ):
            raise ValueError("final_campaign_created_at_timezone_required")
        if self.created_at_utc.utcoffset().total_seconds() != 0:
            raise ValueError("final_campaign_created_at_utc_required")
        if self.report.rounds != 3 or self.summary.rounds != 3:
            raise ValueError("final_campaign_round_shape_invalid")
        if (
            self.report.case_count != 48
            or len(self.report.results) != 144
            or self.summary.case_count != 48
            or self.summary.human_gold_approved_count != 48
        ):
            raise ValueError("final_campaign_case_shape_invalid")
        _validate_retrieval_rounds(self.retrieval_rounds)
        expected_round_ids = ("round-01", "round-02", "round-03")
        if tuple(item.round_id for item in self.provider_rounds) != expected_round_ids:
            raise ValueError("final_campaign_provider_round_identity_invalid")
        if any(item.required_count != 48 for item in self.provider_rounds):
            raise ValueError("final_campaign_provider_required_count_invalid")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("final_campaign_bundle_hash_mismatch")
        return self


class GroundedP2CaseResultV1(_StrictFrozenModel):
    round_id: Literal["round-01", "round-02", "round-03"]
    case_id: NonEmptyStr
    answer_source: Literal["real_provider", "deterministic_fallback"]
    provider_result_status: NonEmptyStr
    final_answer_gate_pass: StrictBool
    release_gate_pass: StrictBool
    reason_codes: tuple[NonEmptyStr, ...]


class GroundedP2CampaignV1(_StrictFrozenModel):
    version: Literal["grounded-answer-p2-campaign.v1"]
    created_at_utc: datetime
    model_id: Literal["z-ai/glm-5.2"]
    profile_id: Literal["composer.zh.grounded.glm-5.2.v3"]
    case_ids: tuple[NonEmptyStr, ...] = Field(min_length=12, max_length=12)
    case_count: Literal[12]
    rounds: Literal[3]
    results: tuple[GroundedP2CaseResultV1, ...] = Field(
        min_length=36, max_length=36
    )
    real_provider_count: StrictInt = Field(ge=0, le=36)
    final_answer_gate_pass_count: StrictInt = Field(ge=0, le=36)
    release_gate_pass_count: StrictInt = Field(ge=0, le=36)
    fallback_count: StrictInt = Field(ge=0, le=36)
    provider_attempt_count: StrictInt = Field(ge=0)
    provider_mean_latency_ms: StrictInt = Field(ge=0)
    provider_p95_latency_ms: StrictInt = Field(ge=0)
    failure_counts: dict[NonEmptyStr, StrictInt]
    unauthorized_effect_count: StrictInt = Field(ge=0)
    production_write_count: StrictInt = Field(ge=0)
    telegram_send_count: StrictInt = Field(ge=0)
    gate_pass: StrictBool
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_campaign(self) -> "GroundedP2CampaignV1":
        if self.created_at_utc.utcoffset() is None or (
            self.created_at_utc.utcoffset().total_seconds() != 0
        ):
            raise ValueError("grounded_p2_created_at_utc_required")
        if self.case_ids != REPRESENTATIVE_P2_CASE_IDS:
            raise ValueError("grounded_p2_case_identity_invalid")
        expected_results = tuple(
            (f"round-{round_number:02d}", case_id)
            for round_number in range(1, 4)
            for case_id in REPRESENTATIVE_P2_CASE_IDS
        )
        if tuple(
            (item.round_id, item.case_id) for item in self.results
        ) != expected_results:
            raise ValueError("grounded_p2_result_identity_invalid")
        expected_gate = (
            self.real_provider_count == 36
            and self.final_answer_gate_pass_count == 36
            and self.release_gate_pass_count == 36
            and self.fallback_count == 0
            and not self.failure_counts
            and self.unauthorized_effect_count == 0
            and self.production_write_count == 0
            and self.telegram_send_count == 0
        )
        if self.gate_pass != expected_gate:
            raise ValueError("grounded_p2_gate_mismatch")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("grounded_p2_hash_mismatch")
        return self


def validate_human_gold_signoff(cases: tuple[EvaluationCaseV2, ...]) -> str:
    if len(cases) != 48 or len({case.case_id for case in cases}) != 48:
        raise ValueError("final_campaign_human_gold_shape_invalid")
    if any(case.gold_audit.status != "human_approved" for case in cases):
        raise ValueError("final_campaign_human_gold_not_approved")
    payload = tuple(
        {
            "case_id": case.case_id,
            "source_fixture_hash": case.gold_audit.source_fixture_hash,
            "v2_case_hash": case.gold_audit.v2_case_hash,
            "status": case.gold_audit.status,
        }
        for case in sorted(cases, key=lambda item: item.case_id)
    )
    return sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _percentile_95(values: tuple[int, ...]) -> int:
    if not values:
        return 0
    ordered = tuple(sorted(values))
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def _validate_retrieval_rounds(
    retrieval_rounds: tuple[Stage12RetrievalEvaluationReportV1, ...],
) -> None:
    if len(retrieval_rounds) != 3 or any(
        item.profile_name != _EXPECTED_RETRIEVAL_PROFILE_NAME
        or item.requested_rounds != 1
        or item.completed_rounds + item.failed_rounds != 1
        or item.action_expansion_count != 0
        or item.record_write_count != 0
        or item.external_send_count != 0
        for item in retrieval_rounds
    ):
        raise ValueError("final_campaign_retrieval_round_invalid")


def _round_observation(
    *,
    round_id: str,
    required_count: int,
    observations: tuple[IsolatedAFRunObservationV1, ...],
) -> ProviderRoundObservationV1:
    if len(observations) != required_count:
        raise RuntimeError("final_campaign_provider_observation_count_invalid")
    execution_ids = tuple(item.execution_id for item in observations)
    if len(set(execution_ids)) != required_count:
        raise RuntimeError("final_campaign_provider_observation_identity_invalid")
    if any(item.round_id != round_id for item in observations):
        raise RuntimeError("final_campaign_provider_observation_round_invalid")
    attempts = tuple(
        attempt
        for observation in observations
        for attempt in observation.provider_attempts
    )
    unavailable_count = sum(
        not any(
            attempt.status == "completed" for attempt in observation.provider_attempts
        )
        for observation in observations
    )
    failures = Counter(
        attempt.failure_code for attempt in attempts if attempt.failure_code is not None
    )
    failures.update(
        observation.failure_code
        for observation in observations
        if observation.failure_code is not None
    )
    latencies = tuple(item.latency_ms for item in attempts)
    values = {
        "version": "final-provider-round-observation.v1",
        "round_id": round_id,
        "required_count": required_count,
        "unavailable_count": unavailable_count,
        "attempt_count": len(attempts),
        "input_tokens": sum(item.input_tokens or 0 for item in attempts),
        "output_tokens": sum(item.output_tokens or 0 for item in attempts),
        "mean_latency_ms": (
            0 if not latencies else int(sum(latencies) / len(latencies))
        ),
        "p95_latency_ms": _percentile_95(latencies),
        "failure_counts": dict(sorted(failures.items())),
        "provider_ids": tuple(sorted({item.provider for item in attempts})),
        "model_ids": tuple(sorted({item.model_id for item in attempts})),
        "profile_ids": tuple(sorted({item.profile_id for item in attempts})),
        "confirmed_action_count": sum(
            item.confirmed_action_count for item in observations
        ),
        "production_write_count": sum(
            item.production_write_count for item in observations
        ),
        "telegram_send_count": sum(item.telegram_send_count for item in observations),
    }
    values["observation_hash"] = specialist_payload_sha256(values)
    return ProviderRoundObservationV1.model_validate(values)


def execute_final_provider_campaign(
    *,
    cases: tuple[EvaluationCaseV2, ...],
    executor: _Executor,
    observations: Mapping[str, IsolatedAFRunObservationV1],
    run_retrieval_round: Callable[[int], Stage12RetrievalEvaluationReportV1],
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FinalProviderCampaignBundleV1:
    approval_hash = validate_human_gold_signoff(cases)
    retrieval_rounds = tuple(run_retrieval_round(index) for index in range(1, 4))
    _validate_retrieval_rounds(retrieval_rounds)

    def safe_execute(request: dict[str, object]):
        trace = executor(request)
        execution_id = str(request["runtime_context"]["execution_id"])
        observation = observations.get(execution_id)
        if observation is None:
            raise RuntimeError("final_campaign_observation_missing")
        if (
            observation.confirmed_action_count
            or observation.production_write_count
            or observation.telegram_send_count
            or trace.safety.unauthorized_effect_count
            or trace.safety.external_send_count
            or any(item.external_effect_count for item in trace.actions)
        ):
            raise RuntimeError("final_campaign_safety_delta_detected")
        return trace

    report = run_v2_report(
        cases=cases,
        execute=safe_execute,
        rounds=3,
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    provider_rounds = tuple(
        _round_observation(
            round_id=f"round-{index:02d}",
            required_count=len(cases),
            observations=tuple(
                item
                for item in observations.values()
                if item.round_id == f"round-{index:02d}"
            ),
        )
        for index in range(1, 4)
    )
    summary = summarize_final_campaign(
        report,
        human_gold_approved_count=48,
        retrieval_candidate_recall_at_20_by_round=tuple(
            item.recall_at_20 if item.passed else 0.0 for item in retrieval_rounds
        ),
        provider_required_count_by_round=tuple(
            item.required_count for item in provider_rounds
        ),
        provider_unavailable_count_by_round=tuple(
            item.unavailable_count for item in provider_rounds
        ),
        confirmed_action_count_by_round=tuple(
            item.confirmed_action_count for item in provider_rounds
        ),
        production_write_count_by_round=tuple(
            item.production_write_count for item in provider_rounds
        ),
        telegram_send_count_by_round=tuple(
            item.telegram_send_count for item in provider_rounds
        ),
    )
    values = {
        "version": "final-provider-campaign-bundle.v1",
        "created_at_utc": now().astimezone(UTC),
        "human_gold_approval_hash": approval_hash,
        "report": report,
        "retrieval_rounds": retrieval_rounds,
        "provider_rounds": provider_rounds,
        "summary": summary,
    }
    hash_payload = FinalProviderCampaignBundleV1.model_construct(
        **values,
        content_hash="0" * 64,
    ).model_dump(mode="json", exclude={"content_hash"})
    values["content_hash"] = specialist_payload_sha256(hash_payload)
    return FinalProviderCampaignBundleV1.model_validate(values)


def execute_grounded_p2_campaign(
    *,
    cases: tuple[EvaluationCaseV2, ...],
    executor: _Executor,
    observations: Mapping[str, IsolatedAFRunObservationV1],
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> GroundedP2CampaignV1:
    if (
        tuple(item.case_id for item in cases) != REPRESENTATIVE_P2_CASE_IDS
        or any(item.gold_audit.status != "human_approved" for item in cases)
    ):
        raise ValueError("grounded_p2_case_identity_invalid")

    def safe_execute(request: dict[str, object]):
        trace = executor(request)
        execution_id = str(request["runtime_context"]["execution_id"])
        observation = observations.get(execution_id)
        if observation is None:
            raise RuntimeError("grounded_p2_observation_missing")
        if (
            observation.confirmed_action_count
            or observation.production_write_count
            or observation.telegram_send_count
            or trace.safety.unauthorized_effect_count
            or trace.safety.external_send_count
            or any(item.external_effect_count for item in trace.actions)
        ):
            raise RuntimeError("grounded_p2_safety_delta_detected")
        return trace

    report = run_v2_report(
        cases=cases,
        execute=safe_execute,
        rounds=3,
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    observed = tuple(observations.values())
    if len(observed) != 36:
        raise RuntimeError("grounded_p2_observation_count_invalid")
    for round_number in range(1, 4):
        _round_observation(
            round_id=f"round-{round_number:02d}",
            required_count=12,
            observations=tuple(
                item
                for item in observed
                if item.round_id == f"round-{round_number:02d}"
            ),
        )

    attempts = tuple(
        attempt for observation in observed for attempt in observation.provider_attempts
    )
    if any(
        item.model_id != _GROUNDED_MODEL_ID
        or item.profile_id != _GROUNDED_PROFILE_ID
        for item in attempts
    ):
        raise RuntimeError("grounded_p2_provider_identity_invalid")
    failures = Counter(
        item.failure_code for item in attempts if item.failure_code is not None
    )
    failures.update(
        item.failure_code
        for item in observed
        if item.failure_code is not None and not item.provider_attempts
    )
    latencies = tuple(item.latency_ms for item in attempts)
    results = tuple(
        GroundedP2CaseResultV1(
            round_id=item.round_id,
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
        "version": "grounded-answer-p2-campaign.v1",
        "created_at_utc": now().astimezone(UTC),
        "model_id": _GROUNDED_MODEL_ID,
        "profile_id": _GROUNDED_PROFILE_ID,
        "case_ids": REPRESENTATIVE_P2_CASE_IDS,
        "case_count": 12,
        "rounds": 3,
        "results": results,
        "real_provider_count": sum(
            item.answer_source == "real_provider" for item in results
        ),
        "final_answer_gate_pass_count": sum(
            item.final_answer_gate_pass for item in results
        ),
        "release_gate_pass_count": sum(item.release_gate_pass for item in results),
        "fallback_count": sum(
            item.answer_source == "deterministic_fallback" for item in results
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
            item.production_write_count for item in observed
        ),
        "telegram_send_count": sum(item.telegram_send_count for item in observed),
    }
    values["gate_pass"] = (
        values["real_provider_count"] == 36
        and values["final_answer_gate_pass_count"] == 36
        and values["release_gate_pass_count"] == 36
        and values["fallback_count"] == 0
        and not values["failure_counts"]
        and values["unauthorized_effect_count"] == 0
        and values["production_write_count"] == 0
        and values["telegram_send_count"] == 0
    )
    hash_values = {
        **values,
        "results": tuple(item.model_dump(mode="json") for item in results),
    }
    values["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedP2CampaignV1.model_validate(values)


def _atomic_write(path: Path, value: str) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _render_summary(bundle: FinalProviderCampaignBundleV1) -> str:
    lines = [
        "# Stage12 Final Provider Campaign",
        "",
        f"- Release gate: `{'PASS' if bundle.summary.release_gate_pass else 'FAIL'}`",
        f"- Human Gold: `{bundle.summary.human_gold_approved_count}/48`",
        f"- Case rounds: `{bundle.report.case_count} × {bundle.report.rounds}`",
        f"- Bundle hash: `{bundle.content_hash}`",
        "",
        "## Metrics",
        "",
    ]
    for name, metric in sorted(bundle.summary.metrics.items()):
        lines.append(
            f"- {name}: mean `{metric.mean:.6f}`, worst `{metric.worst:.6f}`, "
            f"variance `{metric.population_variance:.6f}`, "
            f"gate `{'PASS' if metric.gate_pass else 'FAIL'}`"
        )
    return "\n".join(lines) + "\n"


def write_final_provider_campaign(
    bundle: FinalProviderCampaignBundleV1,
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "stage12-final-provider-campaign.json"
    markdown_path = output_dir / "stage12-final-provider-campaign.md"
    _atomic_write(json_path, bundle.model_dump_json(indent=2) + "\n")
    _atomic_write(markdown_path, _render_summary(bundle))
    return json_path, markdown_path


def write_grounded_p2_campaign(
    campaign: GroundedP2CampaignV1,
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    if output_dir.exists():
        raise FileExistsError("grounded_p2_output_exists")
    output_dir.mkdir(parents=True)
    json_path = output_dir / "stage12-grounded-answer-p2.json"
    markdown_path = output_dir / "stage12-grounded-answer-p2.md"
    markdown = "\n".join(
        (
            "# Stage12 Grounded Answer P2",
            "",
            f"- Model: `{campaign.model_id}`",
            f"- Case rounds: `{campaign.case_count} × {campaign.rounds}`",
            f"- Real Provider: `{campaign.real_provider_count}/36`",
            f"- Final-answer gate: `{campaign.final_answer_gate_pass_count}/36`",
            f"- Fallback: `{campaign.fallback_count}`",
            f"- Provider mean/p95 ms: `{campaign.provider_mean_latency_ms}` / `{campaign.provider_p95_latency_ms}`",
            f"- Gate: `{'PASS' if campaign.gate_pass else 'FAIL'}`",
            f"- Content hash: `{campaign.content_hash}`",
            "",
        )
    )
    _atomic_write(json_path, campaign.model_dump_json(indent=2) + "\n")
    _atomic_write(markdown_path, markdown)
    return json_path, markdown_path


def _default_retrieval_round(_round_number: int):
    corpus_path = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "stage12_retrieval_benchmark_v2.json"
    )
    corpus = RetrievalBenchmarkCorpusV2.model_validate_json(
        corpus_path.read_text(encoding="utf-8")
    )
    profile_name = "openrouter-bge-m3"
    profile = get_stage12_benchmark_profile(profile_name)
    provider = _create_named_provider(profile_name, profile)
    try:
        return run_stage12_retrieval_v2_evaluation(
            corpus,
            provider=provider,
            rounds=1,
        )
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--representative-p2", action="store_true")
    args = parser.parse_args(argv)

    cases = build_stage12_truth_cases()
    validate_human_gold_signoff(cases)
    if not args.env_file.is_file():
        raise RuntimeError("final_campaign_env_file_missing")
    load_env_file(args.env_file)
    composer_profile = build_grounded_composer_profile(max_attempts=2)
    clock = lambda: datetime.now(UTC)
    gateway = ModelGatewayV1(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        profiles={"composer": composer_profile},
        now=clock,
    )
    provider = GroundedAnswerProviderAdapterV2(gateway=gateway, now=clock)
    executor = IsolatedAFExecutor(composer_provider=provider)
    if args.representative_p2:
        by_id = {item.case_id: item for item in cases}
        campaign = execute_grounded_p2_campaign(
            cases=tuple(by_id[case_id] for case_id in REPRESENTATIVE_P2_CASE_IDS),
            executor=executor,
            observations=executor.observations,
            now=clock,
        )
        json_path, markdown_path = write_grounded_p2_campaign(
            campaign,
            output_dir=args.output_dir,
        )
        print(
            json.dumps(
                {
                    "gate_pass": campaign.gate_pass,
                    "content_hash": campaign.content_hash,
                    "json": str(json_path),
                    "markdown": str(markdown_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if campaign.gate_pass else 1
    bundle = execute_final_provider_campaign(
        cases=cases,
        executor=executor,
        observations=executor.observations,
        run_retrieval_round=_default_retrieval_round,
        now=clock,
    )
    json_path, markdown_path = write_final_provider_campaign(
        bundle,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "release_gate_pass": bundle.summary.release_gate_pass,
                "bundle_hash": bundle.content_hash,
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if bundle.summary.release_gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FinalProviderCampaignBundleV1",
    "GroundedP2CampaignV1",
    "ProviderRoundObservationV1",
    "REPRESENTATIVE_P2_CASE_IDS",
    "execute_final_provider_campaign",
    "execute_grounded_p2_campaign",
    "main",
    "validate_human_gold_signoff",
    "write_final_provider_campaign",
    "write_grounded_p2_campaign",
]
