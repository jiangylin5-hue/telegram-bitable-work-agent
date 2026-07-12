import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { AppShell } from '../app/AppShell'

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
