from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from app.models.stage06_templates import ImportJob
from app.models.stage06_platform import WorkspaceMember
from app.models.stage08_runtime import Stage08ExecutionTicket
from app.runtime.stage08_collaboration_contracts import Stage08CollaborationContractFactory
from app.runtime.stage08_contracts import ExecutionBudget, ExecutionPlan, ExecutionTicketState, ToolInvocation
from app.runtime.stage08_tool_gateway import Stage08ToolGateway, Stage08ToolGatewayError
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    confirm_record_change_draft,
    create_digital_employee,
    reject_record_change_draft,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_runtime import begin_execution_plan


def test_record_query_returns_visible_field_keys_and_count() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(actions=["query"], views=[fixture.view.id])

    result = fixture.execute(employee, "record.query", {"view_id": str(fixture.view.id)})

    assert result.visible_field_keys == ["status"]
    assert result.counts == {"record_count": 1}
    assert result.entity_refs == [str(fixture.view.id)]
    assert result.error_code is None


def test_table_summarize_returns_only_projection_metadata() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(actions=["summarize"], views=[fixture.view.id])

    result = fixture.execute(employee, "table.summarize", {"view_id": str(fixture.view.id)})

    assert result.visible_field_keys == ["status"]
    assert result.counts == {"record_count": 1}
    assert result.entity_refs == [str(fixture.view.id)]


def test_contact_resolve_returns_only_member_reference_and_count() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(actions=["contact.resolve"])

    result = fixture.execute(
        employee,
        "contact.resolve",
        {"workspace_member_id": str(fixture.operator_member.id)},
    )

    assert result.entity_refs == [str(fixture.operator_member.id)]
    assert result.visible_field_keys == []
    assert result.counts == {"resolved_count": 1}
    assert "operator-1" not in result.model_dump_json()


def test_import_preview_returns_only_import_metadata_counts() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(actions=["import.preview"])
    import_job = ImportJob(
        id=uuid4(),
        workspace_id=fixture.workspace.id,
        base_id=None,
        source_type="csv",
        file_ref={"filename": "private.csv", "rows": [{"status": "open"}, {"status": "closed"}]},
        detected_schema=[{"key": "status"}, {"key": "private"}],
        preview_rows=[{"status": "open"}],
        mapping=[],
        status="awaiting_confirmation",
        created_by_user_id="operator-1",
        error_summary=None,
    )
    fixture.uow.add_import_job(import_job)

    result = fixture.execute(
        employee,
        "import.preview",
        {"import_job_id": str(import_job.id)},
    )

    assert result.entity_refs == [str(import_job.id)]
    assert result.visible_field_keys == []
    assert result.counts == {"row_count": 2, "field_count": 2}
    assert "private.csv" not in result.model_dump_json()


def test_tool_catalog_returns_exact_allowlist_without_manifest_text() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(actions=["tool_catalog.inspect"])

    result = fixture.execute(employee, "tool_catalog.inspect", {})

    assert result.counts == {"tool_count": 7}
    assert result.entity_refs == [
        "contact.resolve",
        "import.preview",
        "record.query",
        "record_change_draft.create",
        "table.summarize",
        "task.create_draft",
        "tool_catalog.inspect",
    ]
    assert result.visible_field_keys == []


def test_task_create_draft_does_not_create_record_until_confirmed() -> None:
    fixture = _gateway_fixture(with_record=False)
    employee = fixture.employee(actions=["draft_create"], tables=[fixture.table.id])
    proposed_values = {"status": "open"}

    result = fixture.execute(
        employee,
        "task.create_draft",
        {"table_id": str(fixture.table.id), "proposed_values": proposed_values},
    )

    assert len(fixture.uow.records) == 0
    assert len(fixture.uow.record_change_drafts) == 1
    draft = fixture.uow.record_change_drafts[0]
    assert draft.draft_type == "create_record"
    assert draft.record_id is None
    assert draft.status == "pending_confirmation"
    assert result.entity_refs == [str(draft.id), str(fixture.table.id)]
    assert result.counts == {"draft_count": 1, "confirmation_required": 1}
    assert "proposed_values" not in result.model_dump_json()

    confirm_record_change_draft(fixture.uow, draft.id, actor=fixture.operator)

    assert draft.status == "confirmed"
    assert draft.record_id is not None
    assert len(fixture.uow.records) == 1
    assert fixture.uow.records[0].values == proposed_values
    assert "proposed_values" not in _persisted_gateway_text(fixture)


