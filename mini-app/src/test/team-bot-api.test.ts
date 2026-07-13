import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('parses only the safe team bot summary contract and sends its required idempotency key', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input) !== '/mini-app/team-bots/employee-1/summaries') {
      return Promise.resolve(json({ detail: 'unexpected' }, 404))
    }
    return Promise.resolve(json({
      kind: 'summary',
      employee_id: 'employee-1',
      base_id: 'base-1',
      view_id: 'view-1',
      answer: 'Safe team answer.',
      citations: [{ record_id: 'record-1' }],
      knowledge_window_truncated: true,
      audit_event_id: 'audit-1',
    }))
  })
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.summarizeTeamBot('employee-1', {
    baseId: 'base-1',
    viewId: 'view-1',
    instruction: 'Summarize the current team work.',
  }, 'team-key')).resolves.toEqual({
    kind: 'summary',
    employeeId: 'employee-1',
    baseId: 'base-1',
    viewId: 'view-1',
    answer: 'Safe team answer.',
    citations: [{ recordId: 'record-1' }],
    knowledgeWindowTruncated: true,
    auditEventId: 'audit-1',
  })
  expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/team-bots/employee-1/summaries',
    expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ 'idempotency-key': 'team-key' }),
      body: JSON.stringify({ base_id: 'base-1', view_id: 'view-1', instruction: 'Summarize the current team work.' }),
    }),
  )
})
