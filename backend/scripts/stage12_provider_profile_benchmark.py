"""Run the focused Stage12-E synthetic Provider profile benchmark."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
import json
import math
import os
from pathlib import Path
from statistics import mean
from typing import Annotated, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_specialist_results import (
    ProviderFailureCode,
    ProviderRole,
    specialist_payload_sha256,
)
from app.services.agent_model_gateway import (
    ModelGatewayV1,
    ModelProfileV1,
    ProviderGatewayResult,
    model_profile_sha256,
)
from app.services.agent_provider_validation import (
    ProviderValidationError,
    parse_and_validate_provider_response,
)


BASELINE_MODEL_ID = "google/gemini-2.5-flash"
BENCHMARK_ROLES: tuple[ProviderRole, ...] = ("risk", "daily", "composer")
NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProviderProfileBenchmarkReportV1(_StrictFrozenModel):
    version: Literal["provider-profile-benchmark.v1"]
    provider: Literal["openrouter-compatible"]
    model_id: NonEmptyStr
    profile_ids: tuple[NonEmptyStr, ...]
    roles: tuple[ProviderRole, ...]
    case_count: StrictInt = Field(ge=1)
    pass_count: StrictInt = Field(ge=0)
    failure_count: StrictInt = Field(ge=0)
    failure_counts: dict[ProviderFailureCode, StrictInt]
    attempt_count: StrictInt = Field(ge=0)
    mean_latency_ms: StrictFloat = Field(ge=0)
    p95_latency_ms: StrictFloat = Field(ge=0)
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    report_hash: Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def validate_report(self) -> "ProviderProfileBenchmarkReportV1":
        if self.pass_count + self.failure_count != self.case_count:
            raise ValueError("provider_benchmark_case_count_invalid")
        if sum(self.failure_counts.values()) != self.failure_count:
            raise ValueError("provider_benchmark_failure_count_invalid")
        if len(set(self.profile_ids)) != len(self.profile_ids):
            raise ValueError("provider_benchmark_profile_duplicate")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"report_hash"})
        )
        if self.report_hash != expected:
            raise ValueError("provider_benchmark_hash_mismatch")
        return self


class _BenchmarkPayload(_StrictFrozenModel):
    answer: NonEmptyStr = Field(max_length=600)
    evidence_ids: tuple[NonEmptyStr, ...] = Field(min_length=1, max_length=2)


class _Gateway(Protocol):
    def invoke(self, **kwargs: object) -> ProviderGatewayResult: ...


class _SyntheticCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str
    role: ProviderRole
    objective: str
    evidence_id: str
    evidence_text: str


_CASES = (
    _SyntheticCase(
        case_id="provider-risk-01",
        role="risk",
        objective="只判断给定事项的风险，并引用证据编号。",
        evidence_id="syn-risk-01",
        evidence_text="合成项目甲的阻塞状态为 true，风险级别为 high。",
    ),
    _SyntheticCase(
        case_id="provider-daily-01",
        role="daily",
        objective="只概括给定聚合结果，不重新计数。",
        evidence_id="syn-daily-01",
        evidence_text="合成日报聚合：待处理 3 项，已完成 7 项。",
    ),
    _SyntheticCase(
        case_id="provider-composer-01",
        role="composer",
        objective="把给定事实写成简洁中文答复，不增加事实。",
        evidence_id="syn-composer-01",
        evidence_text="合成事实：本轮状态为 degraded，原因是 evidence_incomplete。",
    ),
)


def _profile(role: ProviderRole) -> ModelProfileV1:
    if role not in BENCHMARK_ROLES:
        raise ValueError("provider_benchmark_role_unsupported")
    values: dict[str, object] = {
        "version": "model-profile.v1",
        "profile_id": f"{role}.zh.baseline.v1",
        "provider": "openrouter-compatible",
        "model_id": BASELINE_MODEL_ID,
        "allowed_roles": (role,),
        "supports_strict_json_schema": True,
        "response_language": "zh-Hans",
        "temperature": 0.0 if role == "risk" else 0.1,
        "max_output_tokens": 800 if role == "risk" else 1000,
        "request_timeout_seconds": 25,
        "max_attempts": 2,
        "max_concurrency": 2,
        "data_policy": "permission-filtered-only",
    }
    values["content_hash"] = model_profile_sha256(values)
    return ModelProfileV1.model_validate(values)


def get_stage12_baseline_profiles() -> dict[ProviderRole, ModelProfileV1]:
    return {role: _profile(role) for role in BENCHMARK_ROLES}


def _percentile_95(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)])


def run_provider_profile_benchmark(
    *,
    gateway: _Gateway,
    profiles: Mapping[ProviderRole, ModelProfileV1],
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ProviderProfileBenchmarkReportV1:
    if tuple(profiles) != BENCHMARK_ROLES:
        raise ValueError("provider_benchmark_profiles_invalid")
    failures: Counter[ProviderFailureCode] = Counter()
    observations = []
    passed = 0
    schema = _BenchmarkPayload.model_json_schema()

    for case in _CASES:
        expected = frozenset({case.evidence_id})

        def validate(
            content: str, expected_ids: frozenset[str] = expected
        ) -> BaseModel:
            def exact_evidence(payload: _BenchmarkPayload) -> None:
                if frozenset(payload.evidence_ids) != expected_ids:
                    raise ProviderValidationError(
                        "provider_citation_invalid", "$.evidence_ids"
                    )

            return parse_and_validate_provider_response(
                content,
                payload_type=_BenchmarkPayload,
                allowed_evidence_ids=expected_ids,
                response_language="zh-Hans",
                semantic_validator=exact_evidence,
                forbid_completion_claims=case.role == "composer",
            )

        result = gateway.invoke(
            role=case.role,
            messages=(
                {
                    "role": "system",
                    "content": (
                        "仅使用给定合成证据。返回严格 JSON："
                        "answer 为简体中文，evidence_ids 只能引用给定编号。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "objective": case.objective,
                            "evidence": {
                                "id": case.evidence_id,
                                "text": case.evidence_text,
                            },
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ),
            response_schema=schema,
            validate=validate,
            deadline_at=now() + timedelta(seconds=50),
        )
        observations.extend(result.observations)
        if result.status == "completed":
            passed += 1
        else:
            failures[result.failure_code or "provider_http_error"] += 1

    latencies = [item.latency_ms for item in observations]
    input_tokens = sum(item.input_tokens or 0 for item in observations)
    output_tokens = sum(item.output_tokens or 0 for item in observations)
    profile_values = tuple(profiles[role] for role in BENCHMARK_ROLES)
    values: dict[str, object] = {
        "version": "provider-profile-benchmark.v1",
        "provider": "openrouter-compatible",
        "model_id": BASELINE_MODEL_ID,
        "profile_ids": tuple(item.profile_id for item in profile_values),
        "roles": BENCHMARK_ROLES,
        "case_count": len(_CASES),
        "pass_count": passed,
        "failure_count": len(_CASES) - passed,
        "failure_counts": dict(sorted(failures.items())),
        "attempt_count": len(observations),
        "mean_latency_ms": float(mean(latencies)) if latencies else 0.0,
        "p95_latency_ms": _percentile_95(latencies),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    values["report_hash"] = specialist_payload_sha256(values)
    return ProviderProfileBenchmarkReportV1.model_validate(values)


def _default_gateway(
    profiles: Mapping[ProviderRole, ModelProfileV1],
) -> ModelGatewayV1:
    return ModelGatewayV1(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        profiles=profiles,
        now=lambda: datetime.now(UTC),
    )


def _write_report(report: ProviderProfileBenchmarkReportV1, output: Path) -> None:
    resolved = output.expanduser().resolve()
    if not resolved.parent.is_dir():
        raise ValueError("provider_benchmark_output_parent_missing")
    temporary = resolved.with_name(f".{resolved.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, resolved)


def main(
    argv: list[str] | None = None,
    *,
    gateway_factory: (
        Callable[[Mapping[ProviderRole, ModelProfileV1]], _Gateway] | None
    ) = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    parser = argparse.ArgumentParser(
        description="Run the focused Stage12-E synthetic Provider benchmark."
    )
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    profiles = get_stage12_baseline_profiles()
    gateway = (gateway_factory or _default_gateway)(profiles)
    report = run_provider_profile_benchmark(
        gateway=gateway,
        profiles=profiles,
        now=now,
    )
    _write_report(report, args.output_json)
    return 0 if report.failure_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ProviderProfileBenchmarkReportV1",
    "get_stage12_baseline_profiles",
    "main",
    "run_provider_profile_benchmark",
]
