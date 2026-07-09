from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateDigitalEmployeeRequest(BaseModel):
    name: str
    description: str
    telegram_alias: str | None = None
    accessible_tables: list[str] = Field(default_factory=list)
    accessible_views: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    field_policy: dict[str, Any] = Field(default_factory=dict)
    confirmation_policy: dict[str, Any] = Field(default_factory=dict)
    response_style: dict[str, Any] = Field(default_factory=dict)


class DigitalEmployeeResponse(BaseModel):
    id: str
    workspace_id: str
    base_id: str
    name: str
    description: str
    telegram_alias: str | None = None
    accessible_tables: list[str]
    accessible_views: list[str]
    allowed_actions: list[str]
    status: str


class UpdateDigitalEmployeeRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    telegram_alias: str | None = None
    accessible_tables: list[str] | None = None
    accessible_views: list[str] | None = None
    allowed_actions: list[str] | None = None
    field_policy: dict[str, Any] | None = None
    confirmation_policy: dict[str, Any] | None = None
    response_style: dict[str, Any] | None = None
    status: str | None = None


class InvokeDigitalEmployeeRequest(BaseModel):
    action: str
    view_id: str | None = None
    table_id: str | None = None
    record_id: str | None = None
    proposed_values: dict[str, Any] | None = None
    runtime_mode: str = "deterministic"
    prompt: str | None = None


class InvokeDigitalEmployeeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: str
    employee_id: str | None = None
    view_id: str | None = None
    record_count: int | None = None
    records: list[dict[str, Any]] | None = None
    draft_id: str | None = None
    status: str | None = None
    record_id: str | None = None
    base_id: str | None = None
    telegram_chat_id: str | None = None
    answer: str | None = None
    citations: list[dict[str, Any]] | None = None
    runtime: dict[str, Any] | None = None
    skill_evidence: dict[str, Any] | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")


class RecordChangeDraftResponse(BaseModel):
    id: str
    workspace_id: str
    base_id: str
    table_id: str
    record_id: str | None = None
    draft_type: str
    proposed_values: dict[str, Any]
    before_values: dict[str, Any] | None = None
    created_by_type: str
    created_by_id: str
    status: str
    trace_id: str
    expected_version: int


class RecordChangeDraftListResponse(BaseModel):
    drafts: list[RecordChangeDraftResponse]


class BindTelegramContextRequest(BaseModel):
    workspace_member_id: str
    telegram_chat_id: str
    telegram_user_id: str
    binding_type: str = "chat_user"
    default_base_id: str | None = None
    default_digital_employee_id: str | None = None
    scope_policy: dict[str, Any] = Field(default_factory=dict)


class TelegramBindingResponse(BaseModel):
    id: str
    workspace_id: str
    workspace_member_id: str
    telegram_chat_id: str | None = None
    telegram_user_id: str | None = None
    binding_type: str
    default_base_id: str | None = None
    default_digital_employee_id: str | None = None
    scope_policy: dict[str, Any]
    status: str


class TelegramMentionRequest(BaseModel):
    telegram_chat_id: str
    telegram_user_id: str
    alias: str
    text: str


class CreateNotificationRequest(BaseModel):
    workspace_id: str
    base_id: str | None = None
    source_record_id: str | None = None
    channel: str
    target: dict[str, Any]
    message_payload: dict[str, Any]
    send_policy: dict[str, Any] = Field(default_factory=dict)


class NotificationRequestResponse(BaseModel):
    id: str
    workspace_id: str
    base_id: str | None = None
    source_record_id: str | None = None
    channel: str
    target: dict[str, Any]
    message_payload: dict[str, Any]
    send_policy: dict[str, Any]
    status: str
    trace_id: str


class NotificationRequestListResponse(BaseModel):
    requests: list[NotificationRequestResponse]


class AuditEventResponse(BaseModel):
    id: str
    trace_id: str
    actor_type: str
    actor_id: str
    event_type: str
    entity_type: str
    entity_id: str | None = None
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    permission_snapshot: dict[str, Any] | None = None


class AuditEventListResponse(BaseModel):
    events: list[AuditEventResponse]
