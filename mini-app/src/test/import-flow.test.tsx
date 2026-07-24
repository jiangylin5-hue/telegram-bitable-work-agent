import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())

function stubCommittedImportWithOpenFailure(failurePath: string, failureStatus: number) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === failurePath) return Promise.resolve(json({ detail: 'post-commit open unavailable' }, failureStatus))
    const responses: Record<string, unknown> = {
      '/mini-app/bootstrap': {
        identity: { user_id: 'owner-1', source: 'header' },
        workspaces: [{
          id: 'workspace-1',
          name: 'Acme',
          slug: 'acme',
          role: 'owner',
          capabilities: {
            can_read_bases: true,
            can_manage_workspace: true,
            can_manage_schema: true,
            can_review_drafts: false,
          },
        }],
      },
      '/workspaces/workspace-1/home': {
        workspace_id: 'workspace-1',
        recent_bases: [{ id: 'base-1', name: 'Imported CRM', source_type: 'import' }],
        queue: [],
      },
      '/templates': { templates: [] },
      '/workspaces/workspace-1/imports': {
        id: 'job-1',
        workspace_id: 'workspace-1',
        base_id: null,
        source_type: 'csv',
        status: 'awaiting_confirmation',
        detected_schema: [{ key: 'name', name: 'Name', field_type: 'text' }],
        preview_rows: [{ name: 'Ada' }],
        mapping: [{ source_key: 'name', target_key: 'name', field_type: 'text' }],
      },
      '/imports/job-1/commit': {
        import_job_id: 'job-1',
        status: 'committed',
        resource_map: { base_id: 'base-1', table_id: 'table-1' },
      },
      '/workspaces/workspace-1/bases': {
        bases: [{ id: 'base-1', name: 'Imported CRM', source_type: 'import', status: 'active' }],
      },
      '/bases/base-1/tables': {
        tables: [{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }],
      },
      '/bases/base-1/views': {
        views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }],
      },
      '/tables/table-1/schema': {
        table: { id: 'table-1', name: 'Customers', key: 'customers' },
        fields: [],
      },
      '/views/view-1/presentation': {
        view_id: 'view-1',
        table_id: 'table-1',
        view_type: 'grid',
        visible_field_keys: [],
        group_by_field_key: null,
        date_field_key: null,
        form_field_keys: [],
      },
      '/views/view-1/records': {
        view_id: 'view-1',
        records: [],
        next_cursor: null,
        has_more: false,
      },
    }
    return Promise.resolve(path in responses ? json(responses[path]) : json({ detail: 'unexpected' }, 404))
  }))
}

async function submitWorkspaceImport() {
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '模板与导入' }))
  fireEvent.click(await screen.findByRole('button', { name: '导入到新 Base' }))
  const file = new File(['Name\nAda\n'], 'customers.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: () => Promise.resolve('Name\nAda\n') })
  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))
  await screen.findByText('Ada')
  fireEvent.change(screen.getByLabelText('Base 名称'), { target: { value: 'Imported CRM' } })
  fireEvent.click(screen.getByRole('button', { name: '确认创建数据表' }))
}

test('starts a workspace import from the authorized template hub', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'owner-1', source: 'header' }, workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/templates') return Promise.resolve(json({ templates: [] }))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '模板与导入' }))
  fireEvent.click(await screen.findByRole('button', { name: '导入到新 Base' }))

  expect(await screen.findByRole('heading', { name: '导入数据表' })).toBeVisible()
})

test('returns focus to the exact Base action that opened an in-Base import', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    const responses: Record<string, unknown> = {
      '/mini-app/bootstrap': {
        identity: { user_id: 'owner-1', source: 'header' },
        workspaces: [{ id: 'workspace-1', name: 'Acme', slug: 'acme', role: 'owner', capabilities: { can_read_bases: true, can_manage_workspace: true, can_manage_schema: true, can_review_drafts: false } }],
      },
      '/workspaces/workspace-1/home': { workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: 'CRM', source_type: 'blank' }], queue: [] },
      '/bases/base-1/tables': { tables: [{ id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' }] },
      '/bases/base-1/views': { views: [{ id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Grid', view_type: 'grid', status: 'active' }] },
      '/tables/table-1/schema': { table: { id: 'table-1', name: 'Customers', key: 'customers' }, fields: [] },
      '/views/view-1/presentation': { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] },
      '/views/view-1/records': { view_id: 'view-1', records: [], next_cursor: null, has_more: false },
      '/views/view-1/builder': { detail: 'unavailable' },
    }
    return Promise.resolve(path in responses ? json(responses[path]) : json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'CRM' }))
  const moreActions = await screen.findByRole('button', { name: '更多 Base 操作' })
  fireEvent.click(moreActions)
  fireEvent.click(screen.getByRole('button', { name: '导入到当前 Base' }))
  expect(await screen.findByRole('heading', { name: '导入数据表' })).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: '关闭导入' }))
  await waitFor(() => expect(moreActions).toHaveFocus())
})

