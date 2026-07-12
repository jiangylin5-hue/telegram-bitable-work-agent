import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { TemplateImportHub } from '../app/TemplateImportHub'

test('renders safe template metadata and starts one selected installation', () => {
  const onInstall = vi.fn()
  render(<TemplateImportHub
    templates={[{ id: 'template-1', name: 'CRM', category: 'crm', description: 'Customer operations', version: '1.0.0', status: 'published' }]}
    loading={false}
    error={null}
    onRetry={vi.fn()}
    onInstall={onInstall}
    onStartWorkspaceImport={vi.fn()}
    onClose={vi.fn()}
  />)

  expect(screen.getByText('CRM')).toBeVisible()
  expect(screen.getByText('Customer operations')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '安装模板 CRM' }))
  expect(onInstall).toHaveBeenCalledWith(expect.objectContaining({ id: 'template-1' }))
  expect(screen.queryByText('manifest')).not.toBeInTheDocument()
})

test('contains an installation failure for the parent to render as a safe message', async () => {
  const onInstallError = vi.fn()
  render(<TemplateImportHub
    templates={[{ id: 'template-1', name: 'CRM', category: 'crm', description: 'Customer operations', version: '1.0.0', status: 'published' }]}
    loading={false}
    error={null}
    onRetry={vi.fn()}
    onInstall={vi.fn().mockRejectedValue(new Error('network details must not render'))}
    onInstallError={onInstallError}
    onClose={vi.fn()}
  />)

  fireEvent.click(screen.getByRole('button', { name: '安装模板 CRM' }))
  await waitFor(() => expect(onInstallError).toHaveBeenCalledOnce())
})
