"""Read Stage11 durable evidence into the Stage12 Evaluation V2 trace contract.

The adapter is intentionally conservative: Stage11 safe-view citations and answer
text are presentation data, not candidate/evidence traces. Missing typed evidence
therefore remains ``not_observed``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from app.services.agent_event_runtime import AgentEventRuntimeUnitOfWork
from scripts.stage12_quality_evaluation import (
    PermissionOutcome,
    ProviderTrace,
    RuntimeActionTrace,
    RuntimeAnswerTrace,
    RuntimeDurabilityTrace,
    RuntimeLatencyTrace,
    RuntimeQueryTrace,
    RuntimeRetrievalTrace,
    RuntimeSafetyTrace,
    RuntimeTraceV2,
)


_TERMINAL_STATUSES = {
    "completed",
    "degraded",
    "failed",
    "cancelled",
    "timed_out",
}


def _sum_metric(events: list[Any], key: str) -> int:
    total = 0
    for event in events:
        value = (event.metrics_json or {}).get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            total += value
    return total


def _latency_segments(events: list[Any]) -> dict[str, int]:
    values: dict[str, int] = {}
    for event in events:
        for key, value in (event.metrics_json or {}).items():
            if (
                isinstance(key, str)
                and key.endswith("_ms")
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
            ):
                name = key.removesuffix("_ms")
                values[name] = values.get(name, 0) + value
    return values or {"unobserved": 0}


def collect_stage11_runtime_trace(
    run_id: UUID,
    *,
    uow: AgentEventRuntimeUnitOfWork,
    case_id: str,
    round_id: str,
    permission_outcome: PermissionOutcome,
    resolve_safe_view: Callable[[UUID], Mapping[str, object] | None],
    provider: ProviderTrace | None = None,
    action_traces: tuple[RuntimeActionTrace, ...] = (),
) -> RuntimeTraceV2:
    run = uow.get_run(run_id)
    if run is None:
        raise ValueError("evaluation_stage11_run_not_found")
    events = uow.list_events(run_id)
    checkpoints = uow.list_checkpoints(run_id)

    safe_view: Mapping[str, object] | None = None
    if run.safe_result_ref is not None:
        artifact = uow.get_artifact(run.safe_result_ref)
        if (
            artifact is not None
            and artifact.kind == "assistant_safe_view"
            and artifact.validation_status == "validated"
        ):
            safe_view = resolve_safe_view(artifact.id)
    answer_value = safe_view.get("answer") if safe_view is not None else None
    answer_observed = isinstance(answer_value, str)

    unauthorized_effect_count = _sum_metric(events, "unauthorized_effect_count")
    external_send_count = _sum_metric(events, "external_send_count")
    duplicate_effect_count = _sum_metric(events, "duplicate_effect_count")
    recovered = any(
        "recover" in checkpoint.node_key or "resume" in checkpoint.node_key
        for checkpoint in checkpoints
    )

    return RuntimeTraceV2(
        version="runtime-trace.v2",
        case_id=case_id,
        round_id=round_id,
        provider=provider,
        planner=None,
        specialists=(),
        query=RuntimeQueryTrace(
            observation_status="not_observed",
            result_record_ids=(),
            evidence_record_ids=(),
            predicates=(),
            relation_paths=(),
            aggregates=(),
            facts=(),
            complete=False,
        ),
        retrieval=RuntimeRetrievalTrace(
            observation_status="not_observed",
            candidate_record_ids=(),
            selected_evidence_record_ids=(),
            candidate_table_by_record={},
            relation_paths=(),
            complete=False,
        ),
        answer=RuntimeAnswerTrace(
            observation_status="observed" if answer_observed else "not_observed",
            rendered_answer=answer_value if isinstance(answer_value, str) else "",
            claims=(),
            answer_source="deterministic_fallback",
            provider_result_status="transport_failed",
        ),
        actions=action_traces,
        safety=RuntimeSafetyTrace(
            permission_outcome=permission_outcome,
            unauthorized_effect_count=unauthorized_effect_count,
            external_send_count=external_send_count,
        ),
        durability=RuntimeDurabilityTrace(
            terminal=run.status in _TERMINAL_STATUSES,
            recovery_expectation="required" if recovered else "not_applicable",
            recovered=recovered,
            idempotent=bool(run.idempotency_key_hash) and duplicate_effect_count == 0,
            duplicate_effect_count=duplicate_effect_count,
        ),
        latency=RuntimeLatencyTrace(segments_ms=_latency_segments(events)),
    )


__all__ = ["collect_stage11_runtime_trace"]
