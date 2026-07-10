import { expect, test, vi } from 'vitest'

import { clearAllProtectedQueries, clearProtectedWorkspace, createProtectedQueryClient, protectedQueryKey } from '../app/protectedQuery'

test('keys protected data by verified user and workspace before resource segments', () => {
  expect(protectedQueryKey({ userId: 'user-1', workspaceId: 'workspace-1' }, 'record', 'record-1')).toEqual(['stage07', 'user-1', 'workspace-1', 'record', 'record-1'])
})

test('removes and cancels only the requested protected workspace scope', async () => {
  const client = createProtectedQueryClient()
  const target = { userId: 'user-1', workspaceId: 'workspace-1' }
  const anotherWorkspace = { userId: 'user-1', workspaceId: 'workspace-2' }
  const cancelQueries = vi.spyOn(client, 'cancelQueries')
  const targetKey = protectedQueryKey(target, 'view', 'view-1', 'records', null)
  const otherKey = protectedQueryKey(anotherWorkspace, 'view', 'view-2', 'records', null)
  client.setQueryData(targetKey, { records: ['Ada'] })
  client.setQueryData(otherKey, { records: ['Northstar'] })

  await clearProtectedWorkspace(client, target)

  expect(cancelQueries).toHaveBeenCalledWith({ queryKey: ['stage07', 'user-1', 'workspace-1'] })
  expect(client.getQueryData(targetKey)).toBeUndefined()
  expect(client.getQueryData(otherKey)).toEqual({ records: ['Northstar'] })
})

test('uses security-first query defaults without durable inactive protected data', () => {
  const client = createProtectedQueryClient()
  expect(client.getDefaultOptions().queries).toMatchObject({ staleTime: 0, gcTime: 0, retry: false })
})

test('removes every Stage07 query after identity expiry', async () => {
  const client = createProtectedQueryClient()
  const firstKey = protectedQueryKey({ userId: 'user-1', workspaceId: 'workspace-1' }, 'home')
  const secondKey = protectedQueryKey({ userId: 'user-2', workspaceId: 'workspace-2' }, 'home')
  client.setQueryData(firstKey, { queue: [] })
  client.setQueryData(secondKey, { queue: [] })

  await clearAllProtectedQueries(client)

  expect(client.getQueryData(firstKey)).toBeUndefined()
  expect(client.getQueryData(secondKey)).toBeUndefined()
})
