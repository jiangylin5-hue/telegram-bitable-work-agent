import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'
import { BaseCanvas } from '../app/BaseCanvas'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('shows the employee management entry only when the server capability permits it', () => {
  const onOpenDigitalEmployeeManagement = vi.fn()
  const props = {
    base: { id: 'base-1', name: 'CRM', source_type: 'blank' },
    tables: [{ id: 'table-1', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }],
    views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }],
    table: { id: 'table-1', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' },
    view: { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' },
    schema: { table: { id: 'table-1', name: '客户', key: 'customers' }, fields: [] },
    records: { view_id: 'view-1', records: [], next_cursor: null, has_more: false },
    presentation: { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] },
    onBack: () => undefined,
    onOpenRecord: () => undefined,
    onSelectView: () => undefined,
    onOpenDigitalEmployeeManagement,
  }
  const { rerender } = render(<BaseCanvas {...props} />)

  expect(screen.queryByRole('button', { name: '数字员工管理' })).not.toBeInTheDocument()
  rerender(<BaseCanvas {...props} canManageDigitalEmployees />)
  fireEvent.click(screen.getByRole('button', { name: '数字员工管理' }))
  expect(onOpenDigitalEmployeeManagement).toHaveBeenCalledOnce()
})

test('opens the operation center from an active Base canvas', () => {
  const onOpenTableOperations = vi.fn()
  render(<BaseCanvas
    base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }}
    tables={[{ id: 'table-1', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }]}
    views={[{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }]}
    table={{ id: 'table-1', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }}
    view={{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }}
    schema={{ table: { id: 'table-1', name: '客户', key: 'customers' }, fields: [] }}
    records={{ view_id: 'view-1', records: [], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()} onOpenTableOperations={onOpenTableOperations}
  />)

  fireEvent.click(screen.getByRole('button', { name: '表格操作' }))
  expect(onOpenTableOperations).toHaveBeenCalledOnce()
})

test('opens the Base action menu from right-click and keeps unavailable lifecycle actions disabled', () => {
  const onImportIntoBase = vi.fn()
  const onOpenTableOperations = vi.fn()
  render(<BaseCanvas
    base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }}
    tables={[{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }]}
    views={[{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }]}
    table={{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }}
    view={{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }}
    schema={{ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] }}
    records={{ view_id: 'view-1', records: [], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    canManageSchema
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()}
    onImportIntoBase={onImportIntoBase}
    onOpenTableOperations={onOpenTableOperations}
  />)

  const heading = screen.getByRole('heading', { name: 'CRM' })
  fireEvent.contextMenu(heading)

  expect(screen.getByRole('menu', { name: 'Base 操作' })).toBeVisible()
  expect(screen.getByRole('menuitem', { name: '复制或归档 Base（即将上线）' })).toBeDisabled()
  fireEvent.click(screen.getByRole('menuitem', { name: '导入到当前 Base' }))
  expect(onImportIntoBase).toHaveBeenCalledWith(heading)

  fireEvent.contextMenu(heading)
  fireEvent.click(screen.getByRole('menuitem', { name: '表格操作' }))
  expect(onOpenTableOperations).toHaveBeenCalledWith(heading)
})

