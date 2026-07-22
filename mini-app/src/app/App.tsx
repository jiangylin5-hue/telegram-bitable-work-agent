import { useEffect, useRef, useState } from 'react'
import { isCancelledError, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api, type BaseSummary, type BootstrapResponse, type CreateForm, type PlatformTable, type RecordDetail, type TableSchema, type TelegramDeepLinkDestination, type ViewPresentation, type ViewRecords, type ViewSummary, type WorkspaceHome } from './api'
import { AppShell, type AppShellRoute } from './AppShell'
import { AssistantContextWorkbench } from './AssistantContextWorkbench'
import { TeamBotWorkbench } from './TeamBotWorkbench'
import { BaseCanvas } from './BaseCanvas'
import { DigitalEmployeeManagementWorkbench } from './DigitalEmployeeManagementWorkbench'
import { BaseDirectory, type BaseDirectoryState } from './BaseDirectory'
import { BuilderCreatePanel } from './BuilderCreatePanel'
import { FieldBuilderPanel, type FieldBuilderValues } from './FieldBuilderPanel'
import { ImportWizard, type ImportTarget } from './ImportWizard'
import { CreateRecordPanel } from './CreateRecordPanel'
import { DraftEmployeeHub } from './DraftEmployeeHub'
import { GovernanceWorkbench } from './GovernanceWorkbench'
import { GovernanceWriteWorkbench } from './GovernanceWriteWorkbench'
import { RecordDetailPanel } from './RecordDetail'
import { RelationLookupFieldBuilderPanel, type F2FieldBuilderValues } from './RelationLookupFieldBuilderPanel'
import { SaveTemplatePanel } from './SaveTemplatePanel'
import { TemplateImportHub } from './TemplateImportHub'
import { ViewBuilderPanel } from './ViewBuilderPanel'
import { WorkspaceHome as WorkspaceHomeView } from './WorkspaceHome'
import { clearAllProtectedQueries, clearAssistantContextQueries, clearDigitalEmployeeManagementQueries, clearDraftEmployeeTerminalQueries, clearFieldMutationQueries, clearGovernanceQueries, clearGovernanceWriteQueries, clearProtectedWorkspace, clearRecordMutationQueries, clearRelationCandidateQueries, clearTeamBotQueries, clearTelegramDeepLinkQueries, clearTemplateImportQueries, clearViewBuilderQueries, createProtectedQueryClient, digitalEmployeeManagementKeys, draftEmployeeKeys, governanceKeys, governanceWriteKeys, navigationKeys, protectedQueryKey, relationCandidateQueryKey, teamBotKeys, templateImportKeys, viewBuilderKeys } from './protectedQuery'
import { readTelegramMiniAppLaunch, type TelegramMiniAppLaunch } from './telegram-mini-app'
import type { GovernanceAuditPage, GovernanceMemberPage } from './governance-types'
import type { GovernanceEditableMemberPage, GovernanceFieldPermissionPage, GovernanceFieldPermissionPolicy } from './governance-write-types'
import type { AssistantContextPage, AssistantSelectedView, CurrentCanvasInvocationContext, S5Contact, S5DraftDetail, S5InvocationRequest, S5InvocationResult } from './draft-employee-types'
import type { TeamBotContact, TeamBotKnowledgeContextPage, TeamBotSelectedView, TeamBotSummary } from './team-bot-knowledge-types'
import type { ManagedEmployeeDetail, ManagedEmployeeDirectory, ManagedEmployeeManagementContext, ManagedEmployeeUpdateValues } from './digital-employee-management-types'
import type { CommitImportValues, CreateImportValues, ImportCommitReceipt, ImportPreview, TemplateSummary } from './template-import-types'
import type { ViewBuilderContext, ViewBuilderResponse, ViewInitializationRequest, ViewMemberReplaceRequest, ViewPresentationPatchRequest } from './view-builder-types'

