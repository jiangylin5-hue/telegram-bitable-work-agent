import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { ApiError } from '../app/api'
import { ImportWizard } from '../app/ImportWizard'

test('sends CSV text, renders only server preview and commits scalar mapping', async () => {
  const file = new File(['Name,Score\nAda,10\n'], 'customers.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: () => Promise.resolve('Name,Score\nAda,10\n') })
  const onCreatePreview = vi.fn().mockResolvedValue({
    id: 'job-1', workspaceId: 'workspace-1', baseId: null, sourceType: 'csv', status: 'awaiting_confirmation',
    detectedSchema: [{ key: 'name', name: 'Name', fieldType: 'text' }, { key: 'score', name: 'Score', fieldType: 'number' }],
    previewRows: [{ name: 'Ada', score: 10 }],
    mapping: [{ sourceKey: 'name', targetKey: 'name', fieldType: 'text' }, { sourceKey: 'score', targetKey: 'score', fieldType: 'number' }],
  })
  const onCommit = vi.fn().mockResolvedValue({ importJobId: 'job-1', status: 'committed', baseId: 'base-1', tableId: 'table-1' })
  render(<ImportWizard target={{ kind: 'workspace', workspaceId: 'workspace-1' }} onCreatePreview={onCreatePreview} onCommit={onCommit} onClose={vi.fn()} />)

  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))

  expect(await screen.findByText('Ada')).toBeVisible()
  expect(onCreatePreview).toHaveBeenCalledWith({ sourceType: 'csv', fileName: 'customers.csv', content: 'Name,Score\nAda,10\n', baseId: undefined })
  fireEvent.change(screen.getByLabelText('Base 名称'), { target: { value: 'Imported CRM' } })
  fireEvent.change(screen.getByLabelText('数据表名称'), { target: { value: 'Customers' } })
  fireEvent.change(screen.getByLabelText('数据表 key'), { target: { value: 'customers' } })
  fireEvent.click(screen.getByRole('button', { name: '确认创建数据表' }))

  expect(await screen.findByText('已创建数据表')).toBeVisible()
  expect(onCommit).toHaveBeenCalledWith('job-1', expect.objectContaining({ baseName: 'Imported CRM', tableName: 'Customers', tableKey: 'customers', fieldMapping: [{ sourceKey: 'name', targetKey: 'name', fieldType: 'text' }, { sourceKey: 'score', targetKey: 'score', fieldType: 'number' }] }))
  expect(screen.queryByText('Name,Score')).not.toBeInTheDocument()
})

test('rejects unsupported file names before content leaves the browser', async () => {
  const onCreatePreview = vi.fn()
  render(<ImportWizard target={{ kind: 'workspace', workspaceId: 'workspace-1' }} onCreatePreview={onCreatePreview} onCommit={vi.fn()} onClose={vi.fn()} />)

  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [new File(['secret'], 'customers.txt', { type: 'text/plain' })] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('仅支持 CSV 或 XLSX 文件。')
  expect(onCreatePreview).not.toHaveBeenCalled()
})

