import type {
  SafeViewErrorCode,
  SafeViewField,
  SafeViewMember,
  SafeViewMemberCandidate,
  SafeViewPresentation,
  SafeViewSummary,
  ViewBuilderContext,
  ViewBuilderResponse,
  ViewAccessLevel,
  ViewFilterValue,
  ViewInitializationReceipt,
  ViewInitializationRequest,
  ViewMemberReplaceReceipt,
  ViewMemberReplaceRequest,
  ViewPresentationMutationReceipt,
  ViewPresentationPatchRequest,
  ViewType,
  ViewScope,
} from './view-builder-types'
import type {
  CommitImportValues,
  CreateImportValues,
  ImportCommitReceipt,
  ImportMapping,
  ImportPreview,
  ImportScalarFieldType,
  SaveTemplateValues,
  TemplateInstallationReceipt,
  TemplateSummary,
} from './template-import-types'
import type {
  GovernanceAuditActorType,
  GovernanceAuditEvent,
  GovernanceAuditPage,
  GovernanceMember,
  GovernanceMemberPage,
} from './governance-types'
import type {
  GovernanceAssignableRole,
  GovernanceEditableMember,
  GovernanceEditableMemberPage,
  GovernanceFieldPermission,
  GovernanceFieldPermissionPage,
  GovernanceFieldPermissionPolicy,
  GovernanceFieldPermissionReceipt,
  GovernanceFieldPermissionMode,
  GovernanceMemberRoleReceipt,
  GovernanceRole,
} from './governance-write-types'
import type { AssistantContextPage, AssistantContextView, AssistantSelectedView, S5Citation, S5Contact, S5ContactPage, S5DraftDetail, S5DraftField, S5Intent, S5InvocationRequest, S5InvocationResult, S5TerminalReceipt } from './draft-employee-types'
import type {
  TeamBotCitation,
  TeamBotContact,
  TeamBotContactPage,
  TeamBotKnowledgeContextPage,
  TeamBotKnowledgeView,
  TeamBotSelectedView,
  TeamBotSummary,
  TeamBotSummaryRequest,
  TeamBotViewType,
} from './team-bot-knowledge-types'
import type {
  ManagedEmployeeAccessMode,
  ManagedEmployeeAction,
  ManagedEmployeeCreateValues,
  ManagedEmployeeDetail,
  ManagedEmployeeDirectory,
  ManagedEmployeeLifecycleReceipt,
  ManagedEmployeeManagementContext,
  ManagedEmployeeMemberRole,
  ManagedEmployeeStatus,
  ManagedEmployeeSummary,
  ManagedEmployeeUpdateValues,
  ManagedEmployeeViewType,
} from './digital-employee-management-types'
import type { Stage08AssistantCitation, Stage08AssistantQuery, Stage08AssistantSafeView, Stage08AssistantStatus, Stage08CitationLabel, Stage08DegradationCode } from './stage08-collaboration-types'
import type { Stage08MemoryItem, Stage08MemoryPage, Stage08MemoryType } from './stage08-memory-types'

export type {
  SafeViewErrorCode,
  SafeViewField,
  SafeViewMember,
  SafeViewMemberCandidate,
  SafeViewPresentation,
  SafeViewSummary,
  ViewBuilderContext,
  ViewBuilderResponse,
  ViewFilterValue,
  ViewInitializationReceipt,
  ViewInitializationRequest,
  ViewMemberReplaceReceipt,
  ViewMemberReplaceRequest,
  ViewPresentationMutationReceipt,
  ViewPresentationPatchRequest,
} from './view-builder-types'
export type {
  CommitImportValues,
  CreateImportValues,
  ImportCommitReceipt,
  ImportMapping,
  ImportPreview,
  ImportScalarFieldType,
  SaveTemplateValues,
  TemplateInstallationReceipt,
  TemplateSummary,
} from './template-import-types'
export type {
  GovernanceAuditActorType,
  GovernanceAuditEvent,
  GovernanceAuditPage,
  GovernanceMember,
  GovernanceMemberPage,
} from './governance-types'
export type {
  GovernanceAssignableRole,
  GovernanceEditableMember,
  GovernanceEditableMemberPage,
  GovernanceFieldPermission,
  GovernanceFieldPermissionPage,
  GovernanceFieldPermissionPolicy,
  GovernanceFieldPermissionReceipt,
  GovernanceFieldPermissionMode,
  GovernanceMemberRoleReceipt,
  GovernanceRole,
} from './governance-write-types'
export type {
  ManagedEmployeeAccessMode,
  ManagedEmployeeAction,
  ManagedEmployeeCreateValues,
  ManagedEmployeeDetail,
  ManagedEmployeeDirectory,
  ManagedEmployeeLifecycleReceipt,
  ManagedEmployeeManagementContext,
  ManagedEmployeeMemberRole,
  ManagedEmployeeStatus,
  ManagedEmployeeSummary,
  ManagedEmployeeUpdateValues,
  ManagedEmployeeViewType,
} from './digital-employee-management-types'

export type WorkspaceCapabilities = {
  can_read_bases: boolean
  can_manage_workspace: boolean
  can_manage_schema: boolean
  can_manage_digital_employees?: boolean
  can_review_drafts: boolean
}

export type Workspace = {
  id: string
  name: string
  slug: string
  role: string
  capabilities: WorkspaceCapabilities
}

export type BootstrapResponse = {
  identity: { user_id: string; source: string }
  workspaces: Workspace[]
}

export type TelegramDeepLinkDestination = {
  kind: 'base' | 'view' | 'record' | 'record_change_draft'
  workspaceId: string
  baseId?: string
  tableId?: string
  viewId?: string
  recordId?: string
  draftId?: string
}

export type TelegramDeepLinkResolution =
  | { outcome: 'resolved'; destination: TelegramDeepLinkDestination }
  | { outcome: 'recovery' }

export type BrowserHandoff = {
  ticket: string
  expiresAt: string
}

export type BusinessContextRelation = {
  employee: { id: string; name: string; base_id: string; base_name: string }
  group: { id: string; label: string }
  customer: { id: string; base_id: string; label: string }
  project: { id: string; base_id: string; label: string }
  mapping_version: number
}

export type WorkspaceHome = {
  workspace_id: string
  recent_bases: { id: string; name: string; source_type: string }[]
  queue: {
    id: string
    kind: string
    title: string
    status: string
    destination: { base_id: string; draft_id: string }
    action_availability: { can_confirm: boolean; can_reject: boolean }
  }[]
  business_context_relations?: BusinessContextRelation[]
}

export type BaseSummary = { id: string; name: string; source_type: string; status?: string }
export type PlatformTable = { id: string; base_id: string; name: string; key: string; status: string }
export type ViewSummary = { id: string; base_id: string; table_id: string | null; name: string; view_type: string; status: string; scope?: ViewScope; caller_access_level?: ViewAccessLevel; is_default?: boolean }
export type BuilderInitializationReceipt = { base: BaseSummary; table: PlatformTable; default_view: ViewSummary }
export type SafeTableField = {
  id: string
  table_id: string
  name: string
  key: string
  field_type: string
  required: boolean
  options: { choices?: string[] }
  order_index: number
}
export type FieldInitializationReceipt = { field: SafeTableField; affected_view_ids: string[] }
export type RelationCell = { id: string; label: string }
export type RelationCandidate = RelationCell
export type RelationCandidatePage = {
  field_id: string
  records: RelationCandidate[]
  next_cursor: string | null
  has_more: boolean
}
export type RelationFieldInitializationValues = {
  name: string
  targetTableId: string
  required: boolean
}
export type LookupAggregation = 'values' | 'count' | 'count_distinct' | 'sum' | 'average' | 'min' | 'max'
export type LookupFieldInitializationValues = {
  name: string
  sourceRelationFieldId: string
  targetFieldId: string
  aggregation: LookupAggregation
}
export type TableSchema = { table: { id: string; name: string; key: string }; fields: SafeTableField[] }
export type ViewRecords = { view_id: string; records: { id: string; fields: Record<string, unknown> }[]; next_cursor: string | null; has_more: boolean }
export type ViewPresentation = { view_id: string; table_id: string; view_type: string; visible_field_keys: string[]; group_by_field_key: string | null; date_field_key: string | null; form_field_keys: string[] }
export type RecordDetail = { id: string; table_id: string; values: Record<string, unknown>; record_status: string; version: number }
export type CreateForm = { table_id: string; can_create: boolean; fields: { id: string; key: string; name: string; field_type: string; required: boolean; options: Record<string, unknown>; order_index: number }[] }

export type SafeApiErrorCode =
  | 'duplicate_field_name'
  | 'relation_self_reference'
  | 'lookup_source_not_relation'
  | 'lookup_target_incompatible'
  | 'lookup_dependency_cycle'
  | 'lookup_depth_exceeded'
  | 'record_is_referenced'
  | 'field_has_dependencies'
  | 'import_payload_limit_exceeded'
  | 'import_row_limit_exceeded'
  | 'import_column_limit_exceeded'
  | 'import_cell_limit_exceeded'
  | 'import_has_no_rows'
  | 'import_missing_header'
  | 'import_missing_sheet'
  | 'unsupported_import_source'
  | 'invalid_import_mapping'
  | 'unsupported_field_type'
  | 'resource_scope_mismatch'
  | 'import_job_invalid_state'
  | 'import_table_key_conflict'
  | 'template_not_found'
  | 'idempotency_conflict'
  | 'idempotency_in_progress'
  | 'governance_revision_conflict'
  | 'governance_role_change_forbidden'
  | 'governance_member_inactive'
  | 'governance_field_policy_invalid'
  | 'governance_field_owner_write_required'
  | 'governance_field_policy_forbidden'
  | 'digital_employee_revision_conflict'
  | 'digital_employee_alias_conflict'
  | 'digital_employee_active_requires_pause'
  | 'digital_employee_action_unsupported'
  | 'digital_employee_access_mode_unsupported'
  | 'digital_employee_scope_denied'
  | 'digital_employee_member_scope_denied'
  | 'digital_employee_member_inactive'
  | 'digital_employee_member_grant_required'
  | SafeViewErrorCode

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code?: SafeApiErrorCode) {
    super(`请求失败 (${status})`)
  }
}

