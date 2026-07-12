import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

const draftDetail = {
  id: 'employee-1', name: '客户助手', description: '安全汇总客户', status: 'draft', access_mode: 'assigned',
  table_count: 0, view_count: 0, member_count: 0, version: 1, base_id: 'base-1', telegram_alias: null,
  accessible_table_ids: [], accessible_view_ids: [], allowed_actions: ['summarize'], member_ids: [],
}

const draftSummary = {
  id: draftDetail.id, name: draftDetail.name, description: draftDetail.description, status: draftDetail.status,
  access_mode: draftDetail.access_mode, table_count: draftDetail.table_count, view_count: draftDetail.view_count,
  member_count: draftDetail.member_count, version: draftDetail.version,
}

afterEach(() => vi.unstubAllGlobals())

test('opens the Base management panel and creates only through TD010 endpoints with authoritative rereads', async () => {
  let created = false
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'header' },
      workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_manage_digital_employees: true, can_review_drafts: true } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }], queue: [] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [{ id: 'table-1', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: '客户', key: 'customers' }, fields: [] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }))
    if (path === '/views/view-1/records') return Promise.resolve(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/bases/base-1/digital-employee-management-context') return Promise.resolve(json({
      base: { id: 'base-1', name: 'CRM' }, tables: [{ id: 'table-1', name: '客户' }], views: [{ id: 'view-1', table_id: 'table-1', name: '全部客户', view_type: 'grid' }], members: [{ id: 'member-1', label: '成员 1', role: 'operator' }],
    }))
    if (path === '/mini-app/bases/base-1/digital-employees/management?limit=50') return Promise.resolve(json({ base_id: 'base-1', employees: created ? [draftSummary] : [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/bases/base-1/digital-employees/management' && init?.method === 'POST') {
      created = true
      return Promise.resolve(json(draftDetail))
    }
    if (path === '/mini-app/digital-employees/employee-1/management') return Promise.resolve(json(draftDetail))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  const entry = await screen.findByRole('button', { name: '数字员工管理' })
  fireEvent.click(entry)
  expect(await screen.findByRole('dialog', { name: '数字员工管理' })).toBeVisible()

  fireEvent.change(screen.getByLabelText('员工名称'), { target: { value: '客户助手' } })
  fireEvent.change(screen.getByLabelText('员工说明'), { target: { value: '安全汇总客户' } })
  fireEvent.click(screen.getByRole('button', { name: '创建草稿员工' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/bases/base-1/digital-employees/management',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ name: '客户助手', description: '安全汇总客户', telegram_alias: null }) }),
  ))
  await waitFor(() => expect(screen.getByLabelText('员工名称')).toHaveValue('客户助手'))
  expect(fetchMock.mock.calls.map(([input]) => String(input)).some((path) => path.includes('/invocations'))).toBe(false)
})
