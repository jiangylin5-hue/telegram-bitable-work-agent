import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'
import { ApiError } from '../app/api'
import { ViewBuilderPanel } from '../app/ViewBuilderPanel'
import type { ViewBuilderContext, ViewBuilderResponse } from '../app/view-builder-types'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const capabilities = { can_read_bases: true, can_manage_workspace: false, can_manage_schema: true, can_review_drafts: false }
const bootstrap = { identity: { user_id: 'owner-1', source: 'development_header' }, workspaces: [{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'owner', capabilities }] }
const home = { workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }], queue: [] }
const table = { id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }
const view = (name = 'Private filters') => ({ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name, view_type: 'grid' as const, status: 'active', scope: 'private' as const, caller_access_level: 'owner' as const, is_default: false })
const presentation = { view_id: 'view-1', table_id: 'table-1', view_type: 'grid' as const, visible_field_keys: ['title'], group_by_field_key: null, date_field_key: null, form_field_keys: [] }
const context: ViewBuilderContext = {
  table,
  fields: [{ field_id: 'field-title', key: 'title', label: 'Title', field_type: 'text', filter_operators: ['equals'], filter_values: [], sortable: true, groupable: false, form_eligible: true }],
  views: [],
  member_candidates: [],
}
const builder = (name = 'Private filters', version = 1): ViewBuilderResponse => ({
  view: view(name),
  presentation: { ...presentation, filters: [], sort_rules: [] },
  fields: context.fields,
  members: [],
  version,
  can_edit_presentation: true,
  can_replace_members: true,
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('reloads canonical Canvas state after a version conflict without exposing the server detail', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let builderReads = 0
  let listReads = 0
  let recordReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') {
      listReads += 1
      return Promise.resolve(json({ views: [view(listReads > 1 ? 'Canonical server view' : 'Private filters')] }))
    }
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-title', table_id: 'table-1', name: 'Title', key: 'title', field_type: 'text', required: false, options: {}, order_index: 0 }] }))
    if (path === '/views/view-1/presentation' && init?.method !== 'PATCH') return Promise.resolve(json(presentation))
    if (path === '/views/view-1/records') {
      recordReads += 1
      return Promise.resolve(json({ view_id: 'view-1', records: [{ id: 'record-1', fields: { title: recordReads > 1 ? 'Canonical server row' : 'Initial row' } }], next_cursor: null, has_more: false }))
    }
    if (path === '/tables/table-1/view-builder-context') return Promise.resolve(json(context))
    if (path === '/views/view-1/builder') {
      builderReads += 1
      return Promise.resolve(json(builder(builderReads > 2 ? 'Canonical server view' : 'Private filters', builderReads > 2 ? 2 : 1)))
    }
    if (path === '/views/view-1/presentation' && init?.method === 'PATCH') return Promise.resolve(json({ detail: { code: 'view_version_conflict', message: 'raw server secret must never render' } }, 409))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  fireEvent.click(await screen.findByRole('button', { name: '配置视图' }))
  fireEvent.change(await screen.findByLabelText('视图名称'), { target: { value: 'Stale local draft' } })
  fireEvent.click(screen.getByRole('button', { name: '保存视图' }))

  expect(await screen.findByText('视图已被更新，请重新加载后再试。')).toBeVisible()
  await waitFor(() => expect(screen.getByLabelText('视图名称')).toHaveValue('Canonical server view'))
  expect(await screen.findByRole('cell', { name: 'Canonical server row' })).toBeInTheDocument()
  expect(builderReads).toBeGreaterThanOrEqual(3)
  expect(listReads).toBeGreaterThanOrEqual(2)
  expect(recordReads).toBeGreaterThanOrEqual(2)
  expect(screen.queryByText('raw server secret must never render')).not.toBeInTheDocument()
})

test('retains a safe validation draft and maps only the fixed local error copy', async () => {
  const onSave = vi.fn().mockRejectedValue(new ApiError(422, 'view_filter_invalid'))
  render(<ViewBuilderPanel context={context} builder={builder()} onCreate={vi.fn()} onSave={onSave} onReplaceMembers={vi.fn()} onClose={() => undefined} />)

  fireEvent.change(screen.getByLabelText('视图名称'), { target: { value: 'Keep local draft' } })
  fireEvent.click(screen.getByRole('button', { name: '保存视图' }))

  expect(await screen.findByText('筛选条件不符合要求。')).toBeVisible()
  expect(screen.getByLabelText('视图名称')).toHaveValue('Keep local draft')
  expect(screen.queryByText('raw server secret must never render')).not.toBeInTheDocument()
})

test('reloads canonical member grants after an access version conflict without refetching records', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  let builderReads = 0
  let recordReads = 0
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json(bootstrap))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json(home))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [{ ...view(), scope: 'restricted' }] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-title', table_id: 'table-1', name: 'Title', key: 'title', field_type: 'text', required: false, options: {}, order_index: 0 }] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json(presentation))
    if (path === '/views/view-1/records') {
      recordReads += 1
      return Promise.resolve(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
    }
    if (path === '/tables/table-1/view-builder-context') return Promise.resolve(json({ ...context, member_candidates: [{ id: 'member-1', label: 'Member One' }] }))
    if (path === '/views/view-1/builder') {
      builderReads += 1
      return Promise.resolve(json({
        ...builder('Private filters', builderReads > 2 ? 2 : 1),
        view: { ...view(), scope: 'restricted' },
        members: builderReads > 2 ? [{ user_id: 'member-1', label: 'Member One', access_level: 'editor' }] : [],
      }))
    }
    if (path === '/views/view-1/members' && init?.method === 'PUT') return Promise.resolve(json({ detail: { code: 'view_version_conflict', message: 'raw member conflict detail must never render' } }, 409))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  fireEvent.click(await screen.findByRole('button', { name: '配置视图' }))
  fireEvent.click(await screen.findByRole('button', { name: '管理访问权限' }))
  fireEvent.change(await screen.findByLabelText('Member One 权限'), { target: { value: 'viewer' } })
  fireEvent.click(screen.getByRole('button', { name: '保存成员权限' }))

  expect(await screen.findByText('视图已被更新，请重新加载后再试。')).toBeVisible()
  await waitFor(() => expect(screen.getByLabelText('Member One 权限')).toHaveValue('editor'))
  expect(builderReads).toBeGreaterThanOrEqual(3)
  expect(recordReads).toBe(1)
  expect(screen.queryByText('raw member conflict detail must never render')).not.toBeInTheDocument()
})
