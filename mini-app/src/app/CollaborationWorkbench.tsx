import { useEffect, useState } from 'react'

import type { S5Contact } from './draft-employee-types'
import type { Stage08AssistantIntent, Stage08AssistantSafeView, Stage08CollaborationInvocation, Stage08CitationLabel, Stage08RequestedAction } from './stage08-collaboration-types'

type CollaborationWorkbenchProps = {
  variant?: 'dialog' | 'side-panel'
  contacts: S5Contact[]
  currentRecordId: string | null
  loading: boolean
  failed: boolean
  result: Stage08AssistantSafeView | null
  onInvoke: (request: Stage08CollaborationInvocation) => Promise<Stage08AssistantSafeView>
  onOpenDraft: (draftId: string) => void
  onRetry: () => void
  onClose: () => void
}

type ConversationTurn = {
  question: string
  result: Stage08AssistantSafeView
}

const citationLabels: Record<Stage08CitationLabel, string> = {
  business_data: '业务表格',
  confirmed_memory: '长期记忆',
  group_context: '已使用受权群聊上下文作为证据',
  retrieved_material: '知识库资料',
  analysis_from_current_material: '当前材料分析',
  general_advice: '通用建议',
}

const statusCopy: Record<Stage08AssistantSafeView['status'], string> = {
  completed: '分析已完成',
  draft_pending: '已生成待确认草稿',
  degraded: '当前材料不足，未生成可用答案',
  denied: '当前权限不允许执行这项协作',
  failed: '分析暂时无法完成',
  cancelled: '协作已取消',
  timed_out: '协作超时，请稍后重试',
}

function SafeResultCard({ result, citationSuffix, onOpenDraft }: { result: Stage08AssistantSafeView; citationSuffix: string; onOpenDraft: (draftId: string) => void }) {
  return <div className="collaboration-result-card">
    <strong>{statusCopy[result.status]}</strong>
    {result.answer ? <p>{result.answer}</p> : null}
    {result.citations.length > 0 ? <ul aria-label={`安全证据类别 ${citationSuffix}`}>{result.citations.map((citation) => <li key={`${citation.ordinal}:${citation.label}`}>{citationLabels[citation.label]}</li>)}</ul> : null}
    {result.degradationCodes.length > 0 ? <small>状态：{result.degradationCodes.join('、')}</small> : null}
    {result.draftId ? <button type="button" onClick={() => onOpenDraft(result.draftId!)}>查看待确认草稿</button> : null}
  </div>
}

