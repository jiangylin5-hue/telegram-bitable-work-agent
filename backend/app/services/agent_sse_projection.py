from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.models.agent_event_runtime import AgentEvent
from app.runtime.stage08_collaboration_contracts import AssistantQuerySafeView
from app.schemas.agent_event_runtime import (
    SafeRunActionEvent,
    SafeRunDoneEvent,
    SafeRunErrorEvent,
    SafeRunObjectiveEvent,
    SafeRunResultEvent,
    SafeRunStatusEvent,
    SafeRunStreamEvent,
)
from app.services.agent_event_runtime import (
    AgentEventRuntimeUnitOfWork,
    RuntimeNotFound,
    RuntimeScopeDrift,
)


_STATUS_PHASE = {
    "accepted": "accepted",
    "queued": "queued",
    "running": "running",
    "waiting_approval": "waiting_approval",
}
_ERROR_EVENT = {
    "agent.degraded": ("agent_degraded", "分析能力暂时降级"),
    "agent.failed": ("agent_failed", "分析未能完成"),
    "run.cancelled": ("run_cancelled", "任务已取消"),
    "run.timed_out": ("run_timed_out", "任务已超时"),
}


def project_safe_run_events(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run_id: UUID,
    authorization_hash: str,
    after_sequence: int,
    resolve_safe_view: Callable[[UUID], AssistantQuerySafeView] | None = None,
    resolve_objective: Callable[[UUID], object] | None = None,
    resolve_action: Callable[[UUID], object] | None = None,
) -> list[SafeRunStreamEvent]:
    if after_sequence < 0:
        raise ValueError("agent_event_cursor_invalid")
    run = uow.get_run(run_id)
    if run is None:
        raise RuntimeNotFound("agent_run_not_found")
    if run.scope_hash != authorization_hash:
        raise RuntimeScopeDrift("agent_run_scope_drift")
    return [
        projected
        for event in uow.list_events(run_id, after_sequence=after_sequence)
        if (
            projected := _project_event(
                event,
                uow=uow,
                resolve_safe_view=resolve_safe_view,
                resolve_objective=resolve_objective,
                resolve_action=resolve_action,
            )
        )
        is not None
    ]


def _project_event(
    event: AgentEvent,
    *,
    uow: AgentEventRuntimeUnitOfWork,
    resolve_safe_view: Callable[[UUID], AssistantQuerySafeView] | None,
    resolve_objective: Callable[[UUID], object] | None,
    resolve_action: Callable[[UUID], object] | None,
) -> SafeRunStreamEvent | None:
    common = {
        "run_id": event.run_id,
        "event_id": event.id,
        "sequence": event.sequence,
    }
    if event.event_type.startswith("objective."):
        if resolve_objective is None:
            raise RuntimeNotFound("agent_objective_resolver_missing")
        objective = resolve_objective(event.command_id or event.causation_id)
        if objective is None:
            raise RuntimeNotFound("agent_objective_missing")
        status = event.event_type.removeprefix("objective.")
        if status == "started":
            status = "running"
        return SafeRunObjectiveEvent(
            **common,
            event="objective",
            event_type=event.event_type,
            objective_id=objective.id,
            objective_key=objective.objective_key,
            kind=objective.kind,
            status=status,
            message=event.safe_summary or f"Objective {status}",
        )
    if event.event_type.startswith("action.") and event.command_id is not None:
        if resolve_action is None:
            raise RuntimeNotFound("agent_action_resolver_missing")
        action = resolve_action(event.command_id)
        if action is None:
            raise RuntimeNotFound("agent_action_missing")
        status = event.event_type.removeprefix("action.")
        return SafeRunActionEvent(
            **common,
            event="action",
            event_type=event.event_type,
            slot_id=action.id,
            objective_id=action.objective_run_id,
            action_kind=action.action_kind,
            status=status,
            message=event.safe_summary or f"Action {status}",
        )
    if event.event_type == "agent.completed" and event.artifact_ref is not None:
        artifact = uow.get_artifact(event.artifact_ref)
        if artifact is None:
            raise RuntimeNotFound("agent_result_artifact_missing")
        if artifact.kind != "assistant_safe_view":
            return None
        if resolve_safe_view is None:
            raise RuntimeNotFound("agent_safe_result_resolver_missing")
        return SafeRunResultEvent(
            **common,
            event="result",
            artifact_ref=event.artifact_ref,
            safe_view=resolve_safe_view(event.artifact_ref),
        )
    if event.event_type == "run.completed":
        return SafeRunDoneEvent(**common, event="done", status="completed")
    if event.event_type == "run.degraded":
        return SafeRunDoneEvent(**common, event="done", status="degraded")
    if event.event_type == "run.failed":
        return SafeRunDoneEvent(**common, event="done", status="failed")
    if event.event_type in _ERROR_EVENT:
        code, fallback = _ERROR_EVENT[event.event_type]
        return SafeRunErrorEvent(
            **common,
            event="error",
            code=code,
            message=event.safe_summary or fallback,
        )
    phase = _STATUS_PHASE.get(event.status)
    if phase is None:
        return None
    return SafeRunStatusEvent(
        **common,
        event="status",
        phase=phase,
        message=event.safe_summary or _phase_message(phase),
    )


def _phase_message(phase: str) -> str:
    return {
        "accepted": "任务已受理",
        "queued": "任务已进入队列",
        "running": "正在执行只读分析",
        "waiting_approval": "等待确认",
    }[phase]


__all__ = ["project_safe_run_events"]
