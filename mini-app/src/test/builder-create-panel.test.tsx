import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { BuilderCreatePanel } from '../app/BuilderCreatePanel'
import { BaseCanvas } from '../app/BaseCanvas'
import { WorkspaceHome } from '../app/WorkspaceHome'
import { ApiError } from '../app/api'
import { App } from '../app/App'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('Base mode validates names and submits its default first table', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('crypto', { randomUUID: () => 'base-attempt-1' })

  render(<BuilderCreatePanel mode="base" onSubmit={onSubmit} onClose={() => undefined} />)

  const baseName = screen.getByLabelText('Base 名称')
  expect(baseName).toHaveFocus()
  expect(screen.getByLabelText('首张表名称')).toHaveValue('数据表')
  fireEvent.change(baseName, { target: { value: '  ' } })
  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))
  expect(onSubmit).not.toHaveBeenCalled()
  expect(screen.getByRole('alert')).toHaveTextContent('请填写 Base 名称。')

  fireEvent.change(baseName, { target: { value: '客户运营' } })
  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(
    { baseName: '客户运营', tableName: '数据表' },
    'base-attempt-1',
  ))
})

test('table mode keeps the same idempotency key after a retryable failure', async () => {
  const onSubmit = vi.fn()
    .mockRejectedValueOnce(new Error('network'))
    .mockResolvedValueOnce(undefined)
  vi.stubGlobal('crypto', { randomUUID: () => 'table-attempt-1' })

  render(<BuilderCreatePanel mode="table" onSubmit={onSubmit} onClose={() => undefined} />)

  expect(screen.queryByLabelText('Base 名称')).not.toBeInTheDocument()
  const tableName = screen.getByLabelText('数据表名称')
  expect(tableName).toHaveFocus()
  expect(tableName).toHaveValue('数据表')
  fireEvent.change(tableName, { target: { value: '待办' } })
  fireEvent.click(screen.getByRole('button', { name: '创建数据表' }))
  expect(screen.getByRole('button', { name: '创建中…' })).toBeDisabled()
  expect(await screen.findByRole('alert')).toHaveTextContent('创建失败，请稍后重试。')
  fireEvent.click(screen.getByRole('button', { name: '创建数据表' }))

  await waitFor(() => expect(onSubmit).toHaveBeenNthCalledWith(
    2,
    { tableName: '待办' },
    'table-attempt-1',
  ))
})

