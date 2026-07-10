import { useState } from 'react'

import type { CreateForm } from './api'

type Props = { form: CreateForm; onCreate: (values: Record<string, unknown>) => Promise<void>; onClose: () => void }
const supported = new Set(['text', 'number', 'date', 'checkbox', 'single_select', 'multi_select', 'status', 'url', 'email', 'phone', 'user'])

function choicesFor(field: CreateForm['fields'][number]): string[] {
  const choices = field.options?.choices
  return Array.isArray(choices) && choices.every((choice) => typeof choice === 'string') ? choices : []
}

function toggleChoice(values: string[], choice: string): string[] {
  return values.includes(choice) ? values.filter((item) => item !== choice) : [...values, choice]
}

function stringChoices(value: unknown): string[] {
  return Array.isArray(value) && value.every((item): item is string => typeof item === 'string') ? value : []
}

function isMissingValue(value: unknown): boolean {
  return value === undefined || value === '' || (Array.isArray(value) && value.length === 0)
}

export function CreateRecordPanel({ form, onCreate, onClose }: Props) {
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fields = form.fields.filter((field) => supported.has(field.field_type))
  if (!form.can_create) return <aside className="record-detail" aria-label="新建记录"><header><h2>新建记录</h2><button type="button" onClick={onClose}>关闭</button></header><p className="detail-error" role="alert">此表包含暂不支持的必填字段，暂时无法创建记录。</p></aside>
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const missing = fields.find((field) => field.required && isMissingValue(values[field.key]))
    if (missing) return setError(`${missing.name}为必填项`)
    setSaving(true); setError(null)
    try { await onCreate(Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined && value !== ''))); onClose() } catch { setError('创建失败，请稍后重试。') } finally { setSaving(false) }
  }
  return <aside className="record-detail" aria-label="新建记录"><header><h2>新建记录</h2><button type="button" onClick={onClose}>关闭</button></header>{error && <p role="alert">{error}</p>}<form className="detail-form" onSubmit={submit}>{fields.map((field) => {
    const choices = choicesFor(field)
    if (field.field_type === 'multi_select') {
      const selected = stringChoices(values[field.key])
      return <fieldset className="choice-checkbox-list" key={field.key}><legend>{field.name}</legend>{choices.map((choice) => <label key={choice}><input type="checkbox" checked={selected.includes(choice)} onChange={() => setValues({ ...values, [field.key]: toggleChoice(selected, choice) })} />{choice}</label>)}</fieldset>
    }
    return <label key={field.key}>{field.name}{field.field_type === 'checkbox' ? <input aria-label={field.name} type="checkbox" checked={Boolean(values[field.key])} onChange={(event) => setValues({ ...values, [field.key]: event.target.checked })} /> : choices.length > 0 ? <select aria-label={field.name} value={String(values[field.key] ?? '')} onChange={(event) => setValues({ ...values, [field.key]: event.target.value })}><option value="">请选择</option>{choices.map((choice) => <option key={choice} value={choice}>{choice}</option>)}</select> : <input aria-label={field.name} type={field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text'} value={String(values[field.key] ?? '')} onChange={(event) => setValues({ ...values, [field.key]: field.field_type === 'number' ? Number(event.target.value) : event.target.value })} />}</label>
  })}<button type="submit" disabled={saving}>{saving ? '创建中…' : '创建记录'}</button></form></aside>
}
