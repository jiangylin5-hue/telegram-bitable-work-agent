from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import func, inspect, select, text

from app.models.audit import OpsAuditEvent
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_runtime import DigitalEmployee
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_table,
    create_workspace,
)
from app.services.stage07_digital_employee_management import (
    ManagedEmployeeCreateCommand,
    ManagedEmployeeUpdateCommand,
    activate_managed_employee,
    create_managed_employee,
    pause_managed_employee,
    update_managed_employee,
)
from tests.integration.test_stage07_governance_postgres import (
    DATABASE_URL_ENV,
    Stage06Postgres,
    _alembic_config,
    stage06_postgres,
)


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv(DATABASE_URL_ENV),
        reason=f"{DATABASE_URL_ENV} is required for disposable management PostgreSQL tests",
    ),
]


def test_management_migration_creates_required_postgres_shape(
    stage06_postgres: Stage06Postgres,
) -> None:
    inspector = inspect(stage06_postgres.engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("digital_employees")
    }
    employee_checks = {
        constraint["sqltext"]
        for constraint in inspector.get_check_constraints("digital_employees")
    }
    grant_uniques = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            "digital_employee_member_grants"
        )
    }
    employee_indexes = {
        index["name"]
        for index in inspector.get_indexes("digital_employees")
    }

    assert {"version", "access_mode"}.issubset(columns)
    assert any("version > 0" in check for check in employee_checks)
    assert any(
        "access_mode" in check and "workspace" in check and "assigned" in check
        for check in employee_checks
    )
    assert "uq_stage07_digital_employee_member_grant" in grant_uniques
    assert "ix_stage07_digital_employee_management_base_updated" in employee_indexes


def test_management_migration_downgrades_and_replays(
    stage06_postgres: Stage06Postgres,
) -> None:
    config = _alembic_config(os.environ[DATABASE_URL_ENV])

    command.downgrade(config, "20260712_0025")
    before_replay = inspect(stage06_postgres.engine)
    assert "digital_employee_member_grants" not in before_replay.get_table_names()
    assert "version" not in {
        column["name"]
        for column in before_replay.get_columns("digital_employees")
    }

    command.upgrade(config, "head")
    after_replay = inspect(stage06_postgres.engine)
    assert "digital_employee_member_grants" in after_replay.get_table_names()
    assert {"version", "access_mode"}.issubset(
        {
            column["name"]
            for column in after_replay.get_columns("digital_employees")
        }
    )


def test_management_migration_preserves_legacy_active_employee_behavior(
    stage06_postgres: Stage06Postgres,
) -> None:
    config = _alembic_config(os.environ[DATABASE_URL_ENV])
    workspace_id = uuid4()
    base_id = uuid4()
    employee_id = uuid4()

    command.downgrade(config, "20260713_0026")
    with stage06_postgres.engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO workspaces (
                    id, name, slug, owner_user_id, status, settings
                ) VALUES (
                    :id, :name, :slug, :owner_user_id, :status,
                    CAST(:settings AS jsonb)
                )
                """
            ),
            {
                "id": workspace_id,
                "name": "Legacy migration workspace",
                "slug": f"legacy-{workspace_id.hex[:12]}",
                "owner_user_id": "legacy-owner",
                "status": "active",
                "settings": json.dumps({}),
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO bases (
                    id, workspace_id, name, description, source_type,
                    template_id, status, settings
                ) VALUES (
                    :id, :workspace_id, :name, :description, :source_type,
                    NULL, :status, CAST(:settings AS jsonb)
                )
                """
            ),
            {
                "id": base_id,
                "workspace_id": workspace_id,
                "name": "Legacy Base",
                "description": None,
                "source_type": "manual",
                "status": "active",
                "settings": json.dumps({}),
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO digital_employees (
                    id, workspace_id, base_id, name, description,
                    telegram_alias, accessible_tables, accessible_views,
                    field_policy, allowed_actions, confirmation_policy,
                    response_style, status
                ) VALUES (
                    :id, :workspace_id, :base_id, :name, :description,
                    :telegram_alias, CAST(:accessible_tables AS jsonb),
                    CAST(:accessible_views AS jsonb),
                    CAST(:field_policy AS jsonb),
                    CAST(:allowed_actions AS jsonb),
                    CAST(:confirmation_policy AS jsonb),
                    CAST(:response_style AS jsonb), :status
                )
                """
            ),
            {
                "id": employee_id,
                "workspace_id": workspace_id,
                "base_id": base_id,
                "name": "Legacy active employee",
                "description": "pre-TD010 row",
                "telegram_alias": "legacy-active",
                "accessible_tables": json.dumps([]),
                "accessible_views": json.dumps([]),
                "field_policy": json.dumps({}),
                "allowed_actions": json.dumps(["summarize"]),
                "confirmation_policy": json.dumps({}),
                "response_style": json.dumps({}),
                "status": "active",
            },
        )

    command.upgrade(config, "head")
    with stage06_postgres.engine.connect() as connection:
        legacy_employee = connection.execute(
            text(
                """
                SELECT status, version, access_mode
                FROM digital_employees
                WHERE id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).one()

    assert legacy_employee._mapping == {
        "status": "active",
        "version": 1,
        "access_mode": "workspace",
    }


