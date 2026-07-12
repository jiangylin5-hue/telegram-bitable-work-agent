from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


ManagedEmployeeStatus = Literal["draft", "active", "paused"]
ManagedEmployeeAccessMode = Literal["workspace", "assigned"]
ManagedEmployeeAction = Literal["summarize", "draft_update"]
ManagedEmployeeViewType = Literal["grid", "kanban", "calendar", "form"]
ManagedEmployeeRole = Literal["owner", "admin", "builder", "operator", "viewer"]


class _ManagedEmployeeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManagedEmployeeSummaryResponse(_ManagedEmployeeModel):
    id: str
    name: str
    description: str
    status: ManagedEmployeeStatus
    access_mode: ManagedEmployeeAccessMode
    table_count: StrictInt = Field(ge=0)
    view_count: StrictInt = Field(ge=0)
    member_count: StrictInt = Field(ge=0)
    version: StrictInt = Field(ge=1)


class ManagedEmployeeDetailResponse(ManagedEmployeeSummaryResponse):
    base_id: str
    telegram_alias: str | None
    accessible_table_ids: list[str]
    accessible_view_ids: list[str]
    allowed_actions: list[ManagedEmployeeAction]
    member_ids: list[str]


class ManagedEmployeeDirectoryResponse(_ManagedEmployeeModel):
    base_id: str
    employees: list[ManagedEmployeeSummaryResponse]
    next_cursor: str | None = None
    has_more: bool = False


class ManagedEmployeeContextBaseResponse(_ManagedEmployeeModel):
    id: str
    name: str


class ManagedEmployeeContextTableResponse(_ManagedEmployeeModel):
    id: str
    name: str


class ManagedEmployeeContextViewResponse(_ManagedEmployeeModel):
    id: str
    table_id: str
    name: str
    view_type: ManagedEmployeeViewType


class ManagedEmployeeContextMemberResponse(_ManagedEmployeeModel):
    id: str
    label: str
    role: ManagedEmployeeRole


class ManagedEmployeeManagementContextResponse(_ManagedEmployeeModel):
    base: ManagedEmployeeContextBaseResponse
    tables: list[ManagedEmployeeContextTableResponse]
    views: list[ManagedEmployeeContextViewResponse]
    members: list[ManagedEmployeeContextMemberResponse]


class ManagedEmployeeCreateRequest(_ManagedEmployeeModel):
    name: StrictStr = Field(min_length=1, max_length=160)
    description: StrictStr = Field(min_length=1, max_length=500)
    telegram_alias: StrictStr | None = Field(default=None, max_length=80)


class ManagedEmployeeUpdateRequest(_ManagedEmployeeModel):
    expected_version: StrictInt = Field(ge=1)
    name: StrictStr | None = Field(default=None, min_length=1, max_length=160)
    description: StrictStr | None = Field(default=None, min_length=1, max_length=500)
    telegram_alias: StrictStr | None = Field(default=None, max_length=80)
    accessible_table_ids: list[UUID] | None = Field(default=None, max_length=100)
    accessible_view_ids: list[UUID] | None = Field(default=None, max_length=100)
    allowed_actions: list[ManagedEmployeeAction] | None = Field(
        default=None,
        max_length=2,
    )
    access_mode: ManagedEmployeeAccessMode | None = None


class ManagedEmployeeMemberGrantRequest(_ManagedEmployeeModel):
    expected_version: StrictInt = Field(ge=1)
    member_ids: list[UUID] = Field(default_factory=list, max_length=100)


class ManagedEmployeeLifecycleRequest(_ManagedEmployeeModel):
    expected_version: StrictInt = Field(ge=1)


class ManagedEmployeeLifecycleReceipt(_ManagedEmployeeModel):
    id: str
    status: Literal["active", "paused"]
    version: StrictInt = Field(ge=1)
    audit_event_id: str
