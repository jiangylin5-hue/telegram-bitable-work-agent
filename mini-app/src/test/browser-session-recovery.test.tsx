import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

const workspace = {
  id: 'workspace-1',
  name: '验收工作区',
  slug: 'acceptance',
  role: 'owner',
  capabilities: {
    can_read_bases: true,
    can_manage_workspace: true,
    can_manage_schema: true,
    can_review_drafts: true,
  },
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('guides an expired browser workspace session back to Telegram', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    expect(String(input)).toBe('/mini-app/bootstrap')
    return Promise.resolve(new Response(JSON.stringify({ detail: 'browser_session_invalid' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    }))
  }))

  render(<App />)

  expect(await screen.findByText('当前浏览器工作台会话已失效或无访问权限，请返回 Telegram 重新打开工作区。')).toBeInTheDocument()
  expect(screen.getByRole('main', { name: '无工作区访问权限' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '重新加载工作区' })).not.toBeInTheDocument()
})

test('retries a bootstrap network failure into the authorized workspace Home', async () => {
  let bootstrapCalls = 0
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') {
      bootstrapCalls += 1
      if (bootstrapCalls === 1) return Promise.reject(new TypeError('network unavailable'))
      return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'development_header' }, workspaces: [workspace] }))
    }
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  const retry = await screen.findByRole('button', { name: '重新加载工作区' })
  fireEvent.click(retry)

  expect(await screen.findByRole('main', { name: '工作区首页' })).toBeInTheDocument()
  expect(bootstrapCalls).toBe(2)
})

test('reloads the same authorized Home after a non-auth Home failure', async () => {
  let homeCalls = 0
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'development_header' }, workspaces: [workspace] }))
    if (path === '/workspaces/workspace-1/home') {
      homeCalls += 1
      if (homeCalls === 1) return Promise.reject(new TypeError('network unavailable'))
      return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    }
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)

  const retry = await screen.findByRole('button', { name: '重新加载工作区' })
  fireEvent.click(retry)

  expect(await screen.findByRole('main', { name: '工作区首页' })).toBeInTheDocument()
  expect(homeCalls).toBe(2)
})
