import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { BaseDirectory } from '../app/BaseDirectory'

const bases = [{ id: 'base-1', name: '客户运营', source_type: 'blank' }]

test('opens only the selected safe Base summary', () => {
  const onOpenBase = vi.fn()
  render(<BaseDirectory state="ready" bases={bases} onOpenBase={onOpenBase} onHome={vi.fn()} onRetry={vi.fn()} />)

  expect(screen.getByRole('main', { name: 'Bases' })).toHaveClass('base-directory')
  expect(screen.getByRole('button', { name: '打开 客户运营' })).toHaveClass('base-directory-row')
  fireEvent.click(screen.getByRole('button', { name: '打开 客户运营' }))

  expect(onOpenBase).toHaveBeenCalledWith(bases[0])
  expect(screen.queryByText('base-1')).not.toBeInTheDocument()
})

test('renders fixed loading empty and retryable states without an inferred create action', () => {
  const { rerender } = render(<BaseDirectory state="loading" bases={[]} onOpenBase={vi.fn()} onHome={vi.fn()} onRetry={vi.fn()} />)
  expect(screen.getByRole('main', { name: 'Bases' })).toHaveAttribute('aria-busy', 'true')

  rerender(<BaseDirectory state="empty" bases={[]} onOpenBase={vi.fn()} onHome={vi.fn()} onRetry={vi.fn()} />)
  expect(screen.getByText('当前工作区没有可访问的 Base。')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '返回首页' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /新建|创建|导入/ })).not.toBeInTheDocument()

  const onRetry = vi.fn()
  rerender(<BaseDirectory state="retryable" bases={[]} onOpenBase={vi.fn()} onHome={vi.fn()} onRetry={onRetry} />)
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  expect(onRetry).toHaveBeenCalledTimes(1)
})
