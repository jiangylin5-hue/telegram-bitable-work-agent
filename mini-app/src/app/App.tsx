import { useEffect, useRef, useState } from 'react'
import { QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api, type BaseSummary, type BootstrapResponse, type CreateForm, type PlatformTable, type RecordDetail, type TableSchema, type ViewPresentation, type ViewRecords, type ViewSummary, type WorkspaceHome } from './api'
import { AppShell } from './AppShell'
import { BaseCanvas } from './BaseCanvas'
import { BuilderCreatePanel } from './BuilderCreatePanel'
import { FieldBuilderPanel, type FieldBuilderValues } from './FieldBuilderPanel'
import { CreateRecordPanel } from './CreateRecordPanel'
import { RecordDetailPanel } from './RecordDetail'
import { WorkspaceHome as WorkspaceHomeView } from './WorkspaceHome'
import { clearAllProtectedQueries, clearFieldMutationQueries, clearProtectedWorkspace, createProtectedQueryClient, protectedQueryKey } from './protectedQuery'

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
  createForm?: CreateForm
  loadingMore?: boolean
  loadMoreError?: boolean
}

type AppState =
  | { status: 'loading' }
  | { status: 'denied' }
  | { status: 'error' }
  | { status: 'ready'; bootstrap: BootstrapResponse; home: WorkspaceHome; canvas?: BaseCanvasState; canvasLoading?: boolean }

