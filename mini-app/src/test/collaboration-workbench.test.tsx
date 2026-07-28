import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { CollaborationWorkbench } from '../app/CollaborationWorkbench'
import type { S5Contact } from '../app/draft-employee-types'
import type {
  Stage08AssistantSafeView,
  Stage08AssistantSkillCatalog,
  Stage08AssistantStreamEvent,
  Stage08CollaborationInvocation,
} from '../app/stage08-collaboration-types'

const draftCapableContact: S5Contact = {
  id: 'employee-1',
  baseId: 'base-1',
  name: '客户协作员工',
  description: '跟进和风险建议',
  status: 'active' as const,
  availableIntents: ['summarize', 'draft_update'],
}

const completedResult: Stage08AssistantSafeView = {
  status: 'completed',
  answer: '建议先确认预算，再安排复盘。',
  citations: [{ ordinal: 1, label: 'business_data' }],
  degradationCodes: [],
  draftId: null,
  skill: null,
}

const skillCatalog: Stage08AssistantSkillCatalog = {
  manifestVersion: 'stage06-larksuite-skills-v1' as const,
  defaultSelection: 'auto' as const,
  skills: [
    {
      skillId: 'platform-base', label: '查表问答', description: '基于授权记录回答问题', enabled: true, disabledReason: null,
      supportedIntents: ['business_fact', 'mixed'] as ('business_fact' | 'mixed')[], supportedActions: ['read_only'] as const, confirmationPolicy: 'read_only' as const,
    },
    {
      skillId: 'platform-draft-update', label: '生成跟进草稿', description: '创建待确认草稿', enabled: true, disabledReason: null,
      supportedIntents: ['mixed'] as ('business_fact' | 'mixed')[], supportedActions: ['draft_update'] as const, confirmationPolicy: 'draft_required_for_write' as const,
    },
    {
      skillId: 'platform-telegram-im', label: '群聊上下文', description: '当前群聊范围不可用', enabled: false, disabledReason: 'chat_scope_unavailable' as const,
      supportedIntents: ['mixed'] as ('business_fact' | 'mixed')[], supportedActions: ['read_only'] as const, confirmationPolicy: 'read_only' as const,
    },
  ],
}

type StreamInvoker = (
  request: Stage08CollaborationInvocation,
  onEvent: (event: Stage08AssistantStreamEvent) => void,
  signal: AbortSignal,
) => Promise<Stage08AssistantSafeView>

function successfulStream(result = completedResult): StreamInvoker {
  return vi.fn(async (_request, onEvent) => {
    onEvent({ event: 'status', sequence: 1, requestId: 'request-1', phase: 'authorizing' })
    onEvent({ event: 'answer_delta', sequence: 2, requestId: 'request-1', text: result.answer ?? '' })
    onEvent({ event: 'result', sequence: 3, requestId: 'request-1', safeView: result })
    onEvent({ event: 'status', sequence: 4, requestId: 'request-1', phase: 'completed' })
    onEvent({ event: 'done', sequence: 5, requestId: 'request-1' })
    return result
  })
}

function renderWorkbench({
  contacts = [draftCapableContact],
  currentRecordId = 'record-1',
  currentBaseId = 'base-1',
  currentRecordWritable = true,
  onInvokeStream = successfulStream(),
  onOpenDraft = vi.fn(),
  catalog = skillCatalog,
  catalogLoading = false,
  onEmployeeChange = vi.fn(),
}: {
  contacts?: typeof draftCapableContact[]
  currentRecordId?: string | null
  currentBaseId?: string | null
  currentRecordWritable?: boolean
  onInvokeStream?: StreamInvoker
  onOpenDraft?: (draftId: string) => void
  catalog?: Stage08AssistantSkillCatalog | null
  catalogLoading?: boolean
  onEmployeeChange?: (employeeId: string) => void
} = {}) {
  return {
    onInvokeStream,
    onOpenDraft,
    ...render(<CollaborationWorkbench
      contacts={contacts}
      currentRecordId={currentRecordId}
      currentBaseId={currentBaseId}
      currentRecordWritable={currentRecordWritable}
      loading={false}
      failed={false}
      skillCatalog={catalog}
      skillCatalogLoading={catalogLoading}
      onEmployeeChange={onEmployeeChange}
      onInvokeStream={onInvokeStream}
      onOpenDraft={onOpenDraft}
      onRetry={vi.fn()}
      onClose={vi.fn()}
    />),
  }
}

