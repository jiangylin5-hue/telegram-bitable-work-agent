from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import json
import os
from threading import Barrier, Event, get_ident
import time
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.agent import AgentRun
from app.models.audit import OpsAuditEvent
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_platform import (
    BitableBase,
    PlatformField,
    PlatformRecord,
    PlatformTable,
    PlatformView,
    RecordLink,
    Workspace,
    WorkspaceMember,
)
from app.models.stage06_runtime import DigitalEmployee, RecordChangeDraft
from app.models.stage08_group_context import Stage08GroupBusinessContextBinding
from app.models.stage08_runtime import Stage08ExecutionTicket
from app.models.stage06_platform import Stage06TelegramBinding
from app.runtime.stage08_collaboration_contracts import (
    AnalysisDecision,
    AnalysisProviderOutcome,
    Stage08CollaborationContractFactory,
)
from app.runtime.stage08_tool_gateway import Stage08ToolGateway
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_collaboration import (
    Stage08CollaborationDependencies,
    _trace_hash,
    run_stage08_collaboration,
)
import app.services.stage08_collaboration as collaboration


STAGE08_RAG_DATABASE_URL_ENV = "STAGE08_RAG_DATABASE_URL"
NOW = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)

pytestmark = pytest.mark.postgres


def _database_url() -> str:
    database_url = os.getenv(STAGE08_RAG_DATABASE_URL_ENV)
    if not database_url:
        pytest.skip(
            "STAGE08_RAG_DATABASE_URL is required for Stage08 collaboration PostgreSQL evidence"
        )
    parsed = make_url(database_url)
    if parsed.host not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Stage08 collaboration PostgreSQL evidence must use loopback")
    return database_url


class _DraftProvider:
    def __init__(self, *, on_analyse=None) -> None:
        self.on_analyse = on_analyse

    def analyse(self, material, command, *, budget):
        del material, command, budget
        if self.on_analyse is not None:
            self.on_analyse()
        return AnalysisProviderOutcome(
            status="available",
            reason_code="none",
            decision=AnalysisDecision(
                answer="A controlled proposal is ready.",
                citation_ordinals=(),
                action="draft_update",
                draft_intent=Stage08CollaborationContractFactory.draft_intent(
                    field_key="title",
                    value="E3 controlled",
                ),
            ),
        )


class _GatewayFailure(Stage08ToolGateway):
    def execute_plan(self, uow, ticket, invocations, *, safe_context=None):
        del uow, ticket, invocations, safe_context
        raise RuntimeError("synthetic_gateway_failure")


def _build_fixture(session: Session):
    uow = SqlAlchemyStage06PlatformUnitOfWork(session)
    suffix = uuid4().hex[:8]
    actor = Actor(actor_type="user", actor_id=f"e3-owner-{suffix}", role="owner")
    workspace = create_workspace(
        uow,
        name=f"E3 PostgreSQL {suffix}",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    session.flush()
    member = uow.list_workspace_members(workspace.id)[0]
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    customers = create_table(
        uow, base.id, name="Customers", key=f"customers_{suffix}", actor=actor
    )
    projects = create_table(
        uow, base.id, name="Projects", key=f"projects_{suffix}", actor=actor
    )
    create_field(
        uow, customers.id, name="Name", key="name", field_type="text", actor=actor
    )
    create_field(
        uow, projects.id, name="Title", key="title", field_type="text", actor=actor
    )
    create_field(
        uow,
        projects.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customers.id)},
        actor=actor,
    )
    customer = create_record(
        uow, customers.id, values={"name": "E3 Acme"}, actor=actor
    )
    project = create_record(
        uow,
        projects.id,
        values={"title": "E3 launch", "customer": [str(customer.id)]},
        actor=actor,
    )
    view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Projects",
        view_type="grid",
        config={"fields": ["title", "customer"]},
        actor=actor,
    )
    view.version = 1
    employee = create_digital_employee(
        uow,
        base.id,
        name="E3 employee",
        description="controlled draft execution",
        telegram_alias=None,
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["query", "summarize", "draft_update"],
        actor=actor,
    )
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id=f"-100{suffix}",
        telegram_user_id=suffix,
        binding_type="chat_user",
        scope_policy={},
        status="active",
    )
    uow.add_telegram_binding(binding)
    mapping = Stage08GroupBusinessContextBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        telegram_binding_id=binding.id,
        customer_record_id=customer.id,
        project_record_id=project.id,
        mapping_version=1,
        status="active",
    )
    uow.add_group_business_context_binding(mapping)
    session.flush()
    return SimpleNamespace(
        uow=uow,
        actor=actor,
        workspace=workspace,
        employee=employee,
        project=project,
        mapping=mapping,
    )


