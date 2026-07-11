import { QueryClient, type QueryKey } from '@tanstack/react-query'

export type ProtectedScope = { userId: string; workspaceId: string }

export function protectedWorkspaceKey(scope: ProtectedScope): QueryKey {
  return ['stage07', scope.userId, scope.workspaceId]
}

export function protectedQueryKey(scope: ProtectedScope, ...segments: (string | null)[]): QueryKey {
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
