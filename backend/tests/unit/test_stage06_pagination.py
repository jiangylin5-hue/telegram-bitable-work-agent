from dataclasses import dataclass
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    create_digital_employee,
    create_notification_request,
    invoke_digital_employee,
)
from app.services.stage06_pagination import (
    Stage06PaginationError,
    bounded_page_size,
    paginate_items,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


@dataclass
class _Item:
    id: UUID


def _items(count: int) -> list[_Item]:
    return [_Item(id=UUID(int=index + 1)) for index in range(count)]


def test_stage06_page_limit_above_two_hundred_is_rejected() -> None:
    with pytest.raises(Stage06PaginationError) as denied:
        bounded_page_size(201)

    assert denied.value.code == "page_limit_exceeded"


def test_stage06_cursor_pages_have_no_duplicates_or_missing_items() -> None:
    items = _items(75)

    first = paginate_items(items, limit=50, cursor=None)
    second = paginate_items(items, limit=50, cursor=first.next_cursor)

    first_ids = [str(item.id) for item in first.items]
    second_ids = [str(item.id) for item in second.items]
    assert set(first_ids).isdisjoint(second_ids)
    assert first_ids + second_ids == [str(item.id) for item in items]
    assert first.has_more is True
    assert second.has_more is False
    assert second.next_cursor is None


def test_stage06_view_records_api_returns_additive_cursor_metadata() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Name", key="name", field_type="text")
    for index in range(3):
        create_record(uow, table.id, values={"name": f"row-{index}"})
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Grid",
        view_type="grid",
        config={"fields": ["name"]},
    )
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        headers = {"X-Stage06-User-Id": "owner-1"}
        first = client.get(f"/views/{view.id}/records?limit=2", headers=headers)
        second = client.get(
            f"/views/{view.id}/records",
            headers=headers,
            params={"limit": 2, "cursor": first.json()["next_cursor"]},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["records"]) == 2
    assert first.json()["has_more"] is True
    assert len(second.json()["records"]) == 1
    assert second.json()["has_more"] is False
    first_ids = {item["id"] for item in first.json()["records"]}
    second_ids = {item["id"] for item in second.json()["records"]}
    assert first_ids.isdisjoint(second_ids)


def test_stage06_runtime_lists_return_bounded_cursor_metadata() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="Acme",
        owner_user_id="owner-1",
        actor=actor,
    )
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    table = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
    create_field(uow, table.id, name="Status", key="status", field_type="status", actor=actor)
    records = [
        create_record(uow, table.id, values={"status": "new"}, actor=actor)
        for _index in range(3)
    ]
    employee = create_digital_employee(
        uow,
        base.id,
        name="Ops",
        description="Ops",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[],
        allowed_actions=["draft_update"],
        actor=actor,
    )
    for record in records:
        invoke_digital_employee(
            uow,
            employee.id,
            action="draft_update",
            record_id=record.id,
            proposed_values={"status": "done"},
            actor=actor,
        )
        create_notification_request(
            uow,
            workspace_id=workspace.id,
            base_id=base.id,
            source_record_id=record.id,
            channel="telegram",
            target={"telegram_chat_id": "chat-1"},
            message_payload={"text": "dry-run"},
            send_policy={},
            actor=actor,
        )
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        headers = {"X-Stage06-User-Id": "owner-1"}
        drafts = client.get(
            f"/bases/{base.id}/record-change-drafts?limit=2",
            headers=headers,
        )
        notifications = client.get(
            f"/bases/{base.id}/notification-requests?limit=2",
            headers=headers,
        )
        audit = client.get(
            f"/bases/{base.id}/audit-events?limit=2",
            headers=headers,
        )

    assert len(drafts.json()["drafts"]) == 2
    assert drafts.json()["has_more"] is True
    assert drafts.json()["next_cursor"]
    assert len(notifications.json()["requests"]) == 2
    assert notifications.json()["has_more"] is True
    assert notifications.json()["next_cursor"]
    assert len(audit.json()["events"]) == 2
    assert audit.json()["has_more"] is True
    assert audit.json()["next_cursor"]
