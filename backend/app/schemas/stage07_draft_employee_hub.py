from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


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


class SafeDraftSummaryResponse(BaseModel):
    id: str
    base_id: str
    table_id: str
    record_id: str | None
    draft_type: str
    status: str
    version: int


class SafeDraftPageResponse(BaseModel):
    base_id: str
    drafts: list[SafeDraftSummaryResponse]
    next_cursor: str | None = None
    has_more: bool = False


class SafeDraftFieldResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    field_type: str
    before_value: str | int | float | bool | None = None
    proposed_value: str | int | float | bool | None = None


class SafeDraftActionsResponse(BaseModel):
    can_confirm: bool
    can_reject: bool


class SafeDraftDetailResponse(BaseModel):
    id: str
    base_id: str
    table_id: str
    record_id: str | None
    draft_type: str
    status: str
    version: int
    fields: list[SafeDraftFieldResponse]
    actions: SafeDraftActionsResponse
    terminal_audit_event_id: str | None


class SafeDraftTerminalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int


class SafeDraftTerminalReceipt(BaseModel):
    id: str
    status: str
    version: int
    terminal_audit_event_id: str
