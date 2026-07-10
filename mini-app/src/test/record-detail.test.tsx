import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { ApiError, type RecordDetail } from '../app/api'
import { RecordDetailPanel } from '../app/RecordDetail'

const detail: RecordDetail = { id: 'record-1', table_id: 'table-1', values: { name: 'Ada Co', status: '跟进中' }, record_status: 'active', version: 3 }
const schema = { table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-1', name: '客户名称', key: 'name', field_type: 'text', required: true, order_index: 0 }, { id: 'field-2', name: '状态', key: 'status', field_type: 'status', required: false, order_index: 1 }] }

test('submits a versioned direct human edit and shows the authoritative response', async () => {
  const onSave = vi.fn().mockResolvedValue({ ...detail, values: { name: 'Ada Ltd', status: '跟进中' }, version: 4 })
  render(<RecordDetailPanel detail={detail} schema={schema} onClose={() => undefined} onSave={onSave} />)

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('客户名称'), { target: { value: 'Ada Ltd' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  await waitFor(() => expect(onSave).toHaveBeenCalledWith({ name: 'Ada Ltd' }))
  expect(await screen.findByText('版本 4')).toBeInTheDocument()
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
  const numericSchema = { ...schema, fields: [...schema.fields, { id: 'field-3', name: '评分', key: 'score', field_type: 'number', required: false, order_index: 2 }] }
  const onSave = vi.fn().mockResolvedValue({ ...numericDetail, values: { ...numericDetail.values, score: 42 }, version: 4 })
  render(<RecordDetailPanel detail={numericDetail} schema={numericSchema} onClose={() => undefined} onSave={onSave} />)

  fireEvent.click(screen.getByRole('button', { name: '编辑记录' }))
  fireEvent.change(screen.getByLabelText('评分'), { target: { value: '42' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))

  await waitFor(() => expect(onSave).toHaveBeenCalledWith({ score: 42 }))
})
