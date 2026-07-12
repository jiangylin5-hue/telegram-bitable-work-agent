from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)


def _governance_fixture() -> tuple[
    InMemoryStage06PlatformUnitOfWork,
    str,
    str,
    str,
]:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="Governance",
        owner_user_id="owner-1",
        actor=owner,
    )
    uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id="admin-1",
            role="admin",
            status="active",
        )
    )
    uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id="viewer-1",
            role="viewer",
            status="active",
        )
    )
    base = create_base(uow, workspace.id, name="CRM", actor=owner)
    table = create_table(uow, base.id, name="Customers", key="customers", actor=owner)
    create_field(
        uow,
        table.id,
        name="Private Note",
        key="private_note",
        field_type="text",
        permission_policy={"viewer": "hidden"},
        actor=owner,
    )
    record = create_record(
        uow,
        table.id,
        values={"private_note": "legacy-hidden-value"},
        actor=owner,
    )
    event = next(
        item
        for item in uow.audit_events
        if item.event_type == "stage06.record_created" and item.entity_id == record.id
    )
    event.trace_id = "trace-secret"
    event.actor_id = "actor-secret"
    event.after_state = {"values": {"private_note": "legacy-hidden-value"}}
    event.permission_snapshot = {"role": "owner", "internal": "secret"}
    for audit_event in uow.audit_events:
        audit_event.created_at = datetime(2026, 7, 12, tzinfo=UTC)
    return uow, str(workspace.id), str(base.id), str(record.id)


def _client(uow: InMemoryStage06PlatformUnitOfWork) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow
    return TestClient(app)


def test_governance_members_are_paged_and_closed() -> None:
    uow, workspace_id, _base_id, _record_id = _governance_fixture()

    with _client(uow) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        first = client.get(
            f"/mini-app/workspaces/{workspace_id}/governance/members?limit=1"
        )

    assert first.status_code == 200
    assert set(first.json()) == {"workspace_id", "members", "next_cursor", "has_more"}
    assert first.json()["workspace_id"] == workspace_id
    assert len(first.json()["members"]) == 1
    assert set(first.json()["members"][0]) == {"id", "user_id", "role", "status"}
    assert first.json()["has_more"] is True
    assert first.json()["next_cursor"]


def test_governance_audit_projection_never_emits_legacy_audit_fields() -> None:
    uow, _workspace_id, base_id, _record_id = _governance_fixture()

    with _client(uow) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        response = client.get(
            f"/mini-app/bases/{base_id}/governance/audit-events?limit=50"
        )

    assert response.status_code == 200
    assert set(response.json()) == {"base_id", "events", "next_cursor", "has_more"}
    assert response.json()["base_id"] == base_id
    assert response.json()["events"]
    forbidden = {
        "trace_id",
        "actor_id",
        "entity_id",
        "before_state",
        "after_state",
        "permission_snapshot",
    }
    assert forbidden.isdisjoint(response.json()["events"][0])
    assert "trace-secret" not in response.text
    assert "actor-secret" not in response.text
    assert "legacy-hidden-value" not in response.text


def test_governance_routes_fail_closed_for_viewer_and_invalid_cursor() -> None:
    uow, workspace_id, base_id, _record_id = _governance_fixture()

    with _client(uow) as client:
        client.headers["X-Stage06-User-Id"] = "viewer-1"
        members = client.get(
            f"/mini-app/workspaces/{workspace_id}/governance/members"
        )
        audit = client.get(f"/mini-app/bases/{base_id}/governance/audit-events")
        client.headers["X-Stage06-User-Id"] = "owner-1"
        invalid_cursor = client.get(
            f"/mini-app/workspaces/{workspace_id}/governance/members?cursor=broken"
        )

    assert members.status_code == 403
    assert audit.status_code == 403
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["detail"]["code"] == "governance_invalid_cursor"
