from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage08_group_context import Stage08GroupBusinessContextBinding
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
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
from app.services.stage09_skill_launcher import resolve_stage09_skill_catalog


def _fixture() -> SimpleNamespace:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="stage09-owner", role="owner")
    workspace = create_workspace(uow, name="Stage09", owner_user_id=actor.actor_id, actor=actor)
    base = create_base(uow, workspace.id, name="Operations", actor=actor)
    table = create_table(uow, base.id, name="Work", key="work", actor=actor)
    create_field(uow, table.id, name="Title", key="title", field_type="text", actor=actor)
    create_field(
        uow,
        table.id,
        name="Related work",
        key="related_work",
        field_type="linked_record",
        options={"target_table_id": str(table.id)},
        actor=actor,
    )
    peer_record = create_record(uow, table.id, values={"title": "Customer"}, actor=actor)
    record = create_record(
        uow,
        table.id,
        values={"title": "Follow up", "related_work": [str(peer_record.id)]},
        actor=actor,
    )
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Work view",
        view_type="grid",
        config={"fields": ["title"]},
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Stage09 employee",
        description="catalog fixture",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["query", "summarize", "draft_update"],
        field_policy={"writable_fields": ["title"]},
        actor=actor,
    )
    return SimpleNamespace(
        uow=uow,
        actor=actor,
        workspace=workspace,
        base=base,
        table=table,
        record=record,
        peer_record=peer_record,
        view=view,
        employee=employee,
    )


def _catalog(fixture: SimpleNamespace, *, target_record_id=None):
    return resolve_stage09_skill_catalog(
        fixture.uow,
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        target_record_id=target_record_id,
        actor=fixture.actor,
    )


def _add_current_telegram_context(
    fixture: SimpleNamespace,
    *,
    customer_record_id=None,
    project_record_id=None,
) -> Stage06TelegramBinding:
    member = fixture.uow.list_workspace_members(fixture.workspace.id)[0]
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=fixture.workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id="stage09-chat",
        telegram_user_id="stage09-user",
        binding_type="chat_user",
        default_base_id=fixture.base.id,
        default_digital_employee_id=fixture.employee.id,
        scope_policy={},
        status="active",
    )
    fixture.uow.add_telegram_binding(binding)
    fixture.uow.add_group_business_context_binding(
        Stage08GroupBusinessContextBinding(
            id=uuid4(),
            workspace_id=fixture.workspace.id,
            telegram_binding_id=binding.id,
            customer_record_id=(
                fixture.peer_record.id
                if customer_record_id is None
                else customer_record_id
            ),
            project_record_id=(
                fixture.record.id if project_record_id is None else project_record_id
            ),
            mapping_version=1,
            status="active",
        )
    )
    return binding


def test_catalog_returns_only_the_four_public_skills_in_stable_order() -> None:
    catalog = _catalog(_fixture())

    assert catalog.manifest_version == "stage06-larksuite-skills-v1"
    assert catalog.default_selection == "auto"
    assert [item.skill_id for item in catalog.skills] == [
        "platform-base",
        "platform-tabular-analysis",
        "platform-task",
        "platform-telegram-im",
    ]
    assert all(item.enabled for item in catalog.skills[:3])
    assert catalog.skills[3].enabled is False
    assert catalog.skills[3].disabled_reason == "chat_scope_unavailable"
    assert all(
        "platform-shared-policy" not in repr(item)
        and "platform-approval" not in repr(item)
        for item in catalog.skills
    )


def test_catalog_disables_table_read_skills_when_no_current_employee_view_exists() -> None:
    fixture = _fixture()
    fixture.employee.accessible_views = []

    catalog = _catalog(fixture)

    assert [item.disabled_reason for item in catalog.skills[:3]] == [
        "read_scope_unavailable",
        "read_scope_unavailable",
        "read_scope_unavailable",
    ]


def test_catalog_enables_telegram_only_for_one_current_binding_and_mapping() -> None:
    fixture = _fixture()
    binding = _add_current_telegram_context(fixture)
    member = fixture.uow.list_workspace_members(fixture.workspace.id)[0]

    catalog = _catalog(fixture)

    assert catalog.skills[3].enabled is True
    assert catalog.skills[3].disabled_reason is None

    extra = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=fixture.workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id="stage09-chat-2",
        telegram_user_id="stage09-user",
        binding_type="chat_user",
        default_base_id=fixture.base.id,
        default_digital_employee_id=fixture.employee.id,
        scope_policy={},
        status="active",
    )
    fixture.uow.add_telegram_binding(extra)

    ambiguous = _catalog(fixture)

    assert ambiguous.skills[3].enabled is False
    assert ambiguous.skills[3].disabled_reason == "chat_scope_unavailable"


