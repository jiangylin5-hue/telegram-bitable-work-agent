import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

afterEach(() => {
  vi.unstubAllGlobals()
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
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }], trace_id: 'redacted', has_more: false, next_cursor: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Co' }, record_status: 'active', version: 3 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
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

  fireEvent.click(screen.getByRole('cell', { name: 'Ada Co' }))
  expect(await screen.findByRole('heading', { name: '记录详情' })).toBeInTheDocument()
  expect(screen.getByText('版本 3')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/records/record-1', expect.any(Object))

  fireEvent.click(screen.getByRole('button', { name: '关闭记录详情' }))
  fireEvent.click(screen.getByRole('tab', { name: '按状态' }))
  expect(await screen.findByText('进行中')).toBeInTheDocument()
  expect(screen.getByText('Northstar')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/views/view-2/presentation', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/views/view-2/records', expect.any(Object))
})
