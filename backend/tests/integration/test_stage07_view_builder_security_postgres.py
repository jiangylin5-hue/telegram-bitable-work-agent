from __future__ import annotations

import json
import os
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.api.routes import stage06_platform as platform_routes
from app.models.audit import OpsAuditEvent
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_platform import PlatformView, ViewMemberGrant
from app.schemas.stage06_platform import ViewInitializationRequest, ViewMemberCommand
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    create_field,
    create_form_view,
    create_record,
    initialize_v1_view,
    replace_v1_view_members,
)
from tests.integration.test_stage07_field_builder_postgres import (
    Stage07Postgres,
    _postgres_app,
    stage07_postgres,
)
from tests.integration.test_stage07_view_builder_postgres import _actor, _create_table


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("STAGE06_LOCAL_DATABASE_URL"),
        reason="STAGE06_LOCAL_DATABASE_URL is required for disposable V1 PostgreSQL security tests",
    ),
]


def test_v1_postgres_context_projects_only_safe_field_identifier_and_select_values(
    stage07_postgres: Stage07Postgres,
) -> None:
    owner = _actor("pg-safe-field-owner", "owner")
    table_id = _create_table(stage07_postgres, owner)
    with stage07_postgres.session_factory() as session:
        state = create_field(
            SqlAlchemyStage06PlatformUnitOfWork(session),
            table_id,
            name="State",
            key="state",
            field_type="status",
            options={"choices": ["open", "closed"]},
            actor=owner,
        )
        session.commit()

    app = _postgres_app(stage07_postgres)
    with TestClient(app) as client:
        response = client.get(
            f"/tables/{table_id}/view-builder-context",
            headers={"X-Stage06-User-Id": owner.actor_id},
        )

    assert response.status_code == 200
    fields = {item["key"]: item for item in response.json()["fields"]}
    assert fields["state"]["field_id"] == str(state.id)
    assert fields["state"]["filter_values"] == ["open", "closed"]
    assert fields["title"]["filter_values"] == []
    assert {"options", "permission_policy", "target_table_id"}.isdisjoint(fields["state"])


def test_v1_postgres_preserves_one_default_grid_and_private_rows_are_not_defaults(
    stage07_postgres: Stage07Postgres,
) -> None:
    owner = _actor("pg-default-owner", "owner")
    table_id = _create_table(stage07_postgres, owner)

    with stage07_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        table = uow.get_table(table_id)
        assert table is not None
        default_view = create_form_view(
            uow,
            table.base_id,
            table.id,
            name="System grid",
            view_type="grid",
            config={"fields": ["title"]},
            is_default=True,
            actor=owner,
        )
        private_view = initialize_v1_view(
            uow,
            table.id,
            request=_grid_request("Private grid"),
            idempotency_key="pg-default-private",
            actor=owner,
        ).view
        session.flush()
        assert default_view.is_default is True
        assert default_view.scope == "system_default"
        assert private_view.is_default is False
        assert private_view.scope == "private"
        duplicate_default = PlatformView(
            base_id=table.base_id,
            table_id=table.id,
            name="Duplicate default",
            view_type="grid",
            config={"fields": ["title"]},
            permission_policy={},
            is_default=True,
            status="active",
            scope="system_default",
            version=1,
        )
        session.add(duplicate_default)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_v1_postgres_route_failure_rolls_back_view_audit_and_idempotency(
    stage07_postgres: Stage07Postgres,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _actor("pg-rollback-owner", "owner")
    table_id = _create_table(stage07_postgres, owner)
    app = _postgres_app(stage07_postgres)

    def fail_safe_projection(*_args, **_kwargs):
        raise PlatformValidationError("injected_v1_failure", "injected")

    monkeypatch.setattr(platform_routes, "build_v1_safe_view_summary", fail_safe_projection)
    with TestClient(app) as client:
        response = client.post(
            f"/tables/{table_id}/view-initializations",
            headers={
                "X-Stage06-User-Id": owner.actor_id,
                "Idempotency-Key": "pg-v1-rollback",
            },
            json=_grid_request("Rollback grid").model_dump(),
        )

    assert response.status_code == 422
    with stage07_postgres.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PlatformView)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(OpsAuditEvent)
                .where(OpsAuditEvent.event_type == "stage07.view_initialized")
            )
            == 0
        )
        assert session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord)) == 0


