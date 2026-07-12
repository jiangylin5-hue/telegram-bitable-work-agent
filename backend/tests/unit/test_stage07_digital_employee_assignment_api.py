from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.models.stage06_runtime import DigitalEmployeeMemberGrant
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_form_view,
    create_table,
    create_workspace,
)


def test_assigned_employee_requires_member_grant_for_contact_context_and_invoke(
    monkeypatch,
) -> None:
    fixture = _assignment_fixture()
    runtime_calls: list[str] = []

    def fake_invoke(*args, **kwargs):
        runtime_calls.append(str(kwargs["actor"].actor_id))
        return {"answer": "safe summary", "citations": []}

    monkeypatch.setattr(
        "app.api.routes.stage07_draft_employee_hub.invoke_digital_employee",
        fake_invoke,
    )
    with TestClient(fixture.app) as operator_client:
        operator_client.headers["X-Stage06-User-Id"] = fixture.operator.user_id
        assigned_contacts = operator_client.get(
            f"/mini-app/workspaces/{fixture.workspace_id}/digital-employee-contacts"
        )
        assigned_context = operator_client.get(
            f"/mini-app/digital-employees/{fixture.assigned_employee_id}/assistant-context"
        )

    with TestClient(fixture.app) as viewer_client:
        viewer_client.headers["X-Stage06-User-Id"] = fixture.viewer.user_id
        viewer_contacts = viewer_client.get(
            f"/mini-app/workspaces/{fixture.workspace_id}/digital-employee-contacts"
        )
        denied_context = viewer_client.get(
            f"/mini-app/digital-employees/{fixture.assigned_employee_id}/assistant-context"
        )
        legacy_context = viewer_client.get(
            f"/mini-app/digital-employees/{fixture.legacy_employee_id}/assistant-context"
        )
        denied_invoke = viewer_client.post(
            f"/mini-app/digital-employees/{fixture.assigned_employee_id}/invocations",
            json={
                "intent": "summarize",
                "base_id": fixture.base_id,
                "view_id": fixture.view_id,
            },
        )

    assert assigned_contacts.status_code == assigned_context.status_code == 200
    assert {item["id"] for item in assigned_contacts.json()["contacts"]} == {
        fixture.assigned_employee_id,
        fixture.legacy_employee_id,
    }
    assert viewer_contacts.status_code == 200
    assert [item["id"] for item in viewer_contacts.json()["contacts"]] == [
        fixture.legacy_employee_id
    ]
    assert denied_context.status_code == denied_invoke.status_code == 404
    assert legacy_context.status_code == 200
    assert runtime_calls == []


class _AssignmentFixture:
    def __init__(self) -> None:
        self.uow = InMemoryStage06PlatformUnitOfWork()
        self.owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
        workspace = create_workspace(
            self.uow,
            name="Assigned employee eligibility",
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
        self.viewer = WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id="viewer-1",
            role="viewer",
            status="active",
            version=1,
        )
        self.uow.add_workspace_member(self.operator)
        self.uow.add_workspace_member(self.viewer)
        assigned = create_digital_employee(
            self.uow,
            base.id,
            name="Assigned helper",
            description="Only the operator may use this helper",
            telegram_alias=None,
            accessible_tables=[str(table.id)],
            accessible_views=[str(view.id)],
            allowed_actions=["summarize"],
            actor=self.owner,
        )
        assigned.access_mode = "assigned"
        self.uow.add_digital_employee_member_grant(
            DigitalEmployeeMemberGrant(
                id=uuid4(),
                employee_id=assigned.id,
                workspace_member_id=self.operator.id,
            )
        )
        legacy = create_digital_employee(
            self.uow,
            base.id,
            name="Legacy workspace helper",
            description="Every existing authorized member remains eligible",
            telegram_alias=None,
            accessible_tables=[str(table.id)],
            accessible_views=[str(view.id)],
            allowed_actions=["summarize"],
            actor=self.owner,
        )
        self.workspace_id = str(workspace.id)
        self.base_id = str(base.id)
        self.view_id = str(view.id)
        self.assigned_employee_id = str(assigned.id)
        self.legacy_employee_id = str(legacy.id)
        self.app = create_app()
        self.app.dependency_overrides[get_stage06_platform_uow] = lambda: self.uow


def _assignment_fixture() -> _AssignmentFixture:
    return _AssignmentFixture()
