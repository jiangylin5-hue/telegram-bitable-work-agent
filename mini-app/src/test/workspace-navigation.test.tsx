import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../app/App'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

const workspaceOne = {
  id: 'workspace-1',
  name: '运营中心',
  slug: 'operations',
  role: 'viewer',
  capabilities: {
    can_read_bases: true,
    can_manage_workspace: false,
    can_manage_schema: false,
    can_review_drafts: false,
  },
}

const workspaceTwo = {
  ...workspaceOne,
  id: 'workspace-2',
  name: '项目中心',
  slug: 'projects',
}

const basesNavigationName = 'Bases：浏览和打开多维表格'
const desktopNavigation = () => within(screen.getByRole('complementary', { name: '主导航' }))
const findDesktopBasesButton = async () => within(await screen.findByRole('complementary', { name: '主导航' })).getByRole('button', { name: basesNavigationName })

afterEach(() => {
  vi.unstubAllGlobals()
})

test('reads the safe Base directory, opens a selection, and lets Home leave the Base canvas', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'user-1', source: 'development_header' }, workspaces: [workspaceOne] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户运营', source_type: 'blank' }], queue: [] }))
    if (path === '/workspaces/workspace-1/bases') return Promise.resolve(json({ bases: [{ id: 'base-1', name: '客户运营', source_type: 'blank', status: 'active' }] }))
    if (path === '/bases/base-1/tables') return Promise.resolve(json({ tables: [] }))
    if (path === '/bases/base-1/views') return Promise.resolve(json({ views: [] }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await findDesktopBasesButton())

  expect(await screen.findByRole('heading', { name: 'Bases' })).toBeInTheDocument()
  expect(screen.getByText('客户运营')).toBeInTheDocument()
  expect(screen.queryByText('base-1')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '打开 客户运营' }))
  expect(await screen.findByRole('main', { name: 'Base 工作台' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/bases/base-1/tables', expect.anything())

  fireEvent.click(desktopNavigation().getByRole('button', { name: '工作区：查看今日事项' }))
  expect(await screen.findByRole('main', { name: '工作区首页' })).toBeInTheDocument()
})

test.each([401, 403])('fails closed when the Base directory request returns %i', async (status) => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'user-1', source: 'development_header' }, workspaces: [workspaceOne] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/workspaces/workspace-1/bases') return Promise.resolve(json({ detail: 'forbidden' }, status))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await findDesktopBasesButton())

  expect(await screen.findByRole('main', { name: '无工作区访问权限' })).toBeInTheDocument()
})

test('returns Home instead of rendering a fabricated directory when the endpoint is unavailable', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'user-1', source: 'development_header' }, workspaces: [workspaceOne] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户运营', source_type: 'blank' }], queue: [] }))
    if (path === '/workspaces/workspace-1/bases') return Promise.resolve(json({ detail: 'not found' }, 404))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await findDesktopBasesButton())

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/bases', expect.anything()))
  await waitFor(() => expect(desktopNavigation().getByRole('button', { name: basesNavigationName })).not.toHaveClass('active'))
  expect(screen.getByRole('main', { name: '工作区首页' })).toBeInTheDocument()
})

test('renders the fixed empty state for a permitted empty Base scope', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'user-1', source: 'development_header' }, workspaces: [workspaceOne] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/workspaces/workspace-1/bases') return Promise.resolve(json({ bases: [] }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await findDesktopBasesButton())

  expect(await screen.findByText('当前工作区没有可访问的 Base。')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /新建|创建|导入/ })).not.toBeInTheDocument()
})

test('renders fixed retry copy without the server error body for a 5xx directory failure', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'user-1', source: 'development_header' }, workspaces: [workspaceOne] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [], queue: [] }))
    if (path === '/workspaces/workspace-1/bases') return Promise.resolve(json({ detail: 'database topology: private-host' }, 503))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await findDesktopBasesButton())

  expect(await screen.findByText('暂时无法加载 Bases，请稍后重试。')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument()
  expect(screen.queryByText('database topology: private-host')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  await waitFor(() => expect(fetchMock.mock.calls.filter(([path]) => path === '/workspaces/workspace-1/bases')).toHaveLength(2))
})

test('discards an in-flight Base directory response after a workspace switch', async () => {
  let resolveBases: (response: Response) => void = () => undefined
  const delayedBases = new Promise<Response>((resolve) => { resolveBases = resolve })
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/mini-app/bootstrap') return Promise.resolve(json({ identity: { user_id: 'user-1', source: 'development_header' }, workspaces: [workspaceOne, workspaceTwo] }))
    if (path === '/workspaces/workspace-1/home') return Promise.resolve(json({ workspace_id: 'workspace-1', recent_bases: [{ id: 'base-1', name: '客户运营', source_type: 'blank' }], queue: [] }))
    if (path === '/workspaces/workspace-1/bases') return delayedBases
    if (path === '/workspaces/workspace-2/home') return Promise.resolve(json({ workspace_id: 'workspace-2', recent_bases: [{ id: 'base-2', name: '项目跟踪', source_type: 'blank' }], queue: [] }))
    return Promise.resolve(json({ detail: `unexpected ${path}` }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await findDesktopBasesButton())
  fireEvent.change(screen.getByLabelText('切换工作区（桌面）'), { target: { value: 'workspace-2' } })
  expect(await screen.findByRole('link', { name: '项目跟踪' })).toBeInTheDocument()

  await act(async () => {
    resolveBases(json({ bases: [{ id: 'base-1', name: '客户运营', source_type: 'blank' }] }))
    await Promise.resolve()
  })
  await waitFor(() => expect(screen.queryByText('客户运营')).not.toBeInTheDocument())
})
