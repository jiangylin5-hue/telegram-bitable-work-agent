import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { BaseCanvas } from '../app/BaseCanvas'

function renderCanvas(onOpenRecord = vi.fn()) {
  render(<BaseCanvas
    base={{ id: 'base-1', name: '客户协作工作台', source_type: 'blank' }}
    tables={[{ id: 'table-1', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }]}
    views={[{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }]}
    table={{ id: 'table-1', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }}
    view={{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '全部客户', view_type: 'grid', status: 'active' }}
    schema={{ table: { id: 'table-1', name: '客户', key: 'customers' }, fields: [{ id: 'field-1', table_id: 'table-1', key: 'name', name: '客户名称', field_type: 'text', required: false, options: {}, order_index: 0 }] }}
    records={{ view_id: 'view-1', records: [{ id: 'record-1', fields: { name: '明日璀璨' } }], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    onBack={vi.fn()}
    onOpenRecord={onOpenRecord}
    onSelectView={vi.fn()}
  />)
  return onOpenRecord
}

test('opens the same record detail action from a desktop right-click menu', () => {
  const onOpenRecord = renderCanvas()

  fireEvent.contextMenu(screen.getByText('明日璀璨'))

  expect(screen.getByRole('menu', { name: '记录操作' })).toBeVisible()
  fireEvent.click(screen.getByRole('menuitem', { name: '查看记录详情' }))
  expect(onOpenRecord).toHaveBeenCalledWith('record-1')
  expect(screen.queryByRole('menu', { name: '记录操作' })).not.toBeInTheDocument()
})

test('closes the record context menu on Escape and exposes unavailable lifecycle actions as disabled', () => {
  renderCanvas()

  fireEvent.contextMenu(screen.getByText('明日璀璨'))
  expect(screen.getByRole('menuitem', { name: '复制或归档记录（即将上线）' })).toBeDisabled()
  fireEvent.keyDown(document, { key: 'Escape' })

  expect(screen.queryByRole('menu', { name: '记录操作' })).not.toBeInTheDocument()
})
