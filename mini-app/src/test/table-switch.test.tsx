import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('switches an authorized Base table through its server-returned saved view', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({ identity: { user_id: 'operator-1', source: 'verified_adapter' }, workspaces: [{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ tables: [{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }, { id: 'table-2', base_id: 'base-1', name: 'Projects', key: 'projects', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All customers', view_type: 'grid', status: 'active' }, { id: 'view-2', base_id: 'base-1', table_id: 'table-2', name: 'All projects', view_type: 'grid', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-1', name: 'Customer', key: 'name', field_type: 'text', required: true, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ table: { id: 'table-2', name: 'Projects', key: 'projects' }, fields: [{ id: 'field-2', name: 'Project', key: 'name', field_type: 'text', required: true, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-2', table_id: 'table-2', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-2', records: [{ id: 'record-2', fields: { name: 'Apollo' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  expect(await screen.findByRole('cell', { name: 'Ada Co' })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('tab', { name: 'Projects' }))

  expect(await screen.findByRole('cell', { name: 'Apollo' })).toBeInTheDocument()
  expect(screen.queryByRole('cell', { name: 'Ada Co' })).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-2/schema', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-2/presentation', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-2/records', expect.any(Object))
})

test('shows the safe empty canvas without guessing resources for a table with no saved view', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({ identity: { user_id: 'operator-1', source: 'verified_adapter' }, workspaces: [{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ tables: [{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }, { id: 'table-2', base_id: 'base-1', name: 'Projects', key: 'projects', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All customers', view_type: 'grid', status: 'active' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-1', name: 'Customer', key: 'name', field_type: 'text', required: true, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }], next_cursor: null, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  expect(await screen.findByRole('cell', { name: 'Ada Co' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: 'Projects' }))

  expect(await screen.findByText('这个 Base 还没有可访问的表或保存视图。')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(7)
})
