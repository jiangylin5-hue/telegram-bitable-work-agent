import { afterEach, expect, test, vi } from 'vitest'

import { api, setTelegramInitData } from '../app/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function sseResponse(events: unknown[], contentType = 'text/event-stream; charset=utf-8') {
  const body = events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')
  return new Response(body, { status: 200, headers: { 'Content-Type': contentType } })
}

const streamRequest = {
  workspaceId: 'workspace-1',
  employeeId: 'employee-1',
  intent: 'mixed' as const,
  query: '  下一步怎么推进？  ',
  requestedAction: 'read_only' as const,
  targetRecordId: null,
}

const streamSafeView = {
  status: 'completed',
  answer: '建议先确认范围。',
  citations: [{ ordinal: 1, label: 'general_advice' }],
  degradation_codes: [],
  draft_id: null,
}

const skillCatalogResponse = {
  manifest_version: 'stage06-larksuite-skills-v1',
  default_selection: 'auto',
  skills: [
    {
      skill_id: 'platform-base',
      label: '查表问答',
      description: '基于已授权表格、视图与记录回答问题',
      enabled: true,
      disabled_reason: null,
      supported_intents: ['business_fact', 'mixed'],
      supported_actions: ['read_only'],
      confirmation_policy: 'read_only',
    },
    {
      skill_id: 'platform-draft-update',
      label: '生成跟进草稿',
      description: '将授权记录的更新建议写入待确认草稿',
      enabled: false,
      disabled_reason: 'write_scope_unavailable',
      supported_intents: ['mixed'],
      supported_actions: ['draft_update'],
      confirmation_policy: 'draft_required_for_write',
    },
  ],
}

afterEach(() => {
  vi.unstubAllGlobals()
  setTelegramInitData(null)
})

test('parses the complete strict server skill catalog and rejects unknown or unsafe fields', async () => {
  const fetchMock = vi.fn(() => Promise.resolve(json(skillCatalogResponse)))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.listStage08AssistantSkills('workspace-1', 'employee-1', null)).resolves.toEqual({
    manifestVersion: 'stage06-larksuite-skills-v1',
    defaultSelection: 'auto',
    skills: [
      {
        skillId: 'platform-base',
        label: '查表问答',
        description: '基于已授权表格、视图与记录回答问题',
        enabled: true,
        disabledReason: null,
        supportedIntents: ['business_fact', 'mixed'],
        supportedActions: ['read_only'],
        confirmationPolicy: 'read_only',
      },
      {
        skillId: 'platform-draft-update',
        label: '生成跟进草稿',
        description: '将授权记录的更新建议写入待确认草稿',
        enabled: false,
        disabledReason: 'write_scope_unavailable',
        supportedIntents: ['mixed'],
        supportedActions: ['draft_update'],
        confirmationPolicy: 'draft_required_for_write',
      },
    ],
  })

  fetchMock.mockResolvedValueOnce(json({
    ...skillCatalogResponse,
    skills: [{ ...skillCatalogResponse.skills[0], disabled_reason: 'private_policy_reason' }],
  }))
  await expect(api.listStage08AssistantSkills('workspace-1', 'employee-1', null)).rejects.toThrow('Invalid Stage08 skill catalog response')

  fetchMock.mockResolvedValueOnce(json({ ...skillCatalogResponse, internal_manifest: 'must not render' }))
  await expect(api.listStage08AssistantSkills('workspace-1', 'employee-1', null)).rejects.toThrow('Invalid Stage08 skill catalog response')
})

test('gets the scoped skill catalog with optional record and preserves protected identity headers', async () => {
  const fetchMock = vi.fn(() => Promise.resolve(json(skillCatalogResponse)))
  vi.stubGlobal('fetch', fetchMock)

  await api.listStage08AssistantSkills('workspace-1', 'employee-1', 'record-1', {
    headers: { 'X-Telegram-Init-Data': 'caller-signed-identity', 'X-Trace-ID': 'trace-1' },
  })

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/stage08/assistant/skills?workspace_id=workspace-1&employee_id=employee-1&target_record_id=record-1',
    expect.objectContaining({
      headers: expect.objectContaining({ 'X-Telegram-Init-Data': 'caller-signed-identity', 'X-Trace-ID': 'trace-1' }),
    }),
  )
})

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
    body: JSON.stringify({ workspace_id: 'workspace-1', employee_id: 'employee-1', intent: 'mixed', query: '下一步怎么推进？', requested_action: 'read_only', idempotency_key: 'query-key', skill_id: null }),
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

