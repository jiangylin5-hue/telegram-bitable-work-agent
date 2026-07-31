"""Default-off, allowlisted and sanitized Stage12-E observation seam."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter_ns
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

from app.core.config import Settings, STAGE12_PROVIDER_V2_BASELINE_PROFILE
from app.schemas.agent_task_spec_v2 import Sha256Hex


_SAFE_FAILURE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")


class SpecialistShadowMetricsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    handler_count: StrictInt
    typed_artifact_count: StrictInt
    claim_count: StrictInt
    valid_evidence_count: StrictInt
    provider_attempt_count: StrictInt
    provider_failure_count: StrictInt
    action_proposal_count: StrictInt
    write_count: StrictInt
    send_count: StrictInt
    comparison_hash: Sha256Hex


class SpecialistShadowObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["typed-specialists-shadow-observation.v1"]
    status: Literal["observed", "shadow_failed"]
    handler_count: StrictInt
    typed_artifact_count: StrictInt
    claim_count: StrictInt
    valid_evidence_count: StrictInt
    provider_attempt_count: StrictInt
    provider_failure_count: StrictInt
    action_proposal_count: StrictInt
    write_count: StrictInt
    send_count: StrictInt
    duration_ms: StrictInt
    comparison_hash: Sha256Hex | None
    failure_code: StrictStr | None


def typed_specialists_shadow_enabled(settings: Settings, workspace_id: UUID) -> bool:
    return (
        settings.typed_specialists_v2_mode == "shadow"
        and str(workspace_id) in set(settings.typed_specialists_v2_workspace_allowlist)
        and settings.stage12_provider_v2_profile == STAGE12_PROVIDER_V2_BASELINE_PROFILE
        and bool(settings.openrouter_api_key)
    )


def run_typed_specialists_shadow(
    *,
    settings: Settings,
    workspace_id: UUID,
    execute_pipeline: Callable[[], SpecialistShadowMetricsV1],
) -> SpecialistShadowObservationV1 | None:
    if not typed_specialists_shadow_enabled(settings, workspace_id):
        return None
    started = perf_counter_ns()
    try:
        metrics = execute_pipeline()
        if metrics.write_count != 0 or metrics.send_count != 0:
            raise ValueError("typed_specialists_shadow_side_effect_detected")
        return SpecialistShadowObservationV1(
            version="typed-specialists-shadow-observation.v1",
            status="observed",
            **metrics.model_dump(mode="python"),
            duration_ms=_elapsed_ms(started),
            failure_code=None,
        )
    except Exception as exc:
        return SpecialistShadowObservationV1(
            version="typed-specialists-shadow-observation.v1",
            status="shadow_failed",
            handler_count=0,
            typed_artifact_count=0,
            claim_count=0,
            valid_evidence_count=0,
            provider_attempt_count=0,
            provider_failure_count=1,
            action_proposal_count=0,
            write_count=0,
            send_count=0,
            duration_ms=_elapsed_ms(started),
            comparison_hash=None,
            failure_code=_safe_failure_code(exc),
        )


def _safe_failure_code(exc: Exception) -> str:
    value = getattr(exc, "code", None)
    if not isinstance(value, str):
        value = str(exc)
    return (
        value
        if _SAFE_FAILURE_CODE.fullmatch(value)
        else "typed_specialists_shadow_failure"
    )


def _elapsed_ms(started: int) -> int:
    return max(0, (perf_counter_ns() - started) // 1_000_000)


__all__ = [
    "SpecialistShadowMetricsV1",
    "SpecialistShadowObservationV1",
    "run_typed_specialists_shadow",
    "typed_specialists_shadow_enabled",
]
