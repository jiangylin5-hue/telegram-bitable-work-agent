from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import json
from typing import Protocol

from pydantic import ValidationError

from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV2,
    GroundedAnswerProviderRequestV2,
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
from app.services.agent_model_gateway import ProviderGatewayResult
from app.services.agent_provider_validation import (
    ProviderValidationError as GatewayValidationError,
)


class _GroundedGateway(Protocol):
    def invoke(self, **kwargs: object) -> ProviderGatewayResult: ...


class GroundedAnswerProviderInvocationError(RuntimeError):
    def __init__(self, code: ProviderFailureCode) -> None:
        super().__init__(code)
        self.code = code


def _json_shape(content: str) -> tuple[str, tuple[str, ...], int, int]:
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return "invalid_json", (), 0, 0
    top_level_type = canonical_json_type(payload)
    keys = tuple(sorted(payload)) if isinstance(payload, dict) else ()
    sections = payload.get("sections") if isinstance(payload, dict) else None
    section_count = len(sections) if isinstance(sections, list) else 0
    statement_count = 0
    if isinstance(sections, list):
        for section in sections:
            statements = (
                section.get("statements") if isinstance(section, dict) else None
            )
            if isinstance(statements, list):
                statement_count += len(statements)
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
        self.failure_code: ProviderFailureCode | None = None

    def __call__(
        self, request: GroundedAnswerProviderRequestV2
    ) -> GroundedAnswerPlanV2:
        self.observations = ()
        self.diagnostics = ()
        self.failure_code = None
        diagnostics: list[ProviderResponseFingerprintV1] = []

        def validate(content: str) -> GroundedAnswerPlanV2:
            attempt = len(diagnostics) + 1
            repair = attempt > 1
            try:
                plan = GroundedAnswerPlanV2.model_validate_json(content)
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
                        "你负责撰写完整最终中文回答，而不是只排序章节。"
                        "只能使用请求中的 objective、claim、evidence、action 和 finding 句柄。"
                        "事实、数字、实体、状态和引用必须与所引用 claim 完全一致，不能编造。"
                        "每条事实、分析或建议必须给出完整 claim/evidence 引用闭包。"
                        "Action 只能说明待确认、拒绝、延后或冲突，绝不能声称已执行。"
                        "不要在可见文本中输出任何内部句柄。"
                        "仅返回符合 GroundedAnswerPlanV2 JSON Schema 的对象。"
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
            response_schema=GroundedAnswerPlanV2.model_json_schema(),
            validate=validate,
            deadline_at=self._now() + timedelta(seconds=self._deadline_seconds),
        )
        self.observations = result.observations
        if result.status != "completed" or not isinstance(
            result.payload, GroundedAnswerPlanV2
        ):
            self.failure_code = result.failure_code or "provider_schema_invalid"
            raise GroundedAnswerProviderInvocationError(self.failure_code)
        return result.payload


__all__ = [
    "GroundedAnswerProviderAdapterV2",
    "GroundedAnswerProviderInvocationError",
]
