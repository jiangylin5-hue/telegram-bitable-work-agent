import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const policy = {
  owner: 'write',
  admin: 'write',
  builder: 'write',
  operator: 'read',
  viewer: 'hidden',
} as const

afterEach(() => vi.unstubAllGlobals())

test('parses only the closed editable member context and sends a versioned role command', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/workspaces/workspace-1/governance/member-editor?limit=50') return Promise.resolve(json({
      workspace_id: 'workspace-1',
      members: [{ id: 'member-1', user_id: 'operator-1', role: 'operator', status: 'active', version: 1, assignable_roles: ['builder', 'operator', 'viewer'], action_map: ['must-not-reach-client'] }],
      next_cursor: null, has_more: false,
    }))
    if (path === '/mini-app/workspaces/workspace-1/governance/members/member-1/role') return Promise.resolve(json({
      id: 'member-1', user_id: 'operator-1', role: 'builder', status: 'active', version: 2, audit_trace: 'must-not-reach-client',
    }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.listGovernanceEditableMembers('workspace-1')).resolves.toEqual({
    workspaceId: 'workspace-1',
    members: [{ id: 'member-1', userId: 'operator-1', role: 'operator', status: 'active', version: 1, assignableRoles: ['builder', 'operator', 'viewer'] }],
    nextCursor: null,
    hasMore: false,
  })
  await expect(api.changeGovernanceMemberRole('workspace-1', 'member-1', 'builder', 1, 'write-key')).resolves.toEqual({
    id: 'member-1', userId: 'operator-1', role: 'builder', status: 'active', version: 2,
  })
  expect(fetchMock).toHaveBeenLastCalledWith(
    '/mini-app/workspaces/workspace-1/governance/members/member-1/role',
    expect.objectContaining({ method: 'PATCH', headers: expect.objectContaining({ 'Idempotency-Key': 'write-key' }) }),
  )
})

test('rejects malformed fixed field policy and sends no raw policy extras', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/tables/table-1/governance/field-permissions') return Promise.resolve(json({
      table_id: 'table-1',
      fields: [{ id: 'field-1', key: 'internal', label: 'Internal', field_type: 'text', policy, permission_version: 1, options: { secret: true } }],
    }))
    if (path === '/mini-app/tables/table-1/governance/fields/field-1/permission-policy') return Promise.resolve(json({
      id: 'field-1', key: 'internal', policy, permission_version: 2, raw_state: 'must-not-reach-client',
    }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.listGovernanceFieldPermissions('table-1')).resolves.toEqual({
    tableId: 'table-1',
    fields: [{ id: 'field-1', key: 'internal', label: 'Internal', fieldType: 'text', policy, permissionVersion: 1 }],
  })
  await expect(api.replaceGovernanceFieldPermissionPolicy('table-1', 'field-1', policy, 1, 'policy-key')).resolves.toEqual({
    id: 'field-1', key: 'internal', policy, permissionVersion: 2,
  })
  expect(fetchMock).toHaveBeenLastCalledWith(
    '/mini-app/tables/table-1/governance/fields/field-1/permission-policy',
    expect.objectContaining({ method: 'PUT', headers: expect.objectContaining({ 'Idempotency-Key': 'policy-key' }) }),
  )
})
