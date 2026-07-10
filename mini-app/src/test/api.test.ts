import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('forwards the query cancellation signal to the protected workspace Home request', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchMock)
  const controller = new AbortController()

  await (api.workspaceHome as (workspaceId: string, init: RequestInit) => Promise<unknown>)('workspace-1', { signal: controller.signal })

  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/home', expect.objectContaining({ signal: controller.signal }))
})
