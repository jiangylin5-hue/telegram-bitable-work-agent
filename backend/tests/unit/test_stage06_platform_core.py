from pytest import raises

from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
    get_table_schema,
    initialize_base,
    initialize_table,
    list_view_records,
    update_record,
)


def test_stage06_field_type_allowlist_rejects_unsupported_types() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")

    with raises(PlatformValidationError) as exc:
        create_field(
            uow,
            table.id,
            name="Formula",
            key="formula",
            field_type="formula",
        )

    assert exc.value.code == "unsupported_field_type"


def test_stage06_record_values_validate_against_field_metadata() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Name", key="name", field_type="text", required=True)
    create_field(uow, table.id, name="Score", key="score", field_type="number")
    create_field(uow, table.id, name="Active", key="active", field_type="checkbox")

    with raises(PlatformValidationError) as missing:
        create_record(uow, table.id, values={"score": 10})

    assert missing.value.code == "missing_required_field"

    with raises(PlatformValidationError) as wrong_type:
        create_record(uow, table.id, values={"name": "Ada", "score": "high"})

    assert wrong_type.value.code == "invalid_field_value"

    record = create_record(
        uow,
        table.id,
        values={"name": "Ada", "score": 10, "active": True},
    )

    assert record.values == {"name": "Ada", "score": 10, "active": True}
    assert record.version == 1


def test_stage06_schema_introspection_returns_ordered_fields() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="Projects")
    table = create_table(uow, base.id, name="Tasks", key="tasks")
    create_field(uow, table.id, name="Title", key="title", field_type="text")
    create_field(uow, table.id, name="Status", key="status", field_type="status")

    schema = get_table_schema(uow, table.id)

    assert schema["table"]["key"] == "tasks"
    assert [field["key"] for field in schema["fields"]] == ["title", "status"]
    assert [field["field_type"] for field in schema["fields"]] == ["text", "status"]


def test_stage06_view_records_apply_basic_field_permissions() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Name", key="name", field_type="text")
    create_field(
        uow,
        table.id,
        name="Internal Notes",
        key="internal_notes",
        field_type="text",
        permission_policy={"viewer": "hidden", "operator": "read", "admin": "write"},
    )
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Customer Grid",
        view_type="grid",
        config={"fields": ["name", "internal_notes"]},
    )
    create_record(
        uow,
        table.id,
        values={"name": "Ada Co", "internal_notes": "private"},
    )

    response = list_view_records(
        uow,
        view.id,
        actor=Actor(actor_type="user", actor_id="viewer-1", role="viewer"),
    )

    assert response == {
        "view_id": str(view.id),
        "records": [{"id": response["records"][0]["id"], "fields": {"name": "Ada Co"}}],
        "trace_id": f"stage06:view:{view.id}",
        "next_cursor": None,
        "has_more": False,
    }


def test_stage06_record_update_checks_write_policy_version_and_writes_audit() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(
        uow,
        table.id,
        name="Name",
        key="name",
        field_type="text",
        permission_policy={"viewer": "read", "operator": "write"},
    )
    create_field(
        uow,
        table.id,
        name="Internal Notes",
        key="internal_notes",
        field_type="text",
        permission_policy={"viewer": "hidden", "operator": "write"},
    )
    record = create_record(
        uow,
        table.id,
        values={"name": "Ada", "internal_notes": "old"},
    )

    updated = update_record(
        uow,
        record.id,
        values={"name": "Ada Co"},
        expected_version=1,
        actor=Actor(actor_type="user", actor_id="operator-1", role="operator"),
    )

    assert updated.values == {"name": "Ada Co", "internal_notes": "old"}
    assert updated.version == 2
    assert uow.audit_events[-1].event_type == "stage06.record_updated"
    assert uow.audit_events[-1].before_state == {"field_keys": ["name"]}
    assert uow.audit_events[-1].after_state == {
        "field_keys": ["name"],
        "version": 2,
    }

    with raises(PlatformValidationError) as stale:
        update_record(
            uow,
            record.id,
            values={"name": "Ada Again"},
            expected_version=1,
            actor=Actor(actor_type="user", actor_id="operator-1", role="operator"),
        )

    assert stale.value.code == "record_version_conflict"

    with raises(PlatformValidationError) as denied:
        update_record(
            uow,
            record.id,
            values={"internal_notes": "secret"},
            expected_version=2,
            actor=Actor(actor_type="user", actor_id="viewer-1", role="viewer"),
        )

    assert denied.value.code == "permission_denied"
    assert uow.audit_events[-1].event_type == "permission_denied"
    assert "secret" not in str(uow.audit_events[-1].permission_snapshot)


