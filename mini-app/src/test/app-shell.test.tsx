import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }], trace_id: 'redacted', has_more: true, next_cursor: 'cursor-2' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }, { id: 'record-2', fields: { name: 'Northstar' } }], has_more: false, next_cursor: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Co' }, record_status: 'active', version: 3 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Ltd' }, record_status: 'active', version: 4 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
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

  fireEvent.click(screen.getByRole('cell', { name: 'Ada Co' }))
  expect(await screen.findByRole('heading', { name: '记录详情' })).toBeInTheDocument()
  expect(screen.getByText('版本 3')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/records/record-1', expect.any(Object))

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  expect(await screen.findByText('版本 4')).toBeInTheDocument()
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/records/record-1', expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ values: { name: 'Ada Ltd' }, expected_version: 3 }) })))

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
