from fastapi.testclient import TestClient

from app.api.deps import get_system_actor
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.api.routes.stage06_templates import get_stage06_template_import_uow
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


def test_stage06_backend_pilot_path_has_audit_and_safety_close_evidence() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_template_import_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="pilot-owner",
        role="owner",
    )

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "pilot-owner"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Pilot Workspace", "owner_user_id": "pilot-owner"},
        ).json()["id"]

        import_job = client.post(
            f"/workspaces/{workspace_id}/imports",
            json={
                "source_type": "csv",
                "file_name": "customers.csv",
                "content": "Name,Status\nAda Co,new\n",
                "created_by_user_id": "pilot-owner",
            },
        ).json()
        import_job_id = import_job["id"]
        import_commit = client.post(
            f"/imports/{import_job_id}/commit",
            json={
                "base_name": "Pilot CRM",
                "table_name": "Customers",
                "table_key": "customers",
                "field_mapping": [
                    {"source_key": "name", "target_key": "name", "field_type": "text"},
                    {
                        "source_key": "status",
                        "target_key": "status",
                        "field_type": "status",
                    },
                ],
            },
        ).json()
        base_id = import_commit["resource_map"]["base_id"]
        table_id = import_commit["resource_map"]["table_id"]
        record_id = str(uow.records[0].id)
        view_id = str(
            client.post(
                f"/bases/{base_id}/views",
                json={
                    "table_id": table_id,
                    "name": "Pilot Grid",
                    "view_type": "grid",
                    "config": {"fields": ["name", "status"]},
                },
            ).json()["id"]
        )

        employee_id = client.post(
            f"/bases/{base_id}/digital-employees",
            json={
                "name": "Pilot Helper",
                "description": "Pilot digital employee",
                "telegram_alias": "pilot",
                "accessible_tables": [table_id],
                "accessible_views": [view_id],
                "allowed_actions": ["summarize", "draft_update"],
            },
        ).json()["id"]
        client.post(
            f"/workspaces/{workspace_id}/telegram-bindings",
            json={
                "workspace_member_id": str(uow.workspace_members[0].id),
                "telegram_chat_id": "chat-1",
                "telegram_user_id": "user-1",
                "binding_type": "chat_user",
                "default_base_id": base_id,
                "default_digital_employee_id": employee_id,
                "scope_policy": {"views": [view_id]},
            },
        )

        mention = client.post(
            "/telegram/mentions",
            json={
                "telegram_chat_id": "chat-1",
                "telegram_user_id": "user-1",
                "alias": "pilot",
                "text": "summarize customers",
            },
        )
        draft = client.post(
            f"/digital-employees/{employee_id}/invoke",
            json={
                "action": "draft_update",
                "view_id": view_id,
                "record_id": record_id,
                "proposed_values": {"status": "active"},
            },
        ).json()
        confirm = client.post(f"/record-change-drafts/{draft['draft_id']}/confirm")
        notification = client.post(
            "/notification-requests",
            json={
                "workspace_id": workspace_id,
                "base_id": base_id,
                "source_record_id": record_id,
                "channel": "telegram",
                "target": {"telegram_chat_id": "chat-1"},
                "message_payload": {"text": "Pilot dry-run notification"},
                "send_policy": {"dry_run": True, "allowlist": ["chat-2"]},
            },
        )
        notifications = client.get(f"/bases/{base_id}/notification-requests")
        audit = client.get(f"/bases/{base_id}/audit-events")

    assert mention.status_code == 200
    assert mention.json()["record_count"] == 1
    mention_skill_evidence = mention.json()["skill_evidence"]
    mention_selected_ids = {
        item["skill_id"]
        for item in mention_skill_evidence["selected_skills"]
    }
    assert "platform-base" in mention_selected_ids
    assert "platform-tabular-analysis" in mention_selected_ids
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"
    assert uow.records[0].values["status"] == "active"
    assert notification.status_code == 200
    assert notification.json()["status"] == "blocked"
    assert notifications.json()["requests"][0]["status"] == "blocked"
    assert audit.status_code == 200
    audit_types = {event["event_type"] for event in audit.json()["events"]}
    assert {
        "stage06.import_committed",
        "stage06.digital_employee_invoked",
        "stage06.record_change_draft_confirmed",
        "stage06.notification_blocked",
    }.issubset(audit_types)
