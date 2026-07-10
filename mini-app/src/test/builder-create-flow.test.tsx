import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const capability = { can_read_bases: true, can_manage_workspace: false, can_manage_schema: true, can_review_drafts: false }
const workspace = { id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: capability }
const bootstrap = (workspaces = [workspace]) => ({ identity: { user_id: 'owner-1', source: 'development_header' }, workspaces })
const home = (recent_bases: { id: string; name: string; source_type: string }[]) => ({ workspace_id: 'workspace-1', recent_bases, queue: [] })
const grid = (tableId: string, viewId: string) => ({ view_id: viewId, table_id: tableId, view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] })
const records = (viewId: string) => ({ view_id: viewId, records: [], next_cursor: null, has_more: false })

afterEach(() => {
  vi.unstubAllGlobals()
})

test('creates a Base only after refreshing and resolving the exact authorized receipt resources', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('crypto', { randomUUID: () => 'create-base-1' })
  let homeReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap()))
    if (path === '/workspaces/workspace-1/home') {
      homeReads += 1
      return Promise.resolve(json(homeReads === 1 ? home([]) : home([{ id: 'base-new', name: '客户运营', source_type: 'blank' }])))
    }
    if (path === '/workspaces/workspace-1/base-initializations') {
      expect(init?.method).toBe('POST')
      expect(new Headers(init?.headers).get('Idempotency-Key')).toBe('create-base-1')
      expect(init?.body).toBe(JSON.stringify({ base_name: '客户运营', table_name: '客户' }))
      return Promise.resolve(json({ base: { id: 'base-new', name: '客户运营', source_type: 'blank', status: 'active' }, table: { id: 'table-new', base_id: 'base-new', name: '客户', key: 'tbl_new', status: 'active' }, default_view: { id: 'view-new', base_id: 'base-new', table_id: 'table-new', name: '所有记录', view_type: 'grid', status: 'active' } }, 201))
    }
    if (path === '/bases/base-new/tables') return Promise.resolve(json({ tables: [{ id: 'table-new', base_id: 'base-new', name: '客户', key: 'tbl_new', status: 'active' }] }))
    if (path === '/bases/base-new/views') return Promise.resolve(json({ views: [{ id: 'view-new', base_id: 'base-new', table_id: 'table-new', name: '所有记录', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-new/schema') return Promise.resolve(json({ table: { id: 'table-new', name: '客户', key: 'tbl_new' }, fields: [] }))
    if (path === '/views/view-new/presentation') return Promise.resolve(json(grid('table-new', 'view-new')))
    if (path === '/views/view-new/records') return Promise.resolve(json(records('view-new')))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '新建 Base' }))
  fireEvent.change(screen.getByLabelText('Base 名称'), { target: { value: '客户运营' } })
  fireEvent.change(screen.getByLabelText('首张表名称'), { target: { value: '客户' } })
  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))

  expect(await screen.findByRole('heading', { name: '客户运营' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: '客户' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: '所有记录' })).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('此数据表尚未添加字段。')
  expect(screen.getByRole('button', { name: '添加第一个字段' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '新建记录' })).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/home', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/bases/base-new/tables', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/bases/base-new/views', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-new/schema', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-new/presentation', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-new/records', expect.any(Object))
})

