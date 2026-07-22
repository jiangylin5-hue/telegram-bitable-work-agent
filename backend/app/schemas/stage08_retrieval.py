from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class KnowledgeReindexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    workspace_id: StrictStr = Field(min_length=1, max_length=120)
    knowledge_source_id: StrictStr = Field(min_length=1, max_length=120)
    idempotency_key: StrictStr = Field(min_length=1, max_length=160)
    trace_id: StrictStr = Field(min_length=1, max_length=120)

    @field_validator("idempotency_key", "trace_id")
    @classmethod
    def validate_reference_text(cls, value: str) -> str:
        if value != value.strip() or "\r" in value or "\n" in value:
            raise ValueError("invalid_reference_text")
        return value


class KnowledgeReindexResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ticket_id: StrictStr
    status: Literal["accepted"]
