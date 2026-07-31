from __future__ import annotations

import pytest

from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)


def test_entity_linker_uses_authorized_identity_label_and_alias_without_prefixes() -> (
    None
):
    try:
        from app.services.agent_authorized_entity_linker import (
            build_authorized_entity_candidates,
        )
    except ImportError as exc:
        pytest.fail(f"authorized entity linker is missing: {exc}")

    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-entity-linker", role="owner")
    workspace = create_workspace(
        uow,
        name="Entity Linker",
        owner_user_id=owner.actor_id,
        actor=owner,
    )
    base = create_base(uow, workspace.id, name="Generic", actor=owner)
    table = create_table(uow, base.id, name="Cases", key="cases", actor=owner)
    code = create_field(
        uow,
        table.id,
        name="Case ID",
        key="case_id",
        field_type="text",
        actor=owner,
    )
    label = create_field(
        uow,
        table.id,
        name="Name",
        key="name",
        field_type="text",
        actor=owner,
    )
    alias = create_field(
        uow,
        table.id,
        name="Aliases",
        key="aliases",
        field_type="text",
        actor=owner,
    )
    hidden = create_field(
        uow,
        table.id,
        name="Hidden Alias",
        key="hidden_alias",
        field_type="text",
        permission_policy={"owner": "hidden"},
        actor=owner,
    )
    table.settings = {
        "identity_field_key": code.key,
        "entity_label_field_key": label.key,
        "entity_alias_field_keys": [alias.key, hidden.key],
    }
    record = create_record(
        uow,
        table.id,
        values={
            code.key: "CASE-42",
            label.key: "Apollo",
            alias.key: "阿波罗",
            hidden.key: "绝密代号",
        },
        actor=owner,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Generic Planner",
        description="Entity linker test",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[],
        allowed_actions=["query"],
        actor=owner,
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )

    by_alias = build_authorized_entity_candidates(
        uow,
        query="请检查阿波罗的当前状态",
        actor=owner,
        workspace_id=workspace.id,
        base_id=base.id,
        employee_id=employee.id,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )
    by_code = build_authorized_entity_candidates(
        uow,
        query="打开 CASE-42",
        actor=owner,
        workspace_id=workspace.id,
        base_id=base.id,
        employee_id=employee.id,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )
    hidden_lookup = build_authorized_entity_candidates(
        uow,
        query="打开绝密代号",
        actor=owner,
        workspace_id=workspace.id,
        base_id=base.id,
        employee_id=employee.id,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )

    assert by_alias == by_code
    assert len(by_alias) == 1
    assert by_alias[0].entity_id == record.id
    assert by_alias[0].code == "CASE-42"
    assert by_alias[0].label == "Apollo"
    assert by_alias[0].aliases == ("阿波罗",)
    assert hidden_lookup == ()
    assert str(hidden.id) not in snapshot.model_dump_json()
