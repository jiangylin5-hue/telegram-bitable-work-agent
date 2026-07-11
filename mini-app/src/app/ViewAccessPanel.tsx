import { ShieldCheck, X } from 'lucide-react'
import { type FormEvent, useEffect, useRef, useState } from 'react'

import { toSafeViewError } from './api'
import type { SafeViewMemberCandidate, ViewBuilderResponse, ViewMemberReplaceRequest } from './view-builder-types'

type ViewAccessPanelProps = {
  builder: ViewBuilderResponse
  candidates: SafeViewMemberCandidate[]
  onSave: (request: ViewMemberReplaceRequest) => Promise<void>
  onClose: () => void
}

type GrantDraft = Record<string, 'editor' | 'viewer' | ''>

function initialGrants(builder: ViewBuilderResponse): GrantDraft {
  return Object.fromEntries(builder.members.map((member) => [member.user_id, member.access_level]))
}

export function ViewAccessPanel({ builder, candidates, onSave, onClose }: ViewAccessPanelProps) {
  const firstControlRef = useRef<HTMLSelectElement>(null)
  const [grants, setGrants] = useState<GrantDraft>(() => initialGrants(builder))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const canReplace = builder.view.caller_access_level === 'owner' && builder.can_replace_members

  useEffect(() => {
    setGrants(initialGrants(builder))
  }, [builder])

  useEffect(() => {
    firstControlRef.current?.focus()
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !saving) onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose, saving])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canReplace || saving) return
    const members = candidates.flatMap((candidate) => {
      const accessLevel = grants[candidate.id]
      return accessLevel ? [{ user_id: candidate.id, access_level: accessLevel }] : []
    })
    setSaving(true)
    setError(null)
    try {
      await onSave({ expected_version: builder.version, members })
    } catch (caught) {
      setError(toSafeViewError(caught))
    } finally {
      setSaving(false)
    }
  }

  return <div className="view-builder-backdrop" role="presentation">
    <aside className="view-builder-panel view-access-panel" aria-labelledby="view-access-title" aria-modal="true" role="dialog">
      <header className="view-builder-header">
        <div className="view-builder-heading"><span className="view-builder-icon"><ShieldCheck size={17} /></span><div><p>视图设置</p><h2 id="view-access-title">访问权限</h2></div></div>
        <button className="field-builder-close" type="button" aria-label="关闭访问权限" onClick={onClose} disabled={saving}><X size={18} /></button>
      </header>
      <p className="field-builder-intro">此视图默认是私有的。成员授权不会扩大其原有工作区、Base、数据表、记录或字段权限。</p>
      {!canReplace ? <section className="view-access-readonly" aria-live="polite"><p>仅视图所有者可以管理成员权限</p><small>你的当前访问权限不允许查看或修改成员授权。</small></section> : <form className="view-access-form" onSubmit={submit} noValidate>
        <p className="view-query-hint">保存会原子替换完整成员列表；未选择的成员将失去该视图的额外访问。</p>
        <div className="view-access-list">{candidates.map((candidate, index) => <label key={candidate.id} className="view-access-row"><span>{candidate.label}</span><select ref={index === 0 ? firstControlRef : undefined} aria-label={`${candidate.label} 权限`} value={grants[candidate.id] ?? ''} disabled={saving} onChange={(event) => setGrants((current) => ({ ...current, [candidate.id]: event.target.value as GrantDraft[string] }))}>
          <option value="">不授予访问</option><option value="viewer">查看者</option><option value="editor">编辑者</option>
        </select></label>)}</div>
        {error ? <p className="field-builder-error" role="alert">{error}</p> : null}
        <p className="view-builder-live" aria-live="polite">{saving ? '正在保存成员权限…' : ''}</p>
        <footer className="field-builder-actions"><button type="button" className="button-secondary" onClick={onClose} disabled={saving}>返回</button><button type="submit" className="button-primary" disabled={saving}>{saving ? '保存中…' : '保存成员权限'}</button></footer>
      </form>}
    </aside>
  </div>
}
