import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, buildBrowserHandoffUrl } from '../app/api'

const handoffPagePath = 'public/browser-handoff.html'
const originalDocument = document.documentElement.innerHTML

function handoffScript(html: string): string {
  const match = html.match(/<script>([\s\S]+)<\/script>/)
  if (!match) throw new Error('browser handoff script is missing')
  return match[1]
}

function runHandoffScript(html: string, onNavigate: (path: string) => void): void {
  document.documentElement.innerHTML = html
  ;(window as unknown as { __browserHandoffNavigate?: (path: string) => void }).__browserHandoffNavigate = onNavigate
  window.eval(handoffScript(html).replace("window.location.replace('/')", "window.__browserHandoffNavigate('/')"))
}

afterEach(() => {
  document.documentElement.innerHTML = originalDocument
  history.replaceState(null, '', '/')
  delete (window as unknown as { __browserHandoffNavigate?: unknown }).__browserHandoffNavigate
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('browser workspace handoff', () => {
  it('issues a browser handoff only through the protected in-memory API path and builds a same-origin fragment URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ticket: 'opaque-ticket', expires_at: '2026-07-23T08:00:00Z',
    }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    const handoff = await api.createBrowserHandoff()
    const url = buildBrowserHandoffUrl(handoff.ticket)

    expect(handoff).toEqual({ ticket: 'opaque-ticket', expiresAt: '2026-07-23T08:00:00Z' })
    expect(fetchMock).toHaveBeenCalledWith('/mini-app/browser-handoffs', expect.objectContaining({ method: 'POST' }))
    expect(url).toBe(`${window.location.origin}/browser-handoff.html#ticket=opaque-ticket`)
    expect(new URL(url).search).toBe('')
    expect(window.localStorage.getItem('browser-handoff-ticket')).toBeNull()
    expect(window.sessionStorage.getItem('browser-handoff-ticket')).toBeNull()
  })

  it('exchanges only the fragment ticket, clears it, and then navigates to the workspace root', async () => {
    const html = readFileSync(handoffPagePath, 'utf8')
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    const navigate = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    history.replaceState(null, '', '/browser-handoff.html#ticket=opaque-ticket')
    const replaceState = vi.spyOn(history, 'replaceState')

    runHandoffScript(html, navigate)

    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/'))
    expect(fetchMock).toHaveBeenCalledWith('/mini-app/browser-handoff-exchanges', expect.objectContaining({
      method: 'POST',
      credentials: 'same-origin',
      body: JSON.stringify({ ticket: 'opaque-ticket' }),
    }))
    expect(replaceState).toHaveBeenCalledExactlyOnceWith(null, '', '/browser-handoff.html')
    expect(replaceState.mock.invocationCallOrder[0]).toBeLessThan(fetchMock.mock.invocationCallOrder[0])
    expect(document.body.textContent).not.toContain('opaque-ticket')
  })

  it('clears the fragment before a failed exchange and shows only generic recovery copy', async () => {
    const html = readFileSync(handoffPagePath, 'utf8')
    const navigate = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)
    history.replaceState(null, '', '/browser-handoff.html#ticket=opaque-ticket')
    const replaceState = vi.spyOn(history, 'replaceState')

    runHandoffScript(html, navigate)

    await vi.waitFor(() => expect(document.querySelector<HTMLParagraphElement>('#handoff-error')?.hidden).toBe(false))
    expect(replaceState).toHaveBeenCalledExactlyOnceWith(null, '', '/browser-handoff.html')
    expect(replaceState.mock.invocationCallOrder[0]).toBeLessThan(fetchMock.mock.invocationCallOrder[0])
    expect(window.location.hash).toBe('')
    expect(html).toContain('<meta name="referrer" content="no-referrer">')
    expect(html).toContain('<meta http-equiv="Cache-Control" content="no-store">')
    expect(document.querySelector('#handoff-error')?.textContent).toBe('无法打开工作台，请返回 Telegram 后重试。')
    expect(document.body.textContent).not.toContain('401')
    expect(document.body.textContent).not.toContain('opaque-ticket')
    expect(navigate).not.toHaveBeenCalled()
  })

  it('disconnects a supported opener without reading data from it', () => {
    const html = readFileSync(handoffPagePath, 'utf8')

    expect(html).toContain('window.opener = null')
  })
})
