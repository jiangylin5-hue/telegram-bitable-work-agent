import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('guides an expired browser workspace session back to Telegram', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    expect(String(input)).toBe('/mini-app/bootstrap')
    return Promise.resolve(new Response(JSON.stringify({ detail: 'browser_session_invalid' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    }))
  }))

  render(<App />)

  expect(await screen.findByText('当前浏览器工作台会话已失效或无访问权限，请返回 Telegram 重新打开工作区。')).toBeInTheDocument()
  expect(screen.getByRole('main', { name: '无工作区访问权限' })).toBeInTheDocument()
})
