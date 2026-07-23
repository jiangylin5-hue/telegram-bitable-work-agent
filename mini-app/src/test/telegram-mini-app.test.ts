import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, setTelegramInitData } from '../app/api'
import { prepareTelegramMiniAppViewport, readTelegramMiniAppLaunch } from '../app/telegram-mini-app'

type TelegramWindow = Window & {
  Telegram?: {
    WebApp?: {
      initData?: string
      initDataUnsafe?: { start_param?: unknown; user?: { id: unknown } }
      ready?: () => void
      expand?: () => void
    }
  }
}

afterEach(() => {
  delete (window as TelegramWindow).Telegram
  setTelegramInitData(null)
  vi.unstubAllGlobals()
})

describe('Telegram Mini App runtime adapter', () => {
  it('expands the Telegram host viewport without treating host data as identity', () => {
    const ready = vi.fn()
    const expand = vi.fn()
    ;(window as TelegramWindow).Telegram = { WebApp: { ready, expand } }

    expect(prepareTelegramMiniAppViewport()).toBe(true)
    expect(ready).toHaveBeenCalledTimes(1)
    expect(expand).toHaveBeenCalledTimes(1)
  })

  it('does nothing when the page is opened outside Telegram', () => {
    expect(prepareTelegramMiniAppViewport()).toBe(false)
  })

  it('reads only raw initData and the untrusted start transport hint from memory', () => {
    ;(window as TelegramWindow).Telegram = {
      WebApp: {
        initData: 'raw-signed-init-data',
        initDataUnsafe: { start_param: 'opaqueToken_123456', user: { id: 123 } },
      },
    }

    expect(readTelegramMiniAppLaunch()).toEqual({
      initData: 'raw-signed-init-data',
      startParam: 'opaqueToken_123456',
    })
    expect(window.localStorage.getItem('telegram-init-data')).toBeNull()
    expect(window.sessionStorage.getItem('telegram-init-data')).toBeNull()
  })

  it('returns null without the Telegram runtime or a raw launch proof', () => {
    expect(readTelegramMiniAppLaunch()).toBeNull()
    ;(window as TelegramWindow).Telegram = { WebApp: { initData: '   ' } }
    expect(readTelegramMiniAppLaunch()).toBeNull()
  })

  it('attaches raw initData only as an in-memory request header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      identity: { user_id: 'member-1', source: 'telegram_binding' }, workspaces: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    setTelegramInitData('raw-signed-init-data')

    await api.bootstrap()

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(new Headers(init.headers).get('X-Telegram-Init-Data')).toBe('raw-signed-init-data')
    expect(JSON.stringify(init)).not.toContain('initDataUnsafe')
  })

  it('accepts only a closed resolver response and never exposes raw launch fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      outcome: 'resolved',
      destination: { kind: 'record', workspace_id: 'workspace-1', base_id: 'base-1', table_id: 'table-1', record_id: 'record-1' },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.resolveTelegramDeepLink('opaqueToken_123456')

    expect(result).toEqual({
      outcome: 'resolved',
      destination: { kind: 'record', workspaceId: 'workspace-1', baseId: 'base-1', tableId: 'table-1', recordId: 'record-1' },
    })
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.body).toBe(JSON.stringify({ start_param: 'opaqueToken_123456' }))
  })
})
