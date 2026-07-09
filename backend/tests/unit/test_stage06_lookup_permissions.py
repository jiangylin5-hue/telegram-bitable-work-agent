from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
    list_view_records,
)


def test_stage06_lookup_omits_hidden_target_field() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    target_table = create_table(uow, base.id, name="Secrets", key="secrets")
    create_field(
        uow,
        target_table.id,
        name="Private Note",
        key="private_note",
        field_type="text",
        permission_policy={"viewer": "hidden"},
    )
    target_record = create_record(
        uow,
        target_table.id,
        values={"private_note": "hidden-value"},
    )

    source_table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(
        uow,
        source_table.id,
        name="Secret Link",
        key="secret_link",
        field_type="linked_record",
        options={"target_table_id": str(target_table.id)},
    )
    create_field(
        uow,
        source_table.id,
        name="Private Note Lookup",
        key="private_note_lookup",
        field_type="lookup",
        options={
            "source_field_key": "secret_link",
            "target_field_key": "private_note",
        },
    )
    source_record = create_record(
        uow,
        source_table.id,
        values={"secret_link": [str(target_record.id)]},
    )
    view = create_form_view(
        uow,
        base.id,
        source_table.id,
        name="Customer Grid",
        view_type="grid",
        config={"fields": ["private_note_lookup"]},
    )

    payload = list_view_records(
        uow,
        view.id,
        actor=Actor(actor_type="user", actor_id="viewer-1", role="viewer"),
    )

    assert payload["records"] == [{"id": str(source_record.id), "fields": {}}]
    assert "hidden-value" not in str(payload)