test('uses one Ledgerline context strip, continuous timeline and composer with accessible narrow scope controls', () => {
  renderWorkbench()

  expect(screen.getByTestId('collaboration-context-strip')).toBeVisible()
  const timeline = screen.getByRole('log', { name: '协作时间线' })
  const composer = screen.getByRole('form', { name: '协作输入' })
  expect(timeline).toHaveAttribute('aria-live', 'polite')
  expect(screen.getByRole('complementary', { name: '安全范围' })).toBeVisible()
  const scopeToggle = screen.getByRole('button', { name: '范围与审计' })
  expect(scopeToggle).toHaveAttribute('aria-controls', 'collaboration-safe-scope-drawer')
  expect(screen.queryByRole('heading', { name: '可用数字员工' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '向 AI 提问' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '对话记录' })).not.toBeInTheDocument()
  expect(timeline.compareDocumentPosition(composer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

test('renders auto plus only server catalog skills and preserves disabled safe reasons', () => {
  renderWorkbench()

  expect(screen.getByRole('button', { name: '自动选择' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: '查表问答' })).toBeEnabled()
  expect(screen.getByRole('button', { name: '生成跟进草稿' })).toBeEnabled()
  const disabled = screen.getByRole('button', { name: '群聊上下文' })
  expect(disabled).toBeDisabled()
  expect(disabled).toHaveTextContent('chat_scope_unavailable')
  expect(screen.queryByRole('button', { name: '智能汇总' })).not.toBeInTheDocument()
})

test('submits explicit selected skill_id and auto selection submits null', async () => {
  const onInvokeStream = successfulStream()
  renderWorkbench({ onInvokeStream })
  const textbox = screen.getByRole('textbox', { name: '协作问题' })

  fireEvent.change(textbox, { target: { value: '不要覆盖这条真实问题' } })
  fireEvent.click(screen.getByRole('button', { name: '查表问答' }))
  expect(screen.getByRole('button', { name: '查表问答' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: '自动选择' })).toHaveAttribute('aria-pressed', 'false')
  expect(textbox).toHaveValue('不要覆盖这条真实问题')
  fireEvent.change(textbox, { target: { value: '查询当前状态' } })
  fireEvent.keyDown(textbox, { key: 'Enter' })
  await waitFor(() => expect(onInvokeStream).toHaveBeenCalledTimes(1))
  expect(onInvokeStream).toHaveBeenLastCalledWith(expect.objectContaining({ skillId: 'platform-base', intent: 'business_fact' }), expect.any(Function), expect.any(AbortSignal))

  fireEvent.click(screen.getByRole('button', { name: '自动选择' }))
  fireEvent.change(textbox, { target: { value: '继续查询' } })
  fireEvent.keyDown(textbox, { key: 'Enter' })
  await waitFor(() => expect(onInvokeStream).toHaveBeenCalledTimes(2))
  expect(onInvokeStream).toHaveBeenLastCalledWith(expect.objectContaining({ skillId: null, intent: 'mixed' }), expect.any(Function), expect.any(AbortSignal))
})

test('keeps an unscoped ordinary greeting on server-side mixed routing', async () => {
  const onInvokeStream = successfulStream({
    status: 'completed',
    answer: '你好，我可以帮你梳理任务、解释技能，或在你打开业务表后分析授权数据。',
    citations: [],
    degradationCodes: [],
    draftId: null,
    skill: null,
  })
  renderWorkbench({ currentBaseId: null, currentRecordId: null, onInvokeStream })

  const textbox = screen.getByRole('textbox', { name: '协作问题' })
  fireEvent.change(textbox, { target: { value: '你好' } })
  fireEvent.keyDown(textbox, { key: 'Enter' })

  await waitFor(() => expect(onInvokeStream).toHaveBeenCalledTimes(1))
  expect(onInvokeStream).toHaveBeenLastCalledWith(expect.objectContaining({
    intent: 'mixed',
    requestedAction: 'read_only',
    targetRecordId: null,
    skillId: null,
  }), expect.any(Function), expect.any(AbortSignal))
  expect(await screen.findByText('你好，我可以帮你梳理任务、解释技能，或在你打开业务表后分析授权数据。')).toBeVisible()
  expect(screen.queryByText('当前材料不足，未生成可用答案')).not.toBeInTheDocument()
})

test('resets a selected explicit skill across employee or record scope changes', () => {
  const onEmployeeChange = vi.fn()
  const rendered = renderWorkbench({ onEmployeeChange, contacts: [draftCapableContact, { ...draftCapableContact, id: 'employee-2', name: '第二员工' }] })
  fireEvent.click(screen.getByRole('button', { name: '生成跟进草稿' }))
  expect(screen.getByText('草稿模式 · 确认后写入')).toBeVisible()

  fireEvent.change(screen.getByRole('combobox', { name: '选择数字员工' }), { target: { value: 'employee-2' } })
  expect(onEmployeeChange).toHaveBeenCalledWith('employee-2')
  expect(screen.getByText('只读模式 · 不写入')).toBeVisible()

  rendered.rerender(<CollaborationWorkbench
    contacts={[draftCapableContact]}
    currentRecordId={null}
    loading={false}
    failed={false}
    skillCatalog={skillCatalog}
    skillCatalogLoading={false}
    onEmployeeChange={onEmployeeChange}
    onInvokeStream={successfulStream()}
    onOpenDraft={vi.fn()}
    onRetry={vi.fn()}
    onClose={vi.fn()}
  />)
  expect(screen.getByText('只读模式 · 不写入')).toBeVisible()
})

test('enables draft mode only for an explicit catalog draft_update skill and refuses mismatched result skills', async () => {
  const result: Stage08AssistantSafeView = {
    ...completedResult,
    skill: { skillId: 'platform-base', label: '查表问答', manifestVersion: 'stage06-larksuite-skills-v1', selectionMode: 'explicit' },
  }
  const onInvokeStream = successfulStream(result)
  renderWorkbench({ onInvokeStream })
  expect(screen.getByRole('button', { name: '生成跟进草稿' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: '生成跟进草稿' }))
  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '创建草稿' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })
  expect(await screen.findByText('连接中断，可重试')).toBeVisible()

  const noDraftCatalog = { ...skillCatalog, skills: skillCatalog.skills.filter((skill) => skill.skillId !== 'platform-draft-update') }
  const second = renderWorkbench({ catalog: noDraftCatalog, currentRecordId: 'record-1' })
  expect(screen.getAllByText('只读模式 · 不写入')).not.toHaveLength(0)
  second.unmount()
})

test('refuses an explicit result whose manifest version differs from the selected catalog', async () => {
  const onInvokeStream = successfulStream({
    ...completedResult,
    skill: { skillId: 'platform-base', label: '查表问答', manifestVersion: 'stage06-larksuite-skills-v2', selectionMode: 'explicit' },
  })
  renderWorkbench({ onInvokeStream })
  fireEvent.click(screen.getByRole('button', { name: '查表问答' }))
  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '查询当前状态' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })
  expect(await screen.findByText('连接中断，可重试')).toBeVisible()
})

