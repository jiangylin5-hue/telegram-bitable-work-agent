from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_platform import ViewMemberGrant
from app.schemas.stage06_platform import ViewInitializationRequest, ViewMemberCommand
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    initialize_v1_view,
    list_view_records,
    replace_v1_view_members,
)
from tests.integration.test_stage07_field_builder_postgres import Stage07Postgres, stage07_postgres


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("STAGE06_LOCAL_DATABASE_URL"),
        reason="STAGE06_LOCAL_DATABASE_URL is required for disposable V1 PostgreSQL tests",
    ),
]


def test_v1_migration_adds_durable_view_columns_and_unique_grants(
    stage07_postgres: Stage07Postgres,
) -> None:
    inspector = inspect(stage07_postgres.engine)
    assert {"owner_user_id", "scope", "version"} <= {
        column["name"] for column in inspector.get_columns("views")
    }
    assert "view_member_grants" in inspector.get_table_names()
    assert "uq_view_member_grants_view_user" in {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("view_member_grants")
    }


def test_v1_initialization_replays_one_private_view_and_one_idempotency_row(
    stage07_postgres: Stage07Postgres,
) -> None:
    owner = _actor("pg-replay-owner", "owner")
    table_id = _create_table(stage07_postgres, owner)
    request = _request("Mine")

    with stage07_postgres.session_factory() as session:
        first = initialize_v1_view(
            SqlAlchemyStage06PlatformUnitOfWork(session),
            table_id,
            request=request,
            idempotency_key="pg-v1-replay",
            actor=owner,
        )
        session.commit()

    with stage07_postgres.session_factory() as session:
        replay = initialize_v1_view(
            SqlAlchemyStage06PlatformUnitOfWork(session),
            table_id,
            request=request,
            idempotency_key="pg-v1-replay",
            actor=owner,
        )
        session.commit()
        assert replay.replayed is True
        assert replay.view.id == first.view.id
        assert replay.view.scope == "private"
        assert replay.view.owner_user_id == owner.actor_id
        assert session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord)) == 1


