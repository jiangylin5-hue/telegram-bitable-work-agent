from __future__ import annotations

import os
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_session
from app.main import create_app
from app.models.audit import OpsAuditEvent
from app.models.stage06_platform import WorkspaceMember
from scripts.stage06_local_postgres_migration_smoke import (
    classify_local_postgres_url,
)


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
BACKEND_ROOT = Path(__file__).resolve().parents[2]
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv(DATABASE_URL_ENV),
        reason=f"{DATABASE_URL_ENV} is required for disposable governance PostgreSQL tests",
    ),
]


@dataclass(frozen=True)
class Stage06Postgres:
    engine: Engine
    session_factory: sessionmaker[Session]


@pytest.fixture()
def stage06_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Stage06Postgres, None, None]:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    _reset_public_schema(engine)
    command.upgrade(_alembic_config(database_url), "head")
    try:
        yield Stage06Postgres(
            engine=engine,
            session_factory=sessionmaker(
                bind=engine,
                autoflush=False,
                expire_on_commit=False,
            ),
        )
    finally:
        engine.dispose()


def test_governance_postgres_projects_paged_members_and_redacted_audit(
    stage06_postgres: Stage06Postgres,
) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(
        stage06_postgres.session_factory
    )
    suffix = uuid4().hex[:8]
    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = "governance-owner"
        workspace_id = owner.post(
            "/workspaces",
            json={
                "name": f"Governance {suffix}",
                "owner_user_id": "governance-owner",
            },
        ).json()["id"]
        base_id = owner.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "Governance Base"},
        ).json()["id"]
        table_id = owner.post(
            f"/bases/{base_id}/tables",
            json={"name": "Customers", "key": "customers"},
        ).json()["id"]
        owner.post(
            f"/tables/{table_id}/fields",
            json={"name": "Secret", "key": "secret", "field_type": "text"},
        )
        owner.post(
            f"/tables/{table_id}/records",
            json={"values": {"secret": "legacy-hidden-value"}},
        )

    with stage06_postgres.session_factory() as session:
        session.add_all(
            [
                WorkspaceMember(
                    id=uuid4(),
                    workspace_id=UUID(workspace_id),
                    user_id="governance-admin",
                    role="admin",
                    status="active",
                ),
                WorkspaceMember(
                    id=uuid4(),
                    workspace_id=UUID(workspace_id),
                    user_id="governance-viewer",
                    role="viewer",
                    status="active",
                ),
            ]
        )
        record_event = session.scalar(
            select(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "stage06.record_created"
            )
        )
        assert record_event is not None
        record_event.trace_id = "trace-secret"
        record_event.actor_id = "actor-secret"
        record_event.after_state = {"values": {"secret": "legacy-hidden-value"}}
        record_event.permission_snapshot = {"role": "owner", "internal": "secret"}
        session.commit()

    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = "governance-owner"
        members = owner.get(
            f"/mini-app/workspaces/{workspace_id}/governance/members?limit=1"
        )
        audit = owner.get(
            f"/mini-app/bases/{base_id}/governance/audit-events?limit=1"
        )
        member_next = owner.get(
            f"/mini-app/workspaces/{workspace_id}/governance/members?limit=1&cursor={members.json()['next_cursor']}"
        )
        audit_next = owner.get(
            f"/mini-app/bases/{base_id}/governance/audit-events?limit=1&cursor={audit.json()['next_cursor']}"
        )
        audit_all = owner.get(
            f"/mini-app/bases/{base_id}/governance/audit-events?limit=50"
        )

    with TestClient(app) as viewer:
        viewer.headers["X-Stage06-User-Id"] = "governance-viewer"
        denied_members = viewer.get(
            f"/mini-app/workspaces/{workspace_id}/governance/members"
        )
        denied_audit = viewer.get(
            f"/mini-app/bases/{base_id}/governance/audit-events"
        )

    assert members.status_code == audit.status_code == audit_all.status_code == 200
    assert member_next.status_code == audit_next.status_code == 200
    assert members.json()["has_more"] is True
    assert audit.json()["has_more"] is True
    assert members.json()["members"][0].keys() == {
        "id",
        "user_id",
        "role",
        "status",
    }
    assert audit.json()["events"][0].keys() == {
        "id",
        "occurred_at",
        "actor_type",
        "event_type",
        "entity_type",
    }
    response_text = (
        members.text + audit.text + audit_all.text + member_next.text + audit_next.text
    )
    assert "trace-secret" not in response_text
    assert "actor-secret" not in response_text
    assert "legacy-hidden-value" not in response_text
    assert denied_members.status_code == denied_audit.status_code == 403


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _reset_public_schema(engine: Engine) -> None:
    with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as connection:
        connection.execute(text("drop schema if exists public cascade"))
        connection.execute(text("create schema public"))
        connection.execute(text("grant all on schema public to public"))


def _session_override(session_factory: sessionmaker[Session]):
    def override() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    return override
