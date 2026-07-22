from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.runtime.stage08_contracts import (
    ExecutionBudget,
    ExecutionTicketState,
    RedactedToolResult,
    ToolInvocation,
    ToolName,
)


class RuntimeExecutionPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    workspace_id: StrictStr = Field(min_length=1, max_length=120)
    employee_id: StrictStr = Field(min_length=1, max_length=120)
    action: ToolName
    trace_id: StrictStr = Field(min_length=1, max_length=120)
    idempotency_key: StrictStr = Field(min_length=1, max_length=160)
    budget: ExecutionBudget
    invocations: list[ToolInvocation] = Field(min_length=1, max_length=7)


class RuntimeExecutionPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ticket_id: StrictStr
    status: Literal[
        ExecutionTicketState.succeeded,
        ExecutionTicketState.failed,
        ExecutionTicketState.denied,
    ]
    tool_summary: list[RedactedToolResult]
