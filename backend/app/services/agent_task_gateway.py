from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.agents.agent_capability_registry import get_capability


WORKFLOW_VERSION = "stage11.coordination.v1"

TaskIntent = Literal[
    "business_fact",
    "risk_review",
    "daily_summary",
    "controlled_action",
    "mixed",
    "memory_lookup",
    "general_advice",
]
RequestedAction = Literal[
    "read_only",
    "draft_create",
    "draft_update",
    "task_create",
    "reminder_request",
]


@dataclass(frozen=True, slots=True)
class TaskGatewayRequest:
    workspace_id: UUID
    employee_id: UUID
    actor_user_id: str
    intent: TaskIntent
    requested_action: RequestedAction
    query: str
    target_record_id: UUID | None
    idempotency_key: str
    skill_id: str | None
    allowed_capabilities: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class TaskObjective:
    objective_id: str
    kind: str
    requested_action: RequestedAction
    depends_on: tuple[str, ...]
    expected_outcome: Literal["completed", "proposed", "denied"]


@dataclass(frozen=True, slots=True)
class TaskPlanNode:
    capability_id: str
    command_type: str
    required: bool
    objective_ids: tuple[str, ...]
    depends_on_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TaskPlan:
    workflow_version: str
    objectives: tuple[TaskObjective, ...]
    nodes: tuple[TaskPlanNode, ...]
    final_landing: Literal["safe_answer", "controlled_action_review"]


_SKILL_CAPABILITIES = {
    "platform-base": frozenset({"platform.tabular.analyse"}),
    "platform-tabular-analysis": frozenset({"platform.tabular.analyse"}),
    "platform-risk-analysis": frozenset({"platform.risk.analyse"}),
    "platform-daily-summary": frozenset({"platform.daily.summarise"}),
    "platform-action-proposal": frozenset({"platform.action.propose"}),
}
_RISK_MARKERS = (
    "风险",
    "逾期",
    "阻塞",
    "异常",
    "预警",
    "情绪恶化",
    "依赖",
    "回滚",
    "评审",
    "冲突",
    "high",
    "高优先级",
    "blocked",
)
_DAILY_MARKERS = ("日报", "日结", "今日总结", "运营总结", "周报")
_TASK_MARKERS = ("创建任务", "生成任务", "新增任务", "跟进任务", "待办")
_REMINDER_MARKERS = ("提醒", "通知负责人", "催办")
_RESTRICTED_MARKERS = ("密钥", "密码", "token", "secret", "隐藏字段")
_CONFLICT_MARKERS = ("相互冲突", "同时改为", "冲突")


