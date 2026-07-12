import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { DraftEmployeeHub } from '../app/DraftEmployeeHub'

test('renders only safe draft fields and submits a versioned terminal action', async () => {
  const onConfirm = vi.fn().mockResolvedValue(undefined)
  render(<DraftEmployeeHub
    contacts={[{ id: 'employee-1', baseId: 'base-1', name: '运营助理', description: '安全摘要', status: 'active', availableIntents: ['summarize', 'draft_update'] }]}
    draft={{ id: 'draft-1', baseId: 'base-1', tableId: 'table-1', recordId: 'record-1', draftType: 'update_record', status: 'pending_confirmation', version: 1, fields: [{ key: 'title', label: '标题', fieldType: 'text', beforeValue: '之前', proposedValue: '之后' }], actions: { canConfirm: true, canReject: true }, terminalAuditEventId: null }}
    loading={false}
    onConfirm={onConfirm}
    onReject={vi.fn()}
    onClose={vi.fn()}
  />)

  expect(screen.getByText('运营助理')).toBeInTheDocument()
  expect(screen.getByText('标题')).toBeInTheDocument()
  expect(screen.queryByText('private-trace')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '确认变更' }))
  await waitFor(() => expect(onConfirm).toHaveBeenCalledWith('draft-1', 1))
})

test('uses only the current Canvas IDs for a safe summary invocation', async () => {
  const onInvoke = vi.fn().mockResolvedValue({
    kind: 'summary', answer: '需要复核 2 条记录。', citations: [{ recordId: 'record-1' }],
  })
  render(<DraftEmployeeHub
    contacts={[{ id: 'employee-1', baseId: 'base-1', name: '运营助手', description: '安全摘要', status: 'active', availableIntents: ['summarize', 'draft_update'] }]}
    context={{ baseId: 'base-1', viewId: 'view-1', recordId: null }}
    draft={null}
    loading={false}
    onConfirm={vi.fn()}
    onReject={vi.fn()}
    onInvoke={onInvoke}
    onClose={vi.fn()}
  />)

  fireEvent.click(screen.getByRole('button', { name: '选择数字员工 运营助手' }))
  fireEvent.click(screen.getByRole('button', { name: '执行摘要' }))

  await waitFor(() => expect(onInvoke).toHaveBeenCalledWith('employee-1', {
    intent: 'summarize', baseId: 'base-1', viewId: 'view-1', instruction: undefined,
  }, undefined))
  expect(screen.getByText('需要复核 2 条记录。')).toBeVisible()
  expect(screen.getByText('record-1')).toBeVisible()
  expect(screen.queryByText('private-trace')).not.toBeInTheDocument()
})

test('does not enable a draft invocation without an open current Canvas record', () => {
  render(<DraftEmployeeHub
    contacts={[{ id: 'employee-1', baseId: 'base-1', name: '运营助手', description: '安全摘要', status: 'active', availableIntents: ['draft_update'] }]}
    context={{ baseId: 'base-1', viewId: 'view-1', recordId: null }}
    draft={null}
    loading={false}
    onConfirm={vi.fn()}
    onReject={vi.fn()}
    onInvoke={vi.fn()}
    onClose={vi.fn()}
  />)

  fireEvent.click(screen.getByRole('button', { name: '选择数字员工 运营助手' }))
  expect(screen.getByRole('button', { name: '创建草稿' })).toBeDisabled()
  expect(screen.getByText(/创建草稿需要先打开当前记录/)).toBeVisible()
})

test('creates a proposal only with the open current Canvas record and a fresh idempotency key', async () => {
  const onInvoke = vi.fn().mockResolvedValue({ kind: 'draft', draftId: 'draft-1', status: 'pending_confirmation' })
  render(<DraftEmployeeHub
    contacts={[{ id: 'employee-1', baseId: 'base-1', name: '运营助手', description: '安全摘要', status: 'active', availableIntents: ['draft_update'] }]}
    context={{ baseId: 'base-1', viewId: 'view-1', recordId: 'record-1' }}
    draft={null}
    loading={false}
    onConfirm={vi.fn()}
    onReject={vi.fn()}
    onInvoke={onInvoke}
    onClose={vi.fn()}
  />)

  fireEvent.click(screen.getByRole('button', { name: '选择数字员工 运营助手' }))
  fireEvent.click(screen.getByRole('button', { name: '创建草稿' }))

  await waitFor(() => expect(onInvoke).toHaveBeenCalledWith('employee-1', {
    intent: 'draft_update', baseId: 'base-1', viewId: 'view-1', recordId: 'record-1', instruction: undefined,
  }, expect.any(String)))
})

test('discards a summary that resolves after the Canvas context changes', async () => {
  let resolveInvocation!: () => void
  let completed = false
  const onInvoke = vi.fn(async () => {
    await new Promise<void>((resolve) => { resolveInvocation = resolve })
    completed = true
    return { kind: 'summary' as const, answer: '过期摘要', citations: [{ recordId: 'record-1' }] }
  })
  const props = {
    contacts: [{ id: 'employee-1', baseId: 'base-1', name: '运营助手', description: '安全摘要', status: 'active' as const, availableIntents: ['summarize' as const] }],
    draft: null,
    loading: false,
    onConfirm: vi.fn(),
    onReject: vi.fn(),
    onInvoke,
    onClose: vi.fn(),
  }
  const rendered = render(<DraftEmployeeHub {...props} context={{ baseId: 'base-1', viewId: 'view-1', recordId: null }} />)

  fireEvent.click(screen.getByRole('button', { name: '选择数字员工 运营助手' }))
  fireEvent.click(screen.getByRole('button', { name: '执行摘要' }))
  rendered.rerender(<DraftEmployeeHub {...props} context={{ baseId: 'base-1', viewId: 'view-2', recordId: null }} />)
  resolveInvocation()

  await waitFor(() => expect(completed).toBe(true))
  expect(screen.queryByText('过期摘要')).not.toBeInTheDocument()
})
