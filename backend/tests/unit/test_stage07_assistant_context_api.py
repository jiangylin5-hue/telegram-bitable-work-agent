from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_form_view,
    create_table,
    create_workspace,
)


def _assistant_context_fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Assistant context", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    allowed_view = create_form_view(
        uow, base.id, table.id, name="待处理", view_type="grid", config={"fields": []}, actor=owner,
    )
    excluded_view = create_form_view(
        uow, base.id, table.id, name="内部视图", view_type="kanban", config={"fields": []}, actor=owner,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="运营助理",
        description="仅汇总授权视图。",
        telegram_alias="private_alias",
        accessible_tables=[str(table.id)],
        accessible_views=[str(allowed_view.id)],
        allowed_actions=["summarize"],
        field_policy={"internal": "hidden"},
        confirmation_policy={"draft_update": "required"},
        response_style={"tone": "brief"},
        actor=owner,
    )
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow
    return app, owner, employee, base, table, allowed_view, excluded_view


def test_assistant_context_catalog_returns_only_current_employee_view_intersection() -> None:
    app, owner, employee, base, table, allowed_view, excluded_view = _assistant_context_fixture()

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.get(f"/mini-app/digital-employees/{employee.id}/assistant-context")

    assert response.status_code == 200
    assert response.json() == {
        "employee": {
            "id": str(employee.id),
            "name": "运营助理",
            "description": "仅汇总授权视图。",
            "base_id": str(base.id),
        },
        "views": [{"id": str(allowed_view.id), "name": "待处理", "view_type": "grid"}],
        "next_cursor": None,
        "has_more": False,
    }
    assert str(excluded_view.id) not in response.text
    assert str(table.id) not in response.text
    assert "private_alias" not in response.text
    assert "field_policy" not in response.text
    assert "config" not in response.text


def test_assistant_context_selected_view_rereads_only_the_allowed_safe_view() -> None:
    app, owner, employee, base, _table, allowed_view, excluded_view = _assistant_context_fixture()

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        allowed = client.get(
            f"/mini-app/digital-employees/{employee.id}/assistant-context/views/{allowed_view.id}"
        )
        excluded = client.get(
            f"/mini-app/digital-employees/{employee.id}/assistant-context/views/{excluded_view.id}"
        )
        missing = client.get(
            f"/mini-app/digital-employees/{employee.id}/assistant-context/views/{uuid4()}"
        )

    assert allowed.status_code == 200
    assert allowed.json() == {
        "id": str(allowed_view.id),
        "name": "待处理",
        "view_type": "grid",
        "base_id": str(base.id),
    }
    assert excluded.status_code == missing.status_code == 404
    assert str(excluded_view.id) not in allowed.text
    assert "config" not in allowed.text
