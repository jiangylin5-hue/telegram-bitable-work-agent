from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_session
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import SqlAlchemyStage06PlatformUnitOfWork
from tests.integration.test_stage07_governance_postgres import (
    DATABASE_URL_ENV,
    Stage06Postgres,
    _session_override,
    stage06_postgres,
)


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv(DATABASE_URL_ENV),
        reason=f"{DATABASE_URL_ENV} is required for disposable assistant-context PostgreSQL tests",
    ),
]


def test_assistant_context_postgres_rechecks_employee_table_scope_after_catalog_selection(
    stage06_postgres: Stage06Postgres,
) -> None:
    """A view ID alone must never keep Home assistant context usable after table scope revocation."""
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(stage06_postgres.session_factory)
    owner_id = "assistant-context-postgres-owner"
    suffix = uuid4().hex[:8]

    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = owner_id
        workspace_id = owner.post(
            "/workspaces",
            json={"name": f"Assistant context {suffix}", "owner_user_id": owner_id},
        ).json()["id"]
        base_id = owner.post(
            f"/workspaces/{workspace_id}/bases", json={"name": "Operations"}
        ).json()["id"]
        table_id = owner.post(
            f"/bases/{base_id}/tables",
            json={"name": "Tasks", "key": f"tasks_{suffix}"},
        ).json()["id"]
        owner.post(
            f"/tables/{table_id}/fields",
            json={"name": "Title", "key": "title", "field_type": "text"},
        )
        view_id = owner.post(
            f"/bases/{base_id}/views",
            json={
                "table_id": table_id,
                "name": "Current tasks",
                "view_type": "grid",
                "config": {"fields": ["title"]},
            },
        ).json()["id"]

    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        employee = create_digital_employee(
            uow,
            UUID(base_id),
            name="Scoped assistant",
            description="Summarizes only the current permitted task view.",
            telegram_alias=None,
            accessible_tables=[table_id],
            accessible_views=[view_id],
            allowed_actions=["summarize"],
            actor=Actor(actor_type="user", actor_id=owner_id, role="owner"),
        )
        session.commit()
        employee_id = str(employee.id)

    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = owner_id
        before_revocation = owner.get(
            f"/mini-app/digital-employees/{employee_id}/assistant-context"
        )

    assert before_revocation.status_code == 200
    assert before_revocation.json()["views"] == [
        {"id": view_id, "name": "Current tasks", "view_type": "grid"}
    ]

    with stage06_postgres.session_factory() as session:
        employee = session.get(type(employee), UUID(employee_id))
        assert employee is not None
        employee.accessible_tables = []
        session.commit()

    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = owner_id
        catalog_after_revocation = owner.get(
            f"/mini-app/digital-employees/{employee_id}/assistant-context"
        )
        selected_after_revocation = owner.get(
            f"/mini-app/digital-employees/{employee_id}/assistant-context/views/{view_id}"
        )

    assert catalog_after_revocation.status_code == 200
    assert catalog_after_revocation.json()["views"] == []
    assert selected_after_revocation.status_code == 404
    assert table_id not in catalog_after_revocation.text
