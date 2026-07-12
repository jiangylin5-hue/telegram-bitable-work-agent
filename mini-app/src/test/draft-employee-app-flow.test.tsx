import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }) }
afterEach(() => vi.unstubAllGlobals())

test('opens the S5 Hub only through the safe contacts endpoint', async () => {
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
  expect(await screen.findByRole('dialog', { name: '数字员工与草稿' })).toBeVisible()
  expect(screen.getByText('运营助理')).toBeVisible()
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
  expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法读取数字员工与草稿，请稍后重试。')
  expect(screen.queryByText('raw provider detail must not render')).not.toBeInTheDocument()
  expect(contactReads).toBe(1)
  fireEvent.click(screen.getByRole('button', { name: '重新读取' }))
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