def test_management_pause_locks_two_competing_lifecycle_commands(
    stage06_postgres: Stage06Postgres,
) -> None:
    employee_id = _create_active_employee(stage06_postgres)
    owner = Actor(actor_type="user", actor_id="lifecycle-owner", role="owner")
    barrier = Barrier(2)

    def pause(idempotency_key: str) -> str:
        with stage06_postgres.session_factory() as session:
            uow = SqlAlchemyStage06PlatformUnitOfWork(session)
            barrier.wait()
            try:
                pause_managed_employee(
                    uow,
                    employee_id,
                    actor=owner,
                    expected_version=3,
                    idempotency_key=idempotency_key,
                )
                session.commit()
                return "paused"
            except PlatformValidationError as exc:
                session.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(pause, ["pause-race-a", "pause-race-b"]))

    assert sorted(outcomes) == ["digital_employee_revision_conflict", "paused"]
    with stage06_postgres.session_factory() as session:
        employee = session.get(DigitalEmployee, employee_id)
        assert employee is not None
        assert (employee.status, employee.version) == ("paused", 4)
        assert session.scalar(
            select(func.count()).select_from(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "stage07.digital_employee_paused"
            )
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(Stage06IdempotencyRecord).where(
                Stage06IdempotencyRecord.operation == "stage07.digital_employee.pause"
            )
        ) == 1


def _create_active_employee(stage06_postgres: Stage06Postgres):
    owner = Actor(actor_type="user", actor_id="lifecycle-owner", role="owner")
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Lifecycle race {uuid4().hex[:8]}",
            owner_user_id=owner.actor_id,
            actor=owner,
        )
        session.flush()
        base = create_base(uow, workspace.id, name="Operations", actor=owner)
        table = create_table(uow, base.id, name="Tasks", key=f"tasks_{uuid4().hex[:8]}", actor=owner)
        create_field(uow, table.id, name="Title", key="title", field_type="text", actor=owner)
        view = create_form_view(
            uow,
            base.id,
            table.id,
            name="Current tasks",
            view_type="grid",
            config={"fields": ["title"]},
            actor=owner,
        )
        employee = create_managed_employee(
            uow,
            base.id,
            actor=owner,
            command=ManagedEmployeeCreateCommand(
                name="Lifecycle helper",
                description="Safe lifecycle contention fixture.",
                telegram_alias=None,
            ),
            idempotency_key="lifecycle-race-create",
        )
        session.flush()
        update_managed_employee(
            uow,
            employee.id,
            actor=owner,
            expected_version=1,
            command=ManagedEmployeeUpdateCommand(
                accessible_table_ids=[table.id],
                accessible_view_ids=[view.id],
                allowed_actions=["summarize"],
                access_mode="workspace",
            ),
        )
        activate_managed_employee(
            uow,
            employee.id,
            actor=owner,
            expected_version=2,
            idempotency_key="lifecycle-race-activate",
        )
        session.commit()
        return employee.id
