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

export type WorkspaceCapabilities = {
  can_read_bases: boolean
  can_manage_workspace: boolean
  can_manage_schema: boolean
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
  | 'template_not_found'
  | 'idempotency_conflict'
  | 'idempotency_in_progress'
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
  'template_not_found',
  'idempotency_conflict',
  'idempotency_in_progress',
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

async function getJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
    ...init,
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

const importScalarFieldTypes = new Set<ImportScalarFieldType>(['text', 'number', 'date', 'checkbox'])

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

export function toSafeViewError(error: unknown): string {
  const source = error && typeof error === 'object' ? error as { code?: unknown } : undefined
  const code = source?.code
  return typeof code === 'string' && safeViewErrorCodes.has(code as SafeViewErrorCode)
    ? safeViewErrorCopy[code as SafeViewErrorCode]
    : '视图请求失败，请稍后重试。'
}

export const api = {
  bootstrap: (init?: RequestInit) => getJson<BootstrapResponse>('/mini-app/bootstrap', init),
  workspaceHome: (workspaceId: string, init?: RequestInit) => getJson<WorkspaceHome>(`/workspaces/${workspaceId}/home`, init),
  workspaceBases: async (workspaceId: string, init?: RequestInit): Promise<{ bases: BaseSummary[] }> => {
    const response = jsonRecord(await getJson<unknown>(`/workspaces/${encodeURIComponent(workspaceId)}/bases`, init))
    if (!Array.isArray(response.bases)) throw new Error('Invalid import response')
    return { bases: response.bases.map((item) => {
      const base = jsonRecord(item)
      return { id: stringValue(base.id), name: stringValue(base.name), source_type: stringValue(base.source_type), ...(typeof base.status === 'string' ? { status: base.status } : {}) }
    }) }
  },
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
