import { useEffect, useRef, useState } from 'react'
import { QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api, type BaseSummary, type BootstrapResponse, type PlatformTable, type RecordDetail, type TableSchema, type ViewPresentation, type ViewRecords, type ViewSummary, type WorkspaceHome } from './api'
import { AppShell } from './AppShell'
import { BaseCanvas } from './BaseCanvas'
import { RecordDetailPanel } from './RecordDetail'
import { WorkspaceHome as WorkspaceHomeView } from './WorkspaceHome'
import { clearAllProtectedQueries, clearProtectedWorkspace, createProtectedQueryClient, protectedQueryKey } from './protectedQuery'

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
  loadingMore?: boolean
  loadMoreError?: boolean
}

type AppState =
  | { status: 'loading' }
  | { status: 'denied' }
  | { status: 'error' }
  | { status: 'ready'; bootstrap: BootstrapResponse; home: WorkspaceHome; canvas?: BaseCanvasState; canvasLoading?: boolean }

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function App() {
  const [queryClient] = useState(createProtectedQueryClient)
  return <QueryClientProvider client={queryClient}><AppContent /></QueryClientProvider>
}

function AppContent() {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AppState>({ status: 'loading' })
  const homeRequestVersion = useRef(0)
  const canvasRequestVersion = useRef(0)
  const bootstrapQuery = useQuery({
    queryKey: ['stage07', 'bootstrap'],
    queryFn: ({ signal }) => api.bootstrap({ signal }),
  })

  async function loadWorkspaceHome(bootstrap: BootstrapResponse, workspaceId: string) {
    const requestVersion = ++homeRequestVersion.current
    const workspace = bootstrap.workspaces.find((item) => item.id === workspaceId)
    if (!workspace) {
      setState({ status: 'denied' })
      return
    }
    const scope = { userId: bootstrap.identity.user_id, workspaceId }
    try {
      const home = await queryClient.fetchQuery({
        queryKey: protectedQueryKey(scope, 'home'),
        queryFn: ({ signal }) => api.workspaceHome(workspaceId, { signal }),
      })
      if (homeRequestVersion.current !== requestVersion) return
      setState({ status: 'ready', bootstrap, home })
    } catch (error) {
      if (homeRequestVersion.current !== requestVersion || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await clearAllProtectedQueries(queryClient)
        setState({ status: 'denied' })
        return
      }
      if (error instanceof ApiError && error.status === 403) {
        await clearProtectedWorkspace(queryClient, scope)
        setState({ status: 'denied' })
        return
      }
      setState({ status: 'error' })
    }
  }

  useEffect(() => {
    const bootstrap = bootstrapQuery.data
    if (!bootstrap) return
    const workspace = bootstrap.workspaces[0]
    if (!workspace) {
      setState({ status: 'denied' })
      return
    }
    void loadWorkspaceHome(bootstrap, workspace.id)
  }, [bootstrapQuery.data])

  useEffect(() => {
    if (bootstrapQuery.error instanceof ApiError && (bootstrapQuery.error.status === 401 || bootstrapQuery.error.status === 403)) {
      void clearAllProtectedQueries(queryClient)
    }
  }, [bootstrapQuery.error, queryClient])

  if (bootstrapQuery.isError) return <main className="app-state" aria-label={bootstrapQuery.error instanceof ApiError && (bootstrapQuery.error.status === 401 || bootstrapQuery.error.status === 403) ? '无工作区访问权限' : '网络错误'}>{bootstrapQuery.error instanceof ApiError && (bootstrapQuery.error.status === 401 || bootstrapQuery.error.status === 403) ? '当前身份没有可访问的工作区。' : '暂时无法加载工作区，请稍后重试。'}</main>
  if (bootstrapQuery.isPending || state.status === 'loading') return <main className="app-state" aria-label="正在加载工作区">正在加载工作区…</main>

  if (state.status === 'denied') return <main className="app-state" aria-label="无工作区访问权限">当前身份没有可访问的工作区。</main>
  if (state.status === 'error') return <main className="app-state" aria-label="网络错误">暂时无法加载工作区，请稍后重试。</main>

  const readyState = state
  const activeWorkspace = readyState.bootstrap.workspaces.find((item) => item.id === readyState.home.workspace_id) ?? readyState.bootstrap.workspaces[0]
  async function selectWorkspace(workspaceId: string) {
    if (workspaceId === activeWorkspace.id) return
    homeRequestVersion.current += 1
    canvasRequestVersion.current += 1
    setState({ status: 'loading' })
    await clearProtectedWorkspace(queryClient, { userId: readyState.bootstrap.identity.user_id, workspaceId: activeWorkspace.id })
    await loadWorkspaceHome(readyState.bootstrap, workspaceId)
  }

  async function openBase(base: BaseSummary) {
    const requestVersion = ++canvasRequestVersion.current
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    setState({ ...readyState, canvasLoading: true, canvas: undefined })
    try {
      const [{ tables }, { views }] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'base', base.id, 'tables'), queryFn: ({ signal }) => api.baseTables(base.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'base', base.id, 'views'), queryFn: ({ signal }) => api.baseViews(base.id, { signal }) }),
      ])
      if (canvasRequestVersion.current !== requestVersion) return
      const table = tables[0] ?? null
      const view = table ? views.find((item) => item.table_id === table.id) ?? null : null
      if (!table || !view) {
        setState({ ...readyState, canvas: { base, tables, views, table, view, schema: null, records: null, presentation: null } })
        return
      }
      const [schema, presentation, records] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'table', table.id, 'schema'), queryFn: ({ signal }) => api.tableSchema(table.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'presentation'), queryFn: ({ signal }) => api.viewPresentation(view.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'records', null), queryFn: ({ signal }) => api.viewRecords(view.id, undefined, { signal }) }),
      ])
      if (canvasRequestVersion.current !== requestVersion) return
      setState({ ...readyState, canvas: { base, tables, views, table, view, schema, presentation, records } })
    } catch (error) {
      if (canvasRequestVersion.current !== requestVersion || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await clearAllProtectedQueries(queryClient)
        setState({ status: 'denied' })
      } else if (error instanceof ApiError && error.status === 403) {
        await clearProtectedWorkspace(queryClient, scope)
        setState({ status: 'denied' })
      } else {
        setState({ status: 'error' })
      }
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

  async function refreshRecordAfterConflict() {
    const canvas = readyState.canvas
    const detail = canvas?.detail
    if (!canvas || !detail || !canvas.view) throw new Error('Record is not available')
    try {
      const [updated, records] = await Promise.all([api.recordDetail(detail.id), api.viewRecords(canvas.view.id)])
      const readableKeys = new Set(canvas.schema?.fields.map((field) => field.key) ?? [])
      const safeUpdated = { ...updated, values: Object.fromEntries(Object.entries(updated.values).filter(([key]) => readableKeys.has(key))) }
      setState({ ...readyState, canvas: { ...canvas, detail: safeUpdated, records } })
      return safeUpdated
    } catch (error) {
      if (error instanceof ApiError && (error.status === 403 || error.status === 404)) setState({ status: 'denied' })
      throw error
    }
  }

  async function loadMoreRecords(cursor: string) {
    const canvas = readyState.canvas
    if (!canvas?.view || !canvas.records || canvas.records.next_cursor !== cursor || canvas.loadingMore) return
    const workspaceId = readyState.home.workspace_id
    const viewId = canvas.view.id
    const matchesActiveView = (current: AppState): current is Extract<AppState, { status: 'ready' }> & { canvas: BaseCanvasState } => current.status === 'ready' && current.home.workspace_id === workspaceId && current.canvas?.view?.id === viewId && current.canvas.records?.next_cursor === cursor
    setState((current) => matchesActiveView(current) ? { ...current, canvas: { ...current.canvas, loadingMore: true, loadMoreError: false } } : current)
    try {
      const page = await api.viewRecords(viewId, cursor)
      setState((current) => {
        if (!matchesActiveView(current)) return current
        const currentRecords = current.canvas.records!
        const knownRecordIds = new Set(currentRecords.records.map((record) => record.id))
        return { ...current, canvas: { ...current.canvas, records: { ...page, records: [...currentRecords.records, ...page.records.filter((record) => !knownRecordIds.has(record.id))] }, loadingMore: false, loadMoreError: false } }
      })
    } catch (error) {
      setState((current) => {
        if (!matchesActiveView(current)) return current
        if (error instanceof ApiError && error.status === 403) return { status: 'denied' }
        return { ...current, canvas: { ...current.canvas, loadingMore: false, loadMoreError: true } }
      })
    }
  }

  async function selectView(viewId: string) {
    const canvas = readyState.canvas
    if (!canvas || canvas.view?.id === viewId) return
    const view = canvas.views.find((item) => item.id === viewId)
    const table = view?.table_id ? canvas.tables.find((item) => item.id === view.table_id) ?? null : null
    if (!view || !table) return
    const requestVersion = ++canvasRequestVersion.current
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    setState({ ...readyState, canvasLoading: true, canvas: undefined })
    try {
      const schema = canvas.table?.id === table.id && canvas.schema
        ? canvas.schema
        : await queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'table', table.id, 'schema'), queryFn: ({ signal }) => api.tableSchema(table.id, { signal }) })
      const [presentation, records] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'presentation'), queryFn: ({ signal }) => api.viewPresentation(view.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'records', null), queryFn: ({ signal }) => api.viewRecords(view.id, undefined, { signal }) }),
      ])
      if (canvasRequestVersion.current !== requestVersion) return
      setState({ ...readyState, canvas: { ...canvas, table, view, schema, presentation, records, detail: undefined } })
    } catch (error) {
      if (canvasRequestVersion.current !== requestVersion || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await clearAllProtectedQueries(queryClient)
        setState({ status: 'denied' })
      } else if (error instanceof ApiError && error.status === 403) {
        await clearProtectedWorkspace(queryClient, scope)
        setState({ status: 'denied' })
      } else {
        setState({ status: 'error' })
      }
    }
  }

  const content = readyState.canvasLoading
    ? <main className="app-state" aria-label="正在加载 Base">正在加载 Base…</main>
    : readyState.canvas
      ? <><BaseCanvas {...readyState.canvas} onBack={() => setState({ ...readyState, canvas: undefined })} onOpenRecord={openRecord} onSelectView={selectView} onLoadMore={loadMoreRecords} />{readyState.canvas.detail && <RecordDetailPanel detail={readyState.canvas.detail} schema={readyState.canvas.schema} onSave={saveRecord} onConflict={refreshRecordAfterConflict} onClose={() => setState({ ...readyState, canvas: { ...readyState.canvas!, detail: undefined } })} />}</>
      : <WorkspaceHomeView home={readyState.home} workspace={selectedWorkspace} onOpenBase={openBase} />
  return <AppShell workspace={selectedWorkspace} workspaces={readyState.bootstrap.workspaces} onWorkspaceChange={selectWorkspace}>{content}</AppShell>
}
