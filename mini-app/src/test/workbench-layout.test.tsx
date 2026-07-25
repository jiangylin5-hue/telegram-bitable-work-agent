import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'
import { BaseCanvas } from '../app/BaseCanvas'
import { DigitalEmployeeManagementWorkbench } from '../app/DigitalEmployeeManagementWorkbench'
import { DraftEmployeeHub } from '../app/DraftEmployeeHub'
import { TeamBotWorkbench } from '../app/TeamBotWorkbench'
import { WorkspaceHome } from '../app/WorkspaceHome'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

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

test('opens the operation center from the Home workbench without exposing a fake table action', () => {
  const onOpenTableOperations = vi.fn()
  render(<WorkspaceHome
    workspace={{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }}
    home={{ workspace_id: 'workspace-1', recent_bases: [], queue: [] }}
    onOpenBase={vi.fn()}
    onOpenTableOperations={onOpenTableOperations}
  />)

  fireEvent.click(screen.getByRole('button', { name: '表格操作' }))
  expect(onOpenTableOperations).toHaveBeenCalledOnce()
})

test('offers a factual continue-working path for drafts, bases and team collaboration', () => {
  const onOpenBase = vi.fn()
  const onOpenDraftHub = vi.fn()
  const onOpenTeamBot = vi.fn()
  render(<WorkspaceHome
    workspace={{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }}
    home={{
      workspace_id: 'workspace-1',
      recent_bases: [{ id: 'base-1', name: '客户运营', source_type: 'blank' }],
      queue: [{ id: 'queue-1', kind: 'draft', title: '确认客户回访草稿', status: 'pending', destination: { base_id: 'base-1', draft_id: 'draft-1' }, action_availability: { can_confirm: true, can_reject: true } }],
    }}
    onOpenBase={onOpenBase}
    onOpenDraftHub={onOpenDraftHub}
    onOpenTeamBot={onOpenTeamBot}
  />)

  const continueSection = screen.getByRole('region', { name: '继续处理' })
  fireEvent.click(within(continueSection).getByRole('button', { name: '继续处理待确认草稿' }))
  fireEvent.click(within(continueSection).getByRole('button', { name: '打开可访问 Base 客户运营' }))
  fireEvent.click(within(continueSection).getByRole('button', { name: '继续使用团队 Bot' }))

  expect(onOpenDraftHub).toHaveBeenCalledOnce()
  expect(onOpenBase).toHaveBeenCalledWith({ id: 'base-1', name: '客户运营', source_type: 'blank' })
  expect(onOpenTeamBot).toHaveBeenCalledOnce()
  expect(screen.getByRole('heading', { name: '可访问 Base' })).toBeVisible()
  expect(screen.queryByText(/最近 Base/)).not.toBeInTheDocument()
})

test('offers a direct AI conversation entry from the Home workbench', () => {
  const onOpenCollaboration = vi.fn()
  render(<WorkspaceHome
    workspace={{ id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }}
    home={{ workspace_id: 'workspace-1', recent_bases: [], queue: [] }}
    onOpenBase={vi.fn()}
    onOpenCollaboration={onOpenCollaboration}
  />)

  fireEvent.click(screen.getByRole('button', { name: '打开 AI 对话' }))
  expect(onOpenCollaboration).toHaveBeenCalledOnce()
})

test('turns an empty workspace into three real starting actions instead of a blank canvas', () => {
  const onCreateBase = vi.fn()
  const onOpenTemplateImport = vi.fn()
  const onOpenCollaboration = vi.fn()
  render(<WorkspaceHome
    workspace={{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: true } }}
    home={{ workspace_id: 'workspace-1', recent_bases: [], queue: [], business_context_relations: [] }}
    onOpenBase={vi.fn()}
    onCreateBase={onCreateBase}
    onOpenTemplateImport={onOpenTemplateImport}
    onOpenCollaboration={onOpenCollaboration}
  />)

  const readyState = screen.getByTestId('workspace-ready-state')
  fireEvent.click(within(readyState).getByRole('button', { name: '从工作台新建 Base' }))
  fireEvent.click(within(readyState).getByRole('button', { name: '从 Excel/CSV 导入' }))
  fireEvent.click(within(readyState).getByRole('button', { name: '开始 AI 对话' }))

  expect(onCreateBase).toHaveBeenCalledOnce()
  expect(onOpenTemplateImport).toHaveBeenCalledOnce()
  expect(onOpenCollaboration).toHaveBeenCalledOnce()
})