export function CollaborationWorkbench({ variant = 'dialog', contacts, currentRecordId, loading, failed, result, onInvoke, onOpenDraft, onRetry, onClose }: CollaborationWorkbenchProps) {
  const [employeeId, setEmployeeId] = useState<string | null>(null)
  const [intent, setIntent] = useState<Stage08AssistantIntent>('mixed')
  const [requestedAction, setRequestedAction] = useState<Stage08RequestedAction>('read_only')
  const [query, setQuery] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [localResult, setLocalResult] = useState<Stage08AssistantSafeView | null>(null)
  const [history, setHistory] = useState<ConversationTurn[]>([])
  const selectedEmployee = contacts.find((contact) => contact.id === employeeId) ?? null
  const canDraft = Boolean(currentRecordId && selectedEmployee?.availableIntents.includes('draft_update'))
  const displayResult = history.at(-1)?.result ?? result ?? localResult

  useEffect(() => {
    setEmployeeId((current) => contacts.some((contact) => contact.id === current) ? current : contacts[0]?.id ?? null)
  }, [contacts])

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  async function submit() {
    const cleanQuery = query.trim()
    if (!selectedEmployee || !cleanQuery || submitting || (requestedAction === 'draft_update' && !canDraft)) return
    setSubmitting(true)
    try {
      const nextResult = await onInvoke({
        employeeId: selectedEmployee.id,
        intent,
        query: cleanQuery,
        requestedAction,
        targetRecordId: requestedAction === 'draft_update' ? currentRecordId : null,
      })
      setLocalResult(nextResult)
      setHistory((current) => [...current, { question: cleanQuery, result: nextResult }])
      setQuery('')
    } catch {
      // The parent owns fixed denied/failed copy and must never expose raw transport details.
    } finally {
      setSubmitting(false)
    }
  }

  return <div className={`collaboration-backdrop ${variant}`} role="presentation" onMouseDown={(event) => { if (variant === 'dialog' && event.target === event.currentTarget) onClose() }}>
    <aside className={`collaboration-workbench ${variant === 'side-panel' ? 'side-panel' : ''}`} aria-label="AI 对话" aria-modal={variant === 'dialog' ? 'true' : 'false'} role="dialog">
      <header className="collaboration-header">
        <div><p>AUTHORIZED AI COLLABORATION</p><h2>AI 对话</h2><span>每次提问都会重新检索当前已授权的业务、群聊、记忆与知识。</span></div>
        <button type="button" aria-label="关闭 AI 对话" onClick={onClose}>×</button>
      </header>
      {failed ? <section className="collaboration-state" role="alert"><p>暂时无法读取可协作的数字员工，请稍后重试。</p><button type="button" onClick={onRetry}>重试</button></section> : <div className="collaboration-columns">
        <section className="collaboration-section" aria-label="协作数字员工">
          <header><p>EMPLOYEE</p><h3>可用数字员工</h3></header>
          {contacts.length === 0 ? <p>当前没有可调用的数字员工。</p> : <ul>{contacts.map((contact) => <li key={contact.id}><button type="button" aria-label={`选择数字员工 ${contact.name}`} className={contact.id === employeeId ? 'selected' : ''} onClick={() => { setEmployeeId(contact.id); setRequestedAction('read_only'); setLocalResult(null) }}><strong>{contact.name}</strong><span>{contact.description}</span></button></li>)}</ul>}
        </section>
        <section className="collaboration-section" aria-label="协作请求">
          <header><p>ASK</p><h3>向 AI 提问</h3></header>
          <label>协作意图<select aria-label="协作意图" value={intent} onChange={(event) => setIntent(event.target.value as Stage08AssistantIntent)}><option value="mixed">综合业务与记忆</option><option value="business_fact">查询业务事实</option><option value="memory_lookup">查询长期记忆</option><option value="general_advice">通用建议</option></select></label>
          <label>执行方式<select aria-label="执行方式" value={requestedAction} onChange={(event) => setRequestedAction(event.target.value as Stage08RequestedAction)}><option value="read_only">仅分析，不写入</option>{canDraft ? <option value="draft_update">生成待确认草稿</option> : null}</select></label>
          <p className="collaboration-record-hint">{canDraft ? '当前已打开一条有权限的记录，可选择生成草稿；草稿仍需在既有确认中心审批。' : '未打开可更新记录，因此本次只能只读分析。'}</p>
          <label>协作问题<textarea aria-label="协作问题" maxLength={600} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="例如：客户下一步如何推进？" /></label>
          <button className="collaboration-submit" type="button" disabled={loading || submitting || !selectedEmployee || !query.trim()} onClick={() => void submit()}>{submitting ? 'AI 正在分析…' : '发送问题'}</button>
        </section>
        <section className="collaboration-section collaboration-result" aria-label="AI 对话记录">
          <header><p>SAFE HISTORY</p><h3>对话记录</h3></header>
          {history.length > 0 ? <ol className="collaboration-history" aria-label="AI 对话记录">{history.map((turn, index) => <li key={`${index}:${turn.question}`}><p className="collaboration-question">{turn.question}</p><SafeResultCard result={turn.result} citationSuffix={String(index + 1)} onOpenDraft={onOpenDraft} /></li>)}</ol> : !displayResult ? <p>选择数字员工后直接提问。这里仅显示经过安全投影的答案和证据类别。</p> : <SafeResultCard result={displayResult} citationSuffix="当前" onOpenDraft={onOpenDraft} />}
        </section>
      </div>}
    </aside>
  </div>
}
