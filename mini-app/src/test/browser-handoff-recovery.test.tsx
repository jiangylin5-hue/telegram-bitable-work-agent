import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'
import { setTelegramInitData } from '../app/api'

type TelegramWindow = Window & {
  Telegram?: {
    WebApp?: {
      initData?: string
      version?: string
      ready?: () => void
      expand?: () => void
    }
  }
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => {
  delete (window as TelegramWindow).Telegram
  setTelegramInitData(null)
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

test('restores the current Mini App identity before requesting a browser handoff', async () => {
  ;(window as TelegramWindow).Telegram = {
    WebApp: { initData: 'raw-signed-init-data', version: '7.0' },
  }
  const popup = {
    closed: false,
    close: vi.fn(),
    location: { replace: vi.fn() },
  } as unknown as Window
  vi.spyOn(window, 'open').mockReturnValue(popup)
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'member-1', source: 'telegram_binding' },
      workspaces: [{ id: 'workspace-1', name: '我的协作工作区', slug: 'workspace', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/mini-app/browser-handoffs') return Promise.resolve(json({ ticket: 'opaque-ticket', expires_at: '2026-07-24T12:00:00Z' }, 201))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  await screen.findByRole('main', { name: '工作区首页' })

  setTelegramInitData(null)
  fireEvent.click(screen.getByRole('button', { name: '在浏览器打开完整工作台' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/mini-app/browser-handoffs', expect.anything()))
  const [, request] = fetchMock.mock.calls.find(([input]) => String(input) === '/mini-app/browser-handoffs') as unknown as [RequestInfo | URL, RequestInit | undefined]
  expect(new Headers(request?.headers).get('X-Telegram-Init-Data')).toBe('raw-signed-init-data')
  await waitFor(() => expect(popup.location.replace).toHaveBeenCalledWith(`${window.location.origin}/browser-handoff.html#ticket=opaque-ticket`))
})
