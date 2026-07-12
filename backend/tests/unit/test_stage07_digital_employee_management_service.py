from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.stage06_platform import WorkspaceMember
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_form_view,
    create_table,
    create_workspace,
)
from app.services.stage07_digital_employee_management import (
    ManagedEmployeeCreateCommand,
    ManagedEmployeeUpdateCommand,
    activate_managed_employee,
    create_managed_employee,
    is_member_eligible_for_employee,
    pause_managed_employee,
    replace_managed_employee_grants,
    update_managed_employee,
)


def test_managed_employee_runs_draft_to_assigned_active_to_paused() -> None:
    fixture = _management_fixture()
    employee = create_managed_employee(
        fixture.uow,
        fixture.base.id,
        actor=fixture.owner,
        command=ManagedEmployeeCreateCommand(
            name="Customer helper",
            description="Summarizes the selected customer view",
            telegram_alias="customer-helper",
        ),
        idempotency_key="managed-create-1",
    )

    assert employee.status == "draft"
    assert employee.version == 1
    assert employee.access_mode == "assigned"
    assert employee.allowed_actions == ["summarize"]

    configured = update_managed_employee(
        fixture.uow,
        employee.id,
        actor=fixture.owner,
        expected_version=1,
        command=ManagedEmployeeUpdateCommand(
            accessible_table_ids=[fixture.table.id],
            accessible_view_ids=[fixture.view.id],
            allowed_actions=["summarize", "draft_update"],
            access_mode="assigned",
        ),
    )
    granted = replace_managed_employee_grants(
        fixture.uow,
        employee.id,
        actor=fixture.owner,
        member_ids=[fixture.operator.id],
        expected_version=configured.version,
        idempotency_key="managed-grants-1",
    )
    activation_version = granted.version
    receipt = activate_managed_employee(
        fixture.uow,
        employee.id,
        actor=fixture.owner,
        expected_version=activation_version,
        idempotency_key="managed-activate-1",
    )
    replay = activate_managed_employee(
        fixture.uow,
        employee.id,
        actor=fixture.owner,
        expected_version=activation_version,
        idempotency_key="managed-activate-1",
    )

    assert receipt == replay
    assert receipt.status == "active"
    assert receipt.version == 4
    assert receipt.audit_event_id is not None
    assert is_member_eligible_for_employee(
        fixture.uow,
        employee,
        fixture.operator.user_id,
    ) is True
    assert is_member_eligible_for_employee(
        fixture.uow,
        employee,
        fixture.owner.actor_id,
    ) is False

    with pytest.raises(PlatformValidationError) as active_update:
        update_managed_employee(
            fixture.uow,
            employee.id,
            actor=fixture.owner,
            expected_version=receipt.version,
            command=ManagedEmployeeUpdateCommand(name="Must pause first"),
        )
    assert active_update.value.code == "digital_employee_active_requires_pause"

    records_before = list(fixture.uow.records)
    drafts_before = list(fixture.uow.record_change_drafts)
    pause_version = receipt.version
    paused = pause_managed_employee(
        fixture.uow,
        employee.id,
        actor=fixture.owner,
        expected_version=pause_version,
        idempotency_key="managed-pause-1",
    )
    pause_replay = pause_managed_employee(
        fixture.uow,
        employee.id,
        actor=fixture.owner,
        expected_version=pause_version,
        idempotency_key="managed-pause-1",
    )

    assert paused.status == "paused"
    assert paused.version == 5
    assert pause_replay == paused
    assert fixture.uow.records == records_before
    assert fixture.uow.record_change_drafts == drafts_before
    audit_text = str(fixture.uow.audit_events[-1].after_state)
    assert "field_policy" not in audit_text
    assert "confirmation_policy" not in audit_text
    assert "response_style" not in audit_text
    assert "customer-helper" not in audit_text


