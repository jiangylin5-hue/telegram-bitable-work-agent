from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TelegramDeepLinkKind = Literal["base", "view", "record", "record_change_draft"]


class TelegramDeepLinkResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_param: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class SafeTelegramDeepLinkDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TelegramDeepLinkKind
    workspace_id: str
    base_id: str | None = None
    table_id: str | None = None
    view_id: str | None = None
    record_id: str | None = None
    draft_id: str | None = None


class TelegramDeepLinkResolveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["resolved", "recovery"]
    destination: SafeTelegramDeepLinkDestination | None = None
