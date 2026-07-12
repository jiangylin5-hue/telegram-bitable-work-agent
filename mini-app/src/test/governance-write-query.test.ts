import { QueryClient } from '@tanstack/react-query'
import { expect, test } from 'vitest'

import { clearGovernanceWriteQueries, governanceWriteKeys } from '../app/protectedQuery'

test('governance write keys isolate workspace and table policy state', () => {
  const scope = { userId: 'user-1', workspaceId: 'workspace-1' }
  const other = { userId: 'user-1', workspaceId: 'workspace-2' }
  expect(governanceWriteKeys.members(scope, null)).not.toEqual(governanceWriteKeys.members(other, null))
  expect(governanceWriteKeys.fieldPermissions(scope, 'table-1')).not.toEqual(governanceWriteKeys.fieldPermissions(scope, 'table-2'))
})

test('clears only the selected table write subtree and leaves member context intact', async () => {
  const queryClient = new QueryClient()
  const scope = { userId: 'user-1', workspaceId: 'workspace-1' }
  queryClient.setQueryData(governanceWriteKeys.members(scope, null), { members: [] })
  queryClient.setQueryData(governanceWriteKeys.fieldPermissions(scope, 'table-1'), { fields: [] })
  queryClient.setQueryData(governanceWriteKeys.fieldPermissions(scope, 'table-2'), { fields: [] })

  await clearGovernanceWriteQueries(queryClient, scope, 'table-1')

  expect(queryClient.getQueryData(governanceWriteKeys.members(scope, null))).toEqual({ members: [] })
  expect(queryClient.getQueryData(governanceWriteKeys.fieldPermissions(scope, 'table-1'))).toBeUndefined()
  expect(queryClient.getQueryData(governanceWriteKeys.fieldPermissions(scope, 'table-2'))).toEqual({ fields: [] })
})