def test_stage06_linked_records_are_persisted_and_lookup_values_resolve_in_views() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="Projects")
    customers = create_table(uow, base.id, name="Customers", key="customers")
    tasks = create_table(uow, base.id, name="Tasks", key="tasks")
    create_field(uow, customers.id, name="Name", key="name", field_type="text")
    create_field(uow, tasks.id, name="Title", key="title", field_type="text")
    create_field(
        uow,
        tasks.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customers.id)},
    )
    create_field(
        uow,
        tasks.id,
        name="Customer Name",
        key="customer_name",
        field_type="lookup",
        options={"source_field_key": "customer", "target_field_key": "name"},
    )
    customer = create_record(uow, customers.id, values={"name": "Ada Co"})
    task = create_record(
        uow,
        tasks.id,
        values={"title": "Launch", "customer": [str(customer.id)]},
    )
    view = create_form_view(
        uow,
        base.id,
        tasks.id,
        name="Task Grid",
        view_type="grid",
        config={"fields": ["title", "customer", "customer_name"]},
    )

    assert len(uow.record_links) == 1
    assert uow.record_links[0].source_record_id == task.id
    assert uow.record_links[0].target_record_id == customer.id

    response = list_view_records(
        uow,
        view.id,
        actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
    )

    assert response["records"] == [
        {
            "id": str(task.id),
            "fields": {
                "title": "Launch",
                "customer": [str(customer.id)],
                "customer_name": ["Ada Co"],
            },
        }
    ]


def test_stage06_view_permission_denial_writes_audit_without_record_values() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Name", key="name", field_type="text")
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Private Grid",
        view_type="grid",
        config={"fields": ["name"]},
        permission_policy={"viewer": "none"},
    )
    create_record(uow, table.id, values={"name": "Ada Co"})

    with raises(PlatformValidationError) as denied:
        list_view_records(
            uow,
            view.id,
            actor=Actor(actor_type="user", actor_id="viewer-1", role="viewer"),
        )

    assert denied.value.code == "permission_denied"
    assert uow.audit_events[-1].event_type == "permission_denied"
    assert "Ada Co" not in str(uow.audit_events[-1].permission_snapshot)


def test_initialize_base_creates_one_zero_field_default_grid_and_parent_audit() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")

    result = initialize_base(
        uow,
        workspace.id,
        base_name="客户运营",
        table_name="客户",
        actor=actor,
    )

    assert result.base.workspace_id == workspace.id
    assert result.table.base_id == result.base.id
    assert result.table.key.startswith("tbl_")
    assert uow.list_fields(result.table.id) == []
    assert result.default_view.table_id == result.table.id
    assert result.default_view.name == "所有记录"
    assert result.default_view.view_type == "grid"
    assert result.default_view.config == {"fields": []}
    assert result.default_view.permission_policy == {}
    assert result.default_view.is_default is True
    assert uow.audit_events[-1].event_type == "stage06.base_initialized"
    assert uow.audit_events[-1].after_state == {
        "resource_map": {
            "base_id": str(result.base.id),
            "table_id": str(result.table.id),
            "view_id": str(result.default_view.id),
        }
    }


def test_initialize_table_adds_only_its_own_default_grid() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")

    result = initialize_table(uow, base.id, table_name="待办", actor=actor)

    assert uow.list_tables(base.id) == [result.table]
    assert uow.list_views(result.table.id) == [result.default_view]
    assert result.default_view.is_default is True
    assert uow.list_fields(result.table.id) == []
    assert uow.audit_events[-1].event_type == "stage06.table_initialized"
    assert uow.audit_events[-1].after_state == {
        "resource_map": {
            "base_id": str(base.id),
            "table_id": str(result.table.id),
            "view_id": str(result.default_view.id),
        }
    }


def test_initialize_base_rejects_blank_display_name_without_creating_resources() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")

    with raises(PlatformValidationError) as invalid:
        initialize_base(
            uow,
            workspace.id,
            base_name="  ",
            table_name="客户",
            actor=actor,
        )

    assert invalid.value.code == "invalid_builder_name"
    assert uow.list_bases(workspace.id) == []
