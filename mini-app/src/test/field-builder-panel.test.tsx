import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { ApiError } from '../app/api'
import { FieldBuilderPanel } from '../app/FieldBuilderPanel'

afterEach(() => {
  vi.unstubAllGlobals()
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
