import { useEffect, useState } from 'react'
import { Pencil, X } from 'lucide-react'

import { ApiError, type RecordDetail, type TableSchema } from './api'

type RecordDetailPanelProps = {
  detail: RecordDetail
  schema: TableSchema | null
  onClose: () => void
  onSave: (values: Record<string, unknown>) => Promise<RecordDetail>
}

type Field = TableSchema['fields'][number]

const directFieldTypes = new Set(['text', 'status', 'single_select', 'user', 'url', 'email', 'phone', 'date', 'number', 'checkbox'])

export function RecordDetailPanel({ detail, schema, onClose, onSave }: RecordDetailPanelProps) {
  const [current, setCurrent] = useState(detail)
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState(detail.values)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fields = schema?.fields.filter((field) => Object.hasOwn(current.values, field.key)) ?? []

  useEffect(() => {
    setCurrent(detail)
    setValues(detail.values)
    setEditing(false)
    setError(null)
  }, [detail])

  function beginEditing() {
    setValues(current.values)
    setError(null)
    setEditing(true)
  }

  function updateValue(field: Field, rawValue: string | boolean) {
    const value = field.field_type === 'number' && typeof rawValue === 'string' ? (rawValue === '' ? null : Number(rawValue)) : rawValue
    setValues({ ...values, [field.key]: value })
  }

  async function save() {
    const changedValues = Object.fromEntries(Object.entries(values).filter(([key, value]) => value !== current.values[key]))
    if (Object.keys(changedValues).length === 0) {
      setEditing(false)
      return
    }
    setSaving(true)
    setError(null)
    try {
      const updated = await onSave(changedValues)
      setCurrent(updated)
      setValues(updated.values)
      setEditing(false)
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 409 ? '记录已被更新，请刷新后重试。' : '保存失败，请稍后重试。')
    } finally {
      setSaving(false)
    }
  }

  return <aside className="record-detail" aria-label="记录详情"><header><div><h2>记录详情</h2><span>版本 {current.version}</span></div><div className="detail-actions">{!editing && <button className="detail-edit" type="button" onClick={beginEditing}><Pencil size={14} />编辑记录</button>}<button type="button" aria-label="关闭记录详情" onClick={onClose}><X size={18} /></button></div></header>{error && <p className="detail-error" role="alert">{error}</p>}{editing ? <form className="detail-form" onSubmit={(event) => { event.preventDefault(); void save() }}>{fields.map((field) => directFieldTypes.has(field.field_type) ? <label key={field.id}>{field.name}{field.field_type === 'checkbox' ? <input aria-label={field.name} type="checkbox" checked={Boolean(values[field.key])} onChange={(event) => updateValue(field, event.target.checked)} /> : <input aria-label={field.name} type={field.field_type === 'date' ? 'date' : field.field_type === 'number' ? 'number' : 'text'} value={String(values[field.key] ?? '')} onChange={(event) => updateValue(field, event.target.value)} />}</label> : <div className="detail-readonly" key={field.id}><span>{field.name}</span><output>{formatValue(values[field.key])}</output><small>此字段类型暂不支持直接编辑</small></div>)}<div className="detail-form-actions"><button type="button" onClick={() => { setValues(current.values); setEditing(false); setError(null) }}>取消</button><button type="submit" disabled={saving}>{saving ? '保存中…' : '保存更改'}</button></div></form> : <dl>{fields.map((field) => <div key={field.id}><dt>{field.name}</dt><dd>{formatValue(current.values[field.key])}</dd></div>)}</dl>}</aside>
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  return typeof value === 'string' ? value : JSON.stringify(value)
}