test('an idempotency conflict requires closing the panel before a new attempt', async () => {
  const onSubmit = vi.fn().mockRejectedValue(new ApiError(409))
  const onClose = vi.fn()
  vi.stubGlobal('crypto', { randomUUID: () => 'conflicted-attempt-1' })

  render(<BuilderCreatePanel mode="table" onSubmit={onSubmit} onClose={onClose} />)

  fireEvent.change(screen.getByLabelText('数据表名称'), { target: { value: '待办' } })
  fireEvent.click(screen.getByRole('button', { name: '创建数据表' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('创建请求发生冲突，请关闭后重新创建。')
  expect(screen.getByRole('button', { name: '创建数据表' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '取消' })).toBeEnabled()
})

test('closing the panel does not submit', () => {
  const onClose = vi.fn()
  const onSubmit = vi.fn().mockResolvedValue(undefined)

  render(<BuilderCreatePanel mode="table" onSubmit={onSubmit} onClose={onClose} />)
  fireEvent.click(screen.getByRole('button', { name: '取消' }))

  expect(onClose).toHaveBeenCalledOnce()
  expect(onSubmit).not.toHaveBeenCalled()
})

test('closes an idle create panel with Escape', () => {
  const onClose = vi.fn()

  render(<BuilderCreatePanel mode="table" onSubmit={() => Promise.resolve()} onClose={onClose} />)
  fireEvent.keyDown(document, { key: 'Escape' })

  expect(onClose).toHaveBeenCalledOnce()
})

test('closes an idle create panel from its backdrop', () => {
  const onClose = vi.fn()
  const { container } = render(<BuilderCreatePanel mode="table" onSubmit={() => Promise.resolve()} onClose={onClose} />)

  fireEvent.mouseDown(container.firstElementChild!)

  expect(onClose).toHaveBeenCalledOnce()
})

test('does not close a create panel from Escape or its backdrop while saving', async () => {
  let resolveSubmission: (() => void) | undefined
  const onClose = vi.fn()
  const { container } = render(<BuilderCreatePanel
    mode="table"
    onSubmit={() => new Promise<void>((resolve) => { resolveSubmission = resolve })}
    onClose={onClose}
  />)

  fireEvent.click(screen.getByRole('button', { name: '创建数据表' }))
  await screen.findByRole('button', { name: '创建中…' })
  fireEvent.keyDown(document, { key: 'Escape' })
  fireEvent.mouseDown(container.firstElementChild!)

  expect(onClose).not.toHaveBeenCalled()
  await act(async () => resolveSubmission?.())
})

test('closes the Base create panel with Escape and restores focus to its trigger', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  const trigger = await screen.findByRole('button', { name: '新建 Base' })
  fireEvent.click(trigger)
  await screen.findByRole('dialog', { name: '新建 Base' })

  fireEvent.keyDown(document, { key: 'Escape' })

  await waitFor(() => expect(screen.queryByRole('dialog', { name: '新建 Base' })).not.toBeInTheDocument())
  expect(trigger).toHaveFocus()
})

test('returns focus to the Table Operations Base action after closing the create panel', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '表格操作' }))
  const action = within(await screen.findByRole('dialog', { name: '表格操作中心' })).getByRole('button', { name: '新建 Base' })
  fireEvent.click(action)
  await screen.findByRole('dialog', { name: '新建 Base' })

  fireEvent.keyDown(document, { key: 'Escape' })

  await waitFor(() => expect(screen.queryByRole('dialog', { name: '新建 Base' })).not.toBeInTheDocument())
  expect(action).toHaveFocus()
})

test('creation entries are shown only when the server capability permits schema management', () => {
  const workspace = {
    id: 'workspace-1',
    name: '运营中心',
    slug: 'operations',
    role: 'viewer',
    capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false },
  }
  const home = { workspace_id: 'workspace-1', recent_bases: [], queue: [] }
  const table = { id: 'table-1', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '所有记录', view_type: 'grid', status: 'active' }
  const schema = { table: { id: 'table-1', name: '客户', key: 'customers' }, fields: [{ id: 'field-1', table_id: 'table-1', name: '名称', key: 'name', field_type: 'text', required: false, options: {}, order_index: 0 }] }
  const records = { view_id: 'view-1', records: [], next_cursor: null, has_more: false }
  const presentation = { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }

  const { rerender } = render(<WorkspaceHome home={home} workspace={workspace} onOpenBase={() => undefined} onCreateBase={() => undefined} />)
  expect(screen.queryByRole('button', { name: '新建 Base' })).not.toBeInTheDocument()
  rerender(<WorkspaceHome home={home} workspace={{ ...workspace, capabilities: { ...workspace.capabilities, can_manage_schema: true } }} onOpenBase={() => undefined} onCreateBase={() => undefined} />)
  expect(screen.getByRole('button', { name: '新建 Base' })).toBeInTheDocument()

  rerender(<BaseCanvas base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }} tables={[table]} views={[view]} table={table} view={view} schema={schema} records={records} presentation={presentation} onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} canManageSchema={false} onCreateTable={() => undefined} onCreateField={() => undefined} />)
  expect(screen.queryByRole('button', { name: '新建表' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '添加字段' })).not.toBeInTheDocument()
  rerender(<BaseCanvas base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }} tables={[table]} views={[view]} table={table} view={view} schema={schema} records={records} presentation={presentation} onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} canManageSchema onCreateTable={() => undefined} onCreateField={() => undefined} />)
  expect(screen.getByRole('button', { name: '新建表' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '添加字段' })).toBeInTheDocument()
})
