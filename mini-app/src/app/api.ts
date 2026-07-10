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
export type ViewSummary = { id: string; base_id: string; table_id: string | null; name: string; view_type: string; status: string }
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
export type TableSchema = { table: { id: string; name: string; key: string }; fields: SafeTableField[] }
export type ViewRecords = { view_id: string; records: { id: string; fields: Record<string, unknown> }[]; next_cursor: string | null; has_more: boolean }
export type ViewPresentation = { view_id: string; table_id: string; view_type: string; visible_field_keys: string[]; group_by_field_key: string | null; date_field_key: string | null; form_field_keys: string[] }
export type RecordDetail = { id: string; table_id: string; values: Record<string, unknown>; record_status: string; version: number }
export type CreateForm = { table_id: string; can_create: boolean; fields: { key: string; name: string; field_type: string; required: boolean; options: Record<string, unknown>; order_index: number }[] }

export type SafeApiErrorCode = 'duplicate_field_name'

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

async function safeErrorCode(response: Response): Promise<SafeApiErrorCode | undefined> {
  try {
    const body: unknown = await response.json()
    if (!body || typeof body !== 'object' || !('detail' in body)) return undefined
    const detail = body.detail
    if (!detail || typeof detail !== 'object' || !('code' in detail)) return undefined
    return detail.code === 'duplicate_field_name' ? detail.code : undefined
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

export const api = {
  bootstrap: (init?: RequestInit) => getJson<BootstrapResponse>('/mini-app/bootstrap', init),
  workspaceHome: (workspaceId: string, init?: RequestInit) => getJson<WorkspaceHome>(`/workspaces/${workspaceId}/home`, init),
  initializeBase: (workspaceId: string, values: { baseName: string; tableName: string }, idempotencyKey: string) => postJson<BuilderInitializationReceipt>(`/workspaces/${workspaceId}/base-initializations`, { base_name: values.baseName, table_name: values.tableName }, idempotencyKey),
  initializeTable: (baseId: string, values: { tableName: string }, idempotencyKey: string) => postJson<BuilderInitializationReceipt>(`/bases/${baseId}/table-initializations`, { table_name: values.tableName }, idempotencyKey),
  initializeField: (tableId: string, values: FieldBuilderValues, idempotencyKey: string) => postJson<FieldInitializationReceipt>(`/tables/${tableId}/field-initializations`, {
    name: values.name,
    field_type: values.fieldType,
    required: values.required,
    ...(choiceFieldTypes.has(values.fieldType) ? { choices: values.choices } : {}),
  }, idempotencyKey),
  baseTables: (baseId: string, init?: RequestInit) => getJson<{ tables: PlatformTable[] }>(`/bases/${baseId}/tables`, init),
  baseViews: (baseId: string, init?: RequestInit) => getJson<{ views: ViewSummary[] }>(`/bases/${baseId}/views`, init),
  tableSchema: (tableId: string, init?: RequestInit) => getJson<TableSchema>(`/tables/${tableId}/schema`, init),
  viewPresentation: (viewId: string, init?: RequestInit) => getJson<ViewPresentation>(`/views/${viewId}/presentation`, init),
  viewRecords: (viewId: string, cursor?: string, init?: RequestInit) => getJson<ViewRecords>(`/views/${viewId}/records${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`, init),
  recordDetail: (recordId: string, init?: RequestInit) => getJson<RecordDetail>(`/records/${recordId}`, init),
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
}
import type { FieldBuilderValues } from './FieldBuilderPanel'
