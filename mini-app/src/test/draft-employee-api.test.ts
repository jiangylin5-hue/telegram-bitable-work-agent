import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('parses only safe S5 contacts and draft detail fields', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') return Promise.resolve(json({
      workspace_id: 'workspace-1', contacts: [{ id: 'employee-1', base_id: 'base-1', name: 'Ops', description: 'Safe', status: 'active', available_intents: ['summarize', 'draft_update'], accessible_tables: ['private'] }], next_cursor: null, has_more: false,
    }))
    if (path === '/mini-app/drafts/draft-1') return Promise.resolve(json({
      id: 'draft-1', base_id: 'base-1', table_id: 'table-1', record_id: 'record-1', draft_type: 'update_record', status: 'pending_confirmation', version: 1,
      fields: [{ key: 'title', label: 'Title', field_type: 'text', before_value: 'Before', proposed_value: 'After', private: true }], actions: { can_confirm: true, can_reject: true }, terminal_audit_event_id: null, trace_id: 'never-reach-client',
    }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  await expect(api.listS5Contacts('workspace-1')).resolves.toEqual({
    workspaceId: 'workspace-1', contacts: [{ id: 'employee-1', baseId: 'base-1', name: 'Ops', description: 'Safe', status: 'active', availableIntents: ['summarize', 'draft_update'] }], nextCursor: null, hasMore: false,
  })
  await expect(api.getS5Draft('draft-1')).resolves.toEqual({
    id: 'draft-1', baseId: 'base-1', tableId: 'table-1', recordId: 'record-1', draftType: 'update_record', status: 'pending_confirmation', version: 1,
    fields: [{ key: 'title', label: 'Title', fieldType: 'text', beforeValue: 'Before', proposedValue: 'After' }], actions: { canConfirm: true, canReject: true }, terminalAuditEventId: null,
  })
})
