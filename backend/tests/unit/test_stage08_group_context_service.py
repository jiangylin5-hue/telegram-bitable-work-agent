from datetime import UTC, datetime, timedelta, timezone
from dataclasses import is_dataclass
import json
from uuid import uuid4

import pytest

from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage08_group_context import (
    Stage08GroupBusinessContextBinding,
    Stage08GroupMessageProjection,
)
from app.runtime.stage08_context_contracts import ResolvedBusinessScope
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_group_context import (
    _GroupContextAuthority,
    _materialize_group_context_window,
    Stage08GroupContextAuthorityFactory,
    build_group_context_window,
    purge_expired_group_context_projections,
    purge_group_context_projection,
)


NOW = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-c2", role="owner")
    workspace = create_workspace(
        uow, name="C2", owner_user_id=actor.actor_id, actor=actor
    )
    member = uow.list_workspace_members(workspace.id)[0]
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    customers = create_table(
        uow, base.id, name="Customers", key="customers", actor=actor
    )
    projects = create_table(
        uow, base.id, name="Projects", key="projects", actor=actor
    )
    create_field(
        uow, customers.id, name="Name", key="name", field_type="text", actor=actor
    )
    create_field(
        uow,
        projects.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customers.id)},
        actor=actor,
    )
    customer = create_record(
        uow, customers.id, values={"name": "Acme"}, actor=actor
    )
    project = create_record(
        uow,
        projects.id,
        values={"customer": [str(customer.id)]},
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="C2 employee",
        description="group context",
        telegram_alias=None,
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[],
        allowed_actions=["summarize"],
        actor=actor,
    )
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id="-100200300",
        telegram_user_id="200300",
        binding_type="chat_user",
        scope_policy={},
        status="active",
    )
    uow.add_telegram_binding(binding)
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
    scope = ResolvedBusinessScope(
        workspace_id=workspace.id,
        customer_record_id=customer.id,
        customer_version=customer.version,
        project_record_id=project.id,
        project_version=project.version,
        relation_kind="visible_linked_record",
    )
    return (
        uow,
        actor,
        workspace,
        member,
        base,
        customers,
        projects,
        customer,
        project,
        employee,
        binding,
        mapping,
        scope,
    )


def _add_projection(
    uow,
    mapping,
    *,
    text="x",
    event_at=NOW,
    expires=None,
    source_chat_type="group",
):
    projection = Stage08GroupMessageProjection(
        id=uuid4(),
        source_message_id=uuid4(),
        business_context_binding_id=mapping.id,
        content_fragment=text,
        content_version=1,
        event_at=event_at,
        edited_at=None,
        retention_expires_at=expires or event_at + timedelta(days=30),
        lifecycle_status="active",
        source_chat_type=source_chat_type,
    )
    uow.add_group_message_projection(projection)
    return projection


def _authority(fixture):
    uow, actor, workspace, *_rest, employee, _binding, _mapping, _scope = fixture
    return Stage08GroupContextAuthorityFactory.build(
        uow, actor=actor, employee_id=employee.id, workspace_id=workspace.id
    )


@pytest.mark.parametrize(
    "drift",
    [
        "actor",
        "member",
        "employee",
        "base",
        "binding",
        "mapping",
        "customer",
        "project",
        "workspace",
        "relation",
        "table_scope",
        "ambiguous_binding",
        "ambiguous_mapping",
    ],
)
def test_factory_fails_closed_without_exposing_source_for_invalid_scope(drift) -> None:
    fixture = _fixture()
    (
        uow,
        actor,
        workspace,
        member,
        base,
        customers,
        _projects,
        customer,
        project,
        employee,
        binding,
        mapping,
        scope,
    ) = fixture
    if drift == "actor":
        actor = Actor(actor_type="service", actor_id=actor.actor_id, role="owner")
    elif drift == "member":
        member.status = "inactive"
    elif drift == "employee":
        employee.status = "paused"
    elif drift == "base":
        base.status = "inactive"
    elif drift == "binding":
        binding.status = "inactive"
    elif drift == "mapping":
        mapping.status = "inactive"
    elif drift == "customer":
        customer.record_status = "inactive"
    elif drift == "project":
        project.record_status = "inactive"
    elif drift == "workspace":
        workspace.status = "inactive"
    elif drift == "relation":
        project.record_values["customer"] = []
    elif drift == "table_scope":
        employee.accessible_tables = [str(customers.id)]
    elif drift == "ambiguous_binding":
        duplicate = Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=workspace.id,
            workspace_member_id=member.id,
            telegram_chat_id="-100999",
            telegram_user_id="200300",
            binding_type="chat_user",
            scope_policy={},
            status="active",
        )
        uow.add_telegram_binding(duplicate)
    else:
        uow.group_business_context_bindings.append(
            Stage08GroupBusinessContextBinding(
                id=uuid4(),
                workspace_id=workspace.id,
                telegram_binding_id=binding.id,
                customer_record_id=customer.id,
                project_record_id=project.id,
                mapping_version=2,
                status="active",
            )
        )
    authority = Stage08GroupContextAuthorityFactory.build(
        uow, actor=actor, employee_id=employee.id, workspace_id=workspace.id
    )
    window = build_group_context_window(uow, authority, business_scope=scope, now=NOW)
    assert window.view().status == "group_context_unavailable"
    assert "200300" not in repr(authority)
    assert "Acme" not in repr(window.view())


