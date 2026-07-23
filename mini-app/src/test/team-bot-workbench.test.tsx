import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { TeamBotWorkbench } from '../app/TeamBotWorkbench'

const contact = {
  id: 'employee-1',
  baseId: 'base-1',
  name: '团队助手',
  description: '汇总成员当前可访问的视图。',
  availableIntents: ['summarize'] as const,
}

const context = {
  employee: { id: 'employee-1', name: '团队助手', description: '汇总成员当前可访问的视图。', baseId: 'base-1' },
  views: [{ id: 'view-1', name: '本周任务', viewType: 'grid' as const }],
  nextCursor: null,
  hasMore: false,
}

test('keeps team knowledge separate from personal memory and direct record changes', () => {
  const onClose = vi.fn()
  render(
    <TeamBotWorkbench
      contacts={[contact]}
      context={context}
      selectedView={{ id: 'view-1', name: '本周任务', viewType: 'grid', baseId: 'base-1' }}
      summary={null}
      loading={false}
      failed={false}
      onSelectContact={vi.fn()}
      onSelectView={vi.fn()}
      onSummarize={vi.fn()}
      onOpenBase={vi.fn()}
      onRetry={vi.fn()}
      onClose={onClose}
    />,
  )

  expect(screen.getByRole('region', { name: '团队 Bot' })).toBeInTheDocument()
  expect(screen.getByLabelText('团队助手目录')).toBeVisible()
  expect(screen.getByLabelText('已授权视图')).toBeVisible()
  expect(screen.getByLabelText('团队摘要与审计')).toBeVisible()
  expect(screen.getByText('仅汇总当前成员可访问的团队视图；不会保存个人对话或记忆。')).toBeVisible()
  const returnButton = screen.getByRole('button', { name: '返回工作区' })
  expect(returnButton).toBeVisible()
  fireEvent.click(returnButton)
  expect(onClose).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: '打开 Base 继续处理' })).toBeEnabled()
  expect(screen.queryByRole('button', { name: /创建草稿|直接写入|记录选择/ })).not.toBeInTheDocument()
})

test('bounds one-shot instruction and renders only safe receipt details', async () => {
  const onSummarize = vi.fn().mockResolvedValue(undefined)
  render(
    <TeamBotWorkbench
      contacts={[contact]}
      context={context}
      selectedView={{ id: 'view-1', name: '本周任务', viewType: 'grid', baseId: 'base-1' }}
      summary={{
        kind: 'summary',
        employeeId: 'employee-1',
        baseId: 'base-1',
        viewId: 'view-1',
        answer: '本周任务需要负责人确认。',
        citations: [{ recordId: 'record-1' }],
        knowledgeWindowTruncated: true,
        auditEventId: 'audit-1',
      }}
      loading={false}
      failed={false}
      onSelectContact={vi.fn()}
      onSelectView={vi.fn()}
      onSummarize={onSummarize}
      onOpenBase={vi.fn()}
      onRetry={vi.fn()}
      onClose={vi.fn()}
    />,
  )

  const instruction = screen.getByLabelText('补充说明')
  fireEvent.change(instruction, { target: { value: '请只关注本周阻塞项。' } })
  expect(instruction).toHaveAttribute('maxlength', '600')
  fireEvent.click(screen.getByRole('button', { name: '生成团队摘要' }))
  await waitFor(() => expect(onSummarize).toHaveBeenCalledWith('请只关注本周阻塞项。'))
  expect(screen.getByText('本周任务需要负责人确认。')).toBeVisible()
  expect(screen.getByLabelText('团队对话记录')).toHaveTextContent('本周任务需要负责人确认。')
  expect(screen.getByText('record-1')).toBeVisible()
  expect(screen.getByText('仅展示前 100 条当前可访问记录的摘要。')).toBeVisible()
  expect(screen.getByText('审计回执')).toBeVisible()
  expect(screen.getByText('audit-1')).toBeVisible()
})
