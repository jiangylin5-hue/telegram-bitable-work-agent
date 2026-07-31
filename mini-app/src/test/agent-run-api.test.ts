import { afterEach, expect, test, vi } from 'vitest'

import { api, setTelegramInitData } from '../app/api'


const runId = '11111111-1111-4111-8111-111111111111'
const eventId = (sequence: number) => `22222222-2222-4222-8222-${String(sequence).padStart(12, '0')}`
const safeView = {
  status: 'completed',
  answer: '建议继续跟进。',
  citations: [{ ordinal: 1, label: 'business_data' }],
  degradation_codes: [],
  draft_id: null,
  skill: {
    skill_id: 'platform-tabular-analysis',
    label: '汇总分析',
    manifest_version: 'stage06-larksuite-skills-v1',
    selection_mode: 'explicit',
  },
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function sse(events: Record<string, unknown>[]) {
  const body = events.map((event) => `id: ${event.sequence}\nevent: ${event.event}\ndata: ${JSON.stringify(event)}\n\n`).join('')
  return new Response(body, { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } })
}

afterEach(() => {
  vi.unstubAllGlobals()
  setTelegramInitData(null)
})

test('creates a durable run, consumes safe SSE, and adapts it to the existing conversation UI', async () => {
  setTelegramInitData('signed-identity')
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(json({ run_id: runId, status: 'completed', replayed: false }, 202))
    .mockResolvedValueOnce(sse([
      { run_id: runId, event_id: eventId(1), sequence: 1, event: 'status', phase: 'accepted', message: '已受理' },
      { run_id: runId, event_id: eventId(2), sequence: 2, event: 'status', phase: 'queued', message: '已派发' },
      { run_id: runId, event_id: eventId(3), sequence: 3, event: 'status', phase: 'running', message: '正在分析' },
      { run_id: runId, event_id: eventId(4), sequence: 4, event: 'artifact_ready', artifact_ref: '33333333-3333-4333-8333-333333333333', label: 'Safe analysis result' },
      { run_id: runId, event_id: eventId(5), sequence: 5, event: 'result', artifact_ref: '33333333-3333-4333-8333-333333333333', safe_view: safeView },
      { run_id: runId, event_id: eventId(6), sequence: 6, event: 'done', status: 'completed' },
    ]))
  vi.stubGlobal('fetch', fetchMock)
  const events: string[] = []

  await expect(api.queryStage10AssistantRunStream({
    workspaceId: 'workspace-1',
    employeeId: 'employee-1',
    intent: 'business_fact',
    query: '客户情况如何？',
    requestedAction: 'read_only',
    targetRecordId: null,
    skillId: 'platform-tabular-analysis',
  }, 'idem-1', (event) => events.push(event.event))).resolves.toMatchObject({
    answer: '建议继续跟进。',
    skill: { skillId: 'platform-tabular-analysis' },
  })

  expect(events).toEqual(['status', 'status', 'status', 'answer_delta', 'result', 'done'])
  expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/stage10/agent-runs', expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({
      workspace_id: 'workspace-1', employee_id: 'employee-1', intent: 'business_fact', query: '客户情况如何？', requested_action: 'read_only', target_record_id: null, idempotency_key: 'idem-1', skill_id: 'platform-tabular-analysis',
    }),
  }))
  expect(fetchMock).toHaveBeenNthCalledWith(2, `/api/stage10/agent-runs/${runId}/events`, expect.objectContaining({
    method: 'GET',
    headers: expect.objectContaining({ accept: 'text/event-stream', 'x-telegram-init-data': 'signed-identity' }),
  }))
})

test('creates a blind auto action run and loads only safe confirmation data', async () => {
  const slotId = '44444444-4444-4444-8444-444444444444'
  const objectiveId = '55555555-5555-4555-8555-555555555555'
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(json({ run_id: runId, status: 'waiting_approval', replayed: false }, 202))
    .mockResolvedValueOnce(json({ run_id: runId, objectives: [{ objective_id: objectiveId, objective_key: 'obj-01', kind: 'action', required: true, status: 'proposed', safe_summary: '等待确认', error_code: null }] }))
    .mockResolvedValueOnce(json({ run_id: runId, actions: [{ slot_id: slotId, objective_id: objectiveId, slot_key: 'act-01', action_kind: 'task.create', status: 'pending_confirmation', proposal_version: 4, record_version: null, safe_summary: '创建任务草稿', editable_fields: [{ field_id: '66666666-6666-4666-8666-666666666666', field_key: 'title', label: '标题', field_type: 'text', required: true }], proposed_values: { title: '回滚评审' }, confirmation_required: true, execution_ticket_id: '77777777-7777-4777-8777-777777777777', resource_id: '88888888-8888-4888-8888-888888888888' }] }))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.queryStage12ActionRun({
    workspaceId: 'workspace-1', employeeId: 'employee-1', intent: 'controlled_action', query: '创建回滚评审任务', requestedAction: 'auto', targetRecordId: null,
  }, 'idem-1')).resolves.toMatchObject({
    runId,
    status: 'waiting_approval',
    actions: [{ slotId, status: 'pending_confirmation', proposedValues: { title: '回滚评审' } }],
  })
  expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/stage10/agent-runs', expect.objectContaining({ body: expect.stringContaining('"requested_action":"auto"') }))
})

test('falls back to Stage08 only when the workspace is outside the Stage10 allowlist', async () => {
  const stage08SafeView = {
    status: 'completed',
    answer: '已通过兼容路径完成。',
    citations: [],
    degradation_codes: [],
    draft_id: null,
    skill: safeView.skill,
  }
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(json({ detail: { code: 'agent_event_runtime_disabled' } }, 404))
    .mockResolvedValueOnce(new Response([
      { event: 'answer_delta', sequence: 1, request_id: 'request-1', text: '已通过兼容路径完成。' },
      { event: 'result', sequence: 2, request_id: 'request-1', safe_view: stage08SafeView },
      { event: 'done', sequence: 3, request_id: 'request-1' },
    ].map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''), {
      headers: { 'Content-Type': 'text/event-stream; charset=utf-8' },
    }))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.queryStage10AssistantWithFallback({
    workspaceId: 'workspace-1', employeeId: 'employee-1', intent: 'business_fact', query: '客户情况？', requestedAction: 'read_only', targetRecordId: null,
  }, 'idem-fallback', () => undefined)).resolves.toMatchObject({
    answer: '已通过兼容路径完成。',
  })

  expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/stage08/assistant/query-stream', expect.objectContaining({ method: 'POST' }))
})
