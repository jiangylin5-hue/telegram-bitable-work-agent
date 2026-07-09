from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from app.services.stage06_platform import create_form_view


def test_stage06_platform_api_creates_base_table_field_record_and_schema() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_response = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        )
        workspace_id = workspace_response.json()["id"]

        base_response = client.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "CRM"},
        )
        base_id = base_response.json()["id"]

        table_response = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Customers", "key": "customers"},
        )
        table_id = table_response.json()["id"]

        field_response = client.post(
            f"/tables/{table_id}/fields",
            json={
                "name": "Name",
                "key": "name",
                "field_type": "text",
                "required": True,
            },
        )

        record_response = client.post(
            f"/tables/{table_id}/records",
            json={"values": {"name": "Ada Co"}},
        )

        schema_response = client.get(f"/tables/{table_id}/schema")

    assert workspace_response.status_code == 200
    assert base_response.status_code == 200
    assert table_response.status_code == 200
    assert field_response.status_code == 200
    assert record_response.status_code == 200
    assert schema_response.status_code == 200
    assert schema_response.json()["table"]["key"] == "customers"
    assert schema_response.json()["fields"][0]["key"] == "name"


def test_stage06_platform_api_reads_updates_and_filters_view_records() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_response = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        )
        workspace_id = workspace_response.json()["id"]
        workspace_read_response = client.get(f"/workspaces/{workspace_id}")

        base_response = client.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "CRM"},
        )
        base_id = base_response.json()["id"]
        base_read_response = client.get(f"/bases/{base_id}")

        table_response = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Customers", "key": "customers"},
        )
        table_id = table_response.json()["id"]

        client.post(
            f"/tables/{table_id}/fields",
            json={
                "name": "Name",
                "key": "name",
                "field_type": "text",
                "permission_policy": {"viewer": "read", "operator": "write"},
            },
        )
        client.post(
            f"/tables/{table_id}/fields",
            json={
                "name": "Internal Notes",
                "key": "internal_notes",
                "field_type": "text",
                "permission_policy": {"viewer": "hidden", "operator": "write"},
            },
        )
        record_response = client.post(
            f"/tables/{table_id}/records",
            json={"values": {"name": "Ada", "internal_notes": "old"}},
        )
        record_id = record_response.json()["id"]

        view = create_form_view(
            uow,
            UUID(base_id),
            UUID(table_id),
            name="Customer Grid",
            view_type="grid",
            config={"fields": ["name", "internal_notes"]},
        )
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(),
                workspace_id=UUID(workspace_id),
                user_id="operator-1",
                role="operator",
                status="active",
            )
        )
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(),
                workspace_id=UUID(workspace_id),
                user_id="viewer-1",
                role="viewer",
                status="active",
            )
        )
        client.headers["X-Stage06-User-Id"] = "operator-1"
        update_response = client.patch(
            f"/records/{record_id}",
            json={"values": {"name": "Ada Co"}, "expected_version": 1},
        )

        client.headers["X-Stage06-User-Id"] = "viewer-1"
        view_response = client.get(f"/views/{view.id}/records")

    assert workspace_read_response.status_code == 200
    assert workspace_read_response.json()["id"] == workspace_id
    assert base_read_response.status_code == 200
    assert base_read_response.json()["id"] == base_id
    assert update_response.status_code == 200
    assert update_response.json()["version"] == 2
    assert view_response.status_code == 200
    assert view_response.json()["records"] == [
        {"id": record_id, "fields": {"name": "Ada Co"}}
    ]
    assert "stage06.workspace_created" in {
        event.event_type for event in uow.audit_events
    }
    assert "stage06.record_updated" in {
        event.event_type for event in uow.audit_events
    }


def test_stage06_platform_api_lists_workspace_members() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_response = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        )
        workspace_id = workspace_response.json()["id"]
        members_response = client.get(f"/workspaces/{workspace_id}/members")

    assert members_response.status_code == 200
    assert members_response.json() == {
        "members": [
            {
                "id": str(uow.workspace_members[0].id),
                "workspace_id": workspace_id,
                "user_id": "owner-1",
                "role": "owner",
                "status": "active",
            }
        ]
    }