test('guides an unselected Team Bot through three actionable steps', () => {
  const onSelectContact = vi.fn()
  render(<TeamBotWorkbench
    contacts={[{ id: 'employee-1', baseId: 'base-1', name: '项目助手', description: '安全汇总', availableIntents: ['summarize'] as const }]}
    context={null}
    selectedView={null}
    summary={null}
    loading={false}
    failed={false}
    onSelectContact={onSelectContact}
    onSelectView={vi.fn()}
    onSummarize={vi.fn().mockResolvedValue(undefined)}
    onOpenBase={vi.fn()}
    onRetry={vi.fn()}
    onClose={vi.fn()}
  />)

  const guide = screen.getByRole('region', { name: '团队 Bot 使用步骤' })
  expect(guide).toHaveTextContent('1选择团队助手')
  expect(guide).toHaveTextContent('2选择已授权视图')
  expect(guide).toHaveTextContent('3生成摘要并继续处理')
  fireEvent.click(within(guide).getByRole('button', { name: '选择' }))
  expect(onSelectContact).toHaveBeenCalledWith('employee-1')
})

test('connects an authorized group relationship to employee, customer, project and context indexes', () => {
  const onOpenRecordReference = vi.fn()
  const onOpenEmployeeReference = vi.fn()
  const onOpenAssistantContext = vi.fn()
  render(<WorkspaceHome
    workspace={{ id: 'workspace-1', name: 'Operations', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } }}
    home={{
      workspace_id: 'workspace-1',
      recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }],
      queue: [],
      business_context_relations: [{
        employee: { id: 'employee-1', name: 'Customer Success', base_id: 'base-1', base_name: 'CRM' },
        group: { id: 'group_context:private', label: '已授权群聊 1' },
        customer: { id: 'customer-1', base_id: 'base-1', label: 'Acme Co' },
        project: { id: 'project-1', base_id: 'base-1', label: 'Renewal' },
        mapping_version: 1,
      }],
    }}
    onOpenBase={vi.fn()}
    onOpenRecordReference={onOpenRecordReference}
    onOpenEmployeeReference={onOpenEmployeeReference}
    onOpenAssistantContext={onOpenAssistantContext}
  />)

  expect(screen.getByTestId('business-context-index')).toHaveTextContent('Customer Success')
  expect(screen.getByTestId('business-context-index')).toHaveTextContent('已授权群聊 1')
  fireEvent.click(screen.getByRole('button', { name: '打开客户记录 Acme Co' }))
  fireEvent.click(screen.getByRole('button', { name: '打开项目记录 Renewal' }))
  fireEvent.click(screen.getByRole('button', { name: '打开数字员工 Customer Success' }))
  fireEvent.click(screen.getByRole('button', { name: '查看群聊上下文 已授权群聊 1' }))

  expect(onOpenRecordReference).toHaveBeenNthCalledWith(1, { id: 'customer-1', base_id: 'base-1', label: 'Acme Co' })
  expect(onOpenRecordReference).toHaveBeenNthCalledWith(2, { id: 'project-1', base_id: 'base-1', label: 'Renewal' })
  expect(onOpenEmployeeReference).toHaveBeenCalledTimes(1)
  expect(onOpenEmployeeReference.mock.calls[0][1]).toEqual({ id: 'employee-1', name: 'Customer Success', base_id: 'base-1', base_name: 'CRM' })
  expect(onOpenAssistantContext).toHaveBeenCalledTimes(1)
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

test('renders the same authorized business relationship inside the Base and Team Bot workbenches', () => {
  const onOpenRecordReference = vi.fn()
  const onOpenEmployeeReference = vi.fn()
  const onOpenAssistantContext = vi.fn()
  const relation = {
    employee: { id: 'employee-1', name: 'Customer Success', base_id: 'base-1', base_name: 'CRM' },
    group: { id: 'group_context:private', label: '已授权群聊 1' },
    customer: { id: 'customer-1', base_id: 'base-1', label: 'Acme Co' },
    project: { id: 'project-1', base_id: 'base-1', label: 'Renewal' },
    mapping_version: 1,
  }
  const table = { id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }
  const { rerender } = render(<BaseCanvas
    base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }} tables={[table]} views={[view]} table={table} view={view}
    schema={{ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] }}
    records={{ view_id: 'view-1', records: [], next_cursor: null, has_more: false }}
    presentation={{ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }}
    businessContextRelations={[relation]}
    onOpenRecordReference={onOpenRecordReference}
    onOpenEmployeeReference={onOpenEmployeeReference}
    onOpenAssistantContext={onOpenAssistantContext}
    onBack={vi.fn()} onOpenRecord={vi.fn()} onSelectView={vi.fn()}
  />)

  expect(screen.getByTestId('base-business-context')).toHaveTextContent('Customer Success')
  expect(screen.getByTestId('base-business-context')).toHaveTextContent('Acme Co')
  expect(screen.getByTestId('base-business-context')).not.toHaveTextContent('group_context:private')
  fireEvent.click(screen.getByRole('button', { name: '打开客户记录 Acme Co' }))
  fireEvent.click(screen.getByRole('button', { name: '打开项目记录 Renewal' }))
  fireEvent.click(screen.getByRole('button', { name: '打开数字员工 Customer Success' }))
  fireEvent.click(screen.getByRole('button', { name: '查看群聊上下文 已授权群聊 1' }))

  expect(onOpenRecordReference).toHaveBeenNthCalledWith(1, relation.customer)
  expect(onOpenRecordReference).toHaveBeenNthCalledWith(2, relation.project)
  expect(onOpenEmployeeReference).toHaveBeenCalledWith(expect.any(HTMLElement), relation.employee)
  expect(onOpenAssistantContext).toHaveBeenCalledWith(expect.any(HTMLElement))

  rerender(<TeamBotWorkbench
    contacts={[]}
    context={null}
    selectedView={null}
    summary={null}
    loading={false}
    failed={false}
    businessContextRelations={[relation]}
    onSelectContact={vi.fn()} onSelectView={vi.fn()} onSummarize={vi.fn().mockResolvedValue(undefined)} onOpenBase={vi.fn()} onRetry={vi.fn()} onClose={vi.fn()}
  />)

  expect(screen.getByTestId('team-bot-workbench')).toHaveTextContent('已授权群聊 1')
  expect(screen.getByTestId('team-bot-workbench')).toHaveTextContent('Renewal')
})

