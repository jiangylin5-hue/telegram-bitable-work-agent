from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.models.agent import AgentRun
from app.models.stage06_platform import PlatformRecord, WorkspaceMember
from app.models.stage06_runtime import DigitalEmployee, RecordChangeDraft
from app.models.stage08_runtime import Stage08ExecutionTicket
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.runtime.stage08_contracts import (
    ExecutionBudget,
    ExecutionPlan,
    ExecutionTicketState,
    ToolInvocation,
)
from app.runtime.stage08_tool_gateway import Stage08ToolGateway, Stage08ToolGatewayError
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    confirm_record_change_draft,
    create_create_record_draft,
    create_digital_employee,
    reject_record_change_draft,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_runtime import begin_execution_plan
from tests.integration.test_stage07_governance_postgres import (
    DATABASE_URL_ENV,
    Stage06Postgres,
    stage06_postgres,
)


def _status_literals(check_sql: str) -> set[str]:
    return set(re.findall(r"'([^']+)'", check_sql))


def _ticket(
    *,
    workspace_id,
    employee_id,
    trace_id: str,
    status: str = "planned",
    budget=None,
    tool_summary=None,
):
    return Stage08ExecutionTicket(
        id=uuid4(),
        workspace_id=workspace_id,
        employee_id=employee_id,
        actor_id="stage08-test-actor",
        action="record.query",
        trace_id=trace_id,
        request_fingerprint="f" * 64,
        status=status,
        budget={"max_tool_calls": 1} if budget is None else budget,
        tool_summary=(
            [{"tool_name": "record.query", "status": "succeeded"}]
            if tool_summary is None
            else tool_summary
        ),
    )


def _employee(*, workspace_id, base_id) -> DigitalEmployee:
    return DigitalEmployee(
        id=uuid4(),
        workspace_id=workspace_id,
        base_id=base_id,
        name="Stage08 test employee",
        description="Minimal ticket persistence fixture.",
        telegram_alias=None,
        accessible_tables=[],
        accessible_views=[],
        field_policy={},
        allowed_actions=[],
        confirmation_policy={},
        response_style={},
        status="active",
        version=1,
        access_mode="workspace",
    )


