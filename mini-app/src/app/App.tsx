import { useEffect, useState } from 'react'

import { ApiError, api, type BaseSummary, type BootstrapResponse, type PlatformTable, type RecordDetail, type TableSchema, type ViewPresentation, type ViewRecords, type ViewSummary, type WorkspaceHome } from './api'
import { AppShell } from './AppShell'
import { BaseCanvas } from './BaseCanvas'
import { RecordDetailPanel } from './RecordDetail'
import { WorkspaceHome as WorkspaceHomeView } from './WorkspaceHome'

type BaseCanvasState = {
  base: BaseSummary
  tables: PlatformTable[]
  views: ViewSummary[]
  table: PlatformTable | null
  view: ViewSummary | null
  schema: TableSchema | null
  records: ViewRecords | null
  presentation: ViewPresentation | null
  detail?: RecordDetail
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
        setState({ ...readyState, canvas: { base, tables, views, table, view, schema: null, records: null, presentation: null } })
        return
      }
      const [schema, presentation, records] = await Promise.all([api.tableSchema(table.id), api.viewPresentation(view.id), api.viewRecords(view.id)])
      setState({ ...readyState, canvas: { base, tables, views, table, view, schema, presentation, records } })
    } catch (error) {
      setState({ status: error instanceof ApiError && error.status === 403 ? 'denied' : 'error' })
    }
  }

  const selectedWorkspace = activeWorkspace
  async function openRecord(recordId: string) {
    if (!readyState.canvas) return
    try {
      const detail = await api.recordDetail(recordId)
      setState({ ...readyState, canvas: { ...readyState.canvas, detail } })
    } catch (error) {
      setState({ status: error instanceof ApiError && error.status === 403 ? 'denied' : 'error' })
    }
  }

  async function saveRecord(values: Record<string, unknown>) {
    const canvas = readyState.canvas
    const detail = canvas?.detail
    if (!canvas || !detail) throw new Error('Record is not available')
    const updated = await api.updateRecord(detail.id, values, detail.version)
    const readableKeys = new Set(canvas.schema?.fields.map((field) => field.key) ?? [])
    const safeUpdated = { ...updated, values: Object.fromEntries(Object.entries(updated.values).filter(([key]) => readableKeys.has(key))) }
    const records = canvas.records && { ...canvas.records, records: canvas.records.records.map((record) => record.id === safeUpdated.id ? { ...record, fields: safeUpdated.values } : record) }
    setState({ ...readyState, canvas: { ...canvas, records, detail: safeUpdated } })
    return safeUpdated
  }

  async function selectView(viewId: string) {
    const canvas = readyState.canvas
    if (!canvas || canvas.view?.id === viewId) return
    const view = canvas.views.find((item) => item.id === viewId)
    const table = view?.table_id ? canvas.tables.find((item) => item.id === view.table_id) ?? null : null
    if (!view || !table) return
    setState({ ...readyState, canvasLoading: true, canvas: undefined })
    try {
      const schema = canvas.table?.id === table.id && canvas.schema ? canvas.schema : await api.tableSchema(table.id)
      const [presentation, records] = await Promise.all([api.viewPresentation(view.id), api.viewRecords(view.id)])
      setState({ ...readyState, canvas: { ...canvas, table, view, schema, presentation, records, detail: undefined } })
    } catch (error) {
      setState({ status: error instanceof ApiError && error.status === 403 ? 'denied' : 'error' })
    }
  }

  const content = readyState.canvasLoading
    ? <main className="app-state" aria-label="正在加载 Base">正在加载 Base…</main>
    : readyState.canvas
      ? <><BaseCanvas {...readyState.canvas} onBack={() => setState({ ...readyState, canvas: undefined })} onOpenRecord={openRecord} onSelectView={selectView} />{readyState.canvas.detail && <RecordDetailPanel detail={readyState.canvas.detail} schema={readyState.canvas.schema} onSave={saveRecord} onClose={() => setState({ ...readyState, canvas: { ...readyState.canvas!, detail: undefined } })} />}</>
      : <WorkspaceHomeView home={readyState.home} workspace={selectedWorkspace} onOpenBase={openBase} />
  return <AppShell workspace={selectedWorkspace} workspaces={readyState.bootstrap.workspaces} onWorkspaceChange={selectWorkspace}>{content}</AppShell>
}
