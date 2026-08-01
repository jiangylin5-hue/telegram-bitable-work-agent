"""Read-only resolution of the pre-materialized isolated Stage12 workspace."""

from __future__ import annotations

from uuid import UUID

from app.schemas.agent_stage12_runtime import Stage12IsolatedWorkspaceContext
from app.services.stage06_platform import Stage06PlatformUnitOfWork


_WORKSPACE_NAME = "Stage12 Quality Architecture V2 Evaluation"
_BASE_NAME = "Stage12 Evaluation Fixture"
_TABLE_KEYS = frozenset(
    {
        "projects",
        "work_items",
        "risks",
        "tasks",
        "owners",
        "daily_metrics",
        "interactions",
    }
)
_REQUIRED_READ_ACTIONS = frozenset({"schema_inspect", "query", "summarize"})


def resolve_stage12_isolated_workspace(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    actor_user_id: str,
    digital_employee_id: UUID,
) -> Stage12IsolatedWorkspaceContext:
    workspace = uow.get_workspace(workspace_id)
    if workspace is None or workspace.status != "active":
        raise ValueError("stage12_isolated_workspace_not_found")
    if workspace.name != _WORKSPACE_NAME:
        raise ValueError("stage12_isolated_workspace_marker_mismatch")

    member = next(
        (
            item
            for item in uow.list_workspace_members(workspace_id)
            if item.user_id == actor_user_id and item.status == "active"
        ),
        None,
    )
    if member is None:
        raise ValueError("stage12_isolated_actor_unauthorized")

    bases = uow.list_bases(workspace_id)
    if len(bases) != 1:
        raise ValueError("stage12_isolated_base_ambiguous")
    base = bases[0]
    if base.status != "active" or base.name != _BASE_NAME:
        raise ValueError("stage12_isolated_base_marker_mismatch")

    tables = uow.list_tables(base.id)
    table_ids = {table.key: table.id for table in tables if table.status == "active"}
    if len(tables) != len(table_ids) or set(table_ids) != _TABLE_KEYS:
        raise ValueError("stage12_isolated_table_marker_mismatch")

    employee = uow.get_digital_employee(digital_employee_id)
    if (
        employee is None
        or employee.status != "active"
        or employee.workspace_id != workspace_id
        or employee.base_id != base.id
    ):
        raise ValueError("stage12_isolated_employee_scope_mismatch")
    try:
        accessible_table_ids = {UUID(value) for value in employee.accessible_tables}
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("stage12_isolated_employee_scope_mismatch") from exc
    if accessible_table_ids != set(table_ids.values()) or not _REQUIRED_READ_ACTIONS.issubset(
        set(employee.allowed_actions)
    ):
        raise ValueError("stage12_isolated_employee_scope_mismatch")
    if employee.access_mode == "assigned":
        granted_member_ids = {
            item.workspace_member_id
            for item in uow.list_digital_employee_member_grants(employee.id)
        }
        if member.id not in granted_member_ids:
            raise ValueError("stage12_isolated_actor_unauthorized")
    elif employee.access_mode != "workspace":
        raise ValueError("stage12_isolated_employee_scope_mismatch")

    return Stage12IsolatedWorkspaceContext(
        workspace_id=workspace_id,
        base_id=base.id,
        table_ids=table_ids,
        actor_user_id=actor_user_id,
        digital_employee_id=employee.id,
    )


__all__ = ["resolve_stage12_isolated_workspace"]
