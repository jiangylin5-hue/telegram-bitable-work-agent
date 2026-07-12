from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select

from app.core.database import get_session
from app.main import create_app
from app.models.audit import OpsAuditEvent
from app.models.stage06_platform import PlatformField, WorkspaceMember
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    change_workspace_member_role,
)
from tests.integration.test_stage07_governance_postgres import (
    Stage06Postgres,
    _session_override,
    stage06_postgres,
)


def test_governance_write_postgres_replays_once_and_enforces_field_hiding(
    stage06_postgres: Stage06Postgres,
) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(
        stage06_postgres.session_factory
    )
    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = "governance-owner"
        workspace_id = owner.post(
            "/workspaces",
            json={"name": f"Governance Write {uuid4().hex[:8]}", "owner_user_id": "governance-owner"},
        ).json()["id"]
        base_id = owner.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "Controls"},
        ).json()["id"]
        table_id = owner.post(
            f"/bases/{base_id}/tables",
            json={"name": "Records", "key": f"records_{uuid4().hex[:8]}"},
        ).json()["id"]
        field_id = owner.post(
            f"/tables/{table_id}/fields",
            json={"name": "Internal", "key": "internal", "field_type": "text"},
        ).json()["id"]
        record_id = owner.post(
            f"/tables/{table_id}/records",
            json={"values": {"internal": "secret-value"}},
        ).json()["id"]

    with stage06_postgres.session_factory() as session:
        operator = WorkspaceMember(
            id=uuid4(),
            workspace_id=UUID(workspace_id),
            user_id="governance-operator",
            role="operator",
            status="active",
        )
        session.add_all(
            [
                WorkspaceMember(
                    id=uuid4(),
                    workspace_id=UUID(workspace_id),
                    user_id="governance-admin",
                    role="admin",
                    status="active",
                ),
                operator,
                WorkspaceMember(
                    id=uuid4(),
                    workspace_id=UUID(workspace_id),
                    user_id="governance-viewer",
                    role="viewer",
                    status="active",
                ),
            ]
        )
        session.commit()
        operator_id = str(operator.id)

    policy = {
        "owner": "write",
        "admin": "write",
        "builder": "write",
        "operator": "read",
        "viewer": "hidden",
    }
    with TestClient(app) as admin:
        admin.headers["X-Stage06-User-Id"] = "governance-admin"
        first = admin.patch(
            f"/mini-app/workspaces/{workspace_id}/governance/members/{operator_id}/role",
            headers={"Idempotency-Key": "postgres-role-replay"},
            json={"role": "builder", "expected_version": 1},
        )
        replay = admin.patch(
            f"/mini-app/workspaces/{workspace_id}/governance/members/{operator_id}/role",
            headers={"Idempotency-Key": "postgres-role-replay"},
            json={"role": "builder", "expected_version": 1},
        )
        stale = admin.patch(
            f"/mini-app/workspaces/{workspace_id}/governance/members/{operator_id}/role",
            headers={"Idempotency-Key": "postgres-role-stale"},
            json={"role": "operator", "expected_version": 1},
        )
        policy_response = admin.put(
            f"/mini-app/tables/{table_id}/governance/fields/{field_id}/permission-policy",
            headers={"Idempotency-Key": "postgres-policy"},
            json={"expected_permission_version": 1, "policy": policy},
        )

    with TestClient(app) as viewer:
        viewer.headers["X-Stage06-User-Id"] = "governance-viewer"
        schema = viewer.get(f"/tables/{table_id}/schema")
        detail = viewer.get(f"/records/{record_id}")
        update = viewer.patch(
            f"/records/{record_id}",
            json={"values": {"internal": "forbidden"}, "expected_version": 1},
        )

    assert first.status_code == replay.status_code == policy_response.status_code == 200
    assert stale.status_code == 409
    assert first.json()["version"] == replay.json()["version"] == 2
    assert policy_response.json()["permission_version"] == 2
    assert schema.status_code == detail.status_code == 200
    assert "internal" not in {field["key"] for field in schema.json()["fields"]}
    assert "internal" not in detail.json()["values"]
    assert update.status_code == 403

    with stage06_postgres.session_factory() as session:
        assert session.scalar(
            select(func.count()).select_from(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "stage07.workspace_member_role_changed"
            )
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "stage07.field_permission_policy_replaced"
            )
        ) == 1
        assert session.get(PlatformField, UUID(field_id)).permission_version == 2
        assert session.get(WorkspaceMember, UUID(operator_id)).version == 2
    columns = {column["name"] for column in inspect(stage06_postgres.engine).get_columns("workspace_members")}
    assert "version" in columns
    assert "permission_version" in {
        column["name"] for column in inspect(stage06_postgres.engine).get_columns("fields")
    }


def test_governance_write_postgres_locks_stale_role_command(
    stage06_postgres: Stage06Postgres,
) -> None:
    workspace_id, member_id = _create_concurrent_membership(stage06_postgres)
    barrier = Barrier(2)
    actor = Actor(actor_type="user", actor_id="concurrent-owner", role="owner")

    def change(role: str) -> str:
        with stage06_postgres.session_factory() as session:
            uow = SqlAlchemyStage06PlatformUnitOfWork(session)
            barrier.wait()
            try:
                change_workspace_member_role(
                    uow,
                    workspace_id,
                    member_id,
                    role=role,
                    expected_version=1,
                    actor=actor,
                )
                session.commit()
                return "updated"
            except PlatformValidationError as exc:
                session.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(change, ["builder", "viewer"]))

    assert sorted(outcomes) == ["governance_revision_conflict", "updated"]
    with stage06_postgres.session_factory() as session:
        member = session.get(WorkspaceMember, member_id)
        assert member is not None
        assert member.version == 2
        assert session.scalar(
            select(func.count()).select_from(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "stage07.workspace_member_role_changed"
            )
        ) == 1


def _create_concurrent_membership(stage06_postgres: Stage06Postgres) -> tuple[UUID, UUID]:
    from app.services.stage06_platform import create_workspace

    owner = Actor(actor_type="user", actor_id="concurrent-owner", role="owner")
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Concurrent governance {uuid4().hex[:8]}",
            owner_user_id=owner.actor_id,
            actor=owner,
        )
        member = WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id="concurrent-member",
            role="operator",
            status="active",
        )
        uow.add_workspace_member(member)
        session.commit()
        return workspace.id, member.id
