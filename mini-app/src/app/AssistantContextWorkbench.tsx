import { useState } from 'react'

import type { AssistantContextPage, AssistantSelectedView, S5Citation, S5Contact } from './draft-employee-types'

type AssistantContextWorkbenchProps = {
  contacts: S5Contact[]
  context: AssistantContextPage | null
  selectedView: AssistantSelectedView | null
  summary: { answer: string; citations: S5Citation[] } | null
  loading: boolean
  failed: boolean
  onSelectContact: (employeeId: string) => void
  onSelectView: (viewId: string) => void
  onSummarize: (instruction?: string) => Promise<void>
  onOpenBase: () => void
  onRetry: () => void
  onClose: () => void
}

export function AssistantContextWorkbench({
  contacts,
  context,
  selectedView,
  summary,
  loading,
  failed,
  onSelectContact,
  onSelectView,
  onSummarize,
  onOpenBase,
  onRetry,
  onClose,
}: AssistantContextWorkbenchProps) {
  const [instruction, setInstruction] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const summarize = async () => {
    if (!selectedView || submitting) return
    setSubmitting(true)
    try {
      await onSummarize(instruction.trim() || undefined)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="assistant-context-backdrop" role="presentation">
      <aside className="assistant-context-workbench" role="dialog" aria-label="个人助理上下文" aria-modal="true">
        <header className="assistant-context-header">
          <div>
            <p>PERSONAL ASSISTANT</p>
            <h2>个人助理上下文</h2>
            <span>仅使用当前成员可访问、且数字员工被授权的视图。</span>
          </div>
          <button type="button" aria-label="关闭个人助理上下文" onClick={onClose}>×</button>
        </header>

        {failed ? (
          <section className="assistant-context-state" role="alert">
            <p>暂时无法读取个人助理上下文，请稍后重试。</p>
            <button type="button" onClick={onRetry}>重试</button>
          </section>
        ) : (
          <div className="assistant-context-columns">
            <section className="assistant-context-section">
              <header>
                <p>STEP 1</p>
                <h3>选择数字员工</h3>
              </header>
              {contacts.length === 0 ? <p>当前没有可协作的数字员工。</p> : (
                <ul className="assistant-context-contact-list">
                  {contacts.map((contact) => (
                    <li key={contact.id}>
                      <button type="button" aria-label={`选择数字员工 ${contact.name}`} className={context?.employee.id === contact.id ? 'selected' : ''} onClick={() => onSelectContact(contact.id)}>
                        <strong>{contact.name}</strong>
                        <span>{contact.description}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="assistant-context-section">
              <header>
                <p>STEP 2</p>
                <h3>选择可访问视图</h3>
              </header>
              {!context ? <p>请选择数字员工和可访问视图，再开始协作。</p> : (
                <>
                  <p className="assistant-context-employee">{context.employee.name} · {context.employee.description}</p>
                  {context.views.length === 0 ? <p>该数字员工目前没有可用于协作的视图。</p> : (
                    <ul className="assistant-context-view-list">
                      {context.views.map((view) => (
                        <li key={view.id}>
                          <button type="button" aria-label={`选择视图 ${view.name}`} className={selectedView?.id === view.id ? 'selected' : ''} onClick={() => onSelectView(view.id)}>
                            <strong>{view.name}</strong>
                            <span>{view.viewType}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </section>

            <section className="assistant-context-section assistant-context-summary-section">
              <header>
                <p>STEP 3</p>
                <h3>执行摘要</h3>
              </header>
              {!selectedView ? <p>选定视图后，才会在执行前再次验证它的访问权限。</p> : (
                <div className="assistant-context-invocation">
                  <p>当前视图：{selectedView.name}</p>
                  <label>
                    补充说明
                    <textarea aria-label="补充说明" maxLength={1000} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="可选：说明你希望关注的事项" />
                  </label>
                  <button type="button" disabled={loading || submitting} onClick={() => void summarize()}>{submitting ? '处理中…' : '执行摘要'}</button>
                </div>
              )}
              {summary ? (
                <div className="assistant-context-summary">
                  <p>{summary.answer}</p>
                  {summary.citations.length > 0 ? <ul>{summary.citations.map((citation) => <li key={citation.recordId}><code>{citation.recordId}</code></li>)}</ul> : null}
                </div>
              ) : null}
              {selectedView ? <button type="button" className="assistant-context-open-base" onClick={onOpenBase}>打开 Base 继续处理</button> : null}
            </section>
          </div>
        )}
      </aside>
    </div>
  )
}
