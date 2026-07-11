import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { RelationPicker } from '../app/RelationPicker'

test('loads server candidates, preserves selection order and loads a cursor page', async () => {
  const onChange = vi.fn()
  const loadCandidates = vi.fn()
    .mockResolvedValueOnce({ field_id: 'field-1', records: [{ id: 'record-1', label: 'Acme' }], next_cursor: 'cursor-2', has_more: true })
    .mockResolvedValueOnce({ field_id: 'field-1', records: [{ id: 'record-2', label: 'Bravo' }], next_cursor: null, has_more: false })
  render(<RelationPicker fieldId="field-1" value={[]} onChange={onChange} loadCandidates={loadCandidates} />)

  expect(await screen.findByRole('button', { name: 'Acme' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Acme' }))
  expect(onChange).toHaveBeenCalledWith([{ id: 'record-1', label: 'Acme' }])
  fireEvent.click(screen.getByRole('button', { name: 'Load more' }))

  await waitFor(() => expect(loadCandidates).toHaveBeenLastCalledWith('field-1', '', 'cursor-2'))
  expect(await screen.findByRole('button', { name: 'Bravo' })).toBeInTheDocument()
})
