import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { expect, test, vi } from 'vitest'

import { DigitalEmployeeManagementWorkbench } from '../app/DigitalEmployeeManagementWorkbench'
import type { ManagedEmployeeDetail } from '../app/digital-employee-management-types'

const context = {
  base: { id: 'base-1', name: '客户' },
  tables: [
    { id: 'table-1', name: '客户表' },
    { id: 'table-2', name: '项目表' },
  ],
  views: [
    { id: 'view-1', tableId: 'table-1', name: '全部客户', viewType: 'grid' as const },
    { id: 'view-2', tableId: 'table-2', name: '全部项目', viewType: 'kanban' as const },
  ],
  members: [{ id: 'member-1', label: '成员 1', role: 'operator' as const }],
}

const draft: ManagedEmployeeDetail = {
  id: 'employee-1', name: '客户助手', description: '安全汇总客户', status: 'draft' as const,
  accessMode: 'assigned' as const, tableCount: 0, viewCount: 0, memberCount: 0, version: 1,
  baseId: 'base-1', telegramAlias: null, accessibleTableIds: [], accessibleViewIds: [], allowedActions: ['summarize' as const], memberIds: [],
}

function renderWorkbench(detail = draft, overrides: Partial<ComponentProps<typeof DigitalEmployeeManagementWorkbench>> = {}) {
  return render(<DigitalEmployeeManagementWorkbench
    context={context}
    directory={{ baseId: 'base-1', employees: [detail], nextCursor: null, hasMore: false }}
    detail={detail}
    loading={false}
    onSelectEmployee={vi.fn()}
    onCreate={vi.fn().mockResolvedValue(undefined)}
    onUpdate={vi.fn().mockResolvedValue(undefined)}
    onReplaceGrants={vi.fn().mockResolvedValue(undefined)}
    onActivate={vi.fn().mockResolvedValue(undefined)}
    onPause={vi.fn().mockResolvedValue(undefined)}
    onClose={vi.fn()}
    {...overrides}
  />)
}

test('renders only bounded employee management controls and filters views by selected table', () => {
  renderWorkbench()

  expect(screen.getByRole('region', { name: '数字员工管理' })).toBeInTheDocument()
  expect(screen.getByLabelText('员工名称')).toBeInTheDocument()
  expect(screen.getByLabelText('员工说明')).toBeInTheDocument()
  expect(screen.getByLabelText('Telegram 别名')).toBeInTheDocument()
  expect(screen.getByLabelText('范围表 客户表')).toBeInTheDocument()
  expect(screen.getByLabelText('允许摘要')).toBeInTheDocument()
  expect(screen.getByLabelText('访问范围 assigned')).toBeInTheDocument()
  expect(screen.getByLabelText('可用成员 成员 1')).toBeInTheDocument()
  expect(screen.queryByLabelText(/模型|provider|prompt|memory|knowledge|记录搜索/i)).not.toBeInTheDocument()
  expect(screen.queryByLabelText('范围视图 全部客户')).not.toBeInTheDocument()

  fireEvent.click(screen.getByLabelText('范围表 客户表'))
  expect(screen.getByLabelText('范围视图 全部客户')).toBeInTheDocument()
  expect(screen.queryByLabelText('范围视图 全部项目')).not.toBeInTheDocument()
})

test('renders a read-only status and audit rail without exposing hidden runtime configuration', () => {
  renderWorkbench()

  const reviewRail = screen.getByLabelText('运行状态与审计')
  expect(reviewRail).toBeVisible()
  expect(screen.getByText('当前生命周期')).toBeVisible()
  expect(screen.getByText('确认约束')).toBeVisible()
  expect(screen.getByText('审计说明')).toBeVisible()
  expect(screen.queryByText(/provider|prompt|memory|模型配置/i)).not.toBeInTheDocument()
})

test('requires persisted valid safe scope and assignment before activation, while active is read-only', async () => {
  const onActivate = vi.fn().mockResolvedValue(undefined)
  const { rerender } = renderWorkbench(draft, { onActivate })

  expect(screen.getByRole('button', { name: '激活员工' })).toBeDisabled()
  fireEvent.click(screen.getByLabelText('范围表 客户表'))
  fireEvent.click(screen.getByLabelText('范围视图 全部客户'))
  fireEvent.click(screen.getByLabelText('可用成员 成员 1'))
  expect(screen.getByRole('button', { name: '激活员工' })).toBeDisabled()
  expect(screen.getByText('请先保存当前配置和成员，然后激活员工。')).toBeVisible()

  rerender(<DigitalEmployeeManagementWorkbench
    context={context}
    directory={{ baseId: 'base-1', employees: [draft], nextCursor: null, hasMore: false }}
    detail={{ ...draft, accessibleTableIds: ['table-1'], accessibleViewIds: ['view-1'], memberIds: ['member-1'] }}
    loading={false}
    onSelectEmployee={vi.fn()}
    onCreate={vi.fn()}
    onUpdate={vi.fn()}
    onReplaceGrants={vi.fn()}
    onActivate={onActivate}
    onPause={vi.fn()}
    onClose={vi.fn()}
  />)
  expect(screen.getByRole('button', { name: '激活员工' })).toBeEnabled()
  expect(screen.queryByText('请先保存当前配置和成员，然后激活员工。')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '激活员工' }))
  await waitFor(() => expect(onActivate).toHaveBeenCalledWith('employee-1', 1))
  await waitFor(() => expect(screen.getByRole('button', { name: '激活员工' })).toBeEnabled())

  rerender(<DigitalEmployeeManagementWorkbench
    context={context}
    directory={{ baseId: 'base-1', employees: [{ ...draft, status: 'active', version: 4 }], nextCursor: null, hasMore: false }}
    detail={{ ...draft, status: 'active', version: 4 }}
    loading={false}
    onSelectEmployee={vi.fn()}
    onCreate={vi.fn()}
    onUpdate={vi.fn()}
    onReplaceGrants={vi.fn()}
    onActivate={vi.fn()}
    onPause={vi.fn()}
    onClose={vi.fn()}
  />)
  expect(screen.getByLabelText('员工名称')).toBeDisabled()
  expect(screen.getByRole('button', { name: '暂停员工' })).toBeEnabled()
})

test('keeps paused configuration editable and shows fixed conflict copy without raw server detail', async () => {
  const onUpdate = vi.fn().mockRejectedValue({ status: 409, detail: 'raw-server-detail' })
  const onReload = vi.fn().mockResolvedValue(undefined)
  const onClose = vi.fn()
  renderWorkbench({ ...draft, status: 'paused', version: 5 }, { onUpdate, onReload, onClose })

  expect(screen.getByLabelText('员工名称')).toBeEnabled()
  fireEvent.change(screen.getByLabelText('员工名称'), { target: { value: '已暂停助手' } })
  fireEvent.click(screen.getByRole('button', { name: '保存配置' }))

  await screen.findByText('配置已被其他操作更新，请重新读取后再试。')
  expect(screen.queryByText('raw-server-detail')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '重新读取员工配置' }))
  await waitFor(() => expect(onReload).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByRole('button', { name: '关闭数字员工管理' }))
  expect(onClose).toHaveBeenCalledOnce()
})
