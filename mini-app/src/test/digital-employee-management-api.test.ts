import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const detail = {
  id: 'employee-1',
  name: '客户助手',
  description: '安全汇总客户视图',
  status: 'draft',
  access_mode: 'assigned',
  table_count: 0,
  view_count: 0,
  member_count: 0,
  version: 1,
  base_id: 'base-1',
  telegram_alias: null,
  accessible_table_ids: [],
  accessible_view_ids: [],
  allowed_actions: ['summarize'],
  member_ids: [],
}

const summary = {
  id: detail.id,
  name: detail.name,
  description: detail.description,
  status: detail.status,
  access_mode: detail.access_mode,
  table_count: detail.table_count,
  view_count: detail.view_count,
  member_count: detail.member_count,
  version: detail.version,
}

afterEach(() => vi.unstubAllGlobals())

test('parses closed management shapes and sends only documented commands', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bases/base-1/digital-employee-management-context') return Promise.resolve(json({
      base: { id: 'base-1', name: '客户' },
      tables: [{ id: 'table-1', name: '客户表' }],
      views: [{ id: 'view-1', table_id: 'table-1', name: '全部客户', view_type: 'grid' }],
      members: [{ id: 'member-1', label: '成员 1', role: 'operator' }],
    }))
    if (path === '/mini-app/bases/base-1/digital-employees/management?limit=50') return Promise.resolve(json({
      base_id: 'base-1', employees: [summary], next_cursor: null, has_more: false,
    }))
    if (path === '/mini-app/bases/base-1/digital-employees/management') return Promise.resolve(json(detail))
    if (path === '/mini-app/digital-employees/employee-1/management') {
      if (init?.method === 'PATCH') return Promise.resolve(json({ ...detail, name: '已配置', version: 2 }))
      return Promise.resolve(json(detail))
    }
    if (path === '/mini-app/digital-employees/employee-1/member-grants') return Promise.resolve(json({ ...detail, member_ids: ['member-1'], member_count: 1, version: 3 }))
    if (path === '/mini-app/digital-employees/employee-1/activate') return Promise.resolve(json({ id: 'employee-1', status: 'active', version: 4, audit_event_id: 'audit-1' }))
    if (path === '/mini-app/digital-employees/employee-1/pause') return Promise.resolve(json({ id: 'employee-1', status: 'paused', version: 5, audit_event_id: 'audit-2' }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.getDigitalEmployeeManagementContext('base-1')).resolves.toEqual({
    base: { id: 'base-1', name: '客户' },
    tables: [{ id: 'table-1', name: '客户表' }],
    views: [{ id: 'view-1', tableId: 'table-1', name: '全部客户', viewType: 'grid' }],
    members: [{ id: 'member-1', label: '成员 1', role: 'operator' }],
  })
  await expect(api.listManagedDigitalEmployees('base-1')).resolves.toMatchObject({
    baseId: 'base-1', employees: [expect.objectContaining({ id: 'employee-1', accessMode: 'assigned' })],
  })
  await expect(api.createManagedDigitalEmployee('base-1', {
    name: '客户助手', description: '安全汇总客户视图', telegramAlias: null,
  }, 'create-key')).resolves.toMatchObject({ id: 'employee-1', status: 'draft' })
  await expect(api.updateManagedDigitalEmployee('employee-1', {
    name: '已配置', accessibleTableIds: ['table-1'], accessibleViewIds: ['view-1'], allowedActions: ['summarize'], accessMode: 'assigned',
  }, 1)).resolves.toMatchObject({ name: '已配置', version: 2 })
  await expect(api.replaceManagedDigitalEmployeeGrants('employee-1', ['member-1'], 2, 'grants-key')).resolves.toMatchObject({ memberIds: ['member-1'], version: 3 })
  await expect(api.activateManagedDigitalEmployee('employee-1', 3, 'activate-key')).resolves.toEqual({ id: 'employee-1', status: 'active', version: 4, auditEventId: 'audit-1' })
  await expect(api.pauseManagedDigitalEmployee('employee-1', 4, 'pause-key')).resolves.toEqual({ id: 'employee-1', status: 'paused', version: 5, auditEventId: 'audit-2' })

  expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/digital-employees/employee-1/management',
    expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ expected_version: 1, name: '已配置', accessible_table_ids: ['table-1'], accessible_view_ids: ['view-1'], allowed_actions: ['summarize'], access_mode: 'assigned' }) }),
  )
  expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/digital-employees/employee-1/member-grants',
    expect.objectContaining({ method: 'PUT', headers: expect.objectContaining({ 'Idempotency-Key': 'grants-key' }), body: JSON.stringify({ expected_version: 2, member_ids: ['member-1'] }) }),
  )
})

test.each([
  ['field_policy', { ...detail, field_policy: {} }],
  ['runtime', { ...detail, runtime: {} }],
  ['trace', { ...detail, trace: 'private' }],
])('rejects management payload with prohibited %s root', async (_key, response) => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(json(response))))

  await expect(api.getManagedDigitalEmployee('employee-1')).rejects.toThrow('Invalid digital employee management response')
})