test('Enter sends once while Shift+Enter keeps editing the composer', async () => {
  const onInvokeStream = successfulStream()
  renderWorkbench({ onInvokeStream })
  const textbox = screen.getByRole('textbox', { name: '协作问题' })

  fireEvent.change(textbox, { target: { value: '这个客户下一步怎么推进？' } })
  fireEvent.keyDown(textbox, { key: 'Enter', shiftKey: false })
  await waitFor(() => expect(onInvokeStream).toHaveBeenCalledTimes(1))
  fireEvent.keyDown(textbox, { key: 'Enter', shiftKey: true })
  expect(onInvokeStream).toHaveBeenCalledTimes(1)
})

test('appends real statuses, progressive answer, safe evidence and pending draft in event order', async () => {
  const result: Stage08AssistantSafeView = {
    status: 'draft_pending',
    answer: '已准备跟进事项。',
    citations: [{ ordinal: 1, label: 'group_context' }],
    degradationCodes: [],
    draftId: 'draft-1',
    skill: { skillId: 'platform-draft-update', label: '生成跟进草稿', manifestVersion: 'stage06-larksuite-skills-v1', selectionMode: 'explicit' },
  }
  const onInvokeStream = vi.fn(async (_request, onEvent: (event: Stage08AssistantStreamEvent) => void) => {
    onEvent({ event: 'status', sequence: 1, requestId: 'request-2', phase: 'authorizing' })
    onEvent({ event: 'status', sequence: 2, requestId: 'request-2', phase: 'analysing' })
    onEvent({ event: 'answer_delta', sequence: 3, requestId: 'request-2', text: '已准备' })
    onEvent({ event: 'answer_delta', sequence: 4, requestId: 'request-2', text: '跟进事项。' })
    onEvent({ event: 'result', sequence: 5, requestId: 'request-2', safeView: result })
    onEvent({ event: 'status', sequence: 6, requestId: 'request-2', phase: 'completed' })
    onEvent({ event: 'done', sequence: 7, requestId: 'request-2' })
    return result
  })
  const onOpenDraft = vi.fn()
  renderWorkbench({ onInvokeStream, onOpenDraft })

  fireEvent.click(screen.getByRole('button', { name: '生成跟进草稿' }))
  const textbox = screen.getByRole('textbox', { name: '协作问题' })
  fireEvent.change(textbox, { target: { value: '生成一份跟进草稿' } })
  fireEvent.keyDown(textbox, { key: 'Enter' })

  const turn = await screen.findByRole('article', { name: '协作请求 01' })
  const content = turn.textContent ?? ''
  expect(content.indexOf('正在核验当前身份与操作范围')).toBeLessThan(content.indexOf('正在整理结论与下一步'))
  expect(content.indexOf('正在整理结论与下一步')).toBeLessThan(content.indexOf('已准备跟进事项。'))
  expect(content.indexOf('已准备跟进事项。')).toBeLessThan(content.indexOf('已使用受权群聊上下文作为证据'))
  expect(content.indexOf('已使用受权群聊上下文作为证据')).toBeLessThan(content.indexOf('待确认 · 未写入'))
  expect(content.indexOf('待确认 · 未写入')).toBeLessThan(content.indexOf('已完成'))
  expect(within(turn).getByRole('button', { name: '查看待确认草稿' })).toBeVisible()
  fireEvent.click(within(turn).getByRole('button', { name: '查看待确认草稿' }))
  expect(onOpenDraft).toHaveBeenCalledWith('draft-1')
  expect(within(turn).getAllByText('01')[0]).toBeVisible()
  expect(within(turn).getByText(/\d{2}:\d{2}:\d{2}/).tagName).toBe('TIME')
})

