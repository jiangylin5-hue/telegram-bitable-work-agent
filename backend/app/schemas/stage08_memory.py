from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictInt


class MemoryListItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    memory_type: Literal[
        "decision",
        "preference",
        "risk",
        "customer_fact",
        "project_fact",
    ]
    status: Literal["active"]
    version: StrictInt = Field(ge=1)
    payload: dict[str, JsonValue]
    valid_until: datetime | None = None


class MemoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[MemoryListItemResponse]


class MemoryCandidateRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_version: StrictInt = Field(ge=1)


class MemoryCandidateRevokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_status: Literal["rejected", "accepted", "expired"]
    candidate_version: StrictInt = Field(ge=1)
    memory_status: Literal["revoked"] | None = None
