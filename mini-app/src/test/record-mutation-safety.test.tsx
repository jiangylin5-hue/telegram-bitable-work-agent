import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

afterEach(() => {
  vi.unstubAllGlobals()
})

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

function installRecordMutationFixture(updateStatus: number, refreshStatus?: number, delayUpdate = false, loadMoreStatus?: number) {
  let recordReads = 0
  let viewReads = 0
  let refreshViewSignal: AbortSignal | undefined
  let resolveRefreshView: (response: Response) => void = () => undefined
  const refreshViewResponse = new Promise<Response>((resolve) => { resolveRefreshView = resolve })
  let resolveUpdate: (response: Response) => void = () => undefined
  const updateResponse = new Promise<Response>((resolve) => { resolveUpdate = resolve })
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const requestUrl = new URL(typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url, 'http://fixture.local')
    const path = requestUrl.pathname
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'operator-1', source: 'verified_adapter' },
      workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [{ id: 'table-1', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-name', table_id: 'table-1', name: '客户名称', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 }] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }))
    if (path === '/views/view-1/records') {
      if (requestUrl.searchParams.get('cursor') === 'cursor-1') {
        return Promise.resolve(json({ detail: { code: 'identity_expired' } }, loadMoreStatus ?? 200))
      }
      viewReads += 1
      if (viewReads === 1) return Promise.resolve(json({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }, { id: 'record-2', fields: { name: 'Grace Co' } }], next_cursor: loadMoreStatus ? 'cursor-1' : null, has_more: Boolean(loadMoreStatus) }))
      refreshViewSignal = init?.signal ?? undefined
      return refreshViewResponse
    }
    if (path === '/records/record-1' && init?.method === 'PATCH') {
      return delayUpdate ? updateResponse : Promise.resolve(json({ detail: { code: 'permission_denied', message: 'private server detail' } }, updateStatus))
    }
    if (path === '/records/record-1') {
      recordReads += 1
      if (recordReads > 1 && refreshStatus) return Promise.resolve(json({ detail: { code: 'permission_denied', message: 'private refresh detail' } }, refreshStatus))
      return Promise.resolve(json({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Co' }, record_status: 'active', version: 3 }))
    }
    if (path === '/records/record-2') return Promise.resolve(json({ id: 'record-2', table_id: 'table-1', values: { name: 'Grace Co' }, record_status: 'active', version: 2 }))
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  return { fetchMock, getRefreshViewSignal: () => refreshViewSignal, resolveRefreshView, resolveUpdate }
}

test.each([401, 403, 404])('record save %s fails closed without retaining protected record content', async (status) => {
  const { fetchMock } = installRecordMutationFixture(status)
  render(<App />)

  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Ada Co' }))
  fireEvent.click(await screen.findByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  expect(await screen.findByRole('main', { name: '无工作区访问权限' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '记录详情' })).not.toBeInTheDocument()
  expect(screen.queryByText('Ada Co')).not.toBeInTheDocument()
  expect(document.body.textContent).not.toContain('private server detail')
  expect(fetchMock).toHaveBeenCalledWith('/records/record-1', expect.objectContaining({ method: 'PATCH' }))
})

test('a late direct-save 403 still closes the active workspace after switching records', async () => {
  const fixture = installRecordMutationFixture(403, undefined, true)
  render(<App />)

  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Ada Co' }))
  fireEvent.click(await screen.findByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  expect(fixture.fetchMock).toHaveBeenCalledWith('/records/record-1', expect.objectContaining({ method: 'PATCH' }))

  fireEvent.click(screen.getByRole('cell', { name: 'Grace Co' }))
  expect(await screen.findByText('版本 2')).toBeInTheDocument()
  await act(async () => {
    fixture.resolveUpdate(json({ detail: { code: 'permission_denied', message: 'private late detail' } }, 403))
    await Promise.resolve()
  })

  expect(await screen.findByRole('main', { name: '无工作区访问权限' })).toBeInTheDocument()
  expect(document.body.textContent).not.toContain('private late detail')
})

test('a session failure prevents a concurrent direct-save completion from repopulating protected queries', async () => {
  const fixture = installRecordMutationFixture(200, undefined, true, 401)
  render(<App />)

  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Ada Co' }))
  fireEvent.click(await screen.findByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  expect(fixture.fetchMock).toHaveBeenCalledWith('/records/record-1', expect.objectContaining({ method: 'PATCH' }))

  fireEvent.click(screen.getByRole('button', { name: '加载更多记录' }))
  expect(await screen.findByRole('main', { name: '无工作区访问权限' })).toBeInTheDocument()
  await act(async () => {
    fixture.resolveUpdate(json({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Ltd' }, record_status: 'active', version: 4 }))
    await Promise.resolve()
    await Promise.resolve()
  })

  const recordReads = fixture.fetchMock.mock.calls.filter(([input, init]) => {
    const requestUrl = new URL(typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url, 'http://fixture.local')
    return requestUrl.pathname === '/records/record-1' && init?.method !== 'PATCH'
  })
  expect(recordReads).toHaveLength(1)
  expect(screen.queryByText('Ada Ltd')).not.toBeInTheDocument()
})

test.each([401, 403, 404])('record conflict refresh %s cancels protected rereads and fails closed', async (status) => {
  const fixture = installRecordMutationFixture(409, status)
  render(<App />)

  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Ada Co' }))
  fireEvent.click(await screen.findByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  expect(await screen.findByRole('main', { name: '无工作区访问权限' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '记录详情' })).not.toBeInTheDocument()
  expect(document.body.textContent).not.toContain('private refresh detail')
  expect(fixture.getRefreshViewSignal()).toBeInstanceOf(AbortSignal)
  expect(fixture.getRefreshViewSignal()?.aborted).toBe(true)
  fixture.resolveRefreshView(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
})

test('closing the record panel cancels an already-started conflict refresh', async () => {
  const fixture = installRecordMutationFixture(409)
  render(<App />)

  fireEvent.click(await screen.findByRole('link', { name: '客户管理' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Ada Co' }))
  fireEvent.click(await screen.findByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  await waitFor(() => expect(fixture.getRefreshViewSignal()).toBeInstanceOf(AbortSignal))

  fireEvent.click(screen.getByRole('button', { name: '关闭记录详情' }))
  expect(fixture.getRefreshViewSignal()?.aborted).toBe(true)
  fixture.resolveRefreshView(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
})

test('workspace Home 401 cannot rehydrate protected state through an automatic bootstrap refetch', async () => {
  let bootstrapCalls = 0
  let homeCalls = 0
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.pathname : new URL(input.url).pathname
    if (path === '/mini-app/bootstrap') {
      bootstrapCalls += 1
      return Promise.resolve(json({
        identity: { user_id: 'operator-1', source: 'verified_adapter' },
        workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }],
      }))
    }
    if (path === '/workspaces/workspace-1/home') {
      homeCalls += 1
      return Promise.resolve(homeCalls === 1
        ? json({ detail: { code: 'identity_expired' } }, 401)
        : json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '不应恢复', source_type: 'blank' }], queue: [] }))
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  expect(await screen.findByRole('main', { name: '无工作区访问权限' })).toBeInTheDocument()
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
  expect(bootstrapCalls).toBe(1)
  expect(homeCalls).toBe(1)
  expect(screen.queryByText('不应恢复')).not.toBeInTheDocument()
})
