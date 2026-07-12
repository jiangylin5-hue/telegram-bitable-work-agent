import { QueryClient } from '@tanstack/react-query'
import { expect, test } from 'vitest'

import { clearDraftEmployeeTerminalQueries, draftEmployeeKeys, protectedQueryKey } from '../app/protectedQuery'

test('keeps S5 contact and draft keys inside the verified user and workspace scope', () => {
  const first = { userId: 'user-1', workspaceId: 'workspace-1' }
  const second = { userId: 'user-2', workspaceId: 'workspace-1' }

  expect(draftEmployeeKeys.contacts(first, null)).toEqual(['stage07', 'user-1', 'workspace-1', 's5', 'contacts', null])
  expect(draftEmployeeKeys.draft(first, 'draft-1')).not.toEqual(draftEmployeeKeys.draft(second, 'draft-1'))
})

test('removes the terminal draft, its S5 state, home queue and record cache without affecting another workspace', async () => {
  const client = new QueryClient()
  const scope = { userId: 'user-1', workspaceId: 'workspace-1' }
  const another = { userId: 'user-1', workspaceId: 'workspace-2' }
  client.setQueryData(draftEmployeeKeys.contacts(scope, null), { contacts: [] })
  client.setQueryData(draftEmployeeKeys.draft(scope, 'draft-1'), { id: 'draft-1' })
  client.setQueryData(protectedQueryKey(scope, 'home'), { queue: ['draft-1'] })
  client.setQueryData(protectedQueryKey(scope, 'record', 'record-1'), { id: 'record-1' })
  client.setQueryData(draftEmployeeKeys.draft(another, 'draft-1'), { id: 'draft-1' })

  await clearDraftEmployeeTerminalQueries(client, scope, { id: 'draft-1', recordId: 'record-1' })

  expect(client.getQueryData(draftEmployeeKeys.contacts(scope, null))).toBeUndefined()
  expect(client.getQueryData(draftEmployeeKeys.draft(scope, 'draft-1'))).toBeUndefined()
  expect(client.getQueryData(protectedQueryKey(scope, 'home'))).toBeUndefined()
  expect(client.getQueryData(protectedQueryKey(scope, 'record', 'record-1'))).toBeUndefined()
  expect(client.getQueryData(draftEmployeeKeys.draft(another, 'draft-1'))).toEqual({ id: 'draft-1' })
})
