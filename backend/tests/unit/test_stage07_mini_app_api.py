from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.models.stage06_runtime import RecordChangeDraft
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


def test_mini_app_bootstrap_only_returns_active_memberships_for_identity() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Owner workspace", "owner_user_id": "owner-1"},
        ).json()["id"]
        client.headers["X-Stage06-User-Id"] = "owner-2"
        other_workspace_id = client.post(
            "/workspaces",
            json={"name": "Other workspace", "owner_user_id": "owner-2"},
        ).json()["id"]
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(),
                workspace_id=UUID(other_workspace_id),
                user_id="owner-1",
                role="viewer",
                status="inactive",
            )
        )

        client.headers["X-Stage06-User-Id"] = "owner-1"
        response = client.get("/mini-app/bootstrap")

    assert response.status_code == 200
    assert response.json() == {
        "identity": {"user_id": "owner-1", "source": "development_header"},
        "workspaces": [
            {
                "id": workspace_id,
                "name": "Owner workspace",
                "slug": "owner-workspace",
                "role": "owner",
                "capabilities": {
                    "can_read_bases": True,
                    "can_manage_workspace": True,
                    "can_manage_schema": True,
                    "can_review_drafts": True,
                },
            }
        ],
    }


def test_workspace_home_returns_safe_base_and_draft_queue_models() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        base_id = client.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "Operations", "description": "Internal workspace"},
        ).json()["id"]
        draft_id = uuid4()
        uow.add_record_change_draft(
            RecordChangeDraft(
                id=draft_id,
                workspace_id=UUID(workspace_id),
                base_id=UUID(base_id),
                table_id=uuid4(),
                record_id=None,
                draft_type="record_update",
                proposed_values={"sensitive": "must not reach home"},
                before_values={"sensitive": "must not reach home"},
                created_by_type="agent",
                created_by_id="agent-1",
                status="pending_confirmation",
                confirmation_policy={},
                trace_id="trace-1",
                expected_version=1,
            )
        )

        response = client.get(f"/workspaces/{workspace_id}/home")

    assert response.status_code == 200
    body = response.json()
    assert body["recent_bases"] == [
        {
            "id": base_id,
            "name": "Operations",
            "source_type": "blank",
        }
    ]
    assert body["queue"] == [
        {
            "id": str(draft_id),
            "kind": "record_change_draft",
            "title": "待确认变更",
            "status": "pending_confirmation",
            "destination": {"base_id": base_id, "draft_id": str(draft_id)},
            "action_availability": {"can_confirm": True, "can_reject": True},
        }
    ]
    assert "sensitive" not in response.text


def test_workspace_home_denies_non_members() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        client.headers["X-Stage06-User-Id"] = "outsider-1"
        response = client.get(f"/workspaces/{workspace_id}/home")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "stage06_membership_required"
