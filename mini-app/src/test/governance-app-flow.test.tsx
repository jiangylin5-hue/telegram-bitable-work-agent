import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('opens the governance workbench from the server-hinted entry and reads a selected Base audit page', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'header' },
      workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({
      workspace_id: 'workspace-1',
      recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'manual' }],
      queue: [],
    }))
    if (path === '/mini-app/workspaces/workspace-1/governance/members?limit=50') return Promise.resolve(json({
      workspace_id: 'workspace-1',
      members: [{ id: 'member-1', user_id: 'owner-1', role: 'owner', status: 'active', permission_snapshot: { hidden: true } }],
      next_cursor: null, has_more: false,
    }))
    if (path === '/mini-app/bases/base-1/governance/audit-events?limit=50') return Promise.resolve(json({
      base_id: 'base-1',
      events: [{ id: 'audit-1', occurred_at: '2026-07-12T00:00:00Z', actor_type: 'user', event_type: 'stage06.record_created', entity_type: 'record', trace_id: 'trace-secret' }],
      next_cursor: null, has_more: false,
    }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  const desktopTrigger = await screen.findByRole('button', { name: '成员与权限：管理成员与权限' })
  const mobileMore = screen.getByRole('button', { name: '更多：打开其他工作台' })
  fireEvent.click(mobileMore)
  expect(within(screen.getByLabelText('更多工作台')).getByRole('button', { name: '成员与权限：管理成员与权限' })).toBeInTheDocument()
  fireEvent.click(desktopTrigger)
  expect(await screen.findByRole('dialog', { name: '治理工作台' })).toBeVisible()
  expect(screen.getByText('owner-1')).toBeVisible()
  expect(screen.queryByText('trace-secret')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('选择 Base'), { target: { value: 'base-1' } })
  expect(await screen.findByText('已记录系统操作')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '关闭治理工作台' }))
  expect(desktopTrigger).toHaveFocus()
})
