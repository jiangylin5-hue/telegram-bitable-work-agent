import { type ChangeEvent, type FormEvent, useRef, useState } from 'react'

import { ApiError, type SafeApiErrorCode } from './api'
import type { CommitImportValues, CreateImportValues, ImportCommitReceipt, ImportMapping, ImportPreview, ImportScalarFieldType } from './template-import-types'

export type ImportTarget =
  | { kind: 'workspace'; workspaceId: string }
  | { kind: 'base'; workspaceId: string; baseId: string; baseName: string }

type PreviewInput = Omit<CreateImportValues, 'createdByUserId'>
type Props = {
  target: ImportTarget
  onCreatePreview: (values: PreviewInput) => Promise<ImportPreview>
  onCommit: (jobId: string, values: CommitImportValues) => Promise<ImportCommitReceipt>
  onClose: () => void
}

const scalarTypes: ImportScalarFieldType[] = ['text', 'number', 'date', 'checkbox']
const csvLimit = 5 * 1024 * 1024
const excelLimit = 10 * 1024 * 1024

function fileExtension(file: File) { return file.name.split('.').pop()?.toLowerCase() }

function bytesToBase64(bytes: Uint8Array) {
  let binary = ''
  for (let start = 0; start < bytes.length; start += 0x8000) binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000))
  return btoa(binary)
}

async function payloadForFile(file: File): Promise<{ sourceType: 'csv' | 'excel'; content: string }> {
  const extension = fileExtension(file)
  if (extension === 'csv') {
    if (file.size > csvLimit) throw new Error('CSV 文件不能超过 5 MiB。')
    return { sourceType: 'csv', content: await file.text() }
  }
  if (extension === 'xlsx') {
    if (file.size > excelLimit) throw new Error('XLSX 文件不能超过 10 MiB。')
    return { sourceType: 'excel', content: bytesToBase64(new Uint8Array(await file.arrayBuffer())) }
  }
  throw new Error('仅支持 CSV 或 XLSX 文件。')
}

const importErrorCopy: Partial<Record<SafeApiErrorCode, string>> = {
  import_payload_limit_exceeded: '导入文件超过了允许的大小。',
  import_row_limit_exceeded: '导入行数超过了允许的上限。',
  import_column_limit_exceeded: '导入列数超过了允许的上限。',
  import_cell_limit_exceeded: '导入单元格数量超过了允许的上限。',
  import_has_no_rows: '导入文件没有可用的数据行。',
  import_missing_header: '导入文件缺少表头。',
  import_missing_sheet: 'XLSX 文件缺少可读取的工作表。',
  unsupported_import_source: '仅支持 CSV 或 XLSX 文件。',
  invalid_import_mapping: '字段映射不符合导入要求。',
  unsupported_field_type: '字段类型不支持导入。',
  import_job_invalid_state: '当前导入预览已失效，请重新生成预览。',
}

function safeError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === 'import_table_key_conflict') return '数据表 key 已存在。请修改 key 后再次确认创建。'
    if (error.status === 409) return '请求发生冲突，请刷新后重试。'
    const message = error.code ? importErrorCopy[error.code] : undefined
    if (message) return message
  }
  if (error instanceof Error && ['仅支持 CSV 或 XLSX 文件。', 'CSV 文件不能超过 5 MiB。', 'XLSX 文件不能超过 10 MiB。'].includes(error.message)) return error.message
  return '导入暂时无法继续，请稍后重试。'
}

function validMapping(mapping: ImportMapping[]) {
  const targets = new Set<string>()
  for (const item of mapping) {
    if (!item.targetKey || !scalarTypes.includes(item.fieldType) || targets.has(item.targetKey)) return false
    targets.add(item.targetKey)
  }
  return true
}

