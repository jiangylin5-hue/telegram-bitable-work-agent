from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.runtime.stage08_collaboration_contracts import AssistantQuerySafeView


Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ScopeProofRef = Annotated[
    str,
    StringConstraints(pattern=r"^scope:sha256:[0-9a-f]{64}$", max_length=80),
]
Capability = Literal["platform.tabular.analyse"]
CommandType = Literal["analyse_visible_records"]
EventType = Literal[
    "run.accepted",
    "command.dispatched",
    "agent.started",
    "agent.progressed",
    "agent.completed",
    "agent.degraded",
    "agent.failed",
    "run.waiting_approval",
    "run.cancelled",
    "run.timed_out",
    "run.completed",
]
RuntimeStatus = Literal[
    "accepted",
    "queued",
    "running",
    "completed",
    "degraded",
    "failed",
    "waiting_approval",
    "cancelled",
    "timed_out",
]


class _StrictRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AgentCommandEnvelope(_StrictRuntimeModel):
    schema_version: Literal["agent-command.v1"] = "agent-command.v1"
    command_id: UUID
    run_id: UUID
    parent_command_id: UUID | None = None
    causation_id: UUID
    correlation_id: UUID
    sequence: int = Field(ge=1)
    target_capability: Capability
    command_type: CommandType
    scope_proof_ref: ScopeProofRef
    input_artifact_refs: tuple[UUID, ...] = Field(max_length=16)
    deadline_at: datetime
    idempotency_key_hash: Sha256


class AgentEventEnvelope(_StrictRuntimeModel):
    schema_version: Literal["agent-event.v1"] = "agent-event.v1"
    event_id: UUID
    run_id: UUID
    command_id: UUID | None = None
    causation_id: UUID
    correlation_id: UUID
    sequence: int = Field(ge=1)
    event_type: EventType
    status: RuntimeStatus
    source_role: Literal["supervisor", "specialist"]
    source_capability: Capability | None = None
    safe_summary: str | None = Field(default=None, max_length=240)
    artifact_ref: UUID | None = None
    metrics: dict[str, int] = Field(default_factory=dict)
    occurred_at: datetime

    @model_validator(mode="after")
    def validate_source_authority(self) -> "AgentEventEnvelope":
        if self.source_role == "specialist" and self.event_type.startswith("run."):
            raise ValueError("specialist_run_event_forbidden")
        if self.source_role == "specialist" and self.source_capability is None:
            raise ValueError("specialist_capability_required")
        if self.source_role == "supervisor" and self.source_capability is not None:
            raise ValueError("supervisor_capability_forbidden")
        return self


class RunCheckpointControl(_StrictRuntimeModel):
    completed_command_ids: tuple[UUID, ...] = Field(max_length=64)
    pending_command_ids: tuple[UUID, ...] = Field(max_length=64)
    retry_count: int = Field(ge=0, le=8)
    next_action: Literal[
        "dispatch",
        "wait_children",
        "fan_in",
        "finalize",
        "stop",
    ]


class AgentRunCreateRequest(_StrictRuntimeModel):
    # HTTP JSON represents UUID values as strings.  The durable command/event
    # protocols remain strict; only this public transport boundary performs
    # JSON-native UUID parsing.
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    workspace_id: UUID
    employee_id: UUID
    intent: Literal["business_fact", "memory_lookup", "mixed", "general_advice"]
    query: str = Field(min_length=1, max_length=600)
    requested_action: Literal["read_only"] = "read_only"
    target_record_id: UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)
    skill_id: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_text_boundaries(self) -> "AgentRunCreateRequest":
        bounded = (self.idempotency_key, self.skill_id)
        if any(
            value is not None
            and (value != value.strip() or "\x00" in value or "\r" in value or "\n" in value)
            for value in bounded
        ):
            raise ValueError("agent_run_request_invalid")
        if self.query != self.query.strip() or "\x00" in self.query:
            raise ValueError("agent_run_request_invalid")
        return self


class AgentRunCreateResponse(_StrictRuntimeModel):
    run_id: UUID
    status: RuntimeStatus
    replayed: bool


class AgentPrivateInputPayload(_StrictRuntimeModel):
    schema_version: Literal["agent-private-input.v1"] = "agent-private-input.v1"
    actor_user_id: str = Field(min_length=1, max_length=128)
    workspace_id: UUID
    employee_id: UUID
    intent: Literal["business_fact", "memory_lookup", "mixed", "general_advice"]
    query: str = Field(min_length=1, max_length=600)
    target_record_id: UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)
    skill_id: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_private_text(self) -> "AgentPrivateInputPayload":
        if (
            self.actor_user_id != self.actor_user_id.strip()
            or self.query != self.query.strip()
            or self.idempotency_key != self.idempotency_key.strip()
            or any("\x00" in value for value in (self.actor_user_id, self.query, self.idempotency_key))
            or (
                self.skill_id is not None
                and (
                    self.skill_id != self.skill_id.strip()
                    or "\x00" in self.skill_id
                    or "\r" in self.skill_id
                    or "\n" in self.skill_id
                )
            )
        ):
            raise ValueError("agent_private_input_invalid")
        return self


class _SafeRunStreamBase(_StrictRuntimeModel):
    run_id: UUID
    event_id: UUID
    sequence: int = Field(ge=1)


class SafeRunStatusEvent(_SafeRunStreamBase):
    event: Literal["status"]
    phase: Literal["accepted", "queued", "running", "waiting_approval"]
    message: str = Field(min_length=1, max_length=240)


class SafeRunArtifactReadyEvent(_SafeRunStreamBase):
    event: Literal["artifact_ready"]
    artifact_ref: UUID
    label: str = Field(min_length=1, max_length=120)


class SafeRunResultEvent(_SafeRunStreamBase):
    event: Literal["result"]
    artifact_ref: UUID
    safe_view: AssistantQuerySafeView


class SafeRunErrorEvent(_SafeRunStreamBase):
    event: Literal["error"]
    code: Literal[
        "agent_degraded",
        "agent_failed",
        "run_cancelled",
        "run_timed_out",
        "scope_revoked",
    ]
    message: str = Field(min_length=1, max_length=200)


class SafeRunDoneEvent(_SafeRunStreamBase):
    event: Literal["done"]
    status: Literal["completed", "degraded", "failed", "cancelled", "timed_out"]


SafeRunStreamEvent = Annotated[
    SafeRunStatusEvent
    | SafeRunArtifactReadyEvent
    | SafeRunResultEvent
    | SafeRunErrorEvent
    | SafeRunDoneEvent,
    Field(discriminator="event"),
]


__all__ = [
    "AgentCommandEnvelope",
    "AgentEventEnvelope",
    "AgentPrivateInputPayload",
    "AgentRunCreateRequest",
    "AgentRunCreateResponse",
    "RunCheckpointControl",
    "SafeRunArtifactReadyEvent",
    "SafeRunDoneEvent",
    "SafeRunErrorEvent",
    "SafeRunResultEvent",
    "SafeRunStatusEvent",
    "SafeRunStreamEvent",
]
