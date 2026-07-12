import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { GovernanceWriteWorkbench } from '../app/GovernanceWriteWorkbench'

const policy = { owner: 'write', admin: 'write', builder: 'write', operator: 'read', viewer: 'hidden' } as const

test('submits only an assignable versioned role and never renders raw response detail', async () => {
  const onChangeRole = vi.fn().mockResolvedValue(undefined)
  render(<GovernanceWriteWorkbench
    bases={[{ id: 'base-1', name: 'CRM', source_type: 'manual' }]}
    tables={[]}
    views={[]}
    members={{ workspaceId: 'workspace-1', members: [{ id: 'member-1', userId: 'operator-1', role: 'operator', status: 'active', version: 1, assignableRoles: ['builder', 'operator', 'viewer'] }], nextCursor: null, hasMore: false }}
    fields={null}
    selectedBaseId={null}
    selectedTableId={null}
    membersLoading={false}
    tablesLoading={false}
    fieldsLoading={false}
    onSelectBase={vi.fn()}
    onSelectTable={vi.fn()}
    onChangeRole={onChangeRole}
    onReplacePolicy={vi.fn()}
    onOpenViewAccess={vi.fn()}
    onClose={vi.fn()}
  />)

  fireEvent.change(screen.getByLabelText('成员 operator-1 的角色'), { target: { value: 'builder' } })
  fireEvent.click(screen.getByRole('button', { name: '确认改为 builder' }))

  await waitFor(() => expect(onChangeRole).toHaveBeenCalledWith('member-1', 'builder', 1))
  expect(screen.queryByText('raw-server-detail')).not.toBeInTheDocument()
})

test('retains a typed policy after a conflict and keeps owner permission fixed', async () => {
  const onReplacePolicy = vi.fn().mockRejectedValue({ status: 409, detail: 'raw-server-detail' })
  const onReloadFields = vi.fn().mockResolvedValue(undefined)
  render(<GovernanceWriteWorkbench
    bases={[{ id: 'base-1', name: 'CRM', source_type: 'manual' }]}
    tables={[{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }]}
    views={[]}
    members={null}
    fields={{ tableId: 'table-1', fields: [{ id: 'field-1', key: 'internal', label: 'Internal', fieldType: 'text', policy, permissionVersion: 1 }] }}
    selectedBaseId="base-1"
    selectedTableId="table-1"
    membersLoading={false}
    tablesLoading={false}
    fieldsLoading={false}
    onSelectBase={vi.fn()}
    onSelectTable={vi.fn()}
    onChangeRole={vi.fn()}
    onReplacePolicy={onReplacePolicy}
    onReloadFields={onReloadFields}
    onOpenViewAccess={vi.fn()}
    onClose={vi.fn()}
  />)

  expect(screen.getByLabelText('字段 Internal 的 owner 权限')).toBeDisabled()
  fireEvent.change(screen.getByLabelText('字段 Internal 的 viewer 权限'), { target: { value: 'read' } })
  fireEvent.click(screen.getByRole('button', { name: '确认字段权限' }))

  await screen.findByText('数据已更新，请重新读取后再提交。')
  expect(screen.getByLabelText('字段 Internal 的 viewer 权限')).toHaveValue('read')
  expect(screen.queryByText('raw-server-detail')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '重新读取字段权限' }))
  await waitFor(() => expect(onReloadFields).toHaveBeenCalledOnce())
})

test('only offers existing restricted views owned by the caller to the V1 access editor', () => {
  const onOpenViewAccess = vi.fn()
  render(<GovernanceWriteWorkbench
    bases={[{ id: 'base-1', name: 'CRM', source_type: 'manual' }]}
    tables={[]}
    views={[
      { id: 'view-safe', base_id: 'base-1', table_id: 'table-1', name: 'Restricted pipeline', view_type: 'grid', status: 'active', scope: 'restricted', caller_access_level: 'owner' },
      { id: 'view-private', base_id: 'base-1', table_id: 'table-1', name: 'Private pipeline', view_type: 'grid', status: 'active', scope: 'private', caller_access_level: 'owner' },
      { id: 'view-viewer', base_id: 'base-1', table_id: 'table-1', name: 'Someone else', view_type: 'grid', status: 'active', scope: 'restricted', caller_access_level: 'viewer' },
      { id: 'view-system', base_id: 'base-1', table_id: 'table-1', name: 'Default', view_type: 'grid', status: 'active', scope: 'system_default', caller_access_level: 'owner' },
    ]}
    members={null}
    fields={null}
    selectedBaseId="base-1"
    selectedTableId={null}
    membersLoading={false}
    tablesLoading={false}
    fieldsLoading={false}
    onSelectBase={vi.fn()}
    onSelectTable={vi.fn()}
    onChangeRole={vi.fn()}
    onReplacePolicy={vi.fn()}
    onOpenViewAccess={onOpenViewAccess}
    onClose={vi.fn()}
  />)

  expect(screen.getByRole('option', { name: 'Restricted pipeline' })).toBeInTheDocument()
  expect(screen.queryByRole('option', { name: 'Private pipeline' })).not.toBeInTheDocument()
  expect(screen.queryByRole('option', { name: 'Someone else' })).not.toBeInTheDocument()
  expect(screen.queryByRole('option', { name: 'Default' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '打开已有视图访问设置' }))
  expect(onOpenViewAccess).toHaveBeenCalledWith('view-safe')
})
