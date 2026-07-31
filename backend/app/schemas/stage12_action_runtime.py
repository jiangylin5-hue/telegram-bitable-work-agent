from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictInt,
    model_validator,
)

from app.schemas.agent_specialist_results import specialist_payload_sha256
from app.schemas.agent_task_spec_v2 import ActionKindV1, TaskSpecV2


ObjectiveRuntimeStatus = Literal[
    "queued",
    "running",
    "completed",
    "proposed",
    "denied",
    "degraded",
    "failed",
    "cancelled",
]
ActionRuntimeStatus = Literal[
    "queued",
    "running",
    "proposed",
    "pending_confirmation",
    "confirmed",
    "executed",
    "denied",
    "degraded",
    "failed",
    "rejected",
    "conflicted",
    "cancelled",
    "expired",
]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ObjectiveRunCreateV1(_StrictFrozenModel):
    objective_key: str = Field(min_length=1, max_length=80)
    kind: str = Field(min_length=1, max_length=40)
    required: StrictBool
    dependency_keys: tuple[str, ...] = Field(max_length=32)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ObjectiveRunCreateV1":
        if len(set(self.dependency_keys)) != len(self.dependency_keys):
            raise ValueError("objective_dependency_duplicate")
        if self.objective_key in self.dependency_keys:
            raise ValueError("objective_self_dependency")
        if any(
            not value or value != value.strip() or len(value) > 80 or "\x00" in value
            for value in (self.objective_key, self.kind, *self.dependency_keys)
        ):
            raise ValueError("objective_control_value_invalid")
        return self


class EditableActionFieldV1(_StrictFrozenModel):
    field_id: UUID
    field_key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    field_type: str = Field(min_length=1, max_length=40)
    required: StrictBool


class ActionSlotControlV1(_StrictFrozenModel):
    schema_version: Literal["stage12-action-control.v1"] = "stage12-action-control.v1"
    action_kind: ActionKindV1
    confirmation_policy: Literal["required"]
    dependency_keys: tuple[str, ...] = Field(max_length=32)
    evidence_refs: tuple[str, ...] = Field(max_length=32)
    editable_fields: tuple[EditableActionFieldV1, ...] = Field(max_length=64)
    safe_summary: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_control(self) -> "ActionSlotControlV1":
        if len(set(self.dependency_keys)) != len(self.dependency_keys):
            raise ValueError("action_dependency_duplicate")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("action_evidence_duplicate")
        field_ids = tuple(item.field_id for item in self.editable_fields)
        field_keys = tuple(item.field_key for item in self.editable_fields)
        if len(set(field_ids)) != len(field_ids) or len(set(field_keys)) != len(
            field_keys
        ):
            raise ValueError("action_editable_field_duplicate")
        if (
            self.safe_summary != self.safe_summary.strip()
            or "\x00" in self.safe_summary
        ):
            raise ValueError("action_safe_summary_invalid")
        return self


class PrivateActionAssignmentV1(_StrictFrozenModel):
    record_id: UUID | None
    field_id: UUID
    value: JsonValue


class PrivateRecordVersionV1(_StrictFrozenModel):
    table_id: UUID
    record_id: UUID
    record_version: StrictInt = Field(ge=1)


class ActionPrivatePayloadV1(_StrictFrozenModel):
    schema_version: Literal["stage12-action-private.v1"] = "stage12-action-private.v1"
    actor_user_id: str = Field(min_length=1, max_length=128)
    objective_key: str = Field(min_length=1, max_length=80)
    slot_key: str = Field(min_length=1, max_length=80)
    action_kind: ActionKindV1
    field_policy_version: Literal["stage12-field-policy.v2"] | None = None
    field_policy_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    candidate_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_table_id: UUID | None
    target_record_ids: tuple[UUID, ...] = Field(max_length=200)
    assignments: tuple[PrivateActionAssignmentV1, ...] = Field(max_length=256)
    record_versions: tuple[PrivateRecordVersionV1, ...] = Field(max_length=200)
    evidence_ids: tuple[str, ...] = Field(max_length=32)
    reminder_target: dict[str, JsonValue] | None = None
    reminder_message_payload: dict[str, JsonValue] | None = None
    expires_at: datetime

    @model_validator(mode="after")
    def validate_private_payload(self) -> "ActionPrivatePayloadV1":
        if (self.field_policy_version is None) != (self.field_policy_hash is None):
            raise ValueError("action_private_field_policy_proof_invalid")
        if (
            self.actor_user_id != self.actor_user_id.strip()
            or "\x00" in self.actor_user_id
        ):
            raise ValueError("action_private_actor_invalid")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("action_private_expiry_timezone_required")
        if len(set(self.target_record_ids)) != len(self.target_record_ids):
            raise ValueError("action_private_target_duplicate")
        version_ids = tuple(item.record_id for item in self.record_versions)
        if len(set(version_ids)) != len(version_ids):
            raise ValueError("action_private_version_duplicate")
        assignment_keys = tuple(
            (item.record_id, item.field_id) for item in self.assignments
        )
        if len(set(assignment_keys)) != len(assignment_keys):
            raise ValueError("action_private_assignment_duplicate")
        reminder = self.action_kind == "reminder.request"
        if reminder != (
            self.reminder_target is not None
            and self.reminder_message_payload is not None
        ):
            raise ValueError("action_private_reminder_payload_invalid")
        return self


