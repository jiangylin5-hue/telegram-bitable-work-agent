from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.models.stage06_runtime import RecordChangeDraft
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
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