def test_rejected_task_create_draft_never_creates_record() -> None:
    fixture = _gateway_fixture(with_record=False)
    employee = fixture.employee(actions=["draft_create"], tables=[fixture.table.id])

    fixture.execute(
        employee,
        "task.create_draft",
        {"table_id": str(fixture.table.id), "proposed_values": {"status": "open"}},
    )
    draft = fixture.uow.record_change_drafts[0]
    reject_record_change_draft(fixture.uow, draft.id, actor=fixture.operator)

    assert draft.status == "rejected"
    assert fixture.uow.records == []


def test_record_change_draft_create_is_redacted_and_does_not_write_record() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(
        actions=["draft_update"],
        tables=[fixture.table.id],
        views=[fixture.view.id],
    )
    original_version = fixture.record.version

    result = fixture.execute(
        employee,
        "record_change_draft.create",
        {"record_id": str(fixture.record.id), "proposed_values": {"status": "closed"}},
    )

    draft = fixture.uow.record_change_drafts[0]
    assert fixture.record.values["status"] == "open"
    assert fixture.record.version == original_version
    assert draft.status == "pending_confirmation"
    assert result.entity_refs == [str(draft.id), str(fixture.record.id)]
    assert result.counts == {"draft_count": 1, "confirmation_required": 1}
    assert "proposed_values" not in _persisted_gateway_text(fixture)


def test_e3_safe_execution_redacts_the_complete_ticket_gateway_and_draft_trace() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(
        actions=["draft_update"],
        tables=[fixture.table.id],
        views=[fixture.view.id],
    )
    trace_hash = "stage08:collaboration:" + "b" * 32
    safe_context = Stage08CollaborationContractFactory.safe_execution_context(
        trace_hash=trace_hash
    )
    invocation = ToolInvocation(
        tool_name="record_change_draft.create",
        input={
            "record_id": str(fixture.record.id),
            "proposed_values": {"next_action": "PRIVATE-NEXT-ACTION"},
        },
    )
    plan = ExecutionPlan(
        ticket_id="server-issued",
        workspace_id=str(fixture.workspace.id),
        employee_id=str(employee.id),
        actor="user:operator-1",
        action="record_change_draft.create",
        trace_id=trace_hash,
        idempotency_key="e3-safe-trace",
        state=ExecutionTicketState.planned,
        budget=ExecutionBudget(
            max_tool_calls=1,
            max_wall_time_ms=100,
            max_graph_depth=1,
            max_retries=0,
            max_retrieval_chunks=0,
        ),
        invocations=[invocation],
    )
    ticket = begin_execution_plan(fixture.uow, plan, safe_context=safe_context)
    returned = fixture.gateway.execute_plan(
        fixture.uow,
        ticket,
        [invocation],
        safe_context=safe_context,
    )

    assert returned.status == "succeeded"
    assert len(fixture.uow.record_change_drafts) == 1
    draft = fixture.uow.record_change_drafts[0]
    assert draft.proposed_values == {"next_action": "PRIVATE-NEXT-ACTION"}
    assert draft.trace_id == trace_hash
    assert returned.tool_summary == [
        {
            "graph": "stage08_collaboration_e3",
            "status": "succeeded",
            "action": "record_change_draft.create",
            "counts": {"confirmation_required": 1, "draft_count": 1},
            "code": None,
            "trace_hash": trace_hash,
            "latency_ms": 0,
            "ticket_present": True,
            "draft_present": True,
        }
    ]
    trace_text = json.dumps(
        {
            "agent_runs": [
                {
                    "agent_name": run.agent_name,
                    "graph_name": run.graph_name,
                    "input_summary": run.input_summary,
                    "output_summary": run.output_summary,
                    "tool_calls": run.tool_calls,
                    "trace_id": run.trace_id,
                    "created_entity_refs": run.created_entity_refs,
                }
                for run in fixture.uow.agent_runs
                if run.trace_id == trace_hash
            ],
            "audits": [
                {
                    "trace_id": event.trace_id,
                    "actor_id": event.actor_id,
                    "entity_id": event.entity_id,
                    "before_state": event.before_state,
                    "after_state": event.after_state,
                    "permission_snapshot": event.permission_snapshot,
                }
                for event in fixture.uow.audit_events
                if event.trace_id == trace_hash
            ],
            "tool_summaries": [
                candidate.tool_summary
                for candidate in fixture.uow.execution_tickets
                if candidate.trace_id == trace_hash
            ],
        },
        default=str,
        sort_keys=True,
    )
    forbidden_values = {
        "PRIVATE-NEXT-ACTION",
        "next_action",
        "operator-1",
        str(fixture.record.id),
        str(fixture.table.id),
        str(fixture.base.id),
        str(fixture.workspace.id),
        str(employee.id),
        str(ticket.id),
        str(draft.id),
    }
    assert all(value not in trace_text for value in forbidden_values)
    assert len(
        [run for run in fixture.uow.agent_runs if run.trace_id == trace_hash]
    ) == 1
    assert all(
        event.entity_id is None
        for event in fixture.uow.audit_events
        if event.trace_id == trace_hash
    )


