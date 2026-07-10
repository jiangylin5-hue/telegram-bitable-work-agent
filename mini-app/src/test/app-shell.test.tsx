import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('renders only server-authorized workspace navigation and the safe Home queue', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValueOnce(
    new Response(
      JSON.stringify({
        identity: { user_id: 'owner-1', source: 'development_header' },
        workspaces: [
          {
            id: 'workspace-1',
            name: '运营中心',
            slug: 'operations',
            role: 'operator',
            capabilities: {
              can_read_bases: true,
              can_manage_workspace: false,
              can_manage_schema: false,
              can_review_drafts: true,
            },
          },
        ],
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ),
  )
  fetchMock.mockResolvedValueOnce(
    new Response(
      JSON.stringify({
        workspace_id: 'workspace-1',
        recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }],
        queue: [
          {
            id: 'draft-1',
            kind: 'record_change_draft',
            title: '待确认变更',
            status: 'pending_confirmation',
            destination: { base_id: 'base-1', draft_id: 'draft-1' },
            action_availability: { can_confirm: true, can_reject: true },
          },
        ],
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ),
  )

  render(<App />)

  expect(await screen.findByRole('heading', { name: '今天工作' })).toBeInTheDocument()
  expect(screen.getByText('待确认变更')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '客户管理' })).toBeInTheDocument()
  expect(screen.queryByText('成员与权限')).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/mini-app/bootstrap', expect.any(Object))
  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/home', expect.any(Object))
})

test('switching workspace discards the previous Home and loads the selected authorized Home', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify({
      identity: { user_id: 'owner-1', source: 'development_header' },
      workspaces: [
        { id: 'workspace-1', name: '运营中心', slug: 'operations', role: 'operator', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: true } },
        { id: 'workspace-2', name: '项目中心', slug: 'projects', role: 'viewer', capabilities: { can_read_bases: true, can_manage_workspace: false, can_manage_schema: false, can_review_drafts: false } },
      ],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户管理', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: '项目追踪', source_type: 'blank' }], queue: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  render(<App />)
  expect(await screen.findByRole('link', { name: '客户管理' })).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })

  expect(await screen.findByRole('link', { name: '项目追踪' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: '客户管理' })).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-2/home', expect.any(Object))
})
