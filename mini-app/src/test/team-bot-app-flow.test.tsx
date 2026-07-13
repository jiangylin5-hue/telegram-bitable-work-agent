import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

afterEach(() => vi.unstubAllGlobals())

test('rereads the selected team view before one safe summary and hands off only to its Base', async () => {
  let selectedViewReads = 0
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'user-1', source: 'development_header' },
      workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({
      workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '运营 Base', source_type: 'blank' }], queue: [],
    }))
    if (path === '/mini-app/workspaces/workspace-1/team-bot-contacts?limit=50') return Promise.resolve(json({
      workspace_id: 'workspace-1',
      contacts: [{ id: 'employee-1', base_id: 'base-1', name: '团队助手', description: '汇总当前可访问视图。', available_intents: ['summarize'] }],
      next_cursor: null,
      has_more: false,
    }))
    if (path === '/mini-app/team-bots/employee-1/knowledge-contexts?limit=50') return Promise.resolve(json({
      employee: { id: 'employee-1', name: '团队助手', description: '汇总当前可访问视图。', base_id: 'base-1' },
      views: [{ id: 'view-1', name: '本周任务', view_type: 'grid' }],
      next_cursor: null,
      has_more: false,
    }))
    if (path === '/mini-app/team-bots/employee-1/knowledge-contexts/view-1') {
      selectedViewReads += 1
      return Promise.resolve(json({ id: 'view-1', name: '本周任务', view_type: 'grid', base_id: 'base-1' }))
    }
    if (path === '/mini-app/team-bots/employee-1/summaries' && init?.method === 'POST') return Promise.resolve(json({
      kind: 'summary',
      employee_id: 'employee-1',
      base_id: 'base-1',
      view_id: 'view-1',
      answer: '本周有两项任务等待确认。',
      citations: [{ record_id: 'record-1' }],
      knowledge_window_truncated: false,
      audit_event_id: 'audit-1',
    }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [] }))
    return Promise.resolve(json({ detail: 'unexpected ' + path }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '打开团队 Bot' }))
  fireEvent.click(await screen.findByRole('button', { name: '选择团队助手 团队助手' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/team-bots/employee-1/knowledge-contexts?limit=50',
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  ))
  fireEvent.click(await screen.findByRole('button', { name: '选择团队视图 本周任务' }))
  await waitFor(() => expect(selectedViewReads).toBe(1))

  fireEvent.change(screen.getByLabelText('补充说明'), { target: { value: '请关注阻塞项。' } })
  fireEvent.click(screen.getByRole('button', { name: '生成团队摘要' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/team-bots/employee-1/summaries',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ base_id: 'base-1', view_id: 'view-1', instruction: '请关注阻塞项。' }),
    }),
  ))
  expect(selectedViewReads).toBe(2)
  expect(screen.getByText('本周有两项任务等待确认。')).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: '打开 Base 继续处理' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/bases/base-1/tables', expect.anything()))
})

