import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { AppShell } from '../app/AppShell'
import '../styles.css'

const workspace = {
  id: 'workspace-1',
  name: '运营中心',
  slug: 'operations',
  role: 'owner',
  capabilities: {
    can_read_bases: true,
    can_manage_workspace: false,
    can_manage_schema: true,
    can_review_drafts: false,
  },
}

test('uses desktop and mobile Home/Base controls as route actions', () => {
  const onNavigate = vi.fn()
  render(<AppShell workspace={workspace} workspaces={[workspace]} onWorkspaceChange={vi.fn()} activeRoute="home" onNavigate={onNavigate}><main>内容</main></AppShell>)

  const desktopNavigation = within(screen.getByRole('complementary', { name: '主导航' }))
  const mobileNavigation = within(screen.getByRole('navigation', { name: '移动导航' }))
  expect(desktopNavigation.getByRole('button', { name: '工作区：查看今日事项' })).toHaveClass('active')
  expect(mobileNavigation.getByRole('button', { name: '工作区：查看今日事项' })).toHaveClass('active')
  expect(desktopNavigation.getByRole('button', { name: '工作区：查看今日事项' })).toHaveAttribute('aria-current', 'page')
  expect(mobileNavigation.getByRole('button', { name: '工作区：查看今日事项' })).toHaveAttribute('aria-current', 'page')
  expect(desktopNavigation.getByRole('button', { name: '待确认：即将上线' })).not.toHaveAttribute('aria-current')
  expect(mobileNavigation.getByRole('button', { name: '更多：即将上线' })).not.toHaveAttribute('aria-current')
  fireEvent.click(desktopNavigation.getByRole('button', { name: 'Bases：浏览和打开多维表格' }))
  fireEvent.click(mobileNavigation.getByRole('button', { name: 'Bases：浏览和打开多维表格' }))
  fireEvent.click(desktopNavigation.getByRole('button', { name: '工作区：查看今日事项' }))

  expect(onNavigate.mock.calls).toEqual([['bases'], ['bases'], ['home']])
})

test('shows visible Chinese labels and usage descriptions for desktop navigation actions', () => {
  render(<AppShell workspace={workspace} workspaces={[workspace]} onWorkspaceChange={vi.fn()} activeRoute="home" onNavigate={vi.fn()}><main>内容</main></AppShell>)

  const desktopNavigation = within(screen.getByRole('complementary', { name: '主导航' }))
  const basesButton = desktopNavigation.getByRole('button', { name: 'Bases：浏览和打开多维表格' })
  expect(basesButton).toHaveTextContent('Bases')
  expect(within(basesButton).getByText('浏览和打开多维表格')).toBeVisible()
  expect(within(desktopNavigation.getByRole('button', { name: '工作区：查看今日事项' })).getByText('查看今日事项')).toBeVisible()
})

test('marks only the selected Base controls active', () => {
  render(<AppShell workspace={workspace} workspaces={[workspace]} onWorkspaceChange={vi.fn()} activeRoute="bases" onNavigate={vi.fn()}><main>内容</main></AppShell>)

  const desktopNavigation = within(screen.getByRole('complementary', { name: '主导航' }))
  const mobileNavigation = within(screen.getByRole('navigation', { name: '移动导航' }))
  expect(desktopNavigation.getByRole('button', { name: 'Bases：浏览和打开多维表格' })).toHaveClass('active')
  expect(mobileNavigation.getByRole('button', { name: 'Bases：浏览和打开多维表格' })).toHaveClass('active')
  expect(desktopNavigation.getByRole('button', { name: 'Bases：浏览和打开多维表格' })).toHaveAttribute('aria-current', 'page')
  expect(mobileNavigation.getByRole('button', { name: 'Bases：浏览和打开多维表格' })).toHaveAttribute('aria-current', 'page')
  expect(desktopNavigation.getByRole('button', { name: '工作区：查看今日事项' })).not.toHaveClass('active')
  expect(mobileNavigation.getByRole('button', { name: '工作区：查看今日事项' })).not.toHaveClass('active')
})

