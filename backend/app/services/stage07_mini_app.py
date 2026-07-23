from typing import Any
from uuid import UUID

from app.services.stage06_authorization import (
    action_allowed_for_role,
    authorize_workspace_action,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    read_record_for_actor,
)
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)


def get_mini_app_bootstrap(
    uow: Stage06PlatformUnitOfWork,
    identity: Stage06RequestIdentity,
) -> dict[str, Any]:
    workspaces = []
    for member in uow.list_workspace_members_for_user(identity.user_id):
        if member.status != "active":
            continue
        workspace = uow.get_workspace(member.workspace_id)
        if workspace is None or workspace.status != "active":
            continue
        if not action_allowed_for_role(member.role, "workspace.read"):
            continue
        workspaces.append(
            {
                "id": str(workspace.id),
                "name": workspace.name,
                "slug": workspace.slug,
                "role": member.role,
                "capabilities": _workspace_capabilities(member.role),
            }
        )
    return {
        "identity": {"user_id": identity.user_id, "source": identity.source},
        "workspaces": sorted(workspaces, key=lambda workspace: workspace["name"]),
    }


def get_workspace_home(
    uow: Stage06PlatformUnitOfWork,
    identity: Stage06RequestIdentity,
    workspace_id: UUID,
) -> dict[str, Any]:
    actor = authorize_workspace_action(uow, identity, workspace_id, "workspace.read")
    can_read_bases = action_allowed_for_role(actor.role, "base.read")
    bases = [
        base
        for base in uow.list_bases(workspace_id)
        if base.status == "active" and can_read_bases
    ]
    queue = []
    if action_allowed_for_role(actor.role, "record_change_draft.read"):
        for base in bases:
            for draft in uow.list_record_change_drafts(base.id):
                if draft.status != "pending_confirmation":
                    continue
                queue.append(
                    {
                        "id": str(draft.id),
                        "kind": "record_change_draft",
                        "title": "待确认变更",
                        "status": draft.status,
                        "destination": {
                            "base_id": str(base.id),
                            "draft_id": str(draft.id),
                        },
                        "action_availability": {
                            "can_confirm": action_allowed_for_role(
                                actor.role,
                                "record_change_draft.confirm",
                            ),
                            "can_reject": action_allowed_for_role(
                                actor.role,
                                "record_change_draft.reject",
                            ),
                        },
                    }
                )
    return {
        "workspace_id": str(workspace_id),
        "recent_bases": [
            {"id": str(base.id), "name": base.name, "source_type": base.source_type}
            for base in bases
        ],
        "queue": queue,
        "business_context_relations": _business_context_relations(
            uow,
            workspace_id=workspace_id,
            actor=actor,
            actor_user_id=identity.user_id,
        ),
    }


def _business_context_relations(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    actor: Any,
    actor_user_id: str,
) -> list[dict[str, Any]]:
    """Return only active, unambiguous, actor-readable Stage08 relation indexes."""

    members = [
        member
        for member in uow.list_workspace_members(workspace_id)
        if member.user_id == actor_user_id and member.status == "active"
    ]
    if len(members) != 1:
        return []
    member = members[0]
    relations: list[dict[str, Any]] = []
    bindings = sorted(
        (
            binding
            for binding in uow.list_telegram_bindings()
            if binding.workspace_id == workspace_id
            and binding.workspace_member_id == member.id
            and binding.binding_type == "chat_user"
            and binding.status == "active"
            and binding.default_digital_employee_id is not None
        ),
        key=lambda binding: str(binding.id),
    )
    if len(bindings) != 1:
        return []
    for binding in bindings:
        employee = uow.get_digital_employee(binding.default_digital_employee_id)
        if (
            employee is None
            or employee.workspace_id != workspace_id
            or employee.status != "active"
            or not is_member_eligible_for_employee(uow, employee, actor_user_id)
        ):
            continue
        base = uow.get_base(employee.base_id)
        if (
            base is None
            or base.workspace_id != workspace_id
            or base.status != "active"
        ):
            continue
        mappings = [
            mapping
            for mapping in uow.list_group_business_context_bindings(binding.id)
            if mapping.workspace_id == workspace_id and mapping.status == "active"
        ]
        if len(mappings) != 1:
            continue
        mapping = mappings[0]
        customer = _safe_business_record_reference(
            uow,
            record_id=mapping.customer_record_id,
            workspace_id=workspace_id,
            actor=actor,
            accessible_table_ids=set(employee.accessible_tables),
            fallback_label="客户记录",
        )
        project = _safe_business_record_reference(
            uow,
            record_id=mapping.project_record_id,
            workspace_id=workspace_id,
            actor=actor,
            accessible_table_ids=set(employee.accessible_tables),
            fallback_label="项目记录",
        )
        if customer is None or project is None:
            continue
        relations.append(
            {
                "employee": {
                    "id": str(employee.id),
                    "name": employee.name,
                    "base_id": str(base.id),
                    "base_name": base.name,
                },
                # This is a local correlation identifier, never Telegram chat/user IDs.
                "group": {
                    "id": f"group_context:{binding.id}",
                    "label": f"已授权群聊 {len(relations) + 1}",
                },
                "customer": customer,
                "project": project,
                "mapping_version": mapping.mapping_version,
            }
        )
    return relations


def _safe_business_record_reference(
    uow: Stage06PlatformUnitOfWork,
    *,
    record_id: UUID,
    workspace_id: UUID,
    actor: Any,
    accessible_table_ids: set[str],
    fallback_label: str,
) -> dict[str, str] | None:
    record = uow.get_record(record_id)
    if record is None or record.record_status != "active":
        return None
    table = uow.get_table(record.table_id)
    if table is None or table.status != "active" or str(table.id) not in accessible_table_ids:
        return None
    base = uow.get_base(table.base_id)
    if base is None or base.workspace_id != workspace_id or base.status != "active":
        return None
    try:
        projection = read_record_for_actor(uow, record_id, actor=actor)
    except PlatformValidationError:
        return None
    return {
        "id": str(record.id),
        "base_id": str(base.id),
        "label": _safe_record_label(projection["values"], fallback=fallback_label),
    }


def _safe_record_label(values: dict[str, Any], *, fallback: str) -> str:
    for key in sorted(values):
        value = values[key]
        if isinstance(value, str) and value.strip():
            return value.strip()[:160]
    return fallback


def _workspace_capabilities(role: str) -> dict[str, bool]:
    return {
        "can_read_bases": action_allowed_for_role(role, "base.read"),
        "can_manage_workspace": action_allowed_for_role(role, "member.read"),
        "can_manage_schema": action_allowed_for_role(role, "field.manage"),
        "can_manage_digital_employees": action_allowed_for_role(
            role,
            "digital_employee.create",
        )
        or action_allowed_for_role(role, "digital_employee.update"),
        "can_review_drafts": action_allowed_for_role(
            role,
            "record_change_draft.confirm",
        )
        or action_allowed_for_role(role, "record_change_draft.reject"),
    }
