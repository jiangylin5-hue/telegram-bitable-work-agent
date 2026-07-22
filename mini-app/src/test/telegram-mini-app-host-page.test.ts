import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('Telegram Mini App host page', () => {
  it('loads the official Telegram WebApp bridge before the application module', () => {
    const html = readFileSync('index.html', 'utf8')
    const bridge = '<script src="https://telegram.org/js/telegram-web-app.js?63"></script>'
    const application = '<script type="module" src="/src/main.tsx"></script>'

    expect(html).toContain(bridge)
    expect(html.indexOf(bridge)).toBeLessThan(html.indexOf(application))
  })
})
