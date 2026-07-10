import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import { BaseCanvas } from '../app/BaseCanvas'

const base = { id: 'base-1', name: '项目管理', source_type: 'blank' }
const table = { id: 'table-1', base_id: 'base-1', name: '项目表', key: 'projects', status: 'active' }
const schema = {
  table: { id: 'table-1', name: '项目表', key: 'projects' },
  fields: [
    { id: 'field-1', name: '任务', key: 'name', field_type: 'text', required: true, order_index: 0 },
    { id: 'field-2', name: '状态', key: 'status', field_type: 'status', required: false, order_index: 1 },
    { id: 'field-3', name: '截止日', key: 'due', field_type: 'date', required: false, order_index: 2 },
  ],
}
const records = { view_id: 'view-1', records: [{ id: 'record-1', fields: { name: '发布计划', status: '进行中', due: '2026-07-10' } }], next_cursor: null, has_more: false }

function renderView(viewType: string, presentation: Partial<{ group_by_field_key: string | null; date_field_key: string | null; form_field_keys: string[] }> = {}) {
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '当前视图', view_type: viewType, status: 'active' }
  return render(<BaseCanvas base={base} tables={[table]} views={[view]} table={table} view={view} schema={schema} records={records} presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: viewType, visible_field_keys: ['name', 'status', 'due'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name', 'status', 'due'], ...presentation }} onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} />)
}

test('renders Kanban columns using the server-provided grouping field', () => {
  const view = renderView('kanban', { group_by_field_key: 'status' })
  expect(view.container.querySelector('.kanban-column')).toHaveTextContent('进行中')
  expect(screen.getByText('发布计划')).toBeInTheDocument()
})

test('renders Calendar headings using the server-provided date field', () => {
  renderView('calendar', { date_field_key: 'due' })
  expect(screen.getByRole('heading', { name: '2026-07-10' })).toBeInTheDocument()
})

test('renders Form fields in the server-provided field order', () => {
  renderView('form', { form_field_keys: ['due', 'name'] })
  expect(screen.getByRole('button', { name: '查看记录详情' })).toBeInTheDocument()
  expect(screen.getByText('截止日')).toBeInTheDocument()
})
