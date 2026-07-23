import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('submits only the Stage08 safe query shape and parses the safe response projection', async () => {
  const fetchMock = vi.fn(() => Promise.resolve(json({
    status: 'completed', answer: '建议先确认客户的预算节点，再安排方案复盘。',
    citations: [{ ordinal: 1, label: 'business_data' }, { ordinal: 2, label: 'group_context' }],
    degradation_codes: [], draft_id: null,
    provider_response: 'never reach client', context: { raw_text: 'never reach client' },
  })))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.queryStage08Assistant({
    workspaceId: 'workspace-1', employeeId: 'employee-1', intent: 'mixed', query: '下一步怎么推进？', requestedAction: 'read_only', targetRecordId: null,
  }, 'query-key')).resolves.toEqual({
    status: 'completed', answer: '建议先确认客户的预算节点，再安排方案复盘。',
    citations: [{ ordinal: 1, label: 'business_data' }, { ordinal: 2, label: 'group_context' }], degradationCodes: [], draftId: null,
  })
  expect(fetchMock).toHaveBeenCalledWith('/api/stage08/assistant/query', expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ workspace_id: 'workspace-1', employee_id: 'employee-1', intent: 'mixed', query: '下一步怎么推进？', requested_action: 'read_only', idempotency_key: 'query-key' }),
    headers: expect.objectContaining({ 'idempotency-key': 'query-key' }),
  }))
})

test('rejects a response that tries to surface a private identifier in the answer', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(json({
    status: 'completed', answer: 'private 550e8400-e29b-41d4-a716-446655440000', citations: [], degradation_codes: [], draft_id: null,
  }))))

  await expect(api.queryStage08Assistant({
    workspaceId: 'workspace-1', employeeId: 'employee-1', intent: 'general_advice', query: '给一个建议', requestedAction: 'read_only', targetRecordId: null,
  }, 'query-key')).rejects.toThrow('Invalid Stage08 collaboration response')
})

test('rejects an invalid intent or record target before calling the collaboration transport', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.queryStage08Assistant({
    workspaceId: 'workspace-1', employeeId: 'employee-1', intent: 'unsafe' as never, query: '测试', requestedAction: 'read_only', targetRecordId: null,
  }, 'query-key')).rejects.toThrow('Invalid Stage08 collaboration request')
  await expect(api.queryStage08Assistant({
    workspaceId: 'workspace-1', employeeId: 'employee-1', intent: 'mixed', query: '测试', requestedAction: 'read_only', targetRecordId: 'record-1',
  }, 'query-key')).rejects.toThrow('Invalid Stage08 collaboration request')
  await expect(api.queryStage08Assistant({
    workspaceId: ' \n', employeeId: 'employee-1', intent: 'mixed', query: '测试', requestedAction: 'read_only', targetRecordId: null,
  }, 'query-key')).rejects.toThrow('Invalid Stage08 collaboration request')
  expect(fetchMock).not.toHaveBeenCalled()
})