def test_safe_execution_rejects_default_ticket_with_the_same_hash_trace() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(
        actions=["draft_update"],
        tables=[fixture.table.id],
        views=[fixture.view.id],
    )
    trace_hash = "stage08:collaboration:" + "c" * 32
    invocation = ToolInvocation(
        tool_name="record_change_draft.create",
        input={
            "record_id": str(fixture.record.id),
            "proposed_values": {"next_action": "PRIVATE-DEFAULT-TRACE"},
        },
    )
    plan = ExecutionPlan(
        ticket_id="server-issued",
        workspace_id=str(fixture.workspace.id),
        employee_id=str(employee.id),
        actor="user:operator-1",
        action="record_change_draft.create",
        trace_id=trace_hash,
        idempotency_key="e3-default-trace",
        state=ExecutionTicketState.planned,
        budget=ExecutionBudget(
            max_tool_calls=1,
            max_wall_time_ms=100,
            max_graph_depth=1,
            max_retries=0,
            max_retrieval_chunks=0,
        ),
        invocations=[invocation],
    )
    default_ticket = begin_execution_plan(fixture.uow, plan)
    default_trace_audits = [
        event for event in fixture.uow.audit_events if event.trace_id == trace_hash
    ]
    assert any(
        event.entity_id == default_ticket.id
        and event.after_state["ticket_id"] == str(default_ticket.id)
        for event in default_trace_audits
    )
    safe_context = Stage08CollaborationContractFactory.safe_execution_context(
        trace_hash=trace_hash
    )

    with pytest.raises(PlatformValidationError) as exc_info:
        begin_execution_plan(fixture.uow, plan, safe_context=safe_context)

    assert exc_info.value.code == "stage08_safe_execution_ticket_provenance_unavailable"
    assert len(fixture.uow.execution_tickets) == 1
    assert len(
        [event for event in fixture.uow.audit_events if event.trace_id == trace_hash]
    ) == len(default_trace_audits)


def test_gateway_fails_closed_for_unknown_tool_invalid_input_denied_policy_and_terminal_ticket() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(actions=["query"], views=[fixture.view.id])
    ticket = fixture.ticket(employee, "record.query")
    unknown = ToolInvocation.model_construct(tool_name="unknown.tool", input={})

    with pytest.raises(Stage08ToolGatewayError, match="tool_not_registered"):
        fixture.gateway.execute(fixture.uow, ticket, unknown)
    assert ticket.status == "denied"
    assert fixture.uow.agent_runs == []

    invalid_ticket = fixture.ticket(employee, "record.query", trace_id="invalid-input")
    with pytest.raises(Stage08ToolGatewayError, match="invalid_input"):
        fixture.gateway.execute(
            fixture.uow,
            invalid_ticket,
            ToolInvocation(tool_name="record.query", input={"view_id": "not-a-uuid"}),
        )
    assert invalid_ticket.status == "denied"

    denied_ticket = fixture.ticket(employee, "record.query", trace_id="policy-denied")
    employee.allowed_actions = []
    with pytest.raises(Stage08ToolGatewayError, match="policy_denied"):
        fixture.gateway.execute(
            fixture.uow,
            denied_ticket,
            ToolInvocation(tool_name="record.query", input={"view_id": str(fixture.view.id)}),
        )
    assert denied_ticket.status == "denied"

    employee.allowed_actions = ["query"]
    completed_ticket = fixture.ticket(employee, "record.query", trace_id="completed")
    fixture.gateway.execute(
        fixture.uow,
        completed_ticket,
        ToolInvocation(tool_name="record.query", input={"view_id": str(fixture.view.id)}),
    )
    with pytest.raises(Stage08ToolGatewayError, match="ticket_not_planned"):
        fixture.gateway.execute(
            fixture.uow,
            completed_ticket,
            ToolInvocation(tool_name="record.query", input={"view_id": str(fixture.view.id)}),
        )
    assert completed_ticket.status == "succeeded"