type CanvasTarget = { tableId: string; viewId: string }
type BuilderPanel = { mode: 'base' } | { mode: 'table'; base: BaseSummary } | { mode: 'field'; tableId: string; viewId: string }

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
  const activeWorkspaceId = useRef<string | undefined>(undefined)
  const recordRequestVersion = useRef(0)
  const createFormRequestVersion = useRef(0)
  const builderRequestVersion = useRef(0)
  const [builderPanel, setBuilderPanel] = useState<BuilderPanel>()
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
      activeWorkspaceId.current = workspaceId
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
    recordRequestVersion.current += 1
    createFormRequestVersion.current += 1
    builderRequestVersion.current += 1
    setBuilderPanel(undefined)
    activeWorkspaceId.current = workspaceId
    setState({ status: 'loading' })
    await clearProtectedWorkspace(queryClient, { userId: readyState.bootstrap.identity.user_id, workspaceId: activeWorkspace.id })
    await loadWorkspaceHome(readyState.bootstrap, workspaceId)
  }

  async function openBase(base: BaseSummary, target?: CanvasTarget, homeOverride: WorkspaceHome = readyState.home, builderVersion = ++builderRequestVersion.current): Promise<boolean> {
    const requestVersion = ++canvasRequestVersion.current
    createFormRequestVersion.current += 1
    if (!target) setBuilderPanel(undefined)
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: homeOverride.workspace_id }
    const canvasState = { status: 'ready' as const, bootstrap: readyState.bootstrap, home: homeOverride }
    const isCurrent = () => canvasRequestVersion.current === requestVersion && builderRequestVersion.current === builderVersion && activeWorkspaceId.current === homeOverride.workspace_id
    setState({ ...canvasState, canvasLoading: true, canvas: undefined })
    try {
      const [{ tables }, { views }] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'base', base.id, 'tables'), queryFn: ({ signal }) => api.baseTables(base.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'base', base.id, 'views'), queryFn: ({ signal }) => api.baseViews(base.id, { signal }) }),
      ])
      if (!isCurrent()) return false
      const table = target ? tables.find((item) => item.id === target.tableId) ?? null : tables[0] ?? null
      const view = target
        ? views.find((item) => item.id === target.viewId && item.table_id === table?.id) ?? null
        : table ? views.find((item) => item.table_id === table.id) ?? null : null
      if (!table || !view) {
        setState({ ...canvasState, canvas: { base, tables, views, table, view, schema: null, records: null, presentation: null } })
        return true
      }
      const [schema, presentation, records] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'table', table.id, 'schema'), queryFn: ({ signal }) => api.tableSchema(table.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'presentation'), queryFn: ({ signal }) => api.viewPresentation(view.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'records', null), queryFn: ({ signal }) => api.viewRecords(view.id, undefined, { signal }) }),
      ])
      if (!isCurrent()) return false
      setState({ ...canvasState, canvas: { base, tables, views, table, view, schema, presentation, records } })
      return true
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return false
      if (error instanceof ApiError && error.status === 401) {
        await clearAllProtectedQueries(queryClient)
        setState({ status: 'denied' })
      } else if (error instanceof ApiError && error.status === 403) {
        await clearProtectedWorkspace(queryClient, scope)
        setState({ status: 'denied' })
      } else {
        setState({ status: 'error' })
      }
      return false
    }
  }

  async function refreshBuilderHome(scope: { userId: string; workspaceId: string }): Promise<WorkspaceHome> {
    const homeKey = protectedQueryKey(scope, 'home')
    await queryClient.cancelQueries({ queryKey: homeKey })
    queryClient.removeQueries({ queryKey: homeKey })
    return queryClient.fetchQuery({ queryKey: homeKey, queryFn: ({ signal }) => api.workspaceHome(scope.workspaceId, { signal }) })
  }

  async function createBase(values: { baseName: string; tableName: string }, idempotencyKey: string) {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = builderRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => builderRequestVersion.current === requestVersion && canvasRequestVersion.current === canvasVersion && activeWorkspaceId.current === workspaceId
    try {
      const receipt = await api.initializeBase(workspaceId, values, idempotencyKey)
      if (!isCurrent()) return
      queryClient.removeQueries({ queryKey: protectedQueryKey(scope, 'home') })
      const refreshedHome = await refreshBuilderHome(scope)
      if (!isCurrent()) return
      const opened = await openBase(receipt.base, { tableId: receipt.table.id, viewId: receipt.default_view.id }, refreshedHome, requestVersion)
      if (opened && builderRequestVersion.current === requestVersion && activeWorkspaceId.current === workspaceId) setBuilderPanel(undefined)
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
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
      if (error instanceof ApiError && error.status === 404) {
        setState({ status: 'error' })
        return
      }
      throw error
    }
  }

  async function createTable(base: BaseSummary, values: { tableName: string }, idempotencyKey: string) {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = builderRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => builderRequestVersion.current === requestVersion && canvasRequestVersion.current === canvasVersion && activeWorkspaceId.current === workspaceId
    try {
      const receipt = await api.initializeTable(base.id, values, idempotencyKey)
      if (!isCurrent()) return
      queryClient.removeQueries({ queryKey: protectedQueryKey(scope, 'home') })
      queryClient.removeQueries({ queryKey: protectedQueryKey(scope, 'base', base.id) })
      const refreshedHome = await refreshBuilderHome(scope)
      if (!isCurrent()) return
      const opened = await openBase(receipt.base, { tableId: receipt.table.id, viewId: receipt.default_view.id }, refreshedHome, requestVersion)
      if (opened && builderRequestVersion.current === requestVersion && activeWorkspaceId.current === workspaceId) setBuilderPanel(undefined)
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
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
      if (error instanceof ApiError && error.status === 404) {
        setState({ status: 'error' })
        return
      }
      throw error
    }
  }

  async function createField(
    tableId: string,
    viewId: string,
    values: FieldBuilderValues,
    idempotencyKey: string,
  ) {
    const canvas = readyState.canvas
    if (!canvas?.table || !canvas.view || canvas.table.id !== tableId || canvas.view.id !== viewId) {
      throw new Error('Table is not available')
    }
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = builderRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => builderRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === workspaceId
    try {
      const receipt = await api.initializeField(tableId, values, idempotencyKey)
      if (!isCurrent()) return
      const affectedViewIds = [...new Set([viewId, ...receipt.affected_view_ids])]
      await clearFieldMutationQueries(queryClient, scope, tableId, affectedViewIds)
      if (!isCurrent()) return
      const schema = await queryClient.fetchQuery({
        queryKey: protectedQueryKey(scope, 'table', tableId, 'schema'),
        queryFn: ({ signal }) => api.tableSchema(tableId, { signal }),
      })
      if (!schema.fields.some((field) => field.id === receipt.field.id)) {
        throw new Error('Created field is unavailable')
      }
      const [presentation, records] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', viewId, 'presentation'), queryFn: ({ signal }) => api.viewPresentation(viewId, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', viewId, 'records', null), queryFn: ({ signal }) => api.viewRecords(viewId, undefined, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'table', tableId, 'create-form'), queryFn: ({ signal }) => api.createForm(tableId, { signal }) }),
      ])
      if (!isCurrent()) return
      setState((current) => current.status === 'ready'
        && current.home.workspace_id === workspaceId
        && current.canvas?.table?.id === tableId
        && current.canvas.view?.id === viewId
        ? { ...current, canvas: { ...current.canvas, schema, presentation, records, detail: undefined, createForm: undefined } }
        : current)
      setBuilderPanel(undefined)
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await clearAllProtectedQueries(queryClient)
        setBuilderPanel(undefined)
        setState({ status: 'denied' })
        return
      }
      if (error instanceof ApiError && error.status === 403) {
        await clearProtectedWorkspace(queryClient, scope)
        setBuilderPanel(undefined)
        setState({ status: 'denied' })
        return
      }
      if (error instanceof ApiError && error.status === 404) {
        setBuilderPanel(undefined)
        setState({ status: 'error' })
        return
      }
      throw error
    }
  }

  const selectedWorkspace = activeWorkspace
  async function openRecord(recordId: string) {
    if (!readyState.canvas) return
    const requestVersion = ++recordRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    try {
      const detail = await queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'record', recordId), queryFn: ({ signal }) => api.recordDetail(recordId, { signal }) })
      if (recordRequestVersion.current !== requestVersion || canvasRequestVersion.current !== canvasVersion) return
      setState({ ...readyState, canvas: { ...readyState.canvas, detail } })
    } catch (error) {
      if (recordRequestVersion.current !== requestVersion || canvasRequestVersion.current !== canvasVersion || isAbortError(error)) return
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

  async function saveRecord(values: Record<string, unknown>) {
    const canvas = readyState.canvas
    const detail = canvas?.detail
    if (!canvas || !detail || !canvas.view) throw new Error('Record is not available')
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    await api.updateRecord(detail.id, values, detail.version)
    const recordKey = protectedQueryKey(scope, 'record', detail.id)
    const recordsKey = protectedQueryKey(scope, 'view', canvas.view.id, 'records', null)
    await Promise.all([queryClient.invalidateQueries({ queryKey: recordKey }), queryClient.invalidateQueries({ queryKey: recordsKey })])
    queryClient.removeQueries({ queryKey: recordKey })
    queryClient.removeQueries({ queryKey: recordsKey })
    const [updated, records] = await Promise.all([
      queryClient.fetchQuery({ queryKey: recordKey, queryFn: ({ signal }) => api.recordDetail(detail.id, { signal }) }),
      queryClient.fetchQuery({ queryKey: recordsKey, queryFn: ({ signal }) => api.viewRecords(canvas.view!.id, undefined, { signal }) }),
    ])
    const readableKeys = new Set(canvas.schema?.fields.map((field) => field.key) ?? [])
    const safeUpdated = { ...updated, values: Object.fromEntries(Object.entries(updated.values).filter(([key]) => readableKeys.has(key))) }
    setState({ ...readyState, canvas: { ...canvas, records, detail: safeUpdated } })
    return safeUpdated
  }

  async function refreshRecordAfterConflict() {
    const canvas = readyState.canvas
    const detail = canvas?.detail
    if (!canvas || !detail || !canvas.view) throw new Error('Record is not available')
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    const recordKey = protectedQueryKey(scope, 'record', detail.id)
      const recordsKey = protectedQueryKey(scope, 'view', canvas.view.id, 'records', null)
    try {
      await Promise.all([queryClient.invalidateQueries({ queryKey: recordKey }), queryClient.invalidateQueries({ queryKey: recordsKey })])
      queryClient.removeQueries({ queryKey: recordKey })
      queryClient.removeQueries({ queryKey: recordsKey })
      const [updated, records] = await Promise.all([
        queryClient.fetchQuery({ queryKey: recordKey, queryFn: ({ signal }) => api.recordDetail(detail.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: recordsKey, queryFn: ({ signal }) => api.viewRecords(canvas.view!.id, undefined, { signal }) }),
      ])
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
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const matchesActiveView = (current: AppState): current is Extract<AppState, { status: 'ready' }> & { canvas: BaseCanvasState } => current.status === 'ready' && current.home.workspace_id === workspaceId && current.canvas?.view?.id === viewId && current.canvas.records?.next_cursor === cursor
    setState((current) => matchesActiveView(current) ? { ...current, canvas: { ...current.canvas, loadingMore: true, loadMoreError: false } } : current)
    try {
      const page = await queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', viewId, 'records', cursor), queryFn: ({ signal }) => api.viewRecords(viewId, cursor, { signal }) })
      setState((current) => {
        if (!matchesActiveView(current)) return current
        const currentRecords = current.canvas.records!
        const knownRecordIds = new Set(currentRecords.records.map((record) => record.id))
        return { ...current, canvas: { ...current.canvas, records: { ...page, records: [...currentRecords.records, ...page.records.filter((record) => !knownRecordIds.has(record.id))] }, loadingMore: false, loadMoreError: false } }
      })
    } catch (error) {
      if (isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await clearAllProtectedQueries(queryClient)
        setState({ status: 'denied' })
        return
      }
      if (error instanceof ApiError && error.status === 403) await clearProtectedWorkspace(queryClient, scope)
      setState((current) => {
        if (!matchesActiveView(current)) return current
        if (error instanceof ApiError && error.status === 403) return { status: 'denied' }
        return { ...current, canvas: { ...current.canvas, loadingMore: false, loadMoreError: true } }
      })
    }
  }

  async function openCreateRecord() {
    const canvas = readyState.canvas
    if (!canvas?.table || !canvas.view) return
    const requestVersion = ++createFormRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const tableId = canvas.table.id
    const viewId = canvas.view.id
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    try {
      const form = await queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'table', tableId, 'create-form'), queryFn: ({ signal }) => api.createForm(tableId, { signal }) })
      if (createFormRequestVersion.current !== requestVersion || canvasRequestVersion.current !== canvasVersion) return
      setState((current) => current.status === 'ready' && current.home.workspace_id === workspaceId && current.canvas?.table?.id === tableId && current.canvas.view?.id === viewId
        ? { ...current, canvas: { ...current.canvas, createForm: form } }
        : current)
    } catch (error) {
      if (createFormRequestVersion.current !== requestVersion || isAbortError(error)) return
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

  async function createRecord(values: Record<string, unknown>) {
    const canvas = readyState.canvas
    if (!canvas?.table || !canvas.view) throw new Error('Table is not available')
    const canvasVersion = canvasRequestVersion.current
    const tableId = canvas.table.id
    const viewId = canvas.view.id
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    try {
      await api.createRecord(tableId, values)
      if (canvasRequestVersion.current !== canvasVersion) return
      const recordsKey = protectedQueryKey(scope, 'view', viewId, 'records')
      await queryClient.invalidateQueries({ queryKey: recordsKey })
      queryClient.removeQueries({ queryKey: recordsKey })
      const records = await queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', viewId, 'records', null), queryFn: ({ signal }) => api.viewRecords(viewId, undefined, { signal }) })
      if (canvasRequestVersion.current !== canvasVersion) return
      setState((current) => current.status === 'ready' && current.home.workspace_id === workspaceId && current.canvas?.table?.id === tableId && current.canvas.view?.id === viewId
        ? { ...current, canvas: { ...current.canvas, records, createForm: undefined } }
        : current)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        await clearAllProtectedQueries(queryClient)
        setState({ status: 'denied' })
      } else if (error instanceof ApiError && error.status === 403) {
        await clearProtectedWorkspace(queryClient, scope)
        setState({ status: 'denied' })
      }
      throw error
    }
  }

  async function selectTable(tableId: string) {
    const canvas = readyState.canvas
    if (!canvas || canvas.table?.id === tableId) return
    const table = canvas.tables.find((item) => item.id === tableId)
    if (!table) return
    const view = canvas.views.find((item) => item.table_id === table.id) ?? null
    const requestVersion = ++canvasRequestVersion.current
    createFormRequestVersion.current += 1
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    if (!view) {
      setState({ ...readyState, canvas: { ...canvas, table, view: null, schema: null, presentation: null, records: null, detail: undefined, createForm: undefined } })
      return
    }
    setState({ ...readyState, canvasLoading: true, canvas: undefined })
    try {
      const [schema, presentation, records] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'table', table.id, 'schema'), queryFn: ({ signal }) => api.tableSchema(table.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'presentation'), queryFn: ({ signal }) => api.viewPresentation(view.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'records', null), queryFn: ({ signal }) => api.viewRecords(view.id, undefined, { signal }) }),
      ])
      if (canvasRequestVersion.current !== requestVersion) return
      setState({ ...readyState, canvas: { ...canvas, table, view, schema, presentation, records, detail: undefined, createForm: undefined } })
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

  async function selectView(viewId: string) {
    const canvas = readyState.canvas
    if (!canvas || canvas.view?.id === viewId) return
    const view = canvas.views.find((item) => item.id === viewId)
    const table = view?.table_id ? canvas.tables.find((item) => item.id === view.table_id) ?? null : null
    if (!view || !table) return
    const requestVersion = ++canvasRequestVersion.current
    createFormRequestVersion.current += 1
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
      ? <><BaseCanvas {...readyState.canvas} canManageSchema={selectedWorkspace.capabilities.can_manage_schema} onBack={() => { builderRequestVersion.current += 1; createFormRequestVersion.current += 1; setBuilderPanel(undefined); setState({ ...readyState, canvas: undefined }) }} onOpenRecord={openRecord} onSelectTable={selectTable} onSelectView={selectView} onLoadMore={loadMoreRecords} onCreateRecord={readyState.canvas.schema?.fields.length ? openCreateRecord : undefined} onCreateTable={() => { builderRequestVersion.current += 1; setBuilderPanel({ mode: 'table', base: readyState.canvas!.base }) }} onCreateField={() => { const canvas = readyState.canvas; if (!canvas?.table || !canvas.view) return; builderRequestVersion.current += 1; setBuilderPanel({ mode: 'field', tableId: canvas.table.id, viewId: canvas.view.id }) }} />{readyState.canvas.detail && <RecordDetailPanel detail={readyState.canvas.detail} schema={readyState.canvas.schema} onSave={saveRecord} onConflict={refreshRecordAfterConflict} onClose={() => setState({ ...readyState, canvas: { ...readyState.canvas!, detail: undefined } })} />}{readyState.canvas.createForm && <CreateRecordPanel form={readyState.canvas.createForm} onCreate={createRecord} onClose={() => setState((current) => current.status === 'ready' && current.canvas ? { ...current, canvas: { ...current.canvas, createForm: undefined } } : current)} />}</>
      : <WorkspaceHomeView home={readyState.home} workspace={selectedWorkspace} onOpenBase={openBase} onCreateBase={() => { builderRequestVersion.current += 1; setBuilderPanel({ mode: 'base' }) }} />
  const builderOverlay = builderPanel?.mode === 'base'
    ? <BuilderCreatePanel mode="base" onSubmit={(values, idempotencyKey) => createBase(values as { baseName: string; tableName: string }, idempotencyKey)} onClose={() => { builderRequestVersion.current += 1; setBuilderPanel(undefined) }} />
    : builderPanel?.mode === 'table'
      ? <BuilderCreatePanel mode="table" onSubmit={(values, idempotencyKey) => createTable(builderPanel.base, values as { tableName: string }, idempotencyKey)} onClose={() => { builderRequestVersion.current += 1; setBuilderPanel(undefined) }} />
      : builderPanel?.mode === 'field'
        ? <FieldBuilderPanel onSubmit={(values, idempotencyKey) => createField(builderPanel.tableId, builderPanel.viewId, values, idempotencyKey)} onClose={() => { builderRequestVersion.current += 1; setBuilderPanel(undefined) }} />
        : null
  return <AppShell workspace={selectedWorkspace} workspaces={readyState.bootstrap.workspaces} onWorkspaceChange={selectWorkspace}>{content}{builderOverlay}</AppShell>
}
