from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import json
from typing import Protocol

from pydantic import ValidationError

from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV3,
    GroundedAnswerProviderRequestV3,
    ProviderResponseFingerprintV1,
    canonical_json_type,
    provider_response_sha256,
)
from app.schemas.agent_specialist_results import (
    ProviderAttemptObservationV1,
    ProviderFailureCode,
    specialist_payload_sha256,
)
from app.services.agent_grounded_answer_validation import (
    ProviderValidationError as GroundingValidationError,
    validate_grounded_answer_plan,
)
from app.services.agent_model_gateway import (
    ModelProfileV1,
    ProviderGatewayResult,
    ProviderTransportFingerprintV1,
    model_profile_sha256,
)
from app.services.agent_provider_validation import (
    ProviderValidationError as GatewayValidationError,
)


class _GroundedGateway(Protocol):
    def invoke(self, **kwargs: object) -> ProviderGatewayResult: ...


class GroundedAnswerProviderInvocationError(RuntimeError):
    def __init__(self, code: ProviderFailureCode) -> None:
        super().__init__(code)
        self.code = code


GROUNDED_COMPOSER_MODEL_ID = "z-ai/glm-5.2"
GROUNDED_COMPOSER_PROFILE_ID = "composer.zh.grounded.glm-5.2.v3"


def build_grounded_composer_profile(*, max_attempts: int = 2) -> ModelProfileV1:
    values: dict[str, object] = {
        "version": "model-profile.v1",
        "profile_id": GROUNDED_COMPOSER_PROFILE_ID,
        "provider": "openrouter-compatible",
        "model_id": GROUNDED_COMPOSER_MODEL_ID,
        "allowed_roles": ("composer",),
        "supports_strict_json_schema": True,
        "response_language": "zh-Hans",
        "temperature": 0.1,
        "max_output_tokens": 2400,
        "request_timeout_seconds": 25,
        "max_attempts": max_attempts,
        "max_concurrency": 2,
        "data_policy": "permission-filtered-only",
    }
    values["content_hash"] = model_profile_sha256(values)
    return ModelProfileV1.model_validate(values)


def _json_shape(content: str) -> tuple[str, tuple[str, ...], int, int]:
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return "invalid_json", (), 0, 0
    top_level_type = canonical_json_type(payload)
    keys = tuple(sorted(payload)) if isinstance(payload, dict) else ()
    slots = payload.get("slot_outputs") if isinstance(payload, dict) else None
    section_count = len(slots) if isinstance(slots, list) else 0
    statement_count = section_count
    return top_level_type, keys, section_count, statement_count


