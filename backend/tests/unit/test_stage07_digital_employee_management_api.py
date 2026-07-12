from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.schemas.stage07_digital_employee_management import (
    ManagedEmployeeCreateRequest,
    ManagedEmployeeDetailResponse,
    ManagedEmployeeUpdateRequest,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_form_view,
    create_table,
    create_workspace,
)


def test_management_api_exposes_only_safe_versioned_employee_contracts() -> None:
    fixture = _api_fixture()
    create_payload = {
        "name": "Customer helper",
        "description": "Summarizes the selected customer view",
        "telegram_alias": "customer-helper",
    }

    with fixture.client as client:
        client.headers["X-Stage06-User-Id"] = fixture.owner.actor_id
        context = client.get(
            f"/mini-app/bases/{fixture.base_id}/digital-employee-management-context"
        )
        created = client.post(
            f"/mini-app/bases/{fixture.base_id}/digital-employees/management",
            headers={"Idempotency-Key": "managed-api-create"},
            json=create_payload,
        )
        replay = client.post(
            f"/mini-app/bases/{fixture.base_id}/digital-employees/management",
            headers={"Idempotency-Key": "managed-api-create"},
            json=create_payload,
        )
        directory = client.get(
            f"/mini-app/bases/{fixture.base_id}/digital-employees/management"
        )

    assert context.status_code == 200
    assert set(context.json()) == {"base", "tables", "views", "members"}
    assert context.json()["members"][0].keys() == {"id", "label", "role"}
    assert fixture.operator.user_id not in context.text
    assert created.status_code == replay.status_code == directory.status_code == 200
    assert created.json() == replay.json()
    assert set(created.json()) == {
        "id",
        "name",
        "description",
        "status",
        "access_mode",
        "table_count",
        "view_count",
        "member_count",
        "version",
        "base_id",
        "telegram_alias",
        "accessible_table_ids",
        "accessible_view_ids",
        "allowed_actions",
        "member_ids",
    }
    assert created.json()["status"] == "draft"
    assert created.json()["access_mode"] == "assigned"
    assert directory.json()["employees"][0].keys() == {
        "id",
        "name",
        "description",
        "status",
        "access_mode",
        "table_count",
        "view_count",
        "member_count",
        "version",
    }
    response_text = context.text + created.text + directory.text
    for prohibited in {
        "field_policy",
        "confirmation_policy",
        "response_style",
        "runtime",
        "trace",
        "record_values",
    }:
        assert prohibited not in response_text


def test_management_api_applies_safe_configuration_lifecycle_and_existing_authority() -> None:
    fixture = _api_fixture()
    with fixture.client as client:
        client.headers["X-Stage06-User-Id"] = fixture.owner.actor_id
        created = client.post(
            f"/mini-app/bases/{fixture.base_id}/digital-employees/management",
            headers={"Idempotency-Key": "managed-api-lifecycle-create"},
            json={
                "name": "Lifecycle helper",
                "description": "Can summarize safely",
                "telegram_alias": None,
            },
        )
        employee_id = created.json()["id"]
        configured = client.patch(
            f"/mini-app/digital-employees/{employee_id}/management",
            json={
                "expected_version": 1,
                "accessible_table_ids": [fixture.table_id],
                "accessible_view_ids": [fixture.view_id],
                "allowed_actions": ["summarize", "draft_update"],
                "access_mode": "assigned",
            },
        )
        granted = client.put(
            f"/mini-app/digital-employees/{employee_id}/member-grants",
            headers={"Idempotency-Key": "managed-api-grants"},
            json={
                "expected_version": configured.json()["version"],
                "member_ids": [fixture.operator_id],
            },
        )
        activated = client.post(
            f"/mini-app/digital-employees/{employee_id}/activate",
            headers={"Idempotency-Key": "managed-api-activate"},
            json={"expected_version": granted.json()["version"]},
        )
        stale = client.patch(
            f"/mini-app/digital-employees/{employee_id}/management",
            json={"expected_version": 1, "name": "stale"},
        )

    assert created.status_code == configured.status_code == granted.status_code == 200
    assert activated.status_code == 200
    assert activated.json() == {
        "id": employee_id,
        "status": "active",
        "version": 4,
        "audit_event_id": activated.json()["audit_event_id"],
    }
    assert stale.status_code == 409

    with fixture.client as operator_client:
        operator_client.headers["X-Stage06-User-Id"] = fixture.operator.user_id
        contacts = operator_client.get(
            f"/mini-app/workspaces/{fixture.workspace_id}/digital-employee-contacts?base_id={fixture.base_id}"
        )
        forbidden_detail = operator_client.get(
            f"/mini-app/digital-employees/{employee_id}/management"
        )

    assert contacts.status_code == 200
    assert [contact["id"] for contact in contacts.json()["contacts"]] == [employee_id]
    assert forbidden_detail.status_code == 403

    with fixture.client as owner_client:
        owner_client.headers["X-Stage06-User-Id"] = fixture.owner.actor_id
        paused = owner_client.post(
            f"/mini-app/digital-employees/{employee_id}/pause",
            headers={"Idempotency-Key": "managed-api-pause"},
            json={"expected_version": activated.json()["version"]},
        )
    with fixture.client as paused_operator_client:
        paused_operator_client.headers["X-Stage06-User-Id"] = fixture.operator.user_id
        paused_contacts = paused_operator_client.get(
            f"/mini-app/workspaces/{fixture.workspace_id}/digital-employee-contacts?base_id={fixture.base_id}"
        )

    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["version"] == 5
    assert paused_contacts.status_code == 200
    assert paused_contacts.json()["contacts"] == []


