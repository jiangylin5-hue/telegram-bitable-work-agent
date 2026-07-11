import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { ApiError } from '../app/api'
import { FieldBuilderPanel } from '../app/FieldBuilderPanel'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('exposes an explicit entry for relation and lookup fields without changing F1 field types', () => {
  const onOpenRelationLookup = vi.fn()
  render(<FieldBuilderPanel onSubmit={vi.fn()} onClose={() => undefined} onOpenRelationLookup={onOpenRelationLookup} />)

  fireEvent.click(screen.getByRole('button', { name: '关联记录与查找' }))

  expect(onOpenRelationLookup).toHaveBeenCalledTimes(1)
  expect(screen.getByLabelText('字段类型')).toHaveTextContent('文本')
  expect(screen.queryByRole('option', { name: '关联记录' })).not.toBeInTheDocument()
})

test('renders a focused field drawer, validates its visible inputs, and exposes choices only when needed', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  render(<FieldBuilderPanel onSubmit={onSubmit} onClose={() => undefined} />)

  expect(screen.getByRole('dialog', { name: '添加字段' })).toBeInTheDocument()
  expect(screen.getByLabelText('字段名称')).toHaveFocus()
  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))
  expect(await screen.findByText('请输入字段名称')).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('字段类型'), { target: { value: 'multi_select' } })
  expect(screen.getByRole('button', { name: '添加选项' })).toBeInTheDocument()
  expect(screen.getByLabelText('选项 1')).toBeInTheDocument()
  expect(screen.queryByLabelText(/字段 key|权限策略|JSON/)).not.toBeInTheDocument()
})

test('preserves the same idempotency key after a temporary failure and locks after a conflict', async () => {
  vi.stubGlobal('crypto', { randomUUID: () => 'field-create-1' })
  const onSubmit = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(503))
    .mockRejectedValueOnce(new ApiError(409))
  render(<FieldBuilderPanel onSubmit={onSubmit} onClose={() => undefined} />)

  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户阶段' } })
  fireEvent.change(screen.getByLabelText('字段类型'), { target: { value: 'status' } })
  fireEvent.change(screen.getByLabelText('选项 1'), { target: { value: '新建' } })
  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('创建失败，请稍后重试。')

  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('创建请求发生冲突，请关闭后重新创建。')
  expect(screen.getByRole('button', { name: '创建字段' })).toBeDisabled()
  expect(onSubmit).toHaveBeenNthCalledWith(1, expect.objectContaining({ name: '客户阶段' }), 'field-create-1')
  expect(onSubmit).toHaveBeenNthCalledWith(2, expect.objectContaining({ name: '客户阶段' }), 'field-create-1')
})

test('renders the fixed duplicate-name feedback without rendering the server message', async () => {
  const duplicate = Object.assign(new ApiError(422), { code: 'duplicate_field_name' })
  const onSubmit = vi.fn().mockRejectedValue(duplicate)
  render(<FieldBuilderPanel onSubmit={onSubmit} onClose={() => undefined} />)

  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户阶段' } })
  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('字段名称已存在，请使用其他名称。')
  expect(screen.queryByText('field_name')).not.toBeInTheDocument()
  expect(screen.getByLabelText('字段名称')).toHaveValue('客户阶段')
})

test('keeps unknown field-initialization codes on the generic safe feedback path', async () => {
  const unrecognised = Object.assign(new ApiError(422), { code: 'field_policy_not_allowed' })
  const onSubmit = vi.fn().mockRejectedValue(unrecognised)
  render(<FieldBuilderPanel onSubmit={onSubmit} onClose={() => undefined} />)

  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户阶段' } })
  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('创建失败，请稍后重试。')
  expect(screen.queryByText('field_policy_not_allowed')).not.toBeInTheDocument()
})

test('shows a pending state and closes without submitting when cancelled', async () => {
  let resolveSubmission: () => void = () => undefined
  const onSubmit = vi.fn(() => new Promise<void>((resolve) => { resolveSubmission = resolve }))
  const onClose = vi.fn()
  render(<FieldBuilderPanel onSubmit={onSubmit} onClose={onClose} />)

  fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '负责人' } })
  fireEvent.click(screen.getByRole('button', { name: '创建字段' }))
  expect(screen.getByRole('button', { name: '创建中…' })).toBeDisabled()
  resolveSubmission()

  await waitFor(() => expect(screen.getByRole('button', { name: '取消' })).not.toBeDisabled())
  fireEvent.click(screen.getByRole('button', { name: '取消' }))
  expect(onClose).toHaveBeenCalledTimes(1)
  expect(onSubmit).toHaveBeenCalledTimes(1)
})
