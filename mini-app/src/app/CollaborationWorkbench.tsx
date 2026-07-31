import { useEffect, useLayoutEffect, useReducer, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import {
  Check,
  ChevronDown,
  ClipboardList,
  Database,
  FileText,
  Send,
  ShieldCheck,
  Square,
  UserRound,
} from 'lucide-react'

import type { S5Contact } from './draft-employee-types'
import type { Stage12Action, Stage12ActionRun } from './api'
import type {
  Stage08AssistantIntent,
  Stage08AssistantSafeView,
  Stage08AssistantSkill,
  Stage08AssistantSkillCatalog,
  Stage08AssistantStreamEvent,
  Stage08AssistantStreamPhase,
  Stage08CitationLabel,
  Stage08CollaborationInvocation,
  Stage08RequestedAction,
} from './stage08-collaboration-types'

type CollaborationWorkbenchProps = {
  contacts: S5Contact[]
  currentRecordId: string | null
  currentBaseId?: string | null
  currentRecordWritable?: boolean
  workspaceName?: string
  baseName?: string
  viewName?: string
  loading: boolean
  failed: boolean
  skillCatalog: Stage08AssistantSkillCatalog | null
  skillCatalogLoading: boolean
  durableRuntimeEnabled?: boolean
  onEmployeeChange: (employeeId: string) => void
  onInvokeStream: (
    request: Stage08CollaborationInvocation,
    onEvent: (event: Stage08AssistantStreamEvent) => void,
    signal: AbortSignal,
  ) => Promise<Stage08AssistantSafeView>
  onInvokeAction?: (request: Stage08CollaborationInvocation, signal: AbortSignal) => Promise<Stage12ActionRun>
  onConfirmAction?: (runId: string, action: Stage12Action, proposedValues: Record<string, unknown>) => Promise<Stage12Action>
  onRejectAction?: (runId: string, action: Stage12Action) => Promise<Stage12Action>
  onOpenDraft: (draftId: string) => void
  onRetry: () => void
  onClose: () => void
}

type TimelineItem =
  | { kind: 'status'; sequence: number; phase: Stage08AssistantStreamPhase }
  | { kind: 'answer'; sequence: number }
  | { kind: 'result'; sequence: number }
  | { kind: 'stopped'; sequence: number }
  | { kind: 'failed'; sequence: number }

type ConversationTurn = {
  requestId: string | null
  clientId: string
  question: string
  phase: Stage08AssistantStreamPhase | null
  answer: string
  result: Stage08AssistantSafeView | null
  state: 'running' | 'finalizing' | 'completed' | 'stopped' | 'failed'
  lastSequence: number
  doneSeen: boolean
  createdAt: string
  intent: Stage08AssistantIntent
  requestedAction: Stage08RequestedAction
  skill: Stage08AssistantSkill | null
  manifestVersion: string | null
  items: TimelineItem[]
  actionRun: Stage12ActionRun | null
}

type TimelineAction =
  | {
    type: 'start'
    turn: ConversationTurn
  }
  | {
    type: 'event'
    clientId: string
    event: Stage08AssistantStreamEvent
  }
  | {
    type: 'stopped'
    clientId: string
  }
  | {
    type: 'failed'
    clientId: string
  }
  | {
    type: 'complete'
    clientId: string
  }
  | { type: 'action_ready'; clientId: string; actionRun: Stage12ActionRun }
  | { type: 'action_updated'; clientId: string; action: Stage12Action }

type ComposerInvocationRoute = {
  intent: Stage08AssistantIntent
  requestedAction: Stage08RequestedAction
  skill: Stage08AssistantSkill | null
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
  cancelled: '协作未完成',
  timed_out: '协作超时，请稍后重试',
}

const phaseCopy: Record<Stage08AssistantStreamPhase, string> = {
  authorizing: '正在核验当前身份与操作范围',
  planning_context: '正在确定本次工作范围',
  analysing: '正在整理结论与下一步',
  creating_draft: '正在生成待确认草稿',
  completed: '已完成',
}

export function resolveComposerInvocationRoute({
  intent,
  requestedAction,
  selectedSkill,
}: {
  currentBaseId: string | null | undefined
  currentRecordId: string | null
  intent: Stage08AssistantIntent
  requestedAction: Stage08RequestedAction
  selectedSkill: Stage08AssistantSkill | null
}): ComposerInvocationRoute {
  return { intent, requestedAction, skill: selectedSkill }
}

function failTurn(turn: ConversationTurn, sequence = turn.lastSequence + 1): ConversationTurn {
  if (turn.state === 'failed' || turn.state === 'stopped' || turn.state === 'completed') return turn
  return {
    ...turn,
    state: 'failed',
    items: [...turn.items, { kind: 'failed', sequence }],
  }
}

function timelineReducer(turns: ConversationTurn[], action: TimelineAction): ConversationTurn[] {
  if (action.type === 'start') return [...turns, action.turn]
  return turns.map((turn) => {
    if (turn.clientId !== action.clientId) return turn
    if (action.type === 'stopped') {
      if (turn.state !== 'running' && turn.state !== 'finalizing') return turn
      return {
        ...turn,
        state: 'stopped',
        items: [...turn.items, { kind: 'stopped', sequence: turn.items.length + 1 }],
      }
    }
    if (action.type === 'failed') {
      return failTurn(turn)
    }
    if (action.type === 'complete') {
      if (turn.state !== 'finalizing' || !turn.doneSeen) return turn
      return { ...turn, state: 'completed' }
    }
    if (action.type === 'action_ready') {
      return { ...turn, actionRun: action.actionRun, phase: 'creating_draft', state: 'completed', doneSeen: true }
    }
    if (action.type === 'action_updated') {
      if (!turn.actionRun) return turn
      return { ...turn, actionRun: { ...turn.actionRun, actions: turn.actionRun.actions.map((item) => item.slotId === action.action.slotId ? action.action : item) } }
    }
    const event = action.event
    if (turn.state === 'stopped' || turn.state === 'failed' || turn.state === 'completed' || turn.doneSeen) return turn
    if ((turn.requestId !== null && event.requestId !== turn.requestId) || event.sequence !== turn.lastSequence + 1) {
      return failTurn(turn, event.sequence)
    }
    const requestId = turn.requestId ?? event.requestId
    const eventBase = { ...turn, requestId, lastSequence: event.sequence }
    if (event.event === 'done') {
      if (turn.state !== 'finalizing') return failTurn(eventBase, event.sequence)
      return { ...eventBase, doneSeen: true }
    }
    if (event.event === 'status') {
      if (turn.state === 'finalizing' && event.phase !== 'completed') return failTurn(eventBase, event.sequence)
      if (turn.state !== 'running' && turn.state !== 'finalizing') return failTurn(eventBase, event.sequence)
      return {
        ...eventBase,
        phase: event.phase,
        items: [...turn.items, { kind: 'status', sequence: event.sequence, phase: event.phase }],
      }
    }
    if (event.event === 'answer_delta') {
      if (turn.state !== 'running') return failTurn(eventBase, event.sequence)
      const hasAnswer = turn.items.some((item) => item.kind === 'answer')
      return {
        ...eventBase,
        answer: turn.answer + event.text,
        items: hasAnswer ? turn.items : [...turn.items, { kind: 'answer', sequence: event.sequence }],
      }
    }
    if (event.event === 'result') {
      if (turn.state !== 'running') return failTurn(eventBase, event.sequence)
      const explicitSkillMismatch = turn.skill !== null && (
        event.safeView.skill?.selectionMode !== 'explicit'
        || event.safeView.skill.skillId !== turn.skill.skillId
        || event.safeView.skill.label !== turn.skill.label
        || event.safeView.skill.manifestVersion !== turn.manifestVersion
      )
      if (explicitSkillMismatch) {
        return failTurn(eventBase, event.sequence)
      }
      const hasAnswer = turn.items.some((item) => item.kind === 'answer')
      return {
        ...eventBase,
        answer: event.safeView.answer ?? '',
        result: event.safeView,
        state: 'finalizing',
        items: [
          ...turn.items,
          ...(!hasAnswer && event.safeView.answer ? [{ kind: 'answer' as const, sequence: event.sequence }] : []),
          { kind: 'result', sequence: event.sequence },
        ],
      }
    }
    if (event.event === 'error') {
      return failTurn(eventBase, event.sequence)
    }
    return eventBase
  })
}

function createClientId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `collaboration-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function formatTime(date = new Date()): string {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function EvidenceRows({ result }: { result: Stage08AssistantSafeView }) {
  if (result.citations.length === 0 && result.degradationCodes.length === 0) return null
  return <div className="collaboration-evidence-scroll">
    <table className="collaboration-evidence" aria-label="安全证据">
      <thead><tr><th>序号</th><th>安全来源</th><th>状态</th></tr></thead>
      <tbody>
        {result.citations.map((citation) => <tr key={`${citation.ordinal}:${citation.label}`}>
          <td>{String(citation.ordinal).padStart(2, '0')}</td>
          <td>{citationLabels[citation.label]}</td>
          <td>已投影</td>
        </tr>)}
        {result.degradationCodes.map((code, index) => <tr key={code}>
          <td>{String(result.citations.length + index + 1).padStart(2, '0')}</td>
          <td>结果状态</td>
          <td>{code}</td>
        </tr>)}
      </tbody>
    </table>
  </div>
}

function DraftSheet({ draftId, onOpenDraft }: { draftId: string; onOpenDraft: (draftId: string) => void }) {
  return <section className="collaboration-draft-sheet" aria-label="待确认草稿">
    <div>
      <span>待确认 · 未写入</span>
      <strong>跟进草稿已进入既有确认流程</strong>
      <p>请在待确认中心复核内容；本工作台不会自动确认或重复提交。</p>
    </div>
    <button type="button" onClick={() => onOpenDraft(draftId)}>查看待确认草稿</button>
  </section>
}

function ActionReviewCard({ runId, action, onConfirm, onReject }: { runId: string; action: Stage12Action; onConfirm?: CollaborationWorkbenchProps['onConfirmAction']; onReject?: CollaborationWorkbenchProps['onRejectAction'] }) {
  const [currentAction, setCurrentAction] = useState(action)
  const [values, setValues] = useState<Record<string, unknown>>(action.proposedValues)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pending = currentAction.status === 'pending_confirmation'
  const label = { 'record.create': '创建记录', 'record.update': '更新记录', 'task.create': '创建任务', 'reminder.request': '提醒请求' }[currentAction.actionKind]
  const execute = async (kind: 'confirm' | 'reject') => {
    if (!pending || busy || !onConfirm || !onReject) return
    setBusy(true)
    setError(null)
    try {
      const updated = kind === 'confirm'
        ? await onConfirm(runId, currentAction, values)
        : await onReject(runId, currentAction)
      setCurrentAction(updated)
    } catch {
      setError('操作未完成，请刷新状态后重试。')
    } finally {
      setBusy(false)
    }
  }
  return <section className="collaboration-draft-sheet stage12-action-card" aria-label={`${label}待确认`}>
    <div>
      <span>{pending ? '待确认 · 尚未写入' : `状态 · ${currentAction.status}`}</span>
      <strong>{currentAction.safeSummary}</strong>
      {currentAction.editableFields.map((field) => <label key={field.fieldId}>
        <small>{field.label}{field.required ? '（必填）' : ''}</small>
        {field.fieldType === 'checkbox'
          ? <input type="checkbox" checked={Boolean(values[field.fieldKey])} disabled={!pending || busy} onChange={(event) => setValues((current) => ({ ...current, [field.fieldKey]: event.target.checked }))} />
          : <input type={field.fieldType === 'number' ? 'number' : 'text'} value={String(values[field.fieldKey] ?? '')} disabled={!pending || busy} onChange={(event) => setValues((current) => ({ ...current, [field.fieldKey]: field.fieldType === 'number' ? Number(event.target.value) : event.target.value }))} />}
      </label>)}
      {error ? <p role="alert">{error}</p> : null}
    </div>
    <div className="stage12-action-controls">
      <button type="button" disabled={!pending || busy || !onReject} onClick={() => { void execute('reject') }}>拒绝</button>
      <button type="button" disabled={!pending || busy || !onConfirm} onClick={() => { void execute('confirm') }}>确认执行</button>
    </div>
  </section>
}

function ScopeContent({
  selectedEmployee,
  currentRecordId,
  canDraft,
}: {
  selectedEmployee: S5Contact | null
  currentRecordId: string | null
  canDraft: boolean
}) {
  return <div className="collaboration-scope-content">
    <section>
      <span>当前记录</span>
      <strong>{currentRecordId ? '已关联当前记录' : '未选择记录'}</strong>
      <p>{currentRecordId ? '仅展示当前权限范围内的安全结果。' : '当前协作仅允许只读分析。'}</p>
    </section>
    <section>
      <span>数字员工</span>
      <strong>{selectedEmployee?.name ?? '未选择'}</strong>
      <p>{selectedEmployee?.description ?? '当前没有可调用的数字员工。'}</p>
    </section>
    <section>
      <span>允许动作</span>
      <ul>
        <li><Check aria-hidden="true" />只读分析</li>
        <li className={canDraft ? '' : 'muted'}><Check aria-hidden="true" />{canDraft ? '生成待确认草稿' : '草稿写入未授权'}</li>
      </ul>
    </section>
    <section>
      <span>审计</span>
      <p>最终结果、草稿与受控动作继续使用既有审计链路。</p>
    </section>
  </div>
}

function TimelineTurn({
  turn,
  index,
  onOpenDraft,
  onRetry,
  onConfirmAction,
  onRejectAction,
}: {
  turn: ConversationTurn
  index: number
  onOpenDraft: (draftId: string) => void
  onRetry: (turn: ConversationTurn) => void
  onConfirmAction?: (runId: string, action: Stage12Action, values: Record<string, unknown>) => Promise<Stage12Action>
  onRejectAction?: (runId: string, action: Stage12Action) => Promise<Stage12Action>
}) {
  const sequence = String(index + 1).padStart(2, '0')
  return <article className={`collaboration-turn ${turn.state}`} data-turn-state={turn.state} aria-label={`协作请求 ${sequence}`}>
    <div className="collaboration-turn-mobile-meta" aria-hidden="true">
      <span>{sequence}</span><time>{turn.createdAt}</time>
    </div>
    <header className="collaboration-question-entry">
      <UserRound aria-hidden="true" />
      <div><span>你的请求</span><p>{turn.question}</p></div>
    </header>
    <div className="collaboration-entry-list">
      {turn.items.map((item) => {
        if (item.kind === 'status') return <div className={`collaboration-status-entry phase-${item.phase}`} key={`status:${item.sequence}`}>
          {item.phase === 'completed' ? <Check aria-hidden="true" /> : <ClipboardList aria-hidden="true" />}
          <span>{phaseCopy[item.phase]}</span>
        </div>
        if (item.kind === 'answer') return <section className="collaboration-answer-entry" key={`answer:${item.sequence}`}>
          <span>安全答案</span>
          <p>{turn.answer}</p>
        </section>
        if (item.kind === 'result') {
          const result = turn.result
          if (!result) return null
          return <div className="collaboration-safe-result" key={`result:${item.sequence}`}>
            <strong>{statusCopy[result.status]}</strong>
            {turn.state === 'finalizing' ? <span className="collaboration-finalizing-state">正在确认传输完成…</span> : null}
            <EvidenceRows result={result} />
            {result.draftId ? <DraftSheet draftId={result.draftId} onOpenDraft={onOpenDraft} /> : null}
          </div>
        }
        if (item.kind === 'stopped') return <div className="collaboration-inline-state stopped" key={`stopped:${item.sequence}`}>
          <strong>已停止查看结果</strong>
          <span>这只会停止当前浏览器继续接收内容，服务端执行状态未知。</span>
          {turn.requestedAction === 'read_only' ? <button type="button" onClick={() => onRetry(turn)}>重新发送</button> : <small>请先检查待确认草稿队列或审计记录，不会自动重试。</small>}
        </div>
        return <div className="collaboration-inline-state failed" key={`failed:${item.sequence}`}>
          <strong>连接中断，可重试</strong>
          <span>没有使用前端缓存伪装完成结果。</span>
          {turn.requestedAction === 'read_only' ? <button type="button" onClick={() => onRetry(turn)}>重新发送</button> : <small>请先检查待确认草稿队列或审计记录，不会自动重试。</small>}
        </div>
      })}
      {turn.actionRun ? <section className="stage12-action-review" aria-label="受控动作确认">
        <header><strong>执行计划</strong><span>{turn.actionRun.objectives.length} 个 Objective · {turn.actionRun.actions.length} 个 Action</span></header>
        <ol>{turn.actionRun.objectives.map((objective) => <li key={objective.objectiveId}><span>{objective.kind}</span><strong>{objective.safeSummary ?? objective.status}</strong></li>)}</ol>
        {turn.actionRun.actions.map((action) => <ActionReviewCard key={action.slotId} runId={turn.actionRun!.runId} action={action} onConfirm={onConfirmAction} onReject={onRejectAction} />)}
      </section> : null}
    </div>
  </article>
}

export function CollaborationWorkbench({
  contacts,
  currentRecordId,
  currentBaseId = null,
  currentRecordWritable = false,
  workspaceName = '当前工作区',
  baseName = '未选择 Base',
  viewName = '未选择视图',
  loading,
  failed,
  skillCatalog,
  skillCatalogLoading,
  durableRuntimeEnabled = false,
  onEmployeeChange,
  onInvokeStream,
  onInvokeAction,
  onConfirmAction,
  onRejectAction,
  onOpenDraft,
  onRetry,
  onClose,
}: CollaborationWorkbenchProps) {
  const [employeeId, setEmployeeId] = useState<string | null>(null)
  const [intent, setIntent] = useState<Stage08AssistantIntent>('mixed')
  const [requestedAction, setRequestedAction] = useState<Stage08RequestedAction>('read_only')
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [scopeOpen, setScopeOpen] = useState(false)
  const [turns, dispatch] = useReducer(timelineReducer, [])
  const controllerRef = useRef<AbortController | null>(null)
  const textboxRef = useRef<HTMLTextAreaElement | null>(null)
  const dialogRef = useRef<HTMLElement | null>(null)
  const transcriptRef = useRef<HTMLElement | null>(null)
  const nearTranscriptBottomRef = useRef(true)
  const [portalNode] = useState<HTMLDivElement | null>(() => typeof document === 'undefined' ? null : document.createElement('div'))
  const selectedEmployee = contacts.find((contact) => contact.id === employeeId) ?? null
  const selectedSkill = skillCatalog?.skills.find((skill) => skill.skillId === selectedSkillId && skill.enabled) ?? null
  const currentRecordScopeProven = Boolean(
    currentRecordId
    && currentRecordWritable
    && currentBaseId
    && selectedEmployee
    && selectedEmployee.baseId === currentBaseId,
  )
  const canUseDraftSkill = (skill: Stage08AssistantSkill | null) => Boolean(
    currentRecordScopeProven
    && skill?.enabled
    && skill.supportedActions.includes('draft_update'),
  )
  const canDraft = canUseDraftSkill(selectedSkill)
  const inFlight = turns.some((turn) => turn.state === 'running' || turn.state === 'finalizing')

  useLayoutEffect(() => {
    if (!portalNode) return
    portalNode.dataset.ledgerlineModal = 'true'
    document.body.append(portalNode)
    return () => portalNode.remove()
  }, [portalNode])

  useEffect(() => {
    if (!portalNode) return
    const background = Array.from(document.body.children).filter((element) => element !== portalNode)
    const priorState = background.map((element) => ({
      element,
      ariaHidden: element.getAttribute('aria-hidden'),
      inert: (element as HTMLElement).inert,
    }))
    for (const { element } of priorState) {
      element.setAttribute('aria-hidden', 'true')
      ;(element as HTMLElement).inert = true
    }
    return () => {
      for (const { element, ariaHidden, inert } of priorState) {
        if (ariaHidden === null) element.removeAttribute('aria-hidden')
        else element.setAttribute('aria-hidden', ariaHidden)
        ;(element as HTMLElement).inert = inert
      }
    }
  }, [portalNode])

  useLayoutEffect(() => {
    textboxRef.current?.focus()
  }, [])

  useEffect(() => {
    setEmployeeId((current) => contacts.some((contact) => contact.id === current) ? current : contacts[0]?.id ?? null)
  }, [contacts])

  useEffect(() => {
    if (employeeId) onEmployeeChange(employeeId)
  }, [employeeId, currentRecordId])

  useEffect(() => {
    setSelectedSkillId(null)
    setRequestedAction('read_only')
  }, [employeeId, currentRecordId, currentBaseId, currentRecordWritable])

  useEffect(() => {
    if (selectedSkillId && !skillCatalog?.skills.some((skill) => skill.skillId === selectedSkillId && skill.enabled)) {
      setSelectedSkillId(null)
      setRequestedAction('read_only')
    }
  }, [selectedSkillId, skillCatalog])

  useEffect(() => {
    if (requestedAction === 'draft_update' && !canDraft) {
      setSelectedSkillId(null)
      setRequestedAction('read_only')
    }
  }, [canDraft, requestedAction])

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) {
        controllerRef.current?.abort()
        onClose()
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      window.removeEventListener('keydown', closeOnEscape)
      controllerRef.current?.abort()
    }
  }, [onClose])

  useLayoutEffect(() => {
    const transcript = transcriptRef.current
    if (transcript && nearTranscriptBottomRef.current) transcript.scrollTop = transcript.scrollHeight
  }, [turns])

  function startInvocation(
    question: string,
    nextIntent: Stage08AssistantIntent,
    nextRequestedAction: Stage08RequestedAction,
    nextSkill: Stage08AssistantSkill | null,
  ) {
    const cleanQuery = question.trim()
    const recordAction = nextRequestedAction === 'draft_update' || nextRequestedAction === 'reminder_request'
    if (!selectedEmployee || !cleanQuery || inFlight || (recordAction && !currentRecordId) || (nextRequestedAction === 'draft_update' && !canDraft)) return
    const clientId = createClientId()
    const controller = new AbortController()
    controllerRef.current = controller
    const request: Stage08CollaborationInvocation = {
      employeeId: selectedEmployee.id,
      intent: nextIntent,
      query: cleanQuery,
      requestedAction: nextRequestedAction,
      targetRecordId: recordAction ? currentRecordId : null,
      skillId: nextSkill?.skillId ?? null,
    }
    dispatch({
      type: 'start',
      turn: {
        requestId: null,
        clientId,
        question: cleanQuery,
        phase: null,
        answer: '',
        result: null,
        state: 'running',
        lastSequence: 0,
        doneSeen: false,
        createdAt: formatTime(),
        intent: nextIntent,
        requestedAction: nextRequestedAction,
        skill: nextSkill,
        manifestVersion: nextSkill ? skillCatalog?.manifestVersion ?? null : null,
        items: [],
        actionRun: null,
      },
    })
    setQuery('')
    if (nextRequestedAction !== 'read_only' && durableRuntimeEnabled && onInvokeAction) {
      void onInvokeAction(request, controller.signal).then((actionRun) => {
        dispatch({ type: 'action_ready', clientId, actionRun })
      }).catch(() => {
        dispatch({ type: controller.signal.aborted ? 'stopped' : 'failed', clientId })
      }).finally(() => {
        if (controllerRef.current === controller) controllerRef.current = null
      })
      return
    }
    void onInvokeStream(
      request,
      (event) => dispatch({ type: 'event', clientId, event }),
      controller.signal,
    ).then(() => {
      dispatch({ type: 'complete', clientId })
    }).catch(() => {
      dispatch({ type: controller.signal.aborted ? 'stopped' : 'failed', clientId })
    }).finally(() => {
      if (controllerRef.current === controller) controllerRef.current = null
    })
  }

  function submit() {
    const route = resolveComposerInvocationRoute({
      currentBaseId,
      currentRecordId,
      intent,
      requestedAction,
      selectedSkill,
    })
    startInvocation(query, route.intent, route.requestedAction, route.skill)
  }

  function applySkill(skill: Stage08AssistantSkill | null) {
    if (skill && !skill.enabled) return
    const draftAction = Boolean(skill?.supportedActions.includes('draft_update'))
    if (draftAction && !canUseDraftSkill(skill)) return
    setSelectedSkillId(skill?.skillId ?? null)
    setIntent(skill?.supportedIntents[0] ?? 'mixed')
    setRequestedAction(draftAction ? 'draft_update' : 'read_only')
    requestAnimationFrame(() => textboxRef.current?.focus())
  }

  function stopViewing() {
    controllerRef.current?.abort()
    const current = [...turns].reverse().find((turn) => turn.state === 'running' || turn.state === 'finalizing')
    if (current) dispatch({ type: 'stopped', clientId: current.clientId })
  }

  function closeWorkbench() {
    controllerRef.current?.abort()
    onClose()
  }

  function trapFocus(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      closeWorkbench()
      return
    }
    if (event.key !== 'Tab') return
    const dialog = dialogRef.current
    if (!dialog) return
    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), [href], select:not(:disabled), textarea:not(:disabled), input:not(:disabled), [tabindex]:not([tabindex="-1"])'))
      .filter((element) => !element.hidden && element.getAttribute('aria-hidden') !== 'true')
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const workbench = <div className="collaboration-backdrop" role="presentation" onMouseDown={(event) => {
    if (event.target === event.currentTarget) closeWorkbench()
  }}>
    <section ref={dialogRef} className="collaboration-workbench" aria-label="AI 对话" aria-modal="true" aria-describedby="collaboration-ledger-description" role="dialog" onKeyDown={trapFocus}>
      <header className="collaboration-context-strip" data-testid="collaboration-context-strip">
        <div className="collaboration-ledger-title">
          <span className="collaboration-ledger-mark" aria-hidden="true">L</span>
          <div><strong>Ledgerline</strong><small>受控 AI 协作台账</small></div>
        </div>
        <p id="collaboration-ledger-description" className="sr-only">受权限和审计约束的 AI 协作台账。</p>
        <div className="collaboration-context-track" aria-label="当前安全上下文">
          <span><small>工作区</small><strong>{workspaceName}</strong></span>
          <span><small>Base</small><strong>{baseName}</strong></span>
          <span><small>视图</small><strong>{viewName}</strong></span>
          <span><small>记录</small><strong>{currentRecordId ? '当前记录' : '未选择'}</strong></span>
          <label>
            <small>数字员工</small>
            <select aria-label="选择数字员工" value={employeeId ?? ''} onChange={(event) => {
              setEmployeeId(event.target.value || null)
              setSelectedSkillId(null)
              setRequestedAction('read_only')
            }}>
              {contacts.length === 0 ? <option value="">暂无可用员工</option> : contacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.name}</option>)}
            </select>
          </label>
        </div>
        <div className="collaboration-context-actions">
          <button className="collaboration-scope-toggle" type="button" aria-label="范围与审计" aria-expanded={scopeOpen} aria-controls="collaboration-safe-scope-drawer" onClick={() => setScopeOpen((current) => !current)}>
            <ShieldCheck aria-hidden="true" /><span>范围与审计</span><ChevronDown aria-hidden="true" />
          </button>
          <button className="collaboration-close" type="button" aria-label="关闭 AI 对话" onClick={closeWorkbench}>×</button>
        </div>
      </header>

      <div className="collaboration-ledger-body">
        <ol className="collaboration-index-rail" aria-label="时间线索引">
          {turns.length === 0 ? <li className="empty"><span>00</span><time>--:--:--</time></li> : turns.map((turn, index) => <li className={turn.state === 'running' ? 'active' : ''} key={turn.clientId}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            <time>{turn.createdAt}</time>
            <i aria-hidden="true" />
          </li>)}
        </ol>

        <main ref={transcriptRef} className="collaboration-transcript" role="log" aria-label="协作时间线" aria-live="polite" onScroll={(event) => {
          const transcript = event.currentTarget
          nearTranscriptBottomRef.current = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight <= 48
        }}>
          {failed ? <section className="collaboration-load-state">
            <p>暂时无法读取可协作的数字员工，请稍后重试。</p>
            <button type="button" onClick={onRetry}>重试</button>
          </section> : loading ? <p className="collaboration-empty-ledger">正在读取当前权限范围内的数字员工…</p> : turns.length === 0 ? <section className="collaboration-empty-ledger">
            <ClipboardList aria-hidden="true" />
            <strong>从一句话开始</strong>
            <p>{currentBaseId || currentRecordId ? '直接提问，或选择一个技能来限定工作方式。回答只会使用当前授权范围内的业务材料。' : '可以直接开始对话。打开业务 Base 后，我会把当前授权的表格、视图和记录作为分析上下文。'}</p>
          </section> : turns.map((turn, index) => <TimelineTurn
            key={turn.clientId}
            turn={turn}
            index={index}
            onOpenDraft={onOpenDraft}
            onRetry={(retryTurn) => startInvocation(retryTurn.question, retryTurn.intent, retryTurn.requestedAction, retryTurn.skill)}
            onConfirmAction={onConfirmAction}
            onRejectAction={onRejectAction}
          />)}
        </main>

        <aside className="collaboration-safe-scope" aria-label="安全范围">
          <header><ShieldCheck aria-hidden="true" /><div><strong>安全范围</strong><span>当前已授权摘要</span></div></header>
          <ScopeContent selectedEmployee={selectedEmployee} currentRecordId={currentRecordId} canDraft={canDraft} />
        </aside>

        <section id="collaboration-safe-scope-drawer" className="collaboration-scope-drawer" hidden={!scopeOpen} aria-label="范围与审计详情">
          <ScopeContent selectedEmployee={selectedEmployee} currentRecordId={currentRecordId} canDraft={canDraft} />
        </section>
      </div>

      <form className="collaboration-composer" aria-label="协作输入" onSubmit={(event) => { event.preventDefault(); submit() }}>
        <div className="collaboration-skill-strip" aria-label="快捷技能">
          <button
            type="button"
            data-skill-id="auto"
            aria-label="自动选择"
            aria-pressed={selectedSkillId === null}
            disabled={loading || skillCatalogLoading || !selectedEmployee}
            title="自动选择：由服务端在当前授权范围内决定技能"
            onClick={() => applySkill(null)}
          >
            <ClipboardList aria-hidden="true" /><span>自动选择</span><small>服务端选择</small>
          </button>
          {(skillCatalog?.skills ?? []).map((skill) => {
            const disabled = loading || skillCatalogLoading || !selectedEmployee || !skill.enabled || (skill.supportedActions.includes('draft_update') && !canUseDraftSkill(skill))
            return <button
              type="button"
              data-skill-id={skill.skillId}
              aria-label={skill.label}
              aria-pressed={selectedSkillId === skill.skillId}
              key={skill.skillId}
              disabled={disabled}
              title={`${skill.label}：${skill.enabled ? skill.description : skill.disabledReason}`}
              onClick={() => applySkill(skill)}
            >
              {skill.supportedActions.includes('draft_update') ? <FileText aria-hidden="true" /> : skill.supportedIntents.includes('business_fact') ? <Database aria-hidden="true" /> : <ClipboardList aria-hidden="true" />}
              <span>{skill.label}</span>
              <small>{skill.enabled ? skill.description : skill.disabledReason}</small>
            </button>
          })}
        </div>
        <div className="collaboration-composer-row">
          <label>
            <span className="sr-only">协作问题</span>
            <textarea
              ref={textboxRef}
              aria-label="协作问题"
              maxLength={600}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  submit()
                }
              }}
              placeholder="输入你的问题，或使用快捷技能"
            />
          </label>
          <div className="collaboration-composer-actions">
            {durableRuntimeEnabled ? <label>
              <span className="sr-only">动作模式</span>
              <select aria-label="动作模式" value={requestedAction} onChange={(event) => {
                const action = event.target.value as Stage08RequestedAction
                setRequestedAction(action)
                if (action !== 'read_only') {
                  setSelectedSkillId(null)
                  setIntent('controlled_action')
                }
              }}>
                <option value="read_only">只读分析</option>
                <option value="auto">自动识别动作（需确认）</option>
                <option value="task_create">创建任务（需确认）</option>
                <option value="draft_create">创建记录（需确认）</option>
                <option value="draft_update" disabled={!currentRecordId || !canDraft}>更新当前记录（需确认）</option>
                <option value="reminder_request" disabled={!currentRecordId}>提醒当前记录（需确认）</option>
              </select>
            </label> : null}
            <span>{requestedAction === 'draft_update'
              ? '草稿模式 · 确认后写入'
              : requestedAction !== 'read_only'
                ? '受控动作 · 确认前不写入'
              : durableRuntimeEnabled
                ? '只读模式 · 可恢复事件流'
                : '只读模式 · 不写入'}</span>
            {inFlight ? <button className="collaboration-stop" type="button" onClick={stopViewing}><Square aria-hidden="true" />停止查看</button> : null}
            <button className="collaboration-send" type="submit" aria-label="发送问题" disabled={loading || inFlight || !selectedEmployee || !query.trim() || (requestedAction === 'draft_update' && !canDraft)}>
              <Send aria-hidden="true" />发送
            </button>
          </div>
        </div>
      </form>
    </section>
  </div>
  return portalNode ? createPortal(workbench, portalNode) : null
}
