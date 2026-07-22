import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('starts a workspace import from the authorized template hub', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/templates') return Promise.resolve(json({ templates: [] }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '模板与导入' }))
  fireEvent.click(await screen.findByRole('button', { name: '导入到新 Base' }))

  expect(await screen.findByRole('heading', { name: '导入数据表' })).toBeVisible()
})

test('returns focus to the exact Base action that opened an in-Base import', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    const responses: Record<string, unknown> = {
      '/mini-app/bootstrap': {
        identity: { user_id: 'owner-1', source: 'header' },
        workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }],
      },
      '/workspaces/workspace-1/home': { workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }], queue: [] },
      '/bases/base-1/tables': { tables: [{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }] },
      '/bases/base-1/views': { views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }] },
      '/tables/table-1/schema': { table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] },
      '/views/view-1/presentation': { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] },
      '/views/view-1/records': { view_id: 'view-1', records: [], next_cursor: null, has_more: false },
      '/views/view-1/builder': { detail: 'unavailable' },
    }
    return Promise.resolve(path in responses ? json(responses[path]) : json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  const moreActions = await screen.findByRole('button', { name: '更多 Base 操作' })
  fireEvent.click(moreActions)
  fireEvent.click(screen.getByRole('button', { name: '导入到当前 Base' }))
  expect(await screen.findByRole('heading', { name: '导入数据表' })).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: '关闭导入' }))
  await waitFor(() => expect(moreActions).toHaveFocus())
})
