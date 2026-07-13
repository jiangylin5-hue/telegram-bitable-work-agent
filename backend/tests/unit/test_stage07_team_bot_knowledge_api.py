from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.schemas.stage07_team_bot_knowledge import TeamBotSummaryRequest
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_form_view,
    create_table,
    create_workspace,
)


def test_team_bot_summary_request_is_closed_and_bounded() -> None:
    payload = {
        "base_id": str(uuid4()),
        "view_id": str(uuid4()),
        "instruction": "summarize the current team knowledge",
    }

    assert TeamBotSummaryRequest.model_validate(payload).model_dump() == payload

    with pytest.raises(ValidationError):
        TeamBotSummaryRequest.model_validate({**payload, "records": []})
    with pytest.raises(ValidationError):
        TeamBotSummaryRequest.model_validate({**payload, "instruction": "x" * 601})


def test_team_bot_contacts_return_only_safe_summary_capable_employees() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Team bot", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    view = create_form_view(
        uow, base.id, table.id, name="Current tasks", view_type="grid", config={"fields": []}, actor=owner,
    )
    summary_employee = create_digital_employee(
        uow,
        base.id,
        name="Team summary",
        description="Summarizes the permitted team view.",
        telegram_alias="private-alias",
        accessible_tables=[str(table.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=owner,
    )
    create_digital_employee(
        uow,
        base.id,
        name="Draft only",
        description="Does not belong in team knowledge contacts.",
        telegram_alias="draft-private",
        accessible_tables=[str(table.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["draft_update"],
        actor=owner,
    )
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.get(f"/mini-app/workspaces/{workspace.id}/team-bot-contacts")

    assert response.status_code == 200
    assert response.json() == {
        "workspace_id": str(workspace.id),
        "contacts": [{
            "id": str(summary_employee.id),
            "base_id": str(base.id),
            "name": "Team summary",
            "description": "Summarizes the permitted team view.",
            "available_intents": ["summarize"],
        }],
        "next_cursor": None,
        "has_more": False,
    }
    assert "private-alias" not in response.text
    assert str(table.id) not in response.text