def test_gateway_uses_only_canonical_ticket_after_detached_employee_and_actor_forgery() -> None:
    fixture = _gateway_fixture()
    canonical_employee = fixture.employee(actions=["query"], views=[fixture.view.id])
    forged_employee = fixture.employee(actions=["query"], views=[fixture.view.id])
    ticket = fixture.ticket(canonical_employee, "record.query")
    detached = Stage08ExecutionTicket(
        id=ticket.id,
        workspace_id=uuid4(),
        employee_id=forged_employee.id,
        actor_id="user:owner-1",
        action="record.query",
        trace_id="forged",
        request_fingerprint="f" * 64,
        status="planned",
        budget={},
        tool_summary=[],
        completed_at=None,
    )

    result = fixture.gateway.execute(
        fixture.uow,
        detached,
        ToolInvocation(tool_name="record.query", input={"view_id": str(fixture.view.id)}),
    )

    assert result.visible_field_keys == ["status"]
    assert fixture.uow.agent_runs[-1].agent_name == canonical_employee.name
    assert ticket.status == "succeeded"
    assert len(ticket.tool_summary) == 1
    assert detached.status == "planned"
    assert detached.tool_summary == []


def test_execute_plan_transitions_once_and_appends_successful_summaries_in_order() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(actions=["contact.resolve", "tool_catalog.inspect"])
    ticket = _plan_ticket(
        fixture,
        employee,
        action="contact.resolve",
        invocations=[
            ToolInvocation(
                tool_name="contact.resolve",
                input={"workspace_member_id": str(fixture.operator_member.id)},
            ),
            ToolInvocation(tool_name="tool_catalog.inspect", input={}),
        ],
    )

    returned = fixture.gateway.execute_plan(
        fixture.uow,
        ticket,
        [
            ToolInvocation(
                tool_name="contact.resolve",
                input={"workspace_member_id": str(fixture.operator_member.id)},
            ),
            ToolInvocation(tool_name="tool_catalog.inspect", input={}),
        ],
    )

    assert returned is ticket
    assert ticket.status == "succeeded"
    assert [item["tool_name"] for item in ticket.tool_summary] == [
        "contact.resolve",
        "tool_catalog.inspect",
    ]
    transitions = [
        event.after_state["status"]
        for event in fixture.uow.audit_events
        if event.event_type == "stage08.execution_ticket_transitioned"
    ]
    assert transitions == ["executing", "succeeded"]


def test_execute_plan_stops_after_first_failure_without_invoking_later_adapter() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(actions=["query", "tool_catalog.inspect"])
    ticket = _plan_ticket(
        fixture,
        employee,
        action="record.query",
        invocations=[
            ToolInvocation(tool_name="record.query", input={}),
            ToolInvocation(tool_name="tool_catalog.inspect", input={}),
        ],
    )
    later_calls: list[str] = []

    def fail_first(*args, **kwargs):
        raise RuntimeError("adapter error")

    def track_later(*args, **kwargs):
        later_calls.append("tool_catalog.inspect")
        raise AssertionError("later adapter must not run")

    fixture.gateway._registry["record.query"] = fail_first
    fixture.gateway._registry["tool_catalog.inspect"] = track_later

    returned = fixture.gateway.execute_plan(
        fixture.uow,
        ticket,
        [
            ToolInvocation(tool_name="record.query", input={}),
            ToolInvocation(tool_name="tool_catalog.inspect", input={}),
        ],
    )

    assert returned is ticket
    assert ticket.status == "failed"
    assert ticket.tool_summary == [{
        "tool_name": "record.query",
        "status": "failed",
        "entity_refs": [],
        "visible_field_keys": [],
        "counts": {},
        "error_code": "tool_execution_failed",
    }]
    assert later_calls == []