class DurableActionCandidateV1(_StrictFrozenModel):
    table_id: UUID
    record_id: UUID
    record_version: StrictInt = Field(ge=1)
    writable_field_ids: tuple[UUID, ...]


class DurableAuthorizedCandidateSetV1(_StrictFrozenModel):
    version: Literal["stage12-authorized-candidates.v1"] = (
        "stage12-authorized-candidates.v1"
    )
    objective_key: str = Field(min_length=1, max_length=80)
    slot_key: str = Field(min_length=1, max_length=80)
    action_kind: ActionKindV1
    status: Literal["resolved", "denied"]
    target_table_ids: tuple[UUID, ...] = Field(max_length=16)
    candidates: tuple[DurableActionCandidateV1, ...] = Field(max_length=200)
    assignment_field_ids: tuple[UUID, ...] = Field(max_length=64)
    scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    complete: StrictBool
    denial_reason: str | None = Field(default=None, max_length=120)
    candidate_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_candidate_set(self) -> "DurableAuthorizedCandidateSetV1":
        if len(set(self.target_table_ids)) != len(self.target_table_ids):
            raise ValueError("action_candidate_table_duplicate")
        identities = tuple(item.record_id for item in self.candidates)
        if len(set(identities)) != len(identities):
            raise ValueError("action_candidate_record_duplicate")
        if self.status == "resolved":
            if not self.complete or not self.target_table_ids or self.denial_reason:
                raise ValueError("action_candidate_resolution_invalid")
            if (
                self.action_kind in {"record.update", "reminder.request"}
                and not self.candidates
            ):
                raise ValueError("action_candidate_record_required")
        elif self.candidates or self.denial_reason is None:
            raise ValueError("action_candidate_denial_invalid")
        expected = action_candidate_sha256(
            self.model_dump(mode="json", exclude={"candidate_set_hash"})
        )
        if self.candidate_set_hash != expected:
            raise ValueError("action_candidate_hash_mismatch")
        return self


class DurableTaskSpecV2(_StrictFrozenModel):
    version: Literal["stage12-task-spec-owner.v1"] = "stage12-task-spec-owner.v1"
    task_spec: TaskSpecV2
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_content_hash(self) -> "DurableTaskSpecV2":
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("stage12_task_spec_owner_hash_mismatch")
        return self


def action_candidate_sha256(value: dict[str, object]) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class ActionConfirmRequestV1(_StrictFrozenModel):
    # Public JSON transport parses UUID/scalars normally but still rejects extras.
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    proposal_version: int = Field(ge=1)
    record_version: int | None = Field(default=None, ge=1)
    proposed_values: dict[str, JsonValue] = Field(default_factory=dict, max_length=64)


class ActionRejectRequestV1(_StrictFrozenModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    proposal_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=240)


class SafeObjectiveRunV1(_StrictFrozenModel):
    objective_id: UUID
    objective_key: str
    kind: str
    required: StrictBool
    status: ObjectiveRuntimeStatus
    safe_summary: str | None = Field(default=None, max_length=240)
    error_code: str | None = Field(default=None, max_length=120)


class SafeObjectiveListV1(_StrictFrozenModel):
    run_id: UUID
    objectives: tuple[SafeObjectiveRunV1, ...]


class SafeActionSlotV1(_StrictFrozenModel):
    slot_id: UUID
    objective_id: UUID
    slot_key: str
    action_kind: ActionKindV1
    status: ActionRuntimeStatus
    proposal_version: StrictInt = Field(ge=1)
    record_version: StrictInt | None = Field(default=None, ge=1)
    safe_summary: str = Field(min_length=1, max_length=240)
    editable_fields: tuple[EditableActionFieldV1, ...]
    proposed_values: dict[str, JsonValue]
    confirmation_required: Literal[True] = True
    execution_ticket_id: UUID | None
    resource_id: UUID | None


class SafeActionListV1(_StrictFrozenModel):
    run_id: UUID
    actions: tuple[SafeActionSlotV1, ...]


class SafeEvidenceV1(_StrictFrozenModel):
    evidence_id: UUID
    kind: str = Field(min_length=1, max_length=60)
    validation_status: str = Field(min_length=1, max_length=32)
    safe_summary: str | None = Field(default=None, max_length=240)


class ActionTerminalReceiptV1(_StrictFrozenModel):
    slot_id: UUID
    status: ActionRuntimeStatus
    proposal_version: StrictInt = Field(ge=1)
    execution_ticket_id: UUID | None
    resource_id: UUID | None
    replayed: StrictBool


__all__ = [
    "ActionConfirmRequestV1",
    "ActionPrivatePayloadV1",
    "ActionRejectRequestV1",
    "ActionRuntimeStatus",
    "ActionSlotControlV1",
    "DurableActionCandidateV1",
    "DurableAuthorizedCandidateSetV1",
    "DurableTaskSpecV2",
    "EditableActionFieldV1",
    "ObjectiveRunCreateV1",
    "ObjectiveRuntimeStatus",
    "SafeActionListV1",
    "SafeActionSlotV1",
    "SafeEvidenceV1",
    "SafeObjectiveListV1",
    "SafeObjectiveRunV1",
    "ActionTerminalReceiptV1",
    "action_candidate_sha256",
]
