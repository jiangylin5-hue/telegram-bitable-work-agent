import { expect, test, vi } from 'vitest'

import { clearAllProtectedQueries, clearProtectedWorkspace, clearRecordMutationQueries, clearRelationCandidateQueries, createProtectedQueryClient, protectedQueryKey, relationCandidateQueryKey } from '../app/protectedQuery'

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

test('removes only the current record and initial view window after a record-level 404', async () => {
  const client = createProtectedQueryClient()
  const scope = { userId: 'user-1', workspaceId: 'workspace-1' }
  const currentRecord = protectedQueryKey(scope, 'record', 'record-1')
  const anotherRecord = protectedQueryKey(scope, 'record', 'record-2')
  const currentWindow = protectedQueryKey(scope, 'view', 'view-1', 'records', null)
  const nextWindow = protectedQueryKey(scope, 'view', 'view-1', 'records', 'cursor-2')
  const anotherView = protectedQueryKey(scope, 'view', 'view-2', 'records', null)
  client.setQueryData(currentRecord, { values: { name: 'Ada' } })
  client.setQueryData(anotherRecord, { values: { name: 'Grace' } })
  client.setQueryData(currentWindow, { records: ['Ada'] })
  client.setQueryData(nextWindow, { records: ['Celia'] })
  client.setQueryData(anotherView, { records: ['Northstar'] })

  await clearRecordMutationQueries(client, scope, 'record-1', 'view-1')

  expect(client.getQueryData(currentRecord)).toBeUndefined()
  expect(client.getQueryData(currentWindow)).toBeUndefined()
  expect(client.getQueryData(anotherRecord)).toEqual({ values: { name: 'Grace' } })
  expect(client.getQueryData(nextWindow)).toEqual({ records: ['Celia'] })
  expect(client.getQueryData(anotherView)).toEqual({ records: ['Northstar'] })
})

test('keys and clears only relation candidate pages for the active verified scope', async () => {
  const client = createProtectedQueryClient()
  const scope = { userId: 'user-1', workspaceId: 'workspace-1' }
  const candidate = relationCandidateQueryKey(scope, 'field-1', 'ac', null)
  const anotherField = relationCandidateQueryKey(scope, 'field-2', 'ac', null)
  const anotherScope = relationCandidateQueryKey({ userId: 'user-1', workspaceId: 'workspace-2' }, 'field-1', 'ac', null)
  client.setQueryData(candidate, { records: ['Acme'] })
  client.setQueryData(anotherField, { records: ['Bravo'] })
  client.setQueryData(anotherScope, { records: ['Northstar'] })

  await clearRelationCandidateQueries(client, scope, 'field-1')

  expect(candidate).toEqual(['stage07', 'user-1', 'workspace-1', 'relation-candidates', 'field-1', 'ac', null])
  expect(client.getQueryData(candidate)).toBeUndefined()
  expect(client.getQueryData(anotherField)).toEqual({ records: ['Bravo'] })
  expect(client.getQueryData(anotherScope)).toEqual({ records: ['Northstar'] })
})