def test_window_uses_latest_24_then_decay_history_and_exact_bounds() -> None:
    fixture = _fixture()
    uow, _actor, _workspace, *_middle, mapping, scope = fixture
    created = [
        _add_projection(
            uow,
            mapping,
            text=f"fragment-{index:03d}",
            event_at=NOW - timedelta(minutes=index),
        )
        for index in range(121)
    ]
    authority = _authority(fixture)
    window = build_group_context_window(uow, authority, business_scope=scope, now=NOW)
    materialized = _materialize_group_context_window(
        uow, authority, window, business_scope=scope, now=NOW
    )
    view = window.view()
    assert view.status == "group_context_partial"
    assert view.usage.selected_fragments == 120
    assert view.usage.latest_selected_fragments == 24
    assert view.usage.history_selected_fragments == 96
    assert view.omissions.fragment_limit == 1
    assert not hasattr(window, "_selected_fragments")
    assert [item.display_id for item in materialized._fragments] == [
        f"group_context:{index:02d}" for index in range(1, 121)
    ]
    assert [item._text for item in materialized._fragments] == [
        projection.content_fragment for projection in created[:120]
    ]
    assert all(item.label == "group_context" for item in materialized._fragments)
    assert all(
        item.source_type == "group_message_fragment"
        for item in materialized._fragments
    )
    assert all(
        item.scope_categories == (
            "workspace",
            "group",
            "customer",
            "project",
        )
        for item in materialized._fragments
    )
    assert "fragment-000" not in repr(materialized)
    safe_view_dump = repr(window.view().model_dump(mode="python"))
    assert all(item.content_fragment not in safe_view_dump for item in created)
    assert all(str(item.id) not in safe_view_dump for item in created)


def test_window_omits_oversized_fragment_without_replacing_latest_band_slot() -> None:
    fixture = _fixture()
    uow, _actor, _workspace, *_middle, mapping, scope = fixture
    _add_projection(uow, mapping, text="x" * 501, event_at=NOW)
    for index in range(120):
        _add_projection(
            uow,
            mapping,
            text="ok",
            event_at=NOW - timedelta(minutes=index + 1),
        )
    authority = _authority(fixture)
    window = build_group_context_window(
        uow, authority, business_scope=scope, now=NOW
    )
    def forbidden_unconditional_get(_projection_id):
        raise AssertionError("fresh_materialization_must_use_eligible_uow_query")

    uow.get_group_message_projection = forbidden_unconditional_get
    materialized = _materialize_group_context_window(
        uow, authority, window, business_scope=scope, now=NOW
    )
    assert window.view().usage.latest_selected_fragments == 23
    assert window.view().usage.history_selected_fragments == 96
    assert window.view().usage.selected_fragments == 119
    assert window.view().omissions.character_limit == 1
    assert window.view().omissions.fragment_limit == 1
    assert all(len(item._text) <= 500 for item in materialized._fragments)


