from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.api.routes.stage06_templates import get_stage06_template_import_uow
from app.main import app
from app.models.stage06_platform import WorkspaceMember
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_workspace,
)


def _headers(user_id: str) -> dict[str, str]:
    return {"X-Stage06-User-Id": user_id}


def test_stage06_workspace_create_requires_identity() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    try:
        response = TestClient(app).post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "stage06_identity_required"


def test_stage06_workspace_create_rejects_different_owner_user() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    try:
        response = TestClient(app).post(
            "/workspaces",
            headers=_headers("owner-1"),
            json={"name": "Acme", "owner_user_id": "other-user"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "workspace_owner_mismatch"


def test_stage06_viewer_cannot_create_base() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id="viewer-1",
            role="viewer",
            status="active",
        )
    )
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    try:
        response = TestClient(app).post(
            f"/workspaces/{workspace.id}/bases",
            headers=_headers("viewer-1"),
            json={"name": "Denied"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "stage06_action_denied"
    assert uow.bases == []


def test_stage06_outsider_cannot_read_base() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    try:
        response = TestClient(app).get(
            f"/bases/{base.id}",
            headers=_headers("outsider-1"),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "stage06_membership_required"


def test_stage06_owner_can_create_and_read_own_workspace() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    try:
        client = TestClient(app)
        create_response = client.post(
            "/workspaces",
            headers=_headers("owner-1"),
            json={"name": "Acme", "owner_user_id": "owner-1"},
        )
        read_response = client.get(
            f"/workspaces/{create_response.json()['id']}",
            headers=_headers("owner-1"),
        )
    finally:
        app.dependency_overrides.clear()

    assert create_response.status_code == 200
    assert read_response.status_code == 200
    assert read_response.json()["owner_user_id"] == "owner-1"


def test_stage06_template_list_requires_identity() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_template_import_uow] = lambda: uow
    try:
        response = TestClient(app).get("/templates")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "stage06_identity_required"


def test_stage06_viewer_cannot_create_import_job() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id="viewer-1",
            role="viewer",
            status="active",
        )
    )
    app.dependency_overrides[get_stage06_template_import_uow] = lambda: uow
    try:
        response = TestClient(app).post(
            f"/workspaces/{workspace.id}/imports",
            headers=_headers("viewer-1"),
            json={
                "source_type": "csv",
                "file_name": "data.csv",
                "content": "name\nAda",
                "created_by_user_id": "viewer-1",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "stage06_action_denied"
    assert uow.import_jobs == []


def test_stage06_outsider_cannot_read_digital_employee() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    employee = create_digital_employee(
        uow,
        base.id,
        name="Ops",
        description="Ops helper",
        telegram_alias="ops",
        accessible_tables=[],
        accessible_views=[],
        allowed_actions=["summarize"],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow
    try:
        response = TestClient(app).get(
            f"/digital-employees/{employee.id}",
            headers=_headers("outsider-1"),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "stage06_membership_required"