export function ImportWizard({ target, onCreatePreview, onCommit, onClose }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const tableKeyInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [mapping, setMapping] = useState<ImportMapping[]>([])
  const [baseName, setBaseName] = useState(target.kind === 'base' ? target.baseName : '')
  const [tableName, setTableName] = useState('')
  const [tableKey, setTableKey] = useState('')
  const [pending, setPending] = useState<'preview' | 'commit' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<ImportCommitReceipt | null>(null)

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setError(null); setPreview(null); setMapping([]); setReceipt(null)
    setFile(event.target.files?.[0] ?? null)
  }

  async function createPreview() {
    if (!file) { setError('请选择一个 CSV 或 XLSX 文件。'); return }
    setPending('preview'); setError(null)
    try {
      const payload = await payloadForFile(file)
      const next = await onCreatePreview({ ...payload, fileName: file.name, ...(target.kind === 'base' ? { baseId: target.baseId } : {}) })
      setPreview(next); setMapping(next.mapping); setTableName(next.detectedSchema[0]?.name || 'Imported data'); setTableKey(next.detectedSchema[0]?.key || 'imported_data')
    } catch (caught) { setError(safeError(caught)) } finally { setFile(null); if (fileInputRef.current) fileInputRef.current.value = ''; setPending(null) }
  }

  function updateMapping(index: number, field: 'targetKey' | 'fieldType', value: string) {
    setMapping((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: field === 'fieldType' ? value as ImportScalarFieldType : value } : item))
  }

  async function commit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedBaseName = baseName.trim()
    const normalizedTableName = tableName.trim()
    const normalizedTableKey = tableKey.trim()
    if ((target.kind === 'workspace' && !normalizedBaseName) || !normalizedTableName || !normalizedTableKey || !validMapping(mapping)) {
      setError('请完善 Base、数据表与唯一的标量字段映射。')
      return
    }
    if (!preview || preview.status !== 'awaiting_confirmation') return
    setPending('commit'); setError(null)
    try {
      setReceipt(await onCommit(preview.id, { baseName: normalizedBaseName, tableName: normalizedTableName, tableKey: normalizedTableKey, fieldMapping: mapping }))
    } catch (caught) {
      setError(safeError(caught))
      if (caught instanceof ApiError && caught.code === 'import_table_key_conflict') tableKeyInputRef.current?.focus()
    } finally { setPending(null) }
  }

  return <div className="template-import-backdrop" role="presentation">
    <aside className="template-import-panel import-wizard" aria-labelledby="import-wizard-title" aria-modal="true" role="dialog">
      <header className="template-import-header"><div><p>SERVER PREVIEW</p><h2 id="import-wizard-title">导入数据表</h2><span>仅上传一个 CSV 或 XLSX 文件；字段、预览和限制由服务器确认。</span></div><button type="button" aria-label="关闭导入" disabled={pending !== null} onClick={onClose}>×</button></header>
      {receipt ? <section className="template-save-success" role="status"><strong>已创建数据表</strong><span>导入已提交并写入持久化数据表。</span><small>Base: {receipt.baseId} · Table: {receipt.tableId}</small><button type="button" onClick={onClose}>完成</button></section> : !preview ? <section className="template-import-form"><label>选择导入文件<input ref={fileInputRef} aria-label="选择导入文件" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={pending !== null} type="file" onChange={selectFile} /></label><small>CSV 最大 5 MiB；XLSX 最大 10 MiB。文件只在生成服务器预览期间保留在当前内存。</small>{error ? <p className="template-import-error" role="alert">{error}</p> : null}<footer><button type="button" className="button-secondary" disabled={pending !== null} onClick={onClose}>取消</button><button type="button" className="button-primary" disabled={!file || pending !== null} onClick={() => { void createPreview() }}>{pending === 'preview' ? '正在生成预览…' : '生成预览'}</button></footer></section> : <form className="template-import-form" noValidate onSubmit={commit}><section className="import-preview"><h3>服务器预览</h3><div className="import-preview-table"><table><thead><tr>{preview.detectedSchema.map((field) => <th key={field.key}>{field.name}</th>)}</tr></thead><tbody>{preview.previewRows.map((row, rowIndex) => <tr key={rowIndex}>{preview.detectedSchema.map((field) => <td key={field.key}>{String(row[field.key] ?? '')}</td>)}</tr>)}</tbody></table></div></section><section className="import-mapping"><h3>字段映射</h3>{mapping.map((item, index) => <div className="import-mapping-row" key={item.sourceKey}><span>{item.sourceKey}</span><input aria-label={`${item.sourceKey} 目标 key`} value={item.targetKey} disabled={pending !== null} onChange={(event) => updateMapping(index, 'targetKey', event.target.value)} /><select aria-label={`${item.sourceKey} 字段类型`} value={item.fieldType} disabled={pending !== null} onChange={(event) => updateMapping(index, 'fieldType', event.target.value)}>{scalarTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></div>)}</section>{target.kind === 'workspace' ? <label>Base 名称<input aria-label="Base 名称" value={baseName} disabled={pending !== null} onChange={(event) => setBaseName(event.target.value)} /></label> : <p className="template-import-context">目标 Base：{target.baseName}</p>}<label>数据表名称<input aria-label="数据表名称" value={tableName} disabled={pending !== null} onChange={(event) => setTableName(event.target.value)} /></label><label>数据表 key<input ref={tableKeyInputRef} aria-label="数据表 key" value={tableKey} disabled={pending !== null} onChange={(event) => setTableKey(event.target.value)} /></label>{error ? <p className="template-import-error" role="alert">{error}</p> : null}<footer><button type="button" className="button-secondary" disabled={pending !== null} onClick={onClose}>取消</button><button type="submit" className="button-primary" disabled={pending !== null}>{pending === 'commit' ? '正在创建…' : '确认创建数据表'}</button></footer></form>}
    </aside>
  </div>
}
