import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }) }
afterEach(() => vi.unstubAllGlobals())

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((nextResolve) => { resolve = nextResolve })
  return { promise, resolve }
}

test('opens Home assistant context only through the safe contacts endpoint', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', contacts: [{ id: 'employee-1', base_id: 'base-1', name: '运营助理', description: '安全摘要', status: 'active', available_intents: ['summarize'] }], next_cursor: null, has_more: false }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '智能汇总' }))
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(
    '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50',
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  ))
  expect(await screen.findByRole('dialog', { name: '个人助理上下文' })).toBeVisible()
  expect(screen.getByText('运营助理')).toBeVisible()
})

test('binds a Canvas summary invocation to only the current Base and view IDs', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'Operations', source_type: 'blank' }], queue: [] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [{ id: 'table-1', base_id: 'base-1', name: 'Tasks', key: 'tasks', status: 'active' }] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All tasks', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Tasks', key: 'tasks' }, fields: [{ id: 'field-title', table_id: 'table-1', name: 'Title', key: 'title', field_type: 'text', required: false, options: {}, order_index: 0 }] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['title'], group_by_field_key: null, date_field_key: null, form_field_keys: ['title'] }))
    if (path === '/views/view-1/records') return Promise.resolve(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', contacts: [{ id: 'employee-1', base_id: 'base-1', name: '运营助手', description: '安全摘要', status: 'active', available_intents: ['summarize'] }], next_cursor: null, has_more: false }))
    if (path === '/mini-app/digital-employees/employee-1/invocations') return Promise.resolve(json({ kind: 'summary', answer: '需要复核 2 条记录。', citations: [{ record_id: 'record-1' }] }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'Operations' }))
  fireEvent.click(await screen.findByRole('button', { name: '数字员工' }))
  fireEvent.click(await screen.findByRole('button', { name: '选择数字员工 运营助手' }))
  fireEvent.click(screen.getByRole('button', { name: '执行摘要' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/mini-app/digital-employees/employee-1/invocations',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ intent: 'summarize', base_id: 'base-1', view_id: 'view-1' }) }),
  ))
  expect(screen.getByText('需要复核 2 条记录。')).toBeVisible()
})

test('opens a queue draft only through the safe S5 detail endpoint', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [{ id: 'queue-1', kind: 'record_change_draft', title: '更新客户状态', status: 'pending_confirmation', destination: { base_id: 'base-1', draft_id: 'draft-1' }, action_availability: { can_confirm: true, can_reject: true } }] }))
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', contacts: [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/drafts/draft-1') return Promise.resolve(json({ id: 'draft-1', base_id: 'base-1', table_id: 'table-1', record_id: 'record-1', draft_type: 'update_record', status: 'pending_confirmation', version: 2, fields: [{ key: 'status', label: '客户状态', field_type: 'single_select', before_value: '跟进中', proposed_value: '已签约' }], actions: { can_confirm: true, can_reject: true }, terminal_audit_event_id: null }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '查看草稿' }))
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(
    '/mini-app/drafts/draft-1',
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  ))
  expect(await screen.findByText('客户状态')).toBeVisible()
  expect(screen.getByText(/之后：已签约/)).toBeVisible()
})

test('rereads the authoritative safe draft before showing a confirmed receipt', async () => {
  vi.stubGlobal('crypto', { randomUUID: () => 'confirm-1' })
  let draftReads = 0
  let confirmInit: RequestInit | undefined
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [{ id: 'queue-1', kind: 'record_change_draft', title: '更新客户状态', status: 'pending_confirmation', destination: { base_id: 'base-1', draft_id: 'draft-1' }, action_availability: { can_confirm: true, can_reject: true } }] }))
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', contacts: [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/drafts/draft-1') {
      draftReads += 1
      return Promise.resolve(json({ id: 'draft-1', base_id: 'base-1', table_id: 'table-1', record_id: 'record-1', draft_type: 'update_record', status: draftReads === 1 ? 'pending_confirmation' : 'confirmed', version: draftReads === 1 ? 2 : 3, fields: [{ key: 'status', label: '客户状态', field_type: 'single_select', before_value: '跟进中', proposed_value: '已签约' }], actions: { can_confirm: draftReads === 1, can_reject: draftReads === 1 }, terminal_audit_event_id: draftReads === 1 ? null : 'audit-1' }))
    }
    if (path === '/mini-app/drafts/draft-1/confirm') {
      confirmInit = init
      return Promise.resolve(json({ id: 'draft-1', status: 'confirmed', version: 3, terminal_audit_event_id: 'audit-1' }))
    }
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '查看草稿' }))
  fireEvent.click(await screen.findByRole('button', { name: '确认变更' }))
  await waitFor(() => expect(confirmInit).toBeDefined())
  expect(confirmInit).toMatchObject({ method: 'POST', headers: { 'idempotency-key': 'confirm-1' } })
  await waitFor(() => expect(draftReads).toBe(2))
  expect(await screen.findByText(/状态：confirmed/)).toBeVisible()
  expect(screen.getByText('audit-1')).toBeVisible()
})