def _validation_details(
    exc: ValidationError,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    error_types = []
    paths = []
    for item in exc.errors(include_url=False):
        error_types.append(str(item.get("type", "validation_error")))
        location = item.get("loc", ())
        paths.append("$" + "".join(f".{part}" for part in location))
    return tuple(dict.fromkeys(error_types)), tuple(dict.fromkeys(paths))


def _fingerprint(
    content: str,
    *,
    attempt: int,
    repair: bool,
    error_types: tuple[str, ...] = (),
    paths: tuple[str, ...] = (),
) -> ProviderResponseFingerprintV1:
    top_level_type, keys, section_count, statement_count = _json_shape(content)
    values = {
        "version": "provider-response-fingerprint.v1",
        "attempt": attempt,
        "top_level_type": top_level_type,
        "top_level_keys": keys,
        "section_count": section_count,
        "statement_count": statement_count,
        "response_bytes": len(content.encode("utf-8")),
        "response_sha256": provider_response_sha256(content),
        "validation_error_types": error_types,
        "validation_paths": paths,
        "repair": repair,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return ProviderResponseFingerprintV1.model_validate(values)


class GroundedAnswerProviderAdapterV2:
    def __init__(
        self,
        *,
        gateway: _GroundedGateway,
        now: Callable[[], datetime],
        deadline_seconds: int = 50,
    ) -> None:
        if deadline_seconds < 1 or deadline_seconds > 120:
            raise ValueError("grounded_answer_provider_deadline_invalid")
        self._gateway = gateway
        self._now = now
        self._deadline_seconds = deadline_seconds
        self.observations: tuple[ProviderAttemptObservationV1, ...] = ()
        self.diagnostics: tuple[ProviderResponseFingerprintV1, ...] = ()
        self.transport_diagnostics: tuple[ProviderTransportFingerprintV1, ...] = ()
        self.failure_code: ProviderFailureCode | None = None

    def __call__(
        self, request: GroundedAnswerProviderRequestV3
    ) -> GroundedAnswerPlanV3:
        self.observations = ()
        self.diagnostics = ()
        self.transport_diagnostics = ()
        self.failure_code = None
        diagnostics: list[ProviderResponseFingerprintV1] = []

        def validate(content: str) -> GroundedAnswerPlanV3:
            attempt = len(diagnostics) + 1
            repair = attempt > 1
            try:
                plan = GroundedAnswerPlanV3.model_validate_json(content)
            except ValidationError as exc:
                error_types, paths = _validation_details(exc)
                diagnostics.append(
                    _fingerprint(
                        content,
                        attempt=attempt,
                        repair=repair,
                        error_types=error_types,
                        paths=paths,
                    )
                )
                self.diagnostics = tuple(diagnostics)
                raise GatewayValidationError(
                    "provider_schema_invalid", paths[0] if paths else "$"
                ) from exc
            try:
                validate_grounded_answer_plan(request, plan)
            except GroundingValidationError as exc:
                diagnostics.append(
                    _fingerprint(
                        content,
                        attempt=attempt,
                        repair=repair,
                        error_types=(exc.code,),
                        paths=(exc.detail,),
                    )
                )
                self.diagnostics = tuple(diagnostics)
                raise GatewayValidationError(exc.code, exc.detail) from exc
            diagnostics.append(_fingerprint(content, attempt=attempt, repair=repair))
            self.diagnostics = tuple(diagnostics)
            return plan

        result = self._gateway.invoke(
            role="composer",
            messages=(
                {
                    "role": "system",
                    "content": (
                        "你负责为后端已经密封的 RenderSlot 撰写完整最终中文回答。"
                        "后端已经决定 section_kind、statement_kind 以及 objective、claim、"
                        "evidence、finding、action 的全部引用闭包；你不得重建、修改或补充它们。"
                        "每个 required slot_handle 按请求顺序恰好返回一次，"
                        "只能填写 slot_handle 和中文 text。"
                        "text 只能使用该 slot 密封闭包中的安全事实、数字、实体、状态与 Specialist 结论，"
                        "不能编造，不能输出任何 handle。"
                        "若 slot 含 finding，优先忠实表达对应 finding.safe_text；"
                        "若为 action_status，只能表达 action.safe_summary 中的待确认、拒绝、延后或冲突，"
                        "绝不能声称已经执行。"
                        "不要输出标题、引用数组、推理过程或额外字段。"
                        "仅返回符合 GroundedAnswerPlanV3 JSON Schema 的对象。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        request.model_dump(mode="json"),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ),
            response_schema=GroundedAnswerPlanV3.model_json_schema(),
            validate=validate,
            deadline_at=self._now() + timedelta(seconds=self._deadline_seconds),
            reasoning_effort="none",
        )
        self.observations = result.observations
        self.transport_diagnostics = result.transport_diagnostics
        if result.status != "completed" or not isinstance(
            result.payload, GroundedAnswerPlanV3
        ):
            self.failure_code = result.failure_code or "provider_schema_invalid"
            raise GroundedAnswerProviderInvocationError(self.failure_code)
        return result.payload


__all__ = [
    "GROUNDED_COMPOSER_MODEL_ID",
    "GROUNDED_COMPOSER_PROFILE_ID",
    "GroundedAnswerProviderAdapterV2",
    "GroundedAnswerProviderInvocationError",
    "build_grounded_composer_profile",
]
