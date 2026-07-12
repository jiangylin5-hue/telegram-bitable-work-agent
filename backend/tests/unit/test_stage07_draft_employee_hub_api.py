from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.models.stage06_runtime import RecordChangeDraft
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)


def test_s5_contact_directory_returns_only_safe_active_contact_projection() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="S5 Hub",
        owner_user_id=owner.actor_id,
        actor=owner,
    )
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    create_digital_employee(
        uow,
        base.id,
        name="Operations assistant",
        description="Summarizes and prepares drafts.",
        telegram_alias="ops_private",
        accessible_tables=[str(table.id)],
        accessible_views=[],
        allowed_actions=["summarize", "draft_update"],
        field_policy={"internal": "hidden"},
        confirmation_policy={"draft_update": "required"},
        response_style={"tone": "brief"},
        actor=owner,
    )
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.get(
            f"/mini-app/workspaces/{workspace.id}/digital-employee-contacts"
        )

    assert response.status_code == 200
    assert response.json() == {
        "workspace_id": str(workspace.id),
        "contacts": [
            {
                "id": response.json()["contacts"][0]["id"],
                "base_id": str(base.id),
                "name": "Operations assistant",
                "description": "Summarizes and prepares drafts.",
                "status": "active",
                "available_intents": ["summarize", "draft_update"],
            }
        ],
        "next_cursor": None,
        "has_more": False,
    }
    assert "ops_private" not in response.text
    assert "field_policy" not in response.text
    assert "accessible_tables" not in response.text


def test_s5_draft_model_starts_with_terminal_revision_and_audit_reference() -> None:
    assert RecordChangeDraft.__table__.c.version.default.arg == 1
    assert "terminal_audit_event_id" in RecordChangeDraft.__table__.c


def test_s5_draft_read_models_filter_hidden_values_and_metadata() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 drafts", owner_user_id="owner-1", actor=owner)
    viewer = WorkspaceMember(
        id=uuid4(), workspace_id=workspace.id, user_id="viewer-1", role="viewer", status="active"
    )
    uow.add_workspace_member(viewer)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    create_field(uow, table.id, name="Title", key="title", field_type="text", actor=owner)
    create_field(
        uow,
        table.id,
        name="Internal",
        key="internal",
        field_type="text",
        permission_policy={"viewer": "hidden"},
        actor=owner,
    )
    draft = RecordChangeDraft(
        id=uuid4(),
        workspace_id=workspace.id,
        base_id=base.id,
        table_id=table.id,
        record_id=None,
        draft_type="update_record",
        proposed_values={"title": "After", "internal": "secret-after"},
        before_values={"title": "Before", "internal": "secret-before"},
        created_by_type="digital_employee",
        created_by_id="private-employee",
        status="pending_confirmation",
        confirmation_policy={},
        trace_id="private-trace",
        expected_version=7,
        version=1,
    )
    uow.add_record_change_draft(draft)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "viewer-1"
        listed = client.get(f"/mini-app/bases/{base.id}/drafts")
        detail = client.get(f"/mini-app/drafts/{draft.id}")

    assert listed.status_code == detail.status_code == 200
    assert listed.json()["drafts"] == [{
        "id": str(draft.id), "base_id": str(base.id), "table_id": str(table.id),
        "record_id": None, "draft_type": "update_record", "status": "pending_confirmation", "version": 1,
    }]
    assert detail.json() == {
        "id": str(draft.id), "base_id": str(base.id), "table_id": str(table.id), "record_id": None,
        "draft_type": "update_record", "status": "pending_confirmation", "version": 1,
        "fields": [{"key": "title", "label": "Title", "field_type": "text", "before_value": "Before", "proposed_value": "After"}],
        "actions": {"can_confirm": False, "can_reject": False}, "terminal_audit_event_id": None,
    }
    assert "secret" not in (listed.text + detail.text)
    assert "private-employee" not in detail.text
    assert "private-trace" not in detail.text


def test_s5_reject_is_versioned_idempotent_and_has_no_record_write() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 reject", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    draft = RecordChangeDraft(
        id=uuid4(), workspace_id=workspace.id, base_id=base.id, table_id=table.id,
        record_id=None, draft_type="update_record", proposed_values={"title": "never-write"},
        before_values=None, created_by_type="digital_employee", created_by_id="private", status="pending_confirmation",
        confirmation_policy={}, trace_id="private-trace", expected_version=1, version=1,
    )
    uow.add_record_change_draft(draft)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        first = client.post(
            f"/mini-app/drafts/{draft.id}/reject", headers={"Idempotency-Key": "s5-reject-1"},
            json={"expected_version": 1},
        )
        replay = client.post(
            f"/mini-app/drafts/{draft.id}/reject", headers={"Idempotency-Key": "s5-reject-1"},
            json={"expected_version": 1},
        )

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["status"] == "rejected"
    assert first.json()["version"] == 2
    assert first.json()["terminal_audit_event_id"]
    assert uow.records == []
    assert "private-trace" not in first.text


def test_s5_confirm_reuses_versioned_record_update_and_safe_receipt() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 confirm", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    create_field(uow, table.id, name="Title", key="title", field_type="text", actor=owner)
    record = create_record(uow, table.id, values={"title": "Before"}, actor=owner)
    draft = RecordChangeDraft(
        id=uuid4(), workspace_id=workspace.id, base_id=base.id, table_id=table.id,
        record_id=record.id, draft_type="update_record", proposed_values={"title": "After"},
        before_values={"title": "Before"}, created_by_type="digital_employee", created_by_id="private",
        status="pending_confirmation", confirmation_policy={}, trace_id="private-trace",
        expected_version=record.version, version=1,
    )
    uow.add_record_change_draft(draft)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.post(
            f"/mini-app/drafts/{draft.id}/confirm", headers={"Idempotency-Key": "s5-confirm-1"},
            json={"expected_version": 1},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["version"] == 2
    assert response.json()["terminal_audit_event_id"]
    assert record.values == {"title": "After"}
    assert record.version == 2
    assert "private-trace" not in response.text
