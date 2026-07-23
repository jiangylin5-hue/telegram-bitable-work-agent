import { fireEvent, render, screen } from '@testing-library/react'
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

  expect(screen.getByRole('button', { name: '工作区' })).toHaveClass('active')
  expect(screen.getByRole('button', { name: 'Home' })).toHaveClass('active')
  expect(screen.getByRole('button', { name: '工作区' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('button', { name: 'Home' })).toHaveAttribute('aria-current', 'page')
  fireEvent.click(screen.getByRole('button', { name: 'Base' }))
  fireEvent.click(screen.getByRole('button', { name: 'Bases' }))
  fireEvent.click(screen.getByRole('button', { name: '工作区' }))

  expect(onNavigate.mock.calls).toEqual([['bases'], ['bases'], ['home']])
})

test('marks only the selected Base controls active', () => {
  render(<AppShell workspace={workspace} workspaces={[workspace]} onWorkspaceChange={vi.fn()} activeRoute="bases" onNavigate={vi.fn()}><main>内容</main></AppShell>)

  expect(screen.getByRole('button', { name: 'Base' })).toHaveClass('active')
  expect(screen.getByRole('button', { name: 'Bases' })).toHaveClass('active')
  expect(screen.getByRole('button', { name: 'Base' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('button', { name: 'Bases' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('button', { name: '工作区' })).not.toHaveClass('active')
  expect(screen.getByRole('button', { name: 'Home' })).not.toHaveClass('active')
})

test.each([320, 375, 900])('puts the mobile header before in-flow fullscreen controls at %ipx', (width) => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
  const rendered = render(<AppShell workspace={workspace} workspaces={[workspace]} onWorkspaceChange={vi.fn()} activeRoute="home" onNavigate={vi.fn()} telegramState={{ kind: 'windowed' }} onOpenBrowser={vi.fn()}><main>内容</main></AppShell>)

  const header = rendered.container.querySelector('.mobile-header')
  const controls = screen.getByRole('complementary', { name: '工作台打开方式' })
  if (!header) throw new Error('Expected mobile header')
  expect(header.compareDocumentPosition(controls) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  expect(getComputedStyle(controls).position).toBe('static')
  expect(screen.getByRole('button', { name: '进入专注全屏' })).toBeVisible()
  expect(screen.getByRole('button', { name: '在浏览器打开完整工作台' })).toBeVisible()
})
