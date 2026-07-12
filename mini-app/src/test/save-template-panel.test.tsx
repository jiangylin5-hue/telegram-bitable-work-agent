import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { SaveTemplatePanel } from '../app/SaveTemplatePanel'

test('submits only editable template metadata and renders the safe draft receipt', async () => {
  const onSave = vi.fn().mockResolvedValue({ id: 'template-1', name: 'Ops starter', category: 'operations', description: 'Reusable', version: '1.0.0', status: 'draft' })
  render(<SaveTemplatePanel base={{ id: 'base-1', name: 'Operations', source_type: 'blank' }} onSave={onSave} onClose={vi.fn()} />)

  fireEvent.change(screen.getByLabelText('模板名称'), { target: { value: 'Ops starter' } })
  fireEvent.change(screen.getByLabelText('模板分类'), { target: { value: 'operations' } })
  fireEvent.change(screen.getByLabelText('模板说明'), { target: { value: 'Reusable' } })
  fireEvent.click(screen.getByRole('button', { name: '保存为模板' }))

  await waitFor(() => expect(onSave).toHaveBeenCalledWith({ name: 'Ops starter', category: 'operations', description: 'Reusable' }))
  expect(await screen.findByText('草稿模板')).toBeVisible()
  expect(screen.queryByText('manifest')).not.toBeInTheDocument()
})