test('opens one controlled table menu from keyboard and the visible chevron trigger', () => {
  const onOpenTableOperations = vi.fn()
  const onCreateRecord = vi.fn()
  const onCreateField = vi.fn()
  render(<BaseCanvas
    base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }}
    tables={[{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }]}
    views={[{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }]}
    table={{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }}
    view={{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }}
    schema={{ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-1', table_id: 'table-1', key: 'name', name: 'Name', field_type: 'text', required: false, options: {}, order_index: 0 }] }}
    records={{ view_id: 'view-1', records: [], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    canManageSchema canCreateRecords
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()}
    onOpenTableOperations={onOpenTableOperations}
    onCreateRecord={onCreateRecord}
    onCreateField={onCreateField}
  />)

  const tab = screen.getByRole('tab', { name: 'Customers' })
  fireEvent.keyDown(tab, { key: 'ContextMenu' })

  expect(screen.getByRole('menu', { name: '数据表操作' })).toBeVisible()
  expect(screen.getByRole('menuitem', { name: '复制或归档数据表（即将上线）' })).toBeDisabled()
  fireEvent.click(screen.getByRole('menuitem', { name: '表格操作' }))
  expect(onOpenTableOperations).toHaveBeenCalledWith(tab, 'table-1')

  fireEvent.click(screen.getByRole('button', { name: '更多 Customers 操作' }))
  expect(screen.getByRole('menu', { name: '数据表操作' })).toBeVisible()
  fireEvent.click(screen.getByRole('menuitem', { name: '新建记录' }))
  expect(onCreateRecord).toHaveBeenCalledOnce()
})

test('closes object menus with Escape or the backdrop and restores focus to each trigger', async () => {
  render(<BaseCanvas
    base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }}
    tables={[{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }]}
    views={[{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }]}
    table={{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }}
    view={{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }}
    schema={{ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] }}
    records={{ view_id: 'view-1', records: [], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    canManageSchema
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()}
    onSaveTemplate={vi.fn()} onOpenTableOperations={vi.fn()}
  />)

  const baseTrigger = screen.getByRole('button', { name: '更多 Base 操作' })
  fireEvent.click(baseTrigger)
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('menu', { name: 'Base 操作' })).not.toBeInTheDocument()
  await waitFor(() => expect(baseTrigger).toHaveFocus())

  const tab = screen.getByRole('tab', { name: 'Customers' })
  fireEvent.keyDown(tab, { key: 'F10', shiftKey: true })
  const menu = screen.getByRole('menu', { name: '数据表操作' })
  fireEvent.mouseDown(menu.parentElement!)
  expect(screen.queryByRole('menu', { name: '数据表操作' })).not.toBeInTheDocument()
  await waitFor(() => expect(tab).toHaveFocus())
})

