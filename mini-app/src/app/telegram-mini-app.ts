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
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp }
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
