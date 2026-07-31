"""Default-off, allowlisted and sanitized Stage12-D retrieval observation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from statistics import mean
from time import perf_counter_ns
from typing import Literal
from uuid import UUID
import re

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)

from app.core.config import Settings, STAGE12_RETRIEVAL_ACTIVE_PROFILE
from app.schemas.agent_task_spec_v2 import Sha256Hex
from app.schemas.retrieval_v2 import canonical_retrieval_sha256
from app.services.retrieval_v2_hybrid import AuthorizedRetrievalResultV2


_SAFE_FAILURE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")


class RetrievalShadowObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["retrieval-shadow-observation.v1"]
    status: Literal["observed", "shadow_failed"]
    v1_candidate_count: StrictInt
    v2_candidate_count: StrictInt
    overlap_count: StrictInt
    recall_at_20: StrictFloat
    mrr_at_20: StrictFloat
    mean_absolute_rank_delta: StrictFloat
    truncated: StrictBool
    duration_ms: StrictInt
    comparison_hash: Sha256Hex | None
    failure_code: StrictStr | None


@dataclass(frozen=True, slots=True)
class RetrievalShadowCandidateSetV1:
    v1_candidate_ids: tuple[str, ...]
    v2_result: AuthorizedRetrievalResultV2

    def __post_init__(self) -> None:
        if (
            len(self.v1_candidate_ids) > 20
            or len(set(self.v1_candidate_ids)) != len(self.v1_candidate_ids)
            or any(
                not value or value != value.strip() or "\n" in value or "\r" in value
                for value in self.v1_candidate_ids
            )
        ):
            raise ValueError("retrieval_shadow_candidate_contract_invalid")


RetrievalShadowCandidateLoader = Callable[[], RetrievalShadowCandidateSetV1]


def retrieval_v2_shadow_enabled(settings: Settings, workspace_id: UUID) -> bool:
    return (
        settings.retrieval_v2_mode == "shadow"
        and str(workspace_id) in set(settings.retrieval_v2_workspace_allowlist)
        and settings.retrieval_v2_active_profile == STAGE12_RETRIEVAL_ACTIVE_PROFILE
        and bool(settings.openrouter_api_key)
    )


def run_retrieval_v2_shadow(
    *,
    settings: Settings,
    workspace_id: UUID,
    candidate_loader: RetrievalShadowCandidateLoader,
) -> RetrievalShadowObservationV1 | None:
    if not retrieval_v2_shadow_enabled(settings, workspace_id):
        return None
    started = perf_counter_ns()
    try:
        candidate_set = candidate_loader()
        v1_ids = candidate_set.v1_candidate_ids[:20]
        v2_ids = tuple(
            item.source_id for item in candidate_set.v2_result.primary_candidates[:20]
        )
        if len(set(v2_ids)) != len(v2_ids):
            raise ValueError("retrieval_shadow_candidate_contract_invalid")
        v1_rank = {candidate_id: index for index, candidate_id in enumerate(v1_ids, 1)}
        v2_rank = {candidate_id: index for index, candidate_id in enumerate(v2_ids, 1)}
        overlap = set(v1_rank) & set(v2_rank)
        recall = 1.0 if not v1_ids else len(overlap) / len(v1_ids)
        reciprocal_rank = max(
            (1.0 / v2_rank[candidate_id] for candidate_id in overlap),
            default=0.0,
        )
        rank_delta = (
            mean(abs(v1_rank[item] - v2_rank[item]) for item in overlap)
            if overlap
            else 0.0
        )
        comparison_payload = {
            "workspace_id": workspace_id,
            "v1_candidate_ids": v1_ids,
            "v2_candidate_ids": v2_ids,
            "truncated": candidate_set.v2_result.truncated,
        }
        return RetrievalShadowObservationV1(
            version="retrieval-shadow-observation.v1",
            status="observed",
            v1_candidate_count=len(v1_ids),
            v2_candidate_count=len(v2_ids),
            overlap_count=len(overlap),
            recall_at_20=float(recall),
            mrr_at_20=float(reciprocal_rank),
            mean_absolute_rank_delta=float(rank_delta),
            truncated=candidate_set.v2_result.truncated,
            duration_ms=_elapsed_ms(started),
            comparison_hash=canonical_retrieval_sha256(comparison_payload),
            failure_code=None,
        )
    except Exception as exc:
        return RetrievalShadowObservationV1(
            version="retrieval-shadow-observation.v1",
            status="shadow_failed",
            v1_candidate_count=0,
            v2_candidate_count=0,
            overlap_count=0,
            recall_at_20=0.0,
            mrr_at_20=0.0,
            mean_absolute_rank_delta=0.0,
            truncated=False,
            duration_ms=_elapsed_ms(started),
            comparison_hash=None,
            failure_code=_safe_failure_code(exc),
        )


def _safe_failure_code(exc: Exception) -> str:
    candidate = getattr(exc, "code", None)
    if not isinstance(candidate, str):
        candidate = str(exc)
    return (
        candidate
        if _SAFE_FAILURE_CODE.fullmatch(candidate)
        else "retrieval_v2_shadow_failure"
    )


def _elapsed_ms(started: int) -> int:
    return max(0, (perf_counter_ns() - started) // 1_000_000)


__all__ = [
    "RetrievalShadowCandidateSetV1",
    "RetrievalShadowObservationV1",
    "retrieval_v2_shadow_enabled",
    "run_retrieval_v2_shadow",
]
