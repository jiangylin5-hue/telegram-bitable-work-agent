import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { WorkspaceLaunchControls } from '../app/WorkspaceLaunchControls'

test('renders the browser workspace action after Telegram reports fullscreen unsupported', () => {
  const onOpenBrowser = vi.fn()

  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreenFailed', error: 'UNSUPPORTED' }} onOpenBrowser={onOpenBrowser} />)

  fireEvent.click(screen.getByRole('button', { name: '在浏览器打开工作台' }))
  expect(onOpenBrowser).toHaveBeenCalledTimes(1)
})

test('does not render a browser workspace action without a real handoff callback', () => {
  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreenFailed', error: 'UNSUPPORTED' }} />)

  expect(screen.queryByRole('button', { name: '在浏览器打开工作台' })).not.toBeInTheDocument()
})

test('opens an issued same-origin fragment URL from the click handler without writing browser storage', async () => {
  const openLink = vi.fn()
  const issueHandoff = vi.fn().mockResolvedValue(`${window.location.origin}/browser-handoff.html#ticket=opaque-ticket`)
  const storageWrite = vi.spyOn(Storage.prototype, 'setItem')
  ;(window as unknown as { Telegram?: { WebApp?: { openLink?: (url: string) => void } } }).Telegram = { WebApp: { openLink } }

  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreenFailed', error: 'UNSUPPORTED' }} onOpenBrowser={issueHandoff} />)

  fireEvent.click(screen.getByRole('button', { name: '在浏览器打开工作台' }))

  await waitFor(() => expect(openLink).toHaveBeenCalledTimes(1))
  const [url] = openLink.mock.calls[0] as [string]
  expect(url).toContain('#ticket=opaque-ticket')
  expect(url).not.toContain('?ticket=')
  expect(storageWrite).not.toHaveBeenCalled()
  delete (window as unknown as { Telegram?: unknown }).Telegram
})
