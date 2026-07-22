from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.models.stage06_platform import WorkspaceMember
from app.models.stage06_runtime import DigitalEmployeeMemberGrant
from app.models.stage08_runtime import Stage08ExecutionTicket
from app.runtime.stage08_contracts import (
    ExecutionBudget,
    ExecutionPlan,
    ExecutionTicketState,
    ToolInvocation,
)
from app.runtime.stage08_policy import evaluate_execution_plan
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_workspace,
)
from app.services.stage08_runtime import (
    begin_execution_plan,
    transition_execution_ticket,
)


def test_policy_allows_active_member_and_employee_query_tool() -> None:
    fixture = _runtime_fixture()

    decision = evaluate_execution_plan(fixture.uow, fixture.plan())

    assert decision.allowed is True
    assert decision.reason_code is None
    assert decision.effective_tool_names == ("record.query",)


def test_policy_denies_unconfigured_tool_without_persisting_anything() -> None:
    fixture = _runtime_fixture()
    plan = fixture.plan(
        action="import.preview",
        invocations=[ToolInvocation(tool_name="import.preview", input={"file": "safe"})],
    )

    decision = evaluate_execution_plan(fixture.uow, plan)

    assert decision.allowed is False
    assert decision.reason_code == "tool_not_allowed_by_employee"
    assert decision.effective_tool_names == ()
    with pytest.raises(PlatformValidationError) as denied:
        begin_execution_plan(fixture.uow, plan)
    assert denied.value.code == "stage08_policy_denied"
    assert fixture.uow.execution_tickets == []
    assert fixture.uow.idempotency_records == []
    assert fixture.uow.audit_events == fixture.initial_audit_events


@pytest.mark.parametrize(
    ("mutate", "reason_code"),
    [
        (lambda fixture, plan: setattr(plan, "workspace_id", str(uuid4())), "workspace_mismatch"),
        (lambda fixture, plan: setattr(plan, "actor", "operator-1"), "actor_invalid"),
        (
            lambda fixture, plan: setattr(fixture.operator, "status", "inactive"),
            "actor_not_workspace_member",
        ),
    ],
)
def test_policy_denies_invalid_workspace_or_actor(
    mutate,
    reason_code: str,
) -> None:
    fixture = _runtime_fixture()
    plan = fixture.plan()
    mutate(fixture, plan)

    decision = evaluate_execution_plan(fixture.uow, plan)

    assert decision.allowed is False
    assert decision.reason_code == reason_code
    assert decision.effective_tool_names == ()


def test_policy_denies_assigned_employee_without_member_grant() -> None:
    fixture = _runtime_fixture()
    fixture.employee.access_mode = "assigned"

    decision = evaluate_execution_plan(fixture.uow, fixture.plan())

    assert decision.allowed is False
    assert decision.reason_code == "employee_caller_scope_denied"
    fixture.uow.add_digital_employee_member_grant(
        DigitalEmployeeMemberGrant(
            id=uuid4(),
            employee_id=fixture.employee.id,
            workspace_member_id=fixture.operator.id,
        )
    )
    assert evaluate_execution_plan(fixture.uow, fixture.plan()).allowed is True


def test_policy_denies_injected_plan_action_and_constructed_budget_bypass() -> None:
    fixture = _runtime_fixture()
    injected_data = fixture.plan().model_dump()
    injected_data["action"] = "telegram.send"
    injected = ExecutionPlan.model_construct(**injected_data)
    unsafe_budget = ExecutionBudget.model_construct(
        max_tool_calls=0,
        max_wall_time_ms=99,
        max_graph_depth=4,
        max_retries=3,
        max_retrieval_chunks=1,
    )
    bypassed_data = fixture.plan().model_dump()
    bypassed_data["budget"] = unsafe_budget
    bypassed_data["invocations"] = [
        ToolInvocation(tool_name="record.query", input={"query": "safe"}),
        ToolInvocation(tool_name="record.query", input={"query": "safe-2"}),
    ]
    bypassed = ExecutionPlan.model_construct(**bypassed_data)

    assert evaluate_execution_plan(fixture.uow, injected).reason_code == "plan_action_invalid"
    assert evaluate_execution_plan(fixture.uow, bypassed).reason_code == "execution_budget_invalid"


