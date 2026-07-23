import { fireEvent, render, screen } from '@testing-library/react'
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