function installEmployeeRelationFixture(canManageDigitalEmployees: boolean) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'operator-1', source: 'development_header' },
      workspaces: [{
        id: 'workspace-1',
        name: 'Operations',
        slug: 'operations',
        role: canManageDigitalEmployees ? 'owner' : 'operator',
        capabilities: {
          can_read_bases: true,
          can_manage_workspace: canManageDigitalEmployees,
          can_manage_schema: canManageDigitalEmployees,
          can_manage_digital_employees: canManageDigitalEmployees,
          can_review_drafts: true,
        },
      }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({
      workspace_id: 'workspace-1',
      recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }],
      queue: [],
      business_context_relations: [{
        employee: { id: 'employee-1', name: 'Customer Success', base_id: 'base-1', base_name: 'CRM' },
        group: { id: 'group_context:private', label: '已授权群聊 1' },
        customer: { id: 'customer-1', base_id: 'base-1', label: 'Acme Co' },
        project: { id: 'project-1', base_id: 'base-1', label: 'Renewal' },
        mapping_version: 1,
      }],
    }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'All', view_type: 'grid', status: 'active' }] }))
    if (path === '/tables/table-1/schema') return Promise.resolve(json({ table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] }))
    if (path === '/views/view-1/presentation') return Promise.resolve(json({ view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] }))
    if (path === '/views/view-1/records') return Promise.resolve(json({ view_id: 'view-1', records: [], next_cursor: null, has_more: false }))
    if (path === '/views/view-1/builder') return Promise.resolve(json({ detail: 'unavailable' }, 404))
    if (path === '/mini-app/workspaces/workspace-1/team-bot-contacts?limit=50') return Promise.resolve(json({
      workspace_id: 'workspace-1',
      contacts: [{ id: 'employee-1', base_id: 'base-1', name: 'Customer Success', description: 'Read-only authorized context', available_intents: ['summarize'] }],
      next_cursor: null,
      has_more: false,
    }))
    if (path === '/mini-app/bases/base-1/digital-employee-management-context') return Promise.resolve(json({
      base: { id: 'base-1', name: 'CRM' },
      tables: [{ id: 'table-1', name: 'Customers' }],
      views: [{ id: 'view-1', table_id: 'table-1', name: 'All', view_type: 'grid' }],
      members: [],
    }))
    if (path === '/mini-app/bases/base-1/digital-employees/management?limit=50') return Promise.resolve(json({ base_id: 'base-1', employees: [], next_cursor: null, has_more: false }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

test('opens a read-only Team Bot relationship without calling management APIs when management is unavailable', async () => {
  const fetchMock = installEmployeeRelationFixture(false)
  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))

  fireEvent.click(await screen.findByRole('button', { name: '打开数字员工 Customer Success' }))

  expect(await screen.findByTestId('team-bot-workbench')).toBeVisible()
  expect(fetchMock).toHaveBeenCalledWith('/mini-app/workspaces/workspace-1/team-bot-contacts?limit=50', expect.any(Object))
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('digital-employee-management'))).toBe(false)
  expect(screen.queryByRole('main', { name: '无工作区访问权限' })).not.toBeInTheDocument()
})

test('keeps the existing management relationship entry when management is available', async () => {
  const fetchMock = installEmployeeRelationFixture(true)
  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))

  fireEvent.click(await screen.findByRole('button', { name: '打开数字员工 Customer Success' }))

  await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input) === '/mini-app/bases/base-1/digital-employee-management-context')).toBe(true))
  expect(await screen.findByTestId('digital-employee-workbench')).toBeVisible()
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('team-bot-contacts'))).toBe(false)
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
