"""Strict contracts for the isolated Stage12 deployed answer runtime."""

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

from app.schemas.agent_specialist_results import ObjectiveSpecialistInputV1


Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
TypedArtifactOwnerRef = Annotated[
    str,
    StringConstraints(
        pattern=(
            r"^stage08-idempotency:[0-9a-f]{8}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        ),
        max_length=57,
    ),
]
PrivateInputRef = Annotated[
    str,
    StringConstraints(
        pattern=(
            r"^agent-private-input:[0-9a-f]{8}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        ),
        max_length=56,
    ),
]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Stage12RuntimeAdmissionRequest(_StrictFrozenModel):
    run_id: UUID
    actor_user_id: NonEmptyStr = Field(max_length=128)
    workspace_id: UUID
    digital_employee_id: UUID
    intent: Literal["business_fact", "memory_lookup", "mixed", "general_advice"]
    query: NonEmptyStr = Field(max_length=600)
    target_record_id: UUID | None
    idempotency_key: NonEmptyStr = Field(max_length=128)
    skill_id: NonEmptyStr | None = Field(default=None, max_length=120)
    authorization_hash: Sha256
    deadline_at: datetime

    @model_validator(mode="after")
    def validate_request(self) -> "Stage12RuntimeAdmissionRequest":
        if (
            self.deadline_at.tzinfo is None
            or self.deadline_at.utcoffset() is None
            or self.deadline_at.utcoffset().total_seconds() != 0
        ):
            raise ValueError("stage12_admission_utc_required")
        if (
            self.actor_user_id != self.actor_user_id.strip()
            or self.query != self.query.strip()
            or self.idempotency_key != self.idempotency_key.strip()
            or "\x00" in self.actor_user_id
            or "\x00" in self.query
            or "\x00" in self.idempotency_key
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
            raise ValueError("stage12_admission_text_invalid")
        return self


class Stage12ObjectiveDispatchV1(_StrictFrozenModel):
    objective: ObjectiveSpecialistInputV1
    objective_artifact_id: UUID
    dependency_artifact_ids: tuple[UUID, ...] = Field(max_length=16)
    private_input_ref: PrivateInputRef

    @model_validator(mode="after")
    def validate_dispatch(self) -> "Stage12ObjectiveDispatchV1":
        if self.objective_artifact_id in self.dependency_artifact_ids:
            raise ValueError("stage12_objective_owner_dependency_conflict")
        if self.dependency_artifact_ids != self.objective.input_artifact_refs:
            raise ValueError("stage12_objective_dependency_mismatch")
        return self


class Stage12RuntimeAdmissionResult(_StrictFrozenModel):
    task_spec_ref: TypedArtifactOwnerRef
    schema_ref: TypedArtifactOwnerRef
    objective_dispatches: tuple[Stage12ObjectiveDispatchV1, ...] = Field(
        min_length=1,
        max_length=16,
    )
    data_version_hash: Sha256

    @model_validator(mode="after")
    def validate_dispatches(self) -> "Stage12RuntimeAdmissionResult":
        objective_ids = tuple(
            item.objective.objective_id for item in self.objective_dispatches
        )
        owner_ids = tuple(
            item.objective_artifact_id for item in self.objective_dispatches
        )
        if len(set(objective_ids)) != len(objective_ids):
            raise ValueError("stage12_dispatch_objective_duplicate")
        if len(set(owner_ids)) != len(owner_ids):
            raise ValueError("stage12_dispatch_owner_duplicate")
        return self


class Stage12IsolatedWorkspaceContext(_StrictFrozenModel):
    workspace_id: UUID
    base_id: UUID
    table_ids: dict[str, UUID] = Field(min_length=1, max_length=16)
    actor_user_id: NonEmptyStr = Field(max_length=128)
    digital_employee_id: UUID


__all__ = [
    "Stage12IsolatedWorkspaceContext",
    "Stage12ObjectiveDispatchV1",
    "Stage12RuntimeAdmissionRequest",
    "Stage12RuntimeAdmissionResult",
]
