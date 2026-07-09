from uuid import uuid4

import pytest

from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    create_digital_employee,
    invoke_digital_employee,
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
from app.services.stage06_templates import create_import_job_from_csv


def _owner() -> Actor:
    return Actor(actor_type="user", actor_id="owner-1", role="owner")


def test_stage06_view_rejects_table_from_another_base() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base_a = create_base(uow, workspace.id, name="A")
    base_b = create_base(uow, workspace.id, name="B")
    table_b = create_table(uow, base_b.id, name="B", key="b")

    with pytest.raises(PlatformValidationError) as denied:
        create_form_view(
            uow,
            base_a.id,
            table_b.id,
            name="Cross Base",
            view_type="grid",
            config={},
        )

    assert denied.value.code == "resource_scope_mismatch"


def test_stage06_import_rejects_base_from_another_workspace() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace_a = create_workspace(uow, name="A", owner_user_id="owner-1")
    workspace_b = create_workspace(uow, name="B", owner_user_id="owner-2")
    base_b = create_base(uow, workspace_b.id, name="B")

    with pytest.raises(PlatformValidationError) as denied:
        create_import_job_from_csv(
            uow,
            workspace_a.id,
            file_name="data.csv",
            content="name\nAda",
            created_by_user_id="owner-1",
            base_id=base_b.id,
        )

    assert denied.value.code == "resource_scope_mismatch"


def test_stage06_employee_rejects_view_from_another_base() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base_a = create_base(uow, workspace.id, name="A")
    base_b = create_base(uow, workspace.id, name="B")
    table_b = create_table(uow, base_b.id, name="B", key="b")
    view_b = create_form_view(
        uow,
        base_b.id,
        table_b.id,
        name="B Grid",
        view_type="grid",
        config={},
    )

    with pytest.raises(PlatformValidationError) as denied:
        create_digital_employee(
            uow,
            base_a.id,
            name="Cross",
            description="Cross base",
            telegram_alias="cross",
            accessible_tables=[],
            accessible_views=[str(view_b.id)],
            allowed_actions=["summarize"],
            actor=_owner(),
        )

    assert denied.value.code == "resource_scope_mismatch"


def test_stage06_empty_employee_table_scope_denies_draft_update() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Status", key="status", field_type="status")
    record = create_record(uow, table.id, values={"status": "new"})
    employee = create_digital_employee(
        uow,
        base.id,
        name="No Scope",
        description="No table access",
        telegram_alias=None,
        accessible_tables=[],
        accessible_views=[],
        allowed_actions=["draft_update"],
        actor=_owner(),
    )

    with pytest.raises(PlatformValidationError) as denied:
        invoke_digital_employee(
            uow,
            employee.id,
            action="draft_update",
            record_id=record.id,
            proposed_values={"status": "done"},
            actor=_owner(),
        )

    assert denied.value.code == "digital_employee_scope_denied"


def test_stage06_linked_record_rejects_cross_base_target() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base_a = create_base(uow, workspace.id, name="A")
    base_b = create_base(uow, workspace.id, name="B")
    table_a = create_table(uow, base_a.id, name="A", key="a")
    table_b = create_table(uow, base_b.id, name="B", key="b")
    target = create_record(uow, table_b.id, values={})
    create_field(
        uow,
        table_a.id,
        name="Cross Link",
        key="cross_link",
        field_type="linked_record",
        options={"target_table_id": str(table_b.id)},
    )

    with pytest.raises(PlatformValidationError) as denied:
        create_record(
            uow,
            table_a.id,
            values={"cross_link": [str(target.id)]},
        )

    assert denied.value.code == "resource_scope_mismatch"
