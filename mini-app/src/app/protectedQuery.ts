import { QueryClient, type QueryKey } from '@tanstack/react-query'

export type ProtectedScope = { userId: string; workspaceId: string }

export function protectedWorkspaceKey(scope: ProtectedScope): QueryKey {
  return ['stage07', scope.userId, scope.workspaceId]
}

export function protectedQueryKey(scope: ProtectedScope, ...segments: (string | null)[]): QueryKey {
  return [...protectedWorkspaceKey(scope), ...segments]
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