def build_task_plan(request: TaskGatewayRequest) -> TaskPlan:
    _validate_request(request)
    query = request.query.casefold()
    objective_specs: list[tuple[str, RequestedAction, Literal["completed", "proposed", "denied"]]] = [
        ("fact", "read_only", "completed")
    ]
    if request.intent == "risk_review" or any(value in query for value in _RISK_MARKERS):
        objective_specs.append(("risk", "read_only", "completed"))
    if request.intent == "daily_summary" or any(value in query for value in _DAILY_MARKERS):
        objective_specs.append(("daily_summary", "read_only", "completed"))
    if request.requested_action in {"draft_create", "draft_update"}:
        objective_specs.append(("record_change", request.requested_action, "proposed"))
    if request.requested_action == "task_create" or any(value in query for value in _TASK_MARKERS):
        objective_specs.append(("task", "task_create", "proposed"))
    if request.requested_action == "reminder_request" or any(
        value in query for value in _REMINDER_MARKERS
    ):
        objective_specs.append(("reminder", "reminder_request", "proposed"))
    if any(value in query for value in _RESTRICTED_MARKERS):
        objective_specs.append(("restricted_data", "read_only", "denied"))
    if any(value in query for value in _CONFLICT_MARKERS):
        objective_specs.append(("conflict", "read_only", "denied"))

    objective_specs = _deduplicate_specs(objective_specs)
    objectives: list[TaskObjective] = []
    fact_id = "objective-01"
    risk_id: str | None = None
    for index, (kind, action, outcome) in enumerate(objective_specs, start=1):
        objective_id = f"objective-{index:02d}"
        if kind == "risk":
            risk_id = objective_id
        dependencies: tuple[str, ...] = ()
        if kind in {"risk", "daily_summary"}:
            dependencies = (fact_id,)
        elif kind in {"record_change", "task", "reminder"}:
            dependencies = tuple(value for value in (fact_id, risk_id) if value is not None)
        objectives.append(
            TaskObjective(
                objective_id=objective_id,
                kind=kind,
                requested_action=action,
                depends_on=dependencies,
                expected_outcome=outcome,
            )
        )

    by_kind = {item.kind: item for item in objectives}
    requested_capabilities = ["platform.tabular.analyse"]
    if "risk" in by_kind:
        requested_capabilities.append("platform.risk.analyse")
    if "daily_summary" in by_kind:
        requested_capabilities.append("platform.daily.summarise")
    action_kinds = {"record_change", "task", "reminder"}
    if action_kinds.intersection(by_kind):
        requested_capabilities.append("platform.action.propose")

    allowed = (
        frozenset(request.allowed_capabilities)
        if request.allowed_capabilities is not None
        else frozenset(requested_capabilities)
    )
    if request.skill_id is not None:
        skill_capabilities = _SKILL_CAPABILITIES.get(request.skill_id, frozenset())
        if not skill_capabilities or not skill_capabilities.issubset(allowed):
            raise ValueError("skill_capability_not_authorized")

    nodes: list[TaskPlanNode] = []
    for capability_id in requested_capabilities:
        if capability_id not in allowed:
            continue
        definition = get_capability(capability_id)
        objective_ids = tuple(
            item.objective_id
            for item in objectives
            if _capability_serves_objective(capability_id, item.kind)
        )
        dependencies = ()
        if capability_id == "platform.action.propose":
            dependencies = tuple(
                item
                for item in (
                    "platform.tabular.analyse",
                    "platform.risk.analyse" if "risk" in by_kind else None,
                )
                if item is not None and item in allowed
            )
        nodes.append(
            TaskPlanNode(
                capability_id=capability_id,
                command_type=definition.command_type,
                required=True,
                objective_ids=objective_ids,
                depends_on_capabilities=dependencies,
            )
        )

    final_landing = (
        "controlled_action_review"
        if action_kinds.intersection(by_kind)
        else "safe_answer"
    )
    return TaskPlan(
        workflow_version=WORKFLOW_VERSION,
        objectives=tuple(objectives),
        nodes=tuple(nodes),
        final_landing=final_landing,
    )


def _validate_request(request: TaskGatewayRequest) -> None:
    if not request.query or request.query != request.query.strip() or "\x00" in request.query:
        raise ValueError("task_query_invalid")
    if not request.actor_user_id.strip() or not request.idempotency_key.strip():
        raise ValueError("task_identity_invalid")
    if request.allowed_capabilities is not None:
        for capability_id in request.allowed_capabilities:
            get_capability(capability_id)


def _deduplicate_specs(
    specs: list[tuple[str, RequestedAction, Literal["completed", "proposed", "denied"]]],
) -> list[tuple[str, RequestedAction, Literal["completed", "proposed", "denied"]]]:
    seen: set[str] = set()
    result = []
    for item in specs:
        if item[0] not in seen:
            seen.add(item[0])
            result.append(item)
    return result


def _capability_serves_objective(capability_id: str, kind: str) -> bool:
    if capability_id == "platform.tabular.analyse":
        return kind in {"fact", "risk", "daily_summary", "record_change", "task", "reminder"}
    if capability_id == "platform.risk.analyse":
        return kind == "risk"
    if capability_id == "platform.daily.summarise":
        return kind == "daily_summary"
    if capability_id == "platform.action.propose":
        return kind in {"record_change", "task", "reminder"}
    return False


__all__ = [
    "RequestedAction",
    "TaskGatewayRequest",
    "TaskIntent",
    "TaskObjective",
    "TaskPlan",
    "TaskPlanNode",
    "WORKFLOW_VERSION",
    "build_task_plan",
]
