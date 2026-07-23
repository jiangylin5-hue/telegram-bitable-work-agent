import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { CollaborationWorkbench } from '../app/CollaborationWorkbench'

test('runs a safe read-only collaboration query and renders only safe evidence labels', async () => {
  const onInvoke = vi.fn().mockResolvedValue({
    status: 'completed', answer: '建议先确认预算，再安排复盘。', citations: [{ ordinal: 1, label: 'business_data' }, { ordinal: 2, label: 'group_context' }], degradationCodes: [], draftId: null,
  })
  render(<CollaborationWorkbench
    contacts={[{ id: 'employee-1', baseId: 'base-1', name: '客户协作员工', description: '跟进和风险建议', status: 'active', availableIntents: ['summarize', 'draft_update'] }]}
    currentRecordId={null}
    loading={false}
    failed={false}
    result={null}
    onInvoke={onInvoke}
    onOpenDraft={vi.fn()}
    onRetry={vi.fn()}
    onClose={vi.fn()}
  />)

  fireEvent.click(screen.getByRole('button', { name: '选择数字员工 客户协作员工' }))
  fireEvent.change(screen.getByLabelText('协作问题'), { target: { value: '这个客户下一步怎么推进？' } })
  fireEvent.click(screen.getByRole('button', { name: '开始协作' }))

  await vi.waitFor(() => expect(onInvoke).toHaveBeenCalledWith({ employeeId: 'employee-1', intent: 'mixed', query: '这个客户下一步怎么推进？', requestedAction: 'read_only', targetRecordId: null }))
  expect(await screen.findByText('建议先确认预算，再安排复盘。')).toBeVisible()
  expect(screen.getByText('业务表格')).toBeVisible()
  expect(screen.getByText('已使用受权群聊上下文作为证据')).toBeVisible()
  expect(screen.queryByText('provider_response')).not.toBeInTheDocument()
})

test('requires an already-open record before it exposes draft creation and hands an approved draft to the existing review flow', async () => {
  const onOpenDraft = vi.fn()
  const onInvoke = vi.fn().mockResolvedValue({ status: 'draft_pending', answer: '已生成一份待确认草稿。', citations: [], degradationCodes: [], draftId: 'draft-1' })
  render(<CollaborationWorkbench
    contacts={[{ id: 'employee-1', baseId: 'base-1', name: '客户协作员工', description: '跟进和风险建议', status: 'active', availableIntents: ['summarize', 'draft_update'] }]}
    currentRecordId="record-1"
    loading={false}
    failed={false}
    result={null}
    onInvoke={onInvoke}
    onOpenDraft={onOpenDraft}
    onRetry={vi.fn()}
    onClose={vi.fn()}
  />)

  fireEvent.click(screen.getByRole('button', { name: '选择数字员工 客户协作员工' }))
  fireEvent.change(screen.getByLabelText('协作问题'), { target: { value: '请起草下一步更新。' } })
  fireEvent.change(screen.getByLabelText('执行方式'), { target: { value: 'draft_update' } })
  fireEvent.click(screen.getByRole('button', { name: '开始协作' }))
  await vi.waitFor(() => expect(onInvoke).toHaveBeenCalledWith({ employeeId: 'employee-1', intent: 'mixed', query: '请起草下一步更新。', requestedAction: 'draft_update', targetRecordId: 'record-1' }))

  fireEvent.click(await screen.findByRole('button', { name: '查看待确认草稿' }))
  expect(onOpenDraft).toHaveBeenCalledWith('draft-1')
})