const choiceFieldTypes = new Set<FieldBuilderValues['fieldType']>([
  'status',
  'single_select',
  'multi_select',
])

const safeApiErrorCodes = new Set<SafeApiErrorCode>([
  'duplicate_field_name',
  'relation_self_reference',
  'lookup_source_not_relation',
  'lookup_target_incompatible',
  'lookup_dependency_cycle',
  'lookup_depth_exceeded',
  'record_is_referenced',
  'field_has_dependencies',
  'import_payload_limit_exceeded',
  'import_row_limit_exceeded',
  'import_column_limit_exceeded',
  'import_cell_limit_exceeded',
  'import_has_no_rows',
  'import_missing_header',
  'import_missing_sheet',
  'unsupported_import_source',
  'invalid_import_mapping',
  'unsupported_field_type',
  'resource_scope_mismatch',
  'import_job_invalid_state',
  'import_table_key_conflict',
  'template_not_found',
  'idempotency_conflict',
  'idempotency_in_progress',
  'governance_revision_conflict',
  'governance_role_change_forbidden',
  'governance_member_inactive',
  'governance_field_policy_invalid',
  'governance_field_owner_write_required',
  'governance_field_policy_forbidden',
  'digital_employee_revision_conflict',
  'digital_employee_alias_conflict',
  'digital_employee_active_requires_pause',
  'digital_employee_action_unsupported',
  'digital_employee_access_mode_unsupported',
  'digital_employee_scope_denied',
  'digital_employee_member_scope_denied',
  'digital_employee_member_inactive',
  'digital_employee_member_grant_required',
  'view_name_invalid',
  'view_type_unsupported',
  'view_version_conflict',
  'view_member_not_active',
  'view_member_invalid',
  'view_member_grant_forbidden',
  'view_field_not_visible',
  'view_filter_invalid',
  'view_sort_invalid',
  'view_group_invalid',
  'view_date_field_invalid',
  'view_form_field_invalid',
  'view_default_ineligible',
  'view_access_denied',
  'view_not_found',
])

const safeViewErrorCopy: Record<SafeViewErrorCode, string> = {
  view_name_invalid: '视图名称不符合要求。',
  view_type_unsupported: '当前视图类型不可用。',
  view_version_conflict: '视图已被更新，请重新加载后再试。',
  view_member_not_active: '成员当前不可用。',
  view_member_invalid: '成员设置不符合要求。',
  view_member_grant_forbidden: '当前成员设置不允许。',
  view_field_not_visible: '所选字段当前不可用。',
  view_filter_invalid: '筛选条件不符合要求。',
  view_sort_invalid: '排序条件不符合要求。',
  view_group_invalid: '分组条件不符合要求。',
  view_date_field_invalid: '日期字段不符合要求。',
  view_form_field_invalid: '表单字段不符合要求。',
  view_default_ineligible: '默认视图不能这样修改。',
  view_access_denied: '当前没有视图访问权限。',
  view_not_found: '视图不可用，请重新加载。',
}

const safeViewErrorCodes = new Set<SafeViewErrorCode>(Object.keys(safeViewErrorCopy) as SafeViewErrorCode[])

async function safeErrorCode(response: Response): Promise<SafeApiErrorCode | undefined> {
  try {
    const body: unknown = await response.json()
    if (!body || typeof body !== 'object' || !('detail' in body)) return undefined
    const detail = body.detail
    if (!detail || typeof detail !== 'object' || !('code' in detail)) return undefined
    return typeof detail.code === 'string' && safeApiErrorCodes.has(detail.code as SafeApiErrorCode)
      ? detail.code as SafeApiErrorCode
      : undefined
  } catch {
    return undefined
  }
}

let telegramInitData: string | null = null

export function setTelegramInitData(value: string | null): void {
  telegramInitData = value?.trim() || null
}

function protectedHeaders(input?: HeadersInit): Headers {
  const headers = new Headers(input)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  if (telegramInitData) headers.set('X-Telegram-Init-Data', telegramInitData)
  return headers
}

async function getJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = telegramInitData
    ? Object.fromEntries(protectedHeaders(init.headers).entries())
    : init.headers ?? { Accept: 'application/json' }
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...init,
    headers,
  })
  if (!response.ok) throw new ApiError(response.status, await safeErrorCode(response))
  return response.json() as Promise<T>
}

async function postJson<T>(path: string, payload: unknown, idempotencyKey: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  headers.set('Content-Type', 'application/json')
  headers.set('Idempotency-Key', idempotencyKey)
  return getJson<T>(path, {
    ...init,
    method: 'POST',
    headers: Object.fromEntries(headers.entries()),
    body: JSON.stringify(payload),
  })
}

function jsonRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid view response')
  return value as Record<string, unknown>
}

function stringValue(value: unknown): string {
  if (typeof value !== 'string') throw new Error('Invalid view response')
  return value
}

function booleanValue(value: unknown): boolean {
  if (typeof value !== 'boolean') throw new Error('Invalid view response')
  return value
}

function numberValue(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error('Invalid view response')
  return value
}

function nullableStringValue(value: unknown): string | null {
  if (value === null) return null
  return stringValue(value)
}

function safeBrowserHandoff(value: unknown): BrowserHandoff {
  const record = jsonRecord(value)
  const ticket = stringValue(record.ticket).trim()
  const expiresAt = stringValue(record.expires_at).trim()
  if (!ticket || !expiresAt) throw new Error('Invalid browser handoff response')
  return { ticket, expiresAt }
}

/**
 * Builds the handoff location without a query string. Callers must keep the
 * ticket in their local call frame and must not persist or render it.
 */
export function buildBrowserHandoffUrl(ticket: string): string {
  const url = new URL('/browser-handoff.html', window.location.origin)
  url.hash = new URLSearchParams({ ticket }).toString()
  return url.toString()
}

const importScalarFieldTypes = new Set<ImportScalarFieldType>(['text', 'number', 'date', 'checkbox'])
const governanceActorTypes = new Set<GovernanceAuditActorType>(['user', 'digital_employee', 'system'])

function safeGovernanceMember(value: unknown): GovernanceMember {
  const record = jsonRecord(value)
  return {
    id: stringValue(record.id),
    userId: stringValue(record.user_id),
    role: stringValue(record.role),
    status: stringValue(record.status),
  }
}

function safeGovernanceMemberPage(value: unknown): GovernanceMemberPage {
  const record = jsonRecord(value)
  if (!Array.isArray(record.members)) throw new Error('Invalid governance response')
  return {
    workspaceId: stringValue(record.workspace_id),
    members: record.members.map(safeGovernanceMember),
    nextCursor: nullableStringValue(record.next_cursor),
    hasMore: booleanValue(record.has_more),
  }
}

function safeGovernanceAuditEvent(value: unknown): GovernanceAuditEvent {
  const record = jsonRecord(value)
  const actorType = stringValue(record.actor_type)
  if (!governanceActorTypes.has(actorType as GovernanceAuditActorType)) {
    throw new Error('Invalid governance response')
  }
  return {
    id: stringValue(record.id),
    occurredAt: stringValue(record.occurred_at),
    actorType: actorType as GovernanceAuditActorType,
    eventType: stringValue(record.event_type),
    entityType: stringValue(record.entity_type),
  }
}

function safeGovernanceAuditPage(value: unknown): GovernanceAuditPage {
  const record = jsonRecord(value)
  if (!Array.isArray(record.events)) throw new Error('Invalid governance response')
  return {
    baseId: stringValue(record.base_id),
    events: record.events.map(safeGovernanceAuditEvent),
    nextCursor: nullableStringValue(record.next_cursor),
    hasMore: booleanValue(record.has_more),
  }
}

const governanceRoles = new Set<GovernanceRole>(['owner', 'admin', 'builder', 'operator', 'viewer'])
const governanceAssignableRoles = new Set<GovernanceAssignableRole>(['admin', 'builder', 'operator', 'viewer'])
const governanceFieldPermissionModes = new Set<GovernanceFieldPermissionMode>(['hidden', 'read', 'write'])

function governanceRole(value: unknown): GovernanceRole {
  const role = stringValue(value)
  if (!governanceRoles.has(role as GovernanceRole)) throw new Error('Invalid governance write response')
  return role as GovernanceRole
}

function governanceActiveStatus(value: unknown): 'active' {
  if (value !== 'active') throw new Error('Invalid governance write response')
  return 'active'
}

function governanceVersion(value: unknown): number {
  const version = numberValue(value)
  if (!Number.isInteger(version) || version < 1) throw new Error('Invalid governance write response')
  return version
}

function governanceAssignableRoleList(value: unknown): GovernanceAssignableRole[] {
  if (!Array.isArray(value) || value.length === 0) throw new Error('Invalid governance write response')
  const roles = value.map((item) => stringValue(item))
  if (roles.some((role) => !governanceAssignableRoles.has(role as GovernanceAssignableRole))) throw new Error('Invalid governance write response')
  return [...new Set(roles)] as GovernanceAssignableRole[]
}

