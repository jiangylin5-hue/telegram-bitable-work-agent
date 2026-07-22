import { useEffect, useRef, useState } from 'react'

import type { CurrentCanvasInvocationContext, S5Contact, S5DraftDetail, S5InvocationRequest, S5InvocationResult } from './draft-employee-types'

type DraftEmployeeHubProps = {
  contacts: S5Contact[]
  context?: CurrentCanvasInvocationContext | null
  draft: S5DraftDetail | null
  loading: boolean
  failed?: boolean
  onConfirm: (draftId: string, expectedVersion: number) => Promise<void>
  onReject: (draftId: string, expectedVersion: number) => Promise<void>
  onInvoke?: (employeeId: string, request: S5InvocationRequest, idempotencyKey?: string) => Promise<S5InvocationResult>
  onRetry?: () => void
  onClose: () => void
}

export function DraftEmployeeHub({ contacts, context = null, draft, loading, failed = false, onConfirm, onReject, onInvoke, onRetry, onClose }: DraftEmployeeHubProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const invocationVersion = useRef(0)
  const [selectedContactId, setSelectedContactId] = useState<string | null>(null)
  const [instruction, setInstruction] = useState('')
  const [summary, setSummary] = useState<Extract<S5InvocationResult, { kind: 'summary' }> | null>(null)
  const [invocationPending, setInvocationPending] = useState<'summarize' | 'draft_update' | null>(null)
  const [pending, setPending] = useState<'confirm' | 'reject' | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { headingRef.current?.focus() }, [])
  const contextKey = context ? `${context.baseId}:${context.viewId}:${context.recordId ?? ''}` : ''
  useEffect(() => {
    invocationVersion.current += 1
    setSummary(null)
    setInvocationPending(null)
    setError(null)
  }, [contextKey])

  const selectedContact = contacts.find((contact) => contact.id === selectedContactId) ?? null
  const contextMatchesContact = Boolean(context && selectedContact && context.baseId === selectedContact.baseId)
  const canSummarize = Boolean(onInvoke && contextMatchesContact && selectedContact?.availableIntents.includes('summarize'))
  const canDraftUpdate = Boolean(onInvoke && contextMatchesContact && context?.recordId && selectedContact?.availableIntents.includes('draft_update'))

  async function invoke(intent: 'summarize' | 'draft_update') {
    if (!onInvoke || !context || !selectedContact) return
    if (intent === 'summarize' && !canSummarize) return
    if (intent === 'draft_update' && !canDraftUpdate) return
    const request: S5InvocationRequest = intent === 'summarize'
      ? { intent, baseId: context.baseId, viewId: context.viewId, ...(instruction.trim() ? { instruction: instruction.trim() } : {}) }
      : { intent, baseId: context.baseId, viewId: context.viewId, recordId: context.recordId!, ...(instruction.trim() ? { instruction: instruction.trim() } : {}) }
    const requestVersion = ++invocationVersion.current
    setInvocationPending(intent)
    setError(null)
    try {
      const result = await onInvoke(selectedContact.id, request, intent === 'draft_update' ? crypto.randomUUID() : undefined)
      if (requestVersion !== invocationVersion.current) return
      setSummary(result.kind === 'summary' ? result : null)
    } catch {
      if (requestVersion !== invocationVersion.current) return
      setError('无法执行数字员工请求，请重新读取当前上下文后再试。')
    } finally {
      if (requestVersion === invocationVersion.current) setInvocationPending(null)
    }
  }

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
    <section className="draft-hub" aria-label="数字员工与草稿" data-testid="draft-review-workbench" data-workbench-layout="three-pane">
      <header className="draft-hub-header">
        <div><p>DRAFT REVIEW</p><h2 ref={headingRef} tabIndex={-1}>数字员工与草稿</h2><span>仅显示当前有权限查看和确认的服务器安全数据。</span></div>
        <button type="button" aria-label="关闭数字员工与草稿" onClick={onClose}>×</button>
      </header>
      {(failed || error) && <div className="draft-hub-error" role="alert"><p>{failed ? '暂时无法读取数字员工与草稿，请稍后重试。' : error}</p>{onRetry && <button type="button" onClick={onRetry}>重新读取</button>}</div>}
      <div className="draft-hub-columns">
        <section aria-label="数字员工目录" className="draft-hub-section"><header><p>ASSISTANTS</p><h3>数字员工</h3></header>
          {loading ? <p role="status">正在读取联系人…</p> : contacts.length ? <ul className="draft-hub-contacts">{contacts.map((contact) => <li key={contact.id}><button type="button" className={selectedContactId === contact.id ? 'draft-hub-contact-select selected' : 'draft-hub-contact-select'} aria-label={`选择数字员工 ${contact.name}`} aria-pressed={selectedContactId === contact.id} onClick={() => { setSelectedContactId(contact.id); setSummary(null); setError(null) }}><strong>{contact.name}</strong><span>{contact.description}</span><small>{contact.availableIntents.map((intent) => intent === 'summarize' ? '智能汇总' : '创建草稿').join(' · ')}</small></button></li>)}</ul> : <p>当前上下文没有可用数字员工。</p>}
        </section>
        <section aria-label="当前上下文" className="draft-hub-section"><header><p>CONTEXT</p><h3>当前上下文</h3></header>
          <div className="draft-hub-context" role="status">{!context ? '请先打开当前 Base 和视图，再使用数字员工。' : <>{'已连接当前 Base 和视图。'}{context.recordId ? ' 已打开当前记录。' : ' 创建草稿需要先打开当前记录。'}</>}</div>
          {draft ? <section className="draft-hub-thread" aria-label="草稿变更预览"><header><p>BOT PROPOSAL</p><h4>待确认变更</h4><span>以下内容来自服务器过滤后的字段级差异。</span></header><dl className="draft-hub-diff">{draft.fields.map((field) => <div key={field.key}><dt>{field.label}</dt><dd><span>之前：{String(field.beforeValue ?? '')}</span><strong>之后：{String(field.proposedValue ?? '')}</strong></dd></div>)}</dl></section> : null}
          {selectedContact ? <div className="draft-hub-invocation">
            {!contextMatchesContact ? <p role="alert">选择的数字员工不适用于当前 Base。</p> : <>
              <label>补充说明<textarea aria-label="补充说明" value={instruction} maxLength={1000} onChange={(event) => setInstruction(event.target.value)} /></label>
              <div className="draft-hub-actions">
                {selectedContact.availableIntents.includes('summarize') ? <button type="button" aria-label="执行摘要" disabled={!canSummarize || invocationPending !== null} onClick={() => { void invoke('summarize') }}>执行摘要</button> : null}
                {selectedContact.availableIntents.includes('draft_update') ? <button type="button" aria-label="创建草稿" disabled={!canDraftUpdate || invocationPending !== null} onClick={() => { void invoke('draft_update') }}>创建草稿</button> : null}
              </div>
            </>}
          </div> : null}
          {summary ? <section className="draft-hub-summary" aria-label="安全摘要"><p>{summary.answer}</p>{summary.citations.length ? <ul>{summary.citations.map((citation) => <li key={citation.recordId}><code>{citation.recordId}</code></li>)}</ul> : null}</section> : null}
        </section>
        <section aria-label="草稿确认" className="draft-hub-section draft-hub-review"><header><p>REVIEW</p><h3>草稿确认</h3></header>
          {!draft ? <p>选择上下文或打开待确认草稿后，在此查看服务器过滤后的差异。</p> : <>
            <p className="draft-hub-status">状态：{draft.status === 'pending_confirmation' ? '等待确认' : draft.status}</p>
            <dl className="draft-hub-review-list"><div><dt>状态</dt><dd>{draft.status === 'pending_confirmation' ? '等待确认' : draft.status}</dd></div><div><dt>影响字段</dt><dd>{draft.fields.length} 项字段级变更</dd></div><div><dt>确认方式</dt><dd>当前用户显式确认后执行</dd></div></dl>
            {draft.terminalAuditEventId && <p className="draft-hub-audit">审计回执：<code>{draft.terminalAuditEventId}</code></p>}
            {draft.status === 'pending_confirmation' && <div className="draft-hub-actions">
              <button type="button" disabled={pending !== null || !draft.actions.canConfirm} onClick={() => { void terminal('confirm') }}>确认变更</button>
              <button type="button" disabled={pending !== null || !draft.actions.canReject} onClick={() => { void terminal('reject') }}>拒绝草稿</button>
            </div>}
          </>}
        </section>
      </div>
    </section>
  </div>
}
