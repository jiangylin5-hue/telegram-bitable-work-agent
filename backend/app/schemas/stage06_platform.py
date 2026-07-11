from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator


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


class InitializeBaseRequest(BaseModel):
    base_name: str
    table_name: str


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


class InitializeTableRequest(BaseModel):
    table_name: str


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


class CreateFormFieldResponse(BaseModel):
    id: str
    key: str
    name: str
    field_type: str
    required: bool
    options: dict[str, Any]
    order_index: int


class CreateFormResponse(BaseModel):
    table_id: str
    can_create: bool
    fields: list[CreateFormFieldResponse]


class UpdateRecordRequest(BaseModel):
    values: dict[str, Any]
    expected_version: int = Field(ge=1)


class RecordResponse(BaseModel):
    id: str
    table_id: str
    values: dict[str, Any]
    record_status: str
    version: int


class RecordDetailResponse(RecordResponse):
    pass


class SafeTableFieldResponse(BaseModel):
    id: str
    table_id: str
    name: str
    key: str
    field_type: str
    required: bool
    options: dict[str, Any]
    order_index: int


class InitializeFieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    field_type: str
    required: bool = False
    choices: list[str] | None = None


class FieldInitializationResponse(BaseModel):
    field: SafeTableFieldResponse
    affected_view_ids: list[str]


class InitializeRelationFieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    target_table_id: str
    required: bool = False


class InitializeLookupFieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source_relation_field_id: str
    target_field_id: str
    aggregation: Literal[
        "values",
        "count",
        "count_distinct",
        "sum",
        "average",
        "min",
        "max",
    ]


class RelationCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str


class RelationCandidatePageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    records: list[RelationCandidateResponse]
    next_cursor: str | None
    has_more: bool


class TableSchemaResponse(BaseModel):
    table: dict[str, Any]
    fields: list[SafeTableFieldResponse]


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


class BuilderInitializationResponse(BaseModel):
    base: BaseSummaryResponse
    table: TableResponse
    default_view: ViewSummaryResponse


class ViewPresentationResponse(BaseModel):
    view_id: str
    table_id: str
    view_type: str
    visible_field_keys: list[str]
    group_by_field_key: str | None = None
    date_field_key: str | None = None
    form_field_keys: list[str]


class ViewRecordsResponse(BaseModel):
    view_id: str
    records: list[dict[str, Any]]
    trace_id: str
    next_cursor: str | None = None
    has_more: bool = False
    groups: list[dict[str, Any]] | None = None


class StrictViewBuilderModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ViewFieldKey = Annotated[str, Field(min_length=1, max_length=120)]
ViewName = Annotated[str, Field(min_length=1, max_length=120)]
ViewFilterValue = StrictStr | StrictInt | StrictFloat | StrictBool | list[StrictStr] | None


class ViewFilterCondition(StrictViewBuilderModel):
    field_key: ViewFieldKey
    operator: Literal[
        "equals",
        "not_equals",
        "contains",
        "is_empty",
        "is_not_empty",
        "gt",
        "gte",
        "lt",
        "lte",
        "is",
        "is_not",
        "contains_any",
        "contains_all",
        "is_true",
        "is_false",
        "contains_record",
        "before",
        "on_or_before",
        "after",
        "on_or_after",
    ]
    value: ViewFilterValue = None


class ViewSortRule(StrictViewBuilderModel):
    field_key: ViewFieldKey
    direction: Literal["asc", "desc"]


class _FilteredSortableViewPresentation(StrictViewBuilderModel):
    visible_field_keys: list[ViewFieldKey] = Field(default_factory=list, max_length=200)
    filter_conjunction: Literal["and"] = "and"
    filters: list[ViewFilterCondition] = Field(default_factory=list, max_length=12)
    sort_rules: list[ViewSortRule] = Field(default_factory=list, max_length=3)


class GridViewPresentationCommand(_FilteredSortableViewPresentation):
    view_type: Literal["grid"]
    group_by_field_key: ViewFieldKey | None = None


class KanbanViewPresentationCommand(_FilteredSortableViewPresentation):
    view_type: Literal["kanban"]
    group_by_field_key: ViewFieldKey


