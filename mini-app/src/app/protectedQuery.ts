import { QueryClient, type QueryKey } from '@tanstack/react-query'

export type ProtectedScope = { userId: string; workspaceId: string }

export function protectedWorkspaceKey(scope: ProtectedScope): QueryKey {
  return ['stage07', scope.userId, scope.workspaceId]
}

export function protectedQueryKey(scope: ProtectedScope, ...segments: (string | number | null)[]): QueryKey {
  return [...protectedWorkspaceKey(scope), ...segments]
}

export function relationCandidateQueryKey(
  scope: ProtectedScope,
  fieldId: string,
  query: string,
  cursor: string | null,
): QueryKey {
  return protectedQueryKey(scope, 'relation-candidates', fieldId, query, cursor)
}

export const navigationKeys = {
  bases: (scope: ProtectedScope): QueryKey => protectedQueryKey(scope, 'navigation', 'bases'),
}

export const viewBuilderKeys = {
  context: (scope: ProtectedScope, tableId: string): QueryKey => (
    protectedQueryKey(scope, 'view-builder-context', tableId)
  ),
  builder: (scope: ProtectedScope, viewId: string, version?: number): QueryKey => (
    protectedQueryKey(scope, 'view-builder', viewId, version ?? null)
  ),
}

export const templateImportKeys = {
  templates: (scope: ProtectedScope): QueryKey => protectedQueryKey(scope, 'templates'),
  importJob: (scope: ProtectedScope, importJobId: string): QueryKey => protectedQueryKey(scope, 'import', importJobId),
}

export const governanceKeys = {
  members: (scope: ProtectedScope, cursor: string | null): QueryKey => (
    protectedQueryKey(scope, 'governance', 'members', cursor)
  ),
  audit: (scope: ProtectedScope, baseId: string, cursor: string | null): QueryKey => (
    protectedQueryKey(scope, 'governance', 'audit', baseId, cursor)
  ),
}

export const governanceWriteKeys = {
  members: (scope: ProtectedScope, cursor: string | null): QueryKey => (
    protectedQueryKey(scope, 'governance-write', 'members', cursor)
  ),
  fieldPermissions: (scope: ProtectedScope, tableId: string): QueryKey => (
    protectedQueryKey(scope, 'governance-write', 'field-policy', tableId)
  ),
}

export const digitalEmployeeManagementKeys = {
  context: (scope: ProtectedScope, baseId: string): QueryKey => (
    protectedQueryKey(scope, 'digital-employee-management', 'base', baseId, 'context')
  ),
  directory: (scope: ProtectedScope, baseId: string, cursor: string | null): QueryKey => (
    protectedQueryKey(scope, 'digital-employee-management', 'base', baseId, 'directory', cursor)
  ),
  detail: (scope: ProtectedScope, employeeId: string): QueryKey => (
    protectedQueryKey(scope, 'digital-employee-management', 'employee', employeeId)
  ),
}

export async function clearDigitalEmployeeManagementQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  target?: { baseId?: string; employeeId?: string },
): Promise<void> {
  const queryKeys: QueryKey[] = [
    ...(target?.baseId ? [protectedQueryKey(scope, 'digital-employee-management', 'base', target.baseId)] : []),
    ...(target?.employeeId ? [protectedQueryKey(scope, 'digital-employee-management', 'employee', target.employeeId)] : []),
  ]
  if (queryKeys.length === 0) queryKeys.push(protectedQueryKey(scope, 'digital-employee-management'))
  await Promise.all(queryKeys.map((queryKey) => queryClient.cancelQueries({ queryKey })))
  for (const queryKey of queryKeys) queryClient.removeQueries({ queryKey })
}

export const draftEmployeeKeys = {
  contacts: (scope: ProtectedScope, cursor: string | null): QueryKey => (
    protectedQueryKey(scope, 's5', 'contacts', cursor)
  ),
  draft: (scope: ProtectedScope, draftId: string): QueryKey => (
    protectedQueryKey(scope, 's5', 'draft', draftId)
  ),
  assistantContext: (scope: ProtectedScope, employeeId: string, cursor: string | null): QueryKey => (
    protectedQueryKey(scope, 'assistant-context', employeeId, cursor)
  ),
  assistantView: (scope: ProtectedScope, employeeId: string, viewId: string): QueryKey => (
    protectedQueryKey(scope, 'assistant-context', employeeId, 'view', viewId)
  ),
}

export async function clearAssistantContextQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  employeeId?: string,
): Promise<void> {
  const queryKey = employeeId
    ? protectedQueryKey(scope, 'assistant-context', employeeId)
    : protectedQueryKey(scope, 'assistant-context')
  await queryClient.cancelQueries({ queryKey })
  queryClient.removeQueries({ queryKey })
}

export const teamBotKeys = {
  contacts: (scope: ProtectedScope, cursor: string | null): QueryKey => (
    protectedQueryKey(scope, 'team-bot', 'contacts', cursor)
  ),
  contexts: (scope: ProtectedScope, employeeId: string, cursor: string | null): QueryKey => (
    protectedQueryKey(scope, 'team-bot', 'employee', employeeId, 'contexts', cursor)
  ),
  selectedView: (scope: ProtectedScope, employeeId: string, viewId: string): QueryKey => (
    protectedQueryKey(scope, 'team-bot', 'employee', employeeId, 'view', viewId)
  ),
}