test('opens the exact new table and view even when fresh lists put older resources first', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('crypto', { randomUUID: () => 'create-table-1' })
  let tableReads = 0
  let viewReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap()))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home([{ id: 'base-1', name: 'CRM', source_type: 'blank' }])))
    if (path === '/bases/base-1/tables') {
      tableReads += 1
      return Promise.resolve(json({ tables: tableReads === 1 ? [{ id: 'table-old', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }] : [{ id: 'table-old', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }, { id: 'table-new', base_id: 'base-1', name: '待办', key: 'tbl_new', status: 'active' }] }))
    }
    if (path === '/bases/base-1/views') {
      viewReads += 1
      return Promise.resolve(json({ views: viewReads === 1 ? [{ id: 'view-old', base_id: 'base-1', table_id: 'table-old', name: '所有客户', view_type: 'grid', status: 'active' }] : [{ id: 'view-old', base_id: 'base-1', table_id: 'table-old', name: '所有客户', view_type: 'grid', status: 'active' }, { id: 'view-new', base_id: 'base-1', table_id: 'table-new', name: '所有待办', view_type: 'grid', status: 'active' }] }))
    }
    if (path === '/bases/base-1/table-initializations') return Promise.resolve(json({ base: { id: 'base-1', name: 'CRM', source_type: 'blank', status: 'active' }, table: { id: 'table-new', base_id: 'base-1', name: '待办', key: 'tbl_new', status: 'active' }, default_view: { id: 'view-new', base_id: 'base-1', table_id: 'table-new', name: '所有待办', view_type: 'grid', status: 'active' } }, 201))
    if (path === '/tables/table-old/schema') return Promise.resolve(json({ table: { id: 'table-old', name: '客户', key: 'customers' }, fields: [{ id: 'name', name: '名称', key: 'name', field_type: 'text', required: false, order_index: 0 }] }))
    if (path === '/views/view-old/presentation') return Promise.resolve(json({ ...grid('table-old', 'view-old'), visible_field_keys: ['name'] }))
    if (path === '/views/view-old/records') return Promise.resolve(json({ view_id: 'view-old', records: [], next_cursor: null, has_more: false }))
    if (path === '/tables/table-new/schema') return Promise.resolve(json({ table: { id: 'table-new', name: '待办', key: 'tbl_new' }, fields: [] }))
    if (path === '/views/view-new/presentation') return Promise.resolve(json(grid('table-new', 'view-new')))
    if (path === '/views/view-new/records') return Promise.resolve(json(records('view-new')))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  expect(await screen.findByRole('tab', { name: '客户' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '新建表' }))
  fireEvent.change(screen.getByLabelText('数据表名称'), { target: { value: '待办' } })
  fireEvent.click(screen.getByRole('button', { name: '创建数据表' }))

  expect(await screen.findByRole('tab', { name: '待办' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('tab', { name: '所有待办' })).toHaveAttribute('aria-selected', 'true')
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-new/schema', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-new/presentation', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-new/records', expect.any(Object))
})

test('renders a safe empty canvas when a receipt resource is absent from fresh authorized lists', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('crypto', { randomUUID: () => 'missing-resource-1' })
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap()))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home([])))
    if (path === '/workspaces/workspace-1/base-initializations') return Promise.resolve(json({ base: { id: 'base-new', name: '客户运营', source_type: 'blank', status: 'active' }, table: { id: 'table-new', base_id: 'base-new', name: '客户', key: 'tbl_new', status: 'active' }, default_view: { id: 'view-new', base_id: 'base-new', table_id: 'table-new', name: '所有记录', view_type: 'grid', status: 'active' } }, 201))
    if (path === '/bases/base-new/tables') return Promise.resolve(json({ tables: [{ id: 'table-old', base_id: 'base-new', name: '旧表', key: 'old', status: 'active' }] }))
    if (path === '/bases/base-new/views') return Promise.resolve(json({ views: [{ id: 'view-old', base_id: 'base-new', table_id: 'table-old', name: '旧视图', view_type: 'grid', status: 'active' }] }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '新建 Base' }))
  fireEvent.change(screen.getByLabelText('Base 名称'), { target: { value: '客户运营' } })
  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))

  expect(await screen.findByText('这个 Base 还没有可访问的表或保存视图。')).toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalledWith('/tables/table-old/schema', expect.any(Object))
  expect(fetchMock).not.toHaveBeenCalledWith('/views/view-old/presentation', expect.any(Object))
  expect(fetchMock).not.toHaveBeenCalledWith('/views/view-old/records', expect.any(Object))
})

test('clears the protected workspace and panel after a denied creation response', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap()))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home([])))
    if (path === '/workspaces/workspace-1/base-initializations') return Promise.resolve(json({ detail: 'denied' }, 403))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '新建 Base' }))
  fireEvent.change(screen.getByLabelText('Base 名称'), { target: { value: '不可见 Base' } })
  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))

  expect(await screen.findByLabelText('无工作区访问权限')).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.queryByText('不可见 Base')).not.toBeInTheDocument()
})

