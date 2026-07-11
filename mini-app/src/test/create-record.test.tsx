import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { CreateRecordPanel } from '../app/CreateRecordPanel'

test('renders only server-provided fields and submits populated create values', async () => {
  const onCreate = vi.fn().mockResolvedValue(undefined)
  render(<CreateRecordPanel form={{ table_id: 'table-1', can_create: true, fields: [{ id: 'field-title', key: 'title', name: 'Title', field_type: 'text', required: true, options: {}, order_index: 0 }] }} onCreate={onCreate} onClose={() => undefined} />)

  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Launch plan' } })
  fireEvent.submit(document.querySelector('form')!)

  await waitFor(() => expect(onCreate).toHaveBeenCalledWith({ title: 'Launch plan' }))
  expect(screen.queryByText('permission_policy')).not.toBeInTheDocument()
})

test('renders server-filtered status choices as a select control', async () => {
  const onCreate = vi.fn().mockResolvedValue(undefined)
  render(<CreateRecordPanel form={{ table_id: 'table-1', can_create: true, fields: [{ id: 'field-status', key: 'status', name: 'Status', field_type: 'status', required: true, options: { choices: ['new', 'active'] }, order_index: 0 }] }} onCreate={onCreate} onClose={() => undefined} />)

  fireEvent.change(screen.getByRole('combobox', { name: 'Status' }), { target: { value: 'active' } })
  fireEvent.submit(document.querySelector('form')!)

  await waitFor(() => expect(onCreate).toHaveBeenCalledWith({ status: 'active' }))
})

test('submits a distinct multi-select array built only from server choices', async () => {
  const onCreate = vi.fn().mockResolvedValue(undefined)
  render(<CreateRecordPanel form={{ table_id: 'table-1', can_create: true, fields: [{ id: 'field-tags', key: 'tags', name: 'Tags', field_type: 'multi_select', required: true, options: { choices: ['vip', 'trial'] }, order_index: 0 }] }} onCreate={onCreate} onClose={() => undefined} />)

  fireEvent.click(screen.getByRole('checkbox', { name: 'vip' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'trial' }))
  fireEvent.submit(document.querySelector('form')!)

  await waitFor(() => expect(onCreate).toHaveBeenCalledWith({ tags: ['vip', 'trial'] }))
  expect(screen.queryByRole('checkbox', { name: 'unknown' })).not.toBeInTheDocument()
})

test('explains when the server marks a form as unavailable for this first slice', () => {
  render(<CreateRecordPanel form={{ table_id: 'table-1', can_create: false, fields: [] }} onCreate={vi.fn()} onClose={() => undefined} />)

  expect(screen.getByRole('alert')).toBeInTheDocument()
  expect(document.querySelector('form')).toBeNull()
})

test('submits relation picker selections as opaque IDs only', async () => {
  const onCreate = vi.fn().mockResolvedValue(undefined)
  const loadRelationCandidates = vi.fn().mockResolvedValue({
    field_id: 'field-relation',
    records: [{ id: 'record-acme', label: 'Acme' }],
    next_cursor: null,
    has_more: false,
  })
  render(<CreateRecordPanel form={{ table_id: 'table-1', can_create: true, fields: [{ id: 'field-relation', key: 'customer', name: 'Customer', field_type: 'linked_record', required: true, options: {}, order_index: 0 }] }} onCreate={onCreate} onClose={() => undefined} loadRelationCandidates={loadRelationCandidates} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Acme' }))
  fireEvent.submit(document.querySelector('form')!)

  await waitFor(() => expect(onCreate).toHaveBeenCalledWith({ customer: ['record-acme'] }))
  expect(screen.queryByText('target_table_id')).not.toBeInTheDocument()
})
