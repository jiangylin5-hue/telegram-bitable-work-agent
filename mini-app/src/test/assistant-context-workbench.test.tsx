import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { AssistantContextWorkbench } from '../app/AssistantContextWorkbench'

const contact = {
  id: 'employee-1',
  baseId: 'base-1',
  name: '运营助理',
  description: '仅汇总授权视图。',
  status: 'active' as const,
  availableIntents: ['summarize' as const],
}

const context = {
  employee: { id: 'employee-1', name: '运营助理', description: '仅汇总授权视图。', baseId: 'base-1' },
  views: [{ id: 'view-1', name: '待处理', viewType: 'grid' as const }],
  nextCursor: null,
  hasMore: false,
}

test('starts without inferred context and exposes only safe contact/view selection', () => {
  const onSelectContact = vi.fn()
  const onSelectView = vi.fn()
  const rendered = render(<AssistantContextWorkbench contacts={[contact]} context={null} selectedView={null} summary={null} loading={false} failed={false} onSelectContact={onSelectContact} onSelectView={onSelectView} onSummarize={vi.fn()} onOpenBase={vi.fn()} onRetry={vi.fn()} onClose={vi.fn()} />)

  expect(screen.getByRole('dialog', { name: '个人助理上下文' })).toBeInTheDocument()
  expect(screen.getByLabelText('数字员工目录')).toBeVisible()
  expect(screen.getByLabelText('当前已授权视图')).toBeVisible()
  expect(screen.getByLabelText('摘要与审计')).toBeVisible()
  expect(screen.getByText('请选择数字员工和可访问视图，再开始协作。')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '选择数字员工 运营助理' }))
  expect(onSelectContact).toHaveBeenCalledWith('employee-1')
  expect(screen.queryByRole('button', { name: '创建草稿' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /记忆|知识|记录/ })).not.toBeInTheDocument()

  rendered.rerender(<AssistantContextWorkbench contacts={[contact]} context={context} selectedView={null} summary={null} loading={false} failed={false} onSelectContact={onSelectContact} onSelectView={onSelectView} onSummarize={vi.fn()} onOpenBase={vi.fn()} onRetry={vi.fn()} onClose={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: '选择视图 待处理' }))
  expect(onSelectView).toHaveBeenCalledWith('view-1')
})

test('summarizes only after a selected-view reread and never renders raw failure detail', async () => {
  const onSummarize = vi.fn().mockResolvedValue(undefined)
  const rendered = render(<AssistantContextWorkbench contacts={[contact]} context={context} selectedView={{ id: 'view-1', name: '待处理', viewType: 'grid', baseId: 'base-1' }} summary={{ answer: '需要复核两条记录。', citations: [{ recordId: 'record-1' }] }} loading={false} failed={false} onSelectContact={vi.fn()} onSelectView={vi.fn()} onSummarize={onSummarize} onOpenBase={vi.fn()} onRetry={vi.fn()} onClose={vi.fn()} />)

  fireEvent.change(screen.getByLabelText('补充说明'), { target: { value: '请汇总' } })
  fireEvent.click(screen.getByRole('button', { name: '执行摘要' }))
  await waitFor(() => expect(onSummarize).toHaveBeenCalledWith('请汇总'))
  expect(screen.getByText('需要复核两条记录。')).toBeVisible()
  expect(screen.getByText('record-1')).toBeVisible()
  expect(screen.getByRole('button', { name: '打开 Base 继续处理' })).toBeEnabled()

  rendered.rerender(<AssistantContextWorkbench contacts={[]} context={null} selectedView={null} summary={null} loading={false} failed={true} onSelectContact={vi.fn()} onSelectView={vi.fn()} onSummarize={vi.fn()} onOpenBase={vi.fn()} onRetry={vi.fn()} onClose={vi.fn()} />)
  expect(screen.getByText('暂时无法读取个人助理上下文，请稍后重试。')).toBeVisible()
  expect(screen.queryByText('database topology: private-host')).not.toBeInTheDocument()
})
