from datetime import UTC, datetime, timedelta
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.stage06_platform import PlatformRecord
from app.services.agent_event_runtime import (
    SqlAlchemyAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.stage12_action_runtime import (
    SqlAlchemyStage12ActionRuntimeRepository,
    create_action_slot,
    create_objective_run,
)
from app.schemas.stage12_action_runtime import (
    ActionConfirmRequestV1,
    ActionPrivatePayloadV1,
    ActionSlotControlV1,
)
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_table,
    create_workspace,
)
from app.services.stage12_action_confirmation import confirm_stage12_action
from app.services.stage12_action_materialization import materialize_action_slot
from scripts.stage06_local_postgres_migration_smoke import classify_local_postgres_url


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
pytestmark = pytest.mark.postgres


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage12-F PostgreSQL evidence",
)
def test_postgres_persists_stage12_objective_and_action_across_sessions() -> None:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    run_id = None
    try:
        now = datetime.now(UTC)
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
            platform = SqlAlchemyStage06PlatformUnitOfWork(session)
            actor = Actor(
                actor_type="user", actor_id=f"stage12-pg-{uuid4()}", role="owner"
            )
            workspace = create_workspace(
                platform,
                name=f"Stage12-F PostgreSQL {uuid4().hex}",
                owner_user_id=actor.actor_id,
                actor=actor,
            )
            platform.flush()
            base = create_base(platform, workspace.id, name="Actions", actor=actor)
            platform.flush()
            employee = create_digital_employee(
                platform,
                base.id,
                name="Action Employee",
                description="PostgreSQL persistence evidence",
                telegram_alias=None,
                accessible_tables=[],
                accessible_views=[],
                allowed_actions=["draft_create"],
                actor=actor,
            )
            platform.flush()
            run = create_agent_run(
                runtime,
                workspace_id=workspace.id,
                root_employee_id=employee.id,
                target_record_id=None,
                scope_hash="a" * 64,
                idempotency_key_hash=uuid4().hex + uuid4().hex,
                deadline_at=now + timedelta(minutes=2),
                now=now,
                workflow_version="stage12.quality-v2.action.v1",
            ).run
            run_id = run.id
            repository = SqlAlchemyStage12ActionRuntimeRepository(session)
            objective = create_objective_run(
                repository,
                run_id=run.id,
                objective_key="obj-pg-01",
                kind="action",
                required=True,
                dependency_keys=(),
            )
            create_action_slot(
                repository,
                run_id=run.id,
                objective_run_id=objective.id,
                slot_key="act-pg-01",
                action_kind="task.create",
                control=ActionSlotControlV1(
                    action_kind="task.create",
                    confirmation_policy="required",
                    dependency_keys=(),
                    evidence_refs=(),
                    editable_fields=(),
                    safe_summary="PostgreSQL 持久化验收",
                ),
                private_payload_ref=f"agent-private-input:{uuid4()}",
                target_scope_hash="a" * 64,
                data_version_hash=None,
                idempotency_key_hash=uuid4().hex + uuid4().hex,
            )
            session.commit()

        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            repository = SqlAlchemyStage12ActionRuntimeRepository(session)
            assert [
                item.objective_key for item in repository.list_objectives(run_id)
            ] == ["obj-pg-01"]
            actions = repository.list_actions(run_id)
            assert len(actions) == 1
            assert actions[0].action_kind == "task.create"
            assert actions[0].status == "queued"
    finally:
        engine.dispose()


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage12-F PostgreSQL evidence",
)
def test_postgres_confirmation_executes_user_edited_values() -> None:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    try:
        now = datetime.now(UTC)
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
            platform = SqlAlchemyStage06PlatformUnitOfWork(session)
            repository = SqlAlchemyStage12ActionRuntimeRepository(session)
            actor = Actor(
                actor_type="user", actor_id=f"stage12-edit-{uuid4()}", role="owner"
            )
            workspace = create_workspace(
                platform,
                name=f"Stage12-F edited confirmation {uuid4().hex}",
                owner_user_id=actor.actor_id,
                actor=actor,
            )
            platform.flush()
            base = create_base(platform, workspace.id, name="Actions", actor=actor)
            platform.flush()
            table = create_table(
                platform, base.id, name="Tasks", key=f"tasks_{uuid4().hex}", actor=actor
            )
            platform.flush()
            title_field = create_field(
                platform,
                table.id,
                name="Title",
                key="title",
                field_type="text",
                actor=actor,
            )
            platform.flush()
            employee = create_digital_employee(
                platform,
                base.id,
                name="Action Employee",
                description="PostgreSQL edited confirmation evidence",
                telegram_alias=None,
                accessible_tables=[str(table.id)],
                accessible_views=[],
                allowed_actions=["draft_create"],
                actor=actor,
            )
            platform.flush()
            run = create_agent_run(
                runtime,
                workspace_id=workspace.id,
                root_employee_id=employee.id,
                target_record_id=None,
                scope_hash="d" * 64,
                idempotency_key_hash=uuid4().hex + uuid4().hex,
                deadline_at=now + timedelta(minutes=2),
                now=now,
                workflow_version="stage12.quality-v2.action.v1",
            ).run
            objective = create_objective_run(
                repository,
                run_id=run.id,
                objective_key="obj-edit-01",
                kind="task_creation",
                required=True,
                dependency_keys=(),
            )
            control = ActionSlotControlV1(
                action_kind="task.create",
                confirmation_policy="required",
                dependency_keys=(),
                evidence_refs=(),
                editable_fields=(
                    {
                        "field_id": title_field.id,
                        "field_key": "title",
                        "label": "Title",
                        "field_type": "text",
                        "required": True,
                    },
                ),
                safe_summary="Create a task after confirmation",
            )
            slot = create_action_slot(
                repository,
                run_id=run.id,
                objective_run_id=objective.id,
                slot_key="act-edit-01",
                action_kind="task.create",
                control=control,
                private_payload_ref=f"agent-private-input:{uuid4()}",
                target_scope_hash=run.scope_hash,
                data_version_hash=None,
                idempotency_key_hash=uuid4().hex + uuid4().hex,
            )
            payload = ActionPrivatePayloadV1(
                actor_user_id=actor.actor_id,
                objective_key=objective.objective_key,
                slot_key=slot.slot_key,
                action_kind="task.create",
                candidate_set_hash="e" * 64,
                target_table_id=table.id,
                target_record_ids=(),
                assignments=(
                    {
                        "record_id": None,
                        "field_id": title_field.id,
                        "value": "Original",
                    },
                ),
                record_versions=(),
                evidence_ids=(),
                expires_at=now + timedelta(minutes=2),
            )
            materialize_action_slot(
                repository,
                platform,
                slot_id=slot.id,
                expected_proposal_version=slot.proposal_version,
                workspace_id=workspace.id,
                employee_id=employee.id,
                actor=actor,
                private_payload=payload,
            )

            confirm_stage12_action(
                repository,
                runtime,
                platform,
                run_id=run.id,
                slot_id=slot.id,
                request=ActionConfirmRequestV1(
                    proposal_version=slot.proposal_version,
                    record_version=None,
                    proposed_values={"title": "Edited by user"},
                ),
                private_payload=payload,
                actor=actor,
            )
            session.commit()

        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            values = session.scalar(
                select(PlatformRecord.record_values).where(
                    PlatformRecord.table_id == table.id
                )
            )
            assert values == {"title": "Edited by user"}
    finally:
        engine.dispose()
