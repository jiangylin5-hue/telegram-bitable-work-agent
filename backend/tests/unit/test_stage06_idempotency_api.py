from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.api.routes.stage06_templates import get_stage06_template_import_uow
from app.main import create_app
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_form_view,
)


def _client_and_uow():
    uow = InMemoryStage06PlatformUnitOfWork()
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow
    app.dependency_overrides[get_stage06_template_import_uow] = lambda: uow
    client = TestClient(app)
    client.headers["X-Stage06-User-Id"] = "owner-1"
    return client, uow


def test_stage06_import_create_replays_same_idempotency_key() -> None:
    client, uow = _client_and_uow()
    workspace_id = client.post(
        "/workspaces",
        json={"name": "Acme", "owner_user_id": "owner-1"},
    ).json()["id"]
    payload = {
        "source_type": "csv",
        "file_name": "data.csv",
        "content": "name\nAda",
        "created_by_user_id": "owner-1",
    }

    first = client.post(
        f"/workspaces/{workspace_id}/imports",
        headers={"Idempotency-Key": "import-key-1"},
        json=payload,
    )
    second = client.post(
        f"/workspaces/{workspace_id}/imports",
        headers={"Idempotency-Key": "import-key-1"},
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(uow.import_jobs) == 1


def test_stage06_import_create_conflicts_when_key_payload_changes() -> None:
    client, _uow = _client_and_uow()
    workspace_id = client.post(
        "/workspaces",
        json={"name": "Acme", "owner_user_id": "owner-1"},
    ).json()["id"]
    headers = {"Idempotency-Key": "import-key-1"}
    first = client.post(
        f"/workspaces/{workspace_id}/imports",
        headers=headers,
        json={
            "source_type": "csv",
            "file_name": "one.csv",
            "content": "name\nAda",
            "created_by_user_id": "owner-1",
        },
    )
    second = client.post(
        f"/workspaces/{workspace_id}/imports",
        headers=headers,
        json={
            "source_type": "csv",
            "file_name": "two.csv",
            "content": "name\nGrace",
            "created_by_user_id": "owner-1",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "idempotency_conflict"


def test_stage06_draft_confirmation_replays_after_completion() -> None:
    client, uow = _client_and_uow()
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
        json={"name": "Status", "key": "status", "field_type": "status"},
    )
    record_id = client.post(
        f"/tables/{table_id}/records",
        json={"values": {"status": "new"}},
    ).json()["id"]
    view = create_form_view(
        uow,
        uow.bases[0].id,
        uow.tables[0].id,
        name="Grid",
        view_type="grid",
        config={"fields": ["status"]},
    )
    employee_id = client.post(
        f"/bases/{base_id}/digital-employees",
        json={
            "name": "Ops",
            "description": "Ops",
            "accessible_tables": [table_id],
            "accessible_views": [str(view.id)],
            "allowed_actions": ["draft_update"],
        },
    ).json()["id"]
    draft_id = client.post(
        f"/digital-employees/{employee_id}/invoke",
        json={
            "action": "draft_update",
            "record_id": record_id,
            "proposed_values": {"status": "done"},
        },
    ).json()["draft_id"]

    first = client.post(
        f"/record-change-drafts/{draft_id}/confirm",
        headers={"Idempotency-Key": "draft-key-1"},
    )
    second = client.post(
        f"/record-change-drafts/{draft_id}/confirm",
        headers={"Idempotency-Key": "draft-key-1"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "confirmed"
    assert second.json()["id"] == draft_id
    assert uow.records[0].version == 2
