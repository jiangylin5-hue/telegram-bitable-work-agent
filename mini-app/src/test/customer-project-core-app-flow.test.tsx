import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('keeps the authorized Customer -> Project -> Task route server-backed and free of opaque identifiers', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    const responses: Record<string, unknown> = {
      '/mini-app/bootstrap': {
        identity: { user_id: 'internal-user', source: 'development_header' },
        workspaces: [{
          id: 'workspace-1',
          name: 'Delivery Workspace',
          slug: 'delivery',
          role: 'viewer',
          capabilities: {
            can_read_bases: true,
            can_manage_workspace: false,
            can_manage_schema: false,
            can_review_drafts: false,
          },
        }],
      },
      '/workspaces/workspace-1/home': {
        workspace_id: 'workspace-1',
        recent_bases: [{ id: 'base-1', name: 'Delivery Hub', source_type: 'blank' }],
        queue: [],
      },
      '/bases/base-1/tables': {
        tables: [
          { id: 'project-table', base_id: 'base-1', name: 'Projects', key: 'projects', status: 'active' },
          { id: 'task-table', base_id: 'base-1', name: 'Tasks', key: 'tasks', status: 'active' },
          { id: 'customer-table', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' },
        ],
      },
      '/bases/base-1/views': {
        views: [
          { id: 'project-view', base_id: 'base-1', table_id: 'project-table', name: 'Project Health', view_type: 'grid', status: 'active' },
          { id: 'task-view', base_id: 'base-1', table_id: 'task-table', name: 'Current Tasks', view_type: 'grid', status: 'active' },
        ],
      },
      '/tables/project-table/schema': {
        table: { id: 'project-table', name: 'Projects', key: 'projects' },
        fields: [
          { id: 'project-name', table_id: 'project-table', name: 'Project', key: 'project', field_type: 'text', required: true, options: {}, order_index: 0 },
          { id: 'project-customer', table_id: 'project-table', name: 'Customer', key: 'customer', field_type: 'linked_record', required: true, options: {}, order_index: 1 },
        ],
      },
      '/views/project-view/presentation': {
        view_id: 'project-view',
        table_id: 'project-table',
        view_type: 'grid',
        visible_field_keys: ['project', 'customer'],
        group_by_field_key: null,
        date_field_key: null,
        form_field_keys: ['project', 'customer'],
      },
      '/views/project-view/records': {
        view_id: 'project-view',
        records: [{
          id: 'project-1',
          fields: { project: 'Website renewal', customer: [{ id: 'customer-1', label: 'Sample customer' }] },
        }],
        next_cursor: null,
        has_more: false,
      },
      '/tables/task-table/schema': {
        table: { id: 'task-table', name: 'Tasks', key: 'tasks' },
        fields: [
          { id: 'task-title', table_id: 'task-table', name: 'Task', key: 'task', field_type: 'text', required: true, options: {}, order_index: 0 },
          { id: 'task-project', table_id: 'task-table', name: 'Project', key: 'project', field_type: 'linked_record', required: true, options: {}, order_index: 1 },
          { id: 'task-status', table_id: 'task-table', name: 'Status', key: 'status', field_type: 'status', required: true, options: { choices: ['not_started', 'in_progress', 'blocked', 'waiting_customer', 'done'] }, order_index: 2 },
        ],
      },
      '/views/task-view/presentation': {
        view_id: 'task-view',
        table_id: 'task-table',
        view_type: 'grid',
        visible_field_keys: ['task', 'project', 'status'],
        group_by_field_key: null,
        date_field_key: null,
        form_field_keys: ['task', 'project', 'status'],
      },
      '/views/task-view/records': {
        view_id: 'task-view',
        records: [{
          id: 'task-1',
          fields: { task: 'Confirm delivery date', project: [{ id: 'project-1', label: 'Website renewal' }], status: 'in_progress' },
        }],
        next_cursor: null,
        has_more: false,
      },
      '/records/task-1': {
        id: 'task-1',
        table_id: 'task-table',
        values: { task: 'Confirm delivery date', project: [{ id: 'project-1', label: 'Website renewal' }], status: 'in_progress' },
        record_status: 'active',
        version: 1,
      },
    }
    return Promise.resolve(path in responses ? json(responses[path]) : json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  const view = render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'Delivery Hub' }))
  expect(await screen.findByRole('cell', { name: 'Website renewal' })).toBeInTheDocument()
  expect(screen.getByText('Sample customer')).toBeInTheDocument()
  expect(screen.queryByText('customer-1')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('tab', { name: 'Tasks' }))
  fireEvent.click(await screen.findByRole('cell', { name: 'Confirm delivery date' }))
  expect(await screen.findByRole('complementary', { name: '记录详情' })).toBeInTheDocument()
  expect(screen.queryByText('task-1')).not.toBeInTheDocument()
  expect(screen.queryByText('project-1')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '关闭记录详情' }))
  fireEvent.click(screen.getByRole('tab', { name: 'Projects' }))
  expect(await screen.findByRole('cell', { name: 'Website renewal' })).toBeInTheDocument()
  fireEvent.click(view.container.querySelector('.back-link')!)
  expect(await screen.findByRole('link', { name: 'Delivery Hub' })).toBeInTheDocument()
})
