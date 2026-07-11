import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { ApiError, type PlatformTable, type TableSchema } from '../app/api'
import { RelationLookupFieldBuilderPanel } from '../app/RelationLookupFieldBuilderPanel'

const orders: PlatformTable = { id: 'table-orders', base_id: 'base-1', name: '订单', key: 'orders', status: 'active' }
const customers: PlatformTable = { id: 'table-customers', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }
const schemas: TableSchema[] = [
  {
    table: { id: orders.id, name: orders.name, key: orders.key },
    fields: [
      { id: 'field-customer', table_id: orders.id, name: '客户关联', key: 'customer', field_type: 'linked_record', required: false, options: {}, order_index: 0 },
      { id: 'field-note', table_id: orders.id, name: '备注', key: 'note', field_type: 'text', required: false, options: {}, order_index: 1 },
    ],
  },
  {
    table: { id: customers.id, name: customers.name, key: customers.key },
    fields: [
      { id: 'field-name', table_id: customers.id, name: '客户名称', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 },
      { id: 'field-total', table_id: customers.id, name: '累计金额', key: 'total', field_type: 'number', required: false, options: {}, order_index: 1 },
      { id: 'field-link', table_id: customers.id, name: '其他关联', key: 'other', field_type: 'linked_record', required: false, options: {}, order_index: 2 },
    ],
  },
]

afterEach(() => {
  vi.unstubAllGlobals()
})

test('relation builder submits only the approved relation values without raw configuration', async () => {
  vi.stubGlobal('crypto', { randomUUID: () => 'relation-attempt-1' })
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  render(<RelationLookupFieldBuilderPanel currentTableId={orders.id} tables={[orders, customers]} schemas={schemas} onSubmit={onSubmit} onClose={() => undefined} />)

  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户' } })
  fireEvent.change(screen.getByLabelText('关联目标表'), { target: { value: customers.id } })
  fireEvent.click(screen.getByLabelText('设为必填字段'))
  fireEvent.click(screen.getByRole('button', { name: '创建关联字段' }))

  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ kind: 'relation', name: '客户', targetTableId: customers.id, required: true }, 'relation-attempt-1'))
  expect(screen.queryByText(/target_table_id|options|policy|formula|table-customers/)).not.toBeInTheDocument()
})

test('lookup builder offers only source relations and fixed compatible aggregations', () => {
  render(<RelationLookupFieldBuilderPanel currentTableId={orders.id} tables={[orders, customers]} schemas={schemas} onSubmit={vi.fn()} onClose={() => undefined} />)

  fireEvent.click(screen.getByRole('button', { name: '查找' }))
  const source = screen.getByLabelText('关联字段')
  expect(source).toHaveTextContent('客户关联')
  expect(source).not.toHaveTextContent('备注')

  fireEvent.change(screen.getByLabelText('目标字段'), { target: { value: 'field-name' } })
  const aggregation = screen.getByLabelText('聚合方式')
  expect(aggregation).toHaveTextContent('values')
  expect(aggregation).toHaveTextContent('count')
  expect(aggregation).toHaveTextContent('count_distinct')
  expect(aggregation).not.toHaveTextContent('sum')
  expect(aggregation).not.toHaveTextContent('average')
  expect(screen.queryByLabelText(/公式|表达式|JSON|options|policy/i)).not.toBeInTheDocument()
})

test('keeps a retry key only for the same network retry and locks after conflict', async () => {
  vi.stubGlobal('crypto', { randomUUID: vi.fn().mockReturnValueOnce('relation-attempt-1').mockReturnValueOnce('relation-attempt-2') })
  const onSubmit = vi.fn().mockRejectedValueOnce(new ApiError(503)).mockRejectedValueOnce(new ApiError(409))
  render(<RelationLookupFieldBuilderPanel currentTableId={orders.id} tables={[orders, customers]} schemas={schemas} onSubmit={onSubmit} onClose={() => undefined} />)

  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户' } })
  fireEvent.change(screen.getByLabelText('关联目标表'), { target: { value: customers.id } })
  fireEvent.click(screen.getByRole('button', { name: '创建关联字段' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('创建失败，请稍后重试。')

  fireEvent.click(screen.getByRole('button', { name: '创建关联字段' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('创建请求发生冲突，请关闭后重新创建。')
  expect(screen.getByRole('button', { name: '创建关联字段' })).toBeDisabled()
  expect(screen.getByLabelText('字段名称')).toBeDisabled()
  expect(onSubmit).toHaveBeenNthCalledWith(1, { kind: 'relation', name: '客户', targetTableId: customers.id, required: false }, 'relation-attempt-1')
  expect(onSubmit).toHaveBeenNthCalledWith(2, { kind: 'relation', name: '客户', targetTableId: customers.id, required: false }, 'relation-attempt-1')
})
