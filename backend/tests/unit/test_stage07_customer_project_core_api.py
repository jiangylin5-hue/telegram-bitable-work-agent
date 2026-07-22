from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


def test_customer_project_task_core_keeps_relations_and_internal_project_field_out_of_viewer_projection() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Delivery workspace", "owner_user_id": "owner-1"},
        ).json()["id"]
        base_id = client.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "Customer delivery"},
        ).json()["id"]
        customer_table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Customers", "key": "customers"},
        ).json()["id"]
        project_table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Projects", "key": "projects"},
        ).json()["id"]
        task_table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Tasks", "key": "tasks"},
        ).json()["id"]

        customer_name = client.post(
            f"/tables/{customer_table_id}/fields",
            json={"name": "Customer", "key": "customer", "field_type": "text"},
        ).json()
        project_name = client.post(
            f"/tables/{project_table_id}/fields",
            json={"name": "Project", "key": "project", "field_type": "text"},
        ).json()
        client.post(
            f"/tables/{project_table_id}/fields",
            json={
                "name": "Internal health",
                "key": "internal_health",
                "field_type": "text",
                "permission_policy": {"viewer": "hidden"},
            },
        )
        task_name = client.post(
            f"/tables/{task_table_id}/fields",
            json={"name": "Task", "key": "task", "field_type": "text"},
        ).json()
        task_status = client.post(
            f"/tables/{task_table_id}/fields",
            json={
                "name": "Status",
                "key": "status",
                "field_type": "status",
                "options": {"choices": ["not_started", "in_progress", "blocked", "waiting_customer", "done"]},
            },
        ).json()

        project_customer_relation = client.post(
            f"/tables/{project_table_id}/relation-field-initializations",
            headers={"Idempotency-Key": "project-customer-relation"},
            json={"name": "Customer", "target_table_id": customer_table_id, "required": True},
        ).json()["field"]
        task_project_relation = client.post(
            f"/tables/{task_table_id}/relation-field-initializations",
            headers={"Idempotency-Key": "task-project-relation"},
            json={"name": "Project", "target_table_id": project_table_id, "required": True},
        ).json()["field"]

        customer_record_id = client.post(
            f"/tables/{customer_table_id}/records",
            json={"values": {customer_name["key"]: "Sample customer"}},
        ).json()["id"]
        project_record_id = client.post(
            f"/tables/{project_table_id}/records",
            json={
                "values": {
                    project_name["key"]: "Sample project",
                    project_customer_relation["key"]: [customer_record_id],
                    "internal_health": "internal-only",
                }
            },
        ).json()["id"]
        client.post(
            f"/tables/{task_table_id}/records",
            json={
                "values": {
                    task_name["key"]: "Sample delivery task",
                    task_status["key"]: "in_progress",
                    task_project_relation["key"]: [project_record_id],
                }
            },
        )
        project_view_id = client.post(
            f"/bases/{base_id}/views",
            json={
                "table_id": project_table_id,
                "name": "Project health",
                "view_type": "grid",
                "config": {
                    "fields": [
                        project_name["key"],
                        project_customer_relation["key"],
                        "internal_health",
                    ]
                },
            },
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
        home_response = client.get(f"/workspaces/{workspace_id}/home")
        schema_response = client.get(f"/tables/{project_table_id}/schema")
        records_response = client.get(f"/views/{project_view_id}/records")

        client.headers["X-Stage06-User-Id"] = "outsider-1"
        outsider_response = client.get(f"/workspaces/{workspace_id}/home")

    assert home_response.status_code == 200
    assert home_response.json()["recent_bases"] == [
        {"id": base_id, "name": "Customer delivery", "source_type": "blank"}
    ]
    assert schema_response.status_code == 200
    assert [field["key"] for field in schema_response.json()["fields"]] == [
        project_name["key"],
        project_customer_relation["key"],
    ]
    assert records_response.status_code == 200
    assert records_response.json()["records"] == [
        {
            "id": project_record_id,
            "fields": {
                project_name["key"]: "Sample project",
                project_customer_relation["key"]: [{"id": customer_record_id, "label": "Sample customer"}],
            },
        }
    ]
    assert "internal_health" not in records_response.text
    assert "internal-only" not in records_response.text
    assert outsider_response.status_code == 403