export async function clearTeamBotQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  employeeId?: string,
): Promise<void> {
  const queryKey = employeeId
    ? protectedQueryKey(scope, 'team-bot', 'employee', employeeId)
    : protectedQueryKey(scope, 'team-bot')
  await queryClient.cancelQueries({ queryKey })
  queryClient.removeQueries({ queryKey })
}

export const telegramDeepLinkKeys = {
  resolver: (scope: ProtectedScope): QueryKey => protectedQueryKey(scope, 's6', 'telegram-deep-link'),
}

export async function clearTelegramDeepLinkQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  destination?: { recordId?: string; draftId?: string },
): Promise<void> {
  const queryKeys: QueryKey[] = [
    telegramDeepLinkKeys.resolver(scope),
    ...(destination?.recordId ? [protectedQueryKey(scope, 'record', destination.recordId)] : []),
    ...(destination?.draftId ? [draftEmployeeKeys.draft(scope, destination.draftId)] : []),
  ]
  await Promise.all(queryKeys.map((queryKey) => queryClient.cancelQueries({ queryKey })))
  for (const queryKey of queryKeys) queryClient.removeQueries({ queryKey })
}

export async function clearDraftEmployeeTerminalQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  target: { id: string; recordId: string | null },
): Promise<void> {
  const queryKeys: QueryKey[] = [
    protectedQueryKey(scope, 's5'),
    protectedQueryKey(scope, 'home'),
    ...(target.recordId ? [protectedQueryKey(scope, 'record', target.recordId)] : []),
  ]
  await Promise.all(queryKeys.map((queryKey) => queryClient.cancelQueries({ queryKey })))
  for (const queryKey of queryKeys) queryClient.removeQueries({ queryKey })
}

export async function clearGovernanceWriteQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  tableId?: string,
): Promise<void> {
  const queryKey = tableId
    ? protectedQueryKey(scope, 'governance-write', 'field-policy', tableId)
    : protectedQueryKey(scope, 'governance-write')
  await queryClient.cancelQueries({ queryKey })
  queryClient.removeQueries({ queryKey })
}

export async function clearGovernanceQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  baseId?: string,
): Promise<void> {
  const queryKey = baseId
    ? protectedQueryKey(scope, 'governance', 'audit', baseId)
    : protectedQueryKey(scope, 'governance')
  await queryClient.cancelQueries({ queryKey })
  queryClient.removeQueries({ queryKey })
}

export async function clearTemplateImportQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  importJobId?: string,
): Promise<void> {
  const queryKeys: QueryKey[] = [
    templateImportKeys.templates(scope),
    ...(importJobId
      ? [templateImportKeys.importJob(scope, importJobId)]
      : [protectedQueryKey(scope, 'import')]),
  ]
  await Promise.all(queryKeys.map((queryKey) => queryClient.cancelQueries({ queryKey })))
  for (const queryKey of queryKeys) queryClient.removeQueries({ queryKey })
}

export async function clearViewBuilderQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  tableId: string,
  viewId?: string,
): Promise<void> {
  const queryKeys: QueryKey[] = [
    viewBuilderKeys.context(scope, tableId),
    ...(viewId ? [protectedQueryKey(scope, 'view-builder', viewId)] : []),
  ]
  await Promise.all(queryKeys.map((queryKey) => queryClient.cancelQueries({ queryKey })))
  for (const queryKey of queryKeys) queryClient.removeQueries({ queryKey })
}

export function createProtectedQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 0,
        gcTime: 0,
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  })
}

export async function clearProtectedWorkspace(queryClient: QueryClient, scope: ProtectedScope): Promise<void> {
  const queryKey = protectedWorkspaceKey(scope)
  await queryClient.cancelQueries({ queryKey })
  queryClient.removeQueries({ queryKey })
}

export async function clearAllProtectedQueries(queryClient: QueryClient): Promise<void> {
  const queryKey: QueryKey = ['stage07']
  await queryClient.cancelQueries({ queryKey })
  queryClient.removeQueries({ queryKey })
}

export async function clearFieldMutationQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  tableId: string,
  viewIds: string[],
): Promise<void> {
  const queryKeys: QueryKey[] = [
    protectedQueryKey(scope, 'table', tableId, 'schema'),
    protectedQueryKey(scope, 'table', tableId, 'create-form'),
    protectedQueryKey(scope, 'record'),
    ...viewIds.flatMap((viewId) => [
      protectedQueryKey(scope, 'view', viewId, 'presentation'),
      protectedQueryKey(scope, 'view', viewId, 'records'),
    ]),
  ]
  await Promise.all(queryKeys.map((queryKey) => queryClient.cancelQueries({ queryKey })))
  for (const queryKey of queryKeys) queryClient.removeQueries({ queryKey })
}

export async function clearRecordMutationQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  recordId: string,
  viewId: string,
): Promise<void> {
  const queryKeys: QueryKey[] = [
    protectedQueryKey(scope, 'record', recordId),
    protectedQueryKey(scope, 'view', viewId, 'records', null),
  ]
  await Promise.all(queryKeys.map((queryKey) => queryClient.cancelQueries({ queryKey })))
  for (const queryKey of queryKeys) queryClient.removeQueries({ queryKey })
}

export async function clearRelationCandidateQueries(
  queryClient: QueryClient,
  scope: ProtectedScope,
  fieldId: string,
): Promise<void> {
  const queryKey = protectedQueryKey(scope, 'relation-candidates', fieldId)
  await queryClient.cancelQueries({ queryKey })
  queryClient.removeQueries({ queryKey })
}
