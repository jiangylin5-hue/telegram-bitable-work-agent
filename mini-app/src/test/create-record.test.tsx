import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { CreateRecordPanel } from '../app/CreateRecordPanel'

test('renders only server-provided fields and submits populated create values', async () => {
  const onCreate = vi.fn().mockResolvedValue(undefined)
  render(<CreateRecordPanel form={{ table_id: 'table-1', can_create: true, fields: [{ key: 'title', name: '标题', field_type: 'text', required: true, options: {}, order_index: 0 }] }} onCreate={onCreate} onClose={() => undefined} />)

  fireEvent.change(screen.getByLabelText('标题'), { target: { value: '发布计划' } })
  fireEvent.click(screen.getByRole('button', { name: '创建记录' }))

  await waitFor(() => expect(onCreate).toHaveBeenCalledWith({ title: '发布计划' }))
  expect(screen.queryByText('permission_policy')).not.toBeInTheDocument()
})
