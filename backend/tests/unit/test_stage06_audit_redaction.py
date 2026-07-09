from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)


def _audit_fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="Acme",
        owner_user_id="owner-1",
        actor=actor,
    )
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    table = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
    create_field(
        uow,
        table.id,
        name="Private Note",
        key="private_note",
        field_type="text",
        permission_policy={"viewer": "hidden"},
        actor=actor,
    )
    record = create_record(
        uow,
        table.id,
        values={"private_note": "hidden-value"},
        actor=actor,
    )
    return uow, workspace, base, record


def test_stage06_record_audit_stores_field_keys_not_raw_values() -> None:
    uow, _workspace, _base, record = _audit_fixture()
    event = next(
        item
        for item in uow.audit_events
        if item.event_type == "stage06.record_created" and item.entity_id == record.id
    )

    assert "hidden-value" not in str(event.after_state)
    assert event.after_state["field_keys"] == ["private_note"]
    assert event.after_state["version"] == 1


def test_stage06_audit_readback_requires_owner_or_admin() -> None:
    uow, workspace, base, _record = _audit_fixture()
    owner = uow.workspace_members[0]
    owner.user_id = "viewer-1"
    owner.role = "viewer"
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.get(
            f"/bases/{base.id}/audit-events",
            headers={"X-Stage06-User-Id": "viewer-1"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "stage06_action_denied"
    assert workspace.id is not None


def test_stage06_audit_readback_sanitizes_legacy_raw_values() -> None:
    uow, _workspace, base, record = _audit_fixture()
    event = next(
        item
        for item in uow.audit_events
        if item.event_type == "stage06.record_created" and item.entity_id == record.id
    )
    event.after_state = {
        "values": {"private_note": "legacy-hidden-value"},
        "version": 1,
    }
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.get(
            f"/bases/{base.id}/audit-events",
            headers={"X-Stage06-User-Id": "owner-1"},
        )

    assert response.status_code == 200
    assert "legacy-hidden-value" not in response.text
    record_event = next(
        item
        for item in response.json()["events"]
        if item["event_type"] == "stage06.record_created"
    )
    assert record_event["after_state"]["field_keys"] == ["private_note"]