@pytest.mark.parametrize("drift", ["purge", "member", "mapping"])
def test_built_window_revalidates_before_fresh_text_materialization(drift) -> None:
    fixture = _fixture()
    uow, _actor, _workspace, member, *_middle, mapping, scope = fixture
    projection = _add_projection(uow, mapping, text="never stale")
    authority = _authority(fixture)
    window = build_group_context_window(uow, authority, business_scope=scope, now=NOW)
    before = _materialize_group_context_window(
        uow, authority, window, business_scope=scope, now=NOW
    )
    assert [fragment._text for fragment in before._fragments] == ["never stale"]
    assert not hasattr(window, "_selected_fragments")
    assert "never stale" not in repr(window)

    if drift == "purge":
        projection.content_fragment = ""
        projection.lifecycle_status = "purged"
    elif drift == "member":
        member.status = "inactive"
    else:
        mapping.mapping_version += 1
    after = _materialize_group_context_window(
        uow, authority, window, business_scope=scope, now=NOW
    )
    assert after._fragments == ()
    assert after._available is False


def test_window_character_budget_compression_and_expiry_are_count_only() -> None:
    fixture = _fixture()
    uow, _actor, _workspace, *_middle, mapping, scope = fixture
    for index in range(49):
        _add_projection(
            uow,
            mapping,
            text=str(index % 10) * 500,
            event_at=NOW - timedelta(minutes=index),
        )
    expired = _add_projection(
        uow,
        mapping,
        text="secret expired",
        event_at=NOW - timedelta(days=31),
        expires=NOW - timedelta(days=1),
    )
    authority = _authority(fixture)
    window = build_group_context_window(uow, authority, business_scope=scope, now=NOW)
    assert window.view().usage.raw_selected_chars == 24_500
    assert window.view().compression_required is True
    assert window.view().omissions.expired == 1
    assert expired.content_fragment not in repr(window.view())


def test_window_selects_only_verified_group_provenance_and_ignores_unknown() -> None:
    fixture = _fixture()
    uow, _actor, _workspace, *_middle, mapping, scope = fixture
    unknown = _add_projection(
        uow,
        mapping,
        text="unknown must never load",
        event_at=NOW,
        source_chat_type="unknown",
    )
    valid = _add_projection(
        uow,
        mapping,
        text="verified supergroup",
        event_at=NOW - timedelta(minutes=1),
        source_chat_type="supergroup",
    )
    authority = _authority(fixture)
    window = build_group_context_window(
        uow, authority, business_scope=scope, now=NOW
    )
    materialized = _materialize_group_context_window(
        uow, authority, window, business_scope=scope, now=NOW
    )
    assert [item._text for item in materialized._fragments] == [
        valid.content_fragment
    ]
    assert unknown.content_fragment not in repr(window)
    assert "source_chat_type" not in window.view().model_dump(mode="python")

    valid.source_chat_type = "unknown"
    after_drift = _materialize_group_context_window(
        uow, authority, window, business_scope=scope, now=NOW
    )
    assert after_drift._fragments == ()
    assert after_drift._available is False


def test_window_enforces_thirty_day_retention_even_if_stored_expiry_is_longer() -> None:
    fixture = _fixture()
    uow, _actor, _workspace, *_middle, mapping, scope = fixture
    old = _add_projection(
        uow,
        mapping,
        text="must age out",
        event_at=NOW - timedelta(days=31),
        expires=NOW + timedelta(days=60),
    )
    window = build_group_context_window(
        uow, _authority(fixture), business_scope=scope, now=NOW
    )
    assert window.view().status == "group_context_unavailable"
    assert window.view().usage.selected_fragments == 0
    assert window.view().usage.raw_selected_chars == 0
    assert window.view().omissions.expired == 1
    assert old.content_fragment not in repr(window.view())


def test_factory_rejects_any_invalid_employee_accessible_table_id() -> None:
    fixture = _fixture()
    uow, owner, workspace, *_middle, employee, _binding, mapping, scope = fixture
    foreign_workspace = create_workspace(
        uow, name="foreign", owner_user_id=owner.actor_id, actor=owner
    )
    foreign_base = create_base(uow, foreign_workspace.id, name="foreign", actor=owner)
    foreign_table = create_table(
        uow, foreign_base.id, name="foreign", key="foreign", actor=owner
    )
    employee.accessible_tables.append(str(foreign_table.id))
    _add_projection(uow, mapping, text="must not become visible")
    authority = Stage08GroupContextAuthorityFactory.build(
        uow, actor=owner, employee_id=employee.id, workspace_id=workspace.id
    )
    assert (
        build_group_context_window(
            uow, authority, business_scope=scope, now=NOW
        ).view().status
        == "group_context_unavailable"
    )


