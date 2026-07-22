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
      <section className="assistant-context-workbench team-bot-workbench" aria-label="团队 Bot" data-testid="team-bot-workbench" data-workbench-layout="three-pane">
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
        ) : null}
        <div className="assistant-context-columns">
            <section className="assistant-context-section" aria-label="团队助手目录">
              <header>
                <p>ASSISTANTS</p>
                <h3>团队助手</h3>
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

            <section className="assistant-context-section" aria-label="已授权视图">
              <header>
                <p>CONTEXT</p>
                <h3>已授权视图</h3>
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
              {selectedView ? <section className="team-bot-thread" aria-label="团队对话记录">
                <header><p>CONVERSATION</p><h4>当前对话</h4></header>
                <div className="assistant-context-invocation">
                  <p>当前视图：{selectedView.name}</p>
                  <label>
                    补充说明
                    <textarea aria-label="补充说明" maxLength={600} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="可选：说明这次摘要需要关注的事项" />
                  </label>
                  <button type="button" disabled={loading || submitting} onClick={() => void summarize()}>{submitting ? '处理中…' : '生成团队摘要'}</button>
                </div>
                {summary ? (
                  <div className="assistant-context-summary team-bot-summary">
                    <p>{summary.answer}</p>
                    {summary.knowledgeWindowTruncated ? <p className="team-bot-truncation">仅展示前 100 条当前可访问记录的摘要。</p> : null}
                  </div>
                ) : null}
              </section> : null}
            </section>

            <section className="assistant-context-section assistant-context-summary-section" aria-label="团队摘要与审计">
              <header>
                <p>REVIEW</p>
                <h3>团队摘要与审计</h3>
              </header>
              {!selectedView ? <p>摘要前会重新验证团队助手、已保存视图及当前访问权限。</p> : <>
                <dl className="team-bot-review-list"><div><dt>当前视图</dt><dd>{selectedView.name}</dd></div><div><dt>安全范围</dt><dd>仅当前成员已授权记录</dd></div>{summary ? <><div><dt>来源记录</dt><dd>{summary.citations.length} 条</dd></div><div><dt>审计回执</dt><dd>{summary.auditEventId}</dd></div></> : null}</dl>
                {summary?.citations.length ? <ul className="team-bot-citations">{summary.citations.map((citation) => <li key={citation.recordId}><code>{citation.recordId}</code></li>)}</ul> : null}
                <button type="button" className="assistant-context-open-base" onClick={onOpenBase}>打开 Base 继续处理</button>
              </>}
            </section>
        </div>
      </section>
    </div>
  )
}
