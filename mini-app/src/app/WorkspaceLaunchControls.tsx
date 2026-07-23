import type { TelegramFullscreenState } from './telegram-mini-app'

type WorkspaceLaunchControlsProps = {
  telegramState: TelegramFullscreenState | null
  onOpenBrowser?: () => void
}

/**
 * Renders only an already-authorized browser handoff. It accepts no identity
 * or transport data and cannot create a browser navigation by itself.
 */
export function WorkspaceLaunchControls({ telegramState, onOpenBrowser }: WorkspaceLaunchControlsProps) {
  if (telegramState?.kind !== 'fullscreenFailed' || telegramState.error !== 'UNSUPPORTED' || !onOpenBrowser) return null
  return <aside className="workspace-launch-controls" aria-label="工作台打开方式">
    <button type="button" onClick={onOpenBrowser}>在浏览器打开工作台</button>
  </aside>
}