class CalendarViewPresentationCommand(_FilteredSortableViewPresentation):
    view_type: Literal["calendar"]
    date_field_key: ViewFieldKey


class FormViewPresentationCommand(StrictViewBuilderModel):
    view_type: Literal["form"]
    visible_field_keys: list[ViewFieldKey] = Field(default_factory=list, max_length=200)
    form_field_keys: list[ViewFieldKey] = Field(min_length=1, max_length=200)


ViewPresentationCommand = Annotated[
    GridViewPresentationCommand
    | KanbanViewPresentationCommand
    | CalendarViewPresentationCommand
    | FormViewPresentationCommand,
    Field(discriminator="view_type"),
]


class ViewInitializationRequest(StrictViewBuilderModel):
    name: ViewName
    view_type: Literal["grid", "kanban", "calendar", "form"]
    presentation: ViewPresentationCommand

    @model_validator(mode="after")
    def matches_presentation_type(self) -> "ViewInitializationRequest":
        if self.view_type != self.presentation.view_type:
            raise ValueError("view_type must match presentation.view_type")
        return self


class ViewPresentationPatchRequest(StrictViewBuilderModel):
    expected_version: Annotated[StrictInt, Field(ge=1)]
    name: ViewName | None = None
    presentation: ViewPresentationCommand


class ViewMemberCommand(StrictViewBuilderModel):
    user_id: Annotated[str, Field(min_length=1, max_length=120)]
    access_level: Literal["editor", "viewer"]


class ViewMemberReplaceRequest(StrictViewBuilderModel):
    expected_version: Annotated[StrictInt, Field(ge=1)]
    members: list[ViewMemberCommand] = Field(default_factory=list, max_length=100)


class SafeViewSummaryResponse(StrictViewBuilderModel):
    id: str
    base_id: str
    table_id: str
    name: str
    view_type: Literal["grid", "kanban", "calendar", "form"]
    scope: Literal["system_default", "private", "restricted"]
    caller_access_level: Literal["owner", "editor", "viewer", "system_default"]
    status: str
    is_default: bool


class SafeViewMemberResponse(StrictViewBuilderModel):
    user_id: str
    label: str
    access_level: Literal["editor", "viewer"]


class SafeViewMemberCandidateResponse(StrictViewBuilderModel):
    id: str
    label: str


class SafeViewFieldResponse(StrictViewBuilderModel):
    key: str
    label: str
    field_type: str
    filter_operators: list[str]
    sortable: bool
    groupable: bool
    form_eligible: bool


class SafeViewPresentationResponse(StrictViewBuilderModel):
    view_id: str
    table_id: str
    view_type: Literal["grid", "kanban", "calendar", "form"]
    visible_field_keys: list[str]
    filters: list[ViewFilterCondition]
    sort_rules: list[ViewSortRule]
    group_by_field_key: str | None = None
    date_field_key: str | None = None
    form_field_keys: list[str] = Field(default_factory=list)


class ViewBuilderResponse(StrictViewBuilderModel):
    view: SafeViewSummaryResponse
    presentation: SafeViewPresentationResponse
    fields: list[SafeViewFieldResponse]
    members: list[SafeViewMemberResponse]
    version: Annotated[int, Field(ge=1)]
    can_edit_presentation: bool
    can_replace_members: bool


class ViewBuilderContextResponse(StrictViewBuilderModel):
    table: TableResponse
    fields: list[SafeViewFieldResponse]
    views: list[SafeViewSummaryResponse]
    member_candidates: list[SafeViewMemberCandidateResponse]


class ViewInitializationResponse(StrictViewBuilderModel):
    view: SafeViewSummaryResponse
    affected_view_ids: list[str]


class ViewPresentationMutationResponse(StrictViewBuilderModel):
    view: SafeViewSummaryResponse
    version: Annotated[int, Field(ge=1)]


class ViewMemberReplaceResponse(StrictViewBuilderModel):
    view: SafeViewSummaryResponse
    members: list[SafeViewMemberResponse]
    version: Annotated[int, Field(ge=1)]