def test_in_memory_execution_ticket_looks_up_by_id_and_workspace_trace() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace_id = uuid4()
    ticket = _ticket(
        workspace_id=workspace_id,
        employee_id=uuid4(),
        trace_id="memory-trace",
    )

    uow.add_execution_ticket(ticket)

    assert uow.get_execution_ticket(ticket.id) is ticket
    assert uow.get_execution_ticket_by_trace(workspace_id, "memory-trace") is ticket
    assert uow.get_execution_ticket_by_trace(uuid4(), "memory-trace") is None


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_execution_ticket_migration_has_required_postgres_shape(
    stage06_postgres: Stage06Postgres,
) -> None:
    inspector = inspect(stage06_postgres.engine)

    assert "stage08_execution_tickets" in inspector.get_table_names()
    assert {
        "id",
        "workspace_id",
        "employee_id",
        "actor_id",
        "action",
        "trace_id",
        "request_fingerprint",
        "status",
        "budget",
        "tool_summary",
        "created_at",
        "updated_at",
        "completed_at",
    }.issubset(
        {column["name"] for column in inspector.get_columns("stage08_execution_tickets")}
    )
    assert "uq_stage08_execution_ticket_workspace_trace" in {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("stage08_execution_tickets")
    }
    checks = {
        constraint["name"]: constraint["sqltext"]
        for constraint in inspector.get_check_constraints("stage08_execution_tickets")
    }
    assert {
        "ck_stage08_execution_ticket_status",
        "ck_stage08_execution_ticket_budget_object",
        "ck_stage08_execution_ticket_tool_summary_array",
    }.issubset(checks)
    assert _status_literals(checks["ck_stage08_execution_ticket_status"]) == {
        "planned",
        "executing",
        "succeeded",
        "failed",
        "denied",
        "cancelled",
        "timed_out",
        "expired",
    }
    assert "ix_stage08_execution_ticket_workspace_status_created" in {
        index["name"] for index in inspector.get_indexes("stage08_execution_tickets")
    }


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_sqlalchemy_execution_ticket_round_trips_and_enforces_ticket_constraints(
    stage06_postgres: Stage06Postgres,
) -> None:
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 runtime {uuid4().hex[:8]}",
            owner_user_id="stage08-owner",
        )
        session.flush()
        base = create_base(uow, workspace.id, name="Runtime")
        employee = _employee(workspace_id=workspace.id, base_id=base.id)
        uow.add_digital_employee(employee)
        ticket = _ticket(
            workspace_id=workspace.id,
            employee_id=employee.id,
            trace_id="postgres-trace",
        )
        uow.add_execution_ticket(ticket)
        session.commit()

        assert uow.get_execution_ticket(ticket.id) is not None
        by_trace = uow.get_execution_ticket_by_trace(workspace.id, "postgres-trace")
        assert by_trace is not None
        assert by_trace.budget == {"max_tool_calls": 1}
        assert by_trace.tool_summary == [
            {"tool_name": "record.query", "status": "succeeded"}
        ]

        uow.add_execution_ticket(
            _ticket(
                workspace_id=workspace.id,
                employee_id=employee.id,
                trace_id="postgres-trace",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        other_workspace = create_workspace(
            uow,
            name=f"Stage08 other {uuid4().hex[:8]}",
            owner_user_id="stage08-owner",
        )
        session.flush()
        other_base = create_base(uow, other_workspace.id, name="Runtime")
        other_employee = _employee(
            workspace_id=other_workspace.id,
            base_id=other_base.id,
        )
        uow.add_digital_employee(other_employee)
        uow.add_execution_ticket(
            _ticket(
                workspace_id=other_workspace.id,
                employee_id=other_employee.id,
                trace_id="postgres-trace",
            )
        )
        session.commit()

        for invalid_status in (
            "pending_confirmation",
            "confirmed",
            "rejected",
            "non_whitelist_status",
        ):
            uow.add_execution_ticket(
                _ticket(
                    workspace_id=other_workspace.id,
                    employee_id=other_employee.id,
                    trace_id=f"invalid-{invalid_status}",
                    status=invalid_status,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        for invalid_budget in ([], "not-an-object"):
            uow.add_execution_ticket(
                _ticket(
                    workspace_id=other_workspace.id,
                    employee_id=other_employee.id,
                    trace_id=f"invalid-budget-{uuid4().hex}",
                    budget=invalid_budget,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        for invalid_tool_summary in ({}, "not-an-array"):
            uow.add_execution_ticket(
                _ticket(
                    workspace_id=other_workspace.id,
                    employee_id=other_employee.id,
                    trace_id=f"invalid-tool-summary-{uuid4().hex}",
                    tool_summary=invalid_tool_summary,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_workspace_lock_serializes_conflicting_ticket_creates_without_in_progress_idempotency(
    stage06_postgres: Stage06Postgres,
) -> None:
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 lock {uuid4().hex[:8]}",
            owner_user_id="stage08-operator",
        )
        session.flush()
        base = create_base(uow, workspace.id, name="Runtime")
        employee = _employee(workspace_id=workspace.id, base_id=base.id)
        employee.allowed_actions = ["query"]
        uow.add_digital_employee(employee)
        session.commit()

    b_pid_ready = Event()
    b_pid_holder: list[int] = []

    def begin_in_session_b():
        plan = ExecutionPlan(
            ticket_id=str(uuid4()),
            workspace_id=str(workspace.id),
            employee_id=str(employee.id),
            actor="user:stage08-operator",
            action="record.query",
            trace_id="concurrent-trace",
            idempotency_key="concurrent-key-2",
            state=ExecutionTicketState.planned,
            budget=ExecutionBudget(
                max_tool_calls=1,
                max_wall_time_ms=1_000,
                max_graph_depth=1,
                max_retries=0,
                max_retrieval_chunks=0,
            ),
            invocations=[ToolInvocation(tool_name="record.query", input={"query": "second"})],
        )
        with stage06_postgres.session_factory() as session:
            try:
                b_pid = session.scalar(select(func.pg_backend_pid()))
                assert isinstance(b_pid, int)
                b_pid_holder.append(b_pid)
                b_pid_ready.set()
                ticket = begin_execution_plan(
                    SqlAlchemyStage06PlatformUnitOfWork(session),
                    plan,
                )
                session.commit()
                return "created", ticket.id
            except Exception as exc:
                session.rollback()
                return "error", getattr(exc, "code", type(exc).__name__)

    with stage06_postgres.session_factory() as session_a:
        uow_a = SqlAlchemyStage06PlatformUnitOfWork(session_a)
        assert uow_a.lock_workspace_for_stage08_execution(workspace.id) is not None
        a_pid = session_a.scalar(select(func.pg_backend_pid()))
        assert isinstance(a_pid, int)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(begin_in_session_b)
            try:
                assert b_pid_ready.wait(timeout=5)
                b_pid = b_pid_holder[0]
                _wait_until_backend_is_blocked(
                    stage06_postgres,
                    blocked_pid=b_pid,
                    blocking_pid=a_pid,
                )
                assert future.done() is False
                first_plan = ExecutionPlan(
                    ticket_id=str(uuid4()),
                    workspace_id=str(workspace.id),
                    employee_id=str(employee.id),
                    actor="user:stage08-operator",
                    action="record.query",
                    trace_id="concurrent-trace",
                    idempotency_key="concurrent-key-1",
                    state=ExecutionTicketState.planned,
                    budget=ExecutionBudget(
                        max_tool_calls=1,
                        max_wall_time_ms=1_000,
                        max_graph_depth=1,
                        max_retries=0,
                        max_retrieval_chunks=0,
                    ),
                    invocations=[
                        ToolInvocation(
                            tool_name="record.query",
                            input={"query": "first"},
                        )
                    ],
                )
                first_ticket = begin_execution_plan(uow_a, first_plan)
                session_a.commit()
                result_b = future.result(timeout=15)
            finally:
                if session_a.in_transaction():
                    session_a.rollback()

    assert first_ticket.status == "planned"
    assert result_b == ("error", "stage08_trace_conflict")
    with stage06_postgres.session_factory() as session:
        tickets = list(
            session.scalars(
                select(Stage08ExecutionTicket).where(
                    Stage08ExecutionTicket.workspace_id == workspace.id
                )
            )
        )
        idempotency_records = list(
            session.scalars(
                select(Stage06IdempotencyRecord).where(
                    Stage06IdempotencyRecord.workspace_id == workspace.id
                )
            )
        )

    assert len(tickets) == 1
    assert len(idempotency_records) == 1
    assert idempotency_records[0].status == "completed"


def _wait_until_backend_is_blocked(
    stage06_postgres: Stage06Postgres,
    *,
    blocked_pid: int,
    blocking_pid: int,
) -> None:
    deadline = time.monotonic() + 5
    with stage06_postgres.engine.connect() as observer:
        while time.monotonic() < deadline:
            blocking_pids = observer.scalar(select(func.pg_blocking_pids(blocked_pid)))
            if blocking_pid in set(blocking_pids or ()):
                return
            time.sleep(0.05)
    pytest.fail("Session B did not enter a PostgreSQL lock wait for Session A")


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_gateway_execution_ticket_lock_claims_once_with_postgres_wait_evidence(
    stage06_postgres: Stage06Postgres,
) -> None:
    fixture = _postgres_gateway_fixture(stage06_postgres)
    gateway = Stage08ToolGateway()
    blocked_pid_ready = Event()
    blocked_pids: list[int] = []

    def second_claim() -> tuple[str, str]:
        with stage06_postgres.session_factory() as session:
            try:
                blocked_pid = session.scalar(select(func.pg_backend_pid()))
                assert isinstance(blocked_pid, int)
                blocked_pids.append(blocked_pid)
                blocked_pid_ready.set()
                gateway.execute(
                    SqlAlchemyStage06PlatformUnitOfWork(session),
                    Stage08ExecutionTicket(id=fixture["ticket_id"]),
                    ToolInvocation(
                        tool_name="record.query",
                        input={"view_id": str(fixture["view_id"])},
                    ),
                )
                session.commit()
                return "unexpected", "succeeded"
            except Stage08ToolGatewayError as exc:
                session.rollback()
                return "denied", exc.code
            finally:
                if session.in_transaction():
                    session.rollback()

    with stage06_postgres.session_factory() as session_a:
        uow_a = SqlAlchemyStage06PlatformUnitOfWork(session_a)
        assert uow_a.lock_execution_ticket_for_transition(fixture["ticket_id"]) is not None
        blocking_pid = session_a.scalar(select(func.pg_backend_pid()))
        assert isinstance(blocking_pid, int)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(second_claim)
            try:
                assert blocked_pid_ready.wait(timeout=5)
                _wait_until_backend_is_blocked(
                    stage06_postgres,
                    blocked_pid=blocked_pids[0],
                    blocking_pid=blocking_pid,
                )
                result = gateway.execute(
                    uow_a,
                    Stage08ExecutionTicket(id=fixture["ticket_id"]),
                    ToolInvocation(
                        tool_name="record.query",
                        input={"view_id": str(fixture["view_id"])},
                    ),
                )
                assert result.status == "succeeded"
                session_a.commit()
                second_result = future.result(timeout=15)
            finally:
                if session_a.in_transaction():
                    session_a.rollback()

    assert second_result == ("denied", "ticket_not_planned")
    with stage06_postgres.session_factory() as session:
        ticket = session.get(Stage08ExecutionTicket, fixture["ticket_id"])
        assert ticket is not None and ticket.status == "succeeded"
        assert len(ticket.tool_summary) == 1
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 1


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_create_record_draft_double_confirm_creates_one_record_with_postgres_wait_evidence(
    stage06_postgres: Stage06Postgres,
) -> None:
    fixture = _postgres_create_draft_fixture(stage06_postgres)
    blocked_pid_ready = Event()
    blocked_pids: list[int] = []

    def second_confirm() -> tuple[str, str]:
        with stage06_postgres.session_factory() as session:
            try:
                blocked_pid = session.scalar(select(func.pg_backend_pid()))
                assert isinstance(blocked_pid, int)
                blocked_pids.append(blocked_pid)
                blocked_pid_ready.set()
                confirm_record_change_draft(
                    SqlAlchemyStage06PlatformUnitOfWork(session),
                    fixture["draft_id"],
                    actor=fixture["actor"],
                )
                session.commit()
                return "unexpected", "confirmed"
            except Exception as exc:
                session.rollback()
                return "denied", getattr(exc, "code", type(exc).__name__)

    with stage06_postgres.session_factory() as session_a:
        uow_a = SqlAlchemyStage06PlatformUnitOfWork(session_a)
        assert uow_a.lock_record_change_draft_for_transition(fixture["draft_id"]) is not None
        blocking_pid = session_a.scalar(select(func.pg_backend_pid()))
        assert isinstance(blocking_pid, int)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(second_confirm)
            try:
                assert blocked_pid_ready.wait(timeout=5)
                _wait_until_backend_is_blocked(stage06_postgres, blocked_pid=blocked_pids[0], blocking_pid=blocking_pid)
                confirm_record_change_draft(uow_a, fixture["draft_id"], actor=fixture["actor"])
                session_a.commit()
                second_result = future.result(timeout=15)
            finally:
                if session_a.in_transaction():
                    session_a.rollback()

    assert second_result == ("denied", "record_change_draft_invalid_state")
    _assert_create_draft_terminal_state(stage06_postgres, fixture["draft_id"], "confirmed", 1)


@pytest.mark.postgres
@pytest.mark.parametrize(("first_action", "expected_status", "record_count"), [
    ("reject", "rejected", 0),
    ("confirm", "confirmed", 1),
])
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_create_record_draft_confirm_reject_race_uses_locked_terminal_state(
    stage06_postgres: Stage06Postgres,
    first_action: str,
    expected_status: str,
    record_count: int,
) -> None:
    fixture = _postgres_create_draft_fixture(stage06_postgres)
    blocked_pid_ready = Event()
    blocked_pids: list[int] = []

    def second_action() -> tuple[str, str]:
        with stage06_postgres.session_factory() as session:
            try:
                blocked_pid = session.scalar(select(func.pg_backend_pid()))
                assert isinstance(blocked_pid, int)
                blocked_pids.append(blocked_pid)
                blocked_pid_ready.set()
                uow = SqlAlchemyStage06PlatformUnitOfWork(session)
                if first_action == "reject":
                    confirm_record_change_draft(uow, fixture["draft_id"], actor=fixture["actor"])
                else:
                    reject_record_change_draft(uow, fixture["draft_id"], actor=fixture["actor"])
                session.commit()
                return "unexpected", "terminal"
            except Exception as exc:
                session.rollback()
                return "denied", getattr(exc, "code", type(exc).__name__)

    with stage06_postgres.session_factory() as session_a:
        uow_a = SqlAlchemyStage06PlatformUnitOfWork(session_a)
        assert uow_a.lock_record_change_draft_for_transition(fixture["draft_id"]) is not None
        blocking_pid = session_a.scalar(select(func.pg_backend_pid()))
        assert isinstance(blocking_pid, int)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(second_action)
            try:
                assert blocked_pid_ready.wait(timeout=5)
                _wait_until_backend_is_blocked(stage06_postgres, blocked_pid=blocked_pids[0], blocking_pid=blocking_pid)
                if first_action == "reject":
                    reject_record_change_draft(uow_a, fixture["draft_id"], actor=fixture["actor"])
                else:
                    confirm_record_change_draft(uow_a, fixture["draft_id"], actor=fixture["actor"])
                session_a.commit()
                second_result = future.result(timeout=15)
            finally:
                if session_a.in_transaction():
                    session_a.rollback()

    assert second_result == ("denied", "record_change_draft_invalid_state")
    _assert_create_draft_terminal_state(stage06_postgres, fixture["draft_id"], expected_status, record_count)


def _postgres_gateway_fixture(stage06_postgres: Stage06Postgres) -> dict[str, object]:
    owner = Actor(actor_type="user", actor_id="gateway-owner", role="owner")
    operator = Actor(actor_type="user", actor_id="gateway-operator", role="operator")
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(uow, name=f"Gateway {uuid4().hex}", owner_user_id=owner.actor_id, actor=owner)
        session.flush()
        base = create_base(uow, workspace.id, name="Tasks", actor=owner)
        session.flush()
        table = create_table(uow, base.id, name="Tasks", key=f"tasks_{uuid4().hex[:8]}", actor=owner)
        session.flush()
        create_field(uow, table.id, name="Status", key="status", field_type="status", actor=owner)
        session.flush()
        create_record(uow, table.id, values={"status": "open"}, actor=owner)
        view = create_form_view(uow, base.id, table.id, name="Tasks", view_type="grid", config={"fields": ["status"]}, actor=owner)
        session.flush()
        uow.add_workspace_member(WorkspaceMember(id=uuid4(), workspace_id=workspace.id, user_id=operator.actor_id, role=operator.role, status="active", version=1))
        session.flush()
        employee = create_digital_employee(uow, base.id, name="Gateway query", description="Query", telegram_alias=None, accessible_tables=[], accessible_views=[str(view.id)], allowed_actions=["query"], actor=owner)
        session.flush()
        plan = ExecutionPlan(ticket_id=str(uuid4()), workspace_id=str(workspace.id), employee_id=str(employee.id), actor=f"user:{operator.actor_id}", action="record.query", trace_id=uuid4().hex, idempotency_key=uuid4().hex, state=ExecutionTicketState.planned, budget=ExecutionBudget(max_tool_calls=1, max_wall_time_ms=1_000, max_graph_depth=1, max_retries=0, max_retrieval_chunks=0), invocations=[ToolInvocation(tool_name="record.query", input={"view_id": str(view.id)})])
        ticket = begin_execution_plan(uow, plan)
        session.commit()
        return {"ticket_id": ticket.id, "view_id": view.id}


def _postgres_create_draft_fixture(stage06_postgres: Stage06Postgres) -> dict[str, object]:
    owner = Actor(actor_type="user", actor_id="draft-owner", role="owner")
    operator = Actor(actor_type="user", actor_id="draft-operator", role="operator")
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(uow, name=f"Draft {uuid4().hex}", owner_user_id=owner.actor_id, actor=owner)
        session.flush()
        base = create_base(uow, workspace.id, name="Tasks", actor=owner)
        session.flush()
        table = create_table(uow, base.id, name="Tasks", key=f"tasks_{uuid4().hex[:8]}", actor=owner)
        session.flush()
        create_field(uow, table.id, name="Status", key="status", field_type="status", actor=owner)
        session.flush()
        uow.add_workspace_member(WorkspaceMember(id=uuid4(), workspace_id=workspace.id, user_id=operator.actor_id, role=operator.role, status="active", version=1))
        session.flush()
        employee = create_digital_employee(uow, base.id, name="Draft creator", description="Draft", telegram_alias=None, accessible_tables=[str(table.id)], accessible_views=[], allowed_actions=["draft_create"], actor=owner)
        session.flush()
        draft = create_create_record_draft(uow, employee.id, table_id=table.id, proposed_values={"status": "open"}, actor=operator)
        session.commit()
        return {"draft_id": draft.id, "actor": operator}


def _assert_create_draft_terminal_state(stage06_postgres: Stage06Postgres, draft_id, status: str, record_count: int) -> None:
    with stage06_postgres.session_factory() as session:
        draft = session.get(RecordChangeDraft, draft_id)
        assert draft is not None and draft.status == status
        assert session.scalar(select(func.count()).select_from(PlatformRecord)) == record_count
