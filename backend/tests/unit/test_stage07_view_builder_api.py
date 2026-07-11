from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


def test_v1_routes_return_only_safe_projection_and_enforce_member_roles() -> None:
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
        table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Customers", "key": "customers"},
        ).json()["id"]
        for name, key, field_type, options in (
            ("Name", "name", "text", {}),
            ("State", "state", "status", {"choices": ["active", "closed"]}),
        ):
            response = client.post(
                f"/tables/{table_id}/fields",
                json={
                    "name": name,
                    "key": key,
                    "field_type": field_type,
                    "options": options,
                },
            )
            assert response.status_code == 200
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(),
                workspace_id=UUID(workspace_id),
                user_id="editor-1",
                role="builder",
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

        context_response = client.get(f"/tables/{table_id}/view-builder-context")
        assert context_response.status_code == 200
        assert {"permission_policy", "owner_user_id", "config", "role", "status"}.isdisjoint(
            context_response.json()["member_candidates"][0]
        )
        context_fields = {
            field["key"]: field for field in context_response.json()["fields"]
        }
        assert context_fields["state"]["field_id"]
        assert context_fields["state"]["filter_values"] == ["active", "closed"]
        assert context_fields["name"]["filter_values"] == []
        assert {"options", "permission_policy"}.isdisjoint(context_fields["state"])

        command = {
            "name": "Ranked",
            "view_type": "grid",
            "presentation": {
                "view_type": "grid",
                "visible_field_keys": ["name", "state"],
                "filters": [],
                "sort_rules": [{"field_key": "name", "direction": "asc"}],
                "group_by_field_key": "state",
            },
        }
        rejected_raw_scope = client.post(
            f"/tables/{table_id}/view-initializations",
            json={**command, "scope": "restricted"},
            headers={"Idempotency-Key": "v1-raw-scope"},
        )
        created = client.post(
            f"/tables/{table_id}/view-initializations",
            json=command,
            headers={"Idempotency-Key": "v1-safe-route"},
        )
        replayed = client.post(
            f"/tables/{table_id}/view-initializations",
            json=command,
            headers={"Idempotency-Key": "v1-safe-route"},
        )

        assert created.status_code == 201
        assert replayed.status_code == 200
        assert rejected_raw_scope.status_code == 422
        assert created.json()["view"] == replayed.json()["view"]
        assert {"permission_policy", "owner_user_id", "config"}.isdisjoint(
            created.json()["view"]
        )
        view_id = created.json()["view"]["id"]

        builder = client.get(f"/views/{view_id}/builder")
        assert builder.status_code == 200
        assert {"permission_policy", "owner_user_id", "config"}.isdisjoint(builder.json())
        assert {"options", "permission_policy"}.isdisjoint(builder.json()["fields"][0])

        replaced_members = client.put(
            f"/views/{view_id}/members",
            json={
                "expected_version": 1,
                "members": [
                    {"user_id": "editor-1", "access_level": "editor"},
                    {"user_id": "viewer-1", "access_level": "viewer"},
                ],
            },
        )
        assert replaced_members.status_code == 200
        assert replaced_members.json()["version"] == 2
        assert {"role", "status", "workspace_id"}.isdisjoint(
            replaced_members.json()["members"][0]
        )

        client.headers["X-Stage06-User-Id"] = "editor-1"
        edited = client.patch(
            f"/views/{view_id}/presentation",
            json={
                "expected_version": 2,
                "name": "Ranked by name",
                "presentation": command["presentation"],
            },
        )
        editor_builder = client.get(f"/views/{view_id}/builder")
        assert edited.status_code == 200
        assert edited.json()["version"] == 3
        assert editor_builder.status_code == 200
        assert editor_builder.json()["members"] == []
        stale_edit = client.patch(
            f"/views/{view_id}/presentation",
            json={"expected_version": 2, "presentation": command["presentation"]},
        )
        assert stale_edit.status_code == 409
        assert stale_edit.json()["detail"] == {
            "code": "view_version_conflict",
            "message": "view_version_conflict",
        }

        client.headers["X-Stage06-User-Id"] = "viewer-1"
        denied_builder = client.get(f"/views/{view_id}/builder")
        denied_patch = client.patch(
            f"/views/{view_id}/presentation",
            json={"expected_version": 3, "presentation": command["presentation"]},
        )
        assert denied_builder.status_code == 403
        assert denied_patch.status_code == 403
        assert denied_builder.json()["detail"] == {
            "code": "view_access_denied",
            "message": "view_access_denied",
        }


def test_unapproved_table_view_route_does_not_create_a_v1_view() -> None:
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
        table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Customers", "key": "customers"},
        ).json()["id"]

        response = client.post(
            f"/tables/{table_id}/views",
            json={"scope": "restricted", "permission_policy": {"viewer": "read"}},
        )

    assert response.status_code == 404
    assert uow.list_views(UUID(table_id)) == []


def test_base_view_list_omits_private_v1_summary_from_ungranted_member() -> None:
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
        table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Customers", "key": "customers"},
        ).json()["id"]
        client.post(
            f"/tables/{table_id}/fields",
            json={"name": "Name", "key": "name", "field_type": "text"},
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
        created = client.post(
            f"/tables/{table_id}/view-initializations",
            json={
                "name": "Owner private",
                "view_type": "grid",
                "presentation": {
                    "view_type": "grid",
                    "visible_field_keys": ["name"],
                    "filters": [],
                    "sort_rules": [],
                    "group_by_field_key": None,
                },
            },
            headers={"Idempotency-Key": "private-list"},
        )
        assert created.status_code == 201
        owner_views = client.get(f"/bases/{base_id}/views")
        client.headers["X-Stage06-User-Id"] = "viewer-1"
        viewer_views = client.get(f"/bases/{base_id}/views")
        viewer_presentation = client.get(
            f"/views/{created.json()['view']['id']}/presentation"
        )
        client.headers["X-Stage06-User-Id"] = "owner-1"
        granted = client.put(
            f"/views/{created.json()['view']['id']}/members",
            json={
                "expected_version": 1,
                "members": [{"user_id": "viewer-1", "access_level": "viewer"}],
            },
        )
        client.headers["X-Stage06-User-Id"] = "viewer-1"
        granted_views = client.get(f"/bases/{base_id}/views")

    assert owner_views.status_code == 200
    assert [view["name"] for view in owner_views.json()["views"]] == ["Owner private"]
    assert owner_views.json()["views"][0] == {
        "id": created.json()["view"]["id"],
        "base_id": base_id,
        "table_id": table_id,
        "name": "Owner private",
        "view_type": "grid",
        "status": "active",
        "scope": "private",
        "caller_access_level": "owner",
        "is_default": False,
    }
    assert viewer_views.status_code == 200
    assert viewer_views.json()["views"] == []
    assert viewer_presentation.status_code == 403
    assert viewer_presentation.json()["detail"]["code"] == "view_access_denied"
    assert granted.status_code == 200
    assert [view["name"] for view in granted_views.json()["views"]] == ["Owner private"]
    assert granted_views.json()["views"][0]["caller_access_level"] == "viewer"
    assert {"owner_user_id", "permission_policy", "config"}.isdisjoint(
        granted_views.json()["views"][0]
    )