test('stop only ends viewing, stays inline, and never offers automatic draft retry', async () => {
  const alert = vi.spyOn(window, 'alert').mockImplementation(() => undefined)
  const onInvokeStream = vi.fn((_request, _onEvent, signal: AbortSignal) => new Promise<Stage08AssistantSafeView>((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Stopped viewing', 'AbortError')), { once: true })
  }))
  renderWorkbench({ onInvokeStream })
  fireEvent.click(screen.getByRole('button', { name: '生成跟进草稿' }))
  const textbox = screen.getByRole('textbox', { name: '协作问题' })
  fireEvent.change(textbox, { target: { value: '生成一份跟进草稿' } })
  fireEvent.keyDown(textbox, { key: 'Enter' })
  fireEvent.click(await screen.findByRole('button', { name: '停止查看' }))

  expect(await screen.findByText('已停止查看结果')).toBeVisible()
  expect(screen.queryByText(/服务器任务.*取消|服务端任务.*取消|协作已取消/)).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '重新发送' })).not.toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(alert).not.toHaveBeenCalled()
  alert.mockRestore()
})

test('keeps long transcript content before the sticky composer and all skills keyboard reachable', async () => {
  const longResult = {
    ...completedResult,
    answer: '这是经过安全投影的长答案。'.repeat(80),
  }
  renderWorkbench({ onInvokeStream: successfulStream(longResult) })
  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '请给出完整分析。' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })

  expect(await screen.findByText(longResult.answer)).toBeVisible()
  const timeline = screen.getByRole('log', { name: '协作时间线' })
  const composer = screen.getByRole('form', { name: '协作输入' })
  expect(timeline.compareDocumentPosition(composer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  for (const label of ['自动选择', '查表问答', '生成跟进草稿', '群聊上下文']) {
    expect(screen.getByRole('button', { name: label }).tabIndex).toBe(0)
  }
})