function safeGovernanceEditableMember(value: unknown): GovernanceEditableMember {
  const record = jsonRecord(value)
  return {
    id: stringValue(record.id), userId: stringValue(record.user_id), role: governanceRole(record.role),
    status: governanceActiveStatus(record.status), version: governanceVersion(record.version),
    assignableRoles: governanceAssignableRoleList(record.assignable_roles),
  }
}

function safeGovernanceEditableMemberPage(value: unknown): GovernanceEditableMemberPage {
  const record = jsonRecord(value)
  if (!Array.isArray(record.members)) throw new Error('Invalid governance write response')
  return {
    workspaceId: stringValue(record.workspace_id), members: record.members.map(safeGovernanceEditableMember),
    nextCursor: nullableStringValue(record.next_cursor), hasMore: booleanValue(record.has_more),
  }
}

function safeGovernanceFieldPermissionPolicy(value: unknown): GovernanceFieldPermissionPolicy {
  const record = jsonRecord(value)
  const expectedRoles: GovernanceRole[] = ['owner', 'admin', 'builder', 'operator', 'viewer']
  if (Object.keys(record).length !== expectedRoles.length || expectedRoles.some((role) => !(role in record))) throw new Error('Invalid governance write response')
  const policy = {} as GovernanceFieldPermissionPolicy
  for (const role of expectedRoles) {
    const mode = stringValue(record[role])
    if (!governanceFieldPermissionModes.has(mode as GovernanceFieldPermissionMode)) throw new Error('Invalid governance write response')
    policy[role] = mode as GovernanceFieldPermissionMode
  }
  if (policy.owner !== 'write') throw new Error('Invalid governance write response')
  return policy
}

function safeGovernanceFieldPermission(value: unknown): GovernanceFieldPermission {
  const record = jsonRecord(value)
  return {
    id: stringValue(record.id), key: stringValue(record.key), label: stringValue(record.label), fieldType: stringValue(record.field_type),
    policy: safeGovernanceFieldPermissionPolicy(record.policy), permissionVersion: governanceVersion(record.permission_version),
  }
}

function safeGovernanceFieldPermissionPage(value: unknown): GovernanceFieldPermissionPage {
  const record = jsonRecord(value)
  if (!Array.isArray(record.fields)) throw new Error('Invalid governance write response')
  return { tableId: stringValue(record.table_id), fields: record.fields.map(safeGovernanceFieldPermission) }
}

function safeGovernanceMemberRoleReceipt(value: unknown): GovernanceMemberRoleReceipt {
  const record = jsonRecord(value)
  return { id: stringValue(record.id), userId: stringValue(record.user_id), role: governanceRole(record.role), status: governanceActiveStatus(record.status), version: governanceVersion(record.version) }
}

function safeGovernanceFieldPermissionReceipt(value: unknown): GovernanceFieldPermissionReceipt {
  const record = jsonRecord(value)
  return { id: stringValue(record.id), key: stringValue(record.key), policy: safeGovernanceFieldPermissionPolicy(record.policy), permissionVersion: governanceVersion(record.permission_version) }
}

function s5Intent(value: unknown): S5Intent {
  if (value === 'summarize' || value === 'draft_update') return value
  throw new Error('Invalid S5 response')
}

function s5Status(value: unknown): S5DraftDetail['status'] {
  if (value === 'pending_confirmation' || value === 'confirmed' || value === 'rejected' || value === 'expired') return value
  throw new Error('Invalid S5 response')
}

function s5Value(value: unknown): string | number | boolean | null {
  if (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
  throw new Error('Invalid S5 response')
}

function safeS5Contact(value: unknown): S5Contact {
  const record = jsonRecord(value)
  if (!Array.isArray(record.available_intents) || record.status !== 'active') throw new Error('Invalid S5 response')
  return { id: stringValue(record.id), baseId: stringValue(record.base_id), name: stringValue(record.name), description: stringValue(record.description), status: 'active', availableIntents: record.available_intents.map(s5Intent) }
}

function safeS5ContactPage(value: unknown): S5ContactPage {
  const record = jsonRecord(value)
  if (!Array.isArray(record.contacts)) throw new Error('Invalid S5 response')
  return { workspaceId: stringValue(record.workspace_id), contacts: record.contacts.map(safeS5Contact), nextCursor: nullableStringValue(record.next_cursor), hasMore: booleanValue(record.has_more) }
}

function safeS5DraftField(value: unknown): S5DraftField {
  const record = jsonRecord(value)
  return { key: stringValue(record.key), label: stringValue(record.label), fieldType: stringValue(record.field_type), beforeValue: s5Value(record.before_value), proposedValue: s5Value(record.proposed_value) }
}

function safeS5DraftDetail(value: unknown): S5DraftDetail {
  const record = jsonRecord(value)
  const actions = jsonRecord(record.actions)
  if (!Array.isArray(record.fields) || !Number.isInteger(record.version)) throw new Error('Invalid S5 response')
  return { id: stringValue(record.id), baseId: stringValue(record.base_id), tableId: stringValue(record.table_id), recordId: nullableStringValue(record.record_id), draftType: stringValue(record.draft_type), status: s5Status(record.status), version: record.version as number, fields: record.fields.map(safeS5DraftField), actions: { canConfirm: booleanValue(actions.can_confirm), canReject: booleanValue(actions.can_reject) }, terminalAuditEventId: nullableStringValue(record.terminal_audit_event_id) }
}

function safeS5TerminalReceipt(value: unknown): S5TerminalReceipt {
  const record = jsonRecord(value)
  const status = record.status
  if ((status !== 'confirmed' && status !== 'rejected') || !Number.isInteger(record.version)) throw new Error('Invalid S5 response')
  return { id: stringValue(record.id), status, version: record.version as number, terminalAuditEventId: stringValue(record.terminal_audit_event_id) }
}

function safeS5Citation(value: unknown): S5Citation {
  const record = jsonRecord(value)
  return { recordId: stringValue(record.record_id) }
}

function safeS5InvocationResult(value: unknown): S5InvocationResult {
  const record = jsonRecord(value)
  if (record.kind === 'summary') {
    if (!Array.isArray(record.citations)) throw new Error('Invalid S5 response')
    return { kind: 'summary', answer: stringValue(record.answer), citations: record.citations.map(safeS5Citation) }
  }
  if (record.kind === 'draft' && record.status === 'pending_confirmation') {
    return { kind: 'draft', draftId: stringValue(record.draft_id), status: 'pending_confirmation' }
  }
  throw new Error('Invalid S5 response')
}

const stage08Statuses = new Set<Stage08AssistantStatus>(['completed', 'draft_pending', 'degraded', 'denied', 'failed', 'cancelled', 'timed_out'])
const stage08CitationLabels = new Set<Stage08CitationLabel>(['business_data', 'confirmed_memory', 'group_context', 'retrieved_material', 'analysis_from_current_material', 'general_advice'])
const stage08DegradationCodes = new Set<Stage08DegradationCode>(['context_unavailable', 'retrieval_unavailable', 'compression_unavailable', 'analysis_unavailable', 'no_evidence', 'policy_denied', 'cancelled', 'timed_out', 'internal_failure'])
const stage08Intents = new Set<Stage08AssistantQuery['intent']>(['business_fact', 'memory_lookup', 'mixed', 'general_advice'])
const stage08RequestedActions = new Set<Stage08AssistantQuery['requestedAction']>(['read_only', 'draft_update'])
const privateIdentifierPattern = /(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])/i

function safeStage08Citation(value: unknown): Stage08AssistantCitation {
  const record = jsonRecord(value)
  const ordinal = numberValue(record.ordinal)
  const label = stringValue(record.label)
  if (!Number.isInteger(ordinal) || ordinal < 1 || ordinal > 12 || !stage08CitationLabels.has(label as Stage08CitationLabel)) throw new Error('Invalid Stage08 collaboration response')
  return { ordinal, label: label as Stage08CitationLabel }
}

function safeStage08AssistantSafeView(value: unknown): Stage08AssistantSafeView {
  const record = jsonRecord(value)
  const status = stringValue(record.status)
  const answer = nullableStringValue(record.answer)
  if (!stage08Statuses.has(status as Stage08AssistantStatus) || (answer !== null && (answer.length > 2000 || privateIdentifierPattern.test(answer))) || !Array.isArray(record.citations) || !Array.isArray(record.degradation_codes)) throw new Error('Invalid Stage08 collaboration response')
  const citations = record.citations.map(safeStage08Citation)
  const degradationCodes = record.degradation_codes.map((code) => {
    if (typeof code !== 'string' || !stage08DegradationCodes.has(code as Stage08DegradationCode)) throw new Error('Invalid Stage08 collaboration response')
    return code as Stage08DegradationCode
  })
  if (new Set(citations.map((citation) => citation.ordinal)).size !== citations.length || new Set(degradationCodes).size !== degradationCodes.length) throw new Error('Invalid Stage08 collaboration response')
  const draftId = nullableStringValue(record.draft_id)
  if ((status === 'draft_pending') !== Boolean(draftId)) throw new Error('Invalid Stage08 collaboration response')
  return { status: status as Stage08AssistantStatus, answer, citations, degradationCodes, draftId }
}

const stage08MemoryTypes = new Set<Stage08MemoryType>(['decision', 'preference', 'risk', 'customer_fact', 'project_fact'])

function safeStage08MemoryPayload(value: unknown): Record<string, unknown> {
  const payload = jsonRecord(value)
  if (Object.keys(payload).length > 32) throw new Error('Invalid Stage08 memory response')
  for (const item of Object.values(payload)) {
    if (typeof item === 'string' && item.length > 2000) throw new Error('Invalid Stage08 memory response')
  }
  return payload
}

