import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { BaseCanvas } from '../app/BaseCanvas'

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
  expect(onOpenTableOperations).toHaveBeenCalledWith(tab)

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
