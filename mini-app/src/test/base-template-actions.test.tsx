import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { BaseCanvas } from '../app/BaseCanvas'

test('exposes template save and in-Base import only through authorized Base actions', () => {
  const onSaveTemplate = vi.fn()
  const onImportIntoBase = vi.fn()
  render(<BaseCanvas
    base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }}
    tables={[{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }]}
    views={[{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }]}
    table={{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }}
    view={{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }}
    schema={{ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] }}
    records={{ view_id: 'view-1', records: [], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()} canManageSchema
    onSaveTemplate={onSaveTemplate} onImportIntoBase={onImportIntoBase}
  />)

  fireEvent.click(screen.getByRole('button', { name: '更多 Base 操作' }))
  fireEvent.click(screen.getByRole('button', { name: '保存为模板' }))
  expect(onSaveTemplate).toHaveBeenCalledOnce()
  fireEvent.click(screen.getByRole('button', { name: '更多 Base 操作' }))
  fireEvent.click(screen.getByRole('button', { name: '导入到当前 Base' }))
  expect(onImportIntoBase).toHaveBeenCalledOnce()
})

test('offers an Excel or CSV import path before an empty grid has its first field', () => {
  const onImportIntoBase = vi.fn()
  render(<BaseCanvas
    base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }}
    tables={[{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }]}
    views={[{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }]}
    table={{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }}
    view={{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }}
    schema={{ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] }}
    records={{ view_id: 'view-1', records: [], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()} canManageSchema
    onCreateField={vi.fn()} onImportIntoBase={onImportIntoBase}
  />)

  fireEvent.click(screen.getByRole('button', { name: '从 Excel/CSV 导入' }))
  expect(onImportIntoBase).toHaveBeenCalledOnce()
})
