import { expect, test } from 'vitest'

import { createLocalApiProxy } from '../../vite.config'

test('proxies every existing Stage07 API root to the local FastAPI server for built Mini App acceptance', () => {
  const proxy = createLocalApiProxy()

  expect(proxy?.['/mini-app']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/workspaces']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/bases']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/tables']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/views']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/records']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/templates']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/import-jobs']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
})

test('adds a local-only Stage07 actor header only when an explicit acceptance actor is supplied', () => {
  expect(createLocalApiProxy('stage07-browser-owner')['/mini-app']).toMatchObject({
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    headers: { 'X-Stage06-User-Id': 'stage07-browser-owner' },
  })
  expect(createLocalApiProxy(undefined)['/mini-app']).not.toHaveProperty('headers')
})