def test_v1_grant_database_constraint_rejects_duplicate_recipient_rows(
    stage07_postgres: Stage07Postgres,
) -> None:
    owner = _actor("pg-grant-owner", "owner")
    table_id = _create_table(stage07_postgres, owner, members=[("member-1", "viewer")])
    view_id = _create_private_view(stage07_postgres, table_id, owner, "pg-grant-private")

    with stage07_postgres.session_factory() as session:
        session.add_all(
            [
                ViewMemberGrant(
                    id=uuid4(),
                    view_id=view_id,
                    user_id="member-1",
                    access_level="viewer",
                    status="active",
                ),
                ViewMemberGrant(
                    id=uuid4(),
                    view_id=view_id,
                    user_id="member-1",
                    access_level="editor",
                    status="active",
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_v1_concurrent_member_replacement_allows_one_version_and_conflicts_the_other(
    stage07_postgres: Stage07Postgres,
) -> None:
    owner = _actor("pg-concurrent-owner", "owner")
    table_id = _create_table(
        stage07_postgres,
        owner,
        members=[("editor-1", "builder"), ("viewer-1", "viewer")],
    )
    view_id = _create_private_view(stage07_postgres, table_id, owner, "pg-concurrent-private")
    barrier = Barrier(2)

    def replace(user_id: str, access_level: str) -> str:
        with stage07_postgres.session_factory() as session:
            uow = SqlAlchemyStage06PlatformUnitOfWork(session)
            barrier.wait()
            try:
                replace_v1_view_members(
                    uow,
                    view_id,
                    expected_version=1,
                    members=[ViewMemberCommand(user_id=user_id, access_level=access_level)],
                    actor=owner,
                )
                session.commit()
                return "updated"
            except PlatformValidationError as exc:
                session.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda item: replace(*item),
                [("editor-1", "editor"), ("viewer-1", "viewer")],
            )
        )

    assert sorted(outcomes) == ["updated", "view_version_conflict"]
    with stage07_postgres.session_factory() as session:
        grants = list(session.scalars(select(ViewMemberGrant)))
        assert len(grants) == 1
        assert _load_view(session, view_id).version == 2


def test_v1_postgres_applies_filter_and_sort_before_cursor_pagination(
    stage07_postgres: Stage07Postgres,
) -> None:
    owner = _actor("pg-query-owner", "owner")
    table_id = _create_table(stage07_postgres, owner)
    with stage07_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        create_field(uow, table_id, name="Score", key="score", field_type="number", actor=owner)
        create_field(
            uow,
            table_id,
            name="State",
            key="state",
            field_type="status",
            options={"choices": ["active", "closed"]},
            actor=owner,
        )
        session.flush()
        records = [
            create_record(
                uow,
                table_id,
                values={"title": title, "score": score, "state": state},
                actor=owner,
            )
            for title, score, state in (
                ("bravo", 2, "closed"),
                ("alpha", 5, "active"),
                ("charlie", 3, "active"),
                ("delta", 4, "closed"),
            )
        ]
        session.flush()
        view = initialize_v1_view(
            uow,
            table_id,
            request=ViewInitializationRequest.model_validate(
                {
                    "name": "Ranked",
                    "view_type": "grid",
                    "presentation": {
                        "view_type": "grid",
                        "visible_field_keys": ["title", "score"],
                        "filters": [{"field_key": "score", "operator": "gte", "value": 3}],
                        "sort_rules": [{"field_key": "score", "direction": "desc"}],
                        "group_by_field_key": "state",
                    },
                }
            ),
            idempotency_key="pg-v1-query",
            actor=owner,
        ).view
        session.commit()

    with stage07_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        first = list_view_records(uow, view.id, actor=owner, limit=1)
        second = list_view_records(
            uow,
            view.id,
            actor=owner,
            limit=1,
            cursor=first["next_cursor"],
        )

    assert [row["fields"]["title"] for row in first["records"]] == ["alpha"]
    assert [row["fields"]["title"] for row in second["records"]] == ["charlie"]
    assert first["groups"] == [{"value": "active", "record_ids": [str(records[1].id)]}]
    assert second["groups"] == [{"value": "active", "record_ids": [str(records[2].id)]}]


def _create_table(
    stage07_postgres: Stage07Postgres,
    owner: Actor,
    *,
    members: list[tuple[str, str]] | None = None,
) -> UUID:
    from app.models.stage06_platform import WorkspaceMember

    with stage07_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(uow, name=f"V1 {owner.actor_id}", owner_user_id=owner.actor_id, actor=owner)
        session.flush()
        for user_id, role in members or []:
            uow.add_workspace_member(
                WorkspaceMember(
                    id=uuid4(),
                    workspace_id=workspace.id,
                    user_id=user_id,
                    role=role,
                    status="active",
                )
            )
        session.flush()
        base = create_base(uow, workspace.id, name="Operations", actor=owner)
        table = create_table(uow, base.id, name="Tasks", key=f"tasks_{uuid4().hex[:8]}", actor=owner)
        create_field(uow, table.id, name="Title", key="title", field_type="text", actor=owner)
        session.commit()
        return table.id


def _create_private_view(
    stage07_postgres: Stage07Postgres,
    table_id: UUID,
    owner: Actor,
    key: str,
) -> UUID:
    with stage07_postgres.session_factory() as session:
        result = initialize_v1_view(
            SqlAlchemyStage06PlatformUnitOfWork(session),
            table_id,
            request=_request("Mine"),
            idempotency_key=key,
            actor=owner,
        )
        session.commit()
        return result.view.id


def _load_view(session, view_id: UUID):
    from app.models.stage06_platform import PlatformView

    view = session.get(PlatformView, view_id)
    assert view is not None
    return view


def _request(name: str) -> ViewInitializationRequest:
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


def _actor(user_id: str, role: str) -> Actor:
    return Actor(actor_type="user", actor_id=user_id, role=role)
