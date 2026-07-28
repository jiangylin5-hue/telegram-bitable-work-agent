from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.agent_event_runtime import (
    AgentArtifact,
    AgentCommand,
    AgentEvent,
    AgentOutboxEvent,
    AgentRunCheckpoint,
    AgentWorkflowRun,
)
from app.services.agent_event_runtime import (
    SqlAlchemyAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_orchestrator import (
    SpecialistSafeResult,
    dispatch_specialist_command,
    execute_read_only_specialist,
)
from app.models.stage06_platform import BitableBase, PlatformRecord, PlatformTable, Workspace
from app.models.stage06_runtime import DigitalEmployee
from scripts.stage06_local_postgres_migration_smoke import classify_local_postgres_url


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
BACKEND_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage10 PostgreSQL evidence",
)
def test_postgres_commits_one_recoverable_run_command_checkpoint_event_and_outbox() -> None:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    bootstrap_engine = create_engine(database_url, future=True, pool_pre_ping=True)
    try:
        with bootstrap_engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        bootstrap_engine.dispose()
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workspace.__table__,
            BitableBase.__table__,
            PlatformTable.__table__,
            PlatformRecord.__table__,
            DigitalEmployee.__table__,
        ],
    )
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    with patch.dict(os.environ, {"DATABASE_URL": database_url}):
        command.stamp(config, "20260723_0033")
        command.upgrade(config, "head")
    now = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    try:
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
            suffix = uuid4().hex[:10]
            workspace = Workspace(
                id=uuid4(),
                name=f"Stage10 {suffix}",
                slug=f"stage10-{suffix}",
                owner_user_id=f"stage10-{suffix}",
                status="active",
                settings={},
            )
            session.add(workspace)
            session.flush()
            base = BitableBase(
                id=uuid4(),
                workspace_id=workspace.id,
                name="CRM",
                description=None,
                source_type="native",
                template_id=None,
                status="active",
                settings={},
            )
            session.add(base)
            session.flush()
            table = PlatformTable(
                id=uuid4(),
                base_id=base.id,
                name="Customers",
                key=f"customers_{suffix}",
                description=None,
                primary_field_id=None,
                status="active",
                settings={},
            )
            session.add(table)
            session.flush()
            employee = DigitalEmployee(
                id=uuid4(),
                workspace_id=workspace.id,
                base_id=base.id,
                name="Stage10 analyst",
                description="read-only runtime evidence",
                telegram_alias=None,
                accessible_tables=[str(table.id)],
                accessible_views=[],
                field_policy={},
                allowed_actions=["query", "summarize"],
                confirmation_policy={},
                response_style={},
                status="active",
                version=1,
                access_mode="workspace",
            )
            session.add(employee)
            session.flush()

            run = create_agent_run(
                runtime,
                workspace_id=workspace.id,
                root_employee_id=employee.id,
                scope_hash="a" * 64,
                idempotency_key_hash="b" * 64,
                deadline_at=now + timedelta(minutes=2),
                now=now,
            ).run
            command_row = dispatch_specialist_command(
                runtime,
                run_id=run.id,
                target_capability="platform.tabular.analyse",
                payload_ref="stage08-idempotency:" + str(uuid4()),
                authorization_hash="a" * 64,
                now=now,
            )
            first = execute_read_only_specialist(
                runtime,
                command_id=command_row.id,
                authorization_hash="a" * 64,
                worker_id="postgres-worker",
                now=now + timedelta(seconds=1),
                execute=lambda: SpecialistSafeResult(
                    storage_ref="stage08-idempotency:" + str(uuid4()),
                    content_hash="c" * 64,
                    safe_summary="真实 PostgreSQL 只读运行完成",
                    metrics={"records_read": 1},
                ),
            )
            session.flush()
            replay = execute_read_only_specialist(
                runtime,
                command_id=command_row.id,
                authorization_hash="a" * 64,
                worker_id="postgres-recovery-worker",
                now=now + timedelta(seconds=2),
                execute=lambda: pytest.fail("completed command must not execute twice"),
            )

            assert first.run.status == "completed"
            assert replay.replayed is True
            assert session.scalar(select(func.count()).select_from(AgentWorkflowRun).where(AgentWorkflowRun.id == run.id)) == 1
            assert session.scalar(select(func.count()).select_from(AgentCommand).where(AgentCommand.run_id == run.id)) == 1
            assert session.scalar(select(func.count()).select_from(AgentArtifact).where(AgentArtifact.run_id == run.id)) == 1
            assert session.scalar(select(func.count()).select_from(AgentRunCheckpoint).where(AgentRunCheckpoint.run_id == run.id)) == 5
            assert session.scalar(select(func.count()).select_from(AgentEvent).where(AgentEvent.run_id == run.id)) == 5
            assert session.scalar(select(func.count()).select_from(AgentOutboxEvent).where(AgentOutboxEvent.aggregate_id == run.id)) == 6
            session.rollback()
    finally:
        engine.dispose()