def test_window_rejects_non_utc_now_and_scope_version_or_relation_drift() -> None:
    fixture = _fixture()
    uow, _actor, _workspace, *_middle, project, _employee, _binding, mapping, scope = fixture
    _add_projection(uow, mapping)
    authority = _authority(fixture)
    with pytest.raises(PlatformValidationError, match="group_context_now_invalid"):
        build_group_context_window(
            uow,
            authority,
            business_scope=scope,
            now=NOW.astimezone(timezone(timedelta(hours=8))),
        )
    project.version += 1
    assert (
        build_group_context_window(
            uow, authority, business_scope=scope, now=NOW
        ).view().status
        == "group_context_unavailable"
    )


def test_authorised_purge_is_idempotent_and_drift_invalidates_handle() -> None:
    fixture = _fixture()
    uow, _actor, _workspace, *_middle, mapping, scope = fixture
    projection = _add_projection(uow, mapping, text="erase me")
    authority = _authority(fixture)
    window = build_group_context_window(uow, authority, business_scope=scope, now=NOW)
    handle = window._projection_handles[0]
    first = purge_group_context_projection(
        uow, authority, projection_handle=handle, now=NOW
    )
    second = purge_group_context_projection(
        uow, authority, projection_handle=handle, now=NOW
    )
    assert first.purged_count == 1
    assert second.purged_count == 0
    assert projection.content_fragment == ""
    assert projection.lifecycle_status == "purged"
    assert projection.source_chat_type == "group"

    replacement = _add_projection(uow, mapping, text="must remain")
    current = build_group_context_window(uow, authority, business_scope=scope, now=NOW)
    mapping.mapping_version += 1
    denied = purge_group_context_projection(
        uow,
        authority,
        projection_handle=current._projection_handles[0],
        now=NOW,
    )
    assert denied.purged_count == 0
    assert replacement.content_fragment == "must remain"


def test_authority_and_projection_handle_are_private_non_serializable_objects() -> None:
    fixture = _fixture()
    uow, actor, workspace, *_middle, employee, _binding, mapping, scope = fixture
    _add_projection(uow, mapping)
    authority = _authority(fixture)
    window = build_group_context_window(
        uow, authority, business_scope=scope, now=NOW
    )
    assert not is_dataclass(authority)
    assert not hasattr(authority, "model_dump")
    assert not hasattr(window._projection_handles[0], "model_dump")
    with pytest.raises(TypeError):
        json.dumps(authority)
    with pytest.raises(TypeError, match="group_context_authority_private"):
        _GroupContextAuthority(
            object(),
            actor=actor,
            employee_id=employee.id,
            workspace_id=workspace.id,
        )


def test_expiry_purge_erases_only_expired_active_fragments_without_other_mutations() -> None:
    fixture = _fixture()
    uow, _actor, _workspace, *_middle, mapping, _scope = fixture
    expired = _add_projection(
        uow,
        mapping,
        text="expired",
        event_at=NOW - timedelta(days=30),
        expires=NOW,
    )
    current = _add_projection(uow, mapping, text="current")
    before = (
        len(uow.memory_items),
        len(uow.outbox_events),
        len(uow.audit_events),
        len(uow.agent_runs),
    )
    first = purge_expired_group_context_projections(uow, now=NOW)
    second = purge_expired_group_context_projections(uow, now=NOW)
    assert first.purged_count == 1
    assert second.purged_count == 0
    assert expired.content_fragment == ""
    assert expired.lifecycle_status == "purged"
    assert expired.source_chat_type == "group"
    assert current.content_fragment == "current"
    assert before == (
        len(uow.memory_items),
        len(uow.outbox_events),
        len(uow.audit_events),
        len(uow.agent_runs),
    )


def test_expiry_purge_enforces_event_time_retention_when_stored_expiry_is_longer() -> None:
    fixture = _fixture()
    uow, _actor, _workspace, *_middle, mapping, _scope = fixture
    stale = _add_projection(
        uow,
        mapping,
        text="stale despite extended expiry",
        event_at=NOW - timedelta(days=31),
        expires=NOW + timedelta(days=60),
    )
    result = purge_expired_group_context_projections(uow, now=NOW)
    assert result.purged_count == 1
    assert stale.lifecycle_status == "purged"
    assert stale.content_fragment == ""
