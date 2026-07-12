import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { BaseCanvas } from '../app/BaseCanvas'

const base = { id: 'base-1', name: '项目管理', source_type: 'blank' }
const table = { id: 'table-1', base_id: 'base-1', name: '项目表', key: 'projects', status: 'active' }
const schema = {
  table: { id: 'table-1', name: '项目表', key: 'projects' },
  fields: [
    { id: 'field-1', table_id: 'table-1', name: '任务', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 },
    { id: 'field-2', table_id: 'table-1', name: '状态', key: 'status', field_type: 'status', required: false, options: {}, order_index: 1 },
    { id: 'field-3', table_id: 'table-1', name: '截止日', key: 'due', field_type: 'date', required: false, options: {}, order_index: 2 },
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

test('forwards only the server-provided next cursor when loading another record page', () => {
  const onLoadMore = vi.fn()
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '当前视图', view_type: 'grid', status: 'active' }
  render(<BaseCanvas base={base} tables={[table]} views={[view]} table={table} view={view} schema={schema} records={{ ...records, next_cursor: 'cursor-2', has_more: true }} presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name', 'status', 'due'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name', 'status', 'due'] }} onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} onLoadMore={onLoadMore} />)

  fireEvent.click(screen.getByRole('button', { name: '加载更多记录' }))

  expect(onLoadMore).toHaveBeenCalledWith('cursor-2')
})

test('exposes a create-record entry only when the canvas supplies an authorized handler', () => {
  const onCreateRecord = vi.fn()
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '当前视图', view_type: 'grid', status: 'active' }
  const props = { base, tables: [table], views: [view], table, view, schema, records, presentation: { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }, onBack: () => undefined, onOpenRecord: () => undefined, onSelectView: () => undefined, onCreateRecord }
  const { rerender } = render(<BaseCanvas {...props} />)
  expect(screen.queryByRole('button', { name: '新建记录' })).not.toBeInTheDocument()

  rerender(<BaseCanvas {...props} canCreateRecords />)

  fireEvent.click(screen.getByRole('button', { name: '新建记录' }))
  expect(onCreateRecord).toHaveBeenCalledOnce()
})

test('renders supplied authorized tables as selectable tabs', () => {
  const onSelectTable = vi.fn()
  const tasks = { id: 'table-2', base_id: 'base-1', name: 'Tasks', key: 'tasks', status: 'active' }
  const view = { id: 'view-2', base_id: 'base-1', table_id: 'table-2', name: 'All tasks', view_type: 'grid', status: 'active' }
  const taskSchema = { ...schema, table: { id: 'table-2', name: 'Tasks', key: 'tasks' } }
  render(<BaseCanvas base={base} tables={[table, tasks]} views={[view]} table={tasks} view={view} schema={taskSchema} records={{ ...records, view_id: 'view-2' }} presentation={{ view_id: 'view-2', table_id: 'table-2', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }} onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} onSelectTable={onSelectTable} />)

  expect(screen.getByRole('tab', { name: table.name })).toHaveAttribute('aria-selected', 'false')
  expect(screen.getByRole('tab', { name: 'Tasks' })).toHaveAttribute('aria-selected', 'true')
  fireEvent.click(screen.getByRole('tab', { name: table.name }))
  expect(onSelectTable).toHaveBeenCalledWith(table.id)
})

test('retains the authorized record window and offers retry after a next-page failure', () => {
  const onLoadMore = vi.fn()
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '当前视图', view_type: 'grid', status: 'active' }
  render(<BaseCanvas base={base} tables={[table]} views={[view]} table={table} view={view} schema={schema} records={{ ...records, next_cursor: 'cursor-2', has_more: true }} presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name', 'status', 'due'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name', 'status', 'due'] }} loadMoreError onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} onLoadMore={onLoadMore} />)

  expect(screen.getByRole('cell', { name: '发布计划' })).toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('加载失败，请重试。')
  fireEvent.click(screen.getByRole('button', { name: '加载更多记录' }))
  expect(onLoadMore).toHaveBeenCalledWith('cursor-2')
})

test.each(['grid', 'kanban', 'calendar', 'form'])('renders safe relation chips without opaque IDs in %s', (viewType) => {
  const relationSchema = {
    table: schema.table,
    fields: [
      { id: 'field-name', table_id: 'table-1', name: 'Name', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 },
      { id: 'field-customer', table_id: 'table-1', name: 'Customer', key: 'customer', field_type: 'linked_record', required: false, options: {}, order_index: 1 },
      { id: 'field-revenue', table_id: 'table-1', name: 'Revenue', key: 'revenue', field_type: 'lookup', required: false, options: {}, order_index: 2 },
    ],
  }
  const relationRecords = {
    view_id: 'view-1',
    records: [{ id: 'record-1', fields: { name: 'Launch plan', customer: [{ id: 'record-acme', label: 'Acme Co' }], revenue: 42 } }],
    next_cursor: null,
    has_more: false,
  }
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Current view', view_type: viewType, status: 'active' }

  const rendered = render(<BaseCanvas base={base} tables={[table]} views={[view]} table={table} view={view} schema={relationSchema} records={relationRecords} presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: viewType, visible_field_keys: ['name', 'customer', 'revenue'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name', 'customer', 'revenue'] }} onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} />)

  expect(rendered.container).toHaveTextContent('Acme Co')
  expect(rendered.container).toHaveTextContent('42')
  expect(rendered.container).not.toHaveTextContent('record-acme')
  expect(rendered.container.querySelector('.relation-chip')).toBeInTheDocument()
})

test.each(['grid', 'kanban', 'calendar', 'form'])('renders the server-selected %s surface without browser query execution', (viewType) => {
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Server view', view_type: viewType, status: 'active' }
  render(<BaseCanvas base={base} tables={[table]} views={[view]} table={table} view={view} schema={schema} records={records} presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: viewType, visible_field_keys: ['name', 'status', 'due'], group_by_field_key: viewType === 'kanban' ? 'status' : null, date_field_key: viewType === 'calendar' ? 'due' : null, form_field_keys: ['name', 'status', 'due'] }} serverQuerySummary="服务端已应用 1 条筛选、1 条排序" onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} />)

  expect(screen.getByTestId(`view-${viewType}`)).toBeVisible()
  expect(screen.getByLabelText('服务器查询摘要')).toHaveTextContent('服务端已应用 1 条筛选、1 条排序')
})
