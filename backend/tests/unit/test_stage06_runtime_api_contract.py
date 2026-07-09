import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_system_actor
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


def test_stage06_runtime_api_updates_employee_and_confirms_notification_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STAGE06_NOTIFICATION_MODE", "restricted_test")
    monkeypatch.setenv("STAGE06_NOTIFICATION_ALLOWED_CHAT_IDS", "chat-1")
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
        employee_id = client.post(
            f"/bases/{base_id}/digital-employees",
            json={
                "name": "CRM Helper",
                "description": "Initial description",
                "telegram_alias": "crm",
                "allowed_actions": ["summarize"],
            },
        ).json()["id"]

        employee_update = client.patch(
            f"/digital-employees/{employee_id}",
            json={
                "description": "Updated description",
                "allowed_actions": ["summarize", "draft_update"],
                "status": "active",
            },
        )
        notification = client.post(
            "/notification-requests",
            json={
                "workspace_id": workspace_id,
                "base_id": base_id,
                "channel": "telegram",
                "target": {"telegram_chat_id": "chat-1"},
                "message_payload": {"text": "Please review CRM"},
                "send_policy": {
                    "confirmation": "required",
                    "allowlist": ["chat-1"],
                },
            },
        ).json()
        notification_confirm = client.post(
            f"/notification-requests/{notification['id']}/confirm"
        )

    assert employee_update.status_code == 200
    assert employee_update.json()["description"] == "Updated description"
    assert employee_update.json()["allowed_actions"] == ["summarize", "draft_update"]
    assert notification["status"] == "pending_confirmation"
    assert notification_confirm.status_code == 200
    assert notification_confirm.json()["status"] == "queued"
    assert {
        "stage06.digital_employee_updated",
        "stage06.notification_confirmed",
    }.issubset({event.event_type for event in uow.audit_events})
