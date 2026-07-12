from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, text

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
