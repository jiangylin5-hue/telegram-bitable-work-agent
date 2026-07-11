import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

afterEach(() => {
  vi.unstubAllGlobals()
})

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

test('a delayed relation field receipt reread cannot restore its old workspace or field', async () => {
  let sourceSchemaReads = 0
  let resolveReceiptSchema: (response: Response) => void = () => undefined
  const delayedReceiptSchema = new Promise<Response>((resolve) => { resolveReceiptSchema = resolve })
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.pathname : new URL(input.url).pathname
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'verified_adapter' },
      workspaces: [
        { id: 'workspace-1', name: 'Workspace One', slug: 'workspace-one', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: true, can_review_drafts: false } },
        { id: 'workspace-2', name: 'Workspace Two', slug: 'workspace-two', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } },
      ],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'Orders Base', source_type: 'blank' }], queue: [] }))
    if (path === '/workspaces/workspace-2/home') return Promise.resolve(json({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: 'Current Workspace', source_type: 'blank' }], queue: [] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [
      { id: 'table-orders', base_id: 'base-1', name: 'Orders', key: 'orders', status: 'active' },
      { id: 'table-customers', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' },
    ] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [{ id: 'view-orders', base_id: 'base-1', table_id: 'table-orders', name: 'All Orders', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-orders/schema') {
      sourceSchemaReads += 1
      if (sourceSchemaReads >= 3) return delayedReceiptSchema
      return Promise.resolve(json({ table: { id: 'table-orders', name: 'Orders', key: 'orders' }, fields: [{ id: 'field-name', table_id: 'table-orders', name: 'Order name', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 }] }))
    }
    if (path === '/tables/table-customers/schema') return Promise.resolve(json({ table: { id: 'table-customers', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-customer-name', table_id: 'table-customers', name: 'Customer name', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 }] }))
    if (path === '/views/view-orders/presentation') return Promise.resolve(json({ view_id: 'view-orders', table_id: 'table-orders', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: [] }))
    if (path === '/views/view-orders/records') return Promise.resolve(json({ view_id: 'view-orders', records: [], next_cursor: null, has_more: false }))
    if (path === '/tables/table-orders/create-form') return Promise.resolve(json({ table_id: 'table-orders', can_create: true, fields: [] }))
    if (path === '/tables/table-orders/relation-field-initializations') {
      expect(init?.method).toBe('POST')
      expect(init?.body).toBe(JSON.stringify({ name: 'Customer', target_table_id: 'table-customers', required: false }))
      return Promise.resolve(json({ field: { id: 'field-relation', table_id: 'table-orders', name: 'Customer', key: 'customer', field_type: 'linked_record', required: false, options: {}, order_index: 1 }, affected_view_ids: ['view-orders'] }, 201))
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('crypto', { randomUUID: () => 'relation-race-key' })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'Orders Base' }))
  fireEvent.click(await screen.findByRole('button', { name: '添加字段' }))
  fireEvent.click(screen.getByRole('button', { name: '关联记录与查找' }))
  fireEvent.change(await screen.findByLabelText('字段名称'), { target: { value: 'Customer' } })
  fireEvent.change(screen.getByLabelText('关联目标表'), { target: { value: 'table-customers' } })
  fireEvent.click(screen.getByRole('button', { name: '创建关联字段' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/tables/table-orders/relation-field-initializations', expect.objectContaining({ method: 'POST' })))
  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })
  await act(async () => {
    resolveReceiptSchema(json({ table: { id: 'table-orders', name: 'Orders', key: 'orders' }, fields: [
      { id: 'field-name', table_id: 'table-orders', name: 'Order name', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 },
      { id: 'field-relation', table_id: 'table-orders', name: 'Old workspace customer', key: 'customer', field_type: 'linked_record', required: false, options: {}, order_index: 1 },
    ] }))
    await Promise.resolve()
  })

  expect(await screen.findByRole('link', { name: 'Current Workspace' })).toBeInTheDocument()
  expect(screen.queryByRole('columnheader', { name: 'Old workspace customer' })).not.toBeInTheDocument()
  expect(screen.queryByText('field-relation')).not.toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: '添加关联字段' })).not.toBeInTheDocument()
})

test('uses safe relation candidates for create and direct edit while rendering only server lookup values', async () => {
  let created = false
  let relationUpdated = false
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.pathname : new URL(input.url).pathname
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'operator-1', source: 'verified_adapter' },
      workspaces: [{ id: 'workspace-1', name: 'Workspace One', slug: 'workspace-one', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'Orders Base', source_type: 'blank' }], queue: [] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [{ id: 'table-orders', base_id: 'base-1', name: 'Orders', key: 'orders', status: 'active' }] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [{ id: 'view-orders', base_id: 'base-1', table_id: 'table-orders', name: 'All Orders', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-orders/schema') return Promise.resolve(json({ table: { id: 'table-orders', name: 'Orders', key: 'orders' }, fields: [
      { id: 'field-name', table_id: 'table-orders', name: 'Order name', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 },
      { id: 'field-customer', table_id: 'table-orders', name: 'Customer', key: 'customer', field_type: 'linked_record', required: true, options: {}, order_index: 1 },
      { id: 'field-total', table_id: 'table-orders', name: 'Customer total', key: 'customer_total', field_type: 'lookup', required: false, options: {}, order_index: 2 },
    ] }))
    if (path === '/views/view-orders/presentation') return Promise.resolve(json({ view_id: 'view-orders', table_id: 'table-orders', view_type: 'grid', visible_field_keys: ['name', 'customer', 'customer_total'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name', 'customer'] }))
    if (path === '/views/view-orders/records') return Promise.resolve(json({
      view_id: 'view-orders',
      records: created ? [{ id: 'record-new', fields: { name: 'New order', customer: relationUpdated ? [{ id: 'customer-2', label: 'Acme' }, { id: 'customer-3', label: 'Globex' }] : [{ id: 'customer-2', label: 'Acme' }], customer_total: relationUpdated ? 86 : 42 } }] : [],
      next_cursor: null,
      has_more: false,
    }))
    if (path === '/tables/table-orders/create-form') return Promise.resolve(json({ table_id: 'table-orders', can_create: true, fields: [
      { id: 'field-name', key: 'name', name: 'Order name', field_type: 'text', required: true, options: {}, order_index: 0 },
      { id: 'field-customer', key: 'customer', name: 'Customer', field_type: 'linked_record', required: true, options: {}, order_index: 1 },
    ] }))
    if (path === '/fields/field-customer/relation-candidates') return Promise.resolve(json({ field_id: 'field-customer', records: [{ id: 'customer-2', label: 'Acme' }, { id: 'customer-3', label: 'Globex' }], next_cursor: null, has_more: false }))
    if (path === '/tables/table-orders/records' && init?.method === 'POST') {
      expect(init.body).toBe(JSON.stringify({ values: { name: 'New order', customer: ['customer-2'] } }))
      created = true
      return Promise.resolve(json({ id: 'record-new', table_id: 'table-orders', values: {}, record_status: 'active', version: 1 }, 201))
    }
    if (path === '/records/record-new' && init?.method === 'PATCH') {
      expect(init.body).toBe(JSON.stringify({ values: { customer: ['customer-2', 'customer-3'] }, expected_version: 1 }))
      relationUpdated = true
      return Promise.resolve(json({ id: 'record-new', table_id: 'table-orders', values: {}, record_status: 'active', version: 2 }))
    }
    if (path === '/records/record-new') return Promise.resolve(json({ id: 'record-new', table_id: 'table-orders', values: { name: 'New order', customer: relationUpdated ? [{ id: 'customer-2', label: 'Acme' }, { id: 'customer-3', label: 'Globex' }] : [{ id: 'customer-2', label: 'Acme' }], customer_total: relationUpdated ? 86 : 42 }, record_status: 'active', version: relationUpdated ? 2 : 1 }))
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'Orders Base' }))
  fireEvent.click(await screen.findByRole('button', { name: '新建记录' }))
  fireEvent.change(await screen.findByLabelText('Order name'), { target: { value: 'New order' } })
  fireEvent.click(await screen.findByRole('button', { name: 'Acme' }))
  fireEvent.click(screen.getByRole('button', { name: '创建记录' }))

  expect(await screen.findByRole('cell', { name: 'New order' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('cell', { name: 'New order' }))
  expect(await screen.findByText('42')).toBeInTheDocument()
  expect(screen.getAllByLabelText('Related records')[0]).toHaveTextContent('Acme')
  expect(document.body.textContent).not.toContain('customer-2')
  expect(document.body.textContent).not.toContain('target_table_id')

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  expect(screen.getAllByText('42')).toHaveLength(2)
  fireEvent.click(await screen.findByRole('button', { name: 'Globex' }))
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  expect(await screen.findAllByText('86')).toHaveLength(2)
  expect(fetchMock).toHaveBeenCalledWith('/records/record-new', expect.objectContaining({ method: 'PATCH' }))
  expect(document.body.textContent).not.toContain('customer-3')
})
