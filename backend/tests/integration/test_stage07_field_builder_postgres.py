from __future__ import annotations

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes import stage06_platform as platform_routes
from app.core.database import get_session
from app.main import create_app
from app.models.audit import OpsAuditEvent
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_platform import PlatformField, PlatformView
from app.services.stage06_platform import PlatformValidationError
from scripts.stage06_local_postgres_migration_smoke import (
    classify_local_postgres_url,
)


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
BACKEND_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage07 PostgreSQL field builder tests",
)


@dataclass(frozen=True)
class Stage07Postgres:
    engine: Engine
    session_factory: sessionmaker[Session]


@pytest.fixture()
def stage07_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Stage07Postgres, None, None]:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    _reset_public_schema(engine)
    command.upgrade(_alembic_config(database_url), "head")
    try:
        yield Stage07Postgres(
            engine=engine,
            session_factory=sessionmaker(
                bind=engine,
                autoflush=False,
                expire_on_commit=False,
            ),
        )
    finally:
        engine.dispose()


def test_field_initialization_rolls_back_field_view_audit_and_idempotency(
    stage07_postgres: Stage07Postgres,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _postgres_app(stage07_postgres)
    table_id, view_id = _create_fieldless_table(app, owner_id="rollback-owner")
    original_initialize_field = platform_routes.initialize_field

    def failing_initialize_field(*args, **kwargs):
        original_initialize_field(*args, **kwargs)
        raise PlatformValidationError("injected_field_failure", "injected")

    monkeypatch.setattr(platform_routes, "initialize_field", failing_initialize_field)

    with TestClient(app) as client:
        failed = client.post(
            f"/tables/{table_id}/field-initializations",
            headers={
                "X-Stage06-User-Id": "rollback-owner",
                "Idempotency-Key": "field-rollback-1",
            },
            json={"name": "Stage", "field_type": "text", "required": False},
        )

    assert failed.status_code == 422
    with stage07_postgres.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlatformField)) == 0
        view = session.get(PlatformView, UUID(view_id))
        assert view is not None
        assert view.config == {"fields": []}
        assert (
            session.scalar(
                select(func.count())
                .select_from(OpsAuditEvent)
                .where(OpsAuditEvent.event_type == "stage07.field_initialized")
            )
            == 0
        )
        assert session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord)) == 0


def test_field_initialization_same_key_replays_one_field_and_one_audit(
    stage07_postgres: Stage07Postgres,
) -> None:
    app = _postgres_app(stage07_postgres)
    table_id, view_id = _create_fieldless_table(app, owner_id="replay-owner")
    headers = {
        "X-Stage06-User-Id": "replay-owner",
        "Idempotency-Key": "field-replay-1",
    }
    payload = {
        "name": "Stage",
        "field_type": "status",
        "required": True,
        "choices": ["new", "active"],
    }

    with TestClient(app) as client:
        created = client.post(f"/tables/{table_id}/field-initializations", headers=headers, json=payload)
        replayed = client.post(f"/tables/{table_id}/field-initializations", headers=headers, json=payload)

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.json() == created.json()
    with stage07_postgres.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlatformField)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(OpsAuditEvent)
                .where(OpsAuditEvent.event_type == "stage07.field_initialized")
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord)) == 1
        view = session.get(PlatformView, UUID(view_id))
        assert view is not None
        assert view.config == {"fields": [created.json()["field"]["key"]]}


def test_concurrent_distinct_field_initializations_receive_consecutive_order(
    stage07_postgres: Stage07Postgres,
) -> None:
    app = _postgres_app(stage07_postgres)
    table_id, view_id = _create_fieldless_table(app, owner_id="concurrency-owner")
    barrier = Barrier(2)

    def submit(name: str, idempotency_key: str) -> tuple[int, dict]:
        barrier.wait()
        with TestClient(app) as client:
            response = client.post(
                f"/tables/{table_id}/field-initializations",
                headers={
                    "X-Stage06-User-Id": "concurrency-owner",
                    "Idempotency-Key": idempotency_key,
                },
                json={"name": name, "field_type": "text", "required": False},
            )
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda item: submit(*item),
                [("First", "field-concurrent-1"), ("Second", "field-concurrent-2")],
            )
        )

    assert [status for status, _body in results] == [201, 201]
    assert sorted(body["field"]["order_index"] for _status, body in results) == [0, 1]
    with stage07_postgres.session_factory() as session:
        fields = list(session.scalars(select(PlatformField).order_by(PlatformField.order_index)))
        assert [field.order_index for field in fields] == [0, 1]
        view = session.get(PlatformView, UUID(view_id))
        assert view is not None
        assert set(view.config["fields"]) == {field.key for field in fields}


def _postgres_app(stage07_postgres: Stage07Postgres):
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(stage07_postgres.session_factory)
    return app


def _create_fieldless_table(app, *, owner_id: str) -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner_id
        workspace_id = client.post(
            "/workspaces",
            json={"name": f"F1 {suffix}", "owner_user_id": owner_id},
        ).json()["id"]
        base_id = client.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "Operations"},
        ).json()["id"]
        table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Projects", "key": f"projects-{suffix}"},
        ).json()["id"]
        view_id = client.post(
            f"/bases/{base_id}/views",
            json={
                "table_id": table_id,
                "name": "All projects",
                "view_type": "grid",
                "config": {"fields": []},
            },
        ).json()["id"]
    return table_id, view_id


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
