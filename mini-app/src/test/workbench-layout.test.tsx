import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { BaseCanvas } from '../app/BaseCanvas'
import { DigitalEmployeeManagementWorkbench } from '../app/DigitalEmployeeManagementWorkbench'
import { DraftEmployeeHub } from '../app/DraftEmployeeHub'
import { TeamBotWorkbench } from '../app/TeamBotWorkbench'
import { WorkspaceHome } from '../app/WorkspaceHome'

test('connects a queued draft to its loaded Base from the Home workbench', () => {
  const onOpenBase = vi.fn()
  render(<WorkspaceHome
    workspace={{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }}
    home={{ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户运营', source_type: 'blank' }], queue: [{ id: 'queue-1', kind: 'draft', title: '确认客户回访草稿', status: 'pending', destination: { base_id: 'base-1', draft_id: 'draft-1' }, action_availability: { can_confirm: true, can_reject: true } }] }}
    onOpenBase={onOpenBase}
  />)

  expect(screen.getByTestId('workspace-home-workbench')).toBeVisible()
  expect(screen.queryByRole('button', { name: /搜索/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /按时间排序/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /快速查找记录/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /新建记录/ })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '打开关联 Base 客户运营' }))
  expect(onOpenBase).toHaveBeenCalledWith({ id: 'base-1', name: '客户运营', source_type: 'blank' })
})

test('renders a factual Base context rail beside the table work surface', () => {
  const table = { id: 'table-1', base_id: 'base-1', name: '客户表', key: 'customers', status: 'active' }
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '本周跟进', view_type: 'grid', status: 'active' }
  render(<BaseCanvas
    base={{ id: 'base-1', name: '客户运营', source_type: 'blank' }} tables={[table]} views={[view]} table={table} view={view}
    schema={{ table: { id: 'table-1', name: '客户表', key: 'customers' }, fields: [{ id: 'field-1', table_id: 'table-1', name: '客户名称', key: 'customer_name', field_type: 'text', required: false, options: {}, order_index: 0 }] }}
    records={{ view_id: 'view-1', records: [{ id: 'record-1', fields: { customer_name: '明日璀璨' } }], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['customer_name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['customer_name'] }}
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()}
  />)

  const rail = screen.getByTestId('base-workbench-context')
  expect(rail).toHaveTextContent('客户表')
  expect(rail).toHaveTextContent('本周跟进')
  expect(rail).toHaveTextContent('1 条可访问记录')
})

test('marks the Bot, draft and employee surfaces as full three-pane workbenches', () => {
  const teamProps = {
    contacts: [{ id: 'employee-1', baseId: 'base-1', name: '项目助手', description: '安全汇总', availableIntents: ['summarize'] as const }],
    context: { employee: { id: 'employee-1', name: '项目助手', description: '安全汇总', baseId: 'base-1' }, views: [{ id: 'view-1', name: '本周跟进', viewType: 'grid' as const }], nextCursor: null, hasMore: false },
    selectedView: { id: 'view-1', name: '本周跟进', viewType: 'grid' as const, baseId: 'base-1' }, summary: null, loading: false, failed: false,
    onSelectContact: vi.fn(), onSelectView: vi.fn(), onSummarize: vi.fn().mockResolvedValue(undefined), onOpenBase: vi.fn(), onRetry: vi.fn(), onClose: vi.fn(),
  }
  const employeeContext = { base: { id: 'base-1', name: '客户运营' }, tables: [{ id: 'table-1', name: '客户表' }], views: [{ id: 'view-1', tableId: 'table-1', name: '本周跟进', viewType: 'grid' as const }], members: [{ id: 'member-1', label: '成员一', role: 'operator' as const }] }

  const { rerender } = render(<TeamBotWorkbench {...teamProps} />)
  const teamWorkbench = screen.getByTestId('team-bot-workbench')
  expect(teamWorkbench).toHaveAttribute('data-workbench-layout', 'three-pane')
  expect(teamWorkbench).not.toHaveAttribute('role', 'dialog')
  expect(teamWorkbench).not.toHaveAttribute('aria-modal', 'true')

  rerender(<DraftEmployeeHub contacts={[{ id: 'employee-1', baseId: 'base-1', name: '项目助手', description: '安全汇总', status: 'active', availableIntents: ['summarize'] }]} context={{ baseId: 'base-1', viewId: 'view-1', recordId: null }} draft={null} loading={false} onConfirm={vi.fn()} onReject={vi.fn()} onClose={vi.fn()} />)
  const draftWorkbench = screen.getByTestId('draft-review-workbench')
  expect(draftWorkbench).toHaveAttribute('data-workbench-layout', 'three-pane')
  expect(draftWorkbench).not.toHaveAttribute('role', 'dialog')
  expect(draftWorkbench).not.toHaveAttribute('aria-modal', 'true')

  rerender(<DigitalEmployeeManagementWorkbench context={employeeContext} directory={{ baseId: 'base-1', employees: [], nextCursor: null, hasMore: false }} detail={null} loading={false} onSelectEmployee={vi.fn()} onCreate={vi.fn().mockResolvedValue(undefined)} onUpdate={vi.fn().mockResolvedValue(undefined)} onReplaceGrants={vi.fn().mockResolvedValue(undefined)} onActivate={vi.fn().mockResolvedValue(undefined)} onPause={vi.fn().mockResolvedValue(undefined)} onClose={vi.fn()} />)
  const employeeWorkbench = screen.getByTestId('digital-employee-workbench')
  expect(employeeWorkbench).toHaveAttribute('data-workbench-layout', 'three-pane')
  expect(employeeWorkbench).not.toHaveAttribute('role', 'dialog')
  expect(employeeWorkbench).not.toHaveAttribute('aria-modal', 'true')
})