function safeStage08MemoryItem(value: unknown): Stage08MemoryItem {
  const record = jsonRecord(value)
  const memoryType = stringValue(record.memory_type)
  const status = stringValue(record.status)
  const version = numberValue(record.version)
  if (!stage08MemoryTypes.has(memoryType as Stage08MemoryType) || status !== 'active' || !Number.isInteger(version) || version < 1) throw new Error('Invalid Stage08 memory response')
  const validUntil = nullableStringValue(record.valid_until)
  return { memoryType: memoryType as Stage08MemoryType, status: 'active', version, payload: safeStage08MemoryPayload(record.payload), validUntil }
}

function safeStage08MemoryPage(value: unknown): Stage08MemoryPage {
  const record = jsonRecord(value)
  if (!Array.isArray(record.items) || record.items.length > 200) throw new Error('Invalid Stage08 memory response')
  return { items: record.items.map(safeStage08MemoryItem) }
}

function assistantContextViewType(value: unknown): AssistantContextView['viewType'] {
  if (value === 'grid' || value === 'kanban' || value === 'calendar' || value === 'form') return value
  throw new Error('Invalid assistant context response')
}

function assertAssistantContextKeys(record: Record<string, unknown>, keys: string[]): void {
  if (Object.keys(record).length !== keys.length || keys.some((key) => !(key in record))) {
    throw new Error('Invalid assistant context response')
  }
}

function safeAssistantContextView(value: unknown): AssistantContextView {
  const record = jsonRecord(value)
  assertAssistantContextKeys(record, ['id', 'name', 'view_type'])
  return { id: stringValue(record.id), name: stringValue(record.name), viewType: assistantContextViewType(record.view_type) }
}

function safeAssistantContextPage(value: unknown): AssistantContextPage {
  const record = jsonRecord(value)
  assertAssistantContextKeys(record, ['employee', 'views', 'next_cursor', 'has_more'])
  const employee = jsonRecord(record.employee)
  assertAssistantContextKeys(employee, ['id', 'name', 'description', 'base_id'])
  if (!Array.isArray(record.views)) throw new Error('Invalid assistant context response')
  return {
    employee: { id: stringValue(employee.id), name: stringValue(employee.name), description: stringValue(employee.description), baseId: stringValue(employee.base_id) },
    views: record.views.map(safeAssistantContextView),
    nextCursor: nullableStringValue(record.next_cursor),
    hasMore: booleanValue(record.has_more),
  }
}

function safeAssistantSelectedView(value: unknown): AssistantSelectedView {
  const record = jsonRecord(value)
  assertAssistantContextKeys(record, ['id', 'name', 'view_type', 'base_id'])
  return { id: stringValue(record.id), name: stringValue(record.name), viewType: assistantContextViewType(record.view_type), baseId: stringValue(record.base_id) }
}

function assertTeamBotKeys(record: Record<string, unknown>, keys: string[]): void {
  if (Object.keys(record).length !== keys.length || keys.some((key) => !(key in record))) {
    throw new Error('Invalid team bot response')
  }
}

function teamBotId(value: unknown): string {
  const id = stringValue(value).trim()
  if (!id) throw new Error('Invalid team bot response')
  return id
}

function teamBotViewType(value: unknown): TeamBotViewType {
  if (value === 'grid' || value === 'kanban' || value === 'calendar' || value === 'form') return value
  throw new Error('Invalid team bot response')
}

function safeTeamBotContact(value: unknown): TeamBotContact {
  const record = jsonRecord(value)
  assertTeamBotKeys(record, ['id', 'base_id', 'name', 'description', 'available_intents'])
  if (!Array.isArray(record.available_intents) || record.available_intents.length !== 1 || record.available_intents[0] !== 'summarize') {
    throw new Error('Invalid team bot response')
  }
  return { id: teamBotId(record.id), baseId: teamBotId(record.base_id), name: stringValue(record.name), description: stringValue(record.description), availableIntents: ['summarize'] }
}

function safeTeamBotContactPage(value: unknown): TeamBotContactPage {
  const record = jsonRecord(value)
  assertTeamBotKeys(record, ['workspace_id', 'contacts', 'next_cursor', 'has_more'])
  if (!Array.isArray(record.contacts)) throw new Error('Invalid team bot response')
  return { workspaceId: teamBotId(record.workspace_id), contacts: record.contacts.map(safeTeamBotContact), nextCursor: nullableStringValue(record.next_cursor), hasMore: booleanValue(record.has_more) }
}

function safeTeamBotKnowledgeView(value: unknown): TeamBotKnowledgeView {
  const record = jsonRecord(value)
  assertTeamBotKeys(record, ['id', 'name', 'view_type'])
  return { id: teamBotId(record.id), name: stringValue(record.name), viewType: teamBotViewType(record.view_type) }
}

function safeTeamBotKnowledgeContextPage(value: unknown): TeamBotKnowledgeContextPage {
  const record = jsonRecord(value)
  assertTeamBotKeys(record, ['employee', 'views', 'next_cursor', 'has_more'])
  const employee = jsonRecord(record.employee)
  assertTeamBotKeys(employee, ['id', 'name', 'description', 'base_id'])
  if (!Array.isArray(record.views)) throw new Error('Invalid team bot response')
  return {
    employee: { id: teamBotId(employee.id), name: stringValue(employee.name), description: stringValue(employee.description), baseId: teamBotId(employee.base_id) },
    views: record.views.map(safeTeamBotKnowledgeView),
    nextCursor: nullableStringValue(record.next_cursor),
    hasMore: booleanValue(record.has_more),
  }
}

function safeTeamBotSelectedView(value: unknown): TeamBotSelectedView {
  const record = jsonRecord(value)
  assertTeamBotKeys(record, ['id', 'name', 'view_type', 'base_id'])
  return { id: teamBotId(record.id), name: stringValue(record.name), viewType: teamBotViewType(record.view_type), baseId: teamBotId(record.base_id) }
}

function safeTeamBotCitation(value: unknown): TeamBotCitation {
  const record = jsonRecord(value)
  assertTeamBotKeys(record, ['record_id'])
  return { recordId: teamBotId(record.record_id) }
}

function safeTeamBotSummary(value: unknown): TeamBotSummary {
  const record = jsonRecord(value)
  assertTeamBotKeys(record, ['kind', 'employee_id', 'base_id', 'view_id', 'answer', 'citations', 'knowledge_window_truncated', 'audit_event_id'])
  if ((record.kind !== 'summary' && record.kind !== 'empty_context') || !Array.isArray(record.citations)) {
    throw new Error('Invalid team bot response')
  }
  return {
    kind: record.kind,
    employeeId: teamBotId(record.employee_id),
    baseId: teamBotId(record.base_id),
    viewId: teamBotId(record.view_id),
    answer: stringValue(record.answer),
    citations: record.citations.map(safeTeamBotCitation),
    knowledgeWindowTruncated: booleanValue(record.knowledge_window_truncated),
    auditEventId: teamBotId(record.audit_event_id),
  }
}

const managedEmployeeStatuses = new Set<ManagedEmployeeStatus>(['draft', 'active', 'paused'])
const managedEmployeeAccessModes = new Set<ManagedEmployeeAccessMode>(['workspace', 'assigned'])
const managedEmployeeActions = new Set<ManagedEmployeeAction>(['summarize', 'draft_update'])
const managedEmployeeViewTypes = new Set<ManagedEmployeeViewType>(['grid', 'kanban', 'calendar', 'form'])
const managedEmployeeMemberRoles = new Set<ManagedEmployeeMemberRole>(['owner', 'admin', 'builder', 'operator', 'viewer'])

function assertManagedEmployeeKeys(record: Record<string, unknown>, keys: string[]): void {
  if (Object.keys(record).length !== keys.length || keys.some((key) => !(key in record))) {
    throw new Error('Invalid digital employee management response')
  }
}

function managedEmployeeId(value: unknown): string {
  const id = stringValue(value).trim()
  if (!id) throw new Error('Invalid digital employee management response')
  return id
}

function managedEmployeeCount(value: unknown): number {
  const count = numberValue(value)
  if (!Number.isInteger(count) || count < 0) throw new Error('Invalid digital employee management response')
  return count
}

function managedEmployeeVersion(value: unknown): number {
  const version = numberValue(value)
  if (!Number.isInteger(version) || version < 1) throw new Error('Invalid digital employee management response')
  return version
}

function managedEmployeeStatus(value: unknown): ManagedEmployeeStatus {
  const status = stringValue(value)
  if (!managedEmployeeStatuses.has(status as ManagedEmployeeStatus)) throw new Error('Invalid digital employee management response')
  return status as ManagedEmployeeStatus
}

function managedEmployeeAccessMode(value: unknown): ManagedEmployeeAccessMode {
  const accessMode = stringValue(value)
  if (!managedEmployeeAccessModes.has(accessMode as ManagedEmployeeAccessMode)) throw new Error('Invalid digital employee management response')
  return accessMode as ManagedEmployeeAccessMode
}

function managedEmployeeActionList(value: unknown): ManagedEmployeeAction[] {
  if (!Array.isArray(value)) throw new Error('Invalid digital employee management response')
  const actions = value.map((item) => stringValue(item))
  if (actions.some((action) => !managedEmployeeActions.has(action as ManagedEmployeeAction)) || new Set(actions).size !== actions.length) {
    throw new Error('Invalid digital employee management response')
  }
  return actions as ManagedEmployeeAction[]
}

function managedEmployeeIdList(value: unknown): string[] {
  if (!Array.isArray(value)) throw new Error('Invalid digital employee management response')
  const ids = value.map(managedEmployeeId)
  if (new Set(ids).size !== ids.length) throw new Error('Invalid digital employee management response')
  return ids
}

