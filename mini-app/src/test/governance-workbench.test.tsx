import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { GovernanceWorkbench } from '../app/GovernanceWorkbench'

const memberPage = {
  workspaceId: 'workspace-1',
  members: [{ id: 'member-1', userId: 'owner-1', role: 'owner', status: 'active' }],
  nextCursor: 'member-cursor',
  hasMore: true,
}

const auditPage = {
  baseId: 'base-1',
  events: [{
    id: 'audit-1', occurredAt: '2026-07-12T00:00:00Z', actorType: 'user' as const,
    eventType: 'stage06.record_created', entityType: 'record',
  }],
  nextCursor: 'audit-cursor',
  hasMore: true,
}

test('renders safe members and only selected Base audit rows', () => {
  const onSelectBase = vi.fn()
  render(<GovernanceWorkbench
    bases={[{ id: 'base-1', name: 'CRM', source_type: 'manual' }]}
    members={memberPage}
    audit={auditPage}
    selectedBaseId="base-1"
    membersLoading={false}
    auditLoading={false}
    onSelectBase={onSelectBase}
    onLoadMoreMembers={vi.fn()}
    onLoadMoreAudit={vi.fn()}
    onRetryMembers={vi.fn()}
    onRetryAudit={vi.fn()}
    onClose={vi.fn()}
  />)

  expect(screen.getByRole('dialog', { name: '治理工作台' })).toBeVisible()
  expect(screen.getByText('owner-1')).toBeVisible()
  expect(screen.getByText('已记录系统操作')).toBeVisible()
  expect(screen.queryByText('trace-secret')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('选择 Base'), { target: { value: 'base-1' } })
  expect(onSelectBase).toHaveBeenCalledWith('base-1')
})

test('keeps first audit page while only its continuation is retryable', () => {
  const onRetryAudit = vi.fn()
  render(<GovernanceWorkbench
    bases={[{ id: 'base-1', name: 'CRM', source_type: 'manual' }]}
    members={memberPage}
    audit={auditPage}
    selectedBaseId="base-1"
    membersLoading={false}
    auditLoading={false}
    auditLoadMoreError
    onSelectBase={vi.fn()}
    onLoadMoreMembers={vi.fn()}
    onLoadMoreAudit={vi.fn()}
    onRetryMembers={vi.fn()}
    onRetryAudit={onRetryAudit}
    onClose={vi.fn()}
  />)

  expect(screen.getByText('已记录系统操作')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '重试加载更多审计记录' }))
  expect(onRetryAudit).toHaveBeenCalledOnce()
})
