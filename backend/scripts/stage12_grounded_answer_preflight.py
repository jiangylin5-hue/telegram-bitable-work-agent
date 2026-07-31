"""Run the bounded Stage12 Grounded Answer Provider P1 compatibility gate."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import tempfile
from typing import Annotated, Literal, Protocol

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV2,
    GroundedAnswerProviderRequestV2,
    GroundedClaimCandidateV2,
    GroundedEvidenceCandidateV2,
    GroundedObjectiveCandidateV2,
    GroundedPresentationPolicyV2,
    ProviderResponseFingerprintV1,
)
from app.schemas.agent_specialist_results import specialist_payload_sha256
from app.services.agent_grounded_answer_provider import (
    GroundedAnswerProviderAdapterV2,
    GroundedAnswerProviderInvocationError,
    build_grounded_composer_profile,
)
from app.services.agent_grounded_answer_validation import (
    ProviderValidationError,
    validate_grounded_answer_plan,
)
from app.services.agent_model_gateway import (
    ModelGatewayV1,
    ProviderTransportFingerprintV1,
)
from scripts.stage06_env import load_env_file


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
_SHAPES = (1, 2, 4, 7)
_REQUIRED_CAPABILITIES = frozenset(
    {"reasoning", "response_format", "structured_outputs"}
)


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GroundedAnswerPreflightResultV1(_StrictFrozenModel):
    round_number: StrictInt = Field(ge=1, le=3)
    claim_count: StrictInt = Field(ge=1, le=7)
    request_hash: Sha256Hex
    status: Literal["completed", "failed"]
    failure_code: StrictStr | None
    provider_attempt_count: StrictInt = Field(ge=0, le=2)
    provider_latency_ms: StrictInt = Field(ge=0)
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    diagnostic_hashes: tuple[Sha256Hex, ...]
    response_diagnostics: tuple[ProviderResponseFingerprintV1, ...]
    transport_diagnostics: tuple[ProviderTransportFingerprintV1, ...]


class GroundedAnswerPreflightReportV1(_StrictFrozenModel):
    version: Literal["grounded-answer-preflight-report.v1"]
    model_id: NonEmptyStr
    supported_parameters: tuple[NonEmptyStr, ...]
    required_count: Literal[12]
    http_completed: StrictInt = Field(ge=0, le=12)
    schema_valid: StrictInt = Field(ge=0, le=12)
    grounding_valid: StrictInt = Field(ge=0, le=12)
    answer_source_real_provider: StrictInt = Field(ge=0, le=12)
    fallback_count: Literal[0]
    raw_output_retained: Literal[0]
    failure_counts: dict[NonEmptyStr, StrictInt]
    results: tuple[GroundedAnswerPreflightResultV1, ...] = Field(
        min_length=12, max_length=12
    )
    gate_pass: StrictBool
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_report(self) -> "GroundedAnswerPreflightReportV1":
        expected_gate = (
            self.http_completed == 12
            and self.schema_valid == 12
            and self.grounding_valid == 12
            and self.answer_source_real_provider == 12
            and self.fallback_count == 0
            and self.raw_output_retained == 0
            and not self.failure_counts
        )
        if self.gate_pass != expected_gate:
            raise ValueError("grounded_preflight_gate_mismatch")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("grounded_preflight_hash_mismatch")
        return self


class _Provider(Protocol):
    observations: tuple[object, ...]
    diagnostics: tuple[object, ...]
    transport_diagnostics: tuple[object, ...]

    def __call__(
        self, request: GroundedAnswerProviderRequestV2
    ) -> GroundedAnswerPlanV2: ...


def _handle(kind: str, value: object) -> str:
    return f"{kind}:sha256:{specialist_payload_sha256({'kind': kind, 'value': value})}"


def _request(round_number: int, claim_count: int) -> GroundedAnswerProviderRequestV2:
    objectives = []
    claims = []
    citations = []
    for index in range(1, claim_count + 1):
        identity = {"round": round_number, "shape": claim_count, "index": index}
        objective_handle = _handle("objective", identity)
        claim_handle = _handle("claim", identity)
        evidence_handle = _handle("evidence", identity)
        version_handle = _handle("record-version", identity)
        objectives.append(
            GroundedObjectiveCandidateV2(
                objective_handle=objective_handle,
                kind="fact_query",
                status="completed",
                required=True,
                reason_code=None,
            )
        )
        claims.append(
            GroundedClaimCandidateV2(
                claim_handle=claim_handle,
                objective_handles=(objective_handle,),
                subject_label=f"P1 项目 {index}",
                predicate_label="未完成任务数",
                value_type="integer",
                value_text=str(index),
                qualifiers=("状态不等于已完成",),
                evidence_handles=(evidence_handle,),
                source_versions=(version_handle,),
                status="valid",
            )
        )
        citations.append(
            GroundedEvidenceCandidateV2(
                evidence_handle=evidence_handle,
                display_label=f"证据 {index}",
                source_version=version_handle,
            )
        )
    values = {
        "version": "grounded-answer-provider-request.v2",
        "language": "zh-CN",
        "query": (
            f"请基于 {claim_count} 条授权事实给出完整中文结论；"
            f"这是第 {round_number} 轮兼容性验证。"
        ),
        "objectives": tuple(objectives),
        "claims": tuple(claims),
        "specialist_findings": (),
        "actions": (),
        "citations": tuple(citations),
        "presentation_policy": GroundedPresentationPolicyV2(
            max_sections=7,
            max_statements_per_section=12,
            allowed_section_kinds=(
                "answer",
                "facts",
                "analysis",
                "risks",
                "daily",
                "actions",
                "limitations",
            ),
            allowed_statement_kinds=(
                "fact",
                "analysis",
                "recommendation",
                "action_status",
                "limitation",
            ),
            require_chinese=True,
            require_objective_coverage=True,
        ),
        "scope_hash": specialist_payload_sha256({"scope": "stage12-p1"}),
        "schema_hash": specialist_payload_sha256({"schema": "stage12-p1"}),
        "field_policy_version": "stage12-field-policy.v2",
        "field_policy_hash": specialist_payload_sha256({"policy": "stage12-p1"}),
    }
    hash_values = {
        **values,
        "objectives": tuple(item.model_dump(mode="json") for item in objectives),
        "claims": tuple(item.model_dump(mode="json") for item in claims),
        "citations": tuple(item.model_dump(mode="json") for item in citations),
        "presentation_policy": values["presentation_policy"].model_dump(mode="json"),
    }
    values["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedAnswerProviderRequestV2.model_validate(values)


def build_grounded_answer_preflight_requests() -> (
    tuple[GroundedAnswerProviderRequestV2, ...]
):
    return tuple(
        _request(round_number, shape)
        for round_number in range(1, 4)
        for shape in _SHAPES
    )


def _observation_totals(provider: _Provider) -> tuple[int, int, int, int]:
    observations = tuple(getattr(provider, "observations", ()))
    return (
        len(observations),
        sum(int(getattr(item, "latency_ms", 0)) for item in observations),
        sum(int(getattr(item, "input_tokens", 0) or 0) for item in observations),
        sum(int(getattr(item, "output_tokens", 0) or 0) for item in observations),
    )


def run_grounded_answer_preflight(
    *,
    provider: _Provider,
    load_capabilities: Callable[[], Mapping[str, object]],
) -> GroundedAnswerPreflightReportV1:
    capabilities = dict(load_capabilities())
    model_id = capabilities.get("model_id")
    supported = capabilities.get("supported_parameters")
    if (
        not isinstance(model_id, str)
        or not isinstance(supported, (tuple, list))
        or not _REQUIRED_CAPABILITIES.issubset(
            {item for item in supported if isinstance(item, str)}
        )
    ):
        raise RuntimeError("grounded_preflight_capability_missing")
    supported_parameters = tuple(sorted({str(item) for item in supported}))
    results = []
    failures: Counter[str] = Counter()
    http_completed = 0
    schema_valid = 0
    grounding_valid = 0
    real_provider = 0
    requests = build_grounded_answer_preflight_requests()
    for request in requests:
        failure_code = None
        status = "completed"
        try:
            plan = provider(request)
            http_completed += 1
            schema_valid += 1
            validate_grounded_answer_plan(request, plan)
            grounding_valid += 1
            real_provider += 1
        except GroundedAnswerProviderInvocationError as exc:
            status = "failed"
            failure_code = exc.code
            failures[exc.code] += 1
            if exc.code in {
                "provider_schema_invalid",
                "provider_grounding_invalid",
                "provider_language_invalid",
                "provider_semantic_invalid",
                "provider_citation_invalid",
            }:
                http_completed += 1
        except ProviderValidationError as exc:
            status = "failed"
            failure_code = exc.code
            failures[exc.code] += 1
            http_completed += 1
            schema_valid += 1
        attempts, latency, input_tokens, output_tokens = _observation_totals(provider)
        response_diagnostics = tuple(
            ProviderResponseFingerprintV1.model_validate(item)
            for item in getattr(provider, "diagnostics", ())
        )
        diagnostic_hashes = tuple(item.content_hash for item in response_diagnostics)
        transport_diagnostics = tuple(
            ProviderTransportFingerprintV1.model_validate(item)
            for item in getattr(provider, "transport_diagnostics", ())
        )
        shape = len(request.claims)
        round_number = (len(results) // len(_SHAPES)) + 1
        results.append(
            GroundedAnswerPreflightResultV1(
                round_number=round_number,
                claim_count=shape,
                request_hash=request.content_hash,
                status=status,
                failure_code=failure_code,
                provider_attempt_count=attempts,
                provider_latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                diagnostic_hashes=diagnostic_hashes,
                response_diagnostics=response_diagnostics,
                transport_diagnostics=transport_diagnostics,
            )
        )
    values = {
        "version": "grounded-answer-preflight-report.v1",
        "model_id": model_id,
        "supported_parameters": supported_parameters,
        "required_count": 12,
        "http_completed": http_completed,
        "schema_valid": schema_valid,
        "grounding_valid": grounding_valid,
        "answer_source_real_provider": real_provider,
        "fallback_count": 0,
        "raw_output_retained": 0,
        "failure_counts": dict(sorted(failures.items())),
        "results": tuple(results),
        "gate_pass": real_provider == 12 and not failures,
    }
    hash_values = {
        **values,
        "results": tuple(item.model_dump(mode="json") for item in results),
    }
    values["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedAnswerPreflightReportV1.model_validate(values)


def load_openrouter_model_capabilities(
    *, api_key: str, base_url: str, model_id: str
) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=20.0) as client:
        response = client.get(f"{base_url.rstrip('/')}/models", headers=headers)
        response.raise_for_status()
        payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise RuntimeError("grounded_preflight_metadata_invalid")
    model = next(
        (
            item
            for item in data
            if isinstance(item, dict) and item.get("id") == model_id
        ),
        None,
    )
    if model is None:
        raise RuntimeError("grounded_preflight_model_missing")
    supported = model.get("supported_parameters")
    if not isinstance(supported, list):
        raise RuntimeError("grounded_preflight_metadata_invalid")
    return {"model_id": model_id, "supported_parameters": tuple(supported)}


def _atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_grounded_answer_preflight(
    report: GroundedAnswerPreflightReportV1,
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("grounded_preflight_output_exists")
    output_dir.mkdir(parents=True)
    json_path = output_dir / "stage12-grounded-answer-p1-2026-07-31.json"
    markdown_path = output_dir / "stage12-grounded-answer-p1-2026-07-31.md"
    markdown = "\n".join(
        (
            "# Stage12 Grounded Answer P1",
            "",
            f"- Model: `{report.model_id}`",
            f"- HTTP completed: `{report.http_completed}/12`",
            f"- Schema valid: `{report.schema_valid}/12`",
            f"- Grounding valid: `{report.grounding_valid}/12`",
            f"- Real Provider: `{report.answer_source_real_provider}/12`",
            f"- Fallback: `{report.fallback_count}`",
            f"- Gate: `{'PASS' if report.gate_pass else 'FAIL'}`",
            "",
        )
    )
    _atomic_write(json_path, report.model_dump_json(indent=2) + "\n")
    _atomic_write(markdown_path, markdown)
    return json_path, markdown_path


def _p1_profile():
    return build_grounded_composer_profile(max_attempts=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.env_file.is_file():
        raise RuntimeError("grounded_preflight_env_file_missing")
    load_env_file(args.env_file)
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("grounded_preflight_api_key_missing")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    os.environ["AGENT_SAVE_FULL_PROMPT"] = "false"
    os.environ["AGENT_SAVE_FULL_RESPONSE"] = "false"
    profile = _p1_profile()
    clock = lambda: datetime.now(UTC)
    gateway = ModelGatewayV1(
        api_key=api_key,
        base_url=base_url,
        profiles={"composer": profile},
        now=clock,
    )
    provider = GroundedAnswerProviderAdapterV2(gateway=gateway, now=clock)
    report = run_grounded_answer_preflight(
        provider=provider,
        load_capabilities=lambda: load_openrouter_model_capabilities(
            api_key=api_key,
            base_url=base_url,
            model_id=profile.model_id,
        ),
    )
    json_path, markdown_path = write_grounded_answer_preflight(
        report, output_dir=args.output_dir
    )
    print(
        json.dumps(
            {
                "gate_pass": report.gate_pass,
                "content_hash": report.content_hash,
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "GroundedAnswerPreflightReportV1",
    "build_grounded_answer_preflight_requests",
    "load_openrouter_model_capabilities",
    "run_grounded_answer_preflight",
    "write_grounded_answer_preflight",
]