function managedEmployeeSummaryFromRecord(record: Record<string, unknown>): ManagedEmployeeSummary {
  return {
    id: managedEmployeeId(record.id),
    name: stringValue(record.name),
    description: stringValue(record.description),
    status: managedEmployeeStatus(record.status),
    accessMode: managedEmployeeAccessMode(record.access_mode),
    tableCount: managedEmployeeCount(record.table_count),
    viewCount: managedEmployeeCount(record.view_count),
    memberCount: managedEmployeeCount(record.member_count),
    version: managedEmployeeVersion(record.version),
  }
}

function safeManagedEmployeeSummary(value: unknown): ManagedEmployeeSummary {
  const record = jsonRecord(value)
  assertManagedEmployeeKeys(record, ['id', 'name', 'description', 'status', 'access_mode', 'table_count', 'view_count', 'member_count', 'version'])
  return managedEmployeeSummaryFromRecord(record)
}

function safeManagedEmployeeDetail(value: unknown): ManagedEmployeeDetail {
  const record = jsonRecord(value)
  assertManagedEmployeeKeys(record, [
    'id', 'name', 'description', 'status', 'access_mode', 'table_count', 'view_count', 'member_count', 'version',
    'base_id', 'telegram_alias', 'accessible_table_ids', 'accessible_view_ids', 'allowed_actions', 'member_ids',
  ])
  return {
    ...managedEmployeeSummaryFromRecord(record),
    baseId: managedEmployeeId(record.base_id),
    telegramAlias: nullableStringValue(record.telegram_alias),
    accessibleTableIds: managedEmployeeIdList(record.accessible_table_ids),
    accessibleViewIds: managedEmployeeIdList(record.accessible_view_ids),
    allowedActions: managedEmployeeActionList(record.allowed_actions),
    memberIds: managedEmployeeIdList(record.member_ids),
  }
}

function safeManagedEmployeeDirectory(value: unknown): ManagedEmployeeDirectory {
  const record = jsonRecord(value)
  assertManagedEmployeeKeys(record, ['base_id', 'employees', 'next_cursor', 'has_more'])
  if (!Array.isArray(record.employees)) throw new Error('Invalid digital employee management response')
  return {
    baseId: managedEmployeeId(record.base_id),
    employees: record.employees.map(safeManagedEmployeeSummary),
    nextCursor: nullableStringValue(record.next_cursor),
    hasMore: booleanValue(record.has_more),
  }
}

function safeManagedEmployeeManagementContext(value: unknown): ManagedEmployeeManagementContext {
  const record = jsonRecord(value)
  assertManagedEmployeeKeys(record, ['base', 'tables', 'views', 'members'])
  const base = jsonRecord(record.base)
  assertManagedEmployeeKeys(base, ['id', 'name'])
  if (!Array.isArray(record.tables) || !Array.isArray(record.views) || !Array.isArray(record.members)) {
    throw new Error('Invalid digital employee management response')
  }
  return {
    base: { id: managedEmployeeId(base.id), name: stringValue(base.name) },
    tables: record.tables.map((item) => {
      const table = jsonRecord(item)
      assertManagedEmployeeKeys(table, ['id', 'name'])
      return { id: managedEmployeeId(table.id), name: stringValue(table.name) }
    }),
    views: record.views.map((item) => {
      const view = jsonRecord(item)
      assertManagedEmployeeKeys(view, ['id', 'table_id', 'name', 'view_type'])
      const viewType = stringValue(view.view_type)
      if (!managedEmployeeViewTypes.has(viewType as ManagedEmployeeViewType)) throw new Error('Invalid digital employee management response')
      return { id: managedEmployeeId(view.id), tableId: managedEmployeeId(view.table_id), name: stringValue(view.name), viewType: viewType as ManagedEmployeeViewType }
    }),
    members: record.members.map((item) => {
      const member = jsonRecord(item)
      assertManagedEmployeeKeys(member, ['id', 'label', 'role'])
      const role = stringValue(member.role)
      if (!managedEmployeeMemberRoles.has(role as ManagedEmployeeMemberRole)) throw new Error('Invalid digital employee management response')
      return { id: managedEmployeeId(member.id), label: stringValue(member.label), role: role as ManagedEmployeeMemberRole }
    }),
  }
}

function safeManagedEmployeeLifecycleReceipt(value: unknown): ManagedEmployeeLifecycleReceipt {
  const record = jsonRecord(value)
  assertManagedEmployeeKeys(record, ['id', 'status', 'version', 'audit_event_id'])
  const status = record.status
  if (status !== 'active' && status !== 'paused') throw new Error('Invalid digital employee management response')
  return {
    id: managedEmployeeId(record.id),
    status,
    version: managedEmployeeVersion(record.version),
    auditEventId: managedEmployeeId(record.audit_event_id),
  }
}

function safeTelegramDeepLinkResolution(value: unknown): TelegramDeepLinkResolution {
  const record = jsonRecord(value)
  if (record.outcome === 'recovery') {
    if (Object.keys(record).length !== 1) throw new Error('Invalid Telegram deep-link response')
    return { outcome: 'recovery' }
  }
  if (record.outcome !== 'resolved') throw new Error('Invalid Telegram deep-link response')
  const destination = jsonRecord(record.destination)
  const kind = stringValue(destination.kind)
  if (!['base', 'view', 'record', 'record_change_draft'].includes(kind)) throw new Error('Invalid Telegram deep-link response')
  const allowedKeys = new Set(['kind', 'workspace_id', 'base_id', 'table_id', 'view_id', 'record_id', 'draft_id'])
  if (Object.keys(destination).some((key) => !allowedKeys.has(key))) throw new Error('Invalid Telegram deep-link response')
  const optionalId = (key: string): string | undefined => destination[key] === undefined ? undefined : stringValue(destination[key])
  return {
    outcome: 'resolved',
    destination: {
      kind: kind as TelegramDeepLinkDestination['kind'],
      workspaceId: stringValue(destination.workspace_id),
      ...(optionalId('base_id') ? { baseId: optionalId('base_id') } : {}),
      ...(optionalId('table_id') ? { tableId: optionalId('table_id') } : {}),
      ...(optionalId('view_id') ? { viewId: optionalId('view_id') } : {}),
      ...(optionalId('record_id') ? { recordId: optionalId('record_id') } : {}),
      ...(optionalId('draft_id') ? { draftId: optionalId('draft_id') } : {}),
    },
  }
}

function safeTemplateSummary(value: unknown): TemplateSummary {
  const record = jsonRecord(value)
  return {
    id: stringValue(record.id),
    name: stringValue(record.name),
    category: stringValue(record.category),
    description: stringValue(record.description),
    version: stringValue(record.version),
    status: stringValue(record.status),
  }
}

function safeImportScalarFieldType(value: unknown): ImportScalarFieldType {
  if (typeof value !== 'string' || !importScalarFieldTypes.has(value as ImportScalarFieldType)) throw new Error('Invalid import response')
  return value as ImportScalarFieldType
}

function safeImportMapping(value: unknown): ImportMapping {
  const record = jsonRecord(value)
  const name = record.name
  if (name !== undefined && typeof name !== 'string') throw new Error('Invalid import response')
  return {
    sourceKey: stringValue(record.source_key),
    targetKey: stringValue(record.target_key),
    fieldType: safeImportScalarFieldType(record.field_type),
    ...(typeof name === 'string' ? { name } : {}),
  }
}

function safePreviewRow(value: unknown): Record<string, unknown> {
  const record = jsonRecord(value)
  for (const item of Object.values(record)) {
    if (item !== null && typeof item !== 'string' && typeof item !== 'number' && typeof item !== 'boolean') throw new Error('Invalid import response')
  }
  return record
}

function safeImportPreview(value: unknown): ImportPreview {
  const record = jsonRecord(value)
  const sourceType = record.source_type
  const status = record.status
  if (sourceType !== 'csv' && sourceType !== 'excel') throw new Error('Invalid import response')
  if (status !== 'awaiting_confirmation' && status !== 'committed') throw new Error('Invalid import response')
  if (!Array.isArray(record.detected_schema) || !Array.isArray(record.preview_rows) || !Array.isArray(record.mapping)) throw new Error('Invalid import response')
  return {
    id: stringValue(record.id),
    workspaceId: stringValue(record.workspace_id),
    baseId: nullableStringValue(record.base_id),
    sourceType,
    detectedSchema: record.detected_schema.map((item) => {
      const field = jsonRecord(item)
      return { key: stringValue(field.key), name: stringValue(field.name), fieldType: safeImportScalarFieldType(field.field_type) }
    }),
    previewRows: record.preview_rows.map(safePreviewRow),
    mapping: record.mapping.map(safeImportMapping),
    status,
  }
}

function safeTemplateInstallationReceipt(value: unknown): TemplateInstallationReceipt {
  const record = jsonRecord(value)
  return {
    id: stringValue(record.id),
    workspaceId: stringValue(record.workspace_id),
    baseId: stringValue(record.base_id),
    templateId: stringValue(record.template_id),
    templateVersion: stringValue(record.template_version),
  }
}

function safeImportCommitReceipt(value: unknown): ImportCommitReceipt {
  const record = jsonRecord(value)
  const resourceMap = jsonRecord(record.resource_map)
  if (record.status !== 'committed') throw new Error('Invalid import response')
  return {
    importJobId: stringValue(record.import_job_id),
    status: 'committed',
    baseId: stringValue(resourceMap.base_id),
    tableId: stringValue(resourceMap.table_id),
  }
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) throw new Error('Invalid view response')
  return [...value] as string[]
}

function viewType(value: unknown): ViewType {
  if (value === 'grid' || value === 'kanban' || value === 'calendar' || value === 'form') return value
  throw new Error('Invalid view response')
}

