import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { ViewBuilderPanel } from '../app/ViewBuilderPanel'
import type { ViewBuilderContext, ViewBuilderResponse } from '../app/view-builder-types'

const context: ViewBuilderContext = {
  table: { id: 'table-1', base_id: 'base-1', name: 'Customers', key: 'customers', status: 'active' },
  fields: [
    { field_id: 'field-title', key: 'title', label: 'Title', field_type: 'text', filter_operators: ['equals', 'is_empty'], filter_values: [], sortable: true, groupable: false, form_eligible: true },
    { field_id: 'field-state', key: 'state', label: 'State', field_type: 'status', filter_operators: ['is', 'is_empty'], filter_values: ['open', 'closed'], sortable: true, groupable: true, form_eligible: true },
  ],
  views: [],
  member_candidates: [{ id: 'member-1', label: 'Member One' }],
}

const ownerBuilder: ViewBuilderResponse = {
  view: { id: 'view-1', base_id: 'base-1', table_id: 'table-1', name: 'Priority', view_type: 'grid', scope: 'private', caller_access_level: 'owner', status: 'active', is_default: false },
  presentation: { view_id: 'view-1', table_id: 'table-1', view_type: 'grid', visible_field_keys: ['title', 'state'], filters: [], sort_rules: [], group_by_field_key: null, date_field_key: null, form_field_keys: [] },
  fields: context.fields,
  members: [],
  version: 1,
  can_edit_presentation: true,
  can_replace_members: true,
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('creates a private view before rendering its owner access panel', async () => {
  vi.stubGlobal('crypto', { randomUUID: () => 'view-create-1' })
  const onCreate = vi.fn().mockResolvedValue(ownerBuilder)

  render(<ViewBuilderPanel context={context} onCreate={onCreate} onSave={vi.fn()} onReplaceMembers={vi.fn()} onClose={() => undefined} />)

  expect(screen.getByText('新建视图')).toBeVisible()
  expect(screen.getByText('创建后默认仅自己可见')).toBeVisible()
  fireEvent.change(screen.getByLabelText('视图名称'), { target: { value: '  Priority  ' } })
  fireEvent.click(screen.getByRole('button', { name: '创建私有视图' }))

  await waitFor(() => expect(onCreate).toHaveBeenCalledWith({
    name: 'Priority',
    view_type: 'grid',
    presentation: {
      view_type: 'grid', visible_field_keys: ['title', 'state'], filters: [], sort_rules: [], group_by_field_key: null,
    },
  }, 'view-create-1'))
  expect(await screen.findByRole('heading', { name: '访问权限' })).toBeVisible()
})

test('uses safe discrete filter choices instead of a raw options editor', () => {
  render(<ViewBuilderPanel context={context} builder={ownerBuilder} onCreate={vi.fn()} onSave={vi.fn()} onReplaceMembers={vi.fn()} onClose={() => undefined} />)

  fireEvent.click(screen.getByRole('button', { name: '添加筛选条件' }))
  fireEvent.change(screen.getByLabelText('筛选字段 1'), { target: { value: 'state' } })

  expect(screen.getByLabelText('筛选值 1')).toHaveTextContent('open')
  expect(screen.getByLabelText('筛选值 1')).toHaveTextContent('closed')
  expect(screen.queryByLabelText(/options|JSON/i)).not.toBeInTheDocument()
})
