"""Default-off Stage12-B comparison between authoritative V1 and shadow V2.

Only bounded hashes, counts, normalized kinds, and stable denial codes leave this
module. V2 output is observational and is never returned as a dispatch plan.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr

from app.core.config import Settings
from app.schemas.agent_task_spec_v2 import (
    AuthorizedSchemaSnapshot,
    PlannerRequestV2,
    Sha256Hex,
    TaskSpecArtifact,
)
from app.services.agent_task_gateway import TaskPlan
from app.services.agent_task_planner_v2 import plan_task_v2


_V1_OBJECTIVE_KIND = {
    "fact": "fact_query",
    "risk": "risk_analysis",
    "daily_summary": "daily_summary",
    "record_change": "record_change",
    "task": "task_creation",
    "reminder": "reminder_request",
    "restricted_data": "restricted_request",
    "conflict": "conflict_resolution",
}
_V1_ACTION_KIND = {
    "draft_create": "record.create",
    "draft_update": "record.update",
    "task_create": "task.create",
    "reminder_request": "reminder.request",
}
_SAFE_FAILURE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")


class PlannerShadowObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["planner-shadow-observation.v1"]
    status: Literal["observed", "shadow_failed"]
    v1_plan_hash: Sha256Hex
    v2_artifact_hash: Sha256Hex | None
    schema_hash: Sha256Hex
    v1_objective_count: StrictInt
    v2_objective_count: StrictInt | None
    v1_action_count: StrictInt
    v2_action_count: StrictInt | None
    objective_kind_deltas: tuple[StrictStr, ...]
    action_kind_deltas: tuple[StrictStr, ...]
    denial_codes: tuple[StrictStr, ...]
    failure_code: StrictStr | None
    v1_dispatch_unchanged: StrictBool


PlannerShadowObserver = Callable[[PlannerShadowObservation], None]


@dataclass(frozen=True, slots=True)
class PlannerShadowRun:
    observation: PlannerShadowObservation
    task_artifact: TaskSpecArtifact | None


def planner_shadow_enabled(settings: Settings, workspace_id: UUID) -> bool:
    return settings.agent_task_planner_v2_mode == "shadow" and str(workspace_id) in set(
        settings.agent_task_planner_v2_shadow_workspace_ids
    )


def run_task_planner_shadow_with_artifact(
    v1_plan: TaskPlan,
    request: PlannerRequestV2,
    snapshot: AuthorizedSchemaSnapshot,
    *,
    observer: PlannerShadowObserver | None,
) -> PlannerShadowRun:
    if request.authorized_schema != snapshot:
        raise ValueError("planner_shadow_schema_snapshot_mismatch")
    original_nodes = v1_plan.nodes
    v1_hash = _sha256_json(asdict(v1_plan))
    v1_objective_kinds = Counter(
        _V1_OBJECTIVE_KIND.get(item.kind, "unknown") for item in v1_plan.objectives
    )
    v1_action_kinds = Counter(
        mapped
        for item in v1_plan.objectives
        if (mapped := _V1_ACTION_KIND.get(item.requested_action)) is not None
    )
    artifact: TaskSpecArtifact | None = None
    try:
        artifact = plan_task_v2(request)
        spec = artifact.task_spec
        v2_objective_kinds = Counter(item.kind for item in spec.objectives)
        v2_action_kinds = Counter(item.action_kind for item in spec.action_slots)
        denial_codes = tuple(
            sorted(
                {
                    code
                    for code in (
                        *(item.denial_reason for item in spec.objectives),
                        *(item.denial_reason for item in spec.action_slots),
                    )
                    if code is not None
                }
            )
        )
        observation = PlannerShadowObservation(
            version="planner-shadow-observation.v1",
            status="observed",
            v1_plan_hash=v1_hash,
            v2_artifact_hash=artifact.content_hash,
            schema_hash=snapshot.schema_hash,
            v1_objective_count=len(v1_plan.objectives),
            v2_objective_count=len(spec.objectives),
            v1_action_count=sum(v1_action_kinds.values()),
            v2_action_count=len(spec.action_slots),
            objective_kind_deltas=_counter_delta(
                v1_objective_kinds,
                v2_objective_kinds,
            ),
            action_kind_deltas=_counter_delta(v1_action_kinds, v2_action_kinds),
            denial_codes=denial_codes,
            failure_code=None,
            v1_dispatch_unchanged=v1_plan.nodes == original_nodes,
        )
    except Exception as exc:  # Shadow must never take authority from V1 dispatch.
        observation = PlannerShadowObservation(
            version="planner-shadow-observation.v1",
            status="shadow_failed",
            v1_plan_hash=v1_hash,
            v2_artifact_hash=None,
            schema_hash=snapshot.schema_hash,
            v1_objective_count=len(v1_plan.objectives),
            v2_objective_count=None,
            v1_action_count=sum(v1_action_kinds.values()),
            v2_action_count=None,
            objective_kind_deltas=(),
            action_kind_deltas=(),
            denial_codes=(),
            failure_code=_safe_failure_code(exc),
            v1_dispatch_unchanged=v1_plan.nodes == original_nodes,
        )
    if observer is not None:
        try:
            observer(observation)
        except Exception:
            pass
    return PlannerShadowRun(observation=observation, task_artifact=artifact)


def run_task_planner_shadow(
    v1_plan: TaskPlan,
    request: PlannerRequestV2,
    snapshot: AuthorizedSchemaSnapshot,
    *,
    observer: PlannerShadowObserver | None,
) -> PlannerShadowObservation:
    return run_task_planner_shadow_with_artifact(
        v1_plan,
        request,
        snapshot,
        observer=observer,
    ).observation


def _counter_delta(before: Counter[str], after: Counter[str]) -> tuple[str, ...]:
    values: list[str] = []
    for kind in sorted(set(before) | set(after)):
        delta = after[kind] - before[kind]
        if delta:
            values.append(f"{kind}:{delta:+d}")
    return tuple(values)


def _sha256_json(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _safe_failure_code(exc: Exception) -> str:
    value = str(exc)
    return value if _SAFE_FAILURE_CODE.fullmatch(value) else "shadow_planner_failure"


__all__ = [
    "PlannerShadowObservation",
    "PlannerShadowObserver",
    "PlannerShadowRun",
    "planner_shadow_enabled",
    "run_task_planner_shadow",
    "run_task_planner_shadow_with_artifact",
]
