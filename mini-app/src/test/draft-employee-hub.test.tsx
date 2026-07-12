import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { DraftEmployeeHub } from '../app/DraftEmployeeHub'

test('renders only safe draft fields and submits a versioned terminal action', async () => {
  const onConfirm = vi.fn().mockResolvedValue(undefined)
  render(<DraftEmployeeHub
    contacts={[{ id: 'employee-1', baseId: 'base-1', name: '运营助理', description: '安全摘要', status: 'active', availableIntents: ['summarize', 'draft_update'] }]}
    draft={{ id: 'draft-1', baseId: 'base-1', tableId: 'table-1', recordId: 'record-1', draftType: 'update_record', status: 'pending_confirmation', version: 1, fields: [{ key: 'title', label: '标题', fieldType: 'text', beforeValue: '之前', proposedValue: '之后' }], actions: { canConfirm: true, canReject: true }, terminalAuditEventId: null }}
    loading={false}
    onConfirm={onConfirm}
    onReject={vi.fn()}
    onClose={vi.fn()}
  />)

  expect(screen.getByText('运营助理')).toBeInTheDocument()
  expect(screen.getByText('标题')).toBeInTheDocument()
  expect(screen.queryByText('private-trace')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '确认变更' }))
  await waitFor(() => expect(onConfirm).toHaveBeenCalledWith('draft-1', 1))
})