test('keeps a committed import successful when opening its Base fails', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({
      identity: { user_id: 'owner-1', source: 'header' },
      workspaces: [{
        id: 'workspace-1',
        name: 'Acme',
        slug: 'acme',
        role: 'owner',
        capabilities: {
          can_read_bases: true,
          can_manage_workspace: true,
          can_manage_schema: true,
          can_review_drafts: false,
        },
      }],
    }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/templates') return Promise.resolve(json({ templates: [] }))
    if (path === '/workspaces/workspace-1/imports') return Promise.resolve(json({
      id: 'job-1',
      workspace_id: 'workspace-1',
      base_id: null,
      source_type: 'csv',
      status: 'awaiting_confirmation',
      detected_schema: [{ key: 'name', name: 'Name', field_type: 'text' }],
      preview_rows: [{ name: 'Ada' }],
      mapping: [{ source_key: 'name', target_key: 'name', field_type: 'text' }],
    }))
    if (path === '/imports/job-1/commit') return Promise.resolve(json({
      import_job_id: 'job-1',
      status: 'committed',
      resource_map: { base_id: 'base-1', table_id: 'table-1' },
    }))
    if (path === '/workspaces/workspace-1/bases') return Promise.resolve(json({ detail: 'readback unavailable' }, 503))
    return Promise.resolve(json({ detail: 'unexpected' }, 404))
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '模板与导入' }))
  fireEvent.click(await screen.findByRole('button', { name: '导入到新 Base' }))

  const file = new File(['Name\nAda\n'], 'customers.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: () => Promise.resolve('Name\nAda\n') })
  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))
  await screen.findByText('Ada')
  fireEvent.change(screen.getByLabelText('Base 名称'), { target: { value: 'Imported CRM' } })
  fireEvent.click(screen.getByRole('button', { name: '确认创建数据表' }))

  expect(await screen.findByText('已创建数据表')).toBeVisible()
  expect(screen.getByText('数据表已创建；暂时无法自动打开，可从 Bases 重新进入。')).toBeVisible()
  expect(screen.queryByText('导入暂时无法继续，请稍后重试。')).not.toBeInTheDocument()
})

test('preserves the safe Home and receipt when a later committed Base request fails', async () => {
  stubCommittedImportWithOpenFailure('/tables/table-1/schema', 503)

  await submitWorkspaceImport()

  expect(await screen.findByText('已创建数据表')).toBeVisible()
  expect(screen.getByText('数据表已创建；暂时无法自动打开，可从 Bases 重新进入。')).toBeVisible()
  expect(screen.queryByRole('main', { name: '网络错误' })).not.toBeInTheDocument()
})

test.each([
  [401, '/workspaces/workspace-1/bases'],
  [403, '/bases/base-1/tables'],
])('shows a cache-safe committed notice before the HTTP %i denied terminal state', async (status, failurePath) => {
  stubCommittedImportWithOpenFailure(failurePath, status)

  await submitWorkspaceImport()

  const denied = await screen.findByRole('main', { name: '无工作区访问权限' })
  expect(denied).toHaveTextContent('数据表已创建')
  expect(denied).toHaveTextContent('从 Telegram 重新打开工作区')
  expect(denied).not.toHaveTextContent('base-1')
  expect(denied).not.toHaveTextContent('table-1')
  expect(screen.queryByRole('heading', { name: '导入数据表' })).not.toBeInTheDocument()
  expect(screen.queryByRole('main', { name: '网络错误' })).not.toBeInTheDocument()
})