test('streams the normalized Stage08 query with identity and idempotency headers', async () => {
  setTelegramInitData('telegram-signed-identity')
  const fetchMock = vi.fn(() => Promise.resolve(sseResponse([
    { event: 'status', sequence: 1, request_id: 'req-1', phase: 'authorizing' },
    { event: 'answer_delta', sequence: 2, request_id: 'req-1', text: '建议先确认范围。' },
    { event: 'result', sequence: 3, request_id: 'req-1', safe_view: streamSafeView },
    { event: 'done', sequence: 4, request_id: 'req-1' },
  ])))
  vi.stubGlobal('fetch', fetchMock)
  const received: string[] = []

  await expect(api.queryStage08AssistantStream(
    streamRequest,
    'idem-1',
    (event) => received.push(event.event),
  )).resolves.toEqual({
    status: 'completed',
    answer: '建议先确认范围。',
    citations: [{ ordinal: 1, label: 'general_advice' }],
    degradationCodes: [],
    draftId: null,
  })

  expect(received).toEqual(['status', 'answer_delta', 'result', 'done'])
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/stage08/assistant/query-stream',
    expect.objectContaining({
      method: 'POST',
      credentials: 'same-origin',
      headers: expect.objectContaining({
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        'Idempotency-Key': 'idem-1',
        'X-Telegram-Init-Data': 'telegram-signed-identity',
      }),
      body: JSON.stringify({
        workspace_id: 'workspace-1',
        employee_id: 'employee-1',
        intent: 'mixed',
        query: '下一步怎么推进？',
        requested_action: 'read_only',
        idempotency_key: 'idem-1',
        skill_id: null,
      }),
    }),
  )
})

test('preserves a caller identity header when no global Telegram identity is set', async () => {
  const fetchMock = vi.fn((_input: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(sseResponse([
    { event: 'result', sequence: 1, request_id: 'req-1', safe_view: { ...streamSafeView, answer: null } },
    { event: 'done', sequence: 2, request_id: 'req-1' },
  ])))
  vi.stubGlobal('fetch', fetchMock)

  await api.queryStage08AssistantStream(
    streamRequest,
    'idem-1',
    () => undefined,
    { headers: { 'X-Telegram-Init-Data': 'caller-signed-identity', 'X-Trace-ID': 'trace-1' } },
  )

  const requestInit = fetchMock.mock.calls[0][1] as RequestInit
  const headers = new Headers(requestInit.headers)
  expect(headers.get('X-Telegram-Init-Data')).toBe('caller-signed-identity')
  expect(headers.get('X-Trace-ID')).toBe('trace-1')
})

test('global Telegram identity overrides a caller-supplied identity header', async () => {
  setTelegramInitData('global-signed-identity')
  const fetchMock = vi.fn((_input: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(sseResponse([
    { event: 'result', sequence: 1, request_id: 'req-1', safe_view: { ...streamSafeView, answer: null } },
    { event: 'done', sequence: 2, request_id: 'req-1' },
  ])))
  vi.stubGlobal('fetch', fetchMock)

  await api.queryStage08AssistantStream(
    streamRequest,
    'idem-1',
    () => undefined,
    { headers: { 'X-Telegram-Init-Data': 'caller-spoof' } },
  )

  const requestInit = fetchMock.mock.calls[0][1] as RequestInit
  expect(new Headers(requestInit.headers).get('X-Telegram-Init-Data')).toBe('global-signed-identity')
})

test('rejects a successful non-SSE response without exposing its raw body', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
    'private provider stack trace',
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  ))))

  await expect(api.queryStage08AssistantStream(
    streamRequest,
    'idem-1',
    () => undefined,
  )).rejects.toThrow('Invalid assistant stream response')
})

test('normalizes AbortError to the stable stopped-viewing outcome', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new DOMException(
    'internal obsolete request detail',
    'AbortError',
  ))))

  const outcome = api.queryStage08AssistantStream(
    streamRequest,
    'idem-1',
    () => undefined,
    { signal: new AbortController().signal },
  )

  await expect(outcome).rejects.toMatchObject({
    name: 'AbortError',
    message: 'Stopped viewing',
  })
})