def test_catalog_disables_telegram_when_mapping_records_are_not_visibly_linked() -> None:
    fixture = _fixture()
    unlinked_customer = create_record(
        fixture.uow,
        fixture.table.id,
        values={"title": "Unlinked customer"},
        actor=fixture.actor,
    )
    unlinked_project = create_record(
        fixture.uow,
        fixture.table.id,
        values={"title": "Unlinked project"},
        actor=fixture.actor,
    )
    _add_current_telegram_context(
        fixture,
        customer_record_id=unlinked_customer.id,
        project_record_id=unlinked_project.id,
    )

    catalog = _catalog(fixture)

    assert catalog.skills[3].enabled is False
    assert catalog.skills[3].disabled_reason == "chat_scope_unavailable"


def test_catalog_offers_draft_only_for_visible_target_and_writable_field_intersection() -> None:
    fixture = _fixture()

    without_target = _catalog(fixture)
    with_target = _catalog(fixture, target_record_id=fixture.record.id)
    fixture.employee.field_policy = {"writable_fields": []}
    without_intersection = _catalog(fixture, target_record_id=fixture.record.id)

    assert [item.supported_actions for item in without_target.skills[:3]] == [
        ("read_only",),
        ("read_only",),
        ("read_only",),
    ]
    assert with_target.skills[0].supported_actions == ("read_only", "draft_update")
    assert with_target.skills[2].supported_actions == ("read_only", "draft_update")
    assert without_intersection.skills[0].supported_actions == ("read_only",)
    assert without_intersection.skills[2].supported_actions == ("read_only",)


def test_catalog_omits_draft_when_writable_field_is_not_in_current_employee_view() -> None:
    fixture = _fixture()
    create_field(
        fixture.uow,
        fixture.table.id,
        name="Private update",
        key="private_update",
        field_type="text",
        actor=fixture.actor,
    )
    fixture.employee.field_policy = {"writable_fields": ["private_update"]}

    catalog = _catalog(fixture, target_record_id=fixture.record.id)

    assert catalog.skills[0].supported_actions == ("read_only",)
    assert catalog.skills[2].supported_actions == ("read_only",)


def test_catalog_rejects_malformed_employee_scope() -> None:
    fixture = _fixture()
    fixture.employee.accessible_tables = ["not-a-uuid"]

    with pytest.raises(PlatformValidationError) as exc_info:
        _catalog(fixture)

    assert exc_info.value.code == "stage09_skill_catalog_scope_denied"


@pytest.mark.parametrize(
    "scope_drift",
    [
        "foreign_base",
        "missing_table",
        "inactive_table",
        "missing_view",
        "inactive_view",
        "view_table_mismatch",
    ],
)
def test_catalog_rejects_noncurrent_employee_resource_scope(scope_drift: str) -> None:
    fixture = _fixture()
    if scope_drift == "foreign_base":
        other_base = create_base(
            fixture.uow,
            fixture.workspace.id,
            name="Other",
            actor=fixture.actor,
        )
        other_table = create_table(
            fixture.uow,
            other_base.id,
            name="Other table",
            key="other",
            actor=fixture.actor,
        )
        create_field(
            fixture.uow,
            other_table.id,
            name="Name",
            key="name",
            field_type="text",
            actor=fixture.actor,
        )
        other_view = create_form_view(
            fixture.uow,
            other_base.id,
            other_table.id,
            name="Other view",
            view_type="grid",
            config={"fields": ["name"]},
            actor=fixture.actor,
        )
        fixture.employee.accessible_tables = [str(other_table.id)]
        fixture.employee.accessible_views = [str(other_view.id)]
    elif scope_drift == "missing_table":
        fixture.employee.accessible_tables = [str(uuid4())]
    elif scope_drift == "inactive_table":
        fixture.table.status = "archived"
    elif scope_drift == "missing_view":
        fixture.employee.accessible_views = [str(uuid4())]
    elif scope_drift == "inactive_view":
        fixture.view.status = "archived"
    else:
        other_table = create_table(
            fixture.uow,
            fixture.base.id,
            name="Other table",
            key="other",
            actor=fixture.actor,
        )
        create_field(
            fixture.uow,
            other_table.id,
            name="Name",
            key="name",
            field_type="text",
            actor=fixture.actor,
        )
        other_view = create_form_view(
            fixture.uow,
            fixture.base.id,
            other_table.id,
            name="Other view",
            view_type="grid",
            config={"fields": ["name"]},
            actor=fixture.actor,
        )
        fixture.employee.accessible_views = [str(other_view.id)]

    with pytest.raises(PlatformValidationError) as exc_info:
        _catalog(fixture)

    assert exc_info.value.code == "stage09_skill_catalog_scope_denied"
