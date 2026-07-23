import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('reads only the safe Stage08 memory projection for the current workspace', async () => {
  const fetchMock = vi.fn(() => Promise.resolve(json({
    items: [{ memory_type: 'preference', status: 'active', version: 3, payload: { preference: '周报使用风险—动作—需支持格式' }, valid_until: null, source_refs: ['private'] }],
  })))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.listStage08Memory('workspace-1')).resolves.toEqual({
    items: [{ memoryType: 'preference', status: 'active', version: 3, payload: { preference: '周报使用风险—动作—需支持格式' }, validUntil: null }],
  })
  expect(fetchMock).toHaveBeenCalledWith('/api/stage08/memory?workspace_id=workspace-1&status=active', expect.anything())
})
