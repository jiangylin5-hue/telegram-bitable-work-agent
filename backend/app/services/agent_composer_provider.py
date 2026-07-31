from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import json
from typing import Protocol

from pydantic import ValidationError

from app.schemas.agent_specialist_results import (
    ProviderAttemptObservationV1,
    ProviderFailureCode,
)
from app.services.agent_composer_v2 import (
    ComposerSectionOrderingPlanV1,
    ComposerSectionOrderingRequestV1,
)
from app.services.agent_model_gateway import ProviderGatewayResult
from app.services.agent_provider_validation import ProviderValidationError


class _ComposerGateway(Protocol):
    def invoke(self, **kwargs: object) -> ProviderGatewayResult: ...


class ComposerProviderInvocationError(RuntimeError):
    def __init__(self, code: ProviderFailureCode) -> None:
        super().__init__(code)
        self.code = code


_SEMANTIC_MODEL_ERRORS = {
    "composer_section_handle_invalid",
    "composer_section_handle_duplicate",
    "composer_section_connector_map_invalid",
    "composer_section_connector_position_invalid",
}


def _model_failure_code(exc: ValidationError) -> ProviderFailureCode:
    messages = {str(item.get("ctx", {}).get("error", "")) for item in exc.errors()}
    if any(code in message for code in _SEMANTIC_MODEL_ERRORS for message in messages):
        return "provider_semantic_invalid"
    return "provider_schema_invalid"


def _validate_ordering_plan(
    request: ComposerSectionOrderingRequestV1,
    plan: ComposerSectionOrderingPlanV1,
) -> None:
    expected = tuple(item.section_handle for item in request.candidates)
    ordered = plan.ordered_section_handles
    if len(ordered) != len(expected) or len(set(ordered)) != len(expected):
        raise ProviderValidationError(
            "provider_semantic_invalid", "$.ordered_section_handles"
        )
    if set(ordered) != set(expected):
        raise ProviderValidationError(
            "provider_semantic_invalid", "$.ordered_section_handles"
        )
    if set(plan.connector_by_handle) != set(expected):
        raise ProviderValidationError(
            "provider_semantic_invalid", "$.connector_by_handle"
        )
    candidate_by_handle = {item.section_handle: item for item in request.candidates}
    for rank, handle in enumerate(ordered):
        connector = plan.connector_by_handle[handle]
        if connector not in candidate_by_handle[handle].allowed_connector_codes:
            raise ProviderValidationError(
                "provider_semantic_invalid", f"$.connector_by_handle.{handle}"
            )
        if (rank == 0 and connector != "direct") or (
            rank > 0 and connector == "direct"
        ):
            raise ProviderValidationError(
                "provider_semantic_invalid", f"$.connector_by_handle.{handle}"
            )


class ComposerProviderAdapterV1:
    def __init__(
        self,
        *,
        gateway: _ComposerGateway,
        now: Callable[[], datetime],
        deadline_seconds: int = 50,
    ) -> None:
        if deadline_seconds < 1 or deadline_seconds > 120:
            raise ValueError("composer_provider_deadline_invalid")
        self._gateway = gateway
        self._now = now
        self._deadline_seconds = deadline_seconds
        self.observations: tuple[ProviderAttemptObservationV1, ...] = ()
        self.failure_code: ProviderFailureCode | None = None

    def __call__(
        self, request: ComposerSectionOrderingRequestV1
    ) -> ComposerSectionOrderingPlanV1:
        self.observations = ()
        self.failure_code = None

        def validate(content: str) -> ComposerSectionOrderingPlanV1:
            try:
                plan = ComposerSectionOrderingPlanV1.model_validate_json(content)
            except ValidationError as exc:
                code = _model_failure_code(exc)
                path = (
                    "$.ordered_section_handles"
                    if code == "provider_semantic_invalid"
                    else "$"
                )
                raise ProviderValidationError(code, path) from exc
            _validate_ordering_plan(request, plan)
            return plan

        try:
            result = self._gateway.invoke(
                role="composer",
                messages=(
                    {
                        "role": "system",
                        "content": (
                            "你只规划最终回答的章节顺序和连接方式。"
                            "只能重排提供的 section_handle，不能遗漏、重复或新增。"
                            "只能选择候选项提供的 connector；第一项必须是 direct，"
                            "后续项不得是 direct。不得生成任何事实、解释或新标识。"
                            "仅返回符合 JSON Schema 的 ComposerSectionOrderingPlanV1。"
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
                response_schema=ComposerSectionOrderingPlanV1.model_json_schema(),
                validate=validate,
                deadline_at=self._now() + timedelta(seconds=self._deadline_seconds),
            )
        except ProviderValidationError as exc:
            self.failure_code = exc.code
            raise ComposerProviderInvocationError(exc.code) from exc
        self.observations = result.observations
        if result.status != "completed" or not isinstance(
            result.payload, ComposerSectionOrderingPlanV1
        ):
            self.failure_code = result.failure_code or "provider_semantic_invalid"
            raise ComposerProviderInvocationError(self.failure_code)
        return result.payload


__all__ = [
    "ComposerProviderAdapterV1",
    "ComposerProviderInvocationError",
]
