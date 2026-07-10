from typing import Any
from uuid import UUID

from app.services.stage06_authorization import (
    action_allowed_for_role,
    authorize_workspace_action,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import Stage06PlatformUnitOfWork


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
    }


def _workspace_capabilities(role: str) -> dict[str, bool]:
    return {
        "can_read_bases": action_allowed_for_role(role, "base.read"),
        "can_manage_workspace": action_allowed_for_role(role, "member.read"),
        "can_manage_schema": action_allowed_for_role(role, "field.manage"),
        "can_review_drafts": action_allowed_for_role(
            role,
            "record_change_draft.confirm",
        )
        or action_allowed_for_role(role, "record_change_draft.reject"),
    }