test('keeps a safe result finalizing until a done event and completed stream resolution', async () => {
  const onInvokeStream: StreamInvoker = vi.fn(async (_request, onEvent) => {
    onEvent({ event: 'status', sequence: 1, requestId: 'request-1', phase: 'authorizing' })
    onEvent({ event: 'answer_delta', sequence: 2, requestId: 'request-1', text: completedResult.answer ?? '' })
    onEvent({ event: 'result', sequence: 3, requestId: 'request-1', safeView: completedResult })
    return completedResult
  })
  renderWorkbench({ onInvokeStream })

  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '检查完整性' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })

  const turn = await screen.findByRole('article', { name: '协作请求 01' })
  expect(turn).toHaveAttribute('data-turn-state', 'finalizing')
  expect(turn).toHaveTextContent('正在确认传输完成')
})

test('marks a result turn failed when a later stream error is received', async () => {
  const onInvokeStream: StreamInvoker = vi.fn(async (_request, onEvent) => {
    onEvent({ event: 'status', sequence: 1, requestId: 'request-1', phase: 'authorizing' })
    onEvent({ event: 'answer_delta', sequence: 2, requestId: 'request-1', text: completedResult.answer ?? '' })
    onEvent({ event: 'result', sequence: 3, requestId: 'request-1', safeView: completedResult })
    onEvent({ event: 'error', sequence: 4, requestId: 'request-1', code: 'stream_failure', message: 'failed' })
    throw new Error('failed')
  })
  renderWorkbench({ onInvokeStream })

  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '检查失败' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })

  const turn = await screen.findByRole('article', { name: '协作请求 01' })
  expect(turn).toHaveAttribute('data-turn-state', 'failed')
})

test('fails closed for a mismatched server request id or non-contiguous sequence', async () => {
  const onInvokeStream: StreamInvoker = vi.fn(async (_request, onEvent) => {
    onEvent({ event: 'status', sequence: 1, requestId: 'request-1', phase: 'authorizing' })
    onEvent({ event: 'answer_delta', sequence: 3, requestId: 'request-1', text: '跳号' })
    onEvent({ event: 'result', sequence: 4, requestId: 'another-request', safeView: completedResult })
    throw new Error('invalid stream')
  })
  renderWorkbench({ onInvokeStream })

  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '检查序列' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })

  const turn = await screen.findByRole('article', { name: '协作请求 01' })
  expect(turn).toHaveAttribute('data-turn-state', 'failed')
  expect(turn).not.toHaveTextContent(completedResult.answer ?? '')
})