def _command(case, *, idempotency_key: str):
    return Stage08CollaborationContractFactory.command(
        workspace_id=case.workspace.id,
        employee_id=case.employee.id,
        actor_user_id=case.actor.actor_id,
        intent="business_fact",
        query="create a controlled draft",
        requested_action="draft_update",
        target_record_id=case.project.id,
        idempotency_key=idempotency_key,
    )


def _counts(session: Session, *, workspace_id: UUID, traces: set[str]) -> dict[str, int]:
    return {
        "tickets": session.scalar(
            select(func.count()).select_from(Stage08ExecutionTicket).where(
                Stage08ExecutionTicket.workspace_id == workspace_id
            )
        ),
        "idempotency": session.scalar(
            select(func.count()).select_from(Stage06IdempotencyRecord).where(
                Stage06IdempotencyRecord.workspace_id == workspace_id,
                Stage06IdempotencyRecord.operation == "stage08.execution_plan",
            )
        ),
        "drafts": session.scalar(
            select(func.count()).select_from(RecordChangeDraft).where(
                RecordChangeDraft.workspace_id == workspace_id,
                RecordChangeDraft.trace_id.in_(traces),
            )
        ),
        "agent_runs": session.scalar(
            select(func.count()).select_from(AgentRun).where(
                AgentRun.trace_id.in_(traces)
            )
        ),
        "audits": session.scalar(
            select(func.count()).select_from(OpsAuditEvent).where(
                OpsAuditEvent.trace_id.in_(traces)
            )
        ),
    }


def _trace_projection_text(session: Session, traces: set[str]) -> str:
    audits = list(
        session.scalars(
            select(OpsAuditEvent).where(OpsAuditEvent.trace_id.in_(traces))
        )
    )
    runs = list(
        session.scalars(select(AgentRun).where(AgentRun.trace_id.in_(traces)))
    )
    tickets = list(
        session.scalars(
            select(Stage08ExecutionTicket).where(
                Stage08ExecutionTicket.trace_id.in_(traces)
            )
        )
    )
    return json.dumps(
        {
            "audits": [
                {
                    "actor_type": event.actor_type,
                    "actor_id": event.actor_id,
                    "entity_id": event.entity_id,
                    "before": event.before_state,
                    "after": event.after_state,
                    "permission": event.permission_snapshot,
                }
                for event in audits
            ],
            "runs": [
                {
                    "input": run.input_summary,
                    "output": run.output_summary,
                    "tools": run.tool_calls,
                    "refs": run.created_entity_refs,
                }
                for run in runs
            ],
            "tickets": [ticket.tool_summary for ticket in tickets],
        },
        default=str,
        sort_keys=True,
    )


