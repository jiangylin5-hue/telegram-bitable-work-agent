import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const capability = { can_read_bases: true, can_manage_workspace: false, can_manage_schema: true, can_review_drafts: false }
const bootstrap = { identity: { user_id: 'owner-1', source: 'development_header' }, workspaces: [{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'owner', capabilities: capability }] }
const home = { workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }], queue: [] }
const table = { id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }
const view = (name = 'Private filters') => ({ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name, view_type: 'grid', status: 'active', scope: 'private', caller_access_level: 'owner', is_default: false })
const presentation = { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['title', 'state'], group_by_field_key: 'state', date_field_key: null, form_field_keys: [] }
const builderContext = { table: { id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }, fields: [{ field_id: 'field-title', key: 'title', label: 'Title', field_type: 'text', filter_operators: ['equals'], filter_values: [], sortable: true, groupable: false, form_eligible: true }, { field_id: 'field-state', key: 'state', label: 'State', field_type: 'status', filter_operators: ['is'], filter_values: ['open', 'closed'], sortable: true, groupable: true, form_eligible: true }], views: [], member_candidates: [{ id: 'member-1', label: 'Member One' }] }
const builder = (name = 'Private filters', version = 1) => ({ view: { ...view(name), scope: 'private', caller_access_level: 'owner', is_default: false }, presentation: { ...presentation, filters: [{ field_key: 'state', operator: 'is', value: 'open' }], sort_rules: [{ field_key: 'title', direction: 'asc' }] }, fields: builderContext.fields, members: [], version, can_edit_presentation: true, can_replace_members: true })

afterEach(() => {
  vi.unstubAllGlobals()
})

test('authoritatively rereads builder, view list and records after a versioned presentation save', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let baseViewReads = 0
  let builderReads = 0
  let recordReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') {
      baseViewReads += 1
      return Promise.resolve(json({ views: [view(baseViewReads > 1 ? 'Renamed server view' : 'Private filters')] }))
    }
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-title', table_id: 'table-1', name: 'Title', key: 'title', field_type: 'text', required: false, options: {}, order_index: 0 }, { id: 'field-state', table_id: 'table-1', name: 'State', key: 'state', field_type: 'status', required: false, options: { choices: ['open', 'closed'] }, order_index: 1 }] }))
    if (path === '/views/view-1/presentation' && init?.method === 'PATCH') return Promise.resolve(json({ view: { ...view('Renamed server view'), scope: 'private', caller_access_level: 'owner', is_default: false }, version: 2 }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json(presentation))
    if (path === '/views/view-1/records') {
      recordReads += 1
      return Promise.resolve(json({ view_id: 'view-1', records: [{ id: 'record-1', fields: { title: recordReads > 1 ? 'Server reread row' : 'Initial row', state: 'open' } }], next_cursor: null, has_more: false }))
    }
    if (path === '/tables/table-1/view-builder-context') return Promise.resolve(json(builderContext))
    if (path === '/views/view-1/builder') {
      builderReads += 1
      return Promise.resolve(json(builder(builderReads > 1 ? 'Renamed server view' : 'Private filters', builderReads > 1 ? 2 : 1)))
    }
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  expect(await screen.findByLabelText('服务器查询摘要')).toHaveTextContent('服务端已应用 1 条筛选、1 条排序、按 State 分组')
  fireEvent.click(await screen.findByRole('button', { name: '配置视图' }))
  fireEvent.change(await screen.findByLabelText('视图名称'), { target: { value: 'Renamed server view' } })
  fireEvent.click(screen.getByRole('button', { name: '保存视图' }))

  await waitFor(() => expect(screen.getByRole('tab', { name: 'Renamed server view' })).toHaveAttribute('aria-selected', 'true'))
  expect(await screen.findByRole('cell', { name: 'Server reread row' })).toBeInTheDocument()
  expect(builderReads).toBeGreaterThanOrEqual(2)
  expect(baseViewReads).toBeGreaterThanOrEqual(2)
  expect(recordReads).toBeGreaterThanOrEqual(2)
})