test('does not render Telegram launch controls in a desktop browser workspace', () => {
  render(<AppShell workspace={workspace} workspaces={[workspace]} onWorkspaceChange={vi.fn()} activeRoute="home" onNavigate={vi.fn()} telegramState={{ kind: 'windowed' }} onOpenBrowser={vi.fn()}><main>内容</main></AppShell>)

  expect(screen.queryByLabelText('工作台打开方式')).not.toBeInTheDocument()
})

test('opens real supported destinations and has Chinese usage hints', () => {
  const onOpenDraftHub = vi.fn()
  const onOpenTeamBot = vi.fn()
  const onOpenGovernance = vi.fn()
  const rendered = render(
    <AppShell
      workspace={{ ...workspace, capabilities: { ...workspace.capabilities, can_manage_workspace: true } }}
      workspaces={[workspace]}
      onWorkspaceChange={vi.fn()}
      activeRoute="home"
      onNavigate={vi.fn()}
      onOpenDraftHub={onOpenDraftHub}
      onOpenTeamBot={onOpenTeamBot}
      onOpenGovernance={onOpenGovernance}
    >
      <main>内容</main>
    </AppShell>,
  )

  const desktopNavigation = within(screen.getByRole('complementary', { name: '主导航' }))
  const mobileNavigation = within(screen.getByRole('navigation', { name: '移动导航' }))
  const draftButton = desktopNavigation.getByRole('button', { name: '待确认：查看待处理草稿' })
  const teamBotButton = desktopNavigation.getByRole('button', { name: '团队 Bot：使用已授权团队助手' })
  fireEvent.click(draftButton)
  fireEvent.click(teamBotButton)
  fireEvent.click(desktopNavigation.getByRole('button', { name: '成员与权限：管理成员与权限' }))
  fireEvent.click(mobileNavigation.getByRole('button', { name: '待确认：查看待处理草稿' }))
  fireEvent.click(mobileNavigation.getByRole('button', { name: '团队 Bot：使用已授权团队助手' }))

  expect(onOpenDraftHub).toHaveBeenCalledTimes(2)
  expect(onOpenTeamBot).toHaveBeenCalledTimes(2)
  expect(onOpenGovernance).toHaveBeenCalledTimes(1)
  expect(draftButton).toHaveAttribute('title', '待确认：查看待处理草稿')
  expect(draftButton).toHaveAttribute('data-nav-hint', '查看待处理草稿')
  expect(desktopNavigation.getByRole('button', { name: '消息：即将上线' })).toBeDisabled()
  expect(desktopNavigation.getByRole('button', { name: '消息：即将上线' })).toHaveAttribute('data-availability', 'planned')
  expect(rendered.container.querySelectorAll('a.nav-item, a.mobile-nav-item')).toHaveLength(0)

  for (const item of rendered.container.querySelectorAll<HTMLElement>('.nav-item, .mobile-nav-item')) {
    expect(item.tagName).toBe('BUTTON')
    expect(item).toHaveAttribute('title')
    expect(item).toHaveAttribute('aria-label')
    expect(item).toHaveAttribute('data-nav-hint')
  }
})

test.each([
  { missingEntry: 'Draft Hub', missingButton: '待确认：即将上线', availableButton: '团队 Bot：使用已授权团队助手' },
  { missingEntry: 'Team Bot', missingButton: '团队 Bot：即将上线', availableButton: '待确认：查看待处理草稿' },
])('plans and disables a missing $missingEntry action without disabling the other real action', ({ missingEntry, missingButton, availableButton }) => {
  const onNavigate = vi.fn()
  const onOpenDraftHub = missingEntry === 'Team Bot' ? vi.fn() : undefined
  const onOpenTeamBot = missingEntry === 'Draft Hub' ? vi.fn() : undefined
  render(<AppShell workspace={workspace} workspaces={[workspace]} onWorkspaceChange={vi.fn()} activeRoute="home" onNavigate={onNavigate} onOpenDraftHub={onOpenDraftHub} onOpenTeamBot={onOpenTeamBot}><main>内容</main></AppShell>)

  const desktopNavigation = within(screen.getByRole('complementary', { name: '主导航' }))
  const mobileNavigation = within(screen.getByRole('navigation', { name: '移动导航' }))
  const missingButtons = [
    desktopNavigation.getByRole('button', { name: missingButton }),
    mobileNavigation.getByRole('button', { name: missingButton }),
  ]

  for (const button of missingButtons) {
    expect(button).toHaveAttribute('data-availability', 'planned')
    expect(button).toBeDisabled()
    fireEvent.click(button)
  }

  expect(desktopNavigation.getByRole('button', { name: availableButton })).not.toBeDisabled()
  expect(mobileNavigation.getByRole('button', { name: availableButton })).not.toBeDisabled()
  expect(onNavigate).not.toHaveBeenCalled()
})

