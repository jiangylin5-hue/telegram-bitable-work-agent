from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _ControlledProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    proposal_id: UUID
    reason: str = Field(min_length=1, max_length=500)
    source_artifact_refs: tuple[UUID, ...] = Field(default=(), max_length=16)
    requires_confirmation: Literal[True] = True

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        if value != value.strip() or "\x00" in value:
            raise ValueError("controlled_action_reason_invalid")
        return value


class CreateRecordProposal(_ControlledProposal):
    action_type: Literal["create_record"]
    table_id: UUID
    proposed_values: dict[str, Any] = Field(min_length=1, max_length=64)


class UpdateRecordProposal(_ControlledProposal):
    action_type: Literal["update_record"]
    record_id: UUID
    expected_version: int = Field(ge=1)
    proposed_values: dict[str, Any] = Field(min_length=1, max_length=64)


class CreateTaskProposal(_ControlledProposal):
    action_type: Literal["create_task"]
    table_id: UUID
    proposed_values: dict[str, Any] = Field(min_length=1, max_length=64)


class ReminderRequestProposal(_ControlledProposal):
    action_type: Literal["request_reminder"]
    base_id: UUID | None = None
    source_record_id: UUID | None = None
    channel: Literal["telegram"] = "telegram"
    target: dict[str, Any]
    message_payload: dict[str, Any]
    send_policy: dict[str, Any] = Field(default_factory=dict)


ControlledActionProposal = Annotated[
    CreateRecordProposal
    | UpdateRecordProposal
    | CreateTaskProposal
    | ReminderRequestProposal,
    Field(discriminator="action_type"),
]


__all__ = [
    "ControlledActionProposal",
    "CreateRecordProposal",
    "CreateTaskProposal",
    "ReminderRequestProposal",
    "UpdateRecordProposal",
]
