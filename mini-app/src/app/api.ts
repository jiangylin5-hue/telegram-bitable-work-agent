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
export type TableSchema = { table: { id: string; name: string; key: string }; fields: { id: string; name: string; key: string; field_type: string; required: boolean; order_index: number }[] }
export type ViewRecords = { view_id: string; records: { id: string; fields: Record<string, unknown> }[]; next_cursor: string | null; has_more: boolean }

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`请求失败 (${status})`)
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!response.ok) throw new ApiError(response.status)
  return response.json() as Promise<T>
}

export const api = {
  bootstrap: () => getJson<BootstrapResponse>('/mini-app/bootstrap'),
  workspaceHome: (workspaceId: string) => getJson<WorkspaceHome>(`/workspaces/${workspaceId}/home`),
  baseTables: (baseId: string) => getJson<{ tables: PlatformTable[] }>(`/bases/${baseId}/tables`),
  baseViews: (baseId: string) => getJson<{ views: ViewSummary[] }>(`/bases/${baseId}/views`),
  tableSchema: (tableId: string) => getJson<TableSchema>(`/tables/${tableId}/schema`),
  viewRecords: (viewId: string) => getJson<ViewRecords>(`/views/${viewId}/records`),
}
