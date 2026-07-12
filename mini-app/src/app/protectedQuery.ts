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
    ...(importJobId ? [templateImportKeys.importJob(scope, importJobId)] : []),
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
