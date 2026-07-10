import { useState } from 'react'

import type { CreateForm } from './api'

type Props = { form: CreateForm; onCreate: (values: Record<string, unknown>) => Promise<void>; onClose: () => void }
const supported = new Set(['text', 'number', 'date', 'checkbox', 'select', 'status', 'url', 'email', 'phone', 'user'])

export function CreateRecordPanel({ form, onCreate, onClose }: Props) {
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fields = form.fields.filter((field) => supported.has(field.field_type))
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const missing = fields.find((field) => field.required && (values[field.key] === undefined || values[field.key] === ''))
    if (missing) return setError(`${missing.name}为必填项`)
    setSaving(true); setError(null)
    try { await onCreate(Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined && value !== ''))); onClose() } catch { setError('创建失败，请稍后重试。') } finally { setSaving(false) }
  }
  return <aside className="record-detail" aria-label="新建记录"><header><h2>新建记录</h2><button type="button" onClick={onClose}>关闭</button></header>{error && <p role="alert">{error}</p>}<form className="detail-form" onSubmit={submit}>{fields.map((field) => <label key={field.key}>{field.name}{field.field_type === 'checkbox' ? <input aria-label={field.name} type="checkbox" checked={Boolean(values[field.key])} onChange={(event) => setValues({ ...values, [field.key]: event.target.checked })} /> : <input aria-label={field.name} type={field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text'} value={String(values[field.key] ?? '')} onChange={(event) => setValues({ ...values, [field.key]: field.field_type === 'number' ? Number(event.target.value) : event.target.value })} />}</label>)}<button type="submit" disabled={saving}>{saving ? '创建中…' : '创建记录'}</button></form></aside>
}
