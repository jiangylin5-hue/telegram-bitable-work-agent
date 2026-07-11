import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

afterEach(() => {
  vi.unstubAllGlobals()
})

function prepareDelayedRelationLookupSchema() {
  const fetchMock = vi.fn()
  let schemaReads = 0
  let resolveSchema: (response: Response) => void = () => undefined
  const delayedSchema = new Promise<Response>((resolve) => { resolveSchema = resolve })
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(new Response(JSON.stringify({ identity: { user_id: 'owner-1', source: 'development_header' }, workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: true, can_review_drafts: false } }, { id: 'workspace-2', name: '项目中心', slug: 'projects', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/workspaces/workspace-2/home') return Promise.resolve(new Response(JSON.stringify({ workspace_id: 'workspace-2', recent_bases: [], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/bases/base-1/tables') return Promise.resolve(new Response(JSON.stringify({ tables: [{ id: 'table-orders', base_id: 'base-1', name: '订单', key: 'orders', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/bases/base-1/views') return Promise.resolve(new Response(JSON.stringify({ views: [{ id: 'view-orders', base_id: 'base-1', table_id: 'table-orders', name: '全部订单', view_type: 'grid', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/tables/table-orders/schema') {
      schemaReads += 1
      if (schemaReads > 1) return delayedSchema
      return Promise.resolve(new Response(JSON.stringify({ table: { id: 'table-orders', name: '订单', key: 'orders' }, fields: [{ id: 'field-name', table_id: 'table-orders', name: '订单名称', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (path === '/views/view-orders/presentation') return Promise.resolve(new Response(JSON.stringify({ view_id: 'view-orders', table_id: 'table-orders', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/views/view-orders/records') return Promise.resolve(new Response(JSON.stringify({ view_id: 'view-orders', records: [], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    return Promise.resolve(new Response(JSON.stringify({ detail: `unexpected ${path}` }), { status: 404, headers: { 'Content-Type': 'application/json' } }))
  })
  return {
    resolveSchema: () => resolveSchema(new Response(JSON.stringify({ table: { id: 'table-orders', name: '订单', key: 'orders' }, fields: [{ id: 'field-name', table_id: 'table-orders', name: '订单名称', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } })),
  }
}

test('replaces the F1 builder with non-submittable loading while relation schema preload is pending', async () => {
  const preload = prepareDelayedRelationLookupSchema()
  render(<App />)

  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加字段' }))
  fireEvent.click(screen.getByRole('button', { name: '关联记录与查找' }))

  expect(screen.queryByRole('button', { name: '创建字段' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '创建关联字段' })).not.toBeInTheDocument()
  await act(async () => { preload.resolveSchema(); await Promise.resolve() })
  expect(await screen.findByRole('dialog', { name: '添加关联字段' })).toBeInTheDocument()
})

test('does not restore a relation builder after its loading state is closed before delayed schema resolution', async () => {
  const preload = prepareDelayedRelationLookupSchema()
  render(<App />)

  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加字段' }))
  fireEvent.click(screen.getByRole('button', { name: '关联记录与查找' }))
  fireEvent.click(screen.getByRole('button', { name: '关闭' }))
  await act(async () => { preload.resolveSchema(); await Promise.resolve() })

  await waitFor(() => expect(screen.queryByRole('dialog', { name: '添加关联字段' })).not.toBeInTheDocument())
  expect(screen.queryByRole('dialog', { name: '添加字段' })).not.toBeInTheDocument()
})

test('does not restore a relation builder after a workspace generation replaces the loading canvas', async () => {
  const preload = prepareDelayedRelationLookupSchema()
  render(<App />)

  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加字段' }))
  fireEvent.click(screen.getByRole('button', { name: '关联记录与查找' }))
  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })
  await act(async () => { preload.resolveSchema(); await Promise.resolve() })

  await waitFor(() => expect(screen.queryByRole('dialog', { name: '添加关联字段' })).not.toBeInTheDocument())
  expect(screen.queryByRole('dialog', { name: '正在加载关系字段' })).not.toBeInTheDocument()
})

test('reuses protected table schemas to initialize a relation field and verifies its safe receipt by reread', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('crypto', { randomUUID: () => 'relation-field-1' })
  let sourceSchemaReads = 0
  let relationInitializations = 0
  let lookupInitializations = 0
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(new Response(JSON.stringify({ identity: { user_id: 'owner-1', source: 'development_header' }, workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: true, can_review_drafts: false } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/bases/base-1/tables') return Promise.resolve(new Response(JSON.stringify({ tables: [{ id: 'table-orders', base_id: 'base-1', name: '订单', key: 'orders', status: 'active' }, { id: 'table-customers', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/bases/base-1/views') return Promise.resolve(new Response(JSON.stringify({ views: [{ id: 'view-orders', base_id: 'base-1', table_id: 'table-orders', name: '全部订单', view_type: 'grid', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/tables/table-orders/schema') {
      sourceSchemaReads += 1
      const fields = [{ id: 'field-customer', table_id: 'table-orders', name: '客户关联', key: 'customer', field_type: 'linked_record', required: false, options: {}, order_index: 0 }]
      if (relationInitializations > 0) fields.push({ id: 'field-relation', table_id: 'table-orders', name: '客户', key: 'linked_customers', field_type: 'linked_record', required: true, options: {}, order_index: 1 })
      if (lookupInitializations > 0) fields.push({ id: 'field-lookup', table_id: 'table-orders', name: '客户名称查找', key: 'customer_name_lookup', field_type: 'lookup', required: false, options: {}, order_index: 2 })
      return Promise.resolve(new Response(JSON.stringify({ table: { id: 'table-orders', name: '订单', key: 'orders' }, fields }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (path === '/tables/table-customers/schema') return Promise.resolve(new Response(JSON.stringify({ table: { id: 'table-customers', name: '客户表', key: 'customers' }, fields: [{ id: 'field-name', table_id: 'table-customers', name: '客户名称', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/views/view-orders/presentation') return Promise.resolve(new Response(JSON.stringify({ view_id: 'view-orders', table_id: 'table-orders', view_type: 'grid', visible_field_keys: lookupInitializations > 0 ? ['customer', 'linked_customers', 'customer_name_lookup'] : relationInitializations > 0 ? ['customer', 'linked_customers'] : ['customer'], group_by_field_key: null, date_field_key: null, form_field_keys: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/views/view-orders/records') return Promise.resolve(new Response(JSON.stringify({ view_id: 'view-orders', records: [], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/tables/table-orders/create-form') return Promise.resolve(new Response(JSON.stringify({ table_id: 'table-orders', can_create: true, fields: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/tables/table-orders/relation-field-initializations') {
      relationInitializations += 1
      expect(init?.method).toBe('POST')
      expect(init?.body).toBe(JSON.stringify({ name: '客户', target_table_id: 'table-customers', required: true }))
      return Promise.resolve(new Response(JSON.stringify({ field: { id: 'field-relation', table_id: 'table-orders', name: '客户', key: 'linked_customers', field_type: 'linked_record', required: true, options: {}, order_index: 1 }, affected_view_ids: ['view-orders'] }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    }
    if (path === '/tables/table-orders/lookup-field-initializations') {
      lookupInitializations += 1
      expect(init?.method).toBe('POST')
      expect(init?.body).toBe(JSON.stringify({ name: '客户名称查找', source_relation_field_id: 'field-customer', target_field_id: 'field-name', aggregation: 'values' }))
      return Promise.resolve(new Response(JSON.stringify({ field: { id: 'field-lookup', table_id: 'table-orders', name: '客户名称查找', key: 'customer_name_lookup', field_type: 'lookup', required: false, options: {}, order_index: 2 }, affected_view_ids: ['view-orders'] }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    }
    return Promise.resolve(new Response(JSON.stringify({ detail: `unexpected ${path}` }), { status: 404, headers: { 'Content-Type': 'application/json' } }))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加字段' }))
  fireEvent.click(screen.getByRole('button', { name: '关联记录与查找' }))
  expect(await screen.findByRole('dialog', { name: '添加关联字段' })).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户' } })
  fireEvent.change(screen.getByLabelText('关联目标表'), { target: { value: 'table-customers' } })
  fireEvent.click(screen.getByLabelText('设为必填字段'))
  fireEvent.click(screen.getByRole('button', { name: '创建关联字段' }))

  expect(await screen.findByRole('columnheader', { name: '客户' })).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: '添加关联字段' })).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-orders/relation-field-initializations', expect.objectContaining({ method: 'POST' }))
  expect(sourceSchemaReads).toBeGreaterThanOrEqual(3)

  fireEvent.click(screen.getByRole('button', { name: '添加字段' }))
  fireEvent.click(screen.getByRole('button', { name: '关联记录与查找' }))
  fireEvent.click(await screen.findByRole('button', { name: '查找' }))
  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户名称查找' } })
  fireEvent.change(screen.getByLabelText('关联字段'), { target: { value: 'field-customer' } })
  fireEvent.change(screen.getByLabelText('目标字段'), { target: { value: 'field-name' } })
  fireEvent.click(screen.getByRole('button', { name: '创建查找字段' }))

  expect(await screen.findByRole('columnheader', { name: '客户名称查找' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-orders/lookup-field-initializations', expect.objectContaining({ method: 'POST' }))
})

test('fails closed when the protected schema reread for the relation builder is denied', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let schemaReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(new Response(JSON.stringify({ identity: { user_id: 'owner-1', source: 'development_header' }, workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: true, can_review_drafts: false } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/bases/base-1/tables') return Promise.resolve(new Response(JSON.stringify({ tables: [{ id: 'table-orders', base_id: 'base-1', name: '订单', key: 'orders', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/bases/base-1/views') return Promise.resolve(new Response(JSON.stringify({ views: [{ id: 'view-orders', base_id: 'base-1', table_id: 'table-orders', name: '全部订单', view_type: 'grid', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/tables/table-orders/schema') {
      schemaReads += 1
      if (schemaReads > 1) return Promise.resolve(new Response(JSON.stringify({ detail: 'denied' }), { status: 403, headers: { 'Content-Type': 'application/json' } }))
      return Promise.resolve(new Response(JSON.stringify({ table: { id: 'table-orders', name: '订单', key: 'orders' }, fields: [{ id: 'field-customer', table_id: 'table-orders', name: '客户关联', key: 'customer', field_type: 'linked_record', required: false, options: {}, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (path === '/views/view-orders/presentation') return Promise.resolve(new Response(JSON.stringify({ view_id: 'view-orders', table_id: 'table-orders', view_type: 'grid', visible_field_keys: ['customer'], group_by_field_key: null, date_field_key: null, form_field_keys: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/views/view-orders/records') return Promise.resolve(new Response(JSON.stringify({ view_id: 'view-orders', records: [], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    return Promise.resolve(new Response(JSON.stringify({ detail: `unexpected ${path}` }), { status: 404, headers: { 'Content-Type': 'application/json' } }))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加字段' }))
  fireEvent.click(screen.getByRole('button', { name: '关联记录与查找' }))

  expect(await screen.findByLabelText('无工作区访问权限')).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: '添加关联字段' })).not.toBeInTheDocument()
  expect(screen.queryByText('table-orders')).not.toBeInTheDocument()
})

test('renders only server-authorized workspace navigation and the safe Home queue', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValueOnce(
    new Response(
      JSON.stringify({
        identity: { user_id: 'owner-1', source: 'development_header' },
        workspaces: [
          {
            id: 'workspace-1',
            name: '运营中心',
            slug: 'operations',
            role: 'operator',
            capabilities: {
              can_read_bases: true,
              can_manage_workspace: false,
              can_manage_schema: false,
              can_review_drafts: true,
            },
          },
        ],
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ),
  )
  fetchMock.mockResolvedValueOnce(
    new Response(
      JSON.stringify({
        workspace_id: 'workspace-1',
        recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }],
        queue: [
          {
            id: 'draft-1',
            kind: 'record_change_draft',
            title: '待确认变更',
            status: 'pending_confirmation',
            destination: { base_id: 'base-1', draft_id: 'draft-1' },
            action_availability: { can_confirm: true, can_reject: true },
          },
        ],
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ),
  )

  render(<App />)

  expect(await screen.findByRole('heading', { name: '今天工作' })).toBeInTheDocument()
  expect(screen.getByText('待确认变更')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '客户管理' })).toBeInTheDocument()
  expect(screen.queryByText('成员与权限')).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/mini-app/bootstrap', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/home', expect.any(Object))
})

test('switching workspace discards the previous Home and loads the selected authorized Home', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({
      identity: { user_id: 'owner-1', source: 'development_header' },
      workspaces: [
        { id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } },
        { id: 'workspace-2', name: '项目中心', slug: 'projects', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } },
      ],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: '项目追踪', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  render(<App />)
  expect(await screen.findByRole('link', { name: '客户管理' })).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })

  expect(await screen.findByRole('link', { name: '项目追踪' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: '客户管理' })).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-2/home', expect.any(Object))
})

test('opening a Base loads its authorized table schema and saved-view records as a grid', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({
      identity: { user_id: 'operator-1', source: 'verified_adapter' },
      workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({
      workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ tables: [{ id: 'table-1', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }, { id: 'view-2', base_id: 'base-1', table_id: 'table-1', name: '按状态', view_type: 'kanban', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-1', name: '客户名称', key: 'name', field_type: 'text', required: true, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }], trace_id: 'redacted', has_more: true, next_cursor: 'cursor-2' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }, { id: 'record-2', fields: { name: 'Northstar' } }], has_more: false, next_cursor: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Co' }, record_status: 'active', version: 3 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Ltd' }, record_status: 'active', version: 4 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Ltd' }, record_status: 'active', version: 4 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Ltd' } }, { id: 'record-2', fields: { name: 'Northstar' } }], has_more: false, next_cursor: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-2', table_id: 'table-1', view_type: 'kanban', visible_field_keys: ['name', 'status'], group_by_field_key: 'status', date_field_key: null, form_field_keys: ['name', 'status'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-2', records: [{ id: 'record-2', fields: { name: 'Northstar', status: '进行中' } }], has_more: false, next_cursor: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))

  expect(await screen.findByRole('heading', { name: '客户管理' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: '全部客户' })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: '客户名称' })).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: 'Ada Co' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/bases/base-1/tables', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/bases/base-1/views', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-1/schema', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-1/presentation', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-1/records', expect.any(Object))

  fireEvent.click(screen.getByRole('button', { name: '加载更多记录' }))
  expect(await screen.findByRole('cell', { name: 'Northstar' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/views/view-1/records?cursor=cursor-2', expect.any(Object))
  const cursorRequest = fetchMock.mock.calls.find(([path]) => path === '/views/view-1/records?cursor=cursor-2')
  expect(cursorRequest?.[1]).toEqual(expect.objectContaining({ signal: expect.any(AbortSignal) }))

  fireEvent.click(screen.getByRole('cell', { name: 'Ada Co' }))
  expect(await screen.findByRole('heading', { name: '记录详情' })).toBeInTheDocument()
  expect(screen.getByText('版本 3')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/records/record-1', expect.any(Object))

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  expect(await screen.findByText('版本 4')).toBeInTheDocument()
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/records/record-1', expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ values: { name: 'Ada Ltd' }, expected_version: 3 }) })))
  await waitFor(() => expect(fetchMock.mock.calls.filter(([path]) => path === '/records/record-1').length).toBeGreaterThanOrEqual(2))
  expect(screen.getAllByText('Ada Ltd')).toHaveLength(2)

  fireEvent.click(screen.getByRole('button', { name: '关闭记录详情' }))
  fireEvent.click(screen.getByRole('tab', { name: '按状态' }))
  expect(await screen.findByText('进行中')).toBeInTheDocument()
  expect(screen.getByText('Northstar')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/views/view-2/presentation', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-2/records', expect.any(Object))
})

test('a record version conflict reloads the authoritative detail and current view window', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({ identity: { user_id: 'operator-1', source: 'verified_adapter' }, workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ tables: [{ id: 'table-1', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-1', name: '客户名称', key: 'name', field_type: 'text', required: true, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Co' }, record_status: 'active', version: 3 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'record_version_conflict' }), { status: 409, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Global' }, record_status: 'active', version: 4 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Global' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Ada Co' }))
  fireEvent.click(await screen.findByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  expect(await screen.findByText('记录已被更新，已刷新最新版本，请重新编辑。')).toBeInTheDocument()
  expect(screen.getByText('版本 4')).toBeInTheDocument()
  expect(screen.getAllByText('Ada Global')).toHaveLength(2)
  await waitFor(() => expect(fetchMock.mock.calls.filter(([path]) => path === '/views/view-1/records')).toHaveLength(2))
  expect(fetchMock.mock.calls.filter(([path]) => path === '/records/record-1')).toHaveLength(3)
})

test('discarding an in-flight Base open cannot restore the previous workspace after a switch', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let resolveTables: (response: Response) => void = () => undefined
  let resolveViews: (response: Response) => void = () => undefined
  const tablesResponse = new Promise<Response>((resolve) => { resolveTables = resolve })
  const viewsResponse = new Promise<Response>((resolve) => { resolveViews = resolve })
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({ identity: { user_id: 'operator-1', source: 'verified_adapter' }, workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }, { id: 'workspace-2', name: '项目中心', slug: 'projects', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockImplementationOnce(() => tablesResponse)
    .mockImplementationOnce(() => viewsResponse)
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: '项目跟踪', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })
  expect(await screen.findByRole('link', { name: '项目跟踪' })).toBeInTheDocument()

  resolveTables(new Response(JSON.stringify({ tables: [{ id: 'table-1', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  resolveViews(new Response(JSON.stringify({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  await waitFor(() => expect(screen.getByRole('link', { name: '项目跟踪' })).toBeInTheDocument())
  expect(screen.queryByRole('heading', { name: '客户管理' })).not.toBeInTheDocument()
})

test('discarding an in-flight saved-view selection cannot restore the previous Base after a workspace switch', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let resolvePresentation: (response: Response) => void = () => undefined
  let resolveRecords: (response: Response) => void = () => undefined
  let resolveWorkspaceHome: (response: Response) => void = () => undefined
  const viewPresentation = new Promise<Response>((resolve) => { resolvePresentation = resolve })
  const viewRecords = new Promise<Response>((resolve) => { resolveRecords = resolve })
  const workspaceHome = new Promise<Response>((resolve) => { resolveWorkspaceHome = resolve })
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({ identity: { user_id: 'operator-1', source: 'verified_adapter' }, workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }, { id: 'workspace-2', name: '项目中心', slug: 'projects', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ tables: [{ id: 'table-1', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }, { id: 'view-2', base_id: 'base-1', table_id: 'table-1', name: '按状态', view_type: 'kanban', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-name', name: '客户名称', key: 'name', field_type: 'text', required: true, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockImplementationOnce(() => viewPresentation)
    .mockImplementationOnce(() => viewRecords)
    .mockImplementationOnce(() => workspaceHome)

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('tab', { name: '按状态' }))
  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })

  await act(async () => {
    resolvePresentation(new Response(JSON.stringify({ view_id: 'view-2', table_id: 'table-1', view_type: 'kanban', visible_field_keys: ['name'], group_by_field_key: 'status', date_field_key: null, form_field_keys: ['name'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    resolveRecords(new Response(JSON.stringify({ view_id: 'view-2', records: [{ id: 'record-1', fields: { name: 'Ada Co', status: '进行中' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await Promise.resolve()
  })

  expect(screen.queryByRole('heading', { name: '客户管理' })).not.toBeInTheDocument()
  resolveWorkspaceHome(new Response(JSON.stringify({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: '项目跟踪', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  expect(await screen.findByRole('link', { name: '项目跟踪' })).toBeInTheDocument()
})

test('discarding an in-flight record detail cannot restore the previous workspace after a switch', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let resolveRecord: (response: Response) => void = () => undefined
  const recordDetail = new Promise<Response>((resolve) => { resolveRecord = resolve })
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({ identity: { user_id: 'operator-1', source: 'verified_adapter' }, workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }, { id: 'workspace-2', name: '项目中心', slug: 'projects', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ tables: [{ id: 'table-1', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-name', name: '客户名称', key: 'name', field_type: 'text', required: true, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockImplementationOnce(() => recordDetail)
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: '项目跟踪', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Ada Co' }))
  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })
  expect(await screen.findByRole('link', { name: '项目跟踪' })).toBeInTheDocument()

  await act(async () => {
    resolveRecord(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Co' }, record_status: 'active', version: 3 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await Promise.resolve()
  })

  expect(screen.queryByRole('heading', { name: '记录详情' })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: '项目跟踪' })).toBeInTheDocument()
})

test('discarding an in-flight record save cannot restore the previous workspace after a switch', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let resolveUpdate: (response: Response) => void = () => undefined
  const updateResponse = new Promise<Response>((resolve) => { resolveUpdate = resolve })
  let recordReads = 0

  fetchMock.mockImplementation((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.pathname : new URL(input.url).pathname
    if (path === '/mini-app/bootstrap') return Promise.resolve(new Response(JSON.stringify({
      identity: { user_id: 'operator-1', source: 'verified_adapter' },
      workspaces: [
        { id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } },
        { id: 'workspace-2', name: '项目中心', slug: 'projects', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } },
      ],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/workspaces/workspace-2/home') return Promise.resolve(new Response(JSON.stringify({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: '项目跟踪', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/bases/base-1/tables') return Promise.resolve(new Response(JSON.stringify({ tables: [{ id: 'table-1', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/bases/base-1/views') return Promise.resolve(new Response(JSON.stringify({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/tables/table-1/schema') return Promise.resolve(new Response(JSON.stringify({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-name', table_id: 'table-1', name: '客户名称', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/views/view-1/presentation') return Promise.resolve(new Response(JSON.stringify({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/views/view-1/records') return Promise.resolve(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: recordReads > 0 ? 'Ada Ltd' : 'Ada Co' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (path === '/records/record-1' && init?.method === 'PATCH') return updateResponse
    if (path === '/records/record-1') {
      recordReads += 1
      return Promise.resolve(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: recordReads > 1 ? 'Ada Ltd' : 'Ada Co' }, record_status: 'active', version: recordReads > 1 ? 4 : 3 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Ada Co' }))
  fireEvent.click(await screen.findByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/records/record-1', expect.objectContaining({ method: 'PATCH' })))

  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })
  expect(await screen.findByRole('link', { name: '项目跟踪' })).toBeInTheDocument()

  await act(async () => {
    resolveUpdate(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Ltd' }, record_status: 'active', version: 4 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await Promise.resolve()
  })

  await waitFor(() => expect(screen.getByRole('link', { name: '项目跟踪' })).toBeInTheDocument())
  expect(screen.queryByRole('heading', { name: '客户管理' })).not.toBeInTheDocument()
  expect(screen.queryByText('Ada Ltd')).not.toBeInTheDocument()
})