def test_management_api_forbids_generic_runtime_payloads_and_idempotency_changes() -> None:
    fixture = _api_fixture()
    with fixture.client as client:
        client.headers["X-Stage06-User-Id"] = fixture.owner.actor_id
        invalid_payload = client.post(
            f"/mini-app/bases/{fixture.base_id}/digital-employees/management",
            headers={"Idempotency-Key": "managed-api-invalid"},
            json={
                "name": "Bad payload",
                "description": "Must reject policy",
                "telegram_alias": None,
                "field_policy": {"viewer": "write"},
            },
        )
        first = client.post(
            f"/mini-app/bases/{fixture.base_id}/digital-employees/management",
            headers={"Idempotency-Key": "managed-api-collision"},
            json={
                "name": "Collision helper",
                "description": "First payload",
                "telegram_alias": None,
            },
        )
        collision = client.post(
            f"/mini-app/bases/{fixture.base_id}/digital-employees/management",
            headers={"Idempotency-Key": "managed-api-collision"},
            json={
                "name": "Collision changed",
                "description": "First payload",
                "telegram_alias": None,
            },
        )

    assert invalid_payload.status_code == 422
    assert first.status_code == 200
    assert collision.status_code == 409
    assert ManagedEmployeeCreateRequest.model_config["extra"] == "forbid"
    assert ManagedEmployeeUpdateRequest.model_config["extra"] == "forbid"
    assert ManagedEmployeeDetailResponse.model_config["extra"] == "forbid"


class _ApiFixture:
    def __init__(self) -> None:
        self.uow = InMemoryStage06PlatformUnitOfWork()
        self.owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
        workspace = create_workspace(
            self.uow,
            name="Employee management API",
            owner_user_id=self.owner.actor_id,
            actor=self.owner,
        )
        base = create_base(self.uow, workspace.id, name="Customers", actor=self.owner)
        table = create_table(
            self.uow,
            base.id,
            name="Customers",
            key="customers",
            actor=self.owner,
        )
        view = create_form_view(
            self.uow,
            base.id,
            table.id,
            name="Customer grid",
            view_type="grid",
            config={"fields": []},
            actor=self.owner,
        )
        self.operator = WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id="operator-1",
            role="operator",
            status="active",
            version=1,
        )
        self.uow.add_workspace_member(self.operator)
        self.workspace_id = str(workspace.id)
        self.base_id = str(base.id)
        self.table_id = str(table.id)
        self.view_id = str(view.id)
        self.operator_id = str(self.operator.id)
        app = create_app()
        app.dependency_overrides[get_stage06_platform_uow] = lambda: self.uow
        self.client = TestClient(app)


def _api_fixture() -> _ApiFixture:
    return _ApiFixture()
