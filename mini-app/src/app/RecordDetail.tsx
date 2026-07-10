import { X } from 'lucide-react'

import type { RecordDetail, TableSchema } from './api'

type RecordDetailPanelProps = { detail: RecordDetail; schema: TableSchema | null; onClose: () => void }

export function RecordDetailPanel({ detail, schema, onClose }: RecordDetailPanelProps) {
  const fields = schema?.fields.filter((field) => Object.hasOwn(detail.values, field.key)) ?? []
  return <aside className="record-detail" aria-label="记录详情"><header><div><h2>记录详情</h2><span>版本 {detail.version}</span></div><button type="button" aria-label="关闭记录详情" onClick={onClose}><X size={18} /></button></header><dl>{fields.map((field) => <div key={field.id}><dt>{field.name}</dt><dd>{formatValue(detail.values[field.key])}</dd></div>)}</dl></aside>
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  return typeof value === 'string' ? value : JSON.stringify(value)
}