test('creates a private view only after its safe receipt is present in the refreshed server list', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('crypto', { randomUUID: () => 'view-create-1' })
  let baseViewReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') {
      baseViewReads += 1
      return Promise.resolve(json({ views: baseViewReads === 1 ? [view('All customers')] : [view('All customers'), { id: 'view-2', base_id: 'base-1', table_id: 'table-1', name: 'My private view', view_type: 'grid', status: 'active', scope: 'private', caller_access_level: 'owner', is_default: false }] }))
    }
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-title', table_id: 'table-1', name: 'Title', key: 'title', field_type: 'text', required: false, options: {}, order_index: 0 }, { id: 'field-state', table_id: 'table-1', name: 'State', key: 'state', field_type: 'status', required: false, options: { choices: ['open', 'closed'] }, order_index: 1 }] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json(presentation))
    if (path === '/views/view-1/records') return Promise.resolve(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
    if (path === '/tables/table-1/view-builder-context') return Promise.resolve(json(builderContext))
    if (path === '/tables/table-1/view-initializations') {
      expect(init?.method).toBe('POST')
      expect(new Headers(init?.headers).get('Idempotency-Key')).toBe('view-create-1')
      return Promise.resolve(json({ view: { id: 'view-2', base_id: 'base-1', table_id: 'table-1', name: 'My private view', view_type: 'grid', scope: 'private', caller_access_level: 'owner', status: 'active', is_default: false }, affected_view_ids: ['view-2'] }, 201))
    }
    if (path === '/views/view-2/builder') return Promise.resolve(json({ ...builder('My private view', 1), view: { ...builder('My private view', 1).view, id: 'view-2' }, presentation: { ...builder('My private view', 1).presentation, view_id: 'view-2' } }))
    if (path === '/views/view-2/records') return Promise.resolve(json({ view_id: 'view-2', records: [{ id: 'record-2', fields: { title: 'New view row', state: 'open' } }], next_cursor: null, has_more: false }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  fireEvent.click(await screen.findByRole('button', { name: '新建视图' }))
  fireEvent.change(await screen.findByLabelText('视图名称'), { target: { value: 'My private view' } })
  fireEvent.click(screen.getByRole('button', { name: '创建私有视图' }))

  expect(await screen.findByRole('heading', { name: '访问权限' })).toBeVisible()
  expect(screen.getByRole('tab', { name: 'My private view' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('cell', { name: 'New view row' })).toBeInTheDocument()
  expect(baseViewReads).toBeGreaterThanOrEqual(2)
})

test('replaces members through a fresh list and Builder reread without refetching an unchanged record window', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let baseViewReads = 0
  let builderReads = 0
  let recordReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') {
      baseViewReads += 1
      return Promise.resolve(json({ views: [{ ...view(), scope: baseViewReads > 1 ? 'restricted' : 'private' }] }))
    }
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-title', table_id: 'table-1', name: 'Title', key: 'title', field_type: 'text', required: false, options: {}, order_index: 0 }, { id: 'field-state', table_id: 'table-1', name: 'State', key: 'state', field_type: 'status', required: false, options: { choices: ['open', 'closed'] }, order_index: 1 }] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json(presentation))
    if (path === '/views/view-1/records') {
      recordReads += 1
      return Promise.resolve(json({ view_id: 'view-1', records: [{ id: 'record-1', fields: { title: 'Initial row', state: 'open' } }], next_cursor: null, has_more: false }))
    }
    if (path === '/tables/table-1/view-builder-context') return Promise.resolve(json(builderContext))
    if (path === '/views/view-1/builder') {
      builderReads += 1
      return Promise.resolve(json({
        ...builder('Private filters', builderReads > 2 ? 2 : 1),
        view: { ...builder('Private filters', builderReads > 2 ? 2 : 1).view, scope: builderReads > 2 ? 'restricted' : 'private' },
        members: builderReads > 2 ? [{ user_id: 'member-1', label: 'Member One', access_level: 'viewer' }] : [],
      }))
    }
    if (path === '/views/view-1/members') {
      expect(init?.method).toBe('PUT')
      expect(JSON.parse(String(init?.body))).toEqual({ expected_version: 1, members: [{ user_id: 'member-1', access_level: 'viewer' }] })
      return Promise.resolve(json({ view: { ...view(), scope: 'restricted' }, members: [{ user_id: 'member-1', label: 'Member One', access_level: 'viewer' }], version: 2 }))
    }
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  fireEvent.click(await screen.findByRole('button', { name: '配置视图' }))
  fireEvent.click(await screen.findByRole('button', { name: '管理访问权限' }))
  fireEvent.change(await screen.findByLabelText('Member One 权限'), { target: { value: 'viewer' } })
  fireEvent.click(screen.getByRole('button', { name: '保存成员权限' }))

  await waitFor(() => expect(builderReads).toBeGreaterThanOrEqual(3))
  expect(baseViewReads).toBeGreaterThanOrEqual(2)
  expect(screen.getByLabelText('Member One 权限')).toHaveValue('viewer')
  expect(recordReads).toBe(1)
})