test('keeps a failed creation drawer and its idempotency key for an explicit retry', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('crypto', { randomUUID: () => 'retry-base-1' })
  let creationAttempts = 0
  let homeReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap()))
    if (path === '/workspaces/workspace-1/home') {
      homeReads += 1
      return Promise.resolve(json(home(homeReads === 1 ? [] : [{ id: 'base-retry', name: '重试 Base', source_type: 'blank' }])))
    }
    if (path === '/workspaces/workspace-1/base-initializations') {
      creationAttempts += 1
      expect(new Headers(init?.headers).get('Idempotency-Key')).toBe('retry-base-1')
      if (creationAttempts === 1) return Promise.resolve(json({ detail: 'temporary' }, 500))
      return Promise.resolve(json({ base: { id: 'base-retry', name: '重试 Base', source_type: 'blank', status: 'active' }, table: { id: 'table-retry', base_id: 'base-retry', name: '数据表', key: 'tbl_retry', status: 'active' }, default_view: { id: 'view-retry', base_id: 'base-retry', table_id: 'table-retry', name: '所有记录', view_type: 'grid', status: 'active' } }, 201))
    }
    if (path === '/bases/base-retry/tables') return Promise.resolve(json({ tables: [{ id: 'table-retry', base_id: 'base-retry', name: '数据表', key: 'tbl_retry', status: 'active' }] }))
    if (path === '/bases/base-retry/views') return Promise.resolve(json({ views: [{ id: 'view-retry', base_id: 'base-retry', table_id: 'table-retry', name: '所有记录', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-retry/schema') return Promise.resolve(json({ table: { id: 'table-retry', name: '数据表', key: 'tbl_retry' }, fields: [] }))
    if (path === '/views/view-retry/presentation') return Promise.resolve(json(grid('table-retry', 'view-retry')))
    if (path === '/views/view-retry/records') return Promise.resolve(json(records('view-retry')))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '新建 Base' }))
  fireEvent.change(screen.getByLabelText('Base 名称'), { target: { value: '重试 Base' } })
  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('创建失败，请稍后重试。')
  expect(screen.getByRole('dialog')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))
  expect(await screen.findByRole('heading', { name: '重试 Base' })).toBeInTheDocument()
  expect(creationAttempts).toBe(2)
})

test('ignores a delayed creation receipt after the user has changed workspace', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let resolveCreation: (response: Response) => void = () => undefined
  const delayedCreation = new Promise<Response>((resolve) => { resolveCreation = resolve })
  const workspaceTwo = { id: 'workspace-2', name: '项目中心', slug: 'projects', role: 'viewer', capabilities: { ...capability, can_manage_schema: false } }
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap([workspace, workspaceTwo])))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home([])))
    if (path === '/workspaces/workspace-2/home') return Promise.resolve(json({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: '项目跟踪', source_type: 'blank' }], queue: [] }))
    if (path === '/workspaces/workspace-1/base-initializations') return delayedCreation
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '新建 Base' }))
  fireEvent.change(screen.getByLabelText('Base 名称'), { target: { value: '旧工作区 Base' } })
  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))
  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })
  expect(await screen.findByRole('link', { name: '项目跟踪' })).toBeInTheDocument()

  await act(async () => {
    resolveCreation(json({ base: { id: 'base-old', name: '旧工作区 Base', source_type: 'blank', status: 'active' }, table: { id: 'table-old', base_id: 'base-old', name: '数据表', key: 'tbl_old', status: 'active' }, default_view: { id: 'view-old', base_id: 'base-old', table_id: 'table-old', name: '所有记录', view_type: 'grid', status: 'active' } }, 201))
    await Promise.resolve()
  })

  expect(screen.getByRole('link', { name: '项目跟踪' })).toBeInTheDocument()
  expect(screen.queryByText('旧工作区 Base')).not.toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalledWith('/bases/base-old/tables', expect.any(Object))
})