test('hides desktop governance and plans mobile More for non-managers', () => {
  const onOpenGovernance = vi.fn()
  render(
    <AppShell
      workspace={{ ...workspace, capabilities: { ...workspace.capabilities, can_manage_workspace: false } }}
      workspaces={[workspace]}
      onWorkspaceChange={vi.fn()}
      activeRoute="home"
      onNavigate={vi.fn()}
      onOpenGovernance={onOpenGovernance}
    >
      <main>内容</main>
    </AppShell>,
  )

  const desktopNavigation = within(screen.getByRole('complementary', { name: '主导航' }))
  const mobileNavigation = within(screen.getByRole('navigation', { name: '移动导航' }))
  expect(desktopNavigation.queryByRole('button', { name: '成员与权限：管理成员与权限' })).not.toBeInTheDocument()

  const moreButton = mobileNavigation.getByRole('button', { name: '更多：即将上线' })
  expect(moreButton).toHaveAttribute('data-availability', 'planned')
  expect(moreButton).toBeDisabled()
  fireEvent.click(moreButton)
  expect(onOpenGovernance).not.toHaveBeenCalled()
})

test('opens every additional supported workbench from the mobile More menu', () => {
  const onOpenCollaboration = vi.fn()
  const onOpenMemory = vi.fn()
  render(<AppShell
    workspace={{ ...workspace, capabilities: { ...workspace.capabilities, can_manage_workspace: false } }}
    workspaces={[workspace]}
    onWorkspaceChange={vi.fn()}
    activeRoute="home"
    onNavigate={vi.fn()}
    onOpenCollaboration={onOpenCollaboration}
    onOpenMemory={onOpenMemory}
  >
    <main>内容</main>
  </AppShell>)

  const mobileNavigation = within(screen.getByRole('navigation', { name: '移动导航' }))
  const moreButton = mobileNavigation.getByRole('button', { name: '更多：打开其他工作台' })
  expect(moreButton).toHaveAttribute('aria-expanded', 'false')
  expect(moreButton).toHaveAttribute('aria-controls', 'mobile-more-menu')
  fireEvent.click(moreButton)
  expect(moreButton).toHaveAttribute('aria-expanded', 'true')
  const moreMenu = within(screen.getByLabelText('更多工作台'))
  fireEvent.click(moreMenu.getByRole('button', { name: '智能协作：基于受权业务、记忆和知识协作' }))
  expect(onOpenCollaboration).toHaveBeenCalledOnce()

  fireEvent.click(mobileNavigation.getByRole('button', { name: '更多：打开其他工作台' }))
  fireEvent.click(within(screen.getByLabelText('更多工作台')).getByRole('button', { name: '记忆与知识：查看长期记忆与知识边界' }))
  expect(onOpenMemory).toHaveBeenCalledOnce()
})

test.each([320, 375, 900])('puts the mobile header before in-flow fullscreen controls at %ipx', (width) => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
  const rendered = render(<AppShell workspace={workspace} workspaces={[workspace]} onWorkspaceChange={vi.fn()} activeRoute="home" onNavigate={vi.fn()} isTelegramMiniApp telegramState={{ kind: 'windowed' }} onOpenBrowser={vi.fn()}><main>内容</main></AppShell>)

  const header = rendered.container.querySelector('.mobile-header')
  const controls = screen.getByRole('complementary', { name: '工作台打开方式' })
  if (!header) throw new Error('Expected mobile header')
  expect(header.compareDocumentPosition(controls) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  expect(getComputedStyle(controls).position).toBe('static')
  expect(screen.getByRole('button', { name: '进入专注全屏' })).toBeVisible()
  expect(screen.getByRole('button', { name: '在浏览器打开完整工作台' })).toBeVisible()
})
