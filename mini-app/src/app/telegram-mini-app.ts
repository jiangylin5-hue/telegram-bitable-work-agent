export type TelegramMiniAppLaunch = {
  initData: string
  startParam: string | null
}

export type TelegramFullscreenState =
  | { kind: 'fullscreenRequested' }
  | { kind: 'fullscreen' }
  | { kind: 'windowed' }
  | { kind: 'fullscreenUnsupported' }
  | { kind: 'fullscreenFailed'; error: string }

type TelegramFullscreenEvent = 'fullscreen_changed' | 'fullscreen_failed'
type TelegramFullscreenListener = (payload?: unknown) => void

type TelegramWebApp = {
  initData?: string
  initDataUnsafe?: {
    start_param?: unknown
    [key: string]: unknown
  }
  ready?: () => void
  expand?: () => void
  version?: string
  isFullscreen?: boolean
  isVersionAtLeast?: (version: string) => boolean
  requestFullscreen?: () => void
  exitFullscreen?: () => void
  openLink?: (url: string) => void
  onEvent?: (event: TelegramFullscreenEvent, listener: TelegramFullscreenListener) => void
  offEvent?: (event: TelegramFullscreenEvent, listener: TelegramFullscreenListener) => void
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp }
  }
}

/**
 * Ask the Telegram host to show the available Mini App viewport.
 * This deliberately has no authentication role: only raw initData reaches
 * the API and the server verifies it before resolving an identity.
 */
export function prepareTelegramMiniAppViewport(): boolean {
  try {
    if (typeof window === 'undefined') return false
    const webApp = window.Telegram?.WebApp
    if (!webApp) return false
    webApp.ready?.()
    webApp.expand?.()
    return true
  } catch {
    return false
  }
}

function isVersionAtLeast(webApp: TelegramWebApp, required: string): boolean {
  if (webApp.isVersionAtLeast) return webApp.isVersionAtLeast(required)
  const [major = 0, minor = 0] = webApp.version?.split('.').map(Number) ?? []
  const [requiredMajor, requiredMinor] = required.split('.').map(Number)
  return major > requiredMajor || (major === requiredMajor && minor >= requiredMinor)
}

/**
 * Request a fullscreen viewport only on capable Telegram hosts. This is a
 * presentation request, never a navigation, identity, or browser handoff.
 */
export function requestTelegramMiniAppFullscreen(): 'requested' | 'unsupported' | 'already_fullscreen' {
  try {
    if (typeof window === 'undefined') return 'unsupported'
    const webApp = window.Telegram?.WebApp
    if (!webApp?.requestFullscreen || !isVersionAtLeast(webApp, '8.0')) return 'unsupported'
    if (webApp.isFullscreen) return 'already_fullscreen'
    webApp.requestFullscreen()
    return 'requested'
  } catch {
    return 'unsupported'
  }
}

/**
 * Return a focused Mini App to the Telegram windowed viewport only when the
 * host exposes its versioned fullscreen exit capability.
 */
export function exitTelegramMiniAppFullscreen(): 'requested' | 'unsupported' | 'already_windowed' {
  try {
    if (typeof window === 'undefined') return 'unsupported'
    const webApp = window.Telegram?.WebApp
    if (!webApp?.exitFullscreen || !isVersionAtLeast(webApp, '8.0')) return 'unsupported'
    if (!webApp.isFullscreen) return 'already_windowed'
    webApp.exitFullscreen()
    return 'requested'
  } catch {
    return 'unsupported'
  }
}

/**
 * Telegram Desktop may reject a browser popup even when it was created from a
 * click handler. Use the host bridge for the authenticated browser handoff
 * whenever Telegram provides it; the caller still owns URL validation.
 */
export function hasTelegramMiniAppLinkBridge(): boolean {
  try {
    return typeof window !== 'undefined' && typeof window.Telegram?.WebApp?.openLink === 'function'
  } catch {
    return false
  }
}

