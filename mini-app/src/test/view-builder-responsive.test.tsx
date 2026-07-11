import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const capabilities = { can_read_bases: true, can_manage_workspace: false, can_manage_schema: true, can_review_drafts: false }
const bootstrap = { identity: { user_id: 'owner-1', source: 'development_header' }, workspaces: [{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'owner', capabilities }] }
const home = { workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }], queue: [] }
const table = { id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }
const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Private filters', view_type: 'grid', status: 'active', scope: 'private', caller_access_level: 'owner', is_default: false }
const presentation = { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['title'], group_by_field_key: null, date_field_key: null, form_field_keys: [] }
const context = { table, fields: [{ field_id: 'field-title', key: 'title', label: 'Title', field_type: 'text', filter_operators: ['equals'], filter_values: [], sortable: true, groupable: false, form_eligible: true }], views: [], member_candidates: [] }
const builder = { view, presentation: { ...presentation, filters: [], sort_rules: [] }, fields: context.fields, members: [], version: 1, can_edit_presentation: true, can_replace_members: true }

afterEach(() => {
  vi.unstubAllGlobals()
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 })
})

test('keeps V1 controls reachable at 390px and returns focus to the triggering Canvas control on close', async () => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
  window.dispatchEvent(new Event('resize'))
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [view] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-title', table_id: 'table-1', name: 'Title', key: 'title', field_type: 'text', required: false, options: {}, order_index: 0 }] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json(presentation))
    if (path === '/views/view-1/records') return Promise.resolve(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
    if (path === '/tables/table-1/view-builder-context') return Promise.resolve(json(context))
    if (path === '/views/view-1/builder') return Promise.resolve(json(builder))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  const trigger = await screen.findByRole('button', { name: '配置视图' })
  trigger.focus()
  fireEvent.click(trigger)

  expect(await screen.findByRole('button', { name: '保存视图' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: '关闭视图配置' }))

  await waitFor(() => expect(document.activeElement).toBe(trigger))
})