function safeViewSummary(value: unknown): SafeViewSummary {
  const source = jsonRecord(value)
  const scope = stringValue(source.scope)
  const access = stringValue(source.caller_access_level)
  if (scope !== 'system_default' && scope !== 'private' && scope !== 'restricted') throw new Error('Invalid view response')
  if (access !== 'owner' && access !== 'editor' && access !== 'viewer' && access !== 'system_default') throw new Error('Invalid view response')
  return {
    id: stringValue(source.id), base_id: stringValue(source.base_id), table_id: stringValue(source.table_id),
    name: stringValue(source.name), view_type: viewType(source.view_type), scope, caller_access_level: access,
    status: stringValue(source.status), is_default: booleanValue(source.is_default),
  }
}

function safeBaseViewSummary(value: unknown): ViewSummary {
  const source = jsonRecord(value)
  const summary: ViewSummary = {
    id: stringValue(source.id),
    base_id: stringValue(source.base_id),
    table_id: source.table_id === null ? null : stringValue(source.table_id),
    name: stringValue(source.name),
    view_type: stringValue(source.view_type),
    status: stringValue(source.status),
  }
  if (source.scope !== undefined || source.caller_access_level !== undefined || source.is_default !== undefined) {
    const safe = safeViewSummary(source)
    return { ...summary, scope: safe.scope, caller_access_level: safe.caller_access_level, is_default: safe.is_default }
  }
  return summary
}

function safeViewField(value: unknown): SafeViewField {
  const source = jsonRecord(value)
  return {
    field_id: stringValue(source.field_id), key: stringValue(source.key), label: stringValue(source.label), field_type: stringValue(source.field_type),
    filter_operators: stringArray(source.filter_operators), filter_values: stringArray(source.filter_values), sortable: booleanValue(source.sortable),
    groupable: booleanValue(source.groupable), form_eligible: booleanValue(source.form_eligible),
  }
}

function safeViewMember(value: unknown): SafeViewMember {
  const source = jsonRecord(value)
  const accessLevel = stringValue(source.access_level)
  if (accessLevel !== 'editor' && accessLevel !== 'viewer') throw new Error('Invalid view response')
  return { user_id: stringValue(source.user_id), label: stringValue(source.label), access_level: accessLevel }
}

function safeViewMemberCandidate(value: unknown): SafeViewMemberCandidate {
  const source = jsonRecord(value)
  return { id: stringValue(source.id), label: stringValue(source.label) }
}

