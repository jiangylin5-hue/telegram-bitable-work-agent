"""Provision the first real Stage09 workspace for one allowlisted Telegram owner.

This is an operator-only recovery tool for an empty native platform database.
It deliberately accepts no Telegram identity from CLI input: the one private user
must already be configured in the service allowlists.  The output is safe to
store as deployment evidence and never includes raw Telegram values or secrets.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final, Iterable, Mapping
from uuid import UUID, uuid4

from app.core.database import get_session_factory
from app.models.stage08_group_context import Stage08GroupBusinessContextBinding
from app.models.telegram import Message
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    bind_telegram_context,
    create_digital_employee,
)
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


WORKSPACE_NAME: Final = "我的协作工作区"
BASE_NAME: Final = "客户协作工作台"
TRACE_ID: Final = "stage09.first_workspace_provisioning.v1"


class ProvisioningTargetError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProvisionedWorkspace:
    workspace_id: UUID
    base_id: UUID
    table_count: int
    has_binding: bool
    status: str


def parse_single_private_target(
    candidates: Iterable[Mapping[str, object]],
) -> dict[str, str]:
    matched = [
        candidate
        for candidate in candidates
        if candidate.get("raw_text") == "/stage07-bind"
        and candidate.get("message_type") == "text"
        and isinstance(candidate.get("telegram_user_id"), str)
        and isinstance(candidate.get("telegram_chat_id"), str)
    ]
    if (
        len(matched) != 1
        or matched[0]["telegram_user_id"] != matched[0]["telegram_chat_id"]
        or not str(matched[0]["telegram_user_id"]).isdigit()
    ):
        raise ProvisioningTargetError("single_matching_private_target_required")
    return {
        "telegram_user_id": str(matched[0]["telegram_user_id"]),
        "telegram_chat_id": str(matched[0]["telegram_chat_id"]),
    }


def build_provisioning_receipt(
    *,
    status: str,
    workspace_id: str,
    base_id: str,
    table_count: int,
    has_binding: bool,
) -> dict[str, object]:
    return {
        "status": status,
        "workspace_id": workspace_id,
        "base_id": base_id,
        "table_count": table_count,
        "has_binding": has_binding,
    }


def provision_first_workspace(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    *,
    telegram_user_id: str,
    telegram_chat_id: str,
) -> ProvisionedWorkspace:
    existing_bindings = [
        binding
        for binding in uow.list_telegram_bindings()
        if binding.status == "active" and binding.telegram_user_id == telegram_user_id
    ]
    if len(existing_bindings) > 1:
        raise ProvisioningTargetError("active_telegram_binding_ambiguous")
    if len(existing_bindings) == 1:
        binding = existing_bindings[0]
        workspace = uow.get_workspace(binding.workspace_id)
        base = (
            None
            if binding.default_base_id is None
            else uow.get_base(binding.default_base_id)
        )
        if workspace is None or base is None:
            raise ProvisioningTargetError("existing_binding_incomplete")
        return ProvisionedWorkspace(
            workspace_id=workspace.id,
            base_id=base.id,
            table_count=len(uow.list_tables(base.id)),
            has_binding=True,
            status="existing",
        )

    if uow.list_workspaces():
        raise ProvisioningTargetError("workspace_exists_without_owner_binding")

    member_user_id = _opaque_member_user_id(telegram_user_id)
    actor = Actor(actor_type="user", actor_id=member_user_id, role="owner")
    workspace = create_workspace(
        uow,
        name=WORKSPACE_NAME,
        owner_user_id=member_user_id,
        actor=actor,
    )
    owner_member = next(
        member
        for member in uow.list_workspace_members(workspace.id)
        if member.user_id == member_user_id and member.status == "active"
    )
    base = create_base(
        uow,
        workspace.id,
        name=BASE_NAME,
        description="客户、项目、群聊与数字员工的协作工作台",
        actor=actor,
    )
    customer_table, customer_view = _create_customer_table(uow, base.id, actor)
    project_table, project_view = _create_project_table(
        uow,
        base.id,
        customer_table.id,
        actor,
    )
    group_table, group_view = _create_group_table(
        uow,
        base.id,
        customer_table.id,
        project_table.id,
        actor,
    )
    customer = create_record(
        uow,
        customer_table.id,
        values={
            "name": "明日璀璨",
            "stage": "方案确认",
            "owner": member_user_id,
            "next_action": "确认报价范围并预约价格沟通",
            "last_touch_at": "2026-07-23",
        },
        actor=actor,
    )
    project = create_record(
        uow,
        project_table.id,
        values={
            "name": "年度协作升级",
            "customer": [str(customer.id)],
            "phase": "方案确认",
            "owner": member_user_id,
            "next_milestone": "2026-07-25",
        },
        actor=actor,
    )
    create_record(
        uow,
        group_table.id,
        values={
            "name": "明日璀璨 · 项目协作群",
            "customer": [str(customer.id)],
            "project": [str(project.id)],
            "status": "活跃",
        },
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="客户协作数字员工",
        description="基于授权客户、项目与群聊上下文生成协作草稿。",
        telegram_alias="BitableAgentBot",
        accessible_tables=[
            str(customer_table.id),
            str(project_table.id),
            str(group_table.id),
        ],
        accessible_views=[
            str(customer_view.id),
            str(project_view.id),
            str(group_view.id),
        ],
        allowed_actions=[
            "schema_inspect",
            "query",
            "summarize",
            "draft_create",
            "draft_update",
            "status_advance",
        ],
        actor=actor,
        response_style={"language": "zh-CN", "format": "action_list"},
    )
    binding = bind_telegram_context(
        uow,
        workspace.id,
        workspace_member_id=owner_member.id,
        telegram_chat_id=telegram_chat_id,
        telegram_user_id=telegram_user_id,
        default_base_id=base.id,
        default_digital_employee_id=employee.id,
        scope_policy={
            "scope": "private_chat_owner",
            "confirmation_required": True,
        },
    )
    mapping = Stage08GroupBusinessContextBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        telegram_binding_id=binding.id,
        customer_record_id=customer.id,
        project_record_id=project.id,
        mapping_version=1,
        status="active",
    )
    uow.add_group_business_context_binding(mapping)
    record_audit_event(
        uow.session,
        trace_id=TRACE_ID,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="stage09.first_workspace_provisioned",
        entity_type="workspace",
        entity_id=workspace.id,
        after_state={
            "base_id": str(base.id),
            "table_count": 3,
            "has_active_binding": True,
            "has_group_business_context_mapping": True,
        },
        permission_snapshot={"role": actor.role, "scope": "private_chat_owner"},
    )
    return ProvisionedWorkspace(
        workspace_id=workspace.id,
        base_id=base.id,
        table_count=3,
        has_binding=True,
        status="created",
    )


def _create_customer_table(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    base_id: UUID,
    actor: Actor,
):
    table = create_table(uow, base_id, name="客户", key="customers", actor=actor)
    _create_fields(
        uow,
        table.id,
        actor,
        [
            ("客户名称", "name", "text", True, {}),
            ("当前阶段", "stage", "status", False, {"choices": ["线索", "方案确认", "商务谈判", "已成交"]}),
            ("负责人", "owner", "user", False, {}),
            ("下一步动作", "next_action", "text", False, {}),
            ("最近沟通", "last_touch_at", "date", False, {}),
        ],
    )
    view = create_form_view(
        uow,
        base_id,
        table.id,
        name="全部客户",
        view_type="grid",
        config={"fields": ["name", "stage", "owner", "next_action", "last_touch_at"]},
        is_default=True,
        actor=actor,
    )
    return table, view


def _create_project_table(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    base_id: UUID,
    customer_table_id: UUID,
    actor: Actor,
):
    table = create_table(uow, base_id, name="项目", key="projects", actor=actor)
    _create_fields(
        uow,
        table.id,
        actor,
        [
            ("项目名称", "name", "text", True, {}),
            ("关联客户", "customer", "linked_record", True, {"target_table_id": str(customer_table_id)}),
            ("阶段", "phase", "status", False, {"choices": ["计划中", "方案确认", "执行中", "已完成"]}),
            ("负责人", "owner", "user", False, {}),
            ("下个里程碑", "next_milestone", "date", False, {}),
        ],
    )
    view = create_form_view(
        uow,
        base_id,
        table.id,
        name="全部项目",
        view_type="grid",
        config={"fields": ["name", "customer", "phase", "owner", "next_milestone"]},
        is_default=True,
        actor=actor,
    )
    return table, view


def _create_group_table(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    base_id: UUID,
    customer_table_id: UUID,
    project_table_id: UUID,
    actor: Actor,
):
    table = create_table(uow, base_id, name="群聊", key="groups", actor=actor)
    _create_fields(
        uow,
        table.id,
        actor,
        [
            ("群聊名称", "name", "text", True, {}),
            ("关联客户", "customer", "linked_record", True, {"target_table_id": str(customer_table_id)}),
            ("关联项目", "project", "linked_record", True, {"target_table_id": str(project_table_id)}),
            ("状态", "status", "status", False, {"choices": ["活跃", "已归档"]}),
        ],
    )
    view = create_form_view(
        uow,
        base_id,
        table.id,
        name="全部群聊",
        view_type="grid",
        config={"fields": ["name", "customer", "project", "status"]},
        is_default=True,
        actor=actor,
    )
    return table, view


def _create_fields(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    table_id: UUID,
    actor: Actor,
    fields: list[tuple[str, str, str, bool, dict[str, object]]],
) -> None:
    for name, key, field_type, required, options in fields:
        create_field(
            uow,
            table_id,
            name=name,
            key=key,
            field_type=field_type,
            required=required,
            options=options,
            actor=actor,
        )


def _opaque_member_user_id(telegram_user_id: str) -> str:
    digest = hashlib.sha256(
        f"stage09-telegram-member-v1:{telegram_user_id}".encode("utf-8")
    ).hexdigest()
    return f"tg_member_{digest[:32]}"


def main() -> int:
    session = get_session_factory()()
    try:
        target = parse_single_private_target(
            {
                "telegram_user_id": str(message.telegram_user_id or ""),
                "telegram_chat_id": str(message.telegram_chat_id or ""),
                "raw_text": str(message.raw_text or ""),
                "message_type": str(message.message_type or ""),
            }
            for message in session.query(Message).all()
        )
        result = provision_first_workspace(
            SqlAlchemyStage06PlatformUnitOfWork(session),
            telegram_user_id=target["telegram_user_id"],
            telegram_chat_id=target["telegram_chat_id"],
        )
        session.commit()
    except ProvisioningTargetError as exc:
        session.rollback()
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    except Exception:
        session.rollback()
        print(json.dumps({"status": "failed"}))
        return 1
    finally:
        session.close()

    print(
        json.dumps(
            build_provisioning_receipt(
                status=result.status,
                workspace_id=str(result.workspace_id),
                base_id=str(result.base_id),
                table_count=result.table_count,
                has_binding=result.has_binding,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
