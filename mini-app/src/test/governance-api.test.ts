import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('parses only the safe governance member projection', async () => {
  const fetchMock = vi.fn().mockResolvedValue(json({
    workspace_id: 'workspace-1',
    members: [{
      id: 'member-1', user_id: 'user-1', role: 'admin', status: 'active',
      workspace_id: 'must-not-reach-client', permission_snapshot: { hidden: true },
    }],
    next_cursor: 'cursor-1', has_more: true, internal: 'must-not-reach-client',
  }))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.listGovernanceMembers('workspace-1')).resolves.toEqual({
    workspaceId: 'workspace-1',
    members: [{ id: 'member-1', userId: 'user-1', role: 'admin', status: 'active' }],
    nextCursor: 'cursor-1',
    hasMore: true,
  })
  expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/workspaces/workspace-1/governance/members?limit=50',
    expect.any(Object),
  )
})

test('parses only the safe governance audit projection and opaque cursor', async () => {
  const fetchMock = vi.fn().mockResolvedValue(json({
    base_id: 'base-1',
    events: [{
      id: 'audit-1', occurred_at: '2026-07-12T00:00:00Z', actor_type: 'user',
      event_type: 'stage06.record_created', entity_type: 'record',
      trace_id: 'must-not-reach-client', actor_id: 'must-not-reach-client',
      after_state: { secret: 'must-not-reach-client' },
    }],
    next_cursor: null, has_more: false,
  }))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.listGovernanceAuditEvents('base-1', 'opaque cursor')).resolves.toEqual({
    baseId: 'base-1',
    events: [{
      id: 'audit-1', occurredAt: '2026-07-12T00:00:00Z', actorType: 'user',
      eventType: 'stage06.record_created', entityType: 'record',
    }],
    nextCursor: null,
    hasMore: false,
  })
  expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/bases/base-1/governance/audit-events?limit=50&cursor=opaque+cursor',
    expect.any(Object),
  )
})
