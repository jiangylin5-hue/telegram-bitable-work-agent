import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import '../styles.css'
import { App } from '../app/App'
import { TableOperationCenter } from '../app/TableOperationCenter'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const table = { id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }
const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All customers', view_type: 'grid', status: 'active', scope: 'private', caller_access_level: 'owner', is_default: false }
const field = { id: 'field-title', table_id: 'table-1', name: 'Title', key: 'title', field_type: 'text', required: false, options: {}, order_index: 0 }

afterEach(() => vi.unstubAllGlobals())

function installBaseFixture() {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'development_header' },
      workspaces: [{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }], queue: [] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [table] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [view] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [field] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['title'], group_by_field_key: null, date_field_key: null, form_field_keys: ['title'] }))
    if (path === '/views/view-1/records') return Promise.resolve(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
    if (path === '/views/view-1/builder') return Promise.resolve(json({ detail: 'unavailable' }, 404))
    if (path === '/tables/table-1/view-builder-context') return Promise.resolve(json({
      table,
      fields: [{ field_id: 'field-title', key: 'title', label: 'Title', field_type: 'text', filter_operators: ['equals'], filter_values: [], sortable: true, groupable: false, form_eligible: true }],
      views: [],
      member_candidates: [],
    }))
    if (path === '/tables/table-1/create-form') return Promise.resolve(json({ table_id: 'table-1', can_create: true, fields: [field] }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  }))
}

async function openBaseOperationCenter() {
  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  fireEvent.click(await screen.findByRole('button', { name: '表格操作' }))
  return screen.findByRole('dialog', { name: '表格操作中心' })
}

test('routes each supported table action to an existing controlled surface', () => {
  const onCreateBase = vi.fn()
  const onOpenTemplates = vi.fn()
  const onCreateTable = vi.fn()
  const onCreateField = vi.fn()
  const onCreateView = vi.fn()
  const onConfigureView = vi.fn()
  const onCreateRecord = vi.fn()
  const onImportIntoBase = vi.fn()
  const onSaveTemplate = vi.fn()

  render(<TableOperationCenter
    scope={{ kind: 'base', baseName: '客户协作工作台', tableName: '客户表', viewName: '全部客户' }}
    actions={{ onCreateBase, onOpenTemplates, onCreateTable, onCreateField, onCreateView, onConfigureView, onCreateRecord, onImportIntoBase, onSaveTemplate }}
    onClose={vi.fn()}
  />)

  const createBase = screen.getByRole('button', { name: '新建 Base' })
  const openTemplates = screen.getByRole('button', { name: '模板与导入' })
  const createTable = screen.getByRole('button', { name: '新建数据表' })
  fireEvent.click(createBase)
  fireEvent.click(openTemplates)
  fireEvent.click(createTable)
  fireEvent.click(screen.getByRole('button', { name: '添加字段' }))
  fireEvent.click(screen.getByRole('button', { name: '新建视图' }))
  fireEvent.click(screen.getByRole('button', { name: '配置当前视图' }))
  fireEvent.click(screen.getByRole('button', { name: '新建记录' }))
  fireEvent.click(screen.getByRole('button', { name: '导入到当前 Base' }))
  fireEvent.click(screen.getByRole('button', { name: '保存为模板' }))

  expect(onCreateBase).toHaveBeenCalledWith(createBase)
  expect(onOpenTemplates).toHaveBeenCalledWith(openTemplates)
  expect(onCreateTable).toHaveBeenCalledWith(createTable)
  expect(onCreateField).toHaveBeenCalledOnce()
  expect(onCreateView).toHaveBeenCalledOnce()
  expect(onConfigureView).toHaveBeenCalledOnce()
  expect(onCreateRecord).toHaveBeenCalledOnce()
  expect(onImportIntoBase).toHaveBeenCalledOnce()
  expect(onSaveTemplate).toHaveBeenCalledOnce()
})

test('shows unimplemented lifecycle, bulk and export work as planned rather than fake controls', () => {
  render(<TableOperationCenter
    scope={{ kind: 'workspace' }}
    actions={{ onCreateBase: vi.fn(), onOpenTemplates: vi.fn() }}
    onClose={vi.fn()}
  />)

  for (const name of ['复制或归档 Base', '批量编辑记录', '导出 CSV / XLSX']) {
    const item = screen.getByRole('button', { name })
    expect(item).toBeDisabled()
    expect(item).toHaveAttribute('data-availability', 'planned')
    expect(item).toHaveTextContent('规划中')
  }
  expect(screen.getByText('这些能力尚未有受控的后端契约，不能以静态页面冒充可用。')).toBeVisible()
})