def test_begin_execution_plan_replays_same_semantics_and_conflicts_changed_request() -> None:
    fixture = _runtime_fixture()
    first = begin_execution_plan(fixture.uow, fixture.plan())
    replay = begin_execution_plan(
        fixture.uow,
        fixture.plan(ticket_id=str(uuid4()), trace_id="trace-replay"),
    )

    assert replay is first
    assert len(fixture.uow.execution_tickets) == 1
    assert len(fixture.uow.idempotency_records) == 1
    assert fixture.uow.idempotency_records[0].response_ref == {
        "ticket_id": str(first.id),
        "status": "planned",
    }
    with pytest.raises(PlatformValidationError) as conflict:
        begin_execution_plan(
            fixture.uow,
            fixture.plan(
                ticket_id=str(uuid4()),
                trace_id="trace-conflict",
                invocations=[
                    ToolInvocation(
                        tool_name="record.query",
                        input={"query": "different"},
                    )
                ],
            ),
        )
    assert conflict.value.code == "idempotency_conflict"


def test_begin_execution_plan_rejects_trace_conflict_before_idempotency_record() -> None:
    fixture = _runtime_fixture()
    first = begin_execution_plan(fixture.uow, fixture.plan(idempotency_key="first-key"))

    with pytest.raises(PlatformValidationError) as conflict:
        begin_execution_plan(
            fixture.uow,
            fixture.plan(
                ticket_id=str(uuid4()),
                idempotency_key="second-key",
                invocations=[
                    ToolInvocation(
                        tool_name="record.query",
                        input={"query": "different"},
                    )
                ],
            ),
        )

    assert conflict.value.code == "stage08_trace_conflict"
    assert len(fixture.uow.execution_tickets) == 1
    assert fixture.uow.execution_tickets[0] is first
    assert len(fixture.uow.idempotency_records) == 1


def test_execution_plan_workspace_lock_returns_only_matching_workspace() -> None:
    fixture = _runtime_fixture()

    assert (
        fixture.uow.lock_workspace_for_stage08_execution(fixture.workspace.id)
        is fixture.workspace
    )
    assert fixture.uow.lock_workspace_for_stage08_execution(uuid4()) is None


@pytest.mark.parametrize("poisoned_field", ["workspace_id", "request_fingerprint"])
def test_begin_execution_plan_rejects_replay_ticket_outside_current_scope(
    poisoned_field: str,
) -> None:
    fixture = _runtime_fixture()
    first = begin_execution_plan(fixture.uow, fixture.plan())
    if poisoned_field == "workspace_id":
        first.workspace_id = uuid4()
    else:
        first.request_fingerprint = "poisoned-request-fingerprint"

    with pytest.raises(PlatformValidationError) as invalid_replay:
        begin_execution_plan(
            fixture.uow,
            fixture.plan(ticket_id=str(uuid4()), trace_id="trace-replay"),
        )

    assert invalid_replay.value.code == "stage08_idempotency_replay_invalid"


def test_transition_rejects_detached_ticket_not_tracked_by_uow() -> None:
    fixture = _runtime_fixture()
    detached = Stage08ExecutionTicket(
        id=uuid4(),
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        actor_id="user:operator-1",
        action="record.query",
        trace_id="detached-ticket",
        request_fingerprint="f" * 64,
        status="planned",
        budget={"max_tool_calls": 1},
        tool_summary=[],
        completed_at=None,
    )

    with pytest.raises(PlatformValidationError) as missing:
        transition_execution_ticket(fixture.uow, detached, ExecutionTicketState.executing)

    assert missing.value.code == "stage08_ticket_not_found"
    assert detached.status == "planned"


