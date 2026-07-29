from dataclasses import dataclass
from uuid import UUID

from app.runtime.stage08_contracts import (
    ExecutionPlan,
    ExecutionTicketState,
    ToolInvocation,
    ToolName,
)
from app.services.stage06_platform import Stage06PlatformUnitOfWork
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)


_TOOL_REQUIRED_ACTIONS: dict[ToolName, str] = {
    "record.query": "query",
    "table.summarize": "summarize",
    "contact.resolve": "contact.resolve",
    "import.preview": "import.preview",
    "tool_catalog.inspect": "tool_catalog.inspect",
    "task.create_draft": "draft_create",
    "record_change_draft.create": "draft_update",
    "notification.request": "notification.request",
}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str | None
    effective_tool_names: tuple[ToolName, ...]


def evaluate_execution_plan(
    uow: Stage06PlatformUnitOfWork,
    plan: ExecutionPlan,
) -> PolicyDecision:
    try:
        employee_id = UUID(plan.employee_id)
    except (AttributeError, TypeError, ValueError):
        return _denied("employee_not_found")
    employee = uow.get_digital_employee(employee_id)
    if employee is None:
        return _denied("employee_not_found")
    if employee.status != "active":
        return _denied("employee_inactive")
    try:
        workspace_id = UUID(plan.workspace_id)
    except (AttributeError, TypeError, ValueError):
        return _denied("workspace_mismatch")
    if employee.workspace_id != workspace_id:
        return _denied("workspace_mismatch")

    actor_user_id = _actor_user_id(plan.actor)
    if actor_user_id is None:
        return _denied("actor_invalid")
    member = next(
        (
            candidate
            for candidate in uow.list_workspace_members(workspace_id)
            if candidate.user_id == actor_user_id and candidate.status == "active"
        ),
        None,
    )
    if member is None:
        return _denied("actor_not_workspace_member")
    if not is_member_eligible_for_employee(uow, employee, actor_user_id):
        return _denied("employee_caller_scope_denied")

    if plan.state != ExecutionTicketState.planned:
        return _denied("plan_state_invalid")
    if plan.action not in _TOOL_REQUIRED_ACTIONS:
        return _denied("plan_action_invalid")
    invocations = plan.invocations
    if not isinstance(invocations, list):
        return _denied("plan_action_invalid")
    if any(not isinstance(invocation, ToolInvocation) for invocation in invocations):
        return _denied("plan_action_invalid")
    tool_names = tuple(invocation.tool_name for invocation in invocations)
    if plan.action not in tool_names:
        return _denied("plan_action_invalid")
    for tool_name in tool_names:
        required_action = _TOOL_REQUIRED_ACTIONS.get(tool_name)
        if required_action is None or required_action not in set(employee.allowed_actions):
            return _denied("tool_not_allowed_by_employee")
    if not _has_valid_budget(plan):
        return _denied("execution_budget_invalid")
    return PolicyDecision(
        allowed=True,
        reason_code=None,
        effective_tool_names=tool_names,
    )


def _actor_user_id(actor: object) -> str | None:
    if not isinstance(actor, str) or not actor.startswith("user:"):
        return None
    user_id = actor.removeprefix("user:")
    if not user_id or not user_id.strip():
        return None
    return user_id


def _has_valid_budget(plan: ExecutionPlan) -> bool:
    budget = plan.budget
    values = (
        (getattr(budget, "max_tool_calls", None), 1, 7),
        (getattr(budget, "max_wall_time_ms", None), 100, 30_000),
        (getattr(budget, "max_graph_depth", None), 1, 3),
        (getattr(budget, "max_retries", None), 0, 2),
    )
    if any(type(value) is not int or not low <= value <= high for value, low, high in values):
        return False
    if getattr(budget, "max_retrieval_chunks", None) != 0:
        return False
    return len(plan.invocations) <= budget.max_tool_calls


def _denied(reason_code: str) -> PolicyDecision:
    return PolicyDecision(
        allowed=False,
        reason_code=reason_code,
        effective_tool_names=(),
    )