test('renders a fixed local contact failure and only retries on an explicit user action', async () => {
  let contactReads = 0
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') {
      contactReads += 1
      return Promise.resolve(contactReads === 1
        ? json({ detail: 'raw provider detail must not render' }, 503)
        : json({ workspace_id: 'workspace-1', contacts: [{ id: 'employee-1', base_id: 'base-1', name: '运营助理', description: '安全摘要', status: 'active', available_intents: ['summarize'] }], next_cursor: null, has_more: false }))
    }
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '智能汇总' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法读取个人助理上下文，请稍后重试。')
  expect(screen.queryByText('raw provider detail must not render')).not.toBeInTheDocument()
  expect(contactReads).toBe(1)
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  expect(await screen.findByText('运营助理')).toBeVisible()
  expect(contactReads).toBe(2)
})

test('keeps the safe draft visible after a conflict and rereads only when requested', async () => {
  vi.stubGlobal('crypto', { randomUUID: () => 'conflict-1' })
  let draftReads = 0
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [{ id: 'queue-1', kind: 'record_change_draft', title: '更新客户状态', status: 'pending_confirmation', destination: { base_id: 'base-1', draft_id: 'draft-1' }, action_availability: { can_confirm: true, can_reject: true } }] }))
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', contacts: [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/drafts/draft-1') {
      draftReads += 1
      return Promise.resolve(json({ id: 'draft-1', base_id: 'base-1', table_id: 'table-1', record_id: 'record-1', draft_type: 'update_record', status: draftReads === 1 ? 'pending_confirmation' : 'confirmed', version: draftReads === 1 ? 2 : 3, fields: [{ key: 'status', label: '客户状态', field_type: 'single_select', before_value: '跟进中', proposed_value: '已签约' }], actions: { can_confirm: draftReads === 1, can_reject: draftReads === 1 }, terminal_audit_event_id: draftReads === 1 ? null : 'audit-1' }))
    }
    if (path === '/mini-app/drafts/draft-1/confirm') return Promise.resolve(json({ detail: 'raw conflict detail must not render' }, 409))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '查看草稿' }))
  fireEvent.click(await screen.findByRole('button', { name: '确认变更' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法读取数字员工与草稿，请稍后重试。')
  expect(screen.getByText('客户状态')).toBeVisible()
  expect(screen.queryByText('raw conflict detail must not render')).not.toBeInTheDocument()
  expect(draftReads).toBe(1)
  fireEvent.click(screen.getByRole('button', { name: '重新读取' }))
  expect(await screen.findByText(/状态：confirmed/)).toBeVisible()
  expect(draftReads).toBe(2)
})

test.each([401, 403])('does not let a delayed terminal draft command for the old workspace deny a replacement workspace on %s', async (status) => {
  const terminal = deferred<Response>()
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'header' },
      workspaces: [
        { id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } },
        { id: 'workspace-2', name: 'Northwind', slug: 'northwind', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } },
      ],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [{ id: 'queue-1', kind: 'record_change_draft', title: 'Update customer', status: 'pending_confirmation', destination: { base_id: 'base-1', draft_id: 'draft-1' }, action_availability: { can_confirm: true, can_reject: true } }] }))
    if (path === '/workspaces/workspace-2/home') return Promise.resolve(json({ workspace_id: 'workspace-2', recent_bases: [], queue: [] }))
    if (path === '/mini-app/workspaces/workspace-1/digital-employee-contacts?limit=50') return Promise.resolve(json({ workspace_id: 'workspace-1', contacts: [], next_cursor: null, has_more: false }))
    if (path === '/mini-app/drafts/draft-1') return Promise.resolve(json({ id: 'draft-1', base_id: 'base-1', table_id: 'table-1', record_id: 'record-1', draft_type: 'update_record', status: 'pending_confirmation', version: 1, fields: [{ key: 'status', label: 'Status', field_type: 'text', before_value: 'Before', proposed_value: 'After' }], actions: { can_confirm: true, can_reject: true }, terminal_audit_event_id: null }))
    if (path === '/mini-app/drafts/draft-1/confirm' && init?.method === 'POST') return terminal.promise
    return Promise.resolve(json({ detail: 'unexpected raw server detail' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: '查看草稿' }))
  fireEvent.click(await screen.findByRole('button', { name: '确认变更' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/mini-app/drafts/draft-1/confirm', expect.objectContaining({ method: 'POST' })))

  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })
  expect(await screen.findByRole('main', { name: '工作区首页' })).toHaveTextContent('Northwind')
  terminal.resolve(json({ detail: 'expired or denied identity' }, status))

  await waitFor(() => expect(screen.getByRole('main', { name: '工作区首页' })).toHaveTextContent('Northwind'))
  expect(screen.queryByRole('main', { name: '无工作区访问权限' })).not.toBeInTheDocument()
  expect(screen.queryByText('expired or denied identity')).not.toBeInTheDocument()
})