test('keeps the preview editable after a table-key conflict', async () => {
  const file = new File(['Name\nAda\n'], 'customers.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: () => Promise.resolve('Name\nAda\n') })
  const onCreatePreview = vi.fn().mockResolvedValue({
    id: 'job-1', workspaceId: 'workspace-1', baseId: 'base-1', sourceType: 'csv', status: 'awaiting_confirmation',
    detectedSchema: [{ key: 'name', name: 'Name', fieldType: 'text' }],
    previewRows: [{ name: 'Ada' }],
    mapping: [{ sourceKey: 'name', targetKey: 'name', fieldType: 'text' }],
  })
  const onCommit = vi.fn().mockRejectedValue(new ApiError(409, 'import_table_key_conflict'))
  render(<ImportWizard target={{ kind: 'base', workspaceId: 'workspace-1', baseId: 'base-1', baseName: 'CRM' }} onCreatePreview={onCreatePreview} onCommit={onCommit} onClose={vi.fn()} />)

  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))
  await screen.findByText('Ada')
  fireEvent.change(screen.getByLabelText('数据表名称'), { target: { value: 'Customers' } })
  fireEvent.change(screen.getByLabelText('数据表 key'), { target: { value: 'customers' } })
  fireEvent.click(screen.getByRole('button', { name: '确认创建数据表' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('数据表 key 已存在')
  const tableKeyInput = screen.getByLabelText('数据表 key')
  expect(tableKeyInput).toBeEnabled()
  expect(tableKeyInput).toHaveFocus()
  expect(screen.queryByText('已创建数据表')).not.toBeInTheDocument()
})

test('shows a recoverable message for a generic import conflict', async () => {
  const file = new File(['Name\nAda\n'], 'customers.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: () => Promise.resolve('Name\nAda\n') })
  const onCreatePreview = vi.fn().mockRejectedValue(new ApiError(409))
  render(<ImportWizard target={{ kind: 'workspace', workspaceId: 'workspace-1' }} onCreatePreview={onCreatePreview} onCommit={vi.fn()} onClose={vi.fn()} />)

  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('请求发生冲突，请刷新后重试。')
})

test('shows a known import validation reason without raw API details', async () => {
  const file = new File(['Name\nAda\n'], 'customers.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: () => Promise.resolve('Name\nAda\n') })
  const onCreatePreview = vi.fn().mockRejectedValue(new ApiError(422, 'import_missing_header'))
  render(<ImportWizard target={{ kind: 'workspace', workspaceId: 'workspace-1' }} onCreatePreview={onCreatePreview} onCommit={vi.fn()} onClose={vi.fn()} />)

  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('导入文件缺少表头。')
})

test('derives an editable mapping when the server preview intentionally omits its default mapping', async () => {
  const file = new File(['客户名称,预算\n明日璀璨,12000\n'], '客户运营.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: () => Promise.resolve('客户名称,预算\n明日璀璨,12000\n') })
  const onCreatePreview = vi.fn().mockResolvedValue({
    id: 'job-empty-mapping', workspaceId: 'workspace-1', baseId: null, sourceType: 'csv', status: 'awaiting_confirmation',
    detectedSchema: [{ key: '客户名称', name: '客户名称', fieldType: 'text' }, { key: '预算', name: '预算', fieldType: 'number' }],
    previewRows: [{ 客户名称: '明日璀璨', 预算: 12000 }], mapping: [],
  })
  const onCommit = vi.fn().mockResolvedValue({ importJobId: 'job-empty-mapping', status: 'committed', baseId: 'base-1', tableId: 'table-1' })
  render(<ImportWizard target={{ kind: 'workspace', workspaceId: 'workspace-1' }} onCreatePreview={onCreatePreview} onCommit={onCommit} onClose={vi.fn()} />)

  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))

  expect(await screen.findByLabelText('客户名称 目标 key')).toHaveValue('客户名称')
  expect(screen.getByLabelText('预算 字段类型')).toHaveValue('number')
  expect(screen.getByLabelText('数据表 key')).toHaveValue('imported_data')

  fireEvent.change(screen.getByLabelText('Base 名称'), { target: { value: '客户运营' } })
  fireEvent.change(screen.getByLabelText('数据表名称'), { target: { value: '客户汇总' } })
  fireEvent.click(screen.getByRole('button', { name: '确认创建数据表' }))

  expect(await screen.findByText('已创建数据表')).toBeVisible()
  expect(onCommit).toHaveBeenCalledWith('job-empty-mapping', expect.objectContaining({
    tableKey: 'imported_data',
    fieldMapping: [
      { sourceKey: '客户名称', targetKey: '客户名称', fieldType: 'text', name: '客户名称' },
      { sourceKey: '预算', targetKey: '预算', fieldType: 'number', name: '预算' },
    ],
  }))
})

test('keeps an unexpected controlled import refusal actionable by showing its stable error code', async () => {
  const file = new File(['Name\nAda\n'], 'customers.csv', { type: 'text/csv' })
  Object.defineProperty(file, 'text', { value: () => Promise.resolve('Name\nAda\n') })
  render(<ImportWizard
    target={{ kind: 'workspace', workspaceId: 'workspace-1' }}
    onCreatePreview={vi.fn().mockRejectedValue(new ApiError(422, 'idempotency_in_progress'))}
    onCommit={vi.fn()}
    onClose={vi.fn()}
  />)

  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('idempotency_in_progress')
})

test('closes an idle import panel with Escape or its backdrop without treating panel clicks as cancellation', () => {
  const onClose = vi.fn()
  render(<ImportWizard target={{ kind: 'workspace', workspaceId: 'workspace-1' }} onCreatePreview={vi.fn()} onCommit={vi.fn()} onClose={onClose} />)

  fireEvent.mouseDown(screen.getByRole('dialog', { name: '导入数据表' }))
  expect(onClose).not.toHaveBeenCalled()

  fireEvent.mouseDown(screen.getByRole('presentation'))
  expect(onClose).toHaveBeenCalledOnce()

  fireEvent.keyDown(document, { key: 'Escape' })
  expect(onClose).toHaveBeenCalledTimes(2)
})
