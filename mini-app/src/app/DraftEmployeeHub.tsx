import { useEffect, useRef, useState } from 'react'

import type { S5Contact, S5DraftDetail } from './draft-employee-types'

type DraftEmployeeHubProps = {
  contacts: S5Contact[]
  draft: S5DraftDetail | null
  loading: boolean
  onConfirm: (draftId: string, expectedVersion: number) => Promise<void>
  onReject: (draftId: string, expectedVersion: number) => Promise<void>
  onClose: () => void
}

export function DraftEmployeeHub({ contacts, draft, loading, onConfirm, onReject, onClose }: DraftEmployeeHubProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [pending, setPending] = useState<'confirm' | 'reject' | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { headingRef.current?.focus() }, [])

  async function terminal(action: 'confirm' | 'reject') {
    if (!draft) return
    setPending(action)
    setError(null)
    try {
      if (action === 'confirm') await onConfirm(draft.id, draft.version)
      else await onReject(draft.id, draft.version)
    } catch {
      setError('无法提交草稿决定，请重新读取后再试。')
    } finally {
      setPending(null)
    }
  }

  return <div className="draft-hub-backdrop" role="presentation">
    <aside className="draft-hub" aria-label="数字员工与草稿" aria-modal="true" role="dialog">
      <header className="draft-hub-header">
        <div><p>DRAFT REVIEW</p><h2 ref={headingRef} tabIndex={-1}>数字员工与草稿</h2><span>仅显示当前有权限查看和确认的服务器安全数据。</span></div>
        <button type="button" aria-label="关闭数字员工与草稿" onClick={onClose}>×</button>
      </header>
      {error && <p className="draft-hub-error" role="alert">{error}</p>}
      <div className="draft-hub-columns">
        <section aria-label="可用数字员工" className="draft-hub-section"><header><p>CONTACTS</p><h3>可用数字员工</h3></header>
          {loading ? <p role="status">正在读取联系人…</p> : contacts.length ? <ul className="draft-hub-contacts">{contacts.map((contact) => <li key={contact.id}><strong>{contact.name}</strong><span>{contact.description}</span><small>{contact.availableIntents.map((intent) => intent === 'summarize' ? '智能汇总' : '创建草稿').join(' · ')}</small></li>)}</ul> : <p>当前上下文没有可用数字员工。</p>}
        </section>
        <section aria-label="草稿详情" className="draft-hub-section"><header><p>DRAFT</p><h3>待确认变更</h3></header>
          {!draft ? <p>选择上下文或打开待确认草稿后，在此查看服务器过滤后的差异。</p> : <>
            <p className="draft-hub-status">状态：{draft.status === 'pending_confirmation' ? '等待确认' : draft.status}</p>
            <dl className="draft-hub-diff">{draft.fields.map((field) => <div key={field.key}><dt>{field.label}</dt><dd><span>之前：{String(field.beforeValue ?? '')}</span><strong>之后：{String(field.proposedValue ?? '')}</strong></dd></div>)}</dl>
            {draft.status === 'pending_confirmation' && <div className="draft-hub-actions">
              <button type="button" disabled={pending !== null || !draft.actions.canConfirm} onClick={() => { void terminal('confirm') }}>确认变更</button>
              <button type="button" disabled={pending !== null || !draft.actions.canReject} onClick={() => { void terminal('reject') }}>拒绝草稿</button>
            </div>}
          </>}
        </section>
      </div>
    </aside>
  </div>
}
