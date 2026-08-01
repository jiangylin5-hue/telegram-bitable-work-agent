from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.base import Base
from app.models.agent_event_runtime import AgentArtifact, AgentOutboxEvent
from app.models.audit import OpsAuditEvent
from app.schemas.agent_stage12_runtime import Stage12RuntimeAdmissionRequest
from app.services.agent_event_runtime import SqlAlchemyAgentEventRuntimeUnitOfWork
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
from app.services.agent_orchestrator import build_authorization_hash
from app.services.agent_stage12_runtime_admission import admit_stage12_runtime_run
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
)
from app.services.stage12_action_runtime import SqlAlchemyStage12ActionRuntimeRepository
from scripts.stage06_local_postgres_migration_smoke import classify_local_postgres_url
from scripts.stage12_evaluation_fixture import materialize_stage12_evaluation_fixture


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
pytestmark = pytest.mark.postgres


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage12 SQL admission evidence",
)
def test_sql_admission_persists_authorized_zero_dependency_dispatch_atomically() -> (
    None
):
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    schema_name = f"stage12_admission_{uuid4().hex}"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            connection.execute(
                text(f'SET LOCAL search_path TO "{schema_name}", public')
            )
            Base.metadata.create_all(connection)
            session = Session(
                connection,
                autoflush=True,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            platform = SqlAlchemyStage06PlatformUnitOfWork(session)
            runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
            objectives = SqlAlchemyStage12ActionRuntimeRepository(session)
            actor = Actor(
                actor_type="user",
                actor_id="stage12-eval-owner",
                role="owner",
            )
            fixture = materialize_stage12_evaluation_fixture(platform, actor)
            employee = create_digital_employee(
                platform,
                fixture.base_id,
                name="Stage12 Evaluator",
                description="Read-only deployed runtime evaluator",
                telegram_alias=None,
                accessible_tables=[
                    str(value) for value in fixture.table_ids.values()
                ],
                accessible_views=[],
                allowed_actions=["schema_inspect", "query", "summarize"],
                actor=actor,
            )
            readable = tuple(
                field.id
                for table_id in fixture.table_ids.values()
                for field in platform.list_fields(table_id)
                if field.key not in {"customer_secret", "internal_note"}
            )
            employee.field_policy = build_stage12_field_policy_v2(
                readable_field_ids=readable,
                writable_field_ids=(),
            )
            session.flush()
            record_count_before = sum(
                len(platform.list_records(table_id))
                for table_id in fixture.table_ids.values()
            )
            now = datetime(2026, 8, 1, 9, tzinfo=UTC)
            scope = build_authorization_hash(
                workspace_id=fixture.core.workspace_id,
                employee_id=employee.id,
                target_record_id=None,
                actor_user_id=actor.actor_id,
            )
            request = Stage12RuntimeAdmissionRequest(
                run_id=uuid4(),
                actor_user_id=actor.actor_id,
                workspace_id=fixture.core.workspace_id,
                digital_employee_id=employee.id,
                intent="business_fact",
                query="列出状态为 blocked 的工作项",
                target_record_id=None,
                idempotency_key="stage12-sql-admission-1",
                skill_id="platform-tabular-analysis",
                authorization_hash=scope,
                deadline_at=now + timedelta(seconds=90),
            )
            key = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")
            settings = Settings(
                agent_runtime_input_key=key,
                agent_runtime_input_key_version="stage12-test-v1",
                agent_runtime_input_ttl_seconds=90,
            )

            first = admit_stage12_runtime_run(
                platform,
                runtime,
                objectives,
                request=request,
                settings=settings,
                actor=actor,
                now=now,
            )
            replay = admit_stage12_runtime_run(
                platform,
                runtime,
                objectives,
                request=request,
                settings=settings,
                actor=actor,
                now=now,
            )
            with pytest.raises(PlatformValidationError) as conflict:
                admit_stage12_runtime_run(
                    platform,
                    runtime,
                    objectives,
                    request=request.model_copy(
                        update={"query": "列出全部工作项"}
                    ),
                    settings=settings,
                    actor=actor,
                    now=now,
                )
            assert conflict.value.code == "idempotency_conflict"
            session.flush()

            run = runtime.get_run(first.run_id)
            assert run is not None
            assert first.status == "queued"
            assert replay.replayed is True
            assert replay.run_id == first.run_id
            assert run.workflow_version == "stage12.quality-v2.runtime.v1"
            commands = runtime.list_commands(run.id)
            assert len(commands) == 1
            assert commands[0].target_capability == "platform.tabular.analyse"
            assert commands[0].payload_ref.startswith("agent-private-input:")
            private_ref = commands[0].payload_ref.removeprefix("agent-private-input:")
            private_input_id = UUID(private_ref)
            private_input = runtime.get_private_input(private_input_id)
            assert private_input is not None
            assert request.query.encode("utf-8") not in private_input.ciphertext
            artifact_kinds = {
                item.kind
                for item in session.scalars(
                    select(AgentArtifact).where(AgentArtifact.run_id == run.id)
                )
            }
            assert artifact_kinds >= {
                "authorized_schema_snapshot",
                "task_spec_v2",
                "structured_query_artifact",
                "objective_specialist_input",
            }
            assert len(objectives.list_objectives(run.id)) >= 1
            outbox = tuple(
                session.scalars(
                    select(AgentOutboxEvent).where(
                        AgentOutboxEvent.aggregate_id == run.id
                    )
                )
            )
            assert len(outbox) >= 2
            audits = tuple(
                session.scalars(
                    select(OpsAuditEvent).where(
                        OpsAuditEvent.event_type
                        == "stage12.isolated_runtime_admitted"
                    )
                )
            )
            assert len(audits) == 1
            retained_text = repr(
                [
                    *(item.payload_json for item in outbox),
                    *(item.after_state for item in audits),
                ]
            )
            assert request.query not in retained_text
            assert sum(
                len(platform.list_records(table_id))
                for table_id in fixture.table_ids.values()
            ) == record_count_before
            transaction.rollback()
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        engine.dispose()
