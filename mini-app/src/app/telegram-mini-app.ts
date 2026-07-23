export type TelegramMiniAppLaunch = {
  initData: string
  startParam: string | null
}

type TelegramWebApp = {
  initData?: string
  initDataUnsafe?: {
    start_param?: unknown
    [key: string]: unknown
  }
  ready?: () => void
  expand?: () => void
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