def test_transition_allows_only_planned_to_executing_to_terminal() -> None:
    fixture = _runtime_fixture()
    ticket = begin_execution_plan(fixture.uow, fixture.plan())

    with pytest.raises(PlatformValidationError) as direct_terminal:
        transition_execution_ticket(fixture.uow, ticket, ExecutionTicketState.succeeded)
    assert direct_terminal.value.code == "stage08_ticket_transition_invalid"
    assert ticket.status == "planned"
    assert ticket.completed_at is None

    transition_execution_ticket(fixture.uow, ticket, ExecutionTicketState.executing)
    assert ticket.status == "executing"
    assert ticket.completed_at is None
    transition_execution_ticket(fixture.uow, ticket, ExecutionTicketState.succeeded)
    completed_at = ticket.completed_at
    assert completed_at is not None
    assert ticket.status == "succeeded"

    with pytest.raises(PlatformValidationError) as revived:
        transition_execution_ticket(fixture.uow, ticket, ExecutionTicketState.executing)
    assert revived.value.code == "stage08_ticket_transition_invalid"
    assert ticket.completed_at == completed_at


def test_ticket_audit_and_idempotency_never_persist_invocation_input() -> None:
    fixture = _runtime_fixture()
    sentinel = "INVOCATION_SECRET_SENTINEL"
    ticket = begin_execution_plan(
        fixture.uow,
        fixture.plan(
            invocations=[
                ToolInvocation(
                    tool_name="record.query",
                    input={"query": sentinel, "nested": {"note": "private"}},
                )
            ]
        ),
    )
    transition_execution_ticket(fixture.uow, ticket, ExecutionTicketState.executing)
    transition_execution_ticket(fixture.uow, ticket, ExecutionTicketState.denied)

    persisted_text = json.dumps(
        {
            "audits": [
                {
                    "before": event.before_state,
                    "after": event.after_state,
                    "permission": event.permission_snapshot,
                }
                for event in fixture.uow.audit_events
            ],
            "idempotency": [record.response_ref for record in fixture.uow.idempotency_records],
        },
        sort_keys=True,
        default=str,
    )
    assert sentinel not in persisted_text
    assert '"prompt"' not in persisted_text
    assert '"response"' not in persisted_text
    assert '"api_key"' not in persisted_text


class _RuntimeFixture:
    def __init__(self) -> None:
        self.uow = InMemoryStage06PlatformUnitOfWork()
        self.owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
        self.workspace = create_workspace(
            self.uow,
            name="Stage08 runtime",
            owner_user_id=self.owner.actor_id,
            actor=self.owner,
        )
        self.base = create_base(
            self.uow,
            self.workspace.id,
            name="Runtime",
            actor=self.owner,
        )
        self.operator = WorkspaceMember(
            id=uuid4(),
            workspace_id=self.workspace.id,
            user_id="operator-1",
            role="operator",
            status="active",
            version=1,
        )
        self.uow.add_workspace_member(self.operator)
        self.employee = create_digital_employee(
            self.uow,
            self.base.id,
            name="Query helper",
            description="Reads records",
            telegram_alias=None,
            accessible_tables=[],
            accessible_views=[],
            allowed_actions=["query"],
            actor=self.owner,
        )
        self.initial_audit_events = list(self.uow.audit_events)

    def plan(
        self,
        *,
        ticket_id: str | None = None,
        trace_id: str = "trace-1",
        idempotency_key: str = "idempotency-1",
        action: str = "record.query",
        invocations: list[ToolInvocation] | None = None,
    ) -> ExecutionPlan:
        return ExecutionPlan(
            ticket_id=ticket_id or str(uuid4()),
            workspace_id=str(self.workspace.id),
            employee_id=str(self.employee.id),
            actor="user:operator-1",
            action=action,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            state=ExecutionTicketState.planned,
            budget=ExecutionBudget(
                max_tool_calls=2,
                max_wall_time_ms=1_000,
                max_graph_depth=1,
                max_retries=0,
                max_retrieval_chunks=0,
            ),
            invocations=invocations
            or [ToolInvocation(tool_name="record.query", input={"query": "safe"})],
        )


def _runtime_fixture() -> _RuntimeFixture:
    return _RuntimeFixture()