def test_gateway_rejects_detached_workspace_scope_without_calling_adapter() -> None:
    fixture = _gateway_fixture()
    employee = fixture.employee(actions=["contact.resolve"])
    ticket = fixture.ticket(employee, "contact.resolve")
    foreign_workspace = create_workspace(
        fixture.uow,
        name="Foreign",
        owner_user_id="foreign-owner",
        actor=fixture.owner,
    )
    foreign_member = WorkspaceMember(
        id=uuid4(),
        workspace_id=foreign_workspace.id,
        user_id="foreign-user",
        role="owner",
        status="active",
        version=1,
    )
    fixture.uow.add_workspace_member(foreign_member)
    detached = Stage08ExecutionTicket(
        id=ticket.id,
        workspace_id=foreign_workspace.id,
        employee_id=employee.id,
        actor_id="user:foreign-user",
        action="contact.resolve",
        trace_id="forged-workspace",
        request_fingerprint="f" * 64,
        status="planned",
        budget={},
        tool_summary=[],
        completed_at=None,
    )

    with pytest.raises(Stage08ToolGatewayError, match="permission_denied"):
        fixture.gateway.execute(
            fixture.uow,
            detached,
            ToolInvocation(
                tool_name="contact.resolve",
                input={"workspace_member_id": str(foreign_member.id)},
            ),
        )

    assert ticket.status == "denied"
    assert len(ticket.tool_summary) == 1
    assert detached.status == "planned"
    assert detached.tool_summary == []


@pytest.mark.parametrize("confirmation_actor", [
    Actor(actor_type="user", actor_id="operator-1", role="operator"),
    Actor(actor_type="user", actor_id="viewer-1", role="viewer"),
])
def test_create_record_draft_confirmation_revalidates_current_actor_write_access(
    confirmation_actor: Actor,
) -> None:
    fixture = _gateway_fixture(with_record=False)
    employee = fixture.employee(actions=["draft_create"], tables=[fixture.table.id])
    fixture.uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=fixture.workspace.id,
            user_id="viewer-1",
            role="viewer",
            status="active",
            version=1,
        )
    )
    fixture.execute(
        employee,
        "task.create_draft",
        {"table_id": str(fixture.table.id), "proposed_values": {"status": "open"}},
    )
    draft = fixture.uow.record_change_drafts[0]
    if confirmation_actor.actor_id == "operator-1":
        fixture.uow.fields[0].permission_policy = {"operator": "read", "owner": "write"}

    with pytest.raises(PlatformValidationError):
        confirm_record_change_draft(fixture.uow, draft.id, actor=confirmation_actor)

    assert draft.status == "pending_confirmation"
    assert draft.record_id is None
    assert fixture.uow.records == []


def test_create_record_draft_confirmation_rejects_revoked_workspace_membership() -> None:
    fixture = _gateway_fixture(with_record=False)
    employee = fixture.employee(actions=["draft_create"], tables=[fixture.table.id])
    fixture.execute(
        employee,
        "task.create_draft",
        {"table_id": str(fixture.table.id), "proposed_values": {"status": "open"}},
    )
    draft = fixture.uow.record_change_drafts[0]
    fixture.operator_member.status = "inactive"

    with pytest.raises(PlatformValidationError):
        confirm_record_change_draft(fixture.uow, draft.id, actor=fixture.operator)

    assert draft.status == "pending_confirmation"
    assert draft.record_id is None
    assert fixture.uow.records == []


def test_create_record_draft_confirmation_rejects_stale_actor_after_member_role_downgrade() -> None:
    fixture = _gateway_fixture(with_record=False)
    employee = fixture.employee(actions=["draft_create"], tables=[fixture.table.id])
    fixture.execute(
        employee,
        "task.create_draft",
        {"table_id": str(fixture.table.id), "proposed_values": {"status": "open"}},
    )
    draft = fixture.uow.record_change_drafts[0]
    fixture.operator_member.role = "viewer"

    with pytest.raises(PlatformValidationError):
        confirm_record_change_draft(fixture.uow, draft.id, actor=fixture.operator)

    assert draft.status == "pending_confirmation"
    assert draft.record_id is None
    assert fixture.uow.records == []


