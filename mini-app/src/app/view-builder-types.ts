export type ViewType = 'grid' | 'kanban' | 'calendar' | 'form'
export type ViewScope = 'system_default' | 'private' | 'restricted'
export type ViewAccessLevel = 'owner' | 'editor' | 'viewer' | 'system_default'
export type ViewMemberAccessLevel = 'editor' | 'viewer'
export type ViewFilterValue = string | number | boolean | string[] | null

export type ViewFilterCondition = {
  field_key: string
  operator: string
  value: ViewFilterValue
}

export type ViewSortRule = {
  field_key: string
  direction: 'asc' | 'desc'
}

type FilterablePresentation = {
  visible_field_keys: string[]
  filter_conjunction?: 'and'
  filters: ViewFilterCondition[]
  sort_rules: ViewSortRule[]
}

export type GridViewPresentation = FilterablePresentation & {
  view_type: 'grid'
  group_by_field_key: string | null
}

export type KanbanViewPresentation = FilterablePresentation & {
  view_type: 'kanban'
  group_by_field_key: string
}

export type CalendarViewPresentation = FilterablePresentation & {
  view_type: 'calendar'
  date_field_key: string
}

export type FormViewPresentation = {
  view_type: 'form'
  visible_field_keys: string[]
  form_field_keys: string[]
}

export type ViewPresentationCommand =
  | GridViewPresentation
  | KanbanViewPresentation
  | CalendarViewPresentation
  | FormViewPresentation

export type ViewInitializationRequest = {
  name: string
  view_type: ViewType
  presentation: ViewPresentationCommand
}

export type ViewPresentationPatchRequest = {
  expected_version: number
  name?: string
  presentation: ViewPresentationCommand
}

export type ViewMemberCommand = {
  user_id: string
  access_level: ViewMemberAccessLevel
}

export type ViewMemberReplaceRequest = {
  expected_version: number
  members: ViewMemberCommand[]
}

export type SafeViewSummary = {
  id: string
  base_id: string
  table_id: string
  name: string
  view_type: ViewType
  scope: ViewScope
  caller_access_level: ViewAccessLevel
  status: string
  is_default: boolean
}

export type SafeViewField = {
  field_id: string
  key: string
  label: string
  field_type: string
  filter_operators: string[]
  filter_values: string[]
  sortable: boolean
  groupable: boolean
  form_eligible: boolean
}

export type SafeViewMember = {
  user_id: string
  label: string
  access_level: ViewMemberAccessLevel
}

export type SafeViewMemberCandidate = {
  id: string
  label: string
}

export type SafeViewPresentation = {
  view_id: string
  table_id: string
  view_type: ViewType
  visible_field_keys: string[]
  filters: ViewFilterCondition[]
  sort_rules: ViewSortRule[]
  group_by_field_key: string | null
  date_field_key: string | null
  form_field_keys: string[]
}

export type ViewBuilderContext = {
  table: { id: string; base_id: string; name: string; key: string; status: string }
  fields: SafeViewField[]
  views: SafeViewSummary[]
  member_candidates: SafeViewMemberCandidate[]
}

export type ViewBuilderResponse = {
  view: SafeViewSummary
  presentation: SafeViewPresentation
  fields: SafeViewField[]
  members: SafeViewMember[]
  version: number
  can_edit_presentation: boolean
  can_replace_members: boolean
}

export type ViewInitializationReceipt = {
  view: SafeViewSummary
  affected_view_ids: string[]
}

export type ViewPresentationMutationReceipt = {
  view: SafeViewSummary
  version: number
}

export type ViewMemberReplaceReceipt = {
  view: SafeViewSummary
  members: SafeViewMember[]
  version: number
}

export type SafeViewErrorCode =
  | 'view_name_invalid'
  | 'view_type_unsupported'
  | 'view_version_conflict'
  | 'view_member_not_active'
  | 'view_member_invalid'
  | 'view_member_grant_forbidden'
  | 'view_field_not_visible'
  | 'view_filter_invalid'
  | 'view_sort_invalid'
  | 'view_group_invalid'
  | 'view_date_field_invalid'
  | 'view_form_field_invalid'
  | 'view_default_ineligible'
  | 'view_access_denied'
  | 'view_not_found'
