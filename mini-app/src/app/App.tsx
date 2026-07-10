import { useEffect, useState } from 'react'

import { ApiError, api, type BaseSummary, type BootstrapResponse, type PlatformTable, type TableSchema, type ViewRecords, type ViewSummary, type WorkspaceHome } from './api'
import { AppShell } from './AppShell'
import { BaseCanvas } from './BaseCanvas'
import { WorkspaceHome as WorkspaceHomeView } from './WorkspaceHome'

type BaseCanvasState = {
  base: BaseSummary
  table: PlatformTable | null
  view: ViewSummary | null
  schema: TableSchema | null
  records: ViewRecords | null
}

type AppState =
  | { status: 'loading' }
  | { status: 'denied' }
  | { status: 'error' }
  | { status: 'ready'; bootstrap: BootstrapResponse; home: WorkspaceHome; canvas?: BaseCanvasState; canvasLoading?: boolean }

export function App() {
  const [state, setState] = useState<AppState>({ status: 'loading' })

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const bootstrap = await api.bootstrap()
        const workspace = bootstrap.workspaces[0]
        if (!workspace) {
          if (active) setState({ status: 'denied' })
          return
        }
        const home = await api.workspaceHome(workspace.id)
        if (active) setState({ status: 'ready', bootstrap, home })
      } catch (error) {
        if (!active) return
        setState({ status: error instanceof ApiError && error.status === 403 ? 'denied' : 'error' })
      }
    }
    void load()
    return () => { active = false }
  }, [])

  if (state.status === 'loading') return <main className="app-state" aria-label="正在加载工作区">正在加载工作区…</main>
  if (state.status === 'denied') return <main className="app-state" aria-label="无工作区访问权限">当前身份没有可访问的工作区。</main>
  if (state.status === 'error') return <main className="app-state" aria-label="网络错误">暂时无法加载工作区，请稍后重试。</main>

  const readyState = state
  const activeWorkspace = readyState.bootstrap.workspaces.find((item) => item.id === readyState.home.workspace_id) ?? readyState.bootstrap.workspaces[0]
  async function selectWorkspace(workspaceId: string) {
    if (workspaceId === activeWorkspace.id) return
    setState({ status: 'loading' })
    try {
      const home = await api.workspaceHome(workspaceId)
      setState({ status: 'ready', bootstrap: readyState.bootstrap, home })
    } catch (error) {
      setState({ status: error instanceof ApiError && error.status === 403 ? 'denied' : 'error' })
    }
  }

  async function openBase(base: BaseSummary) {
    setState({ ...readyState, canvasLoading: true, canvas: undefined })
    try {
      const [{ tables }, { views }] = await Promise.all([api.baseTables(base.id), api.baseViews(base.id)])
      const table = tables[0] ?? null
      const view = table ? views.find((item) => item.table_id === table.id) ?? null : null
      if (!table || !view) {
        setState({ ...readyState, canvas: { base, table, view, schema: null, records: null } })
        return
      }
      const [schema, records] = await Promise.all([api.tableSchema(table.id), api.viewRecords(view.id)])
      setState({ ...readyState, canvas: { base, table, view, schema, records } })
    } catch (error) {
      setState({ status: error instanceof ApiError && error.status === 403 ? 'denied' : 'error' })
    }
  }

  const selectedWorkspace = activeWorkspace
  const content = readyState.canvasLoading
    ? <main className="app-state" aria-label="正在加载 Base">正在加载 Base…</main>
    : readyState.canvas
      ? <BaseCanvas {...readyState.canvas} onBack={() => setState({ ...readyState, canvas: undefined })} />
      : <WorkspaceHomeView home={readyState.home} workspace={selectedWorkspace} onOpenBase={openBase} />
  return <AppShell workspace={selectedWorkspace} workspaces={readyState.bootstrap.workspaces} onWorkspaceChange={selectWorkspace}>{content}</AppShell>
}
