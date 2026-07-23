import { useState } from 'react'

import type { TelegramFullscreenState } from './telegram-mini-app'

type WorkspaceLaunchControlsProps = {
  telegramState: TelegramFullscreenState | null
  onOpenBrowser?: () => string | void | Promise<string | void>
}

/**
 * Renders only an already-authorized browser handoff. It accepts no identity
 * or transport data and cannot create a browser navigation by itself.
 */
export function WorkspaceLaunchControls({ telegramState, onOpenBrowser }: WorkspaceLaunchControlsProps) {
  const [failed, setFailed] = useState(false)
  if (telegramState?.kind !== 'fullscreenFailed' || telegramState.error !== 'UNSUPPORTED' || !onOpenBrowser) return null
  const issueBrowserHandoff = onOpenBrowser

  async function openBrowserWorkspaceFromClick(): Promise<void> {
    setFailed(false)
    try {
      const handoffUrl = await issueBrowserHandoff()
      if (typeof handoffUrl !== 'string') return
      const url = new URL(handoffUrl, window.location.origin)
      if (url.origin !== window.location.origin || url.search || !url.hash.startsWith('#ticket=')) throw new Error()
      const openLink = (window as unknown as { Telegram?: { WebApp?: { openLink?: (value: string) => void } } }).Telegram?.WebApp?.openLink
      if (openLink) {
        openLink(url.toString())
        return
      }
      if (!window.open(url.toString(), '_blank', 'noopener,noreferrer')) throw new Error()
    } catch {
      setFailed(true)
    }
  }

  return <aside className="workspace-launch-controls" aria-label="工作台打开方式">
    <button type="button" onClick={() => { void openBrowserWorkspaceFromClick() }}>在浏览器打开工作台</button>
    {failed && <p role="alert">无法打开工作台，请返回 Telegram 后重试。</p>}
  </aside>
}
