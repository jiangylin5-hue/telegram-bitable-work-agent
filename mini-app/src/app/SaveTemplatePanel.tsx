import { type FormEvent, useEffect, useRef, useState } from 'react'

import { ApiError, type BaseSummary } from './api'
import type { TemplateSummary } from './template-import-types'

type Values = { name: string; category: string; description: string }
type Props = { base: BaseSummary; onSave: (values: Values) => Promise<TemplateSummary>; onClose: () => void }

export function SaveTemplatePanel({ base, onSave, onClose }: Props) {
  const nameRef = useRef<HTMLInputElement>(null)
  const [name, setName] = useState('')
  const [category, setCategory] = useState('custom')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<TemplateSummary | null>(null)

  useEffect(() => { nameRef.current?.focus() }, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = { name: name.trim(), category: category.trim(), description: description.trim() }
    if (!values.name || !values.category || !values.description) {
      setError('请完整填写模板信息。')
      return
    }
    setSaving(true); setError(null)
    try { setSaved(await onSave(values)) } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 403 ? '当前没有保存模板的权限。' : '保存模板失败，请稍后重试。')
    } finally { setSaving(false) }
  }

  return <div className="template-import-backdrop" role="presentation">
    <aside className="template-import-panel" aria-labelledby="save-template-title" aria-modal="true" role="dialog">
      <header className="template-import-header"><div><p>BASE TEMPLATE</p><h2 id="save-template-title">保存为模板</h2><span>将当前已授权 Base 保存为可复用草稿模板。</span></div><button type="button" aria-label="关闭保存模板" disabled={saving} onClick={onClose}>×</button></header>
      {saved ? <section className="template-save-success" role="status"><strong>草稿模板</strong><span>{saved.name}</span><small>{saved.category} · v{saved.version} · {saved.status}</small><button type="button" onClick={onClose}>完成</button></section> : <form className="template-import-form" onSubmit={submit} noValidate><p className="template-import-context">来源 Base：{base.name}</p><label>模板名称<input ref={nameRef} aria-label="模板名称" value={name} disabled={saving} onChange={(event) => setName(event.target.value)} /></label><label>模板分类<input aria-label="模板分类" value={category} disabled={saving} onChange={(event) => setCategory(event.target.value)} /></label><label>模板说明<textarea aria-label="模板说明" value={description} disabled={saving} onChange={(event) => setDescription(event.target.value)} /></label>{error && <p className="template-import-error" role="alert">{error}</p>}<footer><button type="button" className="button-secondary" disabled={saving} onClick={onClose}>取消</button><button type="submit" className="button-primary" disabled={saving}>{saving ? '保存中…' : '保存为模板'}</button></footer></form>}
    </aside>
  </div>
}
