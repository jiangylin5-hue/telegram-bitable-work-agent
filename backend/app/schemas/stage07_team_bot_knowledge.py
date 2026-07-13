from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TeamBotContactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    base_id: str
    name: str
    description: str
    available_intents: list[Literal["summarize"]]


class TeamBotContactPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    contacts: list[TeamBotContactResponse]
    next_cursor: str | None = None
    has_more: bool = False


class TeamBotEmployeeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    base_id: str


class TeamBotKnowledgeContextViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    view_type: Literal["grid", "kanban", "calendar", "form"]


class TeamBotKnowledgeContextPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee: TeamBotEmployeeResponse
    views: list[TeamBotKnowledgeContextViewResponse]
    next_cursor: str | None = None
    has_more: bool = False


class TeamBotSelectedViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    view_type: Literal["grid", "kanban", "calendar", "form"]
    base_id: str


class TeamBotSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_id: str
    view_id: str
    instruction: str | None = Field(default=None, max_length=600)


class TeamBotCitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str


class TeamBotSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["summary", "empty_context"]
    employee_id: str
    base_id: str
    view_id: str
    answer: str
    citations: list[TeamBotCitationResponse] = Field(default_factory=list)
    knowledge_window_truncated: bool
    audit_event_id: str

