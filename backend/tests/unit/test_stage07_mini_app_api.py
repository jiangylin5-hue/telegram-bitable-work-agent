from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.models.stage06_runtime import RecordChangeDraft
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


def test_mini_app_bootstrap_only_returns_active_memberships_for_identity() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Owner workspace", "owner_user_id": "owner-1"},
        ).json()["id"]
        client.headers["X-Stage06-User-Id"] = "owner-2"
        other_workspace_id = client.post(
            "/workspaces",
            json={"name": "Other workspace", "owner_user_id": "owner-2"},
        ).json()["id"]
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(),
                workspace_id=UUID(other_workspace_id),
                user_id="owner-1",
                role="viewer",
                status="inactive",
            )
        )

        client.headers["X-Stage06-User-Id"] = "owner-1"
        response = client.get("/mini-app/bootstrap")

    assert response.status_code == 200
    assert response.json() == {
        "identity": {"user_id": "owner-1", "source": "development_header"},
        "workspaces": [
            {
                "id": workspace_id,
                "name": "Owner workspace",
                "slug": "owner-workspace",
                "role": "owner",
                "capabilities": {
                    "can_read_bases": True,
                    "can_manage_workspace": True,
                    "can_manage_schema": True,
                    "can_review_drafts": True,
                },
            }
        ],
    }


def test_workspace_home_returns_safe_base_and_draft_queue_models() -> None:
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
            json={"name": "Operations", "description": "Internal workspace"},
        ).json()["id"]
        draft_id = uuid4()
        uow.add_record_change_draft(
            RecordChangeDraft(
                id=draft_id,
                workspace_id=UUID(workspace_id),
                base_id=UUID(base_id),
                table_id=uuid4(),
                record_id=None,
                draft_type="record_update",
                proposed_values={"sensitive": "must not reach home"},
                before_values={"sensitive": "must not reach home"},
                created_by_type="agent",
                created_by_id="agent-1",
                status="pending_confirmation",
                confirmation_policy={},
                trace_id="trace-1",
                expected_version=1,
            )
        )

        response = client.get(f"/workspaces/{workspace_id}/home")

    assert response.status_code == 200
    body = response.json()
    assert body["recent_bases"] == [
        {
            "id": base_id,
            "name": "Operations",
            "source_type": "blank",
        }
    ]
    assert body["queue"] == [
        {
            "id": str(draft_id),
            "kind": "record_change_draft",
            "title": "待确认变更",
            "status": "pending_confirmation",
            "destination": {"base_id": base_id, "draft_id": str(draft_id)},
            "action_availability": {"can_confirm": True, "can_reject": True},
        }
    ]
    assert "sensitive" not in response.text


def test_workspace_home_denies_non_members() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        client.headers["X-Stage06-User-Id"] = "outsider-1"
        response = client.get(f"/workspaces/{workspace_id}/home")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "stage06_membership_required"


def test_base_canvas_navigation_lists_only_authorized_safe_summaries() -> None:
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
            json={"name": "Operations", "description": "must not be listed"},
        ).json()["id"]
        table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Projects", "key": "projects"},
        ).json()["id"]
        view_id = client.post(
            f"/bases/{base_id}/views",
            json={
                "table_id": table_id,
                "name": "Project Grid",
                "view_type": "grid",
                "config": {"fields": ["hidden-from-navigation"]},
                "permission_policy": {"viewer": "hidden"},
            },
        ).json()["id"]

        bases_response = client.get(f"/workspaces/{workspace_id}/bases")
        tables_response = client.get(f"/bases/{base_id}/tables")
        views_response = client.get(f"/bases/{base_id}/views")

    assert bases_response.status_code == 200
    assert bases_response.json() == {
        "bases": [
            {
                "id": base_id,
                "name": "Operations",
                "source_type": "blank",
                "status": "active",
            }
        ]
    }
    assert tables_response.status_code == 200
    assert tables_response.json() == {
        "tables": [
            {
                "id": table_id,
                "base_id": base_id,
                "name": "Projects",
                "key": "projects",
                "status": "active",
            }
        ]
    }
    assert views_response.status_code == 200
    assert views_response.json() == {
        "views": [
            {
                "id": view_id,
                "base_id": base_id,
                "table_id": table_id,
                "name": "Project Grid",
                "view_type": "grid",
                "status": "active",
            }
        ]
    }
    assert "hidden-from-navigation" not in views_response.text
    assert "permission_policy" not in views_response.text


def test_base_canvas_navigation_denies_cross_workspace_access() -> None:
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
            json={"name": "Operations"},
        ).json()["id"]
        client.headers["X-Stage06-User-Id"] = "outsider-1"
        bases_response = client.get(f"/workspaces/{workspace_id}/bases")
        tables_response = client.get(f"/bases/{base_id}/tables")
        views_response = client.get(f"/bases/{base_id}/views")

    assert bases_response.status_code == 403
    assert tables_response.status_code == 403
    assert views_response.status_code == 403


def test_view_presentation_record_detail_and_schema_hide_inaccessible_fields() -> None:
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
            json={"name": "Operations"},
        ).json()["id"]
        table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Projects", "key": "projects"},
        ).json()["id"]
        client.post(
            f"/tables/{table_id}/fields",
            json={"name": "Name", "key": "name", "field_type": "text"},
        )
        client.post(
            f"/tables/{table_id}/fields",
            json={
                "name": "Internal", "key": "internal", "field_type": "text",
                "permission_policy": {"viewer": "hidden"},
            },
        )
        client.post(
            f"/tables/{table_id}/fields",
            json={"name": "Due", "key": "due", "field_type": "date"},
        )
        record_id = client.post(
            f"/tables/{table_id}/records",
            json={"values": {"name": "Ada", "internal": "secret", "due": "2026-07-10"}},
        ).json()["id"]
        view_id = client.post(
            f"/bases/{base_id}/views",
            json={
                "table_id": table_id,
                "name": "Project Calendar",
                "view_type": "calendar",
                "config": {
                    "fields": ["name", "internal", "due"],
                    "group_by_field_key": "internal",
                    "date_field_key": "due",
                },
            },
        ).json()["id"]
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(), workspace_id=UUID(workspace_id), user_id="viewer-1",
                role="viewer", status="active",
            )
        )

        client.headers["X-Stage06-User-Id"] = "viewer-1"
        schema_response = client.get(f"/tables/{table_id}/schema")
        presentation_response = client.get(f"/views/{view_id}/presentation")
        record_response = client.get(f"/records/{record_id}")

    assert schema_response.status_code == 200
    assert [field["key"] for field in schema_response.json()["fields"]] == ["name", "due"]
    assert presentation_response.status_code == 200
    assert presentation_response.json() == {
        "view_id": view_id,
        "table_id": table_id,
        "view_type": "calendar",
        "visible_field_keys": ["name", "due"],
        "group_by_field_key": None,
        "date_field_key": "due",
        "form_field_keys": ["name", "due"],
    }
    assert record_response.status_code == 200
    assert record_response.json()["values"] == {"name": "Ada", "due": "2026-07-10"}
    assert "secret" not in record_response.text
