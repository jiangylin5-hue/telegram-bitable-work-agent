import { afterEach, expect, test, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import { App } from '../app/App'
import { setTelegramInitData } from '../app/api'

type TelegramWindow = Window & {
  Telegram?: { WebApp?: { initData?: string; initDataUnsafe?: { start_param?: unknown } } }
}

afterEach(() => {
  delete (window as TelegramWindow).Telegram
  setTelegramInitData(null)
  vi.unstubAllGlobals()
})

test('Telegram recovery resolves once and returns to a focusable Workspace Home without target details', async () => {
  ;(window as TelegramWindow).Telegram = {
    WebApp: { initData: 'raw-signed-init-data', initDataUnsafe: { start_param: 'opaqueToken_123456' } },
  }
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.pathname : new URL(input.url).pathname
    if (path === '/mini-app/bootstrap') return Promise.resolve(new Response(JSON.stringify({
      identity: { user_id: 'member-1', source: 'telegram_binding' },
      workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/mini-app/telegram/deep-links/resolve') return Promise.resolve(new Response(JSON.stringify({ outcome: 'recovery' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    return Promise.reject(new Error(`Unexpected request: ${path} ${init?.method ?? 'GET'}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  const recovery = await screen.findByRole('button', { name: '返回工作区首页' })
  expect(recovery).toHaveFocus()
  expect(screen.queryByText('opaqueToken_123456')).not.toBeInTheDocument()
  await waitFor(() => expect(fetchMock.mock.calls.filter(([input]) => String(input) === '/mini-app/telegram/deep-links/resolve')).toHaveLength(1))
  const [, resolveInit] = fetchMock.mock.calls.find(([input]) => String(input) === '/mini-app/telegram/deep-links/resolve') as [string, RequestInit]
  expect(new Headers(resolveInit.headers).get('X-Telegram-Init-Data')).toBe('raw-signed-init-data')
})

test('a resolved record pointer re-reads Base, View and Record before showing the target', async () => {
  ;(window as TelegramWindow).Telegram = {
    WebApp: { initData: 'raw-signed-init-data', initDataUnsafe: { start_param: 'opaqueToken_123456' } },
  }
  const paths: string[] = []
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.pathname : new URL(input.url).pathname
    paths.push(path)
    const response = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/mini-app/bootstrap') return response({ identity: { user_id: 'member-1', source: 'telegram_binding' }, workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } }] })
    if (path === '/mini-app/telegram/deep-links/resolve') return response({ outcome: 'resolved', destination: { kind: 'record', workspace_id: 'workspace-1', base_id: 'base-1', table_id: 'table-1', record_id: 'record-1' } })
    if (path === '/workspaces/workspace-1/home') return response({ workspace_id: 'workspace-1', recent_bases: [], queue: [] })
    if (path === '/workspaces/workspace-1/bases') return response({ bases: [{ id: 'base-1', name: '安全 Base', source_type: 'blank', status: 'active' }] })
    if (path === '/bases/base-1/tables') return response({ tables: [{ id: 'table-1', base_id: 'base-1', name: 'Tasks', key: 'tasks', status: 'active' }] })
    if (path === '/bases/base-1/views') return response({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }] })
    if (path === '/tables/table-1/schema') return response({ table: { id: 'table-1', name: 'Tasks', key: 'tasks' }, fields: [{ id: 'field-1', table_id: 'table-1', name: 'Title', key: 'title', field_type: 'text', required: false, options: {}, order_index: 0 }] })
    if (path === '/views/view-1/presentation') return response({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['title'], group_by_field_key: null, date_field_key: null, form_field_keys: ['title'] })
    if (path === '/views/view-1/records') return response({ view_id: 'view-1', records: [{ id: 'record-1', fields: { title: 'authoritative value' } }], next_cursor: null, has_more: false })
    if (path === '/records/record-1') return response({ id: 'record-1', table_id: 'table-1', values: { title: 'authoritative value' }, record_status: 'active', version: 1 })
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  await waitFor(() => expect(paths).toEqual(expect.arrayContaining([
    '/mini-app/telegram/deep-links/resolve',
    '/workspaces/workspace-1/bases',
    '/bases/base-1/tables',
    '/bases/base-1/views',
    '/tables/table-1/schema',
    '/views/view-1/presentation',
    '/views/view-1/records',
    '/records/record-1',
  ])))
  expect(screen.queryByText('opaqueToken_123456')).not.toBeInTheDocument()
})

test.each([401, 403])('a %i during resolved target reread remains denied instead of recovering to Home', async (status) => {
  ;(window as TelegramWindow).Telegram = {
    WebApp: { initData: 'raw-signed-init-data', initDataUnsafe: { start_param: 'opaqueToken_123456' } },
  }
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.pathname : new URL(input.url).pathname
    const response = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/mini-app/bootstrap') return response({ identity: { user_id: 'member-1', source: 'telegram_binding' }, workspaces: [{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } }] })
    if (path === '/mini-app/telegram/deep-links/resolve') return response({ outcome: 'resolved', destination: { kind: 'record', workspace_id: 'workspace-1', base_id: 'base-1', table_id: 'table-1', record_id: 'record-1' } })
    if (path === '/workspaces/workspace-1/home') return response({ workspace_id: 'workspace-1', recent_bases: [], queue: [] })
    if (path === '/workspaces/workspace-1/bases') return response({ bases: [{ id: 'base-1', name: 'Secure Base', source_type: 'blank', status: 'active' }] })
    if (path === '/bases/base-1/tables') return response({ tables: [{ id: 'table-1', base_id: 'base-1', name: 'Tasks', key: 'tasks', status: 'active' }] })
    if (path === '/bases/base-1/views') return response({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }] })
    if (path === '/tables/table-1/schema') return response({ table: { id: 'table-1', name: 'Tasks', key: 'tasks' }, fields: [] })
    if (path === '/views/view-1/presentation') return response({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] })
    if (path === '/views/view-1/records') return response({ view_id: 'view-1', records: [], next_cursor: null, has_more: false })
    if (path === '/records/record-1') return response({ error: { code: 'target_access_denied' } }, status)
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  await waitFor(() => expect(document.querySelector('.app-state')).toHaveAttribute('aria-label', '无工作区访问权限'))
  expect(screen.queryByRole('button', { name: '返回工作区首页' })).not.toBeInTheDocument()
  expect(screen.queryByText('opaqueToken_123456')).not.toBeInTheDocument()
})