def test_postgres_safe_draft_replay_gateway_rollback_scope_revoke_and_cleanup() -> None:
    engine = create_engine(_database_url(), future=True, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    workspace_id = None
    traces: set[str] = set()
    try:
        assert connection.scalar(
            text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
        ) == 1
        case = _build_fixture(session)
        workspace_id = case.workspace.id
        source_before = dict(case.project.values)

        success_command = _command(case, idempotency_key="e3-pg-success")
        success_trace = _trace_hash(success_command)
        traces.add(success_trace)
        dependencies = Stage08CollaborationDependencies(
            analysis_provider=_DraftProvider()
        )
        first = run_stage08_collaboration(
            case.uow, success_command, case.actor, dependencies, now=NOW
        )
        replay = run_stage08_collaboration(
            case.uow, success_command, case.actor, dependencies, now=NOW
        )
        session.flush()

        assert first == replay
        assert first.status == "draft_pending"
        draft = session.scalar(
            select(RecordChangeDraft).where(
                RecordChangeDraft.trace_id == success_trace
            )
        )
        assert draft is not None
        assert draft.id == first.draft_id
        assert draft.proposed_values == {"title": "E3 controlled"}
        assert case.project.values == source_before
        assert _counts(session, workspace_id=workspace_id, traces=traces)[
            "tickets"
        ] == 1

        failure_command = _command(case, idempotency_key="e3-pg-failure")
        failure_trace = _trace_hash(failure_command)
        traces.add(failure_trace)
        before_failure = _counts(
            session, workspace_id=workspace_id, traces=traces
        )
        failed = run_stage08_collaboration(
            case.uow,
            failure_command,
            case.actor,
            Stage08CollaborationDependencies(
                analysis_provider=_DraftProvider(),
                tool_gateway=_GatewayFailure(),
            ),
            now=NOW,
        )
        session.flush()
        after_failure = _counts(
            session, workspace_id=workspace_id, traces=traces
        )
        assert failed.status == "failed"
        assert after_failure["tickets"] == before_failure["tickets"]
        assert after_failure["idempotency"] == before_failure["idempotency"]
        assert after_failure["drafts"] == before_failure["drafts"]
        assert after_failure["agent_runs"] == before_failure["agent_runs"] + 1
        assert after_failure["audits"] == before_failure["audits"] + 1

        revoke_command = _command(case, idempotency_key="e3-pg-revoke")
        revoke_trace = _trace_hash(revoke_command)
        traces.add(revoke_trace)
        revoked = run_stage08_collaboration(
            case.uow,
            revoke_command,
            case.actor,
            Stage08CollaborationDependencies(
                analysis_provider=_DraftProvider(
                        on_analyse=lambda: setattr(case.mapping, "status", "inactive")
                )
            ),
            now=NOW,
        )
        session.flush()
        assert revoked.status == "denied"
        final_counts = _counts(
            session, workspace_id=workspace_id, traces=traces
        )
        assert final_counts == {
            "tickets": 1,
            "idempotency": 1,
            "drafts": 1,
            "agent_runs": 5,
            "audits": 9,
        }

        projection_text = _trace_projection_text(session, traces)
        forbidden = {
            "create a controlled draft",
            "A controlled proposal is ready.",
            "E3 controlled",
            "title",
            str(case.project.id),
            str(draft.id),
            case.actor.actor_id,
        }
        forbidden.update(
            str(ticket_id)
            for ticket_id in session.scalars(
                select(Stage08ExecutionTicket.id).where(
                    Stage08ExecutionTicket.workspace_id == workspace_id
                )
            )
        )
        assert all(value not in projection_text for value in forbidden)
    finally:
        if transaction.is_active:
            transaction.rollback()
        session.close()
        connection.close()

    try:
        assert workspace_id is not None
        with engine.connect() as observer:
            assert observer.scalar(
                select(func.count()).select_from(Workspace).where(
                    Workspace.id == workspace_id
                )
            ) == 0
            with Session(bind=observer, future=True) as observer_session:
                assert _counts(
                    observer_session,
                    workspace_id=workspace_id,
                    traces=traces,
                ) == {
                    "tickets": 0,
                    "idempotency": 0,
                    "drafts": 0,
                    "agent_runs": 0,
                    "audits": 0,
                }
    finally:
        engine.dispose()


def test_postgres_shared_execution_lock_blocks_second_session_and_cleans_up() -> None:
    engine = create_engine(_database_url(), future=True, pool_pre_ping=True)
    workspace_id = uuid4()
    with Session(engine, future=True) as setup:
        setup.add(
            Workspace(
                id=workspace_id,
                name="E3 lock evidence",
                slug=f"e3-lock-{uuid4().hex}",
                owner_user_id="e3-lock-owner",
                status="active",
                settings={},
            )
        )
        setup.commit()

    blocked_ready = Event()
    blocked_pid: list[int] = []

    def second_lock() -> bool:
        with Session(engine, future=True) as session:
            pid = session.scalar(select(func.pg_backend_pid()))
            assert isinstance(pid, int)
            blocked_pid.append(pid)
            blocked_ready.set()
            locked = SqlAlchemyStage06PlatformUnitOfWork(
                session
            ).lock_workspace_for_stage08_execution(workspace_id)
            session.rollback()
            return locked is not None

    try:
        with Session(engine, future=True) as first_session:
            first_uow = SqlAlchemyStage06PlatformUnitOfWork(first_session)
            assert first_uow.lock_workspace_for_stage08_execution(workspace_id) is not None
            blocking_pid = first_session.scalar(select(func.pg_backend_pid()))
            assert isinstance(blocking_pid, int)
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(second_lock)
                assert blocked_ready.wait(timeout=5)
                deadline = time.monotonic() + 5
                with engine.connect() as observer:
                    while time.monotonic() < deadline:
                        blockers = observer.scalar(
                            select(func.pg_blocking_pids(blocked_pid[0]))
                        )
                        if blocking_pid in set(blockers or ()):
                            break
                        time.sleep(0.05)
                    else:
                        pytest.fail("PostgreSQL did not report the shared lock blocker")
                assert future.done() is False
                first_session.rollback()
                assert future.result(timeout=10) is True
    finally:
        with Session(engine, future=True) as cleanup:
            cleaned = cleanup.execute(
                delete(Workspace).where(Workspace.id == workspace_id)
            ).rowcount
            cleanup.commit()
            assert cleaned == 1
        with engine.connect() as observer:
            assert observer.scalar(
                select(func.count()).select_from(Workspace).where(
                    Workspace.id == workspace_id
                )
            ) == 0
        engine.dispose()


def test_postgres_production_read_branches_overlap_with_distinct_isolated_sessions() -> None:
    engine = create_engine(_database_url(), future=True, pool_pre_ping=True)
    workspace_id = None
    actor_id = None
    trace_hash = None
    fixture_ids: dict[str, object] = {}
    try:
        with Session(engine, future=True, expire_on_commit=False) as setup:
            case = _build_fixture(setup)
            workspace_id = case.workspace.id
            actor_id = case.actor.actor_id
            command = Stage08CollaborationContractFactory.command(
                workspace_id=case.workspace.id,
                employee_id=case.employee.id,
                actor_user_id=case.actor.actor_id,
                intent="business_fact",
                query="analyse current controlled material",
                requested_action="read_only",
                target_record_id=None,
                idempotency_key="e5-pg-parallel-reads",
            )
            trace_hash = _trace_hash(command)
            project_table = case.uow.get_table(case.project.table_id)
            assert project_table is not None
            fixture_ids = {
                "member": case.uow.list_workspace_members(case.workspace.id)[0].id,
                "base": project_table.base_id,
                "tables": tuple(
                    table.id for table in case.uow.list_tables(project_table.base_id)
                ),
                "records": (case.project.id, case.mapping.customer_record_id),
                "view": case.employee.accessible_views[0],
                "employee": case.employee.id,
                "binding": case.mapping.telegram_binding_id,
                "mapping": case.mapping.id,
            }
            setup.commit()

        overlap = Barrier(2)
        session_identities: dict[str, int] = {}

        def branch_probe(branch: str, session_identity: int | None) -> None:
            if branch not in {"composite_context", "retrieval"}:
                return
            assert isinstance(session_identity, int)
            session_identities[branch] = session_identity
            overlap.wait(timeout=10)

        class ReadOnlyProvider:
            def analyse(self, material, command, *, budget):
                del material, command, budget
                return AnalysisProviderOutcome(
                    status="available",
                    reason_code="none",
                    decision=AnalysisDecision(
                        answer="Current controlled material was analysed.",
                        citation_ordinals=(),
                        action="read_only",
                    ),
                )

        with Session(engine, future=True, expire_on_commit=False) as request_session:
            coordinator_thread_id = get_ident()
            request_session_worker_touches: list[tuple[int, str]] = []

            class NoWorkerSessionAccess:
                def __init__(self, delegate: Session) -> None:
                    object.__setattr__(self, "_delegate", delegate)

                def __getattribute__(self, name: str):
                    if name == "_delegate":
                        return object.__getattribute__(self, name)
                    current_thread_id = get_ident()
                    if current_thread_id != coordinator_thread_id:
                        request_session_worker_touches.append(
                            (current_thread_id, name)
                        )
                        raise AssertionError("read_worker_touched_request_session")
                    return getattr(
                        object.__getattribute__(self, "_delegate"), name
                    )

            guarded_request_session = NoWorkerSessionAccess(request_session)
            view = run_stage08_collaboration(
                SqlAlchemyStage06PlatformUnitOfWork(guarded_request_session),
                command,
                case.actor,
                Stage08CollaborationDependencies(
                    analysis_provider=ReadOnlyProvider()
                ),
                now=NOW,
                runtime_control=collaboration._create_stage08_runtime_control(
                    branch_probe=branch_probe
                ),
            )
            request_session.commit()

        assert view.status == "completed"
        assert request_session_worker_touches == []
        assert set(session_identities) == {"composite_context", "retrieval"}
        assert len(set(session_identities.values())) == 2
    finally:
        if workspace_id is not None:
            with Session(engine, future=True) as cleanup:
                if trace_hash is not None:
                    cleanup.execute(
                        delete(AgentRun).where(AgentRun.trace_id == trace_hash)
                    )
                    cleanup.execute(
                        delete(OpsAuditEvent).where(
                            OpsAuditEvent.trace_id == trace_hash
                        )
                    )
                if actor_id is not None:
                    cleanup.execute(
                        delete(OpsAuditEvent).where(
                            OpsAuditEvent.actor_id == actor_id
                        )
                    )
                record_ids = fixture_ids.get("records", ())
                cleanup.execute(
                    delete(RecordLink).where(
                        (RecordLink.source_record_id.in_(record_ids))
                        | (RecordLink.target_record_id.in_(record_ids))
                    )
                )
                cleanup.execute(
                    delete(Stage08GroupBusinessContextBinding).where(
                        Stage08GroupBusinessContextBinding.id
                        == fixture_ids.get("mapping")
                    )
                )
                cleanup.execute(
                    delete(Stage06TelegramBinding).where(
                        Stage06TelegramBinding.id == fixture_ids.get("binding")
                    )
                )
                cleanup.execute(
                    delete(DigitalEmployee).where(
                        DigitalEmployee.id == fixture_ids.get("employee")
                    )
                )
                cleanup.execute(
                    delete(PlatformView).where(
                        PlatformView.id == UUID(str(fixture_ids.get("view")))
                    )
                )
                cleanup.execute(
                    delete(PlatformRecord).where(PlatformRecord.id.in_(record_ids))
                )
                table_ids = fixture_ids.get("tables", ())
                cleanup.execute(
                    delete(PlatformField).where(PlatformField.table_id.in_(table_ids))
                )
                cleanup.execute(
                    delete(PlatformTable).where(PlatformTable.id.in_(table_ids))
                )
                cleanup.execute(
                    delete(BitableBase).where(
                        BitableBase.id == fixture_ids.get("base")
                    )
                )
                cleanup.execute(
                    delete(WorkspaceMember).where(
                        WorkspaceMember.id == fixture_ids.get("member")
                    )
                )
                cleanup.execute(
                    delete(Workspace).where(Workspace.id == workspace_id)
                )
                cleanup.commit()
            with engine.connect() as observer:
                assert observer.scalar(
                    select(func.count()).select_from(Workspace).where(
                        Workspace.id == workspace_id
                    )
                ) == 0
        engine.dispose()
