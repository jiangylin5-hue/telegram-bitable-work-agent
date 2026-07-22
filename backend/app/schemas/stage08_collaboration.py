from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

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

    @field_validator(
        "workspace_id",
        "employee_id",
        "target_record_id",
        "idempotency_key",
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


__all__ = [
    "AssistantQueryRequest",
    "AssistantQueryResponse",
]
