import { fireEvent, render, screen } from '@testing-library/react'
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
