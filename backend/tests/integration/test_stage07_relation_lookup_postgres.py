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
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    assert_field_has_no_relation_lookup_dependents,
    assert_record_has_no_incoming_relation_links,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
    initialize_lookup_field,
    initialize_relation_field,
    list_view_records,
)
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


def test_relation_initializer_replay_persists_one_field_view_audit_and_receipt(
    stage07_postgres: Stage07Postgres,
) -> None:
    app = _postgres_app(stage07_postgres)
    source_id, target_id, view_id = _create_relation_tables(app, owner_id="f2-replay")
    headers = {"X-Stage06-User-Id": "f2-replay", "Idempotency-Key": "f2-replay-1"}
    payload = {"name": "Customer", "target_table_id": target_id, "required": True}

    with TestClient(app) as client:
        created = client.post(f"/tables/{source_id}/relation-field-initializations", headers=headers, json=payload)
        replayed = client.post(f"/tables/{source_id}/relation-field-initializations", headers=headers, json=payload)

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.json() == created.json()
    with stage07_postgres.session_factory() as session:
        field = session.scalar(select(PlatformField))
        view = session.get(PlatformView, UUID(view_id))
        assert field is not None
        assert view is not None and view.config == {"fields": [field.key]}
        assert session.scalar(select(func.count()).select_from(PlatformField)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(OpsAuditEvent)
                .where(OpsAuditEvent.event_type == "stage07.relation_field_initialized")
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Stage06IdempotencyRecord)
                .where(
                    Stage06IdempotencyRecord.operation == "stage07.relation_field.initialize",
                    Stage06IdempotencyRecord.idempotency_key == "f2-replay-1",
                )
            )
            == 1
        )


def test_lookup_initializer_rolls_back_field_view_audit_and_idempotency(
    stage07_postgres: Stage07Postgres,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _postgres_app(stage07_postgres)
    source_id, _target_id, view_id, relation_id, amount_id, relation_key = _create_lookup_fields(
        app,
        owner_id="f2-lookup-rollback",
    )
    original = platform_routes.initialize_lookup_field

    def failing_initializer(*args, **kwargs):
        original(*args, **kwargs)
        raise PlatformValidationError("injected_lookup_failure", "injected")

    monkeypatch.setattr(platform_routes, "initialize_lookup_field", failing_initializer)
    with TestClient(app) as client:
        failed = client.post(
            f"/tables/{source_id}/lookup-field-initializations",
            headers={"X-Stage06-User-Id": "f2-lookup-rollback", "Idempotency-Key": "f2-lookup-rollback-1"},
            json={
                "name": "Customer total",
                "source_relation_field_id": relation_id,
                "target_field_id": amount_id,
                "aggregation": "sum",
            },
        )

    assert failed.status_code == 422
    with stage07_postgres.session_factory() as session:
        fields = list(session.scalars(select(PlatformField).order_by(PlatformField.order_index)))
        view = session.get(PlatformView, UUID(view_id))
        assert {field.field_type for field in fields} == {"linked_record", "number"}
        assert len(fields) == 2
        assert all(field.name != "Customer total" for field in fields)
        assert view is not None and view.config == {"fields": [relation_key]}
        assert (
            session.scalar(
                select(func.count())
                .select_from(OpsAuditEvent)
                .where(OpsAuditEvent.event_type == "stage07.lookup_field_initialized")
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Stage06IdempotencyRecord)
                .where(
                    Stage06IdempotencyRecord.operation == "stage07.lookup_field.initialize",
                    Stage06IdempotencyRecord.idempotency_key == "f2-lookup-rollback-1",
                )
            )
            == 0
        )