test('never enables a draft unless record write, base scope, and catalog proofs all exist', () => {
  const missingWrite = renderWorkbench({ currentRecordWritable: false })
  expect(screen.getByRole('button', { name: '生成跟进草稿' })).toBeDisabled()
  missingWrite.unmount()

  const wrongBase = renderWorkbench({ currentBaseId: 'base-2' })
  expect(screen.getByRole('button', { name: '生成跟进草稿' })).toBeDisabled()
  wrongBase.unmount()

  renderWorkbench({ catalog: { ...skillCatalog, skills: skillCatalog.skills.map((skill) => skill.skillId === 'platform-draft-update' ? { ...skill, enabled: false, disabledReason: 'write_scope_unavailable' as const } : skill) } })
  expect(screen.getByRole('button', { name: '生成跟进草稿' })).toBeDisabled()
})

test('focuses the composer, traps Tab, and closes through Escape', async () => {
  const onClose = vi.fn()
  render(<CollaborationWorkbench
    contacts={[draftCapableContact]}
    currentRecordId="record-1"
    currentBaseId="base-1"
    currentRecordWritable
    loading={false}
    failed={false}
    skillCatalog={skillCatalog}
    skillCatalogLoading={false}
    onEmployeeChange={vi.fn()}
    onInvokeStream={successfulStream()}
    onOpenDraft={vi.fn()}
    onRetry={vi.fn()}
    onClose={onClose}
  />)

  const textbox = await screen.findByRole('textbox', { name: '协作问题' })
  expect(textbox).toHaveFocus()
  const dialog = screen.getByRole('dialog', { name: 'AI 对话' })
  screen.getByRole('button', { name: '发送问题' }).focus()
  fireEvent.keyDown(dialog, { key: 'Tab' })
  expect(document.activeElement).toBe(screen.getByRole('button', { name: '范围与审计' }))
  fireEvent.keyDown(dialog, { key: 'Escape' })
  expect(onClose).toHaveBeenCalledTimes(1)
})

test('focuses the composer before a deferred animation frame is available', () => {
  vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1))
  vi.stubGlobal('cancelAnimationFrame', vi.fn())
  try {
    renderWorkbench()

    expect(screen.getByRole('textbox', { name: '协作问题' })).toHaveFocus()
  } finally {
    vi.unstubAllGlobals()
  }
})

test('auto-follows only when the transcript was already near its bottom edge', async () => {
  const onInvokeStream: StreamInvoker = vi.fn(async (_request, onEvent) => {
    onEvent({ event: 'status', sequence: 1, requestId: 'request-1', phase: 'authorizing' })
    onEvent({ event: 'answer_delta', sequence: 2, requestId: 'request-1', text: completedResult.answer ?? '' })
    onEvent({ event: 'result', sequence: 3, requestId: 'request-1', safeView: completedResult })
    onEvent({ event: 'done', sequence: 4, requestId: 'request-1' })
    return completedResult
  })
  renderWorkbench({ onInvokeStream })
  const timeline = screen.getByRole('log', { name: '协作时间线' })
  Object.defineProperties(timeline, {
    clientHeight: { configurable: true, value: 100 },
    scrollHeight: { configurable: true, value: 1000 },
    scrollTop: { configurable: true, writable: true, value: 0 },
  })

  fireEvent.scroll(timeline)
  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '远离底部' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })
  await screen.findByRole('article', { name: '协作请求 01' })
  expect(timeline.scrollTop).toBe(0)

  timeline.scrollTop = 900
  fireEvent.scroll(timeline)
  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '靠近底部' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })
  await screen.findByRole('article', { name: '协作请求 02' })
  expect(timeline.scrollTop).toBe(1000)
})

