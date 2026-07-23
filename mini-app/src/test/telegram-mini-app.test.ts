import { createElement } from 'react'
import { render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, setTelegramInitData } from '../app/api'
import { App } from '../app/App'
import { exitTelegramMiniAppFullscreen, prepareTelegramMiniAppViewport, readTelegramMiniAppFullscreenState, readTelegramMiniAppLaunch, requestTelegramMiniAppFullscreen, subscribeTelegramMiniAppFullscreen } from '../app/telegram-mini-app'

type TelegramWindow = Window & {
  Telegram?: {
    WebApp?: {
      initData?: string
      initDataUnsafe?: { start_param?: unknown; user?: { id: unknown } }
      ready?: () => void
      expand?: () => void
      version?: string
      isFullscreen?: boolean
      isVersionAtLeast?: (version: string) => boolean
      requestFullscreen?: () => void
      exitFullscreen?: () => void
      onEvent?: (event: string, listener: (payload?: unknown) => void) => void
      offEvent?: (event: string, listener: (payload?: unknown) => void) => void
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

  it.each(['ready', 'expand'] as const)('fails closed when Telegram %s throws synchronously', (method) => {
    const webApp = { ready: vi.fn(), expand: vi.fn() }
    webApp[method].mockImplementation(() => { throw new Error('host failure') })
    ;(window as TelegramWindow).Telegram = { WebApp: webApp }

    expect(prepareTelegramMiniAppViewport()).toBe(false)
  })

  it('fails closed when the Telegram WebApp getter throws during App mount', () => {
    Object.defineProperty(window, 'Telegram', {
      configurable: true,
      get: () => { throw new Error('host getter failure') },
    })
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))

    expect(() => render(createElement(App))).not.toThrow()
  })

  it('does not request Telegram fullscreen when the application mounts', () => {
    const ready = vi.fn()
    const expand = vi.fn()
    const requestFullscreen = vi.fn()
    ;(window as TelegramWindow).Telegram = {
      WebApp: { ready, expand, version: '8.0', requestFullscreen },
    }
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))

    render(createElement(App))

    expect(ready).toHaveBeenCalledTimes(1)
    expect(expand).toHaveBeenCalledTimes(1)
    expect(requestFullscreen).not.toHaveBeenCalled()
  })

  it('requests fullscreen exactly once on a version-8 Telegram runtime', () => {
    const requestFullscreen = vi.fn()
    ;(window as TelegramWindow).Telegram = {
      WebApp: { version: '8.0', requestFullscreen },
    }

    expect(requestTelegramMiniAppFullscreen()).toBe('requested')
    expect(requestFullscreen).toHaveBeenCalledTimes(1)
  })

  it('returns unsupported when Telegram fullscreen request throws synchronously', () => {
    const requestFullscreen = vi.fn(() => { throw new Error('host failure') })
    ;(window as TelegramWindow).Telegram = {
      WebApp: { version: '8.0', requestFullscreen },
    }

    expect(requestTelegramMiniAppFullscreen()).toBe('unsupported')
    expect(requestFullscreen).toHaveBeenCalledTimes(1)
  })

  it('exits fullscreen exactly once on a capable fullscreen Telegram runtime', () => {
    const exitFullscreen = vi.fn()
    ;(window as TelegramWindow).Telegram = {
      WebApp: { version: '8.0', isFullscreen: true, exitFullscreen },
    }

    expect(exitTelegramMiniAppFullscreen()).toBe('requested')
    expect(exitFullscreen).toHaveBeenCalledTimes(1)
  })

  it('returns unsupported when Telegram fullscreen exit throws synchronously', () => {
    const exitFullscreen = vi.fn(() => { throw new Error('host failure') })
    ;(window as TelegramWindow).Telegram = {
      WebApp: { version: '8.0', isFullscreen: true, exitFullscreen },
    }

    expect(exitTelegramMiniAppFullscreen()).toBe('unsupported')
    expect(exitFullscreen).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['request', () => requestTelegramMiniAppFullscreen()],
    ['exit', () => exitTelegramMiniAppFullscreen()],
  ])('returns unsupported when Telegram fullscreen version check throws for %s', (_operation, invoke) => {
    const isVersionAtLeast = vi.fn(() => { throw new Error('host version failure') })
    ;(window as TelegramWindow).Telegram = {
      WebApp: { isFullscreen: true, isVersionAtLeast, requestFullscreen: vi.fn(), exitFullscreen: vi.fn() },
    }

    expect(invoke()).toBe('unsupported')
    expect(isVersionAtLeast).toHaveBeenCalledWith('8.0')
  })

  it('does not exit when Telegram is already windowed', () => {
    const exitFullscreen = vi.fn()
    ;(window as TelegramWindow).Telegram = {
      WebApp: { version: '8.0', isFullscreen: false, exitFullscreen },
    }

    expect(exitTelegramMiniAppFullscreen()).toBe('already_windowed')
    expect(exitFullscreen).not.toHaveBeenCalled()
  })

  it('returns a fail-closed fullscreen state when Telegram isFullscreen throws', () => {
    const webApp = {} as TelegramWindow['Telegram'] extends { WebApp?: infer T } ? T : never
    Object.defineProperty(webApp, 'isFullscreen', {
      configurable: true,
      get: () => { throw new Error('host state failure') },
    })
    ;(window as TelegramWindow).Telegram = { WebApp: webApp }

    expect(readTelegramMiniAppFullscreenState()).toEqual({ kind: 'fullscreenFailed', error: 'UNSUPPORTED' })
  })

  it('subscribes to fullscreen events and removes the same listeners on cleanup', () => {
    const onEvent = vi.fn()
    const offEvent = vi.fn()
    ;(window as TelegramWindow).Telegram = {
      WebApp: { onEvent, offEvent },
    }

    const unsubscribe = subscribeTelegramMiniAppFullscreen(vi.fn())

    expect(onEvent).toHaveBeenCalledTimes(2)
    unsubscribe()
    expect(offEvent).toHaveBeenCalledTimes(2)
    expect(offEvent.mock.calls.map(([event, listener]) => [event, typeof listener])).toEqual([
      ['fullscreen_changed', 'function'],
      ['fullscreen_failed', 'function'],
    ])
  })

  it('cleans up a partially registered fullscreen listener when Telegram onEvent throws', () => {
    const onEvent = vi.fn()
      .mockImplementationOnce(() => undefined)
      .mockImplementationOnce(() => { throw new Error('host event failure') })
    const offEvent = vi.fn()
    ;(window as TelegramWindow).Telegram = { WebApp: { onEvent, offEvent } }

    expect(subscribeTelegramMiniAppFullscreen(vi.fn())).not.toThrow()
    expect(offEvent).toHaveBeenCalledExactlyOnceWith('fullscreen_changed', expect.any(Function))
  })

  it('retries partial fullscreen cleanup when its first Telegram offEvent call throws', () => {
    const onEvent = vi.fn()
      .mockImplementationOnce(() => undefined)
      .mockImplementationOnce(() => { throw new Error('host event failure') })
    const offEvent = vi.fn()
      .mockImplementationOnce(() => { throw new Error('host cleanup failure') })
      .mockImplementationOnce(() => undefined)
    ;(window as TelegramWindow).Telegram = { WebApp: { onEvent, offEvent } }

    const unsubscribe = subscribeTelegramMiniAppFullscreen(vi.fn())

    expect(offEvent).toHaveBeenCalledExactlyOnceWith('fullscreen_changed', expect.any(Function))
    expect(unsubscribe).not.toThrow()
    expect(offEvent).toHaveBeenCalledTimes(2)
    expect(offEvent.mock.calls.map(([event]) => event)).toEqual(['fullscreen_changed', 'fullscreen_changed'])
    unsubscribe()
    expect(offEvent).toHaveBeenCalledTimes(2)
  })

  it('does not throw when Telegram offEvent throws during fullscreen cleanup', () => {
    const onEvent = vi.fn()
    const offEvent = vi.fn(() => { throw new Error('host cleanup failure') })
    ;(window as TelegramWindow).Telegram = { WebApp: { onEvent, offEvent } }

    const unsubscribe = subscribeTelegramMiniAppFullscreen(vi.fn())
    expect(unsubscribe).not.toThrow()
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
