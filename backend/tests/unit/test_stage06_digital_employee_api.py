from fastapi.testclient import TestClient

from app.api.deps import get_system_actor
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_form_view,
)


def test_stage06_digital_employee_api_creates_invokes_drafts_confirms_and_mentions() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="owner-1",
        role="owner",
    )

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
        client.post(
            f"/tables/{table_id}/fields",
            json={
                "name": "Status",
                "key": "status",
                "field_type": "status",
                "permission_policy": {"viewer": "read", "operator": "write"},
            },
        )
        record_id = client.post(
            f"/tables/{table_id}/records",
            json={"values": {"name": "Ada Co", "status": "new"}},
        ).json()["id"]
        view = create_form_view(
            uow,
            uow.bases[0].id,
            uow.tables[0].id,
            name="Customer Grid",
            view_type="grid",
            config={"fields": ["name", "status"]},
        )

        employee_response = client.post(
            f"/bases/{base_id}/digital-employees",
            json={
                "name": "CRM Helper",
                "description": "Operate CRM",
                "telegram_alias": "crm",
                "accessible_tables": [table_id],
                "accessible_views": [str(view.id)],
                "allowed_actions": ["summarize", "draft_update"],
            },
        )
        employee_id = employee_response.json()["id"]

        summary_response = client.post(
            f"/digital-employees/{employee_id}/invoke",
            json={"action": "summarize", "view_id": str(view.id)},
        )
        summary_skill_evidence = summary_response.json()["skill_evidence"]
        draft_response = client.post(
            f"/digital-employees/{employee_id}/invoke",
            json={
                "action": "draft_update",
                "view_id": str(view.id),
                "record_id": record_id,
                "proposed_values": {"status": "active"},
            },
        )
        draft_id = draft_response.json()["draft_id"]

        drafts_response = client.get(f"/bases/{base_id}/record-change-drafts")
        confirm_response = client.post(f"/record-change-drafts/{draft_id}/confirm")

        client.post(
            f"/workspaces/{workspace_id}/telegram-bindings",
            json={
                "telegram_chat_id": "chat-1",
                "telegram_user_id": "user-1",
                "binding_type": "chat_user",
                "default_base_id": base_id,
                "default_digital_employee_id": employee_id,
                "scope_policy": {"views": [str(view.id)]},
            },
        )
        mention_response = client.post(
            "/telegram/mentions",
            json={
                "telegram_chat_id": "chat-1",
                "telegram_user_id": "user-1",
                "alias": "crm",
                "text": "summarize",
            },
        )

    assert employee_response.status_code == 200
    assert summary_response.status_code == 200
    assert summary_response.json()["record_count"] == 1
    summary_selected_ids = {
        item["skill_id"]
        for item in summary_skill_evidence["selected_skills"]
    }
    assert "platform-base" in summary_selected_ids
    assert "platform-tabular-analysis" in summary_selected_ids
    assert draft_response.status_code == 200
    assert draft_response.json()["status"] == "pending_confirmation"
    assert drafts_response.status_code == 200
    assert drafts_response.json()["drafts"][0]["id"] == draft_id
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"
    assert mention_response.status_code == 200
    assert mention_response.json()["employee_id"] == employee_id
