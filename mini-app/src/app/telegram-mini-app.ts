export type TelegramMiniAppLaunch = {
  initData: string
  startParam: string | null
}

export type TelegramFullscreenState =
  | { kind: 'fullscreenRequested' }
  | { kind: 'fullscreen' }
  | { kind: 'windowed' }
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
  if (typeof window === 'undefined') return false
  const webApp = window.Telegram?.WebApp
  if (!webApp) return false
  webApp.ready?.()
  webApp.expand?.()
  return true
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
  if (typeof window === 'undefined') return 'unsupported'
  const webApp = window.Telegram?.WebApp
  if (!webApp?.requestFullscreen || !isVersionAtLeast(webApp, '8.0')) return 'unsupported'
  if (webApp.isFullscreen) return 'already_fullscreen'
  webApp.requestFullscreen()
  return 'requested'
}

/**
 * Observe Telegram fullscreen changes for the UI. The caller owns cleanup so
 * host listeners cannot survive an unmounted app shell.
 */
export function subscribeTelegramMiniAppFullscreen(onState: (state: TelegramFullscreenState) => void): () => void {
  if (typeof window === 'undefined') return () => undefined
  const webApp = window.Telegram?.WebApp
  if (!webApp?.onEvent || !webApp.offEvent) return () => undefined
  const fullscreenChanged: TelegramFullscreenListener = (payload) => {
    const isFullscreen = typeof payload === 'object' && payload !== null && 'is_fullscreen' in payload
      ? (payload as { is_fullscreen?: unknown }).is_fullscreen === true
      : webApp.isFullscreen === true
    onState({ kind: isFullscreen ? 'fullscreen' : 'windowed' })
  }
  const fullscreenFailed: TelegramFullscreenListener = (payload) => {
    const error = typeof payload === 'object' && payload !== null && 'error' in payload
      ? (payload as { error?: unknown }).error
      : undefined
    onState({ kind: 'fullscreenFailed', error: typeof error === 'string' ? error : 'UNKNOWN' })
  }
  webApp.onEvent('fullscreen_changed', fullscreenChanged)
  webApp.onEvent('fullscreen_failed', fullscreenFailed)
  return () => {
    webApp.offEvent?.('fullscreen_changed', fullscreenChanged)
    webApp.offEvent?.('fullscreen_failed', fullscreenFailed)
  }
}

export function readTelegramMiniAppLaunch(): TelegramMiniAppLaunch | null {
  if (typeof window === 'undefined') return null
  const webApp = window.Telegram?.WebApp
  const initData = webApp?.initData?.trim()
  if (!initData) return null
  const startParam = webApp?.initDataUnsafe?.start_param
  return {
    initData,
    startParam: typeof startParam === 'string' && startParam.trim() ? startParam.trim() : null,
  }
}
