import { useState } from 'react'

import { exitTelegramMiniAppFullscreen, hasTelegramMiniAppLinkBridge, openTelegramMiniAppLink, requestTelegramMiniAppFullscreen, type TelegramFullscreenState } from './telegram-mini-app'

type WorkspaceLaunchControlsProps = {
  telegramState: TelegramFullscreenState | null
  onRequestFullscreen?: () => void
  onExitFullscreen?: () => void
  onOpenBrowser?: () => string | void | Promise<string | void>
}

/**
 * Renders only an already-authorized browser handoff. It accepts no identity
 * or transport data and cannot create a browser navigation by itself.
 */
export function WorkspaceLaunchControls({ telegramState, onRequestFullscreen, onExitFullscreen, onOpenBrowser }: WorkspaceLaunchControlsProps) {
  const [failed, setFailed] = useState(false)
  if (telegramState === null || !onOpenBrowser) return null
  const issueBrowserHandoff = onOpenBrowser
  const requestFullscreen = onRequestFullscreen ?? requestTelegramMiniAppFullscreen
  const exitFullscreen = onExitFullscreen ?? exitTelegramMiniAppFullscreen

  function isBrowserHandoffUrl(url: URL): boolean {
    if (url.origin !== window.location.origin || url.pathname !== '/browser-handoff.html' || url.search) return false
    const fragment = url.hash.slice(1)
    const parameters = new URLSearchParams(fragment)
    const ticket = parameters.get('ticket')
    return ticket !== null && ticket.length > 0 && parameters.size === 1 && fragment === new URLSearchParams({ ticket }).toString()
  }

  function closeWindow(browserWindow: Window): void {
    try {
      if (!browserWindow.closed) browserWindow.close()
    } catch {
      // A closed or inaccessible window must not expose handoff details.
    }
  }

  async function openBrowserWorkspaceFromClick(): Promise<void> {
    setFailed(false)
    const useTelegramBridge = hasTelegramMiniAppLinkBridge()
    const browserWindow = useTelegramBridge ? null : window.open('about:blank', '_blank')
    if (!useTelegramBridge && !browserWindow) return setFailed(true)
    if (browserWindow) {
      try {
        browserWindow.opener = null
      } catch {
        // The static handoff page repeats this isolation step when it loads.
      }
    }
    try {
      const handoffUrl = await issueBrowserHandoff()
      if (typeof handoffUrl !== 'string') throw new Error()
      const url = new URL(handoffUrl, window.location.origin)
      if (!isBrowserHandoffUrl(url)) throw new Error()
      if (useTelegramBridge) {
        if (!openTelegramMiniAppLink(url.toString())) throw new Error()
        return
      }
      if (!browserWindow || browserWindow.closed) throw new Error()
      browserWindow.location.replace(url.toString())
    } catch {
      if (browserWindow) closeWindow(browserWindow)
      setFailed(true)
    }
  }

  return <aside className="workspace-launch-controls" aria-label="工作台打开方式">
    {telegramState?.kind === 'fullscreen'
      ? <button type="button" onClick={exitFullscreen}>退出全屏</button>
      : <button type="button" onClick={requestFullscreen}>进入专注全屏</button>}
    <button type="button" onClick={() => { void openBrowserWorkspaceFromClick() }}>在浏览器打开完整工作台</button>
    {failed && <p role="alert">无法打开工作台，请返回 Telegram 后重试。</p>}
  </aside>
}
