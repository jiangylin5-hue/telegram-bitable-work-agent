import { QueryClient } from '@tanstack/react-query'
import { expect, test } from 'vitest'

import { clearGovernanceQueries, governanceKeys } from '../app/protectedQuery'

test('governance query keys remain isolated by verified workspace and Base', () => {
  const scope = { userId: 'user-1', workspaceId: 'workspace-1' }
  const otherScope = { userId: 'user-1', workspaceId: 'workspace-2' }
  expect(governanceKeys.audit(scope, 'base-1', null)).not.toEqual(
    governanceKeys.audit(otherScope, 'base-1', null),
  )
  expect(governanceKeys.audit(scope, 'base-1', null)).not.toEqual(
    governanceKeys.audit(scope, 'base-2', null),
  )
})

test('removes only one Base audit subtree when the selected Base is missing', async () => {
  const queryClient = new QueryClient()
  const scope = { userId: 'user-1', workspaceId: 'workspace-1' }
  queryClient.setQueryData(governanceKeys.members(scope, null), { members: [] })
  queryClient.setQueryData(governanceKeys.audit(scope, 'base-1', null), { events: [] })
  queryClient.setQueryData(governanceKeys.audit(scope, 'base-2', null), { events: [] })

  await clearGovernanceQueries(queryClient, scope, 'base-1')

  expect(queryClient.getQueryData(governanceKeys.members(scope, null))).toEqual({ members: [] })
  expect(queryClient.getQueryData(governanceKeys.audit(scope, 'base-1', null))).toBeUndefined()
  expect(queryClient.getQueryData(governanceKeys.audit(scope, 'base-2', null))).toEqual({ events: [] })
})