export function openTelegramMiniAppLink(url: string): boolean {
  try {
    const openLink = window.Telegram?.WebApp?.openLink
    if (typeof openLink !== 'function') return false
    openLink(url)
    return true
  } catch {
    return false
  }
}

/**
 * Read the host's current presentation state without requesting a viewport
 * change. Initializing a Mini App must remain windowed unless the user asks.
 */
export function readTelegramMiniAppFullscreenState(): TelegramFullscreenState {
  try {
    if (typeof window === 'undefined' || !window.Telegram?.WebApp) return { kind: 'fullscreenFailed', error: 'UNSUPPORTED' }
    const webApp = window.Telegram.WebApp
    if (webApp.isFullscreen) return { kind: 'fullscreen' }
    if (!webApp.requestFullscreen || !isVersionAtLeast(webApp, '8.0')) return { kind: 'fullscreenUnsupported' }
    return { kind: 'windowed' }
  } catch {
    return { kind: 'fullscreenFailed', error: 'UNSUPPORTED' }
  }
}

/**
 * Observe Telegram fullscreen changes for the UI. The caller owns cleanup so
 * host listeners cannot survive an unmounted app shell.
 */
export function subscribeTelegramMiniAppFullscreen(onState: (state: TelegramFullscreenState) => void): () => void {
  const noop = () => undefined
  if (typeof window === 'undefined') return noop
  let webApp: TelegramWebApp | undefined
  let changedSubscribed = false
  let failedSubscribed = false
  const fullscreenChanged: TelegramFullscreenListener = (payload) => {
    try {
      const isFullscreen = typeof payload === 'object' && payload !== null && 'is_fullscreen' in payload
        ? (payload as { is_fullscreen?: unknown }).is_fullscreen === true
        : webApp?.isFullscreen === true
      onState({ kind: isFullscreen ? 'fullscreen' : 'windowed' })
    } catch {
      onState({ kind: 'fullscreenFailed', error: 'UNSUPPORTED' })
    }
  }
  const fullscreenFailed: TelegramFullscreenListener = (payload) => {
    try {
      const error = typeof payload === 'object' && payload !== null && 'error' in payload
        ? (payload as { error?: unknown }).error
        : undefined
      onState({ kind: 'fullscreenFailed', error: typeof error === 'string' ? error : 'UNKNOWN' })
    } catch {
      onState({ kind: 'fullscreenFailed', error: 'UNSUPPORTED' })
    }
  }

  const unsubscribe = () => {
    if (changedSubscribed) {
      try {
        webApp?.offEvent?.('fullscreen_changed', fullscreenChanged)
        changedSubscribed = false
      } catch {
        // Telegram host teardown must not escape React cleanup.
      }
    }
    if (failedSubscribed) {
      try {
        webApp?.offEvent?.('fullscreen_failed', fullscreenFailed)
        failedSubscribed = false
      } catch {
        // Telegram host teardown must not escape React cleanup.
      }
    }
  }

  try {
    webApp = window.Telegram?.WebApp
    if (!webApp?.onEvent || !webApp.offEvent) return noop
    webApp.onEvent('fullscreen_changed', fullscreenChanged)
    changedSubscribed = true
    webApp.onEvent('fullscreen_failed', fullscreenFailed)
    failedSubscribed = true
    return unsubscribe
  } catch {
    if (changedSubscribed) {
      unsubscribe()
      return unsubscribe
    }
    return noop
  }
}

export function readTelegramMiniAppLaunch(): TelegramMiniAppLaunch | null {
  try {
    if (typeof window === 'undefined') return null
    const webApp = window.Telegram?.WebApp
    const initData = webApp?.initData?.trim()
    if (!initData) return null
    const startParam = webApp?.initDataUnsafe?.start_param
    return {
      initData,
      startParam: typeof startParam === 'string' && startParam.trim() ? startParam.trim() : null,
    }
  } catch {
    return null
  }
}
