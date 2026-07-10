from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


def test_canvas_schema_projects_only_safe_field_metadata() -> None:
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
        field_response = client.post(
            f"/tables/{table_id}/fields",
            json={
                "name": "Stage",
                "key": "stage",
                "field_type": "status",
                "required": True,
                "options": {
                    "choices": ["new", "active"],
                    "internal_rule": "must-not-leak",
                },
                "permission_policy": {"viewer": "hidden"},
            },
        )

        schema_response = client.get(f"/tables/{table_id}/schema")

    assert field_response.status_code == 200
    assert schema_response.status_code == 200
    assert schema_response.json()["fields"] == [
        {
            "id": field_response.json()["id"],
            "table_id": table_id,
            "name": "Stage",
            "key": "stage",
            "field_type": "status",
            "required": True,
            "options": {"choices": ["new", "active"]},
            "order_index": 0,
        }
    ]
    assert "permission_policy" not in schema_response.text
    assert "internal_rule" not in schema_response.text
