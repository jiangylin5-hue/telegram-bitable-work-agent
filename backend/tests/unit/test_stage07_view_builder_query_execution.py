from uuid import UUID

from app.schemas.stage06_platform import ViewInitializationRequest
from app.services.permissions import Actor
from app.services.stage06_pagination import paginate_items
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    initialize_v1_view,
    list_view_records,
)


def test_ordered_pagination_keeps_server_sort_order_after_cursor() -> None:
    items = [_Item(UUID(int=value)) for value in (3, 1, 2)]

    first = paginate_items(items, limit=2, cursor=None, preserve_order=True)
    second = paginate_items(items, limit=2, cursor=first.next_cursor, preserve_order=True)

    assert [item.id.int for item in first.items] == [3, 1]
    assert [item.id.int for item in second.items] == [2]
    assert first.has_more is True
    assert second.has_more is False


def test_v1_filter_and_stable_sorts_execute_before_limit_and_cursor() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Name", key="name", field_type="text")
    create_field(uow, table.id, name="Score", key="score", field_type="number")
    records = [
        create_record(uow, table.id, values={"name": "low", "score": 1}),
        create_record(uow, table.id, values={"name": "middle", "score": 3}),
        create_record(uow, table.id, values={"name": "high", "score": 5}),
        create_record(uow, table.id, values={"name": "also-middle", "score": 3}),
    ]
    for index, record in enumerate(records, start=1):
        record.id = UUID(int=index)
    view = initialize_v1_view(
        uow,
        table.id,
        request=ViewInitializationRequest.model_validate(
            {
                "name": "Ranked",
                "view_type": "grid",
                "presentation": {
                    "view_type": "grid",
                    "visible_field_keys": ["name", "score"],
                    "filters": [{"field_key": "score", "operator": "gte", "value": 3}],
                    "sort_rules": [
                        {"field_key": "score", "direction": "desc"},
                        {"field_key": "name", "direction": "asc"},
                    ],
                    "group_by_field_key": None,
                },
            }
        ),
        idempotency_key="query-order",
        actor=actor,
    ).view

    first = list_view_records(uow, view.id, actor=actor, limit=2)
    second = list_view_records(
        uow,
        view.id,
        actor=actor,
        limit=2,
        cursor=first["next_cursor"],
    )

    assert [row["fields"]["name"] for row in first["records"]] == ["high", "also-middle"]
    assert [row["fields"]["name"] for row in second["records"]] == ["middle"]
    assert first["has_more"] is True
    assert second["has_more"] is False


def test_v1_group_metadata_and_group_order_are_server_owned() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Name", key="name", field_type="text")
    create_field(
        uow,
        table.id,
        name="State",
        key="state",
        field_type="status",
        options={"choices": ["active", "closed"]},
    )
    records = [
        create_record(uow, table.id, values={"name": "aardvark", "state": "closed"}),
        create_record(uow, table.id, values={"name": "beta", "state": "active"}),
        create_record(uow, table.id, values={"name": "alpha", "state": "active"}),
    ]
    for index, record in enumerate(records, start=1):
        record.id = UUID(int=index)
    view = initialize_v1_view(
        uow,
        table.id,
        request=ViewInitializationRequest.model_validate(
            {
                "name": "Grouped",
                "view_type": "grid",
                "presentation": {
                    "view_type": "grid",
                    "visible_field_keys": ["name"],
                    "filters": [],
                    "sort_rules": [{"field_key": "name", "direction": "asc"}],
                    "group_by_field_key": "state",
                },
            }
        ),
        idempotency_key="query-groups",
        actor=actor,
    ).view

    response = list_view_records(uow, view.id, actor=actor, limit=10)

    assert [row["fields"]["name"] for row in response["records"]] == [
        "alpha",
        "beta",
        "aardvark",
    ]
    assert response["groups"] == [
        {"value": "active", "record_ids": [str(records[2].id), str(records[1].id)]},
        {"value": "closed", "record_ids": [str(records[0].id)]},
    ]


class _Item:
    def __init__(self, item_id: UUID) -> None:
        self.id = item_id
