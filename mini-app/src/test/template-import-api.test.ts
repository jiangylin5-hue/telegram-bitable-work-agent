import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../app/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

test('renders template summaries from an allowlisted response shape', async () => {
  const fetchMock = vi.fn().mockResolvedValue(json({
    templates: [{
      id: 'template-1', name: 'CRM', category: 'crm', description: 'Safe summary', version: '1.0.0', status: 'published',
      manifest: { tables: [{ name: 'must-not-reach-client' }] }, created_by_user_id: 'must-not-reach-client',
    }],
  }))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.listTemplates()).resolves.toEqual([{
    id: 'template-1', name: 'CRM', category: 'crm', description: 'Safe summary', version: '1.0.0', status: 'published',
  }])
})

test('posts an XLSX preview with only approved fields and idempotency key', async () => {
  const fetchMock = vi.fn().mockResolvedValue(json({
    id: 'import-1', workspace_id: 'workspace-1', base_id: null, source_type: 'excel',
    detected_schema: [{ key: 'title', name: 'Title', field_type: 'text' }],
    preview_rows: [{ title: 'Launch' }], mapping: [], status: 'awaiting_confirmation', error_summary: 'must-not-reach-client',
  }))
  vi.stubGlobal('fetch', fetchMock)

  const preview = await api.createImport('workspace-1', {
    sourceType: 'excel', fileName: 'tasks.xlsx', content: 'UEsDB...', createdByUserId: 'user-1', baseId: undefined,
  }, 'import-create-1')

  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/imports', expect.objectContaining({
    method: 'POST', body: JSON.stringify({ source_type: 'excel', file_name: 'tasks.xlsx', content: 'UEsDB...', created_by_user_id: 'user-1' }),
  }))
  const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(new Headers(request.headers).get('Idempotency-Key')).toBe('import-create-1')
  expect(preview).not.toHaveProperty('error_summary')
})

test('rejects an import preview that includes a non-scalar mapping field', async () => {
  const fetchMock = vi.fn().mockResolvedValue(json({
    id: 'import-1', workspace_id: 'workspace-1', base_id: null, source_type: 'csv',
    detected_schema: [{ key: 'account', name: 'Account', field_type: 'linked_record' }],
    preview_rows: [{ account: 'Acme' }], mapping: [], status: 'awaiting_confirmation',
  }))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.importJob('import-1')).rejects.toThrow('Invalid import response')
})

test('uses the existing safe Base list before opening an installation receipt', async () => {
  const fetchMock = vi.fn().mockResolvedValue(json({
    bases: [{ id: 'base-installed', name: 'CRM', source_type: 'template', status: 'active', settings: { hidden: true } }],
  }))
  vi.stubGlobal('fetch', fetchMock)

  await expect(api.workspaceBases('workspace-1')).resolves.toEqual({
    bases: [{ id: 'base-installed', name: 'CRM', source_type: 'template', status: 'active' }],
  })
  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/bases', expect.any(Object))
})
