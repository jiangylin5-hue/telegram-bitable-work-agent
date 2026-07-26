import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { ApiError, type RecordDetail } from '../app/api'
import { RecordDetailPanel } from '../app/RecordDetail'

const detail: RecordDetail = { id: 'record-1', table_id: 'table-1', values: { name: 'Ada Co', status: '跟进中' }, record_status: 'active', version: 3 }
const schema = { table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-1', table_id: 'table-1', name: '客户名称', key: 'name', field_type: 'text', required: true, options: {}, order_index: 0 }, { id: 'field-2', table_id: 'table-1', name: '状态', key: 'status', field_type: 'status', required: false, options: {}, order_index: 1 }] }

test('submits a versioned direct human edit and shows the authoritative response', async () => {
  const onSave = vi.fn().mockResolvedValue({ ...detail, values: { name: 'Ada Ltd', status: '跟进中' }, version: 4 })
  render(<RecordDetailPanel detail={detail} schema={schema} onClose={() => undefined} onSave={onSave} />)

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  await waitFor(() => expect(onSave).toHaveBeenCalledWith({ name: 'Ada Ltd' }))
  expect(await screen.findByText('版本 4')).toBeInTheDocument()
})

test('offers the current-record collaboration entry only outside a human edit session', () => {
  const onOpenCollaboration = vi.fn()
  render(<RecordDetailPanel detail={detail} schema={schema} onClose={() => undefined} onSave={vi.fn()} onOpenCollaboration={onOpenCollaboration} />)

  fireEvent.click(screen.getByRole('button', { name: '在当前记录中打开 AI 对话' }))
  expect(onOpenCollaboration).toHaveBeenCalledWith(expect.any(HTMLButtonElement))

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  expect(screen.queryByRole('button', { name: '在当前记录中打开 AI 对话' })).not.toBeInTheDocument()
})

test('shows a conflict state instead of a false successful save', async () => {
  const onSave = vi.fn().mockRejectedValue(new ApiError(409))
  const onConflict = vi.fn().mockResolvedValue({ ...detail, values: { ...detail.values, name: 'Ada Global' }, version: 4 })
  render(<RecordDetailPanel detail={detail} schema={schema} onClose={() => undefined} onSave={onSave} onConflict={onConflict} />)

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Labs' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  expect(await screen.findByText('记录已被更新，已刷新最新版本，请重新编辑。')).toBeInTheDocument()
  expect(onConflict).toHaveBeenCalledOnce()
  expect(screen.getByText('版本 4')).toBeInTheDocument()
  expect(screen.getByText('Ada Global')).toBeInTheDocument()
})

test('normalizes a number field before submitting the changed value', async () => {
  const numericDetail: RecordDetail = { ...detail, values: { ...detail.values, score: 12 } }
  const numericSchema = { ...schema, fields: [...schema.fields, { id: 'field-3', table_id: 'table-1', name: '评分', key: 'score', field_type: 'number', required: false, options: {}, order_index: 2 }] }
  const onSave = vi.fn().mockResolvedValue({ ...numericDetail, values: { ...numericDetail.values, score: 42 }, version: 4 })
  render(<RecordDetailPanel detail={numericDetail} schema={numericSchema} onClose={() => undefined} onSave={onSave} />)

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('评分'), { target: { value: '42' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  await waitFor(() => expect(onSave).toHaveBeenCalledWith({ score: 42 }))
})

test('edits configured select fields from their safe options without constructing unknown choices', async () => {
  const choiceDetail: RecordDetail = { ...detail, values: { status: '新建', tags: ['vip'] } }
  const choiceSchema = {
    table: schema.table,
    fields: [
      { id: 'field-status', table_id: 'table-1', name: '状态', key: 'status', field_type: 'status', required: false, options: { choices: ['新建', '跟进中'] }, order_index: 0 },
      { id: 'field-tags', table_id: 'table-1', name: '标签', key: 'tags', field_type: 'multi_select', required: false, options: { choices: ['vip', 'trial'] }, order_index: 1 },
    ],
  }
  const onSave = vi.fn().mockResolvedValue({ ...choiceDetail, values: { status: '跟进中', tags: ['vip', 'trial'] }, version: 4 })
  render(<RecordDetailPanel detail={choiceDetail} schema={choiceSchema} onClose={() => undefined} onSave={onSave} />)

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByRole('combobox', { name: '状态' }), { target: { value: '跟进中' } })
  fireEvent.click(screen.getByRole('checkbox', { name: 'trial' }))
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  await waitFor(() => expect(onSave).toHaveBeenCalledWith({ status: '跟进中', tags: ['vip', 'trial'] }))
  expect(screen.queryByRole('checkbox', { name: 'unknown' })).not.toBeInTheDocument()
})

test('edits a relation with server candidates, submits opaque IDs, and leaves lookup read-only', async () => {
  const linkedDetail: RecordDetail = {
    ...detail,
    values: {
      customer: [{ id: 'record-acme', label: 'Acme Co' }],
      revenue: 42,
    },
  }
  const linkedSchema = {
    table: schema.table,
    fields: [
      { id: 'field-customer', table_id: 'table-1', name: 'Customer', key: 'customer', field_type: 'linked_record', required: false, options: {}, order_index: 0 },
      { id: 'field-revenue', table_id: 'table-1', name: 'Revenue', key: 'revenue', field_type: 'lookup', required: false, options: {}, order_index: 1 },
    ],
  }
  const loadRelationCandidates = vi.fn().mockResolvedValue({
    field_id: 'field-customer',
    records: [
      { id: 'record-acme', label: 'Acme Co' },
      { id: 'record-beacon', label: 'Beacon Ltd' },
    ],
    next_cursor: null,
    has_more: false,
  })
  const onSave = vi.fn().mockResolvedValue({ ...linkedDetail, version: 4 })

  const view = render(<RecordDetailPanel detail={linkedDetail} schema={linkedSchema} onClose={() => undefined} onSave={onSave} loadRelationCandidates={loadRelationCandidates} />)

  expect(view.container).toHaveTextContent('Acme Co')
  expect(view.container).not.toHaveTextContent('record-acme')
  expect(view.container).toHaveTextContent('42')

  fireEvent.click(view.container.querySelector('.detail-edit')!)
  expect(await screen.findByRole('button', { name: 'Beacon Ltd' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Revenue')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Beacon Ltd' }))
  fireEvent.click(view.container.querySelector('button[type="submit"]')!)

  await waitFor(() => expect(onSave).toHaveBeenCalledWith({ customer: ['record-acme', 'record-beacon'] }))
})

test('excludes the current same-table record from relation picker candidates', async () => {
  const sameTableDetail: RecordDetail = {
    id: 'record-self',
    table_id: 'table-1',
    values: { related: [] },
    record_status: 'active',
    version: 1,
  }
  const sameTableSchema = {
    table: schema.table,
    fields: [
      { id: 'field-related', table_id: 'table-1', name: 'Related records', key: 'related', field_type: 'linked_record', required: false, options: {}, order_index: 0 },
    ],
  }
  const loadRelationCandidates = vi.fn().mockResolvedValue({
    field_id: 'field-related',
    records: [
      { id: 'record-self', label: 'Current record' },
      { id: 'record-other', label: 'Other record' },
    ],
    next_cursor: null,
    has_more: false,
  })

  render(<RecordDetailPanel detail={sameTableDetail} schema={sameTableSchema} onClose={() => undefined} onSave={vi.fn()} loadRelationCandidates={loadRelationCandidates} />)

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))

  expect(await screen.findByRole('button', { name: 'Other record' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Current record' })).not.toBeInTheDocument()
})
