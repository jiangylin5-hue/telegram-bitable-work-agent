from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
)

from app.runtime.stage08_collaboration_contracts import AssistantQuerySafeView


class AssistantQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    workspace_id: StrictStr = Field(min_length=1, max_length=120)
    employee_id: StrictStr = Field(min_length=1, max_length=120)
    intent: Literal["business_fact", "memory_lookup", "mixed", "general_advice"]
    query: StrictStr = Field(min_length=1, max_length=600)
    requested_action: Literal["read_only", "draft_update"]
    target_record_id: StrictStr | None = Field(default=None, min_length=1, max_length=120)
    idempotency_key: StrictStr = Field(min_length=1, max_length=128)
    skill_id: StrictStr | None = Field(default=None, min_length=1, max_length=120)

    @field_validator(
        "workspace_id",
        "employee_id",
        "target_record_id",
        "idempotency_key",
        "skill_id",
    )
    @classmethod
    def validate_bounded_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if (
            value != value.strip()
            or "\x00" in value
            or "\r" in value
            or "\n" in value
        ):
            raise ValueError("stage08_collaboration_request_invalid")
        return value

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if value != value.strip() or "\x00" in value:
            raise ValueError("stage08_collaboration_request_invalid")
        return value


AssistantQueryResponse = AssistantQuerySafeView


AssistantSkillDisabledReason = Literal[
    "context_required",
    "read_scope_unavailable",
    "write_scope_unavailable",
    "chat_scope_unavailable",
    "runtime_unsupported",
]


class AssistantSkillCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    skill_id: StrictStr = Field(min_length=1, max_length=120)
    label: StrictStr = Field(min_length=1, max_length=120)
    description: StrictStr = Field(min_length=1, max_length=300)
    enabled: bool
    disabled_reason: AssistantSkillDisabledReason | None
    supported_intents: tuple[Literal["business_fact", "mixed"], ...]
    supported_actions: tuple[Literal["read_only", "draft_update"], ...]
    confirmation_policy: Literal["read_only", "draft_required_for_write"]


class AssistantSkillCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    manifest_version: Literal["stage06-larksuite-skills-v1"]
    default_selection: Literal["auto"]
    skills: tuple[AssistantSkillCatalogItem, ...]

AssistantStreamPhase = Literal[
    "authorizing",
    "planning_context",
    "analysing",
    "creating_draft",
    "completed",
]


class _AssistantStreamEventBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    sequence: StrictInt = Field(ge=1)
    request_id: StrictStr = Field(min_length=1, max_length=64)


class AssistantStreamStatus(_AssistantStreamEventBase):
    event: Literal["status"]
    phase: AssistantStreamPhase


class AssistantStreamAnswerDelta(_AssistantStreamEventBase):
    event: Literal["answer_delta"]
    text: StrictStr = Field(min_length=1, max_length=512)


class AssistantStreamResult(_AssistantStreamEventBase):
    event: Literal["result"]
    safe_view: AssistantQuerySafeView


class AssistantStreamError(_AssistantStreamEventBase):
    event: Literal["error"]
    code: StrictStr = Field(min_length=1, max_length=120)
    message: StrictStr = Field(min_length=1, max_length=200)


class AssistantStreamDone(_AssistantStreamEventBase):
    event: Literal["done"]


AssistantStreamEvent = Annotated[
    AssistantStreamStatus
    | AssistantStreamAnswerDelta
    | AssistantStreamResult
    | AssistantStreamError
    | AssistantStreamDone,
    Field(discriminator="event"),
]


__all__ = [
    "AssistantQueryRequest",
    "AssistantQueryResponse",
    "AssistantSkillCatalogItem",
    "AssistantSkillCatalogResponse",
    "AssistantSkillDisabledReason",
    "AssistantStreamAnswerDelta",
    "AssistantStreamDone",
    "AssistantStreamError",
    "AssistantStreamEvent",
    "AssistantStreamPhase",
    "AssistantStreamResult",
    "AssistantStreamStatus",
]