def test_v1_postgres_viewer_cannot_learn_hidden_field_from_safe_reads(
    stage07_postgres: Stage07Postgres,
) -> None:
    owner = _actor("pg-hidden-owner", "owner")
    viewer = _actor("pg-hidden-viewer", "viewer")
    table_id = _create_table(
        stage07_postgres,
        owner,
        members=[(viewer.actor_id, viewer.role)],
    )
    with stage07_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        create_field(
            uow,
            table_id,
            name="Restricted state",
            key="restricted_state",
            field_type="status",
            options={"choices": ["active", "closed"]},
            permission_policy={"viewer": "hidden"},
            actor=owner,
        )
        session.flush()
        create_record(
            uow,
            table_id,
            values={"title": "Safe row", "restricted_state": "active"},
            actor=owner,
        )
        view = initialize_v1_view(
            uow,
            table_id,
            request=ViewInitializationRequest.model_validate(
                {
                    "name": "Hidden-safe",
                    "view_type": "grid",
                    "presentation": {
                        "view_type": "grid",
                        "visible_field_keys": ["title", "restricted_state"],
                        "filters": [
                            {
                                "field_key": "restricted_state",
                                "operator": "is",
                                "value": "active",
                            }
                        ],
                        "sort_rules": [
                            {"field_key": "restricted_state", "direction": "asc"}
                        ],
                        "group_by_field_key": "restricted_state",
                    },
                }
            ),
            idempotency_key="pg-hidden-safe",
            actor=owner,
        ).view
        session.flush()
        replace_v1_view_members(
            uow,
            view.id,
            expected_version=1,
            members=[ViewMemberCommand(user_id=viewer.actor_id, access_level="viewer")],
            actor=owner,
        )
        session.commit()

    app = _postgres_app(stage07_postgres)
    with TestClient(app) as client:
        headers = {"X-Stage06-User-Id": viewer.actor_id}
        records = client.get(f"/views/{view.id}/records", headers=headers)
        presentation = client.get(f"/views/{view.id}/presentation", headers=headers)
        builder = client.get(f"/views/{view.id}/builder", headers=headers)
        context = client.get(f"/tables/{table_id}/view-builder-context", headers=headers)

    assert records.status_code == 200
    assert presentation.status_code == 200
    assert builder.status_code == 403
    assert context.status_code == 403
    assert "restricted_state" not in json.dumps(records.json())
    assert "restricted_state" not in json.dumps(presentation.json())
    assert "restricted_state" not in json.dumps(builder.json())
    assert "restricted_state" not in json.dumps(context.json())


def test_v1_optional_access_indexes_remain_deferred_after_explain(
    stage07_postgres: Stage07Postgres,
) -> None:
    owner = _actor("pg-explain-owner", "owner")
    viewer = _actor("pg-explain-viewer", "viewer")
    table_id = _create_table(
        stage07_postgres,
        owner,
        members=[(viewer.actor_id, viewer.role)],
    )
    with stage07_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        table = uow.get_table(table_id)
        assert table is not None
        views = [
            PlatformView(
                base_id=table.base_id,
                table_id=table.id,
                name=f"Explain {index}",
                view_type="grid",
                config={"schema": "stage07_v1", "fields": ["title"]},
                permission_policy={},
                is_default=False,
                status="active",
                owner_user_id=owner.actor_id if index % 2 == 0 else "other-owner",
                scope="private" if index % 2 == 0 else "restricted",
                version=1,
            )
            for index in range(128)
        ]
        session.add_all(views)
        session.flush()
        session.add_all(
            ViewMemberGrant(
                view_id=view.id,
                user_id=viewer.actor_id,
                access_level="viewer",
                status="active",
            )
            for index, view in enumerate(views)
            if index % 4 == 1
        )
        session.commit()

    with stage07_postgres.engine.connect() as connection:
        server_version = connection.scalar(text("SHOW server_version"))
        plan_lines = connection.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT DISTINCT views.id
                FROM views
                LEFT JOIN view_member_grants
                  ON view_member_grants.view_id = views.id
                 AND view_member_grants.user_id = :user_id
                 AND view_member_grants.status = 'active'
                WHERE views.table_id = :table_id
                  AND views.status = 'active'
                  AND (
                    views.scope = 'system_default'
                    OR views.owner_user_id = :user_id
                    OR (
                      views.scope = 'restricted'
                      AND view_member_grants.id IS NOT NULL
                    )
                  )
                """
            ),
            {"table_id": table_id, "user_id": viewer.actor_id},
        ).scalars().all()
    indexes = {
        index["name"]
        for index in inspect(stage07_postgres.engine).get_indexes("views")
    }
    grant_indexes = {
        index["name"]
        for index in inspect(stage07_postgres.engine).get_indexes("view_member_grants")
    }
    safe_plan_lines = [
        line.strip()
        for line in plan_lines
        if any(
            marker in line
            for marker in ("Scan", "Join", "Planning Time", "Execution Time")
        )
    ]
    print("V1_POSTGRES_VERSION=" + str(server_version))
    print("V1_EXPLAIN_SUMMARY=" + " | ".join(safe_plan_lines))

    assert safe_plan_lines
    assert "ix_views_table_scope_status" not in indexes
    assert "ix_view_member_grants_user_status" not in grant_indexes


def _grid_request(name: str) -> ViewInitializationRequest:
    return ViewInitializationRequest.model_validate(
        {
            "name": name,
            "view_type": "grid",
            "presentation": {
                "view_type": "grid",
                "visible_field_keys": ["title"],
                "filters": [],
                "sort_rules": [],
                "group_by_field_key": None,
            },
        }
    )
