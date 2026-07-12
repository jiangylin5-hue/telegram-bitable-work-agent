import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('opens governance write only from the existing server-hinted governance surface', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'header' },
      workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'manual' }], queue: [] }))
    if (path === '/mini-app/workspaces/workspace-1/governance/members?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', members: [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/workspaces/workspace-1/governance/member-editor?limit=50') return Promise.resolve(json({
      workspace_id: 'workspace-1',
      members: [{ id: 'member-1', user_id: 'operator-1', role: 'operator', status: 'active', version: 1, assignable_roles: ['builder', 'operator', 'viewer'] }],
      next_cursor: null, has_more: false,
    }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '打开治理工作台' }))
  const settingsTrigger = await screen.findByRole('button', { name: '打开权限设置' })
  fireEvent.click(settingsTrigger)

  expect(await screen.findByRole('dialog', { name: '权限设置' })).toBeVisible()
  expect(screen.getByLabelText('成员 operator-1 的角色')).toHaveValue('operator')
  fireEvent.click(screen.getByRole('button', { name: '关闭权限设置' }))
  await waitFor(() => expect(settingsTrigger).toHaveFocus())
})

test('keeps the workspace open when a selected governance-write Base is no longer found', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'header' },
      workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'manual' }], queue: [] }))
    if (path === '/mini-app/workspaces/workspace-1/governance/members?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', members: [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/workspaces/workspace-1/governance/member-editor?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', members: [], next_cursor: null, has_more: false }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ detail: 'unexpected raw table detail' }, 404))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [] }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '打开治理工作台' }))
  fireEvent.click(await screen.findByRole('button', { name: '打开权限设置' }))
  const dialog = await screen.findByRole('dialog', { name: '权限设置' })
  fireEvent.change(within(dialog).getByLabelText('选择 Base'), { target: { value: 'base-1' } })

  await waitFor(() => expect(screen.queryByRole('main', { name: '无工作区访问权限' })).not.toBeInTheDocument())
  expect(screen.getByRole('dialog', { name: '权限设置' })).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('所选 Base 已不可用，请重新选择。')
  expect(screen.queryByText('unexpected raw table detail')).not.toBeInTheDocument()
})

test.each([401, 403])('fails closed to the workspace boundary when governance-write member context returns %s', async (status) => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'header' },
      workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'manual' }], queue: [] }))
    if (path === '/mini-app/workspaces/workspace-1/governance/members?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', members: [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/workspaces/workspace-1/governance/member-editor?limit=50') return Promise.resolve(json({ detail: 'expired identity' }, status))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '打开治理工作台' }))
  fireEvent.click(await screen.findByRole('button', { name: '打开权限设置' }))

  expect(await screen.findByRole('main', { name: '无工作区访问权限' })).toBeVisible()
  expect(screen.queryByRole('dialog', { name: '权限设置' })).not.toBeInTheDocument()
  expect(screen.queryByText('expired identity')).not.toBeInTheDocument()
})
