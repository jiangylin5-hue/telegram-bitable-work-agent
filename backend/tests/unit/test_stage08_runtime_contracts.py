from pydantic import ValidationError
import pytest

from app.runtime.stage08_contracts import (
    ExecutionBudget,
    ExecutionPlan,
    ExecutionTicketState,
    RedactedToolResult,
    ToolInvocation,
)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("max_tool_calls", 0),
        ("max_tool_calls", 8),
        ("max_wall_time_ms", 99),
        ("max_wall_time_ms", 30_001),
        ("max_graph_depth", 0),
        ("max_graph_depth", 4),
        ("max_retries", -1),
        ("max_retries", 3),
        ("max_retrieval_chunks", 1),
    ],
)
def test_execution_budget_rejects_invalid_limits(field_name: str, value: int) -> None:
    payload = {
        "max_tool_calls": 1,
        "max_wall_time_ms": 100,
        "max_graph_depth": 1,
        "max_retries": 0,
        "max_retrieval_chunks": 0,
    }
    payload[field_name] = value

    with pytest.raises(ValidationError):
        ExecutionBudget(**payload)


@pytest.mark.parametrize("value", [False, 0.0, "0"])
def test_execution_budget_rejects_non_strict_zero_retrieval_limit(value: object) -> None:
    with pytest.raises(ValidationError):
        ExecutionBudget(
            max_tool_calls=1,
            max_wall_time_ms=100,
            max_graph_depth=1,
            max_retries=0,
            max_retrieval_chunks=value,
        )


def test_tool_invocation_rejects_unknown_tool() -> None:
    with pytest.raises(ValidationError):
        ToolInvocation(tool_name="provider.call", input={"record_id": "rec-1"})


@pytest.mark.parametrize("sensitive_key", ["prompt", "response", "api_key", "token", "raw_text"])
def test_tool_invocation_rejects_all_nested_sensitive_keys(sensitive_key: str) -> None:
    with pytest.raises(ValidationError):
        ToolInvocation(
            tool_name="record.query",
            input={"filters": {sensitive_key: "unsafe"}},
        )


def test_tool_invocation_rejects_sensitive_keys_nested_in_lists() -> None:
    with pytest.raises(ValidationError):
        ToolInvocation(
            tool_name="record.query",
            input={"filters": [{"conditions": [{"token": "unsafe"}]}]},
        )


def test_tool_invocation_rejects_non_json_nested_values() -> None:
    with pytest.raises(ValidationError):
        ToolInvocation(tool_name="record.query", input={"record_ids": ("rec-1",)})


def test_tool_invocation_accepts_allowed_tool_and_safe_json_input() -> None:
    invocation = ToolInvocation(
        tool_name="record.query",
        input={"table_id": "tbl-1", "filters": [{"field": "status", "value": "open"}]},
    )

    assert invocation.tool_name == "record.query"
    assert invocation.input == {
        "table_id": "tbl-1",
        "filters": [{"field": "status", "value": "open"}],
    }


def test_redacted_result_dto_has_no_free_text_answer_or_content_fields() -> None:
    result = RedactedToolResult(
        tool_name="record.query",
        status="succeeded",
        entity_refs=["rec-1"],
        visible_field_keys=["status"],
        counts={"records": 1},
        error_code=None,
    )

    assert "answer" not in RedactedToolResult.model_fields
    assert "content" not in RedactedToolResult.model_fields
    assert result.model_dump() == {
        "tool_name": "record.query",
        "status": "succeeded",
        "entity_refs": ["rec-1"],
        "visible_field_keys": ["status"],
        "counts": {"records": 1},
        "error_code": None,
    }
    with pytest.raises(ValidationError):
        RedactedToolResult(
            tool_name="record.query",
            status="succeeded",
            entity_refs=[],
            visible_field_keys=[],
            counts={},
            error_code=None,
            answer="unsafe",
        )


def test_execution_plan_and_ticket_state_are_importable_contracts() -> None:
    plan = ExecutionPlan(
        ticket_id="ticket-1",
        workspace_id="workspace-1",
        employee_id="employee-1",
        actor="user:user-1",
        action="record.query",
        trace_id="trace-1",
        idempotency_key="idempotency-1",
        state=ExecutionTicketState.planned,
        budget=ExecutionBudget(
            max_tool_calls=1,
            max_wall_time_ms=100,
            max_graph_depth=1,
            max_retries=0,
            max_retrieval_chunks=0,
        ),
        invocations=[ToolInvocation(tool_name="tool_catalog.inspect", input=None)],
    )

    assert plan.state is ExecutionTicketState.planned
    assert plan.workspace_id == "workspace-1"
    assert plan.employee_id == "employee-1"
    assert plan.actor == "user:user-1"
    assert plan.action == "record.query"
    assert plan.trace_id == "trace-1"
    assert plan.idempotency_key == "idempotency-1"


@pytest.mark.parametrize(
    "state",
    [
        "planned",
        "executing",
        "succeeded",
        "failed",
        "denied",
        "cancelled",
        "timed_out",
        "expired",
    ],
)
def test_execution_ticket_state_accepts_only_the_approved_state_machine(state: str) -> None:
    assert ExecutionTicketState(state).value == state


def test_execution_ticket_state_has_exactly_the_approved_states() -> None:
    assert {state.value for state in ExecutionTicketState} == {
        "planned",
        "executing",
        "succeeded",
        "failed",
        "denied",
        "cancelled",
        "timed_out",
        "expired",
    }


@pytest.mark.parametrize("state", ["pending_confirmation", "confirmed", "rejected"])
def test_execution_ticket_state_rejects_retired_states(state: str) -> None:
    with pytest.raises(ValueError):
        ExecutionTicketState(state)


@pytest.mark.parametrize("status", ["pending_confirmation", "confirmed", "rejected"])
def test_redacted_result_rejects_retired_statuses(status: str) -> None:
    with pytest.raises(ValidationError):
        RedactedToolResult(
            tool_name="record.query",
            status=status,
            entity_refs=[],
            visible_field_keys=[],
            counts={},
            error_code="policy_denied",
        )


def test_redacted_result_uses_denied_not_rejected() -> None:
    result = RedactedToolResult(
        tool_name="record.query",
        status="denied",
        entity_refs=[],
        visible_field_keys=[],
        counts={},
        error_code="policy_denied",
    )

    assert result.status == "denied"


def test_execution_plan_rejects_more_invocations_than_its_budget() -> None:
    with pytest.raises(ValidationError):
        ExecutionPlan(
            ticket_id="ticket-1",
            workspace_id="workspace-1",
            employee_id="employee-1",
            actor="user:user-1",
            action="record.query",
            trace_id="trace-1",
            idempotency_key="idempotency-1",
            state=ExecutionTicketState.planned,
            budget=ExecutionBudget(
                max_tool_calls=1,
                max_wall_time_ms=100,
                max_graph_depth=1,
                max_retries=0,
                max_retrieval_chunks=0,
            ),
            invocations=[
                ToolInvocation(tool_name="record.query", input=None),
                ToolInvocation(tool_name="tool_catalog.inspect", input=None),
            ],
        )
