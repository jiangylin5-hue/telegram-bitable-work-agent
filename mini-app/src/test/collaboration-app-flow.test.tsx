import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

const sse = (events: unknown[]) => new Response(
  events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
  { headers: { 'Content-Type': 'text/event-stream' } },
)

afterEach(() => vi.unstubAllGlobals())

test('opens Stage08 collaboration from Home and streams only the safe query contract', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'user-1', source: 'development_header' },
      workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') return Promise.resolve(json({
      workspace_id: 'workspace-1', contacts: [{ id: 'employee-1', base_id: 'base-1', name: '客户协作员工', description: '授权协作', status: 'active', available_intents: ['summarize', 'draft_update'] }], next_cursor: null, has_more: false,
    }))
    if (path === '/api/stage08/assistant/query-stream' && init?.method === 'POST') return Promise.resolve(sse([
      { event: 'status', sequence: 1, request_id: 'request-1', phase: 'authorizing' },
      { event: 'private_tool_trace', provider_response: 'must not render' },
      { event: 'answer_delta', sequence: 2, request_id: 'request-1', text: '先确认预算节点。' },
      {
        event: 'result',
        sequence: 3,
        request_id: 'request-1',
        safe_view: {
          status: 'completed',
          answer: '先确认预算节点。',
          citations: [{ ordinal: 1, label: 'group_context' }],
          degradation_codes: [],
          draft_id: null,
        },
      },
      { event: 'status', sequence: 4, request_id: 'request-1', phase: 'completed' },
      { event: 'done', sequence: 5, request_id: 'request-1' },
    ]))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  const dock = await screen.findByRole('complementary', { name: '个人助理与团队 Bot' })
  fireEvent.click(within(dock).getByRole('button', { name: 'AI 对话' }))
  expect(await screen.findByRole('dialog', { name: 'AI 对话' })).toBeVisible()
  fireEvent.change(screen.getByLabelText('协作问题'), { target: { value: '客户下一步怎么推进？' } })
  fireEvent.click(screen.getByRole('button', { name: '发送问题' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/stage08/assistant/query-stream', expect.objectContaining({
    method: 'POST',
    headers: expect.objectContaining({ Accept: 'text/event-stream' }),
    signal: expect.any(AbortSignal),
  })))
  const invocation = fetchMock.mock.calls.find(([input]) => String(input) === '/api/stage08/assistant/query-stream')
  expect(invocation).toBeDefined()
  const body = JSON.parse(String(invocation?.[1]?.body))
  expect(body).toMatchObject({ workspace_id: 'workspace-1', employee_id: 'employee-1', intent: 'mixed', query: '客户下一步怎么推进？', requested_action: 'read_only' })
  expect(body).not.toHaveProperty('target_record_id')
  expect(await screen.findByText('先确认预算节点。')).toBeVisible()
  expect(screen.getByText('已使用受权群聊上下文作为证据')).toBeVisible()
  expect(screen.queryByText('must not render')).not.toBeInTheDocument()
})
