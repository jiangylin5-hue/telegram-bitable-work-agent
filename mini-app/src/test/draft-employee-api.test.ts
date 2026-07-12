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

test('submits only a versioned terminal command and keeps the opaque audit receipt', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => Promise.resolve(json({
    id: 'draft-1', status: 'confirmed', version: 2, terminal_audit_event_id: 'audit-1', trace_id: 'never-reach-client',
  })))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.confirmS5Draft('draft-1', 1, 'confirm-key')).resolves.toEqual({ id: 'draft-1', status: 'confirmed', version: 2, terminalAuditEventId: 'audit-1' })
  expect(fetchMock).toHaveBeenCalledWith('/mini-app/drafts/draft-1/confirm', expect.objectContaining({ method: 'POST', body: JSON.stringify({ expected_version: 1 }), headers: expect.objectContaining({ 'idempotency-key': 'confirm-key' }) }))
})

test('projects safe summary citations and never forwards runtime citation fields', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => Promise.resolve(json({
    kind: 'summary', answer: 'Two records need review.', citations: [{ record_id: 'record-1', field_keys: ['private'] }], runtime: { model_name: 'never-reach-client' },
  })))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.invokeS5Employee('employee-1', {
    intent: 'summarize', baseId: 'base-1', viewId: 'view-1', instruction: '请汇总',
  })).resolves.toEqual({ kind: 'summary', answer: 'Two records need review.', citations: [{ recordId: 'record-1' }] })
  expect(fetchMock).toHaveBeenCalledWith('/mini-app/digital-employees/employee-1/invocations', expect.objectContaining({
    method: 'POST', body: JSON.stringify({ intent: 'summarize', base_id: 'base-1', view_id: 'view-1', instruction: '请汇总' }),
  }))
})

test('parses only the closed assistant contact-to-view context projection', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/digital-employees/employee-1/assistant-context?limit=50') return Promise.resolve(json({
      employee: { id: 'employee-1', name: 'Ops', description: 'Safe', base_id: 'base-1' },
      views: [{ id: 'view-1', name: '待处理', view_type: 'grid' }],
      next_cursor: null,
      has_more: false,
    }))
    if (path === '/mini-app/digital-employees/employee-1/assistant-context/views/view-1') return Promise.resolve(json({
      id: 'view-1', name: '待处理', view_type: 'grid', base_id: 'base-1',
    }))
    if (path === '/mini-app/digital-employees/employee-2/assistant-context?limit=50') return Promise.resolve(json({
      employee: { id: 'employee-2', name: 'Unsafe', description: 'Unsafe', base_id: 'base-1', accessible_views: ['private'] },
      views: [{ id: 'view-1', name: '待处理', view_type: 'grid', config: { private: true } }], next_cursor: null, has_more: false,
    }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  await expect(api.getAssistantContext('employee-1')).resolves.toEqual({
    employee: { id: 'employee-1', name: 'Ops', description: 'Safe', baseId: 'base-1' },
    views: [{ id: 'view-1', name: '待处理', viewType: 'grid' }],
    nextCursor: null,
    hasMore: false,
  })
  await expect(api.getAssistantSelectedView('employee-1', 'view-1')).resolves.toEqual({
    id: 'view-1', name: '待处理', viewType: 'grid', baseId: 'base-1',
  })
  await expect(api.getAssistantContext('employee-2')).rejects.toThrow('Invalid assistant context response')
})