def test_managed_employee_rejects_invalid_scope_actions_and_grants() -> None:
    fixture = _management_fixture()
    other_workspace = create_workspace(
        fixture.uow,
        name="Other workspace",
        owner_user_id="other-owner",
    )
    other_base = create_base(fixture.uow, other_workspace.id, name="Other Base")
    other_table = create_table(
        fixture.uow,
        other_base.id,
        name="Other table",
        key="other_table",
    )
    employee = _create_draft_employee(fixture)

    with pytest.raises(PlatformValidationError) as unknown_action:
        update_managed_employee(
            fixture.uow,
            employee.id,
            actor=fixture.owner,
            expected_version=1,
            command=ManagedEmployeeUpdateCommand(allowed_actions=["query"]),
        )
    assert unknown_action.value.code == "digital_employee_action_unsupported"

    with pytest.raises(PlatformValidationError) as table_outside_base:
        update_managed_employee(
            fixture.uow,
            employee.id,
            actor=fixture.owner,
            expected_version=1,
            command=ManagedEmployeeUpdateCommand(
                accessible_table_ids=[other_table.id],
                accessible_view_ids=[],
            ),
        )
    assert table_outside_base.value.code == "digital_employee_scope_denied"

    with pytest.raises(PlatformValidationError) as inactive_member:
        replace_managed_employee_grants(
            fixture.uow,
            employee.id,
            actor=fixture.owner,
            member_ids=[fixture.inactive_member.id],
            expected_version=1,
            idempotency_key="managed-inactive-member",
        )
    assert inactive_member.value.code == "digital_employee_member_inactive"

    with pytest.raises(PlatformValidationError) as wrong_workspace_member:
        replace_managed_employee_grants(
            fixture.uow,
            employee.id,
            actor=fixture.owner,
            member_ids=[fixture.other_workspace_member.id],
            expected_version=1,
            idempotency_key="managed-other-workspace-member",
        )
    assert wrong_workspace_member.value.code == "digital_employee_member_scope_denied"


def test_managed_employee_requires_current_version_grants_and_alias_uniqueness() -> None:
    fixture = _management_fixture()
    first = _configured_assigned_employee(fixture, alias="same-alias")

    with pytest.raises(PlatformValidationError) as missing_grant:
        activate_managed_employee(
            fixture.uow,
            first.id,
            actor=fixture.owner,
            expected_version=2,
            idempotency_key="managed-first-no-grant",
        )
    assert missing_grant.value.code == "digital_employee_member_grant_required"

    granted = replace_managed_employee_grants(
        fixture.uow,
        first.id,
        actor=fixture.owner,
        member_ids=[fixture.operator.id],
        expected_version=2,
        idempotency_key="managed-first-grant",
    )
    activated = activate_managed_employee(
        fixture.uow,
        first.id,
        actor=fixture.owner,
        expected_version=granted.version,
        idempotency_key="managed-first-activate",
    )
    assert activated.status == "active"

    second = _configured_assigned_employee(fixture, alias="same-alias")
    second_granted = replace_managed_employee_grants(
        fixture.uow,
        second.id,
        actor=fixture.owner,
        member_ids=[fixture.operator.id],
        expected_version=2,
        idempotency_key="managed-second-grant",
    )
    with pytest.raises(PlatformValidationError) as alias_collision:
        activate_managed_employee(
            fixture.uow,
            second.id,
            actor=fixture.owner,
            expected_version=second_granted.version,
            idempotency_key="managed-second-activate",
        )
    assert alias_collision.value.code == "digital_employee_alias_conflict"

    with pytest.raises(PlatformValidationError) as stale_update:
        update_managed_employee(
            fixture.uow,
            first.id,
            actor=fixture.owner,
            expected_version=1,
            command=ManagedEmployeeUpdateCommand(name="Stale update"),
        )
    assert stale_update.value.code == "digital_employee_revision_conflict"


