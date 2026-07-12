import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('starts a workspace import from the authorized template hub', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/templates') return Promise.resolve(json({ templates: [] }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '模板与导入' }))
  fireEvent.click(await screen.findByRole('button', { name: '导入到新 Base' }))

  expect(await screen.findByRole('heading', { name: '导入数据表' })).toBeVisible()
})
