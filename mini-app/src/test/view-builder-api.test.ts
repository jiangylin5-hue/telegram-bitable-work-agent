import { afterEach, expect, test, vi } from 'vitest'

import { api, toSafeViewError } from '../app/api'
import { viewBuilderKeys } from '../app/protectedQuery'
import type { ViewInitializationRequest } from '../app/view-builder-types'

afterEach(() => {
  vi.unstubAllGlobals()
})

const command: ViewInitializationRequest = {
  name: '我的视图',
  view_type: 'grid',
  presentation: {
    view_type: 'grid',
    visible_field_keys: ['title'],
    filters: [],
    sort_rules: [],
    group_by_field_key: null,
  },
}

test('initializes a private view with the only Idempotency-Key and strips unknown response fields', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
    view: {
      id: 'view-1', base_id: 'base-1', table_id: 'table/1', name: '我的视图', view_type: 'grid',
      scope: 'private', caller_access_level: 'owner', status: 'active', is_default: false,
      owner_user_id: 'must-not-reach-browser',
    },
    affected_view_ids: ['view-1'],
    config: { secret: true },
  }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchMock)

  const receipt = await api.initializeView('table/1', command, 'view-idempotency-1')

  expect(fetchMock).toHaveBeenCalledWith(
    '/tables/table%2F1/view-initializations',
    expect.objectContaining({ method: 'POST', body: JSON.stringify(command) }),
  )
  const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
  const headers = new Headers(request.headers)
  expect(headers.get('Idempotency-Key')).toBe('view-idempotency-1')
  expect(receipt).toEqual({
    view: {
      id: 'view-1', base_id: 'base-1', table_id: 'table/1', name: '我的视图', view_type: 'grid',
      scope: 'private', caller_access_level: 'owner', status: 'active', is_default: false,
    },
    affected_view_ids: ['view-1'],
  })
})

test('patches typed presentation without an Idempotency-Key', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
    view: {
      id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '重命名', view_type: 'grid',
      scope: 'private', caller_access_level: 'owner', status: 'active', is_default: false,
    },
    version: 2,
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchMock)

  await api.patchViewPresentation('view/1', { expected_version: 1, presentation: command.presentation })

  expect(fetchMock).toHaveBeenCalledWith(
    '/views/view%2F1/presentation',
    expect.objectContaining({ method: 'PATCH' }),
  )
  const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(new Headers(request.headers).get('Idempotency-Key')).toBeNull()
})

test('uses fixed allowlisted V1 errors and scoped protected query keys', () => {
  expect(toSafeViewError({ code: 'view_version_conflict', message: 'secret backend detail' }))
    .toBe('视图已被更新，请重新加载后再试。')
  expect(toSafeViewError({ code: 'unknown', message: 'secret backend detail' }))
    .toBe('视图请求失败，请稍后重试。')
  expect(viewBuilderKeys.context({ userId: 'user-1', workspaceId: 'workspace-1' }, 'table-1'))
    .toEqual(['stage07', 'user-1', 'workspace-1', 'view-builder-context', 'table-1'])
  expect(viewBuilderKeys.builder({ userId: 'user-1', workspaceId: 'workspace-1' }, 'view-1', 2))
    .toEqual(['stage07', 'user-1', 'workspace-1', 'view-builder', 'view-1', 2])
})
