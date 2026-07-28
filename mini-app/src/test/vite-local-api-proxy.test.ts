import { expect, test } from 'vitest'

import { createBuildOutputOptions, createLocalApiProxy } from '../../vite.config'

test('partitions stable framework dependencies into deterministic cacheable build chunks', () => {
  const { manualChunks } = createBuildOutputOptions()

  expect(manualChunks('D:/workspace/node_modules/react/index.js')).toBe('vendor-react')
  expect(manualChunks('D:/workspace/node_modules/react-dom/client.js')).toBe('vendor-react')
  expect(manualChunks('D:/workspace/node_modules/@tanstack/react-query/build/index.js')).toBe('vendor-query')
  expect(manualChunks('D:/workspace/node_modules/lucide-react/dist/cjs/lucide-react.js')).toBe('vendor-icons')
  expect(manualChunks('D:/workspace/src/app/App.tsx')).toBeNull()
})

test('proxies every Mini App API namespace, including Stage08 /api routes, to the local FastAPI server', () => {
  const proxy = createLocalApiProxy()

  expect(proxy?.['/mini-app']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/workspaces']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/bases']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/tables']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/views']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/records']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/templates']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/import-jobs']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
  expect(proxy?.['/api']).toMatchObject({ target: 'http://127.0.0.1:8000', changeOrigin: true })
})

test('adds a local-only Stage07 actor header only when an explicit acceptance actor is supplied', () => {
  expect(createLocalApiProxy('stage07-browser-owner')['/mini-app']).toMatchObject({
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    headers: { 'X-Stage06-User-Id': 'stage07-browser-owner' },
  })
  expect(createLocalApiProxy(undefined)['/mini-app']).not.toHaveProperty('headers')
})