type BaseCanvasState = {
  base: BaseSummary
  tables: PlatformTable[]
  views: ViewSummary[]
  table: PlatformTable | null
  view: ViewSummary | null
  schema: TableSchema | null
  records: ViewRecords | null
  presentation: ViewPresentation | null
  serverQuerySummary?: string
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

type BaseDirectoryData = { state: BaseDirectoryState; bases: BaseSummary[] }

type CanvasTarget = { tableId?: string; viewId?: string; recordId?: string; openViewBuilder?: boolean }
type BuilderPanel =
  | { mode: 'base' }
  | { mode: 'table'; base: BaseSummary }
  | { mode: 'field'; tableId: string; viewId: string }
  | { mode: 'relation-lookup-loading'; tableId: string; viewId: string }
  | { mode: 'relation-lookup'; tableId: string; viewId: string; tables: PlatformTable[]; schemas: TableSchema[] }
  | { mode: 'view-loading'; tableId: string; viewId?: string }
  | { mode: 'view'; tableId: string; context: ViewBuilderContext; builder?: ViewBuilderResponse }

type TemplateImportPanel =
  | { mode: 'hub'; templates: TemplateSummary[]; loading: boolean; error: string | null }
  | { mode: 'save-template'; base: BaseSummary }
  | { mode: 'workspace-import' }
  | { mode: 'base-import'; base: BaseSummary }

type GovernancePanel = {
  members: GovernanceMemberPage | null
  audit: GovernanceAuditPage | null
  selectedBaseId: string | null
  membersLoading: boolean
  auditLoading: boolean
  membersError: boolean
  auditError: boolean
  membersLoadMoreError: boolean
  auditLoadMoreError: boolean
}

type GovernanceWritePanel = {
  members: GovernanceEditableMemberPage | null
  tables: PlatformTable[]
  views: ViewSummary[]
  fields: GovernanceFieldPermissionPage | null
  selectedBaseId: string | null
  selectedTableId: string | null
  membersLoading: boolean
  tablesLoading: boolean
  fieldsLoading: boolean
  contextError?: 'base_not_available' | 'table_not_available'
}

type DraftEmployeePanel = {
  contacts: S5Contact[]
  draft: S5DraftDetail | null
  loading: boolean
  targetDraftId: string | null
  failed: boolean
}

type AssistantContextPanel = {
  contacts: S5Contact[]
  selectedEmployeeId: string | null
  context: AssistantContextPage | null
  selectedView: AssistantSelectedView | null
  summary: Extract<S5InvocationResult, { kind: 'summary' }> | null
  loading: boolean
  failed: boolean
}

type TeamBotPanel = {
  contacts: TeamBotContact[]
  selectedEmployeeId: string | null
  context: TeamBotKnowledgeContextPage | null
  selectedView: TeamBotSelectedView | null
  summary: TeamBotSummary | null
  loading: boolean
  failed: boolean
}

type DigitalEmployeeManagementPanel = {
  baseId: string
  context: ManagedEmployeeManagementContext | null
  directory: ManagedEmployeeDirectory | null
  detail: ManagedEmployeeDetail | null
  selectedEmployeeId: string | null
  loading: boolean
  failed: boolean
}

function isAbortError(error: unknown): boolean {
  return isCancelledError(error) || (error instanceof DOMException && error.name === 'AbortError')
}

function canvasPresentationFromV1Builder(builder: ViewBuilderResponse): ViewPresentation {
  return {
    view_id: builder.presentation.view_id,
    table_id: builder.presentation.table_id,
    view_type: builder.presentation.view_type,
    visible_field_keys: builder.presentation.visible_field_keys,
    group_by_field_key: builder.presentation.group_by_field_key,
    date_field_key: builder.presentation.date_field_key,
    form_field_keys: builder.presentation.form_field_keys,
  }
}

function v1ServerQuerySummary(builder: ViewBuilderResponse): string {
  const fieldLabels = new Map(builder.fields.map((field) => [field.key, field.label]))
  const items: string[] = []
  if (builder.presentation.filters.length) items.push(`${builder.presentation.filters.length} 条筛选`)
  if (builder.presentation.sort_rules.length) items.push(`${builder.presentation.sort_rules.length} 条排序`)
  if (builder.presentation.group_by_field_key) items.push(`按 ${fieldLabels.get(builder.presentation.group_by_field_key) ?? '字段'} 分组`)
  if (builder.presentation.date_field_key) items.push(`日期：${fieldLabels.get(builder.presentation.date_field_key) ?? '字段'}`)
  return items.length ? `服务端已应用 ${items.join('、')}` : '服务端已应用当前视图规则'
}

export function App() {
  const [queryClient] = useState(createProtectedQueryClient)
  return <QueryClientProvider client={queryClient}><AppContent /></QueryClientProvider>
}

function AppContent() {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AppState>({ status: 'loading' })
  const telegramLaunch = useRef<TelegramMiniAppLaunch | null | undefined>(undefined)
  if (telegramLaunch.current === undefined) {
    telegramLaunch.current = readTelegramMiniAppLaunch()
    api.setTelegramInitData(telegramLaunch.current?.initData ?? null)
  }
  const homeRequestVersion = useRef(0)
  const baseDirectoryRequestVersion = useRef(0)
  const canvasRequestVersion = useRef(0)
  const activeWorkspaceId = useRef<string | undefined>(undefined)
  const recordRequestVersion = useRef(0)
  const createFormRequestVersion = useRef(0)
  const builderRequestVersion = useRef(0)
  const templateImportRequestVersion = useRef(0)
  const governanceRequestVersion = useRef(0)
  const governanceWriteRequestVersion = useRef(0)
  const draftEmployeeRequestVersion = useRef(0)
  const assistantContextRequestVersion = useRef(0)
  const teamBotRequestVersion = useRef(0)
  const digitalEmployeeManagementRequestVersion = useRef(0)
  const telegramLaunchRequestVersion = useRef(0)
  const telegramLaunchHandled = useRef(false)
  const pendingTelegramDestination = useRef<TelegramDeepLinkDestination | null>(null)
  const telegramDestinationHandoff = useRef<((destination: TelegramDeepLinkDestination) => Promise<void>) | null>(null)
  const telegramRecoveryButton = useRef<HTMLButtonElement | null>(null)
  const viewBuilderReturnFocus = useRef<HTMLElement | null>(null)
  const templateImportReturnFocus = useRef<HTMLElement | null>(null)
  const governanceReturnFocus = useRef<HTMLElement | null>(null)
  const governanceWriteReturnFocus = useRef<HTMLElement | null>(null)
  const draftEmployeeReturnFocus = useRef<HTMLElement | null>(null)
  const assistantContextReturnFocus = useRef<HTMLElement | null>(null)
  const teamBotReturnFocus = useRef<HTMLElement | null>(null)
  const digitalEmployeeManagementReturnFocus = useRef<HTMLElement | null>(null)
  const sessionInvalidated = useRef(false)
  const [telegramRecovery, setTelegramRecovery] = useState(false)
  const [navigationRoute, setNavigationRoute] = useState<AppShellRoute>('home')
  const [baseDirectory, setBaseDirectory] = useState<BaseDirectoryData>({ state: 'loading', bases: [] })
  const [builderPanel, setBuilderPanel] = useState<BuilderPanel>()
  const [templateImportPanel, setTemplateImportPanel] = useState<TemplateImportPanel>()
  const [governancePanel, setGovernancePanel] = useState<GovernancePanel>()
  const [governanceWritePanel, setGovernanceWritePanel] = useState<GovernanceWritePanel>()
  const [draftEmployeePanel, setDraftEmployeePanel] = useState<DraftEmployeePanel>()
  const [assistantContextPanel, setAssistantContextPanel] = useState<AssistantContextPanel>()
  const [teamBotPanel, setTeamBotPanel] = useState<TeamBotPanel>()
  const [digitalEmployeeManagementPanel, setDigitalEmployeeManagementPanel] = useState<DigitalEmployeeManagementPanel>()

  function invalidateInFlightRequests() {
    homeRequestVersion.current += 1
    baseDirectoryRequestVersion.current += 1
    canvasRequestVersion.current += 1
    recordRequestVersion.current += 1
    createFormRequestVersion.current += 1
    builderRequestVersion.current += 1
    templateImportRequestVersion.current += 1
    governanceRequestVersion.current += 1
    governanceWriteRequestVersion.current += 1
    draftEmployeeRequestVersion.current += 1
    assistantContextRequestVersion.current += 1
    teamBotRequestVersion.current += 1
    digitalEmployeeManagementRequestVersion.current += 1
    telegramLaunchRequestVersion.current += 1
    pendingTelegramDestination.current = null
  }

  useEffect(() => () => {
    telegramLaunchRequestVersion.current += 1
    pendingTelegramDestination.current = null
    api.setTelegramInitData(null)
  }, [])

  useEffect(() => {
    if (!telegramRecovery || state.status !== 'ready') return
    telegramRecoveryButton.current?.focus()
  }, [state.status, telegramRecovery])

  useEffect(() => {
    if (state.status !== 'ready') return
    const destination = pendingTelegramDestination.current
    if (!destination) return
    pendingTelegramDestination.current = null
    void telegramDestinationHandoff.current?.(destination)
  }, [state])

  async function denyInvalidSession() {
    sessionInvalidated.current = true
    invalidateInFlightRequests()
    setState({ status: 'denied' })
    await clearAllProtectedQueries(queryClient)
  }

  async function denyWorkspace(scope: { userId: string; workspaceId: string }) {
    await clearProtectedWorkspace(queryClient, scope)
    if (!sessionInvalidated.current && activeWorkspaceId.current === scope.workspaceId) {
      invalidateInFlightRequests()
      setState({ status: 'denied' })
    }
  }

  async function discardRecordMutationQueries(scope: { userId: string; workspaceId: string }, recordId: string, viewId: string) {
    await clearRecordMutationQueries(queryClient, scope, recordId, viewId)
  }

  function rememberViewBuilderTrigger() {
    viewBuilderReturnFocus.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null
  }

  function closeViewBuilder() {
    builderRequestVersion.current += 1
    setBuilderPanel(undefined)
    const trigger = viewBuilderReturnFocus.current
    viewBuilderReturnFocus.current = null
    queueMicrotask(() => {
      if (trigger?.isConnected) trigger.focus()
    })
  }

  function abandonRecordDetail(canvas: BaseCanvasState | undefined, workspaceId: string) {
    recordRequestVersion.current += 1
    if (!canvas?.detail || !canvas.view) return
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    void Promise.all([
      discardRecordMutationQueries(scope, canvas.detail.id, canvas.view.id),
      ...(canvas.schema?.fields ?? [])
        .filter((field) => field.field_type === 'linked_record')
        .map((field) => clearRelationCandidateQueries(queryClient, scope, field.id)),
    ])
  }

  const bootstrapQuery = useQuery({
    queryKey: ['stage07', 'bootstrap'],
    queryFn: ({ signal }) => sessionInvalidated.current
      ? Promise.reject(new DOMException('Session invalidated', 'AbortError'))
      : api.bootstrap({ signal }),
    enabled: !sessionInvalidated.current,
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
        await denyInvalidSession()
        return
      }
      if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
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
    if (telegramLaunchHandled.current) {
      void loadWorkspaceHome(bootstrap, workspace.id)
      return
    }
    telegramLaunchHandled.current = true
    const launch = telegramLaunch.current
    const startParam = launch?.startParam
    if (!startParam) {
      void loadWorkspaceHome(bootstrap, workspace.id)
      return
    }
    const requestVersion = ++telegramLaunchRequestVersion.current
    void (async () => {
      try {
        const resolution = await api.resolveTelegramDeepLink(startParam)
        if (telegramLaunchRequestVersion.current !== requestVersion || sessionInvalidated.current) return
        if (resolution.outcome === 'recovery') {
          setTelegramRecovery(true)
          await loadWorkspaceHome(bootstrap, workspace.id)
          return
        }
        const targetWorkspace = bootstrap.workspaces.find((item) => item.id === resolution.destination.workspaceId)
        if (!targetWorkspace) {
          setTelegramRecovery(true)
          await loadWorkspaceHome(bootstrap, workspace.id)
          return
        }
        pendingTelegramDestination.current = resolution.destination
        await loadWorkspaceHome(bootstrap, targetWorkspace.id)
      } catch (error) {
        if (telegramLaunchRequestVersion.current !== requestVersion || isAbortError(error)) return
        if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
        else if (error instanceof ApiError && error.status === 403) {
          await clearAllProtectedQueries(queryClient)
          setState({ status: 'denied' })
        } else {
          setTelegramRecovery(true)
          await loadWorkspaceHome(bootstrap, workspace.id)
        }
      }
    })()
  }, [bootstrapQuery.data])

  useEffect(() => {
    if (bootstrapQuery.error instanceof ApiError && (bootstrapQuery.error.status === 401 || bootstrapQuery.error.status === 403)) {
      void denyInvalidSession()
    }
  }, [bootstrapQuery.error, queryClient])

  if (state.status === 'denied') return <main className="app-state" aria-label="无工作区访问权限">当前身份没有可访问的工作区。</main>
  if (bootstrapQuery.isError) return <main className="app-state" aria-label={bootstrapQuery.error instanceof ApiError && (bootstrapQuery.error.status === 401 || bootstrapQuery.error.status === 403) ? '无工作区访问权限' : '网络错误'}>{bootstrapQuery.error instanceof ApiError && (bootstrapQuery.error.status === 401 || bootstrapQuery.error.status === 403) ? '当前身份没有可访问的工作区。' : '暂时无法加载工作区，请稍后重试。'}</main>
  if (bootstrapQuery.isPending || state.status === 'loading') return <main className="app-state" aria-label="正在加载工作区">正在加载工作区…</main>

  if (state.status === 'error') return <main className="app-state" aria-label="网络错误">暂时无法加载工作区，请稍后重试。</main>

  const readyState = state
  const activeWorkspace = readyState.bootstrap.workspaces.find((item) => item.id === readyState.home.workspace_id) ?? readyState.bootstrap.workspaces[0]
  async function selectWorkspace(workspaceId: string) {
    if (workspaceId === activeWorkspace.id) return
    homeRequestVersion.current += 1
    baseDirectoryRequestVersion.current += 1
    canvasRequestVersion.current += 1
    recordRequestVersion.current += 1
    createFormRequestVersion.current += 1
    builderRequestVersion.current += 1
    templateImportRequestVersion.current += 1
    governanceRequestVersion.current += 1
    governanceWriteRequestVersion.current += 1
    draftEmployeeRequestVersion.current += 1
    assistantContextRequestVersion.current += 1
    teamBotRequestVersion.current += 1
    telegramLaunchRequestVersion.current += 1
    pendingTelegramDestination.current = null
    setBuilderPanel(undefined)
    setTemplateImportPanel(undefined)
    setGovernancePanel(undefined)
    setGovernanceWritePanel(undefined)
    setDraftEmployeePanel(undefined)
    setAssistantContextPanel(undefined)
    setTeamBotPanel(undefined)
    setDigitalEmployeeManagementPanel(undefined)
    setNavigationRoute('home')
    setBaseDirectory({ state: 'loading', bases: [] })
    activeWorkspaceId.current = workspaceId
    setState({ status: 'loading' })
    await clearProtectedWorkspace(queryClient, { userId: readyState.bootstrap.identity.user_id, workspaceId: activeWorkspace.id })
    await loadWorkspaceHome(readyState.bootstrap, workspaceId)
  }

  async function loadBaseDirectory() {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++baseDirectoryRequestVersion.current
    const queryKey = navigationKeys.bases(scope)
    const isCurrent = () => !sessionInvalidated.current
      && baseDirectoryRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setBaseDirectory({ state: 'loading', bases: [] })
    try {
      const { bases } = await queryClient.fetchQuery({
        queryKey,
        queryFn: ({ signal }) => api.workspaceBases(workspaceId, { signal }),
      })
      if (!isCurrent()) return
      setBaseDirectory({ state: bases.length ? 'ready' : 'empty', bases })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
      } else if (error instanceof ApiError && error.status === 404) {
        await queryClient.cancelQueries({ queryKey })
        queryClient.removeQueries({ queryKey })
        if (isCurrent()) setNavigationRoute('home')
      } else if (isCurrent()) {
        setBaseDirectory({ state: 'retryable', bases: [] })
      }
    }
  }

  function selectNavigation(route: AppShellRoute) {
    baseDirectoryRequestVersion.current += 1
    if (readyState.canvasLoading || readyState.canvas) {
      canvasRequestVersion.current += 1
      createFormRequestVersion.current += 1
      builderRequestVersion.current += 1
      abandonRecordDetail(readyState.canvas, readyState.home.workspace_id)
      setBuilderPanel(undefined)
      setState({ ...readyState, canvas: undefined, canvasLoading: false })
    }
    setNavigationRoute(route)
    if (route === 'bases') void loadBaseDirectory()
  }

  async function readV1BuilderForCanvas(
    scope: { userId: string; workspaceId: string },
    view: ViewSummary,
  ): Promise<ViewBuilderResponse | undefined> {
    const workspace = readyState.bootstrap.workspaces.find((item) => item.id === scope.workspaceId)
    if (!view.scope || !workspace?.capabilities.can_manage_schema) return undefined
    try {
      return await readV1Builder(scope, view.id)
    } catch (error) {
      if (error instanceof ApiError && (error.status === 403 || error.status === 404)) return undefined
      throw error
    }
  }

  async function openBase(base: BaseSummary, target?: CanvasTarget, homeOverride: WorkspaceHome = readyState.home, builderVersion = ++builderRequestVersion.current): Promise<boolean> {
    if (digitalEmployeeManagementPanel?.baseId !== undefined && digitalEmployeeManagementPanel.baseId !== base.id) {
      closeDigitalEmployeeManagement()
    }
    const requestVersion = ++canvasRequestVersion.current
    createFormRequestVersion.current += 1
    if (!target) setBuilderPanel(undefined)
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: homeOverride.workspace_id }
    const canvasState = { status: 'ready' as const, bootstrap: readyState.bootstrap, home: homeOverride }
    const isCurrent = () => !sessionInvalidated.current && canvasRequestVersion.current === requestVersion && builderRequestVersion.current === builderVersion && activeWorkspaceId.current === homeOverride.workspace_id
    setState({ ...canvasState, canvasLoading: true, canvas: undefined })
    try {
      const [{ tables }, { views }] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'base', base.id, 'tables'), queryFn: ({ signal }) => api.baseTables(base.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'base', base.id, 'views'), queryFn: ({ signal }) => api.baseViews(base.id, { signal }) }),
      ])
      if (!isCurrent()) return false
      const table = target?.tableId
        ? tables.find((item) => item.id === target.tableId) ?? null
        : tables[0] ?? null
      const view = target?.viewId
        ? views.find((item) => item.id === target.viewId && item.table_id === table?.id) ?? null
        : table ? views.find((item) => item.table_id === table.id) ?? null : null
      if (!table || !view) {
        if (target?.openViewBuilder) setBuilderPanel(undefined)
        setState({ ...canvasState, canvas: { base, tables, views, table, view, schema: null, records: null, presentation: null } })
        return true
      }
      const [schema, presentation, records, builder, builderContext, detail] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'table', table.id, 'schema'), queryFn: ({ signal }) => api.tableSchema(table.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'presentation'), queryFn: ({ signal }) => api.viewPresentation(view.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'records', null), queryFn: ({ signal }) => api.viewRecords(view.id, undefined, { signal }) }),
        readV1BuilderForCanvas(scope, view),
        target?.openViewBuilder
          ? queryClient.fetchQuery({ queryKey: viewBuilderKeys.context(scope, table.id), queryFn: ({ signal }) => api.viewBuilderContext(table.id, { signal }) })
          : Promise.resolve(undefined),
        target?.recordId
          ? queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'record', target.recordId), queryFn: ({ signal }) => api.recordDetail(target.recordId!, { signal }) })
          : Promise.resolve(undefined),
      ])
      if (!isCurrent()) return false
      if (detail && detail.table_id !== table.id) return false
      setState({ ...canvasState, canvas: { base, tables, views, table, view, schema, presentation: builder ? canvasPresentationFromV1Builder(builder) : presentation, serverQuerySummary: builder ? v1ServerQuerySummary(builder) : undefined, records, ...(detail ? { detail } : {}) } })
      if (target?.openViewBuilder) setBuilderPanel(builder && builderContext
        ? { mode: 'view', tableId: table.id, context: builderContext, builder }
        : undefined)
      return true
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return false
      if (target?.openViewBuilder) setBuilderPanel(undefined)
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
      } else {
        setState({ status: 'error' })
      }
      return false
    }
  }

  async function recoverTelegramDeepLink(destination?: TelegramDeepLinkDestination) {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    await clearTelegramDeepLinkQueries(queryClient, scope, {
      recordId: destination?.recordId,
      draftId: destination?.draftId,
    })
    pendingTelegramDestination.current = null
    setTelegramRecovery(true)
    await loadWorkspaceHome(readyState.bootstrap, workspaceId)
  }

  telegramDestinationHandoff.current = async (destination) => {
    const handoffLaunchVersion = telegramLaunchRequestVersion.current
    const canRecover = () => !sessionInvalidated.current && telegramLaunchRequestVersion.current === handoffLaunchVersion
    const workspaceId = readyState.home.workspace_id
    if (destination.workspaceId !== workspaceId) {
      if (canRecover()) await recoverTelegramDeepLink(destination)
      return
    }
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    try {
      if (destination.kind === 'record_change_draft') {
        if (!destination.draftId || !await openDraftEmployeeHub(undefined, destination.draftId)) {
          if (canRecover()) await recoverTelegramDeepLink(destination)
        }
        return
      }
      if (!destination.baseId) {
        if (canRecover()) await recoverTelegramDeepLink(destination)
        return
      }
      const bases = await queryClient.fetchQuery({
        queryKey: protectedQueryKey(scope, 's6', 'bases'),
        queryFn: ({ signal }) => api.workspaceBases(workspaceId, { signal }),
      })
      const base = bases.bases.find((item) => item.id === destination.baseId)
      if (!base) {
        if (canRecover()) await recoverTelegramDeepLink(destination)
        return
      }
      const target: CanvasTarget | undefined = destination.kind === 'base'
        ? undefined
        : {
            ...(destination.tableId ? { tableId: destination.tableId } : {}),
            ...(destination.viewId ? { viewId: destination.viewId } : {}),
            ...(destination.recordId ? { recordId: destination.recordId } : {}),
          }
      if (!await openBase(base, target) && canRecover()) await recoverTelegramDeepLink(destination)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (canRecover()) await recoverTelegramDeepLink(destination)
    }
  }

  async function refreshBuilderHome(scope: { userId: string; workspaceId: string }): Promise<WorkspaceHome> {
    const homeKey = protectedQueryKey(scope, 'home')
    await queryClient.cancelQueries({ queryKey: homeKey })
    queryClient.removeQueries({ queryKey: homeKey })
    return queryClient.fetchQuery({ queryKey: homeKey, queryFn: ({ signal }) => api.workspaceHome(scope.workspaceId, { signal }) })
  }

  function closeTemplateImport() {
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    templateImportRequestVersion.current += 1
    setTemplateImportPanel(undefined)
    const trigger = templateImportReturnFocus.current
    templateImportReturnFocus.current = null
    void clearTemplateImportQueries(queryClient, scope)
    queueMicrotask(() => {
      if (trigger?.isConnected) trigger.focus()
    })
  }

  function closeDraftEmployeeHub() {
    draftEmployeeRequestVersion.current += 1
    setDraftEmployeePanel(undefined)
    const trigger = draftEmployeeReturnFocus.current
    draftEmployeeReturnFocus.current = null
    queueMicrotask(() => {
      if (trigger?.isConnected) trigger.focus()
    })
  }

  function closeAssistantContext() {
    assistantContextRequestVersion.current += 1
    setAssistantContextPanel(undefined)
    const trigger = assistantContextReturnFocus.current
    assistantContextReturnFocus.current = null
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    void clearAssistantContextQueries(queryClient, scope)
    queueMicrotask(() => {
      if (trigger?.isConnected) trigger.focus()
    })
  }

  function closeTeamBot() {
    teamBotRequestVersion.current += 1
    setTeamBotPanel(undefined)
    const trigger = teamBotReturnFocus.current
    teamBotReturnFocus.current = null
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    void clearTeamBotQueries(queryClient, scope)
    queueMicrotask(() => {
      if (trigger?.isConnected) trigger.focus()
    })
  }

  function closeDigitalEmployeeManagement() {
    const panel = digitalEmployeeManagementPanel
    digitalEmployeeManagementRequestVersion.current += 1
    setDigitalEmployeeManagementPanel(undefined)
    const trigger = digitalEmployeeManagementReturnFocus.current
    digitalEmployeeManagementReturnFocus.current = null
    if (panel) {
      const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
      void clearDigitalEmployeeManagementQueries(queryClient, scope)
    }
    queueMicrotask(() => {
      if (trigger?.isConnected) trigger.focus()
    })
  }

  async function openDigitalEmployeeManagement(trigger: HTMLElement): Promise<void> {
    const base = readyState.canvas?.base
    if (!base) return
    digitalEmployeeManagementReturnFocus.current = trigger
    await refreshDigitalEmployeeManagement(base.id, null)
  }

  async function refreshDigitalEmployeeManagement(baseId: string, selectedEmployeeId: string | null): Promise<void> {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++digitalEmployeeManagementRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && digitalEmployeeManagementRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
      && readyState.canvas?.base.id === baseId
    setDigitalEmployeeManagementPanel({ baseId, context: null, directory: null, detail: null, selectedEmployeeId, loading: true, failed: false })
    try {
      const [context, directory] = await Promise.all([
        queryClient.fetchQuery({ queryKey: digitalEmployeeManagementKeys.context(scope, baseId), queryFn: ({ signal }) => api.getDigitalEmployeeManagementContext(baseId, { signal }) }),
        queryClient.fetchQuery({ queryKey: digitalEmployeeManagementKeys.directory(scope, baseId, null), queryFn: ({ signal }) => api.listManagedDigitalEmployees(baseId, null, { signal }) }),
      ])
      if (!isCurrent()) {
        await clearDigitalEmployeeManagementQueries(queryClient, scope)
        return
      }
      const employeeId = selectedEmployeeId && directory.employees.some((employee) => employee.id === selectedEmployeeId)
        ? selectedEmployeeId
        : null
      const detail = employeeId
        ? await queryClient.fetchQuery({ queryKey: digitalEmployeeManagementKeys.detail(scope, employeeId), queryFn: ({ signal }) => api.getManagedDigitalEmployee(employeeId, { signal }) })
        : null
      if (!isCurrent()) {
        await clearDigitalEmployeeManagementQueries(queryClient, scope)
        return
      }
      setDigitalEmployeeManagementPanel({ baseId, context, directory, detail, selectedEmployeeId: employeeId, loading: false, failed: false })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
      } else if (error instanceof ApiError && error.status === 404) {
        await clearDigitalEmployeeManagementQueries(queryClient, scope)
        if (isCurrent()) setDigitalEmployeeManagementPanel(undefined)
      } else if (isCurrent()) {
        setDigitalEmployeeManagementPanel({ baseId, context: null, directory: null, detail: null, selectedEmployeeId, loading: false, failed: true })
      }
    }
  }

  async function selectDigitalEmployeeManagementEmployee(employeeId: string): Promise<void> {
    const panel = digitalEmployeeManagementPanel
    if (!panel || !panel.directory?.employees.some((employee) => employee.id === employeeId)) return
    await refreshDigitalEmployeeManagement(panel.baseId, employeeId)
  }

  async function mutateDigitalEmployeeManagement(
    employeeId: string | null,
    operation: () => Promise<void>,
  ): Promise<void> {
    const panel = digitalEmployeeManagementPanel
    if (!panel) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = digitalEmployeeManagementRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && digitalEmployeeManagementRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
      && digitalEmployeeManagementPanel?.baseId === panel.baseId
    try {
      await operation()
      if (!isCurrent()) {
        await clearDigitalEmployeeManagementQueries(queryClient, scope)
        return
      }
      await clearDigitalEmployeeManagementQueries(queryClient, scope)
      if (!isCurrent()) return
      await refreshDigitalEmployeeManagement(panel.baseId, employeeId)
    } catch (error) {
      if (!isCurrent()) {
        await clearDigitalEmployeeManagementQueries(queryClient, scope)
        return
      }
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) {
        await clearDigitalEmployeeManagementQueries(queryClient, scope)
        if (isCurrent()) setDigitalEmployeeManagementPanel(undefined)
      }
      throw error
    }
  }

  async function createManagedDigitalEmployee(values: { name: string; description: string; telegramAlias: string | null }): Promise<void> {
    const panel = digitalEmployeeManagementPanel
    if (!panel) return
    let createdId: string | null = null
    await mutateDigitalEmployeeManagement(null, async () => {
      const created = await api.createManagedDigitalEmployee(panel.baseId, values, crypto.randomUUID())
      createdId = created.id
    })
    if (createdId) await refreshDigitalEmployeeManagement(panel.baseId, createdId)
  }

  async function updateManagedDigitalEmployee(employeeId: string, values: ManagedEmployeeUpdateValues, expectedVersion: number): Promise<void> {
    await mutateDigitalEmployeeManagement(employeeId, async () => {
      await api.updateManagedDigitalEmployee(employeeId, values, expectedVersion)
    })
  }

  async function replaceManagedDigitalEmployeeGrants(employeeId: string, memberIds: string[], expectedVersion: number): Promise<void> {
    await mutateDigitalEmployeeManagement(employeeId, async () => {
      await api.replaceManagedDigitalEmployeeGrants(employeeId, memberIds, expectedVersion, crypto.randomUUID())
    })
  }

  async function activateManagedDigitalEmployee(employeeId: string, expectedVersion: number): Promise<void> {
    await mutateDigitalEmployeeManagement(employeeId, async () => {
      await api.activateManagedDigitalEmployee(employeeId, expectedVersion, crypto.randomUUID())
    })
  }

  async function pauseManagedDigitalEmployee(employeeId: string, expectedVersion: number): Promise<void> {
    await mutateDigitalEmployeeManagement(employeeId, async () => {
      await api.pauseManagedDigitalEmployee(employeeId, expectedVersion, crypto.randomUUID())
    })
  }

  async function openAssistantContext(trigger?: HTMLElement): Promise<boolean> {
    if (trigger) assistantContextReturnFocus.current = trigger
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++assistantContextRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && assistantContextRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setAssistantContextPanel({ contacts: [], selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: true, failed: false })
    try {
      const contacts = await queryClient.fetchQuery({
        queryKey: draftEmployeeKeys.contacts(scope, null),
        queryFn: ({ signal }) => api.listS5Contacts(workspaceId, null, { signal }),
      })
      if (isCurrent()) {
        setAssistantContextPanel({ contacts: contacts.contacts, selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: false, failed: false })
        return true
      }
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return false
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (isCurrent()) setAssistantContextPanel({ contacts: [], selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: false, failed: true })
    }
    return false
  }

  async function selectAssistantContextEmployee(employeeId: string): Promise<void> {
    const panel = assistantContextPanel
    const contact = panel?.contacts.find((item) => item.id === employeeId)
    if (!panel || !contact) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++assistantContextRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && assistantContextRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setAssistantContextPanel({ ...panel, selectedEmployeeId: employeeId, context: null, selectedView: null, summary: null, loading: true, failed: false })
    try {
      const context = await queryClient.fetchQuery({
        queryKey: draftEmployeeKeys.assistantContext(scope, employeeId, null),
        queryFn: ({ signal }) => api.getAssistantContext(employeeId, null, { signal }),
      })
      if (!isCurrent()) return
      if (context.employee.id !== contact.id || context.employee.baseId !== contact.baseId) throw new Error('Assistant context does not match selected contact')
      setAssistantContextPanel({ contacts: panel.contacts, selectedEmployeeId: employeeId, context, selectedView: null, summary: null, loading: false, failed: false })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else {
        if (error instanceof ApiError && error.status === 404) await clearAssistantContextQueries(queryClient, scope, employeeId)
        if (isCurrent()) setAssistantContextPanel({ contacts: panel.contacts, selectedEmployeeId: employeeId, context: null, selectedView: null, summary: null, loading: false, failed: true })
      }
    }
  }

  async function selectAssistantContextView(viewId: string): Promise<void> {
    const panel = assistantContextPanel
    const context = panel?.context
    if (!panel || !context || !context.views.some((view) => view.id === viewId)) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++assistantContextRequestVersion.current
    const employeeId = context.employee.id
    const isCurrent = () => !sessionInvalidated.current
      && assistantContextRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setAssistantContextPanel({ ...panel, selectedView: null, summary: null, loading: true, failed: false })
    try {
      const selectedView = await queryClient.fetchQuery({
        queryKey: draftEmployeeKeys.assistantView(scope, employeeId, viewId),
        queryFn: ({ signal }) => api.getAssistantSelectedView(employeeId, viewId, { signal }),
      })
      if (!isCurrent()) return
      if (selectedView.id !== viewId || selectedView.baseId !== context.employee.baseId) throw new Error('Assistant view no longer matches context')
      setAssistantContextPanel({ ...panel, selectedView, summary: null, loading: false, failed: false })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else {
        if (error instanceof ApiError && error.status === 404) await clearAssistantContextQueries(queryClient, scope, employeeId)
        if (isCurrent()) setAssistantContextPanel({ contacts: panel.contacts, selectedEmployeeId: panel.selectedEmployeeId, context: null, selectedView: null, summary: null, loading: false, failed: true })
      }
    }
  }

  async function summarizeAssistantContext(instruction?: string): Promise<void> {
    const panel = assistantContextPanel
    const context = panel?.context
    const selectedView = panel?.selectedView
    if (!panel || !context || !selectedView || selectedView.baseId !== context.employee.baseId) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++assistantContextRequestVersion.current
    const employeeId = context.employee.id
    const isCurrent = () => !sessionInvalidated.current
      && assistantContextRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setAssistantContextPanel({ ...panel, loading: true, failed: false })
    try {
      const viewKey = draftEmployeeKeys.assistantView(scope, employeeId, selectedView.id)
      await queryClient.cancelQueries({ queryKey: viewKey })
      queryClient.removeQueries({ queryKey: viewKey })
      const reread = await queryClient.fetchQuery({
        queryKey: viewKey,
        queryFn: ({ signal }) => api.getAssistantSelectedView(employeeId, selectedView.id, { signal }),
      })
      if (!isCurrent()) return
      if (reread.id !== selectedView.id || reread.baseId !== context.employee.baseId) throw new Error('Assistant view reread does not match context')
      const result = await api.invokeS5Employee(employeeId, {
        intent: 'summarize',
        baseId: reread.baseId,
        viewId: reread.id,
        ...(instruction ? { instruction } : {}),
      })
      if (!isCurrent()) return
      if (result.kind !== 'summary') throw new Error('Assistant context summary returned an unsupported result')
      setAssistantContextPanel({ ...panel, selectedView: reread, summary: result, loading: false, failed: false })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else {
        if (error instanceof ApiError && error.status === 404) await clearAssistantContextQueries(queryClient, scope, employeeId)
        if (isCurrent()) setAssistantContextPanel({ contacts: [], selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: false, failed: true })
      }
    }
  }

  async function openAssistantContextBase(): Promise<void> {
    const panel = assistantContextPanel
    const baseId = panel?.selectedView?.baseId
    if (!panel || !baseId || panel.context?.employee.baseId !== baseId) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = assistantContextRequestVersion.current
    try {
      let base = readyState.home.recent_bases.find((item) => item.id === baseId)
      if (!base) {
        const directory = await queryClient.fetchQuery({
          queryKey: navigationKeys.bases(scope),
          queryFn: ({ signal }) => api.workspaceBases(workspaceId, { signal }),
        })
        if (assistantContextRequestVersion.current !== requestVersion || activeWorkspaceId.current !== workspaceId) return
        base = directory.bases.find((item) => item.id === baseId)
      }
      if (!base) throw new Error('Assistant Base is unavailable')
      assistantContextRequestVersion.current += 1
      setAssistantContextPanel(undefined)
      await clearAssistantContextQueries(queryClient, scope)
      await openBase(base)
    } catch (error) {
      if (assistantContextRequestVersion.current !== requestVersion || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else setAssistantContextPanel({ contacts: [], selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: false, failed: true })
    }
  }

  async function openTeamBot(trigger?: HTMLElement): Promise<boolean> {
    if (trigger) teamBotReturnFocus.current = trigger
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++teamBotRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && teamBotRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setTeamBotPanel({ contacts: [], selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: true, failed: false })
    try {
      const contacts = await queryClient.fetchQuery({
        queryKey: teamBotKeys.contacts(scope, null),
        queryFn: ({ signal }) => api.listTeamBotContacts(workspaceId, null, { signal }),
      })
      if (isCurrent()) {
        setTeamBotPanel({ contacts: contacts.contacts, selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: false, failed: false })
        return true
      }
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return false
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (isCurrent()) setTeamBotPanel({ contacts: [], selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: false, failed: true })
    }
    return false
  }

  async function selectTeamBotEmployee(employeeId: string): Promise<void> {
    const panel = teamBotPanel
    const contact = panel?.contacts.find((item) => item.id === employeeId)
    if (!panel || !contact) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++teamBotRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && teamBotRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setTeamBotPanel({ ...panel, selectedEmployeeId: employeeId, context: null, selectedView: null, summary: null, loading: true, failed: false })
    try {
      const context = await queryClient.fetchQuery({
        queryKey: teamBotKeys.contexts(scope, employeeId, null),
        queryFn: ({ signal }) => api.getTeamBotKnowledgeContexts(employeeId, null, { signal }),
      })
      if (!isCurrent()) return
      if (context.employee.id !== contact.id || context.employee.baseId !== contact.baseId) throw new Error('Team Bot context does not match selected contact')
      setTeamBotPanel({ contacts: panel.contacts, selectedEmployeeId: employeeId, context, selectedView: null, summary: null, loading: false, failed: false })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else {
        if (error instanceof ApiError && error.status === 404) await clearTeamBotQueries(queryClient, scope, employeeId)
        if (isCurrent()) setTeamBotPanel({ contacts: panel.contacts, selectedEmployeeId: employeeId, context: null, selectedView: null, summary: null, loading: false, failed: true })
      }
    }
  }

  async function selectTeamBotView(viewId: string): Promise<void> {
    const panel = teamBotPanel
    const context = panel?.context
    if (!panel || !context || !context.views.some((view) => view.id === viewId)) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++teamBotRequestVersion.current
    const employeeId = context.employee.id
    const isCurrent = () => !sessionInvalidated.current
      && teamBotRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setTeamBotPanel({ ...panel, selectedView: null, summary: null, loading: true, failed: false })
    try {
      const selectedView = await queryClient.fetchQuery({
        queryKey: teamBotKeys.selectedView(scope, employeeId, viewId),
        queryFn: ({ signal }) => api.getTeamBotKnowledgeContextView(employeeId, viewId, { signal }),
      })
      if (!isCurrent()) return
      if (selectedView.id !== viewId || selectedView.baseId !== context.employee.baseId) throw new Error('Team Bot view no longer matches context')
      setTeamBotPanel({ ...panel, selectedView, summary: null, loading: false, failed: false })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else {
        if (error instanceof ApiError && error.status === 404) await clearTeamBotQueries(queryClient, scope, employeeId)
        if (isCurrent()) setTeamBotPanel({ contacts: panel.contacts, selectedEmployeeId: panel.selectedEmployeeId, context: null, selectedView: null, summary: null, loading: false, failed: true })
      }
    }
  }

  async function summarizeTeamBot(instruction?: string): Promise<void> {
    const panel = teamBotPanel
    const context = panel?.context
    const selectedView = panel?.selectedView
    if (!panel || !context || !selectedView || selectedView.baseId !== context.employee.baseId) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++teamBotRequestVersion.current
    const employeeId = context.employee.id
    const isCurrent = () => !sessionInvalidated.current
      && teamBotRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setTeamBotPanel({ ...panel, loading: true, failed: false })
    try {
      const viewKey = teamBotKeys.selectedView(scope, employeeId, selectedView.id)
      await queryClient.cancelQueries({ queryKey: viewKey })
      queryClient.removeQueries({ queryKey: viewKey })
      const reread = await queryClient.fetchQuery({
        queryKey: viewKey,
        queryFn: ({ signal }) => api.getTeamBotKnowledgeContextView(employeeId, selectedView.id, { signal }),
      })
      if (!isCurrent()) return
      if (reread.id !== selectedView.id || reread.baseId !== context.employee.baseId) throw new Error('Team Bot view reread does not match context')
      const summary = await api.summarizeTeamBot(employeeId, {
        baseId: reread.baseId,
        viewId: reread.id,
        ...(instruction ? { instruction } : {}),
      }, crypto.randomUUID())
      if (!isCurrent()) return
      setTeamBotPanel({ ...panel, selectedView: reread, summary, loading: false, failed: false })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else {
        if (error instanceof ApiError && error.status === 404) {
          await clearTeamBotQueries(queryClient, scope, employeeId)
          if (isCurrent()) setTeamBotPanel({ contacts: [], selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: false, failed: true })
        } else if (isCurrent()) {
          setTeamBotPanel((current) => current ? {
            ...current,
            summary: null,
            loading: false,
            failed: true,
          } : current)
        }
      }
    }
  }

  async function openTeamBotBase(): Promise<void> {
    const panel = teamBotPanel
    const baseId = panel?.selectedView?.baseId
    if (!panel || !baseId || panel.context?.employee.baseId !== baseId) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = teamBotRequestVersion.current
    try {
      let base = readyState.home.recent_bases.find((item) => item.id === baseId)
      if (!base) {
        const directory = await queryClient.fetchQuery({
          queryKey: navigationKeys.bases(scope),
          queryFn: ({ signal }) => api.workspaceBases(workspaceId, { signal }),
        })
        if (teamBotRequestVersion.current !== requestVersion || activeWorkspaceId.current !== workspaceId) return
        base = directory.bases.find((item) => item.id === baseId)
      }
      if (!base) throw new Error('Team Bot Base is unavailable')
      teamBotRequestVersion.current += 1
      setTeamBotPanel(undefined)
      await clearTeamBotQueries(queryClient, scope)
      await openBase(base)
    } catch (error) {
      if (teamBotRequestVersion.current !== requestVersion || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else setTeamBotPanel({ contacts: [], selectedEmployeeId: null, context: null, selectedView: null, summary: null, loading: false, failed: true })
    }
  }

  function currentS5InvocationContext(): CurrentCanvasInvocationContext | null {
    const canvas = readyState.canvas
    if (!canvas?.view) return null
    return { baseId: canvas.base.id, viewId: canvas.view.id, recordId: canvas.detail?.id ?? null }
  }

  async function openDraftEmployeeHub(trigger?: HTMLElement, draftId?: string): Promise<boolean> {
    if (trigger) draftEmployeeReturnFocus.current = trigger
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++draftEmployeeRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && draftEmployeeRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setDraftEmployeePanel({ contacts: [], draft: null, loading: true, targetDraftId: draftId ?? null, failed: false })
    try {
      const [contacts, draft] = await Promise.all([
        queryClient.fetchQuery({
          queryKey: draftEmployeeKeys.contacts(scope, null),
          queryFn: ({ signal }) => api.listS5Contacts(workspaceId, null, { signal }),
        }),
        draftId
          ? queryClient.fetchQuery({
            queryKey: draftEmployeeKeys.draft(scope, draftId),
            queryFn: ({ signal }) => api.getS5Draft(draftId, { signal }),
          })
          : Promise.resolve(null),
      ])
      if (isCurrent()) {
        setDraftEmployeePanel({ contacts: contacts.contacts, draft, loading: false, targetDraftId: draftId ?? null, failed: false })
        return true
      }
      return false
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return false
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (isCurrent()) setDraftEmployeePanel({ contacts: [], draft: null, loading: false, targetDraftId: draftId ?? null, failed: true })
      return false
    }
  }

  async function terminalS5Draft(action: 'confirm' | 'reject', draftId: string, expectedVersion: number): Promise<void> {
    const panel = draftEmployeePanel
    const draft = panel?.draft
    if (!draft || draft.id !== draftId || draft.version !== expectedVersion) throw new Error('Draft is unavailable')
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = draftEmployeeRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && draftEmployeeRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    try {
      if (action === 'confirm') await api.confirmS5Draft(draftId, expectedVersion, crypto.randomUUID())
      else await api.rejectS5Draft(draftId, expectedVersion, crypto.randomUUID())
      if (!isCurrent()) return
      await clearDraftEmployeeTerminalQueries(queryClient, scope, draft)
      if (!isCurrent()) return
      const [contacts, rereadDraft] = await Promise.all([
        queryClient.fetchQuery({
          queryKey: draftEmployeeKeys.contacts(scope, null),
          queryFn: ({ signal }) => api.listS5Contacts(workspaceId, null, { signal }),
        }),
        queryClient.fetchQuery({
          queryKey: draftEmployeeKeys.draft(scope, draftId),
          queryFn: ({ signal }) => api.getS5Draft(draftId, { signal }),
        }),
      ])
      if (!isCurrent()) {
        await clearDraftEmployeeTerminalQueries(queryClient, scope, draft)
        return
      }
      setDraftEmployeePanel({ contacts: contacts.contacts, draft: rereadDraft, loading: false, targetDraftId: draftId, failed: false })
    } catch (error) {
      if (!isCurrent()) {
        await clearDraftEmployeeTerminalQueries(queryClient, scope, draft)
        return
      }
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) {
        await clearDraftEmployeeTerminalQueries(queryClient, scope, draft)
        if (isCurrent()) setDraftEmployeePanel((current) => current ? { ...current, draft: null, loading: false, failed: true } : current)
      } else if (isCurrent()) {
        setDraftEmployeePanel((current) => current ? { ...current, failed: true } : current)
      }
      throw error
    }
  }

  async function invokeS5Employee(
    employeeId: string,
    request: S5InvocationRequest,
    idempotencyKey?: string,
  ): Promise<S5InvocationResult> {
    const context = currentS5InvocationContext()
    const matchesCurrentContext = () => {
      const current = currentS5InvocationContext()
      return current?.baseId === request.baseId
        && current.viewId === request.viewId
        && (request.intent === 'summarize' || current.recordId === request.recordId)
    }
    if (!context || !matchesCurrentContext()) throw new DOMException('Canvas context is unavailable', 'AbortError')
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = draftEmployeeRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && draftEmployeeRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === workspaceId
      && matchesCurrentContext()
    try {
      const result = await api.invokeS5Employee(employeeId, request, idempotencyKey)
      if (!isCurrent()) throw new DOMException('Obsolete Canvas invocation', 'AbortError')
      if (result.kind === 'draft') {
        const draft = await queryClient.fetchQuery({
          queryKey: draftEmployeeKeys.draft(scope, result.draftId),
          queryFn: ({ signal }) => api.getS5Draft(result.draftId, { signal }),
        })
        if (!isCurrent()) throw new DOMException('Obsolete Canvas invocation', 'AbortError')
        setDraftEmployeePanel((current) => current
          ? { ...current, draft, targetDraftId: draft.id, loading: false, failed: false }
          : current)
      }
      return result
    } catch (error) {
      if (isAbortError(error)) throw error
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) {
        await clearDraftEmployeeTerminalQueries(queryClient, scope, { id: 's5-invocation', recordId: request.intent === 'draft_update' ? request.recordId : null })
      }
      throw error
    }
  }

  function closeGovernance() {
    const workspaceId = readyState.home.workspace_id
    governanceRequestVersion.current += 1
    setGovernancePanel(undefined)
    governanceReturnFocus.current?.focus()
    governanceReturnFocus.current = null
    void clearGovernanceQueries(queryClient, {
      userId: readyState.bootstrap.identity.user_id,
      workspaceId,
    })
  }

  async function openGovernance(trigger?: HTMLElement) {
    governanceReturnFocus.current = trigger ?? governanceReturnFocus.current
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++governanceRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && governanceRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setGovernancePanel({
      members: null,
      audit: null,
      selectedBaseId: null,
      membersLoading: true,
      auditLoading: false,
      membersError: false,
      auditError: false,
      membersLoadMoreError: false,
      auditLoadMoreError: false,
    })
    try {
      const members = await queryClient.fetchQuery({
        queryKey: governanceKeys.members(scope, null),
        queryFn: ({ signal }) => api.listGovernanceMembers(workspaceId, null, { signal }),
      })
      if (isCurrent()) setGovernancePanel((current) => current ? {
        ...current,
        members,
        membersLoading: false,
        membersError: false,
      } : current)
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
      } else {
        setGovernancePanel((current) => current ? {
          ...current,
          membersLoading: false,
          membersError: true,
        } : current)
      }
    }
  }

  function closeGovernanceWrite() {
    governanceWriteRequestVersion.current += 1
    setGovernanceWritePanel(undefined)
    const trigger = governanceWriteReturnFocus.current
    governanceWriteReturnFocus.current = null
    queueMicrotask(() => {
      if (trigger?.isConnected) trigger.focus()
    })
  }

  async function openGovernanceWrite(trigger: HTMLElement) {
    governanceWriteReturnFocus.current = trigger
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++governanceWriteRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && governanceWriteRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setGovernanceWritePanel({
      members: null,
      tables: [],
      views: [],
      fields: null,
      selectedBaseId: null,
      selectedTableId: null,
      membersLoading: true,
      tablesLoading: false,
      fieldsLoading: false,
      contextError: undefined,
    })
    try {
      const members = await queryClient.fetchQuery({
        queryKey: governanceWriteKeys.members(scope, null),
        queryFn: ({ signal }) => api.listGovernanceEditableMembers(workspaceId, null, { signal }),
      })
      if (isCurrent()) setGovernanceWritePanel((current) => current ? { ...current, members, membersLoading: false } : current)
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else setGovernanceWritePanel((current) => current ? { ...current, membersLoading: false } : current)
    }
  }

  async function selectGovernanceWriteBase(baseId: string) {
    const panel = governanceWritePanel
    if (!panel || !baseId) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++governanceWriteRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && governanceWriteRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setGovernanceWritePanel((current) => current ? {
      ...current, selectedBaseId: baseId, selectedTableId: null, tables: [], views: [], fields: null, tablesLoading: true, fieldsLoading: false, contextError: undefined,
    } : current)
    try {
      const [{ tables }, { views }] = await Promise.all([
        queryClient.fetchQuery({
          queryKey: protectedQueryKey(scope, 'governance-write', 'tables', baseId),
          queryFn: ({ signal }) => api.baseTables(baseId, { signal }),
        }),
        queryClient.fetchQuery({
          queryKey: protectedQueryKey(scope, 'governance-write', 'views', baseId),
          queryFn: ({ signal }) => api.baseViews(baseId, { signal }),
        }),
      ])
      if (isCurrent()) setGovernanceWritePanel((current) => current?.selectedBaseId === baseId
        ? { ...current, tables, views, tablesLoading: false }
        : current)
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) {
        await clearGovernanceWriteQueries(queryClient, scope)
        setGovernanceWritePanel((current) => current?.selectedBaseId === baseId
          ? { ...current, selectedBaseId: null, selectedTableId: null, tables: [], views: [], fields: null, tablesLoading: false, fieldsLoading: false, contextError: 'base_not_available' }
          : current)
      } else setGovernanceWritePanel((current) => current ? { ...current, tablesLoading: false } : current)
    }
  }

  async function selectGovernanceWriteTable(tableId: string) {
    const panel = governanceWritePanel
    if (!panel || !tableId) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++governanceWriteRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && governanceWriteRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setGovernanceWritePanel((current) => current ? {
      ...current, selectedTableId: tableId, fields: null, fieldsLoading: true, contextError: undefined,
    } : current)
    try {
      const fields = await queryClient.fetchQuery({
        queryKey: governanceWriteKeys.fieldPermissions(scope, tableId),
        queryFn: ({ signal }) => api.listGovernanceFieldPermissions(tableId, { signal }),
      })
      if (isCurrent()) setGovernanceWritePanel((current) => current?.selectedTableId === tableId
        ? { ...current, fields, fieldsLoading: false }
        : current)
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else {
        if (error instanceof ApiError && error.status === 404) {
          await clearGovernanceWriteQueries(queryClient, scope, tableId)
          setGovernanceWritePanel((current) => current?.selectedTableId === tableId
            ? { ...current, selectedTableId: null, fields: null, fieldsLoading: false, contextError: 'table_not_available' }
            : current)
        } else setGovernanceWritePanel((current) => current?.selectedTableId === tableId ? { ...current, fieldsLoading: false } : current)
      }
    }
  }

  async function openGovernanceV1ViewAccess(viewId: string) {
    const panel = governanceWritePanel
    const view = panel?.views.find((item) => item.id === viewId && item.scope === 'restricted' && item.caller_access_level === 'owner' && item.table_id)
    const base = readyState.home.recent_bases.find((item) => item.id === panel?.selectedBaseId)
    if (!view?.table_id || !base) return
    const builderVersion = ++builderRequestVersion.current
    setBuilderPanel({ mode: 'view-loading', tableId: view.table_id, viewId: view.id })
    closeGovernanceWrite()
    closeGovernance()
    await openBase(base, { tableId: view.table_id, viewId: view.id, openViewBuilder: true }, readyState.home, builderVersion)
  }

  async function refreshGovernanceWriteMemberContext(
    scope: { userId: string; workspaceId: string },
    requestVersion = governanceWriteRequestVersion.current,
  ) {
    const isCurrent = () => !sessionInvalidated.current
      && governanceWriteRequestVersion.current === requestVersion
      && activeWorkspaceId.current === scope.workspaceId
    if (!isCurrent()) return
    await clearGovernanceWriteQueries(queryClient, scope)
    if (!isCurrent()) return
    const members = await queryClient.fetchQuery({
      queryKey: governanceWriteKeys.members(scope, null),
      queryFn: ({ signal }) => api.listGovernanceEditableMembers(scope.workspaceId, null, { signal }),
    })
    if (!isCurrent()) {
      await clearGovernanceWriteQueries(queryClient, scope)
      return
    }
    setGovernanceWritePanel((current) => current ? { ...current, members, membersLoading: false } : current)
  }

  async function changeGovernanceWriteRole(memberId: string, role: 'admin' | 'builder' | 'operator' | 'viewer', expectedVersion: number): Promise<void> {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = governanceWriteRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && governanceWriteRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    try {
      await api.changeGovernanceMemberRole(workspaceId, memberId, role, expectedVersion, crypto.randomUUID())
      if (!isCurrent()) return
      await refreshGovernanceWriteMemberContext(scope, requestVersion)
    } catch (error) {
      if (!isCurrent()) {
        await clearGovernanceWriteQueries(queryClient, scope)
        return
      }
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) await clearGovernanceWriteQueries(queryClient, scope)
      throw error
    }
  }

  async function replaceGovernanceWriteFieldPolicy(fieldId: string, policy: GovernanceFieldPermissionPolicy, expectedPermissionVersion: number): Promise<void> {
    const panel = governanceWritePanel
    const tableId = panel?.selectedTableId
    if (!tableId) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = governanceWriteRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && governanceWriteRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    try {
      await api.replaceGovernanceFieldPermissionPolicy(tableId, fieldId, policy, expectedPermissionVersion, crypto.randomUUID())
      if (!isCurrent()) return
      const viewIds = readyState.canvas?.table?.id === tableId
        ? readyState.canvas.views.filter((view) => view.table_id === tableId).map((view) => view.id)
        : []
      await Promise.all([
        clearGovernanceWriteQueries(queryClient, scope, tableId),
        clearFieldMutationQueries(queryClient, scope, tableId, viewIds),
      ])
      if (!isCurrent()) return
      const fields = await queryClient.fetchQuery({
        queryKey: governanceWriteKeys.fieldPermissions(scope, tableId),
        queryFn: ({ signal }) => api.listGovernanceFieldPermissions(tableId, { signal }),
      })
      if (!isCurrent()) {
        await clearGovernanceWriteQueries(queryClient, scope, tableId)
        return
      }
      setGovernanceWritePanel((current) => current?.selectedTableId === tableId ? { ...current, fields, fieldsLoading: false } : current)
    } catch (error) {
      if (!isCurrent()) {
        await clearGovernanceWriteQueries(queryClient, scope, tableId)
        return
      }
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) await clearGovernanceWriteQueries(queryClient, scope, tableId)
      throw error
    }
  }

  async function reloadGovernanceWriteFieldContext(): Promise<void> {
    const panel = governanceWritePanel
    const tableId = panel?.selectedTableId
    if (!tableId) throw new Error('No governance table is selected.')
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    setGovernanceWritePanel((current) => current?.selectedTableId === tableId
      ? { ...current, fieldsLoading: true, contextError: undefined }
      : current)
    try {
      await clearGovernanceWriteQueries(queryClient, scope, tableId)
      const fields = await queryClient.fetchQuery({
        queryKey: governanceWriteKeys.fieldPermissions(scope, tableId),
        queryFn: ({ signal }) => api.listGovernanceFieldPermissions(tableId, { signal }),
      })
      setGovernanceWritePanel((current) => current?.selectedTableId === tableId
        ? { ...current, fields, fieldsLoading: false }
        : current)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
        return
      }
      if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
        return
      }
      if (error instanceof ApiError && error.status === 404) {
        await clearGovernanceWriteQueries(queryClient, scope, tableId)
        setGovernanceWritePanel((current) => current?.selectedTableId === tableId
          ? { ...current, selectedTableId: null, fields: null, fieldsLoading: false, contextError: 'table_not_available' }
          : current)
        return
      }
      setGovernanceWritePanel((current) => current?.selectedTableId === tableId
        ? { ...current, fieldsLoading: false }
        : current)
      throw error
    }
  }

  async function selectGovernanceBase(baseId: string) {
    if (!baseId || !governancePanel) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const previousBaseId = governancePanel.selectedBaseId
    const requestVersion = ++governanceRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && governanceRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    if (previousBaseId) await clearGovernanceQueries(queryClient, scope, previousBaseId)
    setGovernancePanel((current) => current ? {
      ...current,
      selectedBaseId: baseId,
      audit: null,
      auditLoading: true,
      auditError: false,
      auditLoadMoreError: false,
    } : current)
    try {
      const audit = await queryClient.fetchQuery({
        queryKey: governanceKeys.audit(scope, baseId, null),
        queryFn: ({ signal }) => api.listGovernanceAuditEvents(baseId, null, { signal }),
      })
      if (isCurrent()) setGovernancePanel((current) => current?.selectedBaseId === baseId ? {
        ...current,
        audit,
        auditLoading: false,
        auditError: false,
      } : current)
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
      } else {
        if (error instanceof ApiError && error.status === 404) {
          await clearGovernanceQueries(queryClient, scope, baseId)
        }
        setGovernancePanel((current) => current?.selectedBaseId === baseId ? {
          ...current,
          auditLoading: false,
          auditError: true,
        } : current)
      }
    }
  }

  async function loadMoreGovernanceMembers() {
    const panel = governancePanel
    const workspaceId = readyState.home.workspace_id
    const cursor = panel?.members?.nextCursor
    if (!panel?.members || !cursor || panel.membersLoading) return
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++governanceRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && governanceRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setGovernancePanel((current) => current ? { ...current, membersLoading: true, membersLoadMoreError: false } : current)
    try {
      const page = await queryClient.fetchQuery({
        queryKey: governanceKeys.members(scope, cursor),
        queryFn: ({ signal }) => api.listGovernanceMembers(workspaceId, cursor, { signal }),
      })
      if (isCurrent()) setGovernancePanel((current) => {
        if (!current?.members) return current
        const knownIds = new Set(current.members.members.map((member) => member.id))
        return {
          ...current,
          members: {
            ...page,
            members: [...current.members.members, ...page.members.filter((member) => !knownIds.has(member.id))],
          },
          membersLoading: false,
          membersLoadMoreError: false,
        }
      })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else setGovernancePanel((current) => current ? { ...current, membersLoading: false, membersLoadMoreError: true } : current)
    }
  }

  async function loadMoreGovernanceAudit() {
    const panel = governancePanel
    const workspaceId = readyState.home.workspace_id
    const baseId = panel?.selectedBaseId
    const cursor = panel?.audit?.nextCursor
    if (!panel?.audit || !baseId || !cursor || panel.auditLoading) return
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++governanceRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && governanceRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setGovernancePanel((current) => current ? { ...current, auditLoading: true, auditLoadMoreError: false } : current)
    try {
      const page = await queryClient.fetchQuery({
        queryKey: governanceKeys.audit(scope, baseId, cursor),
        queryFn: ({ signal }) => api.listGovernanceAuditEvents(baseId, cursor, { signal }),
      })
      if (isCurrent()) setGovernancePanel((current) => {
        if (!current?.audit || current.selectedBaseId !== baseId) return current
        const knownIds = new Set(current.audit.events.map((event) => event.id))
        return {
          ...current,
          audit: {
            ...page,
            events: [...current.audit.events, ...page.events.filter((event) => !knownIds.has(event.id))],
          },
          auditLoading: false,
          auditLoadMoreError: false,
        }
      })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else setGovernancePanel((current) => current ? { ...current, auditLoading: false, auditLoadMoreError: true } : current)
    }
  }

  function openWorkspaceImport() {
    templateImportRequestVersion.current += 1
    setTemplateImportPanel({ mode: 'workspace-import' })
  }

  function openBaseImport(base: BaseSummary, trigger: HTMLElement) {
    templateImportRequestVersion.current += 1
    templateImportReturnFocus.current = trigger
    setTemplateImportPanel({ mode: 'base-import', base })
  }

  async function openTemplateImportHub() {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++templateImportRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && templateImportRequestVersion.current === requestVersion
      && activeWorkspaceId.current === workspaceId
    setTemplateImportPanel({ mode: 'hub', templates: [], loading: true, error: null })
    try {
      const templates = await queryClient.fetchQuery({
        queryKey: templateImportKeys.templates(scope),
        queryFn: ({ signal }) => api.listTemplates({ signal }),
      })
      if (isCurrent()) setTemplateImportPanel({ mode: 'hub', templates, loading: false, error: null })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else setTemplateImportPanel({ mode: 'hub', templates: [], loading: false, error: '模板暂时无法加载，请稍后重试。' })
    }
  }

  async function installTemplate(template: TemplateSummary) {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = templateImportRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const builderVersion = builderRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && templateImportRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === workspaceId
    try {
      const receipt = await api.installTemplate(workspaceId, template.id, readyState.bootstrap.identity.user_id, crypto.randomUUID())
      if (!isCurrent()) return
      await clearTemplateImportQueries(queryClient, scope)
      const [refreshedHome, { bases }] = await Promise.all([
        refreshBuilderHome(scope),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'bases'), queryFn: ({ signal }) => api.workspaceBases(workspaceId, { signal }) }),
      ])
      if (!isCurrent()) return
      const base = bases.find((item) => item.id === receipt.baseId)
      if (!base) throw new Error('Installed Base is unavailable')
      const opened = await openBase(base, undefined, refreshedHome, builderVersion)
      if (opened && !sessionInvalidated.current && activeWorkspaceId.current === workspaceId) setTemplateImportPanel(undefined)
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) setTemplateImportPanel({ mode: 'hub', templates: [], loading: false, error: '模板当前不可用，请刷新后重试。' })
      else setTemplateImportPanel((current) => current?.mode === 'hub' ? { ...current, loading: false, error: '安装模板失败，请稍后重试。' } : current)
    }
  }

  async function saveBaseAsTemplate(base: BaseSummary, values: { name: string; category: string; description: string }) {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    try {
      return await api.saveBaseAsTemplate(base.id, { ...values, createdByUserId: readyState.bootstrap.identity.user_id })
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      throw error
    }
  }

  async function createImportPreview(target: ImportTarget, values: Omit<CreateImportValues, 'createdByUserId'>): Promise<ImportPreview> {
    const workspaceId = target.workspaceId
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = templateImportRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current && templateImportRequestVersion.current === requestVersion && canvasRequestVersion.current === canvasVersion && activeWorkspaceId.current === workspaceId
    try {
      const preview = await api.createImport(workspaceId, { ...values, createdByUserId: readyState.bootstrap.identity.user_id }, crypto.randomUUID())
      if (!isCurrent()) throw new DOMException('Import target changed', 'AbortError')
      return preview
    } catch (error) {
      if (isAbortError(error)) throw error
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      throw error
    }
  }

  async function commitImport(target: ImportTarget, importJobId: string, values: CommitImportValues): Promise<ImportCommitReceipt> {
    const workspaceId = target.workspaceId
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = templateImportRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const builderVersion = builderRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current && templateImportRequestVersion.current === requestVersion && canvasRequestVersion.current === canvasVersion && activeWorkspaceId.current === workspaceId
    try {
      const receipt = await api.commitImport(importJobId, values, crypto.randomUUID())
      if (!isCurrent()) throw new DOMException('Import target changed', 'AbortError')
      await clearTemplateImportQueries(queryClient, scope, importJobId)
      const [refreshedHome, { bases }] = await Promise.all([
        refreshBuilderHome(scope),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'bases'), queryFn: ({ signal }) => api.workspaceBases(workspaceId, { signal }) }),
      ])
      if (!isCurrent()) throw new DOMException('Import target changed', 'AbortError')
      const base = bases.find((item) => item.id === receipt.baseId)
      if (!base) throw new Error('Committed Base is unavailable')
      const opened = await openBase(base, undefined, refreshedHome, builderVersion)
      if (!opened || !isCurrent()) throw new DOMException('Import target changed', 'AbortError')
      setTemplateImportPanel(undefined)
      return receipt
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) await clearTemplateImportQueries(queryClient, scope, importJobId)
      throw error
    }
  }

  async function createBase(values: { baseName: string; tableName: string }, idempotencyKey: string) {
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = builderRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current && builderRequestVersion.current === requestVersion && canvasRequestVersion.current === canvasVersion && activeWorkspaceId.current === workspaceId
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
        await denyInvalidSession()
        return
      }
      if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
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
    const isCurrent = () => !sessionInvalidated.current && builderRequestVersion.current === requestVersion && canvasRequestVersion.current === canvasVersion && activeWorkspaceId.current === workspaceId
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
        await denyInvalidSession()
        return
      }
      if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
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
    const isCurrent = () => !sessionInvalidated.current && builderRequestVersion.current === requestVersion
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
        await denyInvalidSession()
        setBuilderPanel(undefined)
        return
      }
      if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
        setBuilderPanel(undefined)
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

  async function openRelationLookupBuilder(tableId: string, viewId: string) {
    const canvas = readyState.canvas
    if (!canvas?.table || !canvas.view || canvas.table.id !== tableId || canvas.view.id !== viewId) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++builderRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current && builderRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === workspaceId
    setBuilderPanel({ mode: 'relation-lookup-loading', tableId, viewId })
    try {
      const { tables } = await queryClient.fetchQuery({
        queryKey: protectedQueryKey(scope, 'base', canvas.base.id, 'tables'),
        queryFn: ({ signal }) => api.baseTables(canvas.base.id, { signal }),
      })
      if (!isCurrent()) return
      const schemas = await Promise.all(tables.map((table) => queryClient.fetchQuery({
        queryKey: protectedQueryKey(scope, 'table', table.id, 'schema'),
        queryFn: ({ signal }) => api.tableSchema(table.id, { signal }),
      })))
      if (!isCurrent()) return
      const authorizedTableIds = new Set(tables.map((table) => table.id))
      const safeSchemas = schemas.filter((schema, index) => authorizedTableIds.has(schema.table.id) && schema.table.id === tables[index]?.id)
      if (!safeSchemas.some((schema) => schema.table.id === tableId)) {
        setBuilderPanel(undefined)
        return
      }
      setBuilderPanel({ mode: 'relation-lookup', tableId, viewId, tables, schemas: safeSchemas })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
        setBuilderPanel(undefined)
        return
      }
      if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
        setBuilderPanel(undefined)
        return
      }
      if (error instanceof ApiError && error.status === 404) {
        setBuilderPanel(undefined)
        setState({ status: 'error' })
        return
      }
      setBuilderPanel(undefined)
      setState({ status: 'error' })
    }
  }

  async function createRelationLookupField(
    tableId: string,
    viewId: string,
    values: F2FieldBuilderValues,
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
    const isCurrent = () => !sessionInvalidated.current && builderRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === workspaceId
    try {
      const receipt = values.kind === 'relation'
        ? await api.initializeRelationField(tableId, values, idempotencyKey)
        : await api.initializeLookupField(tableId, values, idempotencyKey)
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
        await denyInvalidSession()
        setBuilderPanel(undefined)
        return
      }
      if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
        setBuilderPanel(undefined)
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

  async function refreshBaseViews(scope: { userId: string; workspaceId: string }, baseId: string) {
    const viewsKey = protectedQueryKey(scope, 'base', baseId, 'views')
    await queryClient.cancelQueries({ queryKey: viewsKey })
    queryClient.removeQueries({ queryKey: viewsKey })
    return queryClient.fetchQuery({
      queryKey: viewsKey,
      queryFn: ({ signal }) => api.baseViews(baseId, { signal }),
    })
  }

  async function readV1Builder(scope: { userId: string; workspaceId: string }, viewId: string, version?: number) {
    return queryClient.fetchQuery({
      queryKey: viewBuilderKeys.builder(scope, viewId, version),
      queryFn: ({ signal }) => api.viewBuilder(viewId, { signal }),
    })
  }

  async function rereadV1PresentationAfterConflict(
    scope: { userId: string; workspaceId: string },
    canvas: BaseCanvasState,
    tableId: string,
    viewId: string,
    requestVersion: number,
    canvasVersion: number,
  ) {
    const isCurrent = () => !sessionInvalidated.current
      && builderRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === scope.workspaceId
    const recordsKey = protectedQueryKey(scope, 'view', viewId, 'records', null)
    await Promise.all([
      clearViewBuilderQueries(queryClient, scope, tableId, viewId),
      queryClient.cancelQueries({ queryKey: recordsKey }),
    ])
    queryClient.removeQueries({ queryKey: recordsKey })
    const [{ views }, builder, records] = await Promise.all([
      refreshBaseViews(scope, canvas.base.id),
      readV1Builder(scope, viewId),
      queryClient.fetchQuery({ queryKey: recordsKey, queryFn: ({ signal }) => api.viewRecords(viewId, undefined, { signal }) }),
    ])
    if (!isCurrent()) throw new DOMException('Obsolete view conflict reload', 'AbortError')
    const selectedView = views.find((item) => item.id === viewId && item.table_id === tableId)
    if (!selectedView) throw new Error('Updated view is unavailable')
    setState((current) => current.status === 'ready'
      && current.home.workspace_id === scope.workspaceId
      && current.canvas?.view?.id === viewId
      ? {
          ...current,
          canvas: {
            ...current.canvas,
            views,
            view: selectedView,
            presentation: canvasPresentationFromV1Builder(builder),
            serverQuerySummary: v1ServerQuerySummary(builder),
            records,
            detail: undefined,
          },
        }
      : current)
    setBuilderPanel((current) => current?.mode === 'view' && current.tableId === tableId
      ? { ...current, builder }
      : current)
  }

  async function rereadV1MembersAfterConflict(
    scope: { userId: string; workspaceId: string },
    canvas: BaseCanvasState,
    tableId: string,
    viewId: string,
    requestVersion: number,
    canvasVersion: number,
  ) {
    const isCurrent = () => !sessionInvalidated.current
      && builderRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === scope.workspaceId
    await clearViewBuilderQueries(queryClient, scope, tableId, viewId)
    const [{ views }, builder] = await Promise.all([
      refreshBaseViews(scope, canvas.base.id),
      readV1Builder(scope, viewId),
    ])
    if (!isCurrent()) throw new DOMException('Obsolete view member conflict reload', 'AbortError')
    const selectedView = views.find((item) => item.id === viewId && item.table_id === tableId)
    if (!selectedView) throw new Error('Updated view is unavailable')
    setState((current) => current.status === 'ready'
      && current.home.workspace_id === scope.workspaceId
      && current.canvas?.view?.id === viewId
      ? { ...current, canvas: { ...current.canvas, views, view: selectedView, serverQuerySummary: v1ServerQuerySummary(builder) } }
      : current)
    setBuilderPanel((current) => current?.mode === 'view' && current.tableId === tableId
      ? { ...current, builder }
      : current)
  }

  async function openViewBuilder(tableId: string, viewId?: string) {
    const canvas = readyState.canvas
    if (!canvas?.table || canvas.table.id !== tableId) return
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = ++builderRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && builderRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === workspaceId
    setBuilderPanel({ mode: 'view-loading', tableId, viewId })
    try {
      const context = await queryClient.fetchQuery({
        queryKey: viewBuilderKeys.context(scope, tableId),
        queryFn: ({ signal }) => api.viewBuilderContext(tableId, { signal }),
      })
      const builder = viewId ? await readV1Builder(scope, viewId) : undefined
      if (!isCurrent()) return
      setBuilderPanel({ mode: 'view', tableId, context, builder })
    } catch (error) {
      if (!isCurrent() || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
      } else {
        setState({ status: 'error' })
      }
      setBuilderPanel(undefined)
    }
  }

  async function createV1View(tableId: string, request: ViewInitializationRequest, idempotencyKey: string): Promise<ViewBuilderResponse> {
    const canvas = readyState.canvas
    if (!canvas?.table || canvas.table.id !== tableId) throw new Error('Table is not available')
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const requestVersion = builderRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && builderRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === workspaceId
    try {
      const receipt = await api.initializeView(tableId, request, idempotencyKey)
      if (!isCurrent()) throw new DOMException('Obsolete view initialization', 'AbortError')
      const recordsKey = protectedQueryKey(scope, 'view', receipt.view.id, 'records', null)
      await Promise.all([
        clearViewBuilderQueries(queryClient, scope, tableId, receipt.view.id),
        queryClient.cancelQueries({ queryKey: recordsKey }),
      ])
      queryClient.removeQueries({ queryKey: recordsKey })
      const [{ views }, builder, records] = await Promise.all([
        refreshBaseViews(scope, canvas.base.id),
        readV1Builder(scope, receipt.view.id),
        queryClient.fetchQuery({ queryKey: recordsKey, queryFn: ({ signal }) => api.viewRecords(receipt.view.id, undefined, { signal }) }),
      ])
      if (!isCurrent()) throw new DOMException('Obsolete view initialization', 'AbortError')
      const createdView = views.find((item) => item.id === receipt.view.id && item.table_id === tableId)
      if (!createdView) throw new Error('Created view is unavailable')
      setState((current) => current.status === 'ready'
        && current.home.workspace_id === workspaceId
        && current.canvas?.table?.id === tableId
        ? {
            ...current,
            canvas: {
              ...current.canvas,
              views,
              view: createdView,
              presentation: canvasPresentationFromV1Builder(builder),
              serverQuerySummary: v1ServerQuerySummary(builder),
              records,
              detail: undefined,
              createForm: undefined,
            },
          }
        : current)
      setBuilderPanel((current) => current?.mode === 'view' && current.tableId === tableId
        ? { ...current, builder }
        : current)
      return builder
    } catch (error) {
      if (isAbortError(error)) throw error
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) setState({ status: 'error' })
      throw error
    }
  }

  async function saveV1ViewPresentation(tableId: string, request: ViewPresentationPatchRequest): Promise<ViewBuilderResponse> {
    const canvas = readyState.canvas
    const panel = builderPanel
    if (!canvas?.table || canvas.table.id !== tableId || panel?.mode !== 'view' || !panel.builder) throw new Error('View is not available')
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const viewId = panel.builder.view.id
    const requestVersion = builderRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && builderRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === workspaceId
    try {
      const receipt = await api.patchViewPresentation(viewId, request)
      if (!isCurrent()) throw new DOMException('Obsolete view presentation', 'AbortError')
      const recordsKey = protectedQueryKey(scope, 'view', viewId, 'records', null)
      await Promise.all([
        clearViewBuilderQueries(queryClient, scope, tableId, viewId),
        queryClient.cancelQueries({ queryKey: recordsKey }),
      ])
      queryClient.removeQueries({ queryKey: recordsKey })
      const [{ views }, builder, records] = await Promise.all([
        refreshBaseViews(scope, canvas.base.id),
        readV1Builder(scope, viewId, receipt.version),
        queryClient.fetchQuery({ queryKey: recordsKey, queryFn: ({ signal }) => api.viewRecords(viewId, undefined, { signal }) }),
      ])
      if (!isCurrent()) throw new DOMException('Obsolete view presentation', 'AbortError')
      const selectedView = views.find((item) => item.id === viewId && item.table_id === tableId)
      if (!selectedView) throw new Error('Updated view is unavailable')
      setState((current) => current.status === 'ready'
        && current.home.workspace_id === workspaceId
        && current.canvas?.view?.id === viewId
        ? {
            ...current,
            canvas: {
              ...current.canvas,
              views,
              view: selectedView,
              presentation: canvasPresentationFromV1Builder(builder),
              serverQuerySummary: v1ServerQuerySummary(builder),
              records,
              detail: undefined,
            },
          }
        : current)
      setBuilderPanel((current) => current?.mode === 'view' && current.tableId === tableId
        ? { ...current, builder }
        : current)
      return builder
    } catch (error) {
      if (isAbortError(error)) throw error
      if (error instanceof ApiError && error.status === 409) {
        try {
          await rereadV1PresentationAfterConflict(scope, canvas, tableId, viewId, requestVersion, canvasVersion)
        } catch (reloadError) {
          if (isAbortError(reloadError)) throw reloadError
          if (reloadError instanceof ApiError && reloadError.status === 401) await denyInvalidSession()
          else if (reloadError instanceof ApiError && reloadError.status === 403) await denyWorkspace(scope)
          else if (reloadError instanceof ApiError && reloadError.status === 404) setState({ status: 'error' })
        }
      } else if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) setState({ status: 'error' })
      throw error
    }
  }

  async function replaceV1ViewMembers(tableId: string, request: ViewMemberReplaceRequest): Promise<void> {
    const panel = builderPanel
    const canvas = readyState.canvas
    if (!canvas?.table || canvas.table.id !== tableId || panel?.mode !== 'view' || !panel.builder) throw new Error('View is not available')
    const workspaceId = readyState.home.workspace_id
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const viewId = panel.builder.view.id
    const requestVersion = builderRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const isCurrent = () => !sessionInvalidated.current
      && builderRequestVersion.current === requestVersion
      && canvasRequestVersion.current === canvasVersion
      && activeWorkspaceId.current === workspaceId
    try {
      const receipt = await api.replaceViewMembers(viewId, request)
      if (!isCurrent()) throw new DOMException('Obsolete view members', 'AbortError')
      await clearViewBuilderQueries(queryClient, scope, tableId, viewId)
      const [{ views }, builder] = await Promise.all([
        refreshBaseViews(scope, canvas.base.id),
        readV1Builder(scope, viewId, receipt.version),
      ])
      if (!isCurrent()) throw new DOMException('Obsolete view members', 'AbortError')
      setState((current) => current.status === 'ready'
        && current.home.workspace_id === workspaceId
        && current.canvas?.view?.id === viewId
        ? { ...current, canvas: { ...current.canvas, views, serverQuerySummary: v1ServerQuerySummary(builder) } }
        : current)
      setBuilderPanel((current) => current?.mode === 'view' && current.tableId === tableId
        ? { ...current, builder }
        : current)
    } catch (error) {
      if (isAbortError(error)) throw error
      if (error instanceof ApiError && error.status === 409) {
        try {
          await rereadV1MembersAfterConflict(scope, canvas, tableId, viewId, requestVersion, canvasVersion)
        } catch (reloadError) {
          if (isAbortError(reloadError)) throw reloadError
          if (reloadError instanceof ApiError && reloadError.status === 401) await denyInvalidSession()
          else if (reloadError instanceof ApiError && reloadError.status === 403) await denyWorkspace(scope)
          else if (reloadError instanceof ApiError && reloadError.status === 404) setState({ status: 'error' })
        }
      } else if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      else if (error instanceof ApiError && error.status === 404) setState({ status: 'error' })
      throw error
    }
  }

  const selectedWorkspace = activeWorkspace
  async function openRecord(recordId: string) {
    if (!readyState.canvas) return
    abandonRecordDetail(readyState.canvas, readyState.home.workspace_id)
    const requestVersion = ++recordRequestVersion.current
    const canvasVersion = canvasRequestVersion.current
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    try {
      const detail = await queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'record', recordId), queryFn: ({ signal }) => api.recordDetail(recordId, { signal }) })
      if (sessionInvalidated.current || recordRequestVersion.current !== requestVersion || canvasRequestVersion.current !== canvasVersion) return
      setState({ ...readyState, canvas: { ...readyState.canvas, detail } })
    } catch (error) {
      if (sessionInvalidated.current || recordRequestVersion.current !== requestVersion || canvasRequestVersion.current !== canvasVersion || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
      } else {
        setState({ status: 'error' })
      }
    }
  }

  async function saveRecord(values: Record<string, unknown>) {
    const canvas = readyState.canvas
    const detail = canvas?.detail
    if (!canvas || !detail || !canvas.view) throw new Error('Record is not available')
    const workspaceId = readyState.home.workspace_id
    const canvasVersion = canvasRequestVersion.current
    const recordVersion = recordRequestVersion.current
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const isCurrent = () => !sessionInvalidated.current && canvasRequestVersion.current === canvasVersion
      && recordRequestVersion.current === recordVersion
      && activeWorkspaceId.current === workspaceId
    const recordKey = protectedQueryKey(scope, 'record', detail.id)
    const recordsKey = protectedQueryKey(scope, 'view', canvas.view.id, 'records', null)
    try {
      await api.updateRecord(detail.id, values, detail.version)
      if (!isCurrent()) throw new DOMException('Obsolete record mutation', 'AbortError')
      await Promise.all([queryClient.invalidateQueries({ queryKey: recordKey }), queryClient.invalidateQueries({ queryKey: recordsKey })])
      queryClient.removeQueries({ queryKey: recordKey })
      queryClient.removeQueries({ queryKey: recordsKey })
      const [updated, records] = await Promise.all([
        queryClient.fetchQuery({ queryKey: recordKey, queryFn: ({ signal }) => api.recordDetail(detail.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: recordsKey, queryFn: ({ signal }) => api.viewRecords(canvas.view!.id, undefined, { signal }) }),
      ])
      if (!isCurrent()) throw new DOMException('Obsolete record mutation', 'AbortError')
      const readableKeys = new Set(canvas.schema?.fields.map((field) => field.key) ?? [])
      const safeUpdated = { ...updated, values: Object.fromEntries(Object.entries(updated.values).filter(([key]) => readableKeys.has(key))) }
      setState((current) => {
        if (current.status !== 'ready' || !current.canvas
          || current.home.workspace_id !== workspaceId
          || current.canvas.view?.id !== canvas.view?.id
          || current.canvas.detail?.id !== detail.id) return current
        return { ...current, canvas: { ...current.canvas, records, detail: safeUpdated } }
      })
      return safeUpdated
    } catch (error) {
      if (isAbortError(error)) throw error
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
      } else if (error instanceof ApiError && error.status === 404) {
        await Promise.all([
          discardRecordMutationQueries(scope, detail.id, canvas.view.id),
          ...(canvas.schema?.fields ?? [])
            .filter((field) => field.field_type === 'linked_record' && Object.hasOwn(detail.values, field.key))
            .map((field) => clearRelationCandidateQueries(queryClient, scope, field.id)),
        ])
        if (isCurrent()) setState({ status: 'denied' })
      }
      throw error
    }
  }

  async function refreshRecordAfterConflict() {
    const canvas = readyState.canvas
    const detail = canvas?.detail
    if (!canvas || !detail || !canvas.view) throw new Error('Record is not available')
    const workspaceId = readyState.home.workspace_id
    const canvasVersion = canvasRequestVersion.current
    const recordVersion = recordRequestVersion.current
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId }
    const isCurrent = () => !sessionInvalidated.current && canvasRequestVersion.current === canvasVersion
      && recordRequestVersion.current === recordVersion
      && activeWorkspaceId.current === workspaceId
    const recordKey = protectedQueryKey(scope, 'record', detail.id)
    const recordsKey = protectedQueryKey(scope, 'view', canvas.view.id, 'records', null)
    try {
      if (!isCurrent()) throw new DOMException('Obsolete record mutation', 'AbortError')
      await Promise.all([queryClient.invalidateQueries({ queryKey: recordKey }), queryClient.invalidateQueries({ queryKey: recordsKey })])
      queryClient.removeQueries({ queryKey: recordKey })
      queryClient.removeQueries({ queryKey: recordsKey })
      const [updated, records] = await Promise.all([
        queryClient.fetchQuery({ queryKey: recordKey, queryFn: ({ signal }) => api.recordDetail(detail.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: recordsKey, queryFn: ({ signal }) => api.viewRecords(canvas.view!.id, undefined, { signal }) }),
      ])
      if (!isCurrent()) throw new DOMException('Obsolete record mutation', 'AbortError')
      const readableKeys = new Set(canvas.schema?.fields.map((field) => field.key) ?? [])
      const safeUpdated = { ...updated, values: Object.fromEntries(Object.entries(updated.values).filter(([key]) => readableKeys.has(key))) }
      setState((current) => {
        if (current.status !== 'ready' || !current.canvas
          || current.home.workspace_id !== workspaceId
          || current.canvas.view?.id !== canvas.view?.id
          || current.canvas.detail?.id !== detail.id) return current
        return { ...current, canvas: { ...current.canvas, detail: safeUpdated, records } }
      })
      return safeUpdated
    } catch (error) {
      if (isAbortError(error)) throw error
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await denyWorkspace(scope)
      } else if (error instanceof ApiError && error.status === 404) {
        await discardRecordMutationQueries(scope, detail.id, canvas.view.id)
        if (isCurrent()) setState({ status: 'denied' })
      }
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
        await denyInvalidSession()
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
        await denyInvalidSession()
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
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await clearProtectedWorkspace(queryClient, scope)
        setState({ status: 'denied' })
      }
      throw error
    }
  }

  async function loadRelationCandidates(fieldId: string, query: string, cursor: string | null) {
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    try {
      return await queryClient.fetchQuery({
        queryKey: relationCandidateQueryKey(scope, fieldId, query, cursor),
        queryFn: ({ signal }) => api.relationCandidates(fieldId, query, cursor ?? undefined, { signal }),
      })
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) await denyInvalidSession()
      else if (error instanceof ApiError && error.status === 403) await denyWorkspace(scope)
      throw error
    }
  }

  async function closeCreateRecord() {
    const form = readyState.canvas?.createForm
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    await Promise.all((form?.fields ?? [])
      .filter((field) => field.field_type === 'linked_record')
      .map((field) => clearRelationCandidateQueries(queryClient, scope, field.id)))
    setState((current) => current.status === 'ready' && current.canvas
      ? { ...current, canvas: { ...current.canvas, createForm: undefined } }
      : current)
  }

  async function selectTable(tableId: string) {
    const canvas = readyState.canvas
    if (!canvas || canvas.table?.id === tableId) return
    const table = canvas.tables.find((item) => item.id === tableId)
    if (!table) return
    const view = canvas.views.find((item) => item.table_id === table.id) ?? null
    abandonRecordDetail(canvas, readyState.home.workspace_id)
    builderRequestVersion.current += 1
    setBuilderPanel(undefined)
    const requestVersion = ++canvasRequestVersion.current
    createFormRequestVersion.current += 1
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    if (!view) {
      setState({ ...readyState, canvas: { ...canvas, table, view: null, schema: null, presentation: null, records: null, detail: undefined, createForm: undefined } })
      return
    }
    setState({ ...readyState, canvasLoading: true, canvas: undefined })
    try {
      const [schema, presentation, records, builder] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'table', table.id, 'schema'), queryFn: ({ signal }) => api.tableSchema(table.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'presentation'), queryFn: ({ signal }) => api.viewPresentation(view.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'records', null), queryFn: ({ signal }) => api.viewRecords(view.id, undefined, { signal }) }),
        readV1BuilderForCanvas(scope, view),
      ])
      if (canvasRequestVersion.current !== requestVersion) return
      setState({ ...readyState, canvas: { ...canvas, table, view, schema, presentation: builder ? canvasPresentationFromV1Builder(builder) : presentation, records, serverQuerySummary: builder ? v1ServerQuerySummary(builder) : undefined, detail: undefined, createForm: undefined } })
    } catch (error) {
      if (canvasRequestVersion.current !== requestVersion || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
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
    abandonRecordDetail(canvas, readyState.home.workspace_id)
    builderRequestVersion.current += 1
    setBuilderPanel(undefined)
    const requestVersion = ++canvasRequestVersion.current
    createFormRequestVersion.current += 1
    const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id }
    setState({ ...readyState, canvasLoading: true, canvas: undefined })
    try {
      const schema = canvas.table?.id === table.id && canvas.schema
        ? canvas.schema
        : await queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'table', table.id, 'schema'), queryFn: ({ signal }) => api.tableSchema(table.id, { signal }) })
      const [presentation, records, builder] = await Promise.all([
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'presentation'), queryFn: ({ signal }) => api.viewPresentation(view.id, { signal }) }),
        queryClient.fetchQuery({ queryKey: protectedQueryKey(scope, 'view', view.id, 'records', null), queryFn: ({ signal }) => api.viewRecords(view.id, undefined, { signal }) }),
        readV1BuilderForCanvas(scope, view),
      ])
      if (canvasRequestVersion.current !== requestVersion) return
      setState({ ...readyState, canvas: { ...canvas, table, view, schema, presentation: builder ? canvasPresentationFromV1Builder(builder) : presentation, records, serverQuerySummary: builder ? v1ServerQuerySummary(builder) : undefined, detail: undefined } })
    } catch (error) {
      if (canvasRequestVersion.current !== requestVersion || isAbortError(error)) return
      if (error instanceof ApiError && error.status === 401) {
        await denyInvalidSession()
      } else if (error instanceof ApiError && error.status === 403) {
        await clearProtectedWorkspace(queryClient, scope)
        setState({ status: 'denied' })
      } else {
        setState({ status: 'error' })
      }
    }
  }

  const telegramRecoveryNotice = telegramRecovery
    ? <section className="telegram-deep-link-recovery" aria-live="polite">
      <p>链接不可用，已返回工作区首页。</p>
      <button ref={telegramRecoveryButton} type="button" onClick={() => setTelegramRecovery(false)}>返回工作区首页</button>
    </section>
    : null
  const content = readyState.canvasLoading
    ? <main className="app-state" aria-label="正在加载 Base">正在加载 Base…</main>
    : readyState.canvas
    ? <><BaseCanvas {...readyState.canvas} canManageSchema={selectedWorkspace.capabilities.can_manage_schema} canCreateViews={selectedWorkspace.capabilities.can_manage_schema} canManageViews={selectedWorkspace.capabilities.can_manage_schema && Boolean(readyState.canvas.view?.scope)} canCreateRecords={['owner', 'admin', 'builder', 'operator'].includes(selectedWorkspace.role)} canManageDigitalEmployees={selectedWorkspace.capabilities.can_manage_digital_employees === true} onBack={() => { builderRequestVersion.current += 1; createFormRequestVersion.current += 1; closeDigitalEmployeeManagement(); abandonRecordDetail(readyState.canvas, readyState.home.workspace_id); setBuilderPanel(undefined); setState({ ...readyState, canvas: undefined }) }} onOpenRecord={openRecord} onSelectTable={selectTable} onSelectView={selectView} onLoadMore={loadMoreRecords} onCreateRecord={readyState.canvas.schema?.fields.length ? openCreateRecord : undefined} onCreateTable={() => { builderRequestVersion.current += 1; setBuilderPanel({ mode: 'table', base: readyState.canvas!.base }) }} onCreateField={() => { const canvas = readyState.canvas; if (!canvas?.table || !canvas.view) return; builderRequestVersion.current += 1; setBuilderPanel({ mode: 'field', tableId: canvas.table.id, viewId: canvas.view.id }) }} onCreateView={() => { const canvas = readyState.canvas; if (!canvas?.table) return; rememberViewBuilderTrigger(); void openViewBuilder(canvas.table.id) }} onConfigureView={() => { const canvas = readyState.canvas; if (!canvas?.table || !canvas.view) return; rememberViewBuilderTrigger(); void openViewBuilder(canvas.table.id, canvas.view.id) }} onSaveTemplate={() => setTemplateImportPanel({ mode: 'save-template', base: readyState.canvas!.base })} onImportIntoBase={(trigger) => openBaseImport(readyState.canvas!.base, trigger)} onOpenDraftHub={(trigger) => { void openDraftEmployeeHub(trigger) }} onOpenDigitalEmployeeManagement={(trigger) => { void openDigitalEmployeeManagement(trigger) }} />{readyState.canvas.detail && <RecordDetailPanel detail={readyState.canvas.detail} schema={readyState.canvas.schema} onSave={saveRecord} loadRelationCandidates={loadRelationCandidates} onConflict={refreshRecordAfterConflict} onClose={() => { abandonRecordDetail(readyState.canvas, readyState.home.workspace_id); setState({ ...readyState, canvas: { ...readyState.canvas!, detail: undefined } }) }} />}{readyState.canvas.createForm && <CreateRecordPanel form={readyState.canvas.createForm} onCreate={createRecord} onClose={() => { void closeCreateRecord() }} loadRelationCandidates={loadRelationCandidates} />}</>
      : navigationRoute === 'bases'
        ? <BaseDirectory state={baseDirectory.state} bases={baseDirectory.bases} onOpenBase={(base) => { void openBase(base) }} onHome={() => selectNavigation('home')} onRetry={() => { void loadBaseDirectory() }} />
        : <>{telegramRecoveryNotice}<WorkspaceHomeView home={readyState.home} workspace={selectedWorkspace} onOpenBase={openBase} onCreateBase={() => { builderRequestVersion.current += 1; setBuilderPanel({ mode: 'base' }) }} onOpenTemplateImport={() => { void openTemplateImportHub() }} onOpenDraftHub={(trigger, draftId) => { void openDraftEmployeeHub(trigger, draftId) }} onOpenAssistantContext={(trigger) => { void openAssistantContext(trigger) }} onOpenTeamBot={(trigger) => { void openTeamBot(trigger) }} /></>
  const builderOverlay = builderPanel?.mode === 'base'
    ? <BuilderCreatePanel mode="base" onSubmit={(values, idempotencyKey) => createBase(values as { baseName: string; tableName: string }, idempotencyKey)} onClose={() => { builderRequestVersion.current += 1; setBuilderPanel(undefined) }} />
    : builderPanel?.mode === 'table'
      ? <BuilderCreatePanel mode="table" onSubmit={(values, idempotencyKey) => createTable(builderPanel.base, values as { tableName: string }, idempotencyKey)} onClose={() => { builderRequestVersion.current += 1; setBuilderPanel(undefined) }} />
      : builderPanel?.mode === 'field'
        ? <FieldBuilderPanel onSubmit={(values, idempotencyKey) => createField(builderPanel.tableId, builderPanel.viewId, values, idempotencyKey)} onOpenRelationLookup={() => { void openRelationLookupBuilder(builderPanel.tableId, builderPanel.viewId) }} onClose={() => { builderRequestVersion.current += 1; setBuilderPanel(undefined) }} />
        : builderPanel?.mode === 'relation-lookup-loading'
          ? <div className="field-builder-backdrop" role="presentation"><aside className="field-builder-panel" aria-label="正在加载关系字段" aria-modal="true" role="dialog"><header className="field-builder-header"><div className="field-builder-heading"><div><p>关系字段</p><h2>正在加载关系字段</h2></div></div><button className="field-builder-close" type="button" aria-label="关闭" onClick={() => { builderRequestVersion.current += 1; setBuilderPanel(undefined) }}>×</button></header><p className="field-builder-intro">正在加载当前 Base 的授权表结构。</p></aside></div>
          : builderPanel?.mode === 'relation-lookup'
            ? <RelationLookupFieldBuilderPanel currentTableId={builderPanel.tableId} tables={builderPanel.tables} schemas={builderPanel.schemas} onSubmit={(values, idempotencyKey) => createRelationLookupField(builderPanel.tableId, builderPanel.viewId, values, idempotencyKey)} onClose={() => { builderRequestVersion.current += 1; setBuilderPanel(undefined) }} />
            : builderPanel?.mode === 'view-loading'
              ? <div className="view-builder-backdrop" role="presentation"><aside className="view-builder-panel" aria-label="正在加载视图配置" aria-modal="true" role="dialog"><header className="view-builder-header"><div className="view-builder-heading"><div><p>VIEW BUILDER</p><h2>正在加载视图配置</h2></div></div><button className="field-builder-close" type="button" aria-label="关闭视图配置" onClick={closeViewBuilder}>×</button></header><p className="field-builder-intro">正在读取当前权限范围内的安全视图配置。</p></aside></div>
              : builderPanel?.mode === 'view'
                ? <ViewBuilderPanel context={builderPanel.context} builder={builderPanel.builder} onCreate={(request, idempotencyKey) => createV1View(builderPanel.tableId, request, idempotencyKey)} onSave={(request) => saveV1ViewPresentation(builderPanel.tableId, request)} onReplaceMembers={(request) => replaceV1ViewMembers(builderPanel.tableId, request)} onClose={closeViewBuilder} loadRelationCandidates={loadRelationCandidates} />
                : null
  const templateImportOverlay = templateImportPanel?.mode === 'hub'
    ? <TemplateImportHub templates={templateImportPanel.templates} loading={templateImportPanel.loading} error={templateImportPanel.error} onRetry={() => { void openTemplateImportHub() }} onInstall={installTemplate} onInstallError={() => setTemplateImportPanel((current) => current?.mode === 'hub' ? { ...current, loading: false, error: '安装模板失败，请稍后重试。' } : current)} onStartWorkspaceImport={openWorkspaceImport} onClose={closeTemplateImport} />
    : templateImportPanel?.mode === 'save-template'
      ? <SaveTemplatePanel base={templateImportPanel.base} onSave={(values) => saveBaseAsTemplate(templateImportPanel.base, values)} onClose={closeTemplateImport} />
      : templateImportPanel?.mode === 'workspace-import'
        ? <ImportWizard target={{ kind: 'workspace', workspaceId: readyState.home.workspace_id }} onCreatePreview={(values) => createImportPreview({ kind: 'workspace', workspaceId: readyState.home.workspace_id }, values)} onCommit={(jobId, values) => commitImport({ kind: 'workspace', workspaceId: readyState.home.workspace_id }, jobId, values)} onClose={closeTemplateImport} />
        : templateImportPanel?.mode === 'base-import'
          ? <ImportWizard target={{ kind: 'base', workspaceId: readyState.home.workspace_id, baseId: templateImportPanel.base.id, baseName: templateImportPanel.base.name }} onCreatePreview={(values) => createImportPreview({ kind: 'base', workspaceId: readyState.home.workspace_id, baseId: templateImportPanel.base.id, baseName: templateImportPanel.base.name }, values)} onCommit={(jobId, values) => commitImport({ kind: 'base', workspaceId: readyState.home.workspace_id, baseId: templateImportPanel.base.id, baseName: templateImportPanel.base.name }, jobId, values)} onClose={closeTemplateImport} />
      : null
  const draftEmployeeOverlay = draftEmployeePanel
    ? <DraftEmployeeHub
      contacts={draftEmployeePanel.contacts}
      context={currentS5InvocationContext()}
      draft={draftEmployeePanel.draft}
      loading={draftEmployeePanel.loading}
      failed={draftEmployeePanel.failed}
      onRetry={() => {
        const trigger = draftEmployeeReturnFocus.current ?? document.body
        void openDraftEmployeeHub(trigger, draftEmployeePanel.targetDraftId ?? undefined)
      }}
      onConfirm={(draftId, expectedVersion) => terminalS5Draft('confirm', draftId, expectedVersion)}
      onReject={(draftId, expectedVersion) => terminalS5Draft('reject', draftId, expectedVersion)}
      onInvoke={invokeS5Employee}
      onClose={closeDraftEmployeeHub}
    />
    : null
  const assistantContextOverlay = assistantContextPanel
    ? <AssistantContextWorkbench
      contacts={assistantContextPanel.contacts}
      context={assistantContextPanel.context}
      selectedView={assistantContextPanel.selectedView}
      summary={assistantContextPanel.summary}
      loading={assistantContextPanel.loading}
      failed={assistantContextPanel.failed}
      onSelectContact={(employeeId) => { void selectAssistantContextEmployee(employeeId) }}
      onSelectView={(viewId) => { void selectAssistantContextView(viewId) }}
      onSummarize={summarizeAssistantContext}
      onOpenBase={() => { void openAssistantContextBase() }}
      onRetry={() => { void openAssistantContext() }}
      onClose={closeAssistantContext}
    />
    : null
  const teamBotOverlay = teamBotPanel
    ? <TeamBotWorkbench
      contacts={teamBotPanel.contacts}
      context={teamBotPanel.context}
      selectedView={teamBotPanel.selectedView}
      summary={teamBotPanel.summary}
      loading={teamBotPanel.loading}
      failed={teamBotPanel.failed}
      onSelectContact={(employeeId) => { void selectTeamBotEmployee(employeeId) }}
      onSelectView={(viewId) => { void selectTeamBotView(viewId) }}
      onSummarize={summarizeTeamBot}
      onOpenBase={() => { void openTeamBotBase() }}
      onRetry={() => { void openTeamBot() }}
      onClose={closeTeamBot}
    />
    : null
  const digitalEmployeeManagementOverlay = digitalEmployeeManagementPanel
    ? <DigitalEmployeeManagementWorkbench
      context={digitalEmployeeManagementPanel.context}
      directory={digitalEmployeeManagementPanel.directory}
      detail={digitalEmployeeManagementPanel.detail}
      loading={digitalEmployeeManagementPanel.loading}
      failed={digitalEmployeeManagementPanel.failed}
      onSelectEmployee={(employeeId) => { void selectDigitalEmployeeManagementEmployee(employeeId) }}
      onCreate={createManagedDigitalEmployee}
      onUpdate={updateManagedDigitalEmployee}
      onReplaceGrants={replaceManagedDigitalEmployeeGrants}
      onActivate={activateManagedDigitalEmployee}
      onPause={pauseManagedDigitalEmployee}
      onReload={() => refreshDigitalEmployeeManagement(
        digitalEmployeeManagementPanel.baseId,
        digitalEmployeeManagementPanel.selectedEmployeeId,
      )}
      onClose={closeDigitalEmployeeManagement}
    />
    : null
  const governanceOverlay = governancePanel
    ? <GovernanceWorkbench
      bases={readyState.home.recent_bases}
      members={governancePanel.members}
      audit={governancePanel.audit}
      selectedBaseId={governancePanel.selectedBaseId}
      membersLoading={governancePanel.membersLoading}
      auditLoading={governancePanel.auditLoading}
      membersError={governancePanel.membersError}
      auditError={governancePanel.auditError}
      membersLoadMoreError={governancePanel.membersLoadMoreError}
      auditLoadMoreError={governancePanel.auditLoadMoreError}
      onSelectBase={(baseId) => { void selectGovernanceBase(baseId) }}
      onLoadMoreMembers={() => { void loadMoreGovernanceMembers() }}
      onLoadMoreAudit={() => { void loadMoreGovernanceAudit() }}
      onRetryMembers={() => { void openGovernance() }}
      onRetryAudit={() => {
        if (governancePanel.selectedBaseId) void selectGovernanceBase(governancePanel.selectedBaseId)
      }}
      onOpenWrite={(trigger) => { void openGovernanceWrite(trigger) }}
      onClose={closeGovernance}
    />
    : null
  const governanceWriteOverlay = governanceWritePanel
    ? <GovernanceWriteWorkbench
      bases={readyState.home.recent_bases}
      tables={governanceWritePanel.tables}
      views={governanceWritePanel.views}
      members={governanceWritePanel.members}
      fields={governanceWritePanel.fields}
      selectedBaseId={governanceWritePanel.selectedBaseId}
      selectedTableId={governanceWritePanel.selectedTableId}
      membersLoading={governanceWritePanel.membersLoading}
      tablesLoading={governanceWritePanel.tablesLoading}
      fieldsLoading={governanceWritePanel.fieldsLoading}
      contextError={governanceWritePanel.contextError}
      onSelectBase={(baseId) => { void selectGovernanceWriteBase(baseId) }}
      onSelectTable={(tableId) => { void selectGovernanceWriteTable(tableId) }}
      onChangeRole={changeGovernanceWriteRole}
      onReplacePolicy={replaceGovernanceWriteFieldPolicy}
      onReloadMembers={() => refreshGovernanceWriteMemberContext({ userId: readyState.bootstrap.identity.user_id, workspaceId: readyState.home.workspace_id })}
      onReloadFields={reloadGovernanceWriteFieldContext}
      onOpenViewAccess={(viewId) => { void openGovernanceV1ViewAccess(viewId) }}
      onClose={closeGovernanceWrite}
    />
    : null
  return <AppShell workspace={selectedWorkspace} workspaces={readyState.bootstrap.workspaces} onWorkspaceChange={selectWorkspace} activeRoute={navigationRoute} onNavigate={selectNavigation} onOpenGovernance={(trigger) => { void openGovernance(trigger) }}>{content}{builderOverlay}{templateImportOverlay}{draftEmployeeOverlay}{assistantContextOverlay}{teamBotOverlay}{digitalEmployeeManagementOverlay}{governanceOverlay}{governanceWriteOverlay}</AppShell>
}
