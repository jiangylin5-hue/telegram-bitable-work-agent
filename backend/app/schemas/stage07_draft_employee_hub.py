from typing import Literal

from pydantic import BaseModel


class DigitalEmployeeContactResponse(BaseModel):
    id: str
    base_id: str
    name: str
    description: str
    status: Literal["active"]
    available_intents: list[Literal["summarize", "draft_update"]]


class DigitalEmployeeContactPageResponse(BaseModel):
    workspace_id: str
    contacts: list[DigitalEmployeeContactResponse]
    next_cursor: str | None = None
    has_more: bool = False
