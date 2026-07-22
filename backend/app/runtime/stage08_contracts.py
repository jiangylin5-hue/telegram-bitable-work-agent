from enum import Enum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator
from typing_extensions import TypeAliasType


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue = TypeAliasType(
    "JSONValue", JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
)

_SENSITIVE_INPUT_KEYS = frozenset({"prompt", "response", "api_key", "token", "raw_text"})

ToolName = Literal[
    "record.query",
    "table.summarize",
    "contact.resolve",
    "import.preview",
    "tool_catalog.inspect",
    "task.create_draft",
    "record_change_draft.create",
]
ToolResultStatus = Literal["succeeded", "failed", "denied"]
ToolErrorCode = Literal[
    "budget_exceeded",
    "confirmation_required",
    "invalid_input",
    "not_found",
    "permission_denied",
    "policy_denied",
    "tool_execution_failed",
]


class ExecutionBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_tool_calls: StrictInt = Field(ge=1, le=7)
    max_wall_time_ms: StrictInt = Field(ge=100, le=30_000)
    max_graph_depth: StrictInt = Field(ge=1, le=3)
    max_retries: StrictInt = Field(ge=0, le=2)
    max_retrieval_chunks: StrictInt = Field(ge=0, le=0)


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tool_name: ToolName
    input: JSONValue

    @model_validator(mode="after")
    def reject_sensitive_input_keys(self) -> "ToolInvocation":
        _reject_sensitive_input_keys(self.input)
        return self


class ExecutionTicketState(str, Enum):
    planned = "planned"
    executing = "executing"
    succeeded = "succeeded"
    failed = "failed"
    denied = "denied"
    cancelled = "cancelled"
    timed_out = "timed_out"
    expired = "expired"


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: StrictStr
    workspace_id: StrictStr
    employee_id: StrictStr
    actor: StrictStr
    action: StrictStr
    trace_id: StrictStr
    idempotency_key: StrictStr
    state: ExecutionTicketState
    budget: ExecutionBudget
    invocations: list[ToolInvocation]

    @model_validator(mode="after")
    def enforce_tool_call_budget(self) -> "ExecutionPlan":
        if len(self.invocations) > self.budget.max_tool_calls:
            raise ValueError("Execution plan exceeds its tool call budget")
        return self


class RedactedToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: ToolName
    status: ToolResultStatus
    entity_refs: list[StrictStr]
    visible_field_keys: list[StrictStr]
    counts: dict[StrictStr, StrictInt]
    error_code: ToolErrorCode | None


def _reject_sensitive_input_keys(value: JSONValue) -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if key.casefold() in _SENSITIVE_INPUT_KEYS:
                raise ValueError("Tool invocation input contains a prohibited key")
            _reject_sensitive_input_keys(nested_value)
    elif isinstance(value, list):
        for item in value:
            _reject_sensitive_input_keys(item)
