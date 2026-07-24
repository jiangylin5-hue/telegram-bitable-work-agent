import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { TableOperationCenter } from '../app/TableOperationCenter'

test('routes each supported table action to an existing controlled surface', () => {
  const onCreateBase = vi.fn()
  const onOpenTemplates = vi.fn()
  const onCreateTable = vi.fn()
  const onCreateField = vi.fn()
  const onCreateView = vi.fn()
  const onConfigureView = vi.fn()
  const onCreateRecord = vi.fn()
  const onImportIntoBase = vi.fn()
  const onSaveTemplate = vi.fn()

  render(<TableOperationCenter
    scope={{ kind: 'base', baseName: '客户协作工作台', tableName: '客户表', viewName: '全部客户' }}
    actions={{ onCreateBase, onOpenTemplates, onCreateTable, onCreateField, onCreateView, onConfigureView, onCreateRecord, onImportIntoBase, onSaveTemplate }}
    onClose={vi.fn()}
  />)

  fireEvent.click(screen.getByRole('button', { name: '新建 Base' }))
  fireEvent.click(screen.getByRole('button', { name: '模板与导入' }))
  fireEvent.click(screen.getByRole('button', { name: '新建数据表' }))
  fireEvent.click(screen.getByRole('button', { name: '添加字段' }))
  fireEvent.click(screen.getByRole('button', { name: '新建视图' }))
  fireEvent.click(screen.getByRole('button', { name: '配置当前视图' }))
  fireEvent.click(screen.getByRole('button', { name: '新建记录' }))
  fireEvent.click(screen.getByRole('button', { name: '导入到当前 Base' }))
  fireEvent.click(screen.getByRole('button', { name: '保存为模板' }))

  expect(onCreateBase).toHaveBeenCalledOnce()
  expect(onOpenTemplates).toHaveBeenCalledOnce()
  expect(onCreateTable).toHaveBeenCalledOnce()
  expect(onCreateField).toHaveBeenCalledOnce()
  expect(onCreateView).toHaveBeenCalledOnce()
  expect(onConfigureView).toHaveBeenCalledOnce()
  expect(onCreateRecord).toHaveBeenCalledOnce()
  expect(onImportIntoBase).toHaveBeenCalledOnce()
  expect(onSaveTemplate).toHaveBeenCalledOnce()
})

test('shows unimplemented lifecycle, bulk and export work as planned rather than fake controls', () => {
  render(<TableOperationCenter
    scope={{ kind: 'workspace' }}
    actions={{ onCreateBase: vi.fn(), onOpenTemplates: vi.fn() }}
    onClose={vi.fn()}
  />)

  for (const name of ['复制或归档 Base', '批量编辑记录', '导出 CSV / XLSX']) {
    const item = screen.getByRole('button', { name })
    expect(item).toBeDisabled()
    expect(item).toHaveAttribute('data-availability', 'planned')
    expect(item).toHaveTextContent('规划中')
  }
  expect(screen.getByText('这些能力尚未有受控的后端契约，不能以静态页面冒充可用。')).toBeVisible()
})

test('closes the operation center with Escape or its backdrop without closing from panel content', () => {
  const onClose = vi.fn()
  render(<TableOperationCenter scope={{ kind: 'workspace' }} actions={{ onCreateBase: vi.fn(), onOpenTemplates: vi.fn() }} onClose={onClose} />)

  const dialog = screen.getByRole('dialog', { name: '表格操作中心' })
  fireEvent.mouseDown(dialog)
  expect(onClose).not.toHaveBeenCalled()

  fireEvent.mouseDown(screen.getByRole('presentation'))
  expect(onClose).toHaveBeenCalledOnce()

  fireEvent.keyDown(document, { key: 'Escape' })
  expect(onClose).toHaveBeenCalledTimes(2)
})
