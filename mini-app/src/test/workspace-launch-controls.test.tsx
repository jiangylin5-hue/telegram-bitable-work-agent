import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { WorkspaceLaunchControls } from '../app/WorkspaceLaunchControls'
import '../styles.css'

function browserWindow() {
  return {
    closed: false,
    close: vi.fn(),
    location: { replace: vi.fn() },
  } as unknown as Window
}

afterEach(() => {
  delete (window as unknown as { Telegram?: unknown }).Telegram
  vi.restoreAllMocks()
})

test('does not render Telegram launch controls outside Telegram', () => {
  render(<WorkspaceLaunchControls telegramState={null} onOpenBrowser={vi.fn()} />)

  expect(screen.queryByLabelText('工作台打开方式')).not.toBeInTheDocument()
})

test('renders the browser workspace action after Telegram reports fullscreen unsupported', () => {
  const onOpenBrowser = vi.fn()
  vi.spyOn(window, 'open').mockReturnValue(browserWindow())

  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreenFailed', error: 'UNSUPPORTED' }} onOpenBrowser={onOpenBrowser} />)

  fireEvent.click(screen.getByRole('button', { name: '在浏览器打开完整工作台' }))
  expect(onOpenBrowser).toHaveBeenCalledTimes(1)
})

test('shows the browser workspace action while Telegram is fullscreen', () => {
  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreen' }} onOpenBrowser={vi.fn()} />)

  expect(screen.getByRole('button', { name: '在浏览器打开完整工作台' })).toBeVisible()
})

test('requests fullscreen only from an explicit user click', () => {
  const onRequestFullscreen = vi.fn()
  render(<WorkspaceLaunchControls telegramState={{ kind: 'windowed' }} onRequestFullscreen={onRequestFullscreen} onOpenBrowser={vi.fn()} />)

  expect(onRequestFullscreen).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '进入专注全屏' }))
  expect(onRequestFullscreen).toHaveBeenCalledTimes(1)
})

test('exits fullscreen only from an explicit user click', () => {
  const onExitFullscreen = vi.fn()
  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreen' }} onExitFullscreen={onExitFullscreen} onOpenBrowser={vi.fn()} />)

  expect(onExitFullscreen).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '退出全屏' }))
  expect(onExitFullscreen).toHaveBeenCalledTimes(1)
})

test.each([320, 375, 900])('keeps fullscreen controls in the mobile document flow and operable at %ipx', (width) => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
  const onRequestFullscreen = vi.fn()
  render(<WorkspaceLaunchControls telegramState={{ kind: 'windowed' }} onRequestFullscreen={onRequestFullscreen} onOpenBrowser={vi.fn()} />)

  const requestButton = screen.getByRole('button', { name: '进入专注全屏' })
  expect(requestButton).toBeVisible()
  expect(screen.getByRole('button', { name: '在浏览器打开完整工作台' })).toBeVisible()
  const controls = screen.getByRole('complementary', { name: '工作台打开方式' })
  expect(getComputedStyle(controls).position).toBe('static')
  fireEvent.click(requestButton)
  expect(onRequestFullscreen).toHaveBeenCalledOnce()
})

test('does not render a browser workspace action without a real handoff callback', () => {
  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreenFailed', error: 'UNSUPPORTED' }} />)

  expect(screen.queryByRole('button', { name: '在浏览器打开完整工作台' })).not.toBeInTheDocument()
})

test('does not render an inoperable fullscreen action on an unsupported Telegram host', () => {
  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreenUnsupported' } as never} onOpenBrowser={vi.fn()} />)

  expect(screen.queryByRole('button', { name: '进入专注全屏' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '在浏览器打开完整工作台' })).toBeVisible()
})

test('preopens a controlled browser window synchronously before issuing a fragment-only handoff', async () => {
  const popup = browserWindow()
  const issueHandoff = vi.fn().mockResolvedValue(`${window.location.origin}/browser-handoff.html#ticket=opaque-ticket`)
  const storageWrite = vi.spyOn(Storage.prototype, 'setItem')
  const openBrowser = vi.spyOn(window, 'open').mockReturnValue(popup)

  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreenFailed', error: 'UNSUPPORTED' }} onOpenBrowser={issueHandoff} />)

  fireEvent.click(screen.getByRole('button', { name: '在浏览器打开完整工作台' }))

  expect(openBrowser).toHaveBeenCalledExactlyOnceWith('about:blank', '_blank')
  expect(openBrowser.mock.invocationCallOrder[0]).toBeLessThan(issueHandoff.mock.invocationCallOrder[0])
  await waitFor(() => expect(popup.location.replace).toHaveBeenCalledWith(`${window.location.origin}/browser-handoff.html#ticket=opaque-ticket`))
  expect(issueHandoff.mock.invocationCallOrder[0]).toBeLessThan((popup.location.replace as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0])
  expect(storageWrite).not.toHaveBeenCalled()
})

test('uses the Telegram host link bridge instead of a blocked browser popup when it is available', async () => {
  const openLink = vi.fn()
  const issueHandoff = vi.fn().mockResolvedValue(`${window.location.origin}/browser-handoff.html#ticket=opaque-ticket`)
  const popupOpen = vi.spyOn(window, 'open')
  ;(window as unknown as { Telegram?: { WebApp?: { openLink?: (url: string) => void } } }).Telegram = { WebApp: { openLink } }

  render(<WorkspaceLaunchControls telegramState={{ kind: 'windowed' }} onOpenBrowser={issueHandoff} />)
  fireEvent.click(screen.getByRole('button', { name: '在浏览器打开完整工作台' }))

  await waitFor(() => expect(openLink).toHaveBeenCalledExactlyOnceWith(`${window.location.origin}/browser-handoff.html#ticket=opaque-ticket`))
  expect(popupOpen).not.toHaveBeenCalled()
})

test.each([
  `${window.location.origin}/other.html#ticket=opaque-ticket`,
  `${window.location.origin}/browser-handoff.html?ticket=opaque-ticket`,
  `${window.location.origin}/browser-handoff.html#ticket=opaque-ticket&next=1`,
  `${window.location.origin}/browser-handoff.html#ticket=`,
])('rejects a handoff URL outside the exact fragment contract: %s', async (invalidUrl) => {
  const popup = browserWindow()
  vi.spyOn(window, 'open').mockReturnValue(popup)

  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreenFailed', error: 'UNSUPPORTED' }} onOpenBrowser={() => invalidUrl} />)
  fireEvent.click(screen.getByRole('button', { name: '在浏览器打开完整工作台' }))

  await waitFor(() => expect(popup.close).toHaveBeenCalledTimes(1))
  expect(popup.location.replace).not.toHaveBeenCalled()
})

test('closes the preopened browser window when ticket issuance fails without showing the ticket', async () => {
  const popup = browserWindow()
  vi.spyOn(window, 'open').mockReturnValue(popup)

  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreenFailed', error: 'UNSUPPORTED' }} onOpenBrowser={() => Promise.reject(new Error('opaque-ticket'))} />)
  fireEvent.click(screen.getByRole('button', { name: '在浏览器打开完整工作台' }))

  await waitFor(() => expect(popup.close).toHaveBeenCalledTimes(1))
  expect(screen.getByRole('alert')).not.toHaveTextContent('opaque-ticket')
})
