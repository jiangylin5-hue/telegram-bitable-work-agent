from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.schemas.authorized_query_plan import (
    AuthorizedQueryPlanV1,
    QueryPredicateLeaf,
    QueryTraversalSpec,
)
from app.schemas.stage06_platform import GridViewPresentationCommand
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.authorized_query_records import AuthorizedQueryDenied
from app.services.authorized_table_query import execute_authorized_query
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    canonicalize_v1_presentation,
    create_base,
    create_form_view,
    create_table,
    create_workspace,
    update_record,
)
from scripts.stage06_local_postgres_migration_smoke import classify_local_postgres_url
from scripts.stage12_evaluation_fixture import materialize_stage12_evaluation_fixture


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
BACKEND_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=(
        "STAGE06_LOCAL_DATABASE_URL is required for Stage12-C authorized "
        "PostgreSQL evidence"
    ),
)
def test_postgres_authorized_query_exactness_replay_scope_and_versions() -> None:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    connection = None
    transaction = None
    try:
        with engine.connect() as connection:
            vector_installed = bool(
                connection.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_extension "
                        "WHERE extname = 'vector')"
                    )
                )
            )
        # The test never installs extensions. When an administrator has already
        # enabled pgvector, verify against head; otherwise stop at the complete
        # Stage06/07 schema boundary required by this read-only query engine.
        migration_target = "head" if vector_installed else "20260720_0031"
        with patch.dict(os.environ, {"DATABASE_URL": database_url}):
            command.upgrade(_alembic_config(database_url), migration_target)

        connection = engine.connect()
        transaction = connection.begin()
        with Session(
            bind=connection,
            autoflush=True,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            uow = SqlAlchemyStage06PlatformUnitOfWork(session)
            actor = Actor(
                actor_type="user",
                actor_id="stage12-query-postgres-owner",
                role="owner",
            )
            fixture = materialize_stage12_evaluation_fixture(
                uow,
                actor,
                workspace_name=f"Stage12 Query PostgreSQL {uuid4().hex}",
            )
            fields = {
                (table_key, field.key): field
                for table_key, table_id in fixture.table_ids.items()
                for field in uow.list_fields(table_id)
            }
            project_view = create_form_view(
                uow,
                fixture.base_id,
                fixture.table_ids["projects"],
                name="Atlas only",
                view_type="grid",
                config={"fields": []},
                actor=actor,
            )
            project_view.scope = "system_default"
            project_view.version = 1
            project_view.config = canonicalize_v1_presentation(
                uow,
                fixture.table_ids["projects"],
                actor=actor,
                command=GridViewPresentationCommand(
                    view_type="grid",
                    visible_field_keys=["project_code", "phase"],
                    filters=[
                        {
                            "field_key": "project_code",
                            "operator": "equals",
                            "value": "PRJ-ATLAS",
                        }
                    ],
                    sort_rules=[],
                    group_by_field_key=None,
                ),
            )
            employee = create_digital_employee(
                uow,
                fixture.base_id,
                name="Stage12 PostgreSQL query employee",
                description="Isolated exactness evidence",
                telegram_alias=None,
                accessible_tables=[str(item) for item in fixture.table_ids.values()],
                accessible_views=[str(project_view.id)],
                allowed_actions=["query", "summarize"],
                actor=actor,
            )
            session.commit()

            snapshot = build_authorized_schema_snapshot(
                uow,
                workspace_id=fixture.core.workspace_id,
                employee_id=employee.id,
                actor=actor,
            )
            visible_keys = {
                field.key for table in snapshot.tables for field in table.fields
            }
            assert "customer_secret" not in visible_keys
            assert "internal_note" not in visible_keys
            atlas_id = fixture.core.project_record_ids["PRJ-ATLAS"]
            beacon_id = fixture.core.project_record_ids["PRJ-BEACON"]
            view_plan = AuthorizedQueryPlanV1(
                version="authorized-query-plan.v1",
                query_intent_id="postgres-view",
                root_table_id=fixture.table_ids["projects"],
                authorized_view_ids=(project_view.id,),
                entity_codes=(),
                predicate=QueryPredicateLeaf(
                    predicate_id="postgres-phase",
                    table_id=fixture.table_ids["projects"],
                    field_id=fields[("projects", "phase")].id,
                    operator="eq",
                    value="delivery",
                ),
                traversals=(),
                projection_field_ids=(fields[("projects", "project_code")].id,),
                group_by_field_ids=(),
                aggregates=(),
                sort_rules=(),
                limit=None,
                max_scan_rows=5000,
                max_relation_expansions=1000,
                scope_hash=snapshot.scope_hash,
                schema_hash=snapshot.schema_hash,
            )
            first = execute_authorized_query(
                uow,
                actor=actor,
                workspace_id=fixture.core.workspace_id,
                employee_id=employee.id,
                chat_view_ids=(project_view.id,),
                snapshot=snapshot,
                plan=view_plan,
            )
            second = execute_authorized_query(
                uow,
                actor=actor,
                workspace_id=fixture.core.workspace_id,
                employee_id=employee.id,
                chat_view_ids=(project_view.id,),
                snapshot=snapshot,
                plan=view_plan,
            )
            assert first.result.result_hash == second.result.result_hash
            assert [item.record_id for item in first.result.records] == [atlas_id]
            assert str(beacon_id) not in first.model_dump_json()

            catalog = build_authorized_relation_catalog(uow, snapshot)
            work_project_relation = next(
                item
                for item in catalog
                if item.link_field_id == fields[("work_items", "project_link")].id
            )
            reverse = QueryTraversalSpec(
                traversal_id="postgres-reverse-work",
                relation_id=work_project_relation.relation_id,
                link_source_table_id=work_project_relation.link_source_table_id,
                link_field_id=work_project_relation.link_field_id,
                link_target_table_id=work_project_relation.link_target_table_id,
                direction="reverse",
                max_expansion=1000,
            )
            join_plan = view_plan.model_copy(
                update={
                    "query_intent_id": "postgres-reverse-join",
                    "authorized_view_ids": (),
                    "entity_codes": ("PRJ-ATLAS",),
                    "predicate": QueryPredicateLeaf(
                        predicate_id="postgres-high",
                        table_id=fixture.table_ids["work_items"],
                        field_id=fields[("work_items", "priority")].id,
                        operator="eq",
                        value="high",
                    ),
                    "traversals": (reverse,),
                    "projection_field_ids": (fields[("work_items", "ticket_code")].id,),
                }
            )
            joined = execute_authorized_query(
                uow,
                actor=actor,
                workspace_id=fixture.core.workspace_id,
                employee_id=employee.id,
                chat_view_ids=None,
                snapshot=snapshot,
                plan=join_plan,
                allow_whole_table=True,
            )
            joined_codes = {
                value.value
                for record in joined.result.records
                for value in record.values
            }
            assert joined_codes == {"MT-001", "MT-002"}
            assert len(joined.result.relation_paths) == 2

            forward = reverse.model_copy(
                update={
                    "traversal_id": "postgres-forward-project",
                    "direction": "forward",
                }
            )
            forward_plan = view_plan.model_copy(
                update={
                    "query_intent_id": "postgres-forward-join",
                    "root_table_id": fixture.table_ids["work_items"],
                    "authorized_view_ids": (),
                    "predicate": QueryPredicateLeaf(
                        predicate_id="postgres-ticket",
                        table_id=fixture.table_ids["work_items"],
                        field_id=fields[("work_items", "ticket_code")].id,
                        operator="eq",
                        value="MT-001",
                    ),
                    "traversals": (forward,),
                    "projection_field_ids": (fields[("projects", "project_code")].id,),
                }
            )
            forward_result = execute_authorized_query(
                uow,
                actor=actor,
                workspace_id=fixture.core.workspace_id,
                employee_id=employee.id,
                chat_view_ids=None,
                snapshot=snapshot,
                plan=forward_plan,
                allow_whole_table=True,
            )
            assert {
                value.value
                for record in forward_result.result.records
                for value in record.values
            } == {"PRJ-ATLAS"}

            mt001_id = fixture.core.work_item_record_ids["MT-001"]
            before_version = next(
                item.record_version
                for item in joined.result.source_versions
                if item.record_id == mt001_id
            )
            stored = uow.get_record(mt001_id)
            update_record(
                uow,
                mt001_id,
                values={"summary": "committed Stage12-C version evidence"},
                expected_version=stored.version,
                actor=actor,
            )
            session.commit()
            replay = execute_authorized_query(
                uow,
                actor=actor,
                workspace_id=fixture.core.workspace_id,
                employee_id=employee.id,
                chat_view_ids=None,
                snapshot=snapshot,
                plan=join_plan,
                allow_whole_table=True,
            )
            after_version = next(
                item.record_version
                for item in replay.result.source_versions
                if item.record_id == mt001_id
            )
            assert after_version == before_version + 1
            assert replay.result.result_hash != joined.result.result_hash

            other_workspace = create_workspace(
                uow,
                name="Other workspace",
                owner_user_id=actor.actor_id,
                actor=actor,
            )
            other_base = create_base(uow, other_workspace.id, name="Other", actor=actor)
            other_table = create_table(
                uow, other_base.id, name="Other", key="other", actor=actor
            )
            malicious = view_plan.model_copy(
                update={
                    "query_intent_id": "postgres-cross-workspace",
                    "root_table_id": other_table.id,
                    "authorized_view_ids": (),
                    "predicate": None,
                    "projection_field_ids": (),
                }
            )
            with pytest.raises(
                AuthorizedQueryDenied,
                match="^authorized_query_table_not_authorized$",
            ):
                execute_authorized_query(
                    uow,
                    actor=actor,
                    workspace_id=fixture.core.workspace_id,
                    employee_id=employee.id,
                    chat_view_ids=None,
                    snapshot=snapshot,
                    plan=malicious,
                    allow_whole_table=True,
                )
    finally:
        if transaction is not None and transaction.is_active:
            transaction.rollback()
        if connection is not None:
            connection.close()
        engine.dispose()
