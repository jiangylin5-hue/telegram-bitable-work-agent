import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const { clearRelationCandidateQueries } = vi.hoisted(() => ({
  clearRelationCandidateQueries: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../app/protectedQuery', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../app/protectedQuery')>()
  return { ...actual, clearRelationCandidateQueries }
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearRelationCandidateQueries.mockClear()
})

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

test('closing Detail cancels candidate queries for every linked schema field', async () => {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const requestUrl = new URL(typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url, 'http://fixture.local')
    const path = requestUrl.pathname
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'user-1', source: 'verified_adapter' },
      workspaces: [{ id: 'workspace-1', name: 'Workspace One', slug: 'workspace-one', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'Base One', source_type: 'blank' }], queue: [] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [{ id: 'table-1', base_id: 'base-1', name: 'Table One', key: 'table_one', status: 'active' }] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All records', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({
      table: { id: 'table-1', name: 'Table One', key: 'table_one' },
      fields: [
        { id: 'field-name', table_id: 'table-1', name: 'Name', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 },
        { id: 'field-customer', table_id: 'table-1', name: 'Customer', key: 'customer', field_type: 'linked_record', required: false, options: {}, order_index: 1 },
        { id: 'field-project', table_id: 'table-1', name: 'Project', key: 'project', field_type: 'linked_record', required: false, options: {}, order_index: 2 },
      ],
    }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }))
    if (path === '/views/view-1/records') return Promise.resolve(json({ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: 'Ada Co' } }], next_cursor: null, has_more: false }))
    if (path === '/records/record-1') return Promise.resolve(json({ id: 'record-1', table_id: 'table-1', values: { name: 'Ada Co', customer: [], project: [] }, record_status: 'active', version: 1 }))
    if (path.startsWith('/fields/')) {
      const fieldId = path.split('/')[2]
      return Promise.resolve(json({ field_id: fieldId, records: [], next_cursor: null, has_more: false }))
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  const view = render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'Base One' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Ada Co' }))
  const editButton = await waitFor(() => {
    const button = view.container.querySelector<HTMLButtonElement>('.detail-edit')
    expect(button).not.toBeNull()
    return button!
  })
  fireEvent.click(editButton)

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/fields/field-customer/relation-candidates', expect.any(Object)))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/fields/field-project/relation-candidates', expect.any(Object)))
  fireEvent.click(view.container.querySelector('.record-detail .detail-actions button:not(.detail-edit)')!)

  await waitFor(() => expect(clearRelationCandidateQueries).toHaveBeenCalledTimes(2))
  expect(clearRelationCandidateQueries).toHaveBeenCalledWith(expect.anything(), { userId: 'user-1', workspaceId: 'workspace-1' }, 'field-customer')
  expect(clearRelationCandidateQueries).toHaveBeenCalledWith(expect.anything(), { userId: 'user-1', workspaceId: 'workspace-1' }, 'field-project')
})
