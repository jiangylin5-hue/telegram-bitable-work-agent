import { QueryClient } from '@tanstack/react-query'
import { expect, test } from 'vitest'

import { clearTemplateImportQueries, templateImportKeys } from '../app/protectedQuery'

test('template import keys stay scoped to the verified user and workspace', () => {
  expect(templateImportKeys.importJob({ userId: 'user-1', workspaceId: 'workspace-1' }, 'import-1')).not.toEqual(
    templateImportKeys.importJob({ userId: 'user-1', workspaceId: 'workspace-2' }, 'import-1'),
  )
})

test('clears only the selected template import cache entries', async () => {
  const queryClient = new QueryClient()
  const scope = { userId: 'user-1', workspaceId: 'workspace-1' }
  const retainedScope = { userId: 'user-1', workspaceId: 'workspace-2' }
  queryClient.setQueryData(templateImportKeys.templates(scope), [{ id: 'template-1' }])
  queryClient.setQueryData(templateImportKeys.importJob(scope, 'import-1'), { id: 'import-1' })
  queryClient.setQueryData(templateImportKeys.importJob(scope, 'import-2'), { id: 'import-2' })
  queryClient.setQueryData(templateImportKeys.importJob(retainedScope, 'import-1'), { id: 'import-1' })

  await clearTemplateImportQueries(queryClient, scope, 'import-1')

  expect(queryClient.getQueryData(templateImportKeys.templates(scope))).toBeUndefined()
  expect(queryClient.getQueryData(templateImportKeys.importJob(scope, 'import-1'))).toBeUndefined()
  expect(queryClient.getQueryData(templateImportKeys.importJob(scope, 'import-2'))).toEqual({ id: 'import-2' })
  expect(queryClient.getQueryData(templateImportKeys.importJob(retainedScope, 'import-1'))).toEqual({ id: 'import-1' })
})
