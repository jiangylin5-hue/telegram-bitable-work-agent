from typing import Any

from pydantic import BaseModel, Field


class CreateWorkspaceRequest(BaseModel):
    name: str
    owner_user_id: str


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    owner_user_id: str
    status: str


class WorkspaceMemberResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: str
    status: str


class WorkspaceMemberListResponse(BaseModel):
    members: list[WorkspaceMemberResponse]


class MiniAppIdentityResponse(BaseModel):
    user_id: str
    source: str


class MiniAppWorkspaceCapabilitiesResponse(BaseModel):
    can_read_bases: bool
    can_manage_workspace: bool
    can_manage_schema: bool
    can_review_drafts: bool


class MiniAppWorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    role: str
    capabilities: MiniAppWorkspaceCapabilitiesResponse


class MiniAppBootstrapResponse(BaseModel):
    identity: MiniAppIdentityResponse
    workspaces: list[MiniAppWorkspaceResponse]


class MiniAppBaseSummaryResponse(BaseModel):
    id: str
    name: str
    source_type: str


class MiniAppQueueDestinationResponse(BaseModel):
    base_id: str
    draft_id: str


class MiniAppQueueActionAvailabilityResponse(BaseModel):
    can_confirm: bool
    can_reject: bool


class MiniAppQueueItemResponse(BaseModel):
    id: str
    kind: str
    title: str
    status: str
    destination: MiniAppQueueDestinationResponse
    action_availability: MiniAppQueueActionAvailabilityResponse


class MiniAppWorkspaceHomeResponse(BaseModel):
    workspace_id: str
    recent_bases: list[MiniAppBaseSummaryResponse]
    queue: list[MiniAppQueueItemResponse]


class CreateBaseRequest(BaseModel):
    name: str
    description: str | None = None


class BaseResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None = None
    source_type: str
    status: str


class BaseSummaryResponse(BaseModel):
    id: str
    name: str
    source_type: str
    status: str


class BaseListResponse(BaseModel):
    bases: list[BaseSummaryResponse]


class CreateTableRequest(BaseModel):
    name: str
    key: str


class TableResponse(BaseModel):
    id: str
    base_id: str
    name: str
    key: str
    status: str


class TableListResponse(BaseModel):
    tables: list[TableResponse]


class CreateFieldRequest(BaseModel):
    name: str
    key: str
    field_type: str
    required: bool = False
    options: dict[str, Any] = Field(default_factory=dict)
    permission_policy: dict[str, Any] = Field(default_factory=dict)


class FieldResponse(BaseModel):
    id: str
    table_id: str
    name: str
    key: str
    field_type: str
    required: bool
    options: dict[str, Any]
    permission_policy: dict[str, Any]
    order_index: int


class CreateRecordRequest(BaseModel):
    values: dict[str, Any]


class UpdateRecordRequest(BaseModel):
    values: dict[str, Any]
    expected_version: int = Field(ge=1)


class RecordResponse(BaseModel):
    id: str
    table_id: str
    values: dict[str, Any]
    record_status: str
    version: int


class TableSchemaResponse(BaseModel):
    table: dict[str, Any]
    fields: list[dict[str, Any]]


class CreateViewRequest(BaseModel):
    table_id: str
    name: str
    view_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    permission_policy: dict[str, Any] = Field(default_factory=dict)


class ViewResponse(BaseModel):
    id: str
    base_id: str
    table_id: str | None = None
    name: str
    view_type: str
    config: dict[str, Any]
    permission_policy: dict[str, Any]
    status: str


class ViewSummaryResponse(BaseModel):
    id: str
    base_id: str
    table_id: str | None = None
    name: str
    view_type: str
    status: str


class ViewListResponse(BaseModel):
    views: list[ViewSummaryResponse]


class ViewRecordsResponse(BaseModel):
    view_id: str
    records: list[dict[str, Any]]
    trace_id: str
    next_cursor: str | None = None
    has_more: bool = False
