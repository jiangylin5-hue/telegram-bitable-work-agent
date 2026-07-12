import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('opens the safe template shelf from an authorized workspace entry', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'header' },
      workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/templates') return Promise.resolve(json({ templates: [{ id: 'template-1', name: 'CRM', category: 'crm', description: 'Safe summary', version: '1.0.0', status: 'published', manifest: { hidden: true } }] }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  fireEvent.click(await screen.findByRole('button', { name: '模板与导入' }))
  expect(await screen.findByRole('heading', { name: 'CRM' })).toBeVisible()
  expect(screen.queryByText('hidden')).not.toBeInTheDocument()
})

test('closes the template shelf after the receipt Base is reread and opened', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/templates') return Promise.resolve(json({ templates: [{ id: 'template-1', name: 'CRM', category: 'crm', description: 'Safe summary', version: '1.0.0', status: 'published' }] }))
    if (path === '/workspaces/workspace-1/template-installations' && init?.method === 'POST') return Promise.resolve(json({ id: 'installation-1', workspace_id: 'workspace-1', base_id: 'base-1', template_id: 'template-1', template_version: '1.0.0' }))
    if (path === '/workspaces/workspace-1/bases') return Promise.resolve(json({ bases: [{ id: 'base-1', name: 'CRM', source_type: 'template', status: 'active' }] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }))
    if (path === '/views/view-1/records') return Promise.resolve(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
    if (path === '/views/view-1/builder') return Promise.resolve(json({ detail: 'unavailable' }, 404))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '模板与导入' }))
  fireEvent.click(await screen.findByRole('button', { name: '安装模板 CRM' }))

  const canvas = await screen.findByRole('main', { name: 'Base 工作台' })
  expect(within(canvas).getByRole('heading', { name: 'CRM' })).toBeVisible()
  expect(screen.queryByRole('dialog', { name: '模板与导入' })).not.toBeInTheDocument()
})