def test_relation_and_lookup_delete_guards_detect_real_postgres_dependencies(
    stage07_postgres: Stage07Postgres,
) -> None:
    actor = Actor(actor_type="user", actor_id="f2-guards", role="owner")
    with stage07_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(uow, name="F2 guards", owner_user_id=actor.actor_id, actor=actor)
        session.flush()
        base = create_base(uow, workspace.id, name="Operations", actor=actor)
        source = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
        target = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
        label = create_field(uow, target.id, name="Name", key="name", field_type="text", actor=actor)
        amount = create_field(uow, target.id, name="Amount", key="amount", field_type="number", actor=actor)
        session.flush()
        target.primary_field_id = label.id
        relation = initialize_relation_field(
            uow,
            source.id,
            name="Customer",
            target_table_id=target.id,
            required=False,
            actor=actor,
        ).field
        session.flush()
        target_record = create_record(uow, target.id, values={label.key: "Acme", amount.key: 7}, actor=actor)
        session.flush()
        create_record(uow, source.id, values={relation.key: [str(target_record.id)]}, actor=actor)
        lookup = initialize_lookup_field(
            uow,
            source.id,
            name="Customer total",
            source_relation_field_id=relation.id,
            target_field_id=amount.id,
            aggregation="sum",
            actor=actor,
        ).field
        session.commit()

    with stage07_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        with pytest.raises(PlatformValidationError) as record_error:
            assert_record_has_no_incoming_relation_links(uow, target_record.id)
        with pytest.raises(PlatformValidationError) as relation_error:
            assert_field_has_no_relation_lookup_dependents(uow, relation.id)
        with pytest.raises(PlatformValidationError) as target_error:
            assert_field_has_no_relation_lookup_dependents(uow, amount.id)

    assert record_error.value.code == "record_is_referenced"
    assert relation_error.value.code == "field_has_dependencies"
    assert target_error.value.code == "field_has_dependencies"
    assert lookup.id is not None


def test_lookup_projection_evaluates_every_approved_fixed_aggregation_on_real_postgres(
    stage07_postgres: Stage07Postgres,
) -> None:
    actor = Actor(actor_type="user", actor_id="f2-aggregation", role="owner")
    expected = {
        "values": [2, 2, 5],
        "count": 3,
        "count_distinct": 2,
        "sum": 9,
        "average": 3,
        "min": 2,
        "max": 5,
    }

    with stage07_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(uow, name="F2 aggregations", owner_user_id=actor.actor_id, actor=actor)
        session.flush()
        base = create_base(uow, workspace.id, name="Operations", actor=actor)
        source = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
        target = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
        label = create_field(uow, target.id, name="Name", key="name", field_type="text", actor=actor)
        amount = create_field(uow, target.id, name="Amount", key="amount", field_type="number", actor=actor)
        session.flush()
        target.primary_field_id = label.id
        relation = initialize_relation_field(
            uow,
            source.id,
            name="Customer",
            target_table_id=target.id,
            required=False,
            actor=actor,
        ).field
        session.flush()
        targets = [
            create_record(uow, target.id, values={label.key: name, amount.key: value}, actor=actor)
            for name, value in (("Acme", 2), ("Bravo", 2), ("Cyan", 5))
        ]
        session.flush()
        source_record = create_record(
            uow,
            source.id,
            values={relation.key: [str(record.id) for record in targets]},
            actor=actor,
        )
        lookup_fields = {
            aggregation: initialize_lookup_field(
                uow,
                source.id,
                name=f"Customer {aggregation}",
                source_relation_field_id=relation.id,
                target_field_id=amount.id,
                aggregation=aggregation,
                actor=actor,
            ).field
            for aggregation in expected
        }
        session.flush()
        view = create_form_view(
            uow,
            base.id,
            source.id,
            name="All projects",
            view_type="grid",
            config={"fields": [field.key for field in lookup_fields.values()]},
            actor=actor,
        )
        session.flush()

        response = list_view_records(uow, view.id, actor=actor, limit=50, cursor=None)
        session.commit()

    assert response["records"] == [{
        "id": str(source_record.id),
        "fields": {lookup_fields[aggregation].key: value for aggregation, value in expected.items()},
    }]


def _create_lookup_fields(
    app,
    *,
    owner_id: str,
) -> tuple[str, str, str, str, str, str]:
    source_id, target_id, view_id = _create_relation_tables(app, owner_id=owner_id)
    with TestClient(app) as client:
        amount = client.post(
            f"/tables/{target_id}/field-initializations",
            headers={"X-Stage06-User-Id": owner_id, "Idempotency-Key": "f2-amount-1"},
            json={"name": "Amount", "field_type": "number", "required": False},
        )
        relation = client.post(
            f"/tables/{source_id}/relation-field-initializations",
            headers={"X-Stage06-User-Id": owner_id, "Idempotency-Key": "f2-customer-1"},
            json={"name": "Customer", "target_table_id": target_id, "required": False},
        )

    assert amount.status_code == 201
    assert relation.status_code == 201
    return (
        source_id,
        target_id,
        view_id,
        relation.json()["field"]["id"],
        amount.json()["field"]["id"],
        relation.json()["field"]["key"],
    )


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
