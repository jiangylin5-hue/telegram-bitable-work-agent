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

test('prevents a Vitest-detected unhandled rejection for an initial candidate request', async () => {
  const loadCandidates = vi.fn().mockRejectedValue(new Error('network request failed'))

  render(<RelationPicker fieldId="field-1" value={[]} onChange={vi.fn()} loadCandidates={loadCandidates} />)

  await waitFor(() => expect(loadCandidates).toHaveBeenCalledWith('field-1', '', null))
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Search related records' })).not.toBeDisabled())
  expect(screen.queryByRole('button', { name: 'Acme' })).not.toBeInTheDocument()
})

test('keeps an available candidate page and its cursor when loading the next page fails', async () => {
  const loadCandidates = vi.fn()
    .mockResolvedValueOnce({ field_id: 'field-1', records: [{ id: 'record-1', label: 'Acme' }], next_cursor: 'cursor-2', has_more: true })
    .mockRejectedValueOnce(new Error('network request failed'))

  render(<RelationPicker fieldId="field-1" value={[]} onChange={vi.fn()} loadCandidates={loadCandidates} />)

  expect(await screen.findByRole('button', { name: 'Acme' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Load more' }))

  await waitFor(() => expect(screen.getByRole('button', { name: 'Load more' })).not.toBeDisabled())
  expect(screen.getByRole('button', { name: 'Acme' })).toBeInTheDocument()
})