function safeFilterValue(value: unknown): ViewFilterValue {
  if (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
  return stringArray(value)
}

function safeViewPresentation(value: unknown): SafeViewPresentation {
  const source = jsonRecord(value)
  if (!Array.isArray(source.filters) || !Array.isArray(source.sort_rules)) throw new Error('Invalid view response')
  const filters = source.filters.map((item) => {
    const filter = jsonRecord(item)
    return { field_key: stringValue(filter.field_key), operator: stringValue(filter.operator), value: safeFilterValue(filter.value) }
  })
  const sortRules = source.sort_rules.map((item) => {
    const rule = jsonRecord(item)
    const rawDirection = stringValue(rule.direction)
    if (rawDirection !== 'asc' && rawDirection !== 'desc') throw new Error('Invalid view response')
    const direction: 'asc' | 'desc' = rawDirection
    return { field_key: stringValue(rule.field_key), direction }
  })
  return {
    view_id: stringValue(source.view_id), table_id: stringValue(source.table_id), view_type: viewType(source.view_type),
    visible_field_keys: stringArray(source.visible_field_keys), filters, sort_rules: sortRules,
    group_by_field_key: source.group_by_field_key === null ? null : stringValue(source.group_by_field_key),
    date_field_key: source.date_field_key === null ? null : stringValue(source.date_field_key),
    form_field_keys: stringArray(source.form_field_keys),
  }
}

function safeViewBuilderContext(value: unknown): ViewBuilderContext {
  const source = jsonRecord(value)
  const table = jsonRecord(source.table)
  if (!Array.isArray(source.fields) || !Array.isArray(source.views) || !Array.isArray(source.member_candidates)) throw new Error('Invalid view response')
  return {
    table: { id: stringValue(table.id), base_id: stringValue(table.base_id), name: stringValue(table.name), key: stringValue(table.key), status: stringValue(table.status) },
    fields: source.fields.map(safeViewField), views: source.views.map(safeViewSummary),
    member_candidates: source.member_candidates.map(safeViewMemberCandidate),
  }
}

function safeViewBuilder(value: unknown): ViewBuilderResponse {
  const source = jsonRecord(value)
  if (!Array.isArray(source.fields) || !Array.isArray(source.members)) throw new Error('Invalid view response')
  return {
    view: safeViewSummary(source.view), presentation: safeViewPresentation(source.presentation),
    fields: source.fields.map(safeViewField), members: source.members.map(safeViewMember),
    version: numberValue(source.version), can_edit_presentation: booleanValue(source.can_edit_presentation),
    can_replace_members: booleanValue(source.can_replace_members),
  }
}

function safeViewInitializationReceipt(value: unknown): ViewInitializationReceipt {
  const source = jsonRecord(value)
  return { view: safeViewSummary(source.view), affected_view_ids: stringArray(source.affected_view_ids) }
}

function safeViewPresentationReceipt(value: unknown): ViewPresentationMutationReceipt {
  const source = jsonRecord(value)
  return { view: safeViewSummary(source.view), version: numberValue(source.version) }
}

function safeViewMembersReceipt(value: unknown): ViewMemberReplaceReceipt {
  const source = jsonRecord(value)
  if (!Array.isArray(source.members)) throw new Error('Invalid view response')
  return { view: safeViewSummary(source.view), members: source.members.map(safeViewMember), version: numberValue(source.version) }
}

function writeJson<T>(path: string, method: 'PATCH' | 'PUT', payload: unknown): Promise<T> {
  return getJson<T>(path, {
    method,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

function writeIdempotentJson<T>(path: string, method: 'PATCH' | 'PUT', payload: unknown, idempotencyKey: string): Promise<T> {
  return getJson<T>(path, {
    method,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify(payload),
  })
}

export function toSafeViewError(error: unknown): string {
  const source = error && typeof error === 'object' ? error as { code?: unknown } : undefined
  const code = source?.code
  return typeof code === 'string' && safeViewErrorCodes.has(code as SafeViewErrorCode)
    ? safeViewErrorCopy[code as SafeViewErrorCode]
    : '视图请求失败，请稍后重试。'
}

export const api = {
  setTelegramInitData,
  bootstrap: (init?: RequestInit) => getJson<BootstrapResponse>('/mini-app/bootstrap', init),
  createBrowserHandoff: async (): Promise<BrowserHandoff> => safeBrowserHandoff(
    await getJson<unknown>('/mini-app/browser-handoffs', { method: 'POST' }),
  ),
  resolveTelegramDeepLink: async (startParam: string, init?: RequestInit): Promise<TelegramDeepLinkResolution> => safeTelegramDeepLinkResolution(
    await getJson<unknown>('/mini-app/telegram/deep-links/resolve', {
      ...init,
      method: 'POST',
      headers: { ...Object.fromEntries(new Headers(init?.headers).entries()), 'Content-Type': 'application/json' },
      body: JSON.stringify({ start_param: startParam }),
    }),
  ),
  workspaceHome: (workspaceId: string, init?: RequestInit) => getJson<WorkspaceHome>(`/workspaces/${workspaceId}/home`, init),
  workspaceBases: async (workspaceId: string, init?: RequestInit): Promise<{ bases: BaseSummary[] }> => {
    const response = jsonRecord(await getJson<unknown>(`/workspaces/${encodeURIComponent(workspaceId)}/bases`, init))
    if (!Array.isArray(response.bases)) throw new Error('Invalid import response')
    return { bases: response.bases.map((item) => {
      const base = jsonRecord(item)
      return { id: stringValue(base.id), name: stringValue(base.name), source_type: stringValue(base.source_type), ...(typeof base.status === 'string' ? { status: base.status } : {}) }
    }) }
  },
  listGovernanceMembers: async (
    workspaceId: string,
    cursor: string | null = null,
    init?: RequestInit,
  ): Promise<GovernanceMemberPage> => {
    const parameters = new URLSearchParams({ limit: '50' })
    if (cursor) parameters.set('cursor', cursor)
    return safeGovernanceMemberPage(await getJson<unknown>(
      `/mini-app/workspaces/${encodeURIComponent(workspaceId)}/governance/members?${parameters.toString()}`,
      init,
    ))
  },
  listGovernanceAuditEvents: async (
    baseId: string,
    cursor: string | null = null,
    init?: RequestInit,
  ): Promise<GovernanceAuditPage> => {
    const parameters = new URLSearchParams({ limit: '50' })
    if (cursor) parameters.set('cursor', cursor)
    return safeGovernanceAuditPage(await getJson<unknown>(
      `/mini-app/bases/${encodeURIComponent(baseId)}/governance/audit-events?${parameters.toString()}`,
      init,
    ))
  },
  listGovernanceEditableMembers: async (
    workspaceId: string,
    cursor: string | null = null,
    init?: RequestInit,
  ): Promise<GovernanceEditableMemberPage> => {
    const parameters = new URLSearchParams({ limit: '50' })
    if (cursor) parameters.set('cursor', cursor)
    return safeGovernanceEditableMemberPage(await getJson<unknown>(
      `/mini-app/workspaces/${encodeURIComponent(workspaceId)}/governance/member-editor?${parameters.toString()}`,
      init,
    ))
  },
  changeGovernanceMemberRole: async (
    workspaceId: string,
    memberId: string,
    role: GovernanceAssignableRole,
    expectedVersion: number,
    idempotencyKey: string,
  ): Promise<GovernanceMemberRoleReceipt> => safeGovernanceMemberRoleReceipt(
    await writeIdempotentJson<unknown>(
      `/mini-app/workspaces/${encodeURIComponent(workspaceId)}/governance/members/${encodeURIComponent(memberId)}/role`,
      'PATCH',
      { role, expected_version: expectedVersion },
      idempotencyKey,
    ),
  ),
  listGovernanceFieldPermissions: async (
    tableId: string,
    init?: RequestInit,
  ): Promise<GovernanceFieldPermissionPage> => safeGovernanceFieldPermissionPage(
    await getJson<unknown>(`/mini-app/tables/${encodeURIComponent(tableId)}/governance/field-permissions`, init),
  ),
  replaceGovernanceFieldPermissionPolicy: async (
    tableId: string,
    fieldId: string,
    policy: GovernanceFieldPermissionPolicy,
    expectedPermissionVersion: number,
    idempotencyKey: string,
  ): Promise<GovernanceFieldPermissionReceipt> => safeGovernanceFieldPermissionReceipt(
    await writeIdempotentJson<unknown>(
      `/mini-app/tables/${encodeURIComponent(tableId)}/governance/fields/${encodeURIComponent(fieldId)}/permission-policy`,
      'PUT',
      { expected_permission_version: expectedPermissionVersion, policy },
      idempotencyKey,
    ),
  ),
  getDigitalEmployeeManagementContext: async (
    baseId: string,
    init?: RequestInit,
  ): Promise<ManagedEmployeeManagementContext> => safeManagedEmployeeManagementContext(
    await getJson<unknown>(`/mini-app/bases/${encodeURIComponent(baseId)}/digital-employee-management-context`, init),
  ),
  listManagedDigitalEmployees: async (
    baseId: string,
    cursor: string | null = null,
    init?: RequestInit,
  ): Promise<ManagedEmployeeDirectory> => {
    const parameters = new URLSearchParams({ limit: '50' })
    if (cursor) parameters.set('cursor', cursor)
    return safeManagedEmployeeDirectory(await getJson<unknown>(
      `/mini-app/bases/${encodeURIComponent(baseId)}/digital-employees/management?${parameters.toString()}`,
      init,
    ))
  },
  createManagedDigitalEmployee: async (
    baseId: string,
    values: ManagedEmployeeCreateValues,
    idempotencyKey: string,
  ): Promise<ManagedEmployeeDetail> => safeManagedEmployeeDetail(
    await postJson<unknown>(
      `/mini-app/bases/${encodeURIComponent(baseId)}/digital-employees/management`,
      { name: values.name, description: values.description, telegram_alias: values.telegramAlias },
      idempotencyKey,
    ),
  ),
  getManagedDigitalEmployee: async (
    employeeId: string,
    init?: RequestInit,
  ): Promise<ManagedEmployeeDetail> => safeManagedEmployeeDetail(
    await getJson<unknown>(`/mini-app/digital-employees/${encodeURIComponent(employeeId)}/management`, init),
  ),
  updateManagedDigitalEmployee: async (
    employeeId: string,
    values: ManagedEmployeeUpdateValues,
    expectedVersion: number,
  ): Promise<ManagedEmployeeDetail> => {
    const payload: Record<string, unknown> = { expected_version: expectedVersion }
    if (values.name !== undefined) payload.name = values.name
    if (values.description !== undefined) payload.description = values.description
    if (Object.prototype.hasOwnProperty.call(values, 'telegramAlias')) payload.telegram_alias = values.telegramAlias
    if (values.accessibleTableIds !== undefined) payload.accessible_table_ids = values.accessibleTableIds
    if (values.accessibleViewIds !== undefined) payload.accessible_view_ids = values.accessibleViewIds
    if (values.allowedActions !== undefined) payload.allowed_actions = values.allowedActions
    if (values.accessMode !== undefined) payload.access_mode = values.accessMode
    return safeManagedEmployeeDetail(await writeJson<unknown>(
      `/mini-app/digital-employees/${encodeURIComponent(employeeId)}/management`,
      'PATCH',
      payload,
    ))
  },
  replaceManagedDigitalEmployeeGrants: async (
    employeeId: string,
    memberIds: string[],
    expectedVersion: number,
    idempotencyKey: string,
  ): Promise<ManagedEmployeeDetail> => safeManagedEmployeeDetail(
    await writeIdempotentJson<unknown>(
      `/mini-app/digital-employees/${encodeURIComponent(employeeId)}/member-grants`,
      'PUT',
      { expected_version: expectedVersion, member_ids: memberIds },
      idempotencyKey,
    ),
  ),
  activateManagedDigitalEmployee: async (
    employeeId: string,
    expectedVersion: number,
    idempotencyKey: string,
  ): Promise<ManagedEmployeeLifecycleReceipt> => safeManagedEmployeeLifecycleReceipt(
    await postJson<unknown>(
      `/mini-app/digital-employees/${encodeURIComponent(employeeId)}/activate`,
      { expected_version: expectedVersion },
      idempotencyKey,
    ),
  ),
  pauseManagedDigitalEmployee: async (
    employeeId: string,
    expectedVersion: number,
    idempotencyKey: string,
  ): Promise<ManagedEmployeeLifecycleReceipt> => safeManagedEmployeeLifecycleReceipt(
    await postJson<unknown>(
      `/mini-app/digital-employees/${encodeURIComponent(employeeId)}/pause`,
      { expected_version: expectedVersion },
      idempotencyKey,
    ),
  ),
  listS5Contacts: async (workspaceId: string, cursor: string | null = null, init?: RequestInit): Promise<S5ContactPage> => {
    const parameters = new URLSearchParams({ limit: '50' })
    if (cursor) parameters.set('cursor', cursor)
    return safeS5ContactPage(await getJson<unknown>(`/mini-app/workspaces/${encodeURIComponent(workspaceId)}/digital-employee-contacts?${parameters.toString()}`, init))
  },
  listTeamBotContacts: async (workspaceId: string, cursor: string | null = null, init?: RequestInit): Promise<TeamBotContactPage> => {
    const parameters = new URLSearchParams({ limit: '50' })
    if (cursor) parameters.set('cursor', cursor)
    return safeTeamBotContactPage(await getJson<unknown>(`/mini-app/workspaces/${encodeURIComponent(workspaceId)}/team-bot-contacts?${parameters.toString()}`, init))
  },
  getTeamBotKnowledgeContexts: async (employeeId: string, cursor: string | null = null, init?: RequestInit): Promise<TeamBotKnowledgeContextPage> => {
    const parameters = new URLSearchParams({ limit: '50' })
    if (cursor) parameters.set('cursor', cursor)
    return safeTeamBotKnowledgeContextPage(await getJson<unknown>(`/mini-app/team-bots/${encodeURIComponent(employeeId)}/knowledge-contexts?${parameters.toString()}`, init))
  },
  getTeamBotKnowledgeContextView: async (employeeId: string, viewId: string, init?: RequestInit): Promise<TeamBotSelectedView> => safeTeamBotSelectedView(
    await getJson<unknown>(`/mini-app/team-bots/${encodeURIComponent(employeeId)}/knowledge-contexts/${encodeURIComponent(viewId)}`, init),
  ),
  summarizeTeamBot: async (employeeId: string, request: TeamBotSummaryRequest, idempotencyKey: string, init?: RequestInit): Promise<TeamBotSummary> => {
    const instruction = request.instruction?.trim()
    if (instruction && instruction.length > 600) throw new Error('Team Bot instruction is too long')
    return safeTeamBotSummary(await postJson<unknown>(
      `/mini-app/team-bots/${encodeURIComponent(employeeId)}/summaries`,
      {
        base_id: request.baseId,
        view_id: request.viewId,
        ...(instruction ? { instruction } : {}),
      },
      idempotencyKey,
      init,
    ))
  },
  getAssistantContext: async (employeeId: string, cursor: string | null = null, init?: RequestInit): Promise<AssistantContextPage> => {
    const parameters = new URLSearchParams({ limit: '50' })
    if (cursor) parameters.set('cursor', cursor)
    return safeAssistantContextPage(await getJson<unknown>(`/mini-app/digital-employees/${encodeURIComponent(employeeId)}/assistant-context?${parameters.toString()}`, init))
  },
  getAssistantSelectedView: async (employeeId: string, viewId: string, init?: RequestInit): Promise<AssistantSelectedView> => safeAssistantSelectedView(
    await getJson<unknown>(`/mini-app/digital-employees/${encodeURIComponent(employeeId)}/assistant-context/views/${encodeURIComponent(viewId)}`, init),
  ),
  invokeS5Employee: async (employeeId: string, request: S5InvocationRequest, idempotencyKey?: string): Promise<S5InvocationResult> => {
    if (request.intent === 'draft_update' && !idempotencyKey) throw new Error('Idempotency key is required')
    return safeS5InvocationResult(await postJson<unknown>(
      `/mini-app/digital-employees/${encodeURIComponent(employeeId)}/invocations`,
      {
        intent: request.intent,
        base_id: request.baseId,
        view_id: request.viewId,
        ...(request.intent === 'draft_update' ? { record_id: request.recordId } : {}),
        ...(request.instruction ? { instruction: request.instruction } : {}),
      },
      idempotencyKey ?? crypto.randomUUID(),
    ))
  },
  queryStage08Assistant: async (request: Stage08AssistantQuery, idempotencyKey: string, init?: RequestInit): Promise<Stage08AssistantSafeView> => {
    const query = request.query.trim()
    const workspaceId = request.workspaceId.trim()
    const employeeId = request.employeeId.trim()
    const targetRecordId = request.targetRecordId?.trim() || null
    if (!query || query.length > 600 || !workspaceId || workspaceId.length > 200 || !employeeId || employeeId.length > 200 || !idempotencyKey || !stage08Intents.has(request.intent) || !stage08RequestedActions.has(request.requestedAction)) throw new Error('Invalid Stage08 collaboration request')
    if ((request.requestedAction === 'draft_update') !== Boolean(targetRecordId)) throw new Error('Invalid Stage08 collaboration request')
    return safeStage08AssistantSafeView(await postJson<unknown>('/api/stage08/assistant/query', {
      workspace_id: workspaceId,
      employee_id: employeeId,
      intent: request.intent,
      query,
      requested_action: request.requestedAction,
      ...(targetRecordId ? { target_record_id: targetRecordId } : {}),
      idempotency_key: idempotencyKey,
    }, idempotencyKey, init))
  },
  listStage08Memory: async (workspaceId: string, init?: RequestInit): Promise<Stage08MemoryPage> => safeStage08MemoryPage(
    await getJson<unknown>(`/api/stage08/memory?${new URLSearchParams({ workspace_id: workspaceId, status: 'active' }).toString()}`, init),
  ),
  getS5Draft: async (draftId: string, init?: RequestInit): Promise<S5DraftDetail> => safeS5DraftDetail(
    await getJson<unknown>(`/mini-app/drafts/${encodeURIComponent(draftId)}`, init),
  ),
  confirmS5Draft: async (draftId: string, expectedVersion: number, idempotencyKey: string): Promise<S5TerminalReceipt> => safeS5TerminalReceipt(
    await postJson<unknown>(`/mini-app/drafts/${encodeURIComponent(draftId)}/confirm`, { expected_version: expectedVersion }, idempotencyKey),
  ),
  rejectS5Draft: async (draftId: string, expectedVersion: number, idempotencyKey: string): Promise<S5TerminalReceipt> => safeS5TerminalReceipt(
    await postJson<unknown>(`/mini-app/drafts/${encodeURIComponent(draftId)}/reject`, { expected_version: expectedVersion }, idempotencyKey),
  ),
  listTemplates: async (init?: RequestInit): Promise<TemplateSummary[]> => {
    const response = jsonRecord(await getJson<unknown>('/templates', init))
    if (!Array.isArray(response.templates)) throw new Error('Invalid import response')
    return response.templates.map(safeTemplateSummary)
  },
  installTemplate: async (workspaceId: string, templateId: string, installedByUserId: string, idempotencyKey: string): Promise<TemplateInstallationReceipt> => safeTemplateInstallationReceipt(
    await postJson<unknown>(`/workspaces/${encodeURIComponent(workspaceId)}/template-installations`, {
      template_id: templateId,
      installed_by_user_id: installedByUserId,
    }, idempotencyKey),
  ),
  saveBaseAsTemplate: async (baseId: string, values: SaveTemplateValues): Promise<TemplateSummary> => safeTemplateSummary(
    await getJson<unknown>(`/bases/${encodeURIComponent(baseId)}/templates`, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: values.name, category: values.category, description: values.description, created_by_user_id: values.createdByUserId }),
    }),
  ),
  createImport: async (workspaceId: string, values: CreateImportValues, idempotencyKey: string): Promise<ImportPreview> => safeImportPreview(
    await postJson<unknown>(`/workspaces/${encodeURIComponent(workspaceId)}/imports`, {
      source_type: values.sourceType,
      file_name: values.fileName,
      content: values.content,
      created_by_user_id: values.createdByUserId,
      ...(values.baseId ? { base_id: values.baseId } : {}),
    }, idempotencyKey),
  ),
  importJob: async (importJobId: string, init?: RequestInit): Promise<ImportPreview> => safeImportPreview(
    await getJson<unknown>(`/imports/${encodeURIComponent(importJobId)}`, init),
  ),
  commitImport: async (importJobId: string, values: CommitImportValues, idempotencyKey: string): Promise<ImportCommitReceipt> => safeImportCommitReceipt(
    await postJson<unknown>(`/imports/${encodeURIComponent(importJobId)}/commit`, {
      base_name: values.baseName,
      table_name: values.tableName,
      table_key: values.tableKey,
      ...(values.fieldMapping ? { field_mapping: values.fieldMapping.map((item) => ({ source_key: item.sourceKey, target_key: item.targetKey, field_type: item.fieldType, ...(item.name ? { name: item.name } : {}) })) } : {}),
    }, idempotencyKey),
  ),
  initializeBase: (workspaceId: string, values: { baseName: string; tableName: string }, idempotencyKey: string) => postJson<BuilderInitializationReceipt>(`/workspaces/${workspaceId}/base-initializations`, { base_name: values.baseName, table_name: values.tableName }, idempotencyKey),
  initializeTable: (baseId: string, values: { tableName: string }, idempotencyKey: string) => postJson<BuilderInitializationReceipt>(`/bases/${baseId}/table-initializations`, { table_name: values.tableName }, idempotencyKey),
  initializeField: (tableId: string, values: FieldBuilderValues, idempotencyKey: string) => postJson<FieldInitializationReceipt>(`/tables/${tableId}/field-initializations`, {
    name: values.name,
    field_type: values.fieldType,
    required: values.required,
    ...(choiceFieldTypes.has(values.fieldType) ? { choices: values.choices } : {}),
  }, idempotencyKey),
  initializeRelationField: (tableId: string, values: RelationFieldInitializationValues, idempotencyKey: string) => postJson<FieldInitializationReceipt>(`/tables/${tableId}/relation-field-initializations`, {
    name: values.name,
    target_table_id: values.targetTableId,
    required: values.required,
  }, idempotencyKey),
  initializeLookupField: (tableId: string, values: LookupFieldInitializationValues, idempotencyKey: string) => postJson<FieldInitializationReceipt>(`/tables/${tableId}/lookup-field-initializations`, {
    name: values.name,
    source_relation_field_id: values.sourceRelationFieldId,
    target_field_id: values.targetFieldId,
    aggregation: values.aggregation,
  }, idempotencyKey),
  baseTables: (baseId: string, init?: RequestInit) => getJson<{ tables: PlatformTable[] }>(`/bases/${baseId}/tables`, init),
  baseViews: async (baseId: string, init?: RequestInit): Promise<{ views: ViewSummary[] }> => {
    const response = jsonRecord(await getJson<unknown>(`/bases/${baseId}/views`, init))
    if (!Array.isArray(response.views)) throw new Error('Invalid view response')
    return { views: response.views.map(safeBaseViewSummary) }
  },
  tableSchema: (tableId: string, init?: RequestInit) => getJson<TableSchema>(`/tables/${tableId}/schema`, init),
  viewPresentation: (viewId: string, init?: RequestInit) => getJson<ViewPresentation>(`/views/${viewId}/presentation`, init),
  viewRecords: (viewId: string, cursor?: string, init?: RequestInit) => getJson<ViewRecords>(`/views/${viewId}/records${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`, init),
  recordDetail: (recordId: string, init?: RequestInit) => getJson<RecordDetail>(`/records/${recordId}`, init),
  relationCandidates: async (fieldId: string, query: string | undefined, cursor: string | undefined, init?: RequestInit): Promise<RelationCandidatePage> => {
    const parameters = new URLSearchParams()
    if (query) parameters.set('q', query)
    if (cursor) parameters.set('cursor', cursor)
    const suffix = parameters.size > 0 ? `?${parameters.toString()}` : ''
    const page = await getJson<RelationCandidatePage>(`/fields/${fieldId}/relation-candidates${suffix}`, init)
    return {
      field_id: page.field_id,
      records: page.records.map(({ id, label }) => ({ id, label })),
      next_cursor: page.next_cursor,
      has_more: page.has_more,
    }
  },
  createForm: (tableId: string, init?: RequestInit) => getJson<CreateForm>(`/tables/${tableId}/create-form`, init),
  createRecord: (tableId: string, values: Record<string, unknown>) => getJson<RecordDetail>(`/tables/${tableId}/records`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ values }),
  }),
  updateRecord: (recordId: string, values: Record<string, unknown>, expectedVersion: number) => getJson<RecordDetail>(`/records/${recordId}`, {
    method: 'PATCH',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ values, expected_version: expectedVersion }),
  }),
  viewBuilderContext: async (tableId: string, init?: RequestInit): Promise<ViewBuilderContext> => safeViewBuilderContext(
    await getJson<unknown>(`/tables/${encodeURIComponent(tableId)}/view-builder-context`, init),
  ),
  initializeView: async (tableId: string, request: ViewInitializationRequest, idempotencyKey: string): Promise<ViewInitializationReceipt> => safeViewInitializationReceipt(
    await postJson<unknown>(`/tables/${encodeURIComponent(tableId)}/view-initializations`, request, idempotencyKey),
  ),
  viewBuilder: async (viewId: string, init?: RequestInit): Promise<ViewBuilderResponse> => safeViewBuilder(
    await getJson<unknown>(`/views/${encodeURIComponent(viewId)}/builder`, init),
  ),
  patchViewPresentation: async (viewId: string, request: ViewPresentationPatchRequest): Promise<ViewPresentationMutationReceipt> => safeViewPresentationReceipt(
    await writeJson<unknown>(`/views/${encodeURIComponent(viewId)}/presentation`, 'PATCH', request),
  ),
  replaceViewMembers: async (viewId: string, request: ViewMemberReplaceRequest): Promise<ViewMemberReplaceReceipt> => safeViewMembersReceipt(
    await writeJson<unknown>(`/views/${encodeURIComponent(viewId)}/members`, 'PUT', request),
  ),
}
import type { FieldBuilderValues } from './FieldBuilderPanel'