class _GatewayFixture:
    def __init__(self, *, with_record: bool = True) -> None:
        self.uow = InMemoryStage06PlatformUnitOfWork()
        self.owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
        self.operator = Actor(actor_type="user", actor_id="operator-1", role="operator")
        self.workspace = create_workspace(
            self.uow,
            name="Stage08 Gateway",
            owner_user_id=self.owner.actor_id,
            actor=self.owner,
        )
        self.base = create_base(self.uow, self.workspace.id, name="Gateway", actor=self.owner)
        self.operator_member = self.uow.workspace_members[0].__class__(
            id=uuid4(),
            workspace_id=self.workspace.id,
            user_id=self.operator.actor_id,
            role=self.operator.role,
            status="active",
            version=1,
        )
        self.uow.add_workspace_member(self.operator_member)
        self.table = create_table(self.uow, self.base.id, name="Tasks", key="tasks", actor=self.owner)
        create_field(self.uow, self.table.id, name="Status", key="status", field_type="status", permission_policy={"operator": "write", "owner": "write"}, actor=self.owner)
        create_field(self.uow, self.table.id, name="Internal", key="internal", field_type="text", permission_policy={"operator": "hidden", "owner": "write"}, actor=self.owner)
        self.record = None
        if with_record:
            self.record = create_record(self.uow, self.table.id, values={"status": "open", "internal": "secret"}, actor=self.owner)
        self.view = create_form_view(
            self.uow,
            self.base.id,
            self.table.id,
            name="Task Grid",
            view_type="grid",
            config={"fields": ["status", "internal"]},
            actor=self.owner,
        )
        self.gateway = Stage08ToolGateway()

    def employee(self, *, actions: list[str], tables: list[UUID] | None = None, views: list[UUID] | None = None):
        return create_digital_employee(
            self.uow,
            self.base.id,
            name=f"Employee {len(self.uow.digital_employees)}",
            description="Gateway test employee",
            telegram_alias=None,
            accessible_tables=[str(table_id) for table_id in tables or []],
            accessible_views=[str(view_id) for view_id in views or []],
            allowed_actions=actions,
            actor=self.owner,
        )

    def ticket(self, employee, tool_name: str, *, trace_id: str | None = None):
        from app.runtime.stage08_contracts import ExecutionPlan

        return begin_execution_plan(
            self.uow,
            ExecutionPlan(
                ticket_id=str(uuid4()),
                workspace_id=str(self.workspace.id),
                employee_id=str(employee.id),
                actor="user:operator-1",
                action=tool_name,
                trace_id=trace_id or str(uuid4()),
                idempotency_key=str(uuid4()),
                state=ExecutionTicketState.planned,
                budget=ExecutionBudget(max_tool_calls=1, max_wall_time_ms=100, max_graph_depth=1, max_retries=0, max_retrieval_chunks=0),
                invocations=[ToolInvocation(tool_name=tool_name, input={})],
            ),
        )

    def execute(self, employee, tool_name: str, tool_input: dict[str, object]):
        return self.gateway.execute(self.uow, self.ticket(employee, tool_name), ToolInvocation(tool_name=tool_name, input=tool_input))


def _gateway_fixture(*, with_record: bool = True) -> _GatewayFixture:
    return _GatewayFixture(with_record=with_record)


def _plan_ticket(
    fixture: _GatewayFixture,
    employee,
    *,
    action: str,
    invocations: list[ToolInvocation],
):
    return begin_execution_plan(
        fixture.uow,
        ExecutionPlan(
            ticket_id=str(uuid4()),
            workspace_id=str(fixture.workspace.id),
            employee_id=str(employee.id),
            actor="user:operator-1",
            action=action,
            trace_id=str(uuid4()),
            idempotency_key=str(uuid4()),
            state=ExecutionTicketState.planned,
            budget=ExecutionBudget(
                max_tool_calls=2,
                max_wall_time_ms=100,
                max_graph_depth=1,
                max_retries=0,
                max_retrieval_chunks=0,
            ),
            invocations=invocations,
        ),
    )


def _persisted_gateway_text(fixture: _GatewayFixture) -> str:
    return json.dumps(
        {
            "ticket_summaries": [ticket.tool_summary for ticket in fixture.uow.execution_tickets],
            "audits": [
                {"before": event.before_state, "after": event.after_state}
                for event in fixture.uow.audit_events
            ],
        },
        default=str,
        sort_keys=True,
    )
