import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('creates a record from the server-composed form and reloads the active view', async () => {
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
    .mockResolvedValueOnce(new Response(JSON.stringify({ table_id: 'table-1', can_create: true, fields: [{ key: 'name', name: '客户名称', field_type: 'text', required: true, options: {}, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-2', table_id: 'table-1', values: { name: 'Northstar' }, record_status: 'active', version: 1 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }, { id: 'record-2', fields: { name: 'Northstar' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('button', { name: '新建记录' }))

  expect(await screen.findByRole('heading', { name: '新建记录' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-1/create-form', expect.any(Object))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Northstar' } })
  fireEvent.click(screen.getByRole('button', { name: '创建记录' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/tables/table-1/records', expect.objectContaining({ method: 'POST', body: JSON.stringify({ values: { name: 'Northstar' } }) })))
  expect(await screen.findByRole('cell', { name: 'Northstar' })).toBeInTheDocument()
  expect(fetchMock.mock.calls.filter(([path]) => path === '/views/view-1/records')).toHaveLength(2)
})
