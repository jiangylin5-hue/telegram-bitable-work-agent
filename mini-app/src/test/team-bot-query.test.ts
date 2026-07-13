import { QueryClient } from '@tanstack/react-query'
import { expect, test } from 'vitest'

import { clearTeamBotQueries, teamBotKeys } from '../app/protectedQuery'

test('team bot keys are isolated from the personal assistant and other workspaces', () => {
  const first = { userId: 'user-1', workspaceId: 'workspace-1' }
  const second = { userId: 'user-1', workspaceId: 'workspace-2' }

  expect(teamBotKeys.contacts(first, null)).toEqual(['stage07', 'user-1', 'workspace-1', 'team-bot', 'contacts', null])
  expect(teamBotKeys.contexts(first, 'employee-1', null)).not.toEqual(
    teamBotKeys.contexts(second, 'employee-1', null),
  )
})

test('team bot cleanup removes only the selected workspace subtree', async () => {
  const client = new QueryClient()
  const first = { userId: 'user-1', workspaceId: 'workspace-1' }
  const second = { userId: 'user-1', workspaceId: 'workspace-2' }
  client.setQueryData(teamBotKeys.contacts(first, null), { contacts: ['first'] })
  client.setQueryData(teamBotKeys.selectedView(first, 'employee-1', 'view-1'), { id: 'view-1' })
  client.setQueryData(teamBotKeys.contacts(second, null), { contacts: ['second'] })

  await clearTeamBotQueries(client, first)

  expect(client.getQueryData(teamBotKeys.contacts(first, null))).toBeUndefined()
  expect(client.getQueryData(teamBotKeys.selectedView(first, 'employee-1', 'view-1'))).toBeUndefined()
  expect(client.getQueryData(teamBotKeys.contacts(second, null))).toEqual({ contacts: ['second'] })
})

