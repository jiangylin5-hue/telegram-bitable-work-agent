from __future__ import annotations

import json
import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_session
from app.main import create_app
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_templates import ImportJob
from scripts.stage06_local_postgres_migration_smoke import (
    classify_local_postgres_url,
)


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
BACKEND_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage06 PostgreSQL security tests",
)


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


def test_stage06_postgres_enforces_tenant_permission_and_audit_redaction(
    stage06_postgres: Stage06Postgres,
) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(
        stage06_postgres.session_factory
    )
    suffix = uuid4().hex[:8]

    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = "owner-a"
        workspace_id = owner.post(
            "/workspaces",
            json={"name": f"Tenant A {suffix}", "owner_user_id": "owner-a"},
        ).json()["id"]
        base_id = owner.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "Sensitive Base"},
        ).json()["id"]
        table_id = owner.post(
            f"/bases/{base_id}/tables",
            json={"name": "Secrets", "key": "secrets"},
        ).json()["id"]
        owner.post(
            f"/tables/{table_id}/fields",
            json={"name": "Secret", "key": "secret", "field_type": "text"},
        )
        record_response = owner.post(
            f"/tables/{table_id}/records",
            json={"values": {"secret": "must-not-leak"}},
        )
        audit_response = owner.get(f"/bases/{base_id}/audit-events")

    with TestClient(app) as outsider:
        outsider.headers["X-Stage06-User-Id"] = "owner-b"
        outsider.post(
            "/workspaces",
            json={"name": f"Tenant B {suffix}", "owner_user_id": "owner-b"},
        )
        denied_base = outsider.get(f"/bases/{base_id}")
        denied_audit = outsider.get(f"/bases/{base_id}/audit-events")

    assert record_response.status_code == 200
    assert audit_response.status_code == 200
    assert "must-not-leak" not in json.dumps(audit_response.json(), ensure_ascii=False)
    assert denied_base.status_code == 403
    assert denied_base.json()["detail"]["code"] == "stage06_membership_required"
    assert denied_audit.status_code == 403


def test_stage06_postgres_idempotency_has_one_winner_under_concurrency(
    stage06_postgres: Stage06Postgres,
) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(
        stage06_postgres.session_factory
    )
    suffix = uuid4().hex[:8]
    headers = {
        "X-Stage06-User-Id": "concurrency-owner",
        "Idempotency-Key": f"concurrent-import-{suffix}",
    }
    with TestClient(app) as client:
        workspace_id = client.post(
            "/workspaces",
            headers=headers,
            json={
                "name": f"Concurrency {suffix}",
                "owner_user_id": "concurrency-owner",
            },
        ).json()["id"]

    payload = {
        "source_type": "csv",
        "file_name": "customers.csv",
        "content": "name\nAda",
        "created_by_user_id": "concurrency-owner",
    }
    barrier = Barrier(2)

    def create_import() -> tuple[int, dict]:
        barrier.wait()
        with TestClient(app) as concurrent_client:
            response = concurrent_client.post(
                f"/workspaces/{workspace_id}/imports",
                headers=headers,
                json=payload,
            )
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: create_import(), range(2)))

    with TestClient(app) as retry_client:
        retry = retry_client.post(
            f"/workspaces/{workspace_id}/imports",
            headers=headers,
            json=payload,
        )

    assert {status for status, _body in results}.issubset({200, 409})
    assert any(status == 200 for status, _body in results)
    assert retry.status_code == 200
    with stage06_postgres.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ImportJob)) == 1
        assert (
            session.scalar(
                select(func.count()).select_from(Stage06IdempotencyRecord)
            )
            == 1
        )


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
