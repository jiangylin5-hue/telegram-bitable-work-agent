from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.models.stage06_platform import PlatformField, WorkspaceMember
from app.services.permissions import Actor
from app.services.stage06_authorization import action_allowed_for_role
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_table,
    create_workspace,
)


def test_governance_actions_are_owner_admin_only() -> None:
    assert action_allowed_for_role("owner", "member.manage") is True
    assert action_allowed_for_role("admin", "member.manage") is True
    assert action_allowed_for_role("owner", "field.permission.manage") is True
    assert action_allowed_for_role("admin", "field.permission.manage") is True
    assert action_allowed_for_role("builder", "member.manage") is False
    assert action_allowed_for_role("builder", "field.permission.manage") is False
    assert action_allowed_for_role("viewer", "field.permission.manage") is False


def test_governance_models_start_with_revision_one() -> None:
    assert WorkspaceMember.__table__.c.version.default.arg == 1
    assert PlatformField.__table__.c.permission_version.default.arg == 1


def _write_fixture() -> tuple[
    InMemoryStage06PlatformUnitOfWork,
    str,
    str,
    str,
    str,
]:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="Governance write",
        owner_user_id="owner-1",
        actor=owner,
    )
    admin = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id="admin-1",
        role="admin",
        status="active",
        version=1,
    )
    operator = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id="operator-1",
        role="operator",
        status="active",
        version=1,
    )
    uow.add_workspace_member(admin)
    uow.add_workspace_member(operator)
    base = create_base(uow, workspace.id, name="CRM", actor=owner)
    table = create_table(uow, base.id, name="Customers", key="customers", actor=owner)
    field = create_field(
        uow,
        table.id,
        name="Internal note",
        key="internal_note",
        field_type="text",
        permission_policy={},
        actor=owner,
    )
    field.permission_version = 1
    return uow, str(workspace.id), str(table.id), str(admin.id), str(operator.id)


def _write_client(uow: InMemoryStage06PlatformUnitOfWork) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow
    return TestClient(app)


def test_governance_write_member_context_and_role_command_are_closed() -> None:
    uow, workspace_id, _table_id, admin_id, operator_id = _write_fixture()

    with _write_client(uow) as client:
        client.headers["X-Stage06-User-Id"] = "admin-1"
        context = client.get(
            f"/mini-app/workspaces/{workspace_id}/governance/member-editor"
        )
        changed = client.patch(
            f"/mini-app/workspaces/{workspace_id}/governance/members/{operator_id}/role",
            headers={"Idempotency-Key": "governance-role-1"},
            json={"role": "builder", "expected_version": 1},
        )
        replay = client.patch(
            f"/mini-app/workspaces/{workspace_id}/governance/members/{operator_id}/role",
            headers={"Idempotency-Key": "governance-role-1"},
            json={"role": "builder", "expected_version": 1},
        )
        forbidden = client.patch(
            f"/mini-app/workspaces/{workspace_id}/governance/members/{admin_id}/role",
            headers={"Idempotency-Key": "governance-role-2"},
            json={"role": "admin", "expected_version": 1},
        )

    assert context.status_code == 200
    assert set(context.json()) == {"workspace_id", "members", "next_cursor", "has_more"}
    assert set(context.json()["members"][0]) == {
        "id",
        "user_id",
        "role",
        "status",
        "version",
        "assignable_roles",
    }
    assert changed.status_code == replay.status_code == 200
    assert changed.json() == {
        "id": operator_id,
        "user_id": "operator-1",
        "role": "builder",
        "status": "active",
        "version": 2,
    }
    assert forbidden.status_code == 422
    assert "ROLE_ACTIONS" not in context.text


def test_governance_write_field_policy_is_fixed_closed_and_idempotent() -> None:
    uow, _workspace_id, table_id, _admin_id, _operator_id = _write_fixture()
    field_id = str(uow.list_fields(UUID(table_id))[0].id)
    policy = {
        "owner": "write",
        "admin": "write",
        "builder": "write",
        "operator": "read",
        "viewer": "hidden",
    }

    with _write_client(uow) as client:
        client.headers["X-Stage06-User-Id"] = "admin-1"
        context = client.get(
            f"/mini-app/tables/{table_id}/governance/field-permissions"
        )
        changed = client.put(
            f"/mini-app/tables/{table_id}/governance/fields/{field_id}/permission-policy",
            headers={"Idempotency-Key": "governance-policy-1"},
            json={"expected_permission_version": 1, "policy": policy},
        )
        replay = client.put(
            f"/mini-app/tables/{table_id}/governance/fields/{field_id}/permission-policy",
            headers={"Idempotency-Key": "governance-policy-1"},
            json={"expected_permission_version": 1, "policy": policy},
        )
        invalid = client.put(
            f"/mini-app/tables/{table_id}/governance/fields/{field_id}/permission-policy",
            headers={"Idempotency-Key": "governance-policy-2"},
            json={"expected_permission_version": 2, "policy": {**policy, "owner": "read"}},
        )

    assert context.status_code == 200
    assert set(context.json()) == {"table_id", "fields"}
    assert set(context.json()["fields"][0]) == {
        "id",
        "key",
        "label",
        "field_type",
        "policy",
        "permission_version",
    }
    assert changed.status_code == replay.status_code == 200
    assert changed.json()["policy"] == policy
    assert changed.json()["permission_version"] == 2
    assert invalid.status_code == 422
    assert "options" not in context.text