test('routes a non-current table menu to that table and expands only its owning trigger', () => {
  const onOpenTableOperations = vi.fn()
  const onCreateRecord = vi.fn()
  const onCreateField = vi.fn()
  const customers = { id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }
  const projects = { id: 'table-2', base_id: 'base-1', name: 'Projects', key: 'projects', status: 'active' }
  render(<BaseCanvas
    base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }}
    tables={[customers, projects]}
    views={[
      { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All customers', view_type: 'grid', status: 'active' },
      { id: 'view-2', base_id: 'base-1', table_id: 'table-2', name: 'All projects', view_type: 'grid', status: 'active' },
    ]}
    table={customers}
    view={{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All customers', view_type: 'grid', status: 'active' }}
    schema={{ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-1', table_id: 'table-1', key: 'name', name: 'Name', field_type: 'text', required: false, options: {}, order_index: 0 }] }}
    records={{ view_id: 'view-1', records: [], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    canManageSchema canCreateRecords
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()}
    onOpenTableOperations={onOpenTableOperations}
    onCreateRecord={onCreateRecord}
    onCreateField={onCreateField}
  />)

  const customersTrigger = screen.getByRole('button', { name: '更多 Customers 操作' })
  const projectsTrigger = screen.getByRole('button', { name: '更多 Projects 操作' })
  fireEvent.click(projectsTrigger)

  const menu = screen.getByRole('menu', { name: '数据表操作' })
  expect(customersTrigger).toHaveAttribute('aria-expanded', 'false')
  expect(projectsTrigger).toHaveAttribute('aria-expanded', 'true')
  expect(projectsTrigger).toHaveAttribute('aria-controls', menu.id)
  fireEvent.click(screen.getByRole('menuitem', { name: '表格操作' }))
  expect(onOpenTableOperations).toHaveBeenCalledWith(projectsTrigger, 'table-2')

  fireEvent.click(projectsTrigger)
  fireEvent.click(screen.getByRole('menuitem', { name: '添加字段' }))
  expect(onCreateField).toHaveBeenCalledWith('table-2')

  fireEvent.click(projectsTrigger)
  fireEvent.click(screen.getByRole('menuitem', { name: '新建记录' }))
  expect(onCreateRecord).toHaveBeenCalledWith('table-2')
})

test('opens the Base menu from the keyboard and supports standard menu navigation', async () => {
  render(<BaseCanvas
    base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }}
    tables={[{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }]}
    views={[{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }]}
    table={{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }}
    view={{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }}
    schema={{ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] }}
    records={{ view_id: 'view-1', records: [], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    canManageSchema
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()}
    onImportIntoBase={vi.fn()} onSaveTemplate={vi.fn()} onOpenTableOperations={vi.fn()}
  />)

  const heading = screen.getByRole('heading', { name: 'CRM' })
  heading.focus()
  fireEvent.keyDown(heading, { key: 'ContextMenu' })

  expect(heading).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByRole('button', { name: '更多 Base 操作' })).toHaveAttribute('aria-expanded', 'false')
  const importItem = screen.getByRole('menuitem', { name: '导入到当前 Base' })
  const saveItem = screen.getByRole('menuitem', { name: '保存为模板' })
  const operationsItem = screen.getByRole('menuitem', { name: '表格操作' })
  await waitFor(() => expect(importItem).toHaveFocus())
  fireEvent.keyDown(importItem, { key: 'ArrowDown' })
  expect(saveItem).toHaveFocus()
  fireEvent.keyDown(saveItem, { key: 'End' })
  expect(operationsItem).toHaveFocus()
  fireEvent.keyDown(operationsItem, { key: 'Home' })
  expect(importItem).toHaveFocus()
  fireEvent.keyDown(importItem, { key: 'ArrowUp' })
  expect(operationsItem).toHaveFocus()

  fireEvent.keyDown(operationsItem, { key: 'Escape' })
  await waitFor(() => expect(heading).toHaveFocus())

  fireEvent.keyDown(heading, { key: 'F10', shiftKey: true })
  expect(screen.getByRole('menu', { name: 'Base 操作' })).toBeVisible()
})

test('opens App table operations against the selected menu table rather than the current table', async () => {
  const json = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    const responses: Record<string, unknown> = {
      '/mini-app/bootstrap': {
        identity: { user_id: 'owner-1', source: 'development_header' },
        workspaces: [{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }],
      },
      '/workspaces/workspace-1/home': {
        workspace_id: 'workspace-1',
        recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }],
        queue: [],
      },
      '/bases/base-1/tables': {
        tables: [
          { id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' },
          { id: 'table-2', base_id: 'base-1', name: 'Projects', key: 'projects', status: 'active' },
        ],
      },
      '/bases/base-1/views': {
        views: [
          { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All customers', view_type: 'grid', status: 'active' },
          { id: 'view-2', base_id: 'base-1', table_id: 'table-2', name: 'All projects', view_type: 'grid', status: 'active' },
        ],
      },
      '/tables/table-1/schema': { table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [{ id: 'field-1', table_id: 'table-1', key: 'name', name: 'Name', field_type: 'text', required: false, options: {}, order_index: 0 }] },
      '/views/view-1/presentation': { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: [] },
      '/views/view-1/records': { view_id: 'view-1', records: [], next_cursor: null, has_more: false },
      '/tables/table-2/schema': { table: { id: 'table-2', name: 'Projects', key: 'projects' }, fields: [{ id: 'field-2', table_id: 'table-2', key: 'name', name: 'Name', field_type: 'text', required: false, options: {}, order_index: 0 }] },
      '/views/view-2/presentation': { view_id: 'view-2', table_id: 'table-2', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: [] },
      '/views/view-2/records': { view_id: 'view-2', records: [], next_cursor: null, has_more: false },
    }
    return path in responses ? json(responses[path]) : json({ detail: `unexpected ${path}` })
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  fireEvent.click(await screen.findByRole('button', { name: '更多 Projects 操作' }))
  fireEvent.click(screen.getByRole('menuitem', { name: '表格操作' }))

  const dialog = await screen.findByRole('dialog', { name: '表格操作中心' })
  expect(dialog).toHaveTextContent('CRM / Projects / All projects')
})
