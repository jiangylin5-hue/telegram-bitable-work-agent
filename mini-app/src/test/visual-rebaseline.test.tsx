import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { AppShell } from '../app/AppShell'

const workspace = {
  id: 'workspace-1',
  name: '运营中心',
  slug: 'operations',
  role: 'owner' as const,
  capabilities: {
    can_read_bases: true,
    can_manage_workspace: true,
    can_manage_schema: true,
    can_review_drafts: true,
  },
}

test('marks the primary navigation as the Stage07 workbench visual system', () => {
  render(
    <AppShell
      workspace={workspace}
      workspaces={[workspace]}
      activeRoute="home"
      onWorkspaceChange={vi.fn()}
      onNavigate={vi.fn()}
    >
      <main>页面内容</main>
    </AppShell>,
  )

  expect(screen.getByLabelText('主导航')).toHaveAttribute('data-visual-system', 'stage07-workbench')
})
