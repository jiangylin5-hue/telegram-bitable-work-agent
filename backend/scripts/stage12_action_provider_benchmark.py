"""Run one synthetic, side-effect-free real Provider action proposal."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
from typing import Annotated, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_specialist_results import (
    ProviderFailureCode,
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


MODEL_ID = "google/gemini-2.5-flash"
EVIDENCE_ID = "syn-action-01"
ALLOWED_FIELD_KEYS = frozenset({"title", "status"})
NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ActionProviderAssignmentV1(_StrictFrozenModel):
    field_key: Literal["title", "status"]
    value: JsonValue


class ActionProviderPayloadV1(_StrictFrozenModel):
    action_kind: Literal["task.create"]
    safe_summary: NonEmptyStr = Field(max_length=240)
    assignments: tuple[ActionProviderAssignmentV1, ...] = Field(
        min_length=1, max_length=2
    )
    evidence_ids: tuple[NonEmptyStr, ...] = Field(min_length=1, max_length=1)
    confirmation_required: Literal[True]
    execution_status: Literal["not_executed"]

    @property
    def answer(self) -> str:
        """Expose only natural-language output to the shared language validator."""

        return self.safe_summary

    @model_validator(mode="after")
    def validate_assignments(self) -> "ActionProviderPayloadV1":
        keys = tuple(item.field_key for item in self.assignments)
        if len(set(keys)) != len(keys) or "title" not in keys:
            raise ValueError("provider_action_assignment_invalid")
        return self


class ActionProviderBenchmarkReportV1(_StrictFrozenModel):
    version: Literal["action-provider-benchmark.v1"]
    provider: Literal["openrouter-compatible"]
    model_id: NonEmptyStr
    profile_id: NonEmptyStr
    case_count: Literal[1]
    pass_count: StrictInt = Field(ge=0, le=1)
    failure_count: StrictInt = Field(ge=0, le=1)
    failure_code: ProviderFailureCode | None
    provider_call_count: StrictInt = Field(ge=0, le=2)
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    pre_confirmation_record_mutation_count: Literal[0]
    telegram_send_count: Literal[0]
    report_hash: Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def validate_report(self) -> "ActionProviderBenchmarkReportV1":
        if self.pass_count + self.failure_count != 1:
            raise ValueError("action_provider_case_count_invalid")
        if (self.failure_count == 0) != (self.failure_code is None):
            raise ValueError("action_provider_failure_code_invalid")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"report_hash"})
        )
        if self.report_hash != expected:
            raise ValueError("action_provider_report_hash_mismatch")
        return self


class _Gateway(Protocol):
    def invoke(self, **kwargs: object) -> ProviderGatewayResult: ...


def get_stage12_action_profile() -> ModelProfileV1:
    values: dict[str, object] = {
        "version": "model-profile.v1",
        "profile_id": "action.zh.stage12-f.v1",
        "provider": "openrouter-compatible",
        "model_id": MODEL_ID,
        "allowed_roles": ("action",),
        "supports_strict_json_schema": True,
        "response_language": "zh-Hans",
        "temperature": 0.0,
        "max_output_tokens": 800,
        "request_timeout_seconds": 25,
        "max_attempts": 2,
        "max_concurrency": 1,
        "data_policy": "permission-filtered-only",
    }
    values["content_hash"] = model_profile_sha256(values)
    return ModelProfileV1.model_validate(values)


def run_action_provider_benchmark(
    *,
    gateway: _Gateway,
    profile: ModelProfileV1,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ActionProviderBenchmarkReportV1:
    if profile.allowed_roles != ("action",) or profile.model_id != MODEL_ID:
        raise ValueError("action_provider_profile_invalid")

    def validate(content: str) -> BaseModel:
        def semantic(payload: ActionProviderPayloadV1) -> None:
            if (
                payload.action_kind != "task.create"
                or frozenset(payload.evidence_ids) != frozenset({EVIDENCE_ID})
                or not {item.field_key for item in payload.assignments}.issubset(
                    ALLOWED_FIELD_KEYS
                )
                or not payload.confirmation_required
                or payload.execution_status != "not_executed"
            ):
                raise ProviderValidationError("provider_semantic_invalid", "$")

        return parse_and_validate_provider_response(
            content,
            payload_type=ActionProviderPayloadV1,
            allowed_evidence_ids=frozenset({EVIDENCE_ID}),
            response_language="zh-Hans",
            semantic_validator=semantic,
            forbid_completion_claims=True,
        )

    result = gateway.invoke(
        role="action",
        messages=(
            {
                "role": "system",
                "content": (
                    "仅根据给定的合成授权字段和证据生成动作建议。"
                    "必须返回严格 JSON，不得声称已经写入或发送。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "objective": "为合成项目创建一条待确认任务",
                        "action_kind": "task.create",
                        "authorized_fields": ["title", "status"],
                        "evidence": {
                            "id": EVIDENCE_ID,
                            "text": "合成项目需要创建待评审任务，初始状态为待处理。",
                        },
                        "constraints": {
                            "confirmation_required": True,
                            "execution_status": "not_executed",
                        },
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ),
        response_schema=ActionProviderPayloadV1.model_json_schema(),
        validate=validate,
        deadline_at=now() + timedelta(seconds=50),
    )
    observations = result.observations
    values: dict[str, object] = {
        "version": "action-provider-benchmark.v1",
        "provider": "openrouter-compatible",
        "model_id": profile.model_id,
        "profile_id": profile.profile_id,
        "case_count": 1,
        "pass_count": 1 if result.status == "completed" else 0,
        "failure_count": 0 if result.status == "completed" else 1,
        "failure_code": result.failure_code,
        "provider_call_count": len(observations),
        "input_tokens": sum(item.input_tokens or 0 for item in observations),
        "output_tokens": sum(item.output_tokens or 0 for item in observations),
        "pre_confirmation_record_mutation_count": 0,
        "telegram_send_count": 0,
    }
    values["report_hash"] = specialist_payload_sha256(values)
    return ActionProviderBenchmarkReportV1.model_validate(values)


def _default_gateway(profile: ModelProfileV1) -> ModelGatewayV1:
    return ModelGatewayV1(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        profiles={"action": profile},
        now=lambda: datetime.now(UTC),
    )


def _write_report(report: ActionProviderBenchmarkReportV1, output: Path) -> None:
    resolved = output.expanduser().resolve()
    if not resolved.parent.is_dir():
        raise ValueError("action_provider_output_parent_missing")
    temporary = resolved.with_name(f".{resolved.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, resolved)


def main(
    argv: list[str] | None = None,
    *,
    gateway_factory: Callable[[ModelProfileV1], _Gateway] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    parser = argparse.ArgumentParser(
        description="Run the focused Stage12-F synthetic Action Provider benchmark."
    )
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    profile = get_stage12_action_profile()
    gateway = (gateway_factory or _default_gateway)(profile)
    report = run_action_provider_benchmark(
        gateway=gateway,
        profile=profile,
        now=now,
    )
    _write_report(report, args.output_json)
    return 0 if report.failure_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ActionProviderBenchmarkReportV1",
    "ActionProviderPayloadV1",
    "get_stage12_action_profile",
    "main",
    "run_action_provider_benchmark",
]
