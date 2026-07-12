import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

afterEach(() => vi.unstubAllGlobals())

test('uses a selected-view reread before Home summary and opens its Base only by explicit action', async () => {
  let selectedViewReads = 0
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'user-1', source: 'development_header' },
      workspaces: [{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '运营 Base', source_type: 'blank' }], queue: [] }))
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') return Promise.resolve(json({
      workspace_id: 'workspace-1',
      contacts: [{ id: 'employee-1', base_id: 'base-1', name: '运营助理', description: '仅汇总授权视图。', status: 'active', available_intents: ['summarize'] }],
      next_cursor: null,
      has_more: false,
    }))
    if (path === '/mini-app/digital-employees/employee-1/assistant-context?limit=50') return Promise.resolve(json({
      employee: { id: 'employee-1', name: '运营助理', description: '仅汇总授权视图。', base_id: 'base-1' },
      views: [{ id: 'view-1', name: '待处理', view_type: 'grid' }],
      next_cursor: null,
      has_more: false,
    }))
    if (path === '/mini-app/digital-employees/employee-1/assistant-context/views/view-1') {
      selectedViewReads += 1
      return Promise.resolve(json({ id: 'view-1', name: '待处理', view_type: 'grid', base_id: 'base-1' }))
    }
    if (path === '/mini-app/digital-employees/employee-1/invocations' && init?.method === 'POST') return Promise.resolve(json({
      kind: 'summary', answer: '需要复核两项事项。', citations: [{ record_id: 'record-1' }],
    }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [] }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '智能汇总' }))
  fireEvent.click(await screen.findByRole('button', { name: '选择数字员工 运营助理' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/digital-employees/employee-1/assistant-context?limit=50',
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  ))
  fireEvent.click(await screen.findByRole('button', { name: '选择视图 待处理' }))
  await waitFor(() => expect(selectedViewReads).toBe(1))

  fireEvent.change(screen.getByLabelText('补充说明'), { target: { value: '请汇总' } })
  fireEvent.click(screen.getByRole('button', { name: '执行摘要' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/digital-employees/employee-1/invocations',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ intent: 'summarize', base_id: 'base-1', view_id: 'view-1', instruction: '请汇总' }),
    }),
  ))
  expect(selectedViewReads).toBe(2)
  expect(screen.getByText('需要复核两项事项。')).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: '打开 Base 继续处理' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/bases/base-1/tables', expect.anything()))
})
