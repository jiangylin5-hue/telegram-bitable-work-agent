import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { BuilderCreatePanel } from '../app/BuilderCreatePanel'
import { BaseCanvas } from '../app/BaseCanvas'
import { WorkspaceHome } from '../app/WorkspaceHome'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('Base mode validates names and submits its default first table', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('crypto', { randomUUID: () => 'base-attempt-1' })

  render(<BuilderCreatePanel mode="base" onSubmit={onSubmit} onClose={() => undefined} />)

  const baseName = screen.getByLabelText('Base 名称')
  expect(baseName).toHaveFocus()
  expect(screen.getByLabelText('首张表名称')).toHaveValue('数据表')
  fireEvent.change(baseName, { target: { value: '  ' } })
  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))
  expect(onSubmit).not.toHaveBeenCalled()
  expect(screen.getByRole('alert')).toHaveTextContent('请填写 Base 名称。')

  fireEvent.change(baseName, { target: { value: '客户运营' } })
  fireEvent.click(screen.getByRole('button', { name: '创建 Base' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(
    { baseName: '客户运营', tableName: '数据表' },
    'base-attempt-1',
  ))
})

test('table mode keeps the same idempotency key after a retryable failure', async () => {
  const onSubmit = vi.fn()
    .mockRejectedValueOnce(new Error('network'))
    .mockResolvedValueOnce(undefined)
  vi.stubGlobal('crypto', { randomUUID: () => 'table-attempt-1' })

  render(<BuilderCreatePanel mode="table" onSubmit={onSubmit} onClose={() => undefined} />)

  expect(screen.queryByLabelText('Base 名称')).not.toBeInTheDocument()
  const tableName = screen.getByLabelText('数据表名称')
  expect(tableName).toHaveFocus()
  expect(tableName).toHaveValue('数据表')
  fireEvent.change(tableName, { target: { value: '待办' } })
  fireEvent.click(screen.getByRole('button', { name: '创建数据表' }))
  expect(screen.getByRole('button', { name: '创建中…' })).toBeDisabled()
  expect(await screen.findByRole('alert')).toHaveTextContent('创建失败，请稍后重试。')
  fireEvent.click(screen.getByRole('button', { name: '创建数据表' }))

  await waitFor(() => expect(onSubmit).toHaveBeenNthCalledWith(
    2,
    { tableName: '待办' },
    'table-attempt-1',
  ))
})

test('closing the panel does not submit', () => {
  const onClose = vi.fn()
  const onSubmit = vi.fn().mockResolvedValue(undefined)

  render(<BuilderCreatePanel mode="table" onSubmit={onSubmit} onClose={onClose} />)
  fireEvent.click(screen.getByRole('button', { name: '取消' }))

  expect(onClose).toHaveBeenCalledOnce()
  expect(onSubmit).not.toHaveBeenCalled()
})

test('creation entries are shown only when the server capability permits schema management', () => {
  const workspace = {
    id: 'workspace-1',
    name: '运营中心',
    slug: 'operations',
    role: 'viewer',
    capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false },
  }
  const home = { workspace_id: 'workspace-1', recent_bases: [], queue: [] }
  const table = { id: 'table-1', base_id: 'base-1', name: '客户', key: 'customers', status: 'active' }
  const view = { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: '所有记录', view_type: 'grid', status: 'active' }
  const schema = { table: { id: 'table-1', name: '客户', key: 'customers' }, fields: [{ id: 'field-1', name: '名称', key: 'name', field_type: 'text', required: false, order_index: 0 }] }
  const records = { view_id: 'view-1', records: [], next_cursor: null, has_more: false }
  const presentation = { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['name'], group_by_field_key: null, date_field_key: null, form_field_keys: ['name'] }

  const { rerender } = render(<WorkspaceHome home={home} workspace={workspace} onOpenBase={() => undefined} onCreateBase={() => undefined} />)
  expect(screen.queryByRole('button', { name: '新建 Base' })).not.toBeInTheDocument()
  rerender(<WorkspaceHome home={home} workspace={{ ...workspace, capabilities: { ...workspace.capabilities, can_manage_schema: true } }} onOpenBase={() => undefined} onCreateBase={() => undefined} />)
  expect(screen.getByRole('button', { name: '新建 Base' })).toBeInTheDocument()

  rerender(<BaseCanvas base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }} tables={[table]} views={[view]} table={table} view={view} schema={schema} records={records} presentation={presentation} onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} canManageSchema={false} onCreateTable={() => undefined} />)
  expect(screen.queryByRole('button', { name: '新建表' })).not.toBeInTheDocument()
  rerender(<BaseCanvas base={{ id: 'base-1', name: 'CRM', source_type: 'blank' }} tables={[table]} views={[view]} table={table} view={view} schema={schema} records={records} presentation={presentation} onBack={() => undefined} onOpenRecord={() => undefined} onSelectView={() => undefined} canManageSchema onCreateTable={() => undefined} />)
  expect(screen.getByRole('button', { name: '新建表' })).toBeInTheDocument()
})
