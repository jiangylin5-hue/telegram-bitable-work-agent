from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from typing import Protocol

from pydantic import ValidationError

from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV3,
    GroundedAnswerProviderRequestV3,
    GroundedRenderSlotProviderRequestV1,
    GroundedRenderSlotTextV1,
    GroundedRenderSlotV1,
    GroundedSlotProviderObservationV1,
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
    validate_grounded_answer_slot,
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
GROUNDED_COMPOSER_PROFILE_ID = "composer.zh.grounded.glm-5.2.v4"


def build_isolated_grounded_slot_request(
    request: GroundedAnswerProviderRequestV3,
    slot: GroundedRenderSlotV1,
) -> GroundedRenderSlotProviderRequestV1:
    """Project one slot and only its sealed semantic closure for the provider."""

    objective_handles = set(slot.objective_handles)
    claim_handles = set((*slot.claim_handles, *slot.context_claim_handles))
    finding_handles = set(slot.finding_handles)
    action_handles = set(slot.action_handles)
    evidence_handles = set((*slot.evidence_handles, *slot.context_evidence_handles))
    values: dict[str, object] = {
        "version": "grounded-render-slot-provider-request.v1",
        "language": request.language,
        "slot": slot,
        "objectives": tuple(
            item
            for item in request.objectives
            if item.objective_handle in objective_handles
        ),
        "claims": tuple(
            item for item in request.claims if item.claim_handle in claim_handles
        ),
        "specialist_findings": tuple(
            item
            for item in request.specialist_findings
            if item.finding_handle in finding_handles
        ),
        "actions": tuple(
            item for item in request.actions if item.action_handle in action_handles
        ),
        "citations": tuple(
            item
            for item in request.citations
            if item.evidence_handle in evidence_handles
        ),
    }
    hash_values = {
        key: (
            value.model_dump(mode="json")
            if hasattr(value, "model_dump")
            else (
                tuple(
                    (
                        item.model_dump(mode="json")
                        if hasattr(item, "model_dump")
                        else item
                    )
                    for item in value
                )
                if isinstance(value, tuple)
                else value
            )
        )
        for key, value in values.items()
    }
    values["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedRenderSlotProviderRequestV1.model_validate(values)


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


def _grounded_slot_system_prompt(slot: GroundedRenderSlotV1) -> str:
    base = (
        "你只负责为后端已经密封的一个 RenderSlot 撰写中文文本。"
        "后端已经决定这个 slot 的语义和引用闭包；不得重建、修改或补充。"
        "只能填写 slot_handle 和中文 text，且 slot_handle 必须原样返回。"
        "text 必须包含至少一个中文汉字，只能使用当前 payload 内的安全内容，不能编造。"
        "text 绝不能包含任何 objective、claim、evidence、finding、action 的内部 handle。"
    )
    if slot.statement_kind in {"fact", "analysis", "recommendation"}:
        specialized = (
            "只转述 claims、specialist_findings 和 citations 中明确提供的内容；"
            "不得添加任何未出现的拉丁字母、数字或金额。"
            "不得声称已执行、已确认、已发送、已写入或已更新；"
            "不要把查询完成、分析完成或总结完成写成业务动作已经执行。"
        )
    elif slot.statement_kind == "action_status":
        specialized = (
            "优先将 action.safe_summary 忠实改写为一句中文；"
            "除 action.safe_summary 和密封的 context claims 外，"
            "不得添加任何主体、字段、状态、英文标识或数字。"
            "只能表达待确认、拒绝、延后或冲突，绝不能声称已经执行。"
        )
    else:
        specialized = (
            "text 必须写成纯中文限制说明；"
            "不得复制 objective_handle、kind、status、reason_code 等机器字段。"
            "可表述为：当前存在无法完成或降级的部分，未提供未经验证的结论。"
        )
    return (
        base
        + specialized
        + "不要输出标题、引用数组、推理过程或额外字段。"
        + "仅返回符合 GroundedRenderSlotTextV1 JSON Schema 的对象。"
    )


def _grounded_slot_response_schema(slot: GroundedRenderSlotV1) -> dict[str, object]:
    schema = GroundedRenderSlotTextV1.model_json_schema()
    properties = schema.get("properties")
    if isinstance(properties, dict):
        text_schema = properties.get("text")
        if isinstance(text_schema, dict):
            text_schema["description"] = _grounded_slot_system_prompt(slot)
    return schema


def _json_shape(content: str) -> tuple[str, tuple[str, ...], int, int]:
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return "invalid_json", (), 0, 0
    top_level_type = canonical_json_type(payload)
    keys = tuple(sorted(payload)) if isinstance(payload, dict) else ()
    slots = payload.get("slot_outputs") if isinstance(payload, dict) else None
    single_slot = (
        isinstance(payload, dict) and "slot_handle" in payload and "text" in payload
    )
    section_count = 1 if single_slot else len(slots) if isinstance(slots, list) else 0
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
    slot_handle: str,
    attempt: int,
    repair: bool,
    error_types: tuple[str, ...] = (),
    paths: tuple[str, ...] = (),
) -> ProviderResponseFingerprintV1:
    top_level_type, keys, section_count, statement_count = _json_shape(content)
    values = {
        "version": "provider-response-fingerprint.v1",
        "slot_handle": slot_handle,
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
        self.slot_observations: tuple[GroundedSlotProviderObservationV1, ...] = ()
        self.unexpected_error_types: tuple[str, ...] = ()
        self.diagnostics: tuple[ProviderResponseFingerprintV1, ...] = ()
        self.transport_diagnostics: tuple[ProviderTransportFingerprintV1, ...] = ()
        self.failure_code: ProviderFailureCode | None = None

    def __call__(
        self, request: GroundedAnswerProviderRequestV3
    ) -> GroundedAnswerPlanV3:
        self.observations = ()
        self.slot_observations = ()
        self.unexpected_error_types = ()
        self.diagnostics = ()
        self.transport_diagnostics = ()
        self.failure_code = None
        if len(request.render_slots) > 3 or any(
            not slot.required for slot in request.render_slots
        ):
            self.failure_code = "provider_schema_invalid"
            raise GroundedAnswerProviderInvocationError(self.failure_code)

        deadline_at = self._now() + timedelta(seconds=self._deadline_seconds)

        def invoke_slot(
            slot: GroundedRenderSlotV1,
        ) -> tuple[
            ProviderGatewayResult,
            tuple[ProviderResponseFingerprintV1, ...],
        ]:
            isolated_request = build_isolated_grounded_slot_request(request, slot)
            diagnostics: list[ProviderResponseFingerprintV1] = []

            def validate(content: str) -> GroundedRenderSlotTextV1:
                attempt = len(diagnostics) + 1
                repair = attempt > 1
                try:
                    output = GroundedRenderSlotTextV1.model_validate_json(content)
                except ValidationError as exc:
                    error_types, paths = _validation_details(exc)
                    diagnostics.append(
                        _fingerprint(
                            content,
                            slot_handle=slot.slot_handle,
                            attempt=attempt,
                            repair=repair,
                            error_types=error_types,
                            paths=paths,
                        )
                    )
                    raise GatewayValidationError(
                        "provider_schema_invalid", paths[0] if paths else "$"
                    ) from exc
                try:
                    validate_grounded_answer_slot(request, slot, output)
                except GroundingValidationError as exc:
                    diagnostics.append(
                        _fingerprint(
                            content,
                            slot_handle=slot.slot_handle,
                            attempt=attempt,
                            repair=repair,
                            error_types=(exc.code,),
                            paths=(exc.detail,),
                        )
                    )
                    raise GatewayValidationError(exc.code, exc.detail) from exc
                diagnostics.append(
                    _fingerprint(
                        content,
                        slot_handle=slot.slot_handle,
                        attempt=attempt,
                        repair=repair,
                    )
                )
                return output

            result = self._gateway.invoke(
                role="composer",
                messages=(
                    {
                        "role": "system",
                        "content": _grounded_slot_system_prompt(slot),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            isolated_request.model_dump(mode="json"),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    },
                ),
                response_schema=_grounded_slot_response_schema(slot),
                validate=validate,
                deadline_at=deadline_at,
                reasoning_effort="none",
            )
            return result, tuple(diagnostics)

        gathered: list[
            tuple[
                ProviderGatewayResult | None,
                tuple[ProviderResponseFingerprintV1, ...],
                ProviderFailureCode | None,
            ]
        ] = []
        unexpected_error_types: list[str] = []
        with ThreadPoolExecutor(
            max_workers=min(2, len(request.render_slots)),
            thread_name_prefix="grounded-slot",
        ) as executor:
            futures = tuple(
                executor.submit(invoke_slot, slot) for slot in request.render_slots
            )
            for slot, future in zip(request.render_slots, futures, strict=True):
                try:
                    result, diagnostics = future.result()
                except Exception as exc:  # pragma: no cover - defensive boundary
                    unexpected_error_types.append(
                        f"{slot.slot_handle}:{type(exc).__name__}"
                    )
                    gathered.append((None, (), "provider_http_error"))
                else:
                    gathered.append((result, diagnostics, result.failure_code))
        self.unexpected_error_types = tuple(unexpected_error_types)

        self.observations = tuple(
            observation
            for result, _, _ in gathered
            if result is not None
            for observation in result.observations
        )
        self.diagnostics = tuple(
            diagnostic for _, diagnostics, _ in gathered for diagnostic in diagnostics
        )
        self.transport_diagnostics = tuple(
            diagnostic
            for result, _, _ in gathered
            if result is not None
            for diagnostic in result.transport_diagnostics
        )
        slot_observations = []
        for slot, (result, _, failure) in zip(
            request.render_slots, gathered, strict=True
        ):
            completed = (
                result is not None
                and result.status == "completed"
                and isinstance(result.payload, GroundedRenderSlotTextV1)
            )
            values: dict[str, object] = {
                "version": "grounded-slot-provider-observation.v1",
                "slot_handle": slot.slot_handle,
                "status": "completed" if completed else "failed",
                "attempt_count": 0 if result is None else len(result.observations),
                "latency_ms": (
                    0
                    if result is None
                    else sum(item.latency_ms for item in result.observations)
                ),
                "failure_code": (
                    None if completed else failure or "provider_schema_invalid"
                ),
            }
            values["content_hash"] = specialist_payload_sha256(values)
            slot_observations.append(
                GroundedSlotProviderObservationV1.model_validate(values)
            )
        self.slot_observations = tuple(slot_observations)
        failed = next(
            (
                failure or "provider_schema_invalid"
                for result, _, failure in gathered
                if result is None
                or result.status != "completed"
                or not isinstance(result.payload, GroundedRenderSlotTextV1)
            ),
            None,
        )
        if failed is not None:
            self.failure_code = failed
            raise GroundedAnswerProviderInvocationError(failed)
        return GroundedAnswerPlanV3(
            slot_outputs=tuple(
                result.payload
                for result, _, _ in gathered
                if result is not None
                and isinstance(result.payload, GroundedRenderSlotTextV1)
            )
        )


__all__ = [
    "GROUNDED_COMPOSER_MODEL_ID",
    "GROUNDED_COMPOSER_PROFILE_ID",
    "GroundedAnswerProviderAdapterV2",
    "GroundedAnswerProviderInvocationError",
    "build_isolated_grounded_slot_request",
    "build_grounded_composer_profile",
]
