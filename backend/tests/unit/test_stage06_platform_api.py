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


def test_stage07_base_initialization_returns_safe_receipt_and_replays_same_key() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        headers = {"Idempotency-Key": "base-initialization-1"}
        payload = {"base_name": "客户运营", "table_name": "客户"}

        created = client.post(
            f"/workspaces/{workspace_id}/base-initializations",
            headers=headers,
            json=payload,
        )
        replayed = client.post(
            f"/workspaces/{workspace_id}/base-initializations",
            headers=headers,
            json=payload,
        )

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.json() == created.json()
    assert set(created.json()) == {"base", "table", "default_view"}
    assert set(created.json()["base"]) == {"id", "name", "source_type", "status"}
    assert set(created.json()["table"]) == {"id", "base_id", "name", "key", "status"}
    assert set(created.json()["default_view"]) == {
        "id",
        "base_id",
        "table_id",
        "name",
        "view_type",
        "status",
    }
    assert created.json()["default_view"] == {
        "id": created.json()["default_view"]["id"],
        "base_id": created.json()["base"]["id"],
        "table_id": created.json()["table"]["id"],
        "name": "所有记录",
        "view_type": "grid",
        "status": "active",
    }
    assert len(uow.bases) == 1
    assert len(uow.tables) == 1
    assert len(uow.views) == 1
    assert len(uow.idempotency_records) == 1
    assert [event.event_type for event in uow.audit_events].count(
        "stage06.base_initialized"
    ) == 1


def test_stage07_table_initialization_denies_viewer_without_persisting_resources() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        base_id = client.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "CRM"},
        ).json()["id"]
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(),
                workspace_id=UUID(workspace_id),
                user_id="viewer-1",
                role="viewer",
                status="active",
            )
        )
        client.headers["X-Stage06-User-Id"] = "viewer-1"

        denied = client.post(
            f"/bases/{base_id}/table-initializations",
            headers={"Idempotency-Key": "table-initialization-denied-1"},
            json={"table_name": "待办"},
        )

    assert denied.status_code == 403
    assert uow.list_tables(UUID(base_id)) == []
    assert uow.views == []
    assert uow.idempotency_records == []


def test_stage07_base_initialization_rejects_conflicting_reused_key() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        headers = {"Idempotency-Key": "base-initialization-conflict-1"}
        first = client.post(
            f"/workspaces/{workspace_id}/base-initializations",
            headers=headers,
            json={"base_name": "客户运营", "table_name": "客户"},
        )
        conflict = client.post(
            f"/workspaces/{workspace_id}/base-initializations",
            headers=headers,
            json={"base_name": "客户运营", "table_name": "项目"},
        )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    assert len(uow.bases) == 1
    assert len(uow.tables) == 1
    assert len(uow.views) == 1


def test_stage07_base_initialization_rejects_blank_name_without_resources() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]

        invalid = client.post(
            f"/workspaces/{workspace_id}/base-initializations",
            headers={"Idempotency-Key": "base-initialization-invalid-1"},
            json={"base_name": "  ", "table_name": "客户"},
        )

    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_builder_name"
    assert uow.bases == []
    assert uow.tables == []
    assert uow.views == []
    assert uow.idempotency_records == []
