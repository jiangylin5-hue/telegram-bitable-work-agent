import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const capability = { can_read_bases: true, can_manage_workspace: false, can_manage_schema: true, can_review_drafts: false }
const bootstrap = { identity: { user_id: 'owner-1', source: 'development_header' }, workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: capability }] }
const home = { workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }
const table = { id: 'table-1', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }
const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }
const emptyPresentation = { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }
const emptyRecords = { view_id: 'view-1', records: [], next_cursor: null, has_more: false }

afterEach(() => {
  vi.unstubAllGlobals()
})

test('creates the first field only after receiving and rereading the exact safe field receipt', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('crypto', { randomUUID: () => 'field-create-1' })
  let schemaReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [view] }))
    if (path === '/tables/table-1/schema') {
      schemaReads += 1
      return Promise.resolve(json(schemaReads === 1
        ? { table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [] }
        : { table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-stage', table_id: 'table-1', name: '客户阶段', key: 'fld_stage', field_type: 'status', required: true, options: { choices: ['新建', '跟进中'] }, order_index: 0 }] }))
    }
    if (path === '/views/view-1/presentation') return Promise.resolve(json(schemaReads > 1 ? { ...emptyPresentation, visible_field_keys: ['fld_stage'] } : emptyPresentation))
    if (path === '/views/view-1/records') return Promise.resolve(json(emptyRecords))
    if (path === '/tables/table-1/create-form') return Promise.resolve(json({ table_id: 'table-1', can_create: true, fields: [{ key: 'fld_stage', name: '客户阶段', field_type: 'status', required: true, options: { choices: ['新建', '跟进中'] }, order_index: 0 }] }))
    if (path === '/tables/table-1/field-initializations') {
      expect(init?.method).toBe('POST')
      expect(init?.body).toBe(JSON.stringify({ name: '客户阶段', field_type: 'status', required: true, choices: ['新建', '跟进中'] }))
      return Promise.resolve(json({ field: { id: 'field-stage', table_id: 'table-1', name: '客户阶段', key: 'fld_stage', field_type: 'status', required: true, options: { choices: ['新建', '跟进中'] }, order_index: 0 }, affected_view_ids: ['view-1'] }, 201))
    }
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加第一个字段' }))
  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户阶段' } })
  fireEvent.change(screen.getByLabelText('字段类型'), { target: { value: 'status' } })
  fireEvent.click(screen.getByRole('checkbox', { name: '设为必填字段' }))
  fireEvent.change(screen.getByLabelText('选项 1'), { target: { value: '新建' } })
  fireEvent.click(screen.getByRole('button', { name: '添加选项' }))
  fireEvent.change(screen.getByLabelText('选项 2'), { target: { value: '跟进中' } })
  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))

  expect(await screen.findByRole('columnheader', { name: '客户阶段' })).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: '添加字段' })).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-1/field-initializations', expect.objectContaining({ method: 'POST' }))
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-1/create-form', expect.any(Object))
  expect(schemaReads).toBeGreaterThanOrEqual(2)
})

test('clears the protected workspace and field drawer when field creation is denied', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [view] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json(emptyPresentation))
    if (path === '/views/view-1/records') return Promise.resolve(json(emptyRecords))
    if (path === '/tables/table-1/field-initializations') return Promise.resolve(json({ detail: 'denied' }, 403))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加第一个字段' }))
  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '不可见字段' } })
  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))

  expect(await screen.findByLabelText('无工作区访问权限')).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: '添加字段' })).not.toBeInTheDocument()
  expect(screen.queryByText('不可见字段')).not.toBeInTheDocument()
})

test('keeps the field drawer open when a receipt field is absent from the fresh safe schema', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [view] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json(emptyPresentation))
    if (path === '/views/view-1/records') return Promise.resolve(json(emptyRecords))
    if (path === '/tables/table-1/field-initializations') return Promise.resolve(json({ field: { id: 'field-missing', table_id: 'table-1', name: '客户阶段', key: 'fld_stage', field_type: 'text', required: false, options: {}, order_index: 0 }, affected_view_ids: ['view-1'] }, 201))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加第一个字段' }))
  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户阶段' } })
  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('创建失败，请稍后重试。')
  expect(screen.getByRole('dialog', { name: '添加字段' })).toBeInTheDocument()
  expect(screen.queryByRole('columnheader', { name: '客户阶段' })).not.toBeInTheDocument()
})

test('ignores a delayed field receipt after the user changes workspace', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('crypto', { randomUUID: () => 'field-stale-1' })
  let resolveField: (response: Response) => void = () => undefined
  const delayedField = new Promise<Response>((resolve) => { resolveField = resolve })
  const workspaceTwo = { id: 'workspace-2', name: '项目中心', slug: 'projects', role: 'viewer', capabilities: { ...capability, can_manage_schema: false } }
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ ...bootstrap, workspaces: [...bootstrap.workspaces, workspaceTwo] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/workspaces/workspace-2/home') return Promise.resolve(json({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: '项目跟进', source_type: 'blank' }], queue: [] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [view] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json(emptyPresentation))
    if (path === '/views/view-1/records') return Promise.resolve(json(emptyRecords))
    if (path === '/tables/table-1/field-initializations') return delayedField
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加第一个字段' }))
  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '旧工作区字段' } })
  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))
  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })
  expect(await screen.findByRole('link', { name: '项目跟进' })).toBeInTheDocument()

  await act(async () => {
    resolveField(json({ field: { id: 'field-old', table_id: 'table-1', name: '旧工作区字段', key: 'fld_old', field_type: 'text', required: false, options: {}, order_index: 0 }, affected_view_ids: ['view-1'] }, 201))
    await Promise.resolve()
  })

  expect(screen.getByRole('link', { name: '项目跟进' })).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: '添加字段' })).not.toBeInTheDocument()
  expect(screen.queryByText('旧工作区字段')).not.toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalledWith('/tables/table-1/create-form', expect.any(Object))
})