test('closes the operation center with Escape or its backdrop without closing from panel content', () => {
  const onClose = vi.fn()
  render(<TableOperationCenter scope={{ kind: 'workspace' }} actions={{ onCreateBase: vi.fn(), onOpenTemplates: vi.fn() }} onClose={onClose} />)

  const dialog = screen.getByRole('dialog', { name: '表格操作中心' })
  fireEvent.mouseDown(dialog)
  expect(onClose).not.toHaveBeenCalled()

  fireEvent.mouseDown(screen.getByRole('presentation'))
  expect(onClose).toHaveBeenCalledOnce()

  fireEvent.keyDown(document, { key: 'Escape' })
  expect(onClose).toHaveBeenCalledTimes(2)
})

test('uses a right-side drawer layout so table work stays visually in context', () => {
  render(<TableOperationCenter scope={{ kind: 'workspace' }} actions={{ onCreateBase: vi.fn(), onOpenTemplates: vi.fn() }} onClose={vi.fn()} />)

  expect(screen.getByRole('dialog', { name: '表格操作中心' })).toHaveAttribute('data-layout', 'side-drawer')
})

test('removes suspended parent controls from modal, pointer and keyboard interaction', () => {
  const onClose = vi.fn()
  render(<TableOperationCenter scope={{ kind: 'workspace' }} actions={{ onCreateBase: vi.fn(), onOpenTemplates: vi.fn() }} onClose={onClose} suspended />)

  expect(screen.queryByRole('dialog', { name: '表格操作中心' })).not.toBeInTheDocument()
  const backdrop = document.querySelector('.table-operation-backdrop')
  expect(backdrop).toHaveAttribute('data-suspended', 'true')
  expect(screen.getByRole('button', { name: '关闭表格操作中心', hidden: true })).toBeDisabled()
  fireEvent.mouseDown(backdrop!)
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(onClose).not.toHaveBeenCalled()
})

test('suspends the parent drawer for a field child and restores the field action trigger', async () => {
  installBaseFixture()
  const operationCenter = await openBaseOperationCenter()
  const action = within(operationCenter).getByRole('button', { name: '添加字段' })
  action.focus()

  fireEvent.click(action)

  const child = await screen.findByRole('dialog', { name: '添加字段' })
  expect(screen.queryByRole('dialog', { name: '表格操作中心' })).not.toBeInTheDocument()
  expect(document.querySelector('.table-operation-backdrop')).toHaveAttribute('data-suspended', 'true')

  fireEvent.click(within(child).getByRole('button', { name: '关闭' }))
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '添加字段' })).not.toBeInTheDocument())
  expect(action).toHaveFocus()
})

test('suspends the parent drawer for a view child and restores the view action trigger', async () => {
  installBaseFixture()
  const operationCenter = await openBaseOperationCenter()
  const action = within(operationCenter).getByRole('button', { name: '新建视图' })
  action.focus()

  fireEvent.click(action)

  const child = await screen.findByRole('dialog', { name: '新建视图' })
  expect(screen.queryByRole('dialog', { name: '表格操作中心' })).not.toBeInTheDocument()
  expect(document.querySelector('.table-operation-backdrop')).toHaveAttribute('data-suspended', 'true')
  fireEvent.click(within(child).getByRole('button', { name: '关闭视图配置' }))
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '新建视图' })).not.toBeInTheDocument())
  expect(action).toHaveFocus()
})

test('suspends the parent drawer for a record child and restores the record action trigger', async () => {
  installBaseFixture()
  const operationCenter = await openBaseOperationCenter()
  const action = within(operationCenter).getByRole('button', { name: '新建记录' })
  action.focus()

  fireEvent.click(action)

  const child = (await screen.findByRole('heading', { name: '新建记录' })).closest('aside')
  if (!child) throw new Error('Expected the create-record child panel')
  expect(screen.queryByRole('dialog', { name: '表格操作中心' })).not.toBeInTheDocument()
  expect(document.querySelector('.table-operation-backdrop')).toHaveAttribute('data-suspended', 'true')
  fireEvent.click(within(child).getByRole('button', { name: '关闭' }))
  await waitFor(() => expect(screen.queryByRole('heading', { name: '新建记录' })).not.toBeInTheDocument())
  expect(action).toHaveFocus()
})
