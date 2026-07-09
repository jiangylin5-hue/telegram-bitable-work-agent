from uuid import uuid4

import pytest

from app.models.stage06_platform import WorkspaceMember
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    bind_telegram_context,
    create_digital_employee,
    resolve_telegram_mention,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


def _telegram_fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    viewer = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id="viewer-1",
        role="viewer",
        status="active",
    )
    uow.add_workspace_member(viewer)
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Name", key="name", field_type="text")
    create_record(uow, table.id, values={"name": "Ada"})
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Grid",
        view_type="grid",
        config={"fields": ["name"]},
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="CRM Helper",
        description="Summarize CRM",
        telegram_alias="crm",
        accessible_tables=[str(table.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )
    return uow, workspace, viewer, base, view, employee


def test_stage06_telegram_mention_uses_bound_workspace_member_role() -> None:
    uow, workspace, viewer, base, view, employee = _telegram_fixture()
    bind_telegram_context(
        uow,
        workspace.id,
        workspace_member_id=viewer.id,
        telegram_chat_id="chat-1",
        telegram_user_id="telegram-1",
        default_base_id=base.id,
        default_digital_employee_id=employee.id,
        scope_policy={"views": [str(view.id)]},
    )

    response = resolve_telegram_mention(
        uow,
        telegram_chat_id="chat-1",
        telegram_user_id="telegram-1",
        alias="crm",
        text="summarize",
    )

    assert response["record_count"] == 1
    assert uow.agent_runs[-1].input_summary["actor_role"] == "viewer"


def test_stage06_telegram_binding_rejects_member_from_another_workspace() -> None:
    uow, workspace, _viewer, base, view, employee = _telegram_fixture()
    other_workspace = create_workspace(uow, name="Other", owner_user_id="other-owner")
    other_member = uow.list_workspace_members(other_workspace.id)[0]

    with pytest.raises(PlatformValidationError) as denied:
        bind_telegram_context(
            uow,
            workspace.id,
            workspace_member_id=other_member.id,
            telegram_chat_id="chat-1",
            telegram_user_id="telegram-1",
            default_base_id=base.id,
            default_digital_employee_id=employee.id,
            scope_policy={"views": [str(view.id)]},
        )

    assert denied.value.code == "resource_scope_mismatch"
