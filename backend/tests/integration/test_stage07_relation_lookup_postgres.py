from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.routes import stage06_platform as platform_routes
from app.models.audit import OpsAuditEvent
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_platform import PlatformField, PlatformView
from app.services.stage06_platform import PlatformValidationError
from tests.integration.test_stage07_field_builder_postgres import (
    DATABASE_URL_ENV,
    Stage07Postgres,
    _postgres_app,
    stage07_postgres,
)


pytestmark = pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage07 F2 PostgreSQL tests",
)


def test_relation_initializer_rolls_back_field_view_audit_and_idempotency(
    stage07_postgres: Stage07Postgres,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _postgres_app(stage07_postgres)
    source_id, target_id, view_id = _create_relation_tables(app, owner_id="f2-rollback")
    original = platform_routes.initialize_relation_field

    def failing_initializer(*args, **kwargs):
        original(*args, **kwargs)
        raise PlatformValidationError("injected_relation_failure", "injected")

    monkeypatch.setattr(platform_routes, "initialize_relation_field", failing_initializer)
    with TestClient(app) as client:
        failed = client.post(
            f"/tables/{source_id}/relation-field-initializations",
            headers={"X-Stage06-User-Id": "f2-rollback", "Idempotency-Key": "f2-rollback-1"},
            json={"name": "Customer", "target_table_id": target_id, "required": False},
        )

    assert failed.status_code == 422
    with stage07_postgres.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlatformField)) == 0
        assert session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(OpsAuditEvent)
                .where(OpsAuditEvent.event_type == "stage07.relation_field_initialized")
            )
            == 0
        )
        view = session.get(PlatformView, UUID(view_id))
        assert view is not None and view.config == {"fields": []}


def test_concurrent_relation_initializers_have_consecutive_order(
    stage07_postgres: Stage07Postgres,
) -> None:
    app = _postgres_app(stage07_postgres)
    source_id, target_id, view_id = _create_relation_tables(app, owner_id="f2-concurrent")
    barrier = Barrier(2)

    def submit(name: str, key: str) -> tuple[int, dict]:
        barrier.wait()
        with TestClient(app) as client:
            response = client.post(
                f"/tables/{source_id}/relation-field-initializations",
                headers={"X-Stage06-User-Id": "f2-concurrent", "Idempotency-Key": key},
                json={"name": name, "target_table_id": target_id, "required": False},
            )
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda item: submit(*item), [("First", "f2-one"), ("Second", "f2-two")]))

    assert [status for status, _ in results] == [201, 201]
    assert sorted(body["field"]["order_index"] for _, body in results) == [0, 1]
    with stage07_postgres.session_factory() as session:
        fields = list(session.scalars(select(PlatformField).order_by(PlatformField.order_index)))
        view = session.get(PlatformView, UUID(view_id))
        assert len(fields) == 2
        assert view is not None and set(view.config["fields"]) == {field.key for field in fields}


def _create_relation_tables(app, *, owner_id: str) -> tuple[str, str, str]:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner_id
        workspace_id = client.post("/workspaces", json={"name": f"F2 {suffix}", "owner_user_id": owner_id}).json()["id"]
        base_id = client.post(f"/workspaces/{workspace_id}/bases", json={"name": "Operations"}).json()["id"]
        source_id = client.post(f"/bases/{base_id}/tables", json={"name": "Projects", "key": f"projects-{suffix}"}).json()["id"]
        target_id = client.post(f"/bases/{base_id}/tables", json={"name": "Customers", "key": f"customers-{suffix}"}).json()["id"]
        view_id = client.post(
            f"/bases/{base_id}/views",
            json={"table_id": source_id, "name": "All projects", "view_type": "grid", "config": {"fields": []}},
        ).json()["id"]
    return source_id, target_id, view_id