def test_managed_employee_create_is_idempotent_and_legacy_workspace_mode_needs_no_grant() -> None:
    fixture = _management_fixture()
    command = ManagedEmployeeCreateCommand(
        name="Idempotent helper",
        description="Creates once",
        telegram_alias=None,
    )
    first = create_managed_employee(
        fixture.uow,
        fixture.base.id,
        actor=fixture.owner,
        command=command,
        idempotency_key="managed-create-idempotent",
    )
    replay = create_managed_employee(
        fixture.uow,
        fixture.base.id,
        actor=fixture.owner,
        command=command,
        idempotency_key="managed-create-idempotent",
    )

    assert replay.id == first.id
    with pytest.raises(PlatformValidationError) as changed_payload:
        create_managed_employee(
            fixture.uow,
            fixture.base.id,
            actor=fixture.owner,
            command=ManagedEmployeeCreateCommand(
                name="Changed payload",
                description="Creates once",
                telegram_alias=None,
            ),
            idempotency_key="managed-create-idempotent",
        )
    assert changed_payload.value.code == "idempotency_conflict"

    legacy = create_digital_employee(
        fixture.uow,
        fixture.base.id,
        name="Legacy workspace helper",
        description="Legacy employee",
        telegram_alias=None,
        accessible_tables=[],
        accessible_views=[str(fixture.view.id)],
        allowed_actions=["summarize"],
        actor=fixture.owner,
    )

    assert is_member_eligible_for_employee(
        fixture.uow,
        legacy,
        fixture.operator.user_id,
    ) is True


class _ManagementFixture:
    def __init__(self) -> None:
        self.uow = InMemoryStage06PlatformUnitOfWork()
        self.owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
        self.workspace = create_workspace(
            self.uow,
            name="Managed employees",
            owner_user_id=self.owner.actor_id,
            actor=self.owner,
        )
        self.base = create_base(
            self.uow,
            self.workspace.id,
            name="Customers",
            actor=self.owner,
        )
        self.table = create_table(
            self.uow,
            self.base.id,
            name="Customers",
            key="customers",
            actor=self.owner,
        )
        self.view = create_form_view(
            self.uow,
            self.base.id,
            self.table.id,
            name="Customer grid",
            view_type="grid",
            config={"fields": []},
            actor=self.owner,
        )
        self.operator = WorkspaceMember(
            id=uuid4(),
            workspace_id=self.workspace.id,
            user_id="operator-1",
            role="operator",
            status="active",
            version=1,
        )
        self.inactive_member = WorkspaceMember(
            id=uuid4(),
            workspace_id=self.workspace.id,
            user_id="inactive-1",
            role="viewer",
            status="inactive",
            version=1,
        )
        other_workspace = create_workspace(
            self.uow,
            name="Foreign members",
            owner_user_id="foreign-owner",
        )
        self.other_workspace_member = WorkspaceMember(
            id=uuid4(),
            workspace_id=other_workspace.id,
            user_id="foreign-member",
            role="viewer",
            status="active",
            version=1,
        )
        self.uow.add_workspace_member(self.operator)
        self.uow.add_workspace_member(self.inactive_member)
        self.uow.add_workspace_member(self.other_workspace_member)


def _management_fixture() -> _ManagementFixture:
    return _ManagementFixture()


def _create_draft_employee(
    fixture: _ManagementFixture,
    *,
    alias: str | None = None,
):
    return create_managed_employee(
        fixture.uow,
        fixture.base.id,
        actor=fixture.owner,
        command=ManagedEmployeeCreateCommand(
            name="Draft helper",
            description="Draft employee",
            telegram_alias=alias,
        ),
        idempotency_key=f"managed-draft-{uuid4()}",
    )


def _configured_assigned_employee(
    fixture: _ManagementFixture,
    *,
    alias: str,
):
    employee = _create_draft_employee(fixture, alias=alias)
    return update_managed_employee(
        fixture.uow,
        employee.id,
        actor=fixture.owner,
        expected_version=1,
        command=ManagedEmployeeUpdateCommand(
            accessible_table_ids=[fixture.table.id],
            accessible_view_ids=[fixture.view.id],
            allowed_actions=["summarize"],
            access_mode="assigned",
        ),
    )
