import { useState } from 'react'

import type {
  TeamBotContact,
  TeamBotKnowledgeContextPage,
  TeamBotSelectedView,
  TeamBotSummary,
} from './team-bot-knowledge-types'

type TeamBotWorkbenchProps = {
  contacts: TeamBotContact[]
  context: TeamBotKnowledgeContextPage | null
  selectedView: TeamBotSelectedView | null
  summary: TeamBotSummary | null
  loading: boolean
  failed: boolean
  onSelectContact: (employeeId: string) => void
  onSelectView: (viewId: string) => void
  onSummarize: (instruction?: string) => Promise<void>
  onOpenBase: () => void
  onRetry: () => void
  onClose: () => void
}

export function TeamBotWorkbench({
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
}: TeamBotWorkbenchProps) {
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
      <aside className="assistant-context-workbench team-bot-workbench" role="dialog" aria-label="团队 Bot" aria-modal="true">
        <header className="assistant-context-header">
          <div>
            <p>TEAM BOT</p>
            <h2>团队 Bot</h2>
            <span>仅汇总当前成员可访问的团队视图；不会保存个人对话或记忆。</span>
          </div>
          <button type="button" aria-label="关闭团队 Bot" onClick={onClose}>×</button>
        </header>

        {failed ? (
          <section className="assistant-context-state" role="alert">
            <p>暂时无法读取团队知识上下文，请重新选择后重试。</p>
            <button type="button" onClick={onRetry}>重试</button>
          </section>
        ) : (
          <div className="assistant-context-columns">
            <section className="assistant-context-section">
              <header>
                <p>STEP 1</p>
                <h3>选择团队助手</h3>
              </header>
              {contacts.length === 0 ? <p>当前没有可用于团队汇总的数字员工。</p> : (
                <ul className="assistant-context-contact-list">
                  {contacts.map((contact) => (
                    <li key={contact.id}>
                      <button type="button" aria-label={'选择团队助手 ' + contact.name} className={context?.employee.id === contact.id ? 'selected' : ''} onClick={() => onSelectContact(contact.id)}>
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
                <h3>选择团队视图</h3>
              </header>
              {!context ? <p>先选择团队助手，再选择当前可访问的已保存视图。</p> : (
                <>
                  <p className="assistant-context-employee">{context.employee.name} · {context.employee.description}</p>
                  {context.views.length === 0 ? <p>该团队助手当前没有可汇总的视图。</p> : (
                    <ul className="assistant-context-view-list">
                      {context.views.map((view) => (
                        <li key={view.id}>
                          <button type="button" aria-label={'选择团队视图 ' + view.name} className={selectedView?.id === view.id ? 'selected' : ''} onClick={() => onSelectView(view.id)}>
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
                <h3>生成团队摘要</h3>
              </header>
              {!selectedView ? <p>摘要前会重新验证团队助手、已保存视图及当前访问权限。</p> : (
                <div className="assistant-context-invocation">
                  <p>当前视图：{selectedView.name}</p>
                  <label>
                    补充说明
                    <textarea aria-label="补充说明" maxLength={600} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="可选：说明这次摘要需要关注的事项" />
                  </label>
                  <button type="button" disabled={loading || submitting} onClick={() => void summarize()}>{submitting ? '处理中…' : '生成团队摘要'}</button>
                </div>
              )}
              {summary ? (
                <div className="assistant-context-summary team-bot-summary">
                  <p>{summary.answer}</p>
                  {summary.knowledgeWindowTruncated ? <p className="team-bot-truncation">仅展示前 100 条当前可访问记录的摘要。</p> : null}
                  {summary.citations.length > 0 ? <ul>{summary.citations.map((citation) => <li key={citation.recordId}><code>{citation.recordId}</code></li>)}</ul> : null}
                  <small>审计回执：{summary.auditEventId}</small>
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