test('keeps the composer in-flight while a safe result is finalizing', async () => {
  let settle: ((result: Stage08AssistantSafeView) => void) | undefined
  const onInvokeStream: StreamInvoker = vi.fn((_request, onEvent) => {
    onEvent({ event: 'status', sequence: 1, requestId: 'request-1', phase: 'authorizing' })
    onEvent({ event: 'answer_delta', sequence: 2, requestId: 'request-1', text: completedResult.answer ?? '' })
    onEvent({ event: 'result', sequence: 3, requestId: 'request-1', safeView: completedResult })
    onEvent({ event: 'done', sequence: 4, requestId: 'request-1' })
    return new Promise<Stage08AssistantSafeView>((resolve) => { settle = resolve })
  })
  renderWorkbench({ onInvokeStream })
  const textbox = screen.getByRole('textbox', { name: '协作问题' })

  fireEvent.change(textbox, { target: { value: '第一项' } })
  fireEvent.keyDown(textbox, { key: 'Enter' })
  expect(await screen.findByRole('article', { name: '协作请求 01' })).toHaveAttribute('data-turn-state', 'finalizing')
  expect(screen.getByRole('button', { name: '发送问题' })).toBeDisabled()

  fireEvent.change(textbox, { target: { value: '第二项' } })
  fireEvent.keyDown(textbox, { key: 'Enter' })
  expect(onInvokeStream).toHaveBeenCalledTimes(1)
  settle?.(completedResult)
})

test('freezes the turn after the first done and ignores duplicate terminal or later events', async () => {
  const onInvokeStream: StreamInvoker = vi.fn(async (_request, onEvent) => {
    onEvent({ event: 'status', sequence: 1, requestId: 'request-1', phase: 'authorizing' })
    onEvent({ event: 'answer_delta', sequence: 2, requestId: 'request-1', text: completedResult.answer ?? '' })
    onEvent({ event: 'result', sequence: 3, requestId: 'request-1', safeView: completedResult })
    onEvent({ event: 'done', sequence: 4, requestId: 'request-1' })
    onEvent({ event: 'done', sequence: 5, requestId: 'request-1' })
    onEvent({ event: 'status', sequence: 6, requestId: 'request-1', phase: 'authorizing' })
    return completedResult
  })
  renderWorkbench({ onInvokeStream })

  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '冻结终态' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })

  const turn = await screen.findByRole('article', { name: '协作请求 01' })
  await waitFor(() => expect(turn).toHaveAttribute('data-turn-state', 'completed'))
  expect(turn).not.toHaveTextContent('连接中断，可重试')
})

test('allows stopping local viewing while a finalizing stream promise remains in-flight', async () => {
  const onInvokeStream: StreamInvoker = vi.fn((_request, onEvent) => {
    onEvent({ event: 'status', sequence: 1, requestId: 'request-1', phase: 'authorizing' })
    onEvent({ event: 'answer_delta', sequence: 2, requestId: 'request-1', text: completedResult.answer ?? '' })
    onEvent({ event: 'result', sequence: 3, requestId: 'request-1', safeView: completedResult })
    onEvent({ event: 'done', sequence: 4, requestId: 'request-1' })
    return new Promise<Stage08AssistantSafeView>(() => undefined)
  })
  renderWorkbench({ onInvokeStream })

  fireEvent.change(screen.getByRole('textbox', { name: '协作问题' }), { target: { value: '停止 finalizing' } })
  fireEvent.keyDown(screen.getByRole('textbox', { name: '协作问题' }), { key: 'Enter' })
  expect(await screen.findByRole('button', { name: '停止查看' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: '停止查看' }))

  expect((await screen.findByRole('article', { name: '协作请求 01' }))).toHaveAttribute('data-turn-state', 'stopped')
})
