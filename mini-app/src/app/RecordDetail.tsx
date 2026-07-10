import { useEffect, useRef, useState } from 'react'
import { Pencil, X } from 'lucide-react'

import { ApiError, type RecordDetail, type TableSchema } from './api'

type RecordDetailPanelProps = {
  detail: RecordDetail
  schema: TableSchema | null
  onClose: () => void
  onSave: (values: Record<string, unknown>) => Promise<RecordDetail>
  onConflict?: () => Promise<RecordDetail>
}

type Field = TableSchema['fields'][number]

const directFieldTypes = new Set(['text', 'status', 'single_select', 'multi_select', 'user', 'url', 'email', 'phone', 'date', 'number', 'checkbox'])

function choicesFor(field: Field): string[] {
  const choices = field.options?.choices
  return Array.isArray(choices) && choices.every((choice) => typeof choice === 'string') ? choices : []
}

function toggleChoice(values: string[], choice: string): string[] {
  return values.includes(choice) ? values.filter((item) => item !== choice) : [...values, choice]
}

function stringChoices(value: unknown): string[] {
  return Array.isArray(value) && value.every((item): item is string => typeof item === 'string') ? value : []
}

export function RecordDetailPanel({ detail, schema, onClose, onSave, onConflict }: RecordDetailPanelProps) {
  const [current, setCurrent] = useState(detail)
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState(detail.values)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const synchronizedDetailKey = useRef(`${detail.id}:${detail.version}`)
  const fields = schema?.fields.filter((field) => Object.hasOwn(current.values, field.key)) ?? []

  useEffect(() => {
    const nextKey = `${detail.id}:${detail.version}`
    if (synchronizedDetailKey.current === nextKey) return
    synchronizedDetailKey.current = nextKey
    setCurrent(detail)
    setValues(detail.values)
    setEditing(false)
  }, [detail])

  function beginEditing() {
    setValues(current.values)
    setError(null)
    setEditing(true)
  }

  function updateValue(field: Field, rawValue: unknown) {
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
      if (caught instanceof ApiError && caught.status === 409 && onConflict) {
        try {
          const latest = await onConflict()
          setCurrent(latest)
          setValues(latest.values)
          setEditing(false)
          setError('记录已被更新，已刷新最新版本，请重新编辑。')
        } catch {
          setError('记录已被更新，请刷新后重试。')
        }
      } else {
        setError(caught instanceof ApiError && caught.status === 409 ? '记录已被更新，请刷新后重试。' : '保存失败，请稍后重试。')
      }
    } finally {
      setSaving(false)
    }
  }

  return <aside className="record-detail" aria-label="记录详情"><header><div><h2>记录详情</h2><span>版本 {current.version}</span></div><div className="detail-actions">{!editing && <button className="detail-edit" type="button" onClick={beginEditing}><Pencil size={14} />编辑记录</button>}<button type="button" aria-label="关闭记录详情" onClick={onClose}><X size={18} /></button></div></header>{error && <p className="detail-error" role="alert">{error}</p>}{editing ? <form className="detail-form" onSubmit={(event) => { event.preventDefault(); void save() }}>{fields.map((field) => {
    if (!directFieldTypes.has(field.field_type)) return <div className="detail-readonly" key={field.id}><span>{field.name}</span><output>{formatValue(values[field.key])}</output><small>此字段类型暂不支持直接编辑</small></div>
    const choices = choicesFor(field)
    if (field.field_type === 'multi_select') {
      const selected = stringChoices(values[field.key])
      return <fieldset className="choice-checkbox-list" key={field.id}><legend>{field.name}</legend>{choices.map((choice) => <label key={choice}><input type="checkbox" checked={selected.includes(choice)} onChange={() => updateValue(field, toggleChoice(selected, choice))} />{choice}</label>)}</fieldset>
    }
    return <label key={field.id}>{field.name}{field.field_type === 'checkbox' ? <input aria-label={field.name} type="checkbox" checked={Boolean(values[field.key])} onChange={(event) => updateValue(field, event.target.checked)} /> : choices.length > 0 ? <select aria-label={field.name} value={String(values[field.key] ?? '')} onChange={(event) => updateValue(field, event.target.value)}><option value="">请选择</option>{choices.map((choice) => <option key={choice} value={choice}>{choice}</option>)}</select> : <input aria-label={field.name} type={field.field_type === 'date' ? 'date' : field.field_type === 'number' ? 'number' : 'text'} value={String(values[field.key] ?? '')} onChange={(event) => updateValue(field, event.target.value)} />}</label>
  })}<div className="detail-form-actions"><button type="button" onClick={() => { setValues(current.values); setEditing(false); setError(null) }}>取消</button><button type="submit" disabled={saving}>{saving ? '保存中…' : '保存更改'}</button></div></form> : <dl>{fields.map((field) => <div key={field.id}><dt>{field.name}</dt><dd>{formatValue(current.values[field.key])}</dd></div>)}</dl>}</aside>
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  return typeof value === 'string' ? value : JSON.stringify(value)
}
