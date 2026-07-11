import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { ViewAccessPanel } from '../app/ViewAccessPanel'
import type { ViewBuilderResponse } from '../app/view-builder-types'

const baseBuilder: ViewBuilderResponse = {
  view: { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Priority', view_type: 'grid', scope: 'private', caller_access_level: 'owner', status: 'active', is_default: false },
  presentation: { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['title'], filters: [], sort_rules: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] },
  fields: [],
  members: [{ user_id: 'member-1', label: 'Member One', access_level: 'viewer' }],
  version: 2,
  can_edit_presentation: true,
  can_replace_members: true,
}

test('lets only the owner replace the complete member grant list', async () => {
  const onSave = vi.fn().mockResolvedValue(undefined)
  render(<ViewAccessPanel builder={baseBuilder} candidates={[{ id: 'member-1', label: 'Member One' }, { id: 'member-2', label: 'Member Two' }]} onSave={onSave} onClose={() => undefined} />)

  fireEvent.change(screen.getByLabelText('Member Two 权限'), { target: { value: 'editor' } })
  fireEvent.click(screen.getByRole('button', { name: '保存成员权限' }))

  await waitFor(() => expect(onSave).toHaveBeenCalledWith({
    expected_version: 2,
    members: [
      { user_id: 'member-1', access_level: 'viewer' },
      { user_id: 'member-2', access_level: 'editor' },
    ],
  }))
})

test.each(['editor', 'viewer'] as const)('does not render grant controls for %s access', (access) => {
  render(<ViewAccessPanel builder={{ ...baseBuilder, view: { ...baseBuilder.view, caller_access_level: access }, can_replace_members: false }} candidates={[{ id: 'member-1', label: 'Member One' }]} onSave={vi.fn()} onClose={() => undefined} />)

  expect(screen.queryByRole('button', { name: '保存成员权限' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Member One 权限')).not.toBeInTheDocument()
  expect(screen.getByText('仅视图所有者可以管理成员权限')).toBeVisible()
})
