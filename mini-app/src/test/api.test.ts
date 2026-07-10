import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('forwards the query cancellation signal to the protected workspace Home request', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchMock)
  const controller = new AbortController()

  await (api.workspaceHome as (workspaceId: string, init: RequestInit) => Promise<unknown>)('workspace-1', { signal: controller.signal })

  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/home', expect.objectContaining({ signal: controller.signal }))
})

test('loads the server-filtered create form and submits only its values', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ table_id: 'table-1', can_create: true, fields: [{ key: 'title', name: 'Title', field_type: 'text', required: true, options: {}, order_index: 0 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'record-1', table_id: 'table-1', values: { title: 'Launch' }, record_status: 'active', version: 1 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchMock)

  await api.createForm('table-1')
  await api.createRecord('table-1', { title: 'Launch' })

  expect(fetchMock).toHaveBeenCalledWith('/tables/table-1/create-form', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/tables/table-1/records', expect.objectContaining({ method: 'POST', body: JSON.stringify({ values: { title: 'Launch' } }) }))
})

test('submits an atomic Base initialization with its explicit idempotency key', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
    base: { id: 'base-1', name: '客户运营', source_type: 'blank', status: 'active' },
    table: { id: 'table-1', base_id: 'base-1', name: '客户', key: 'tbl_1', status: 'active' },
    default_view: { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '所有记录', view_type: 'grid', status: 'active' },
  }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchMock)

  await api.initializeBase('workspace-1', { baseName: '客户运营', tableName: '客户' }, 'idempotency-1')

  expect(fetchMock).toHaveBeenCalledWith(
    '/workspaces/workspace-1/base-initializations',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ base_name: '客户运营', table_name: '客户' }),
    }),
  )
  const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
  const headers = new Headers(request.headers)
  expect(headers.get('Accept')).toBe('application/json')
  expect(headers.get('Content-Type')).toBe('application/json')
  expect(headers.get('Idempotency-Key')).toBe('idempotency-1')
})
