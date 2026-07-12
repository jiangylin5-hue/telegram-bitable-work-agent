import { QueryClient } from '@tanstack/react-query'
import { expect, test } from 'vitest'

import {
  clearDigitalEmployeeManagementQueries,
  digitalEmployeeManagementKeys,
} from '../app/protectedQuery'

test('management keys isolate employee data across workspaces', () => {
  const first = { userId: 'user-1', workspaceId: 'workspace-1' }
  const second = { userId: 'user-1', workspaceId: 'workspace-2' }

  expect(digitalEmployeeManagementKeys.context(first, 'base-1')).not.toEqual(
    digitalEmployeeManagementKeys.context(second, 'base-1'),
  )
  expect(digitalEmployeeManagementKeys.detail(first, 'employee-1')).not.toEqual(
    digitalEmployeeManagementKeys.detail(first, 'employee-2'),
  )
})

test('management cleanup removes only its selected workspace subtree', async () => {
  const queryClient = new QueryClient()
  const first = { userId: 'user-1', workspaceId: 'workspace-1' }
  const second = { userId: 'user-1', workspaceId: 'workspace-2' }
  queryClient.setQueryData(digitalEmployeeManagementKeys.context(first, 'base-1'), { base: 'first' })
  queryClient.setQueryData(digitalEmployeeManagementKeys.detail(first, 'employee-1'), { employee: 'first' })
  queryClient.setQueryData(digitalEmployeeManagementKeys.context(second, 'base-1'), { base: 'second' })
  queryClient.setQueryData(digitalEmployeeManagementKeys.detail(second, 'employee-1'), { employee: 'second' })

  await clearDigitalEmployeeManagementQueries(queryClient, first)

  expect(queryClient.getQueryData(digitalEmployeeManagementKeys.context(first, 'base-1'))).toBeUndefined()
  expect(queryClient.getQueryData(digitalEmployeeManagementKeys.detail(first, 'employee-1'))).toBeUndefined()
  expect(queryClient.getQueryData(digitalEmployeeManagementKeys.context(second, 'base-1'))).toEqual({ base: 'second' })
  expect(queryClient.getQueryData(digitalEmployeeManagementKeys.detail(second, 'employee-1'))).toEqual({ employee: 'second' })
})
