import type {
  Stage08AssistantSafeView,
  Stage08AssistantStatus,
  Stage08CitationLabel,
  Stage08DegradationCode,
  Stage12AnswerSource,
  Stage12ProviderResultStatus,
} from './stage08-collaboration-types'


export type AgentRunPhase = 'accepted' | 'queued' | 'running' | 'waiting_approval'
export type AgentObjectiveEvent = { event: 'objective'; runId: string; eventId: string; sequence: number; eventType: string; objectiveId: string; objectiveKey: string; kind: string; status: 'queued' | 'running' | 'completed' | 'degraded' | 'denied'; message: string }
export type AgentActionEvent = { event: 'action'; runId: string; eventId: string; sequence: number; eventType: string; slotId: string; objectiveId: string; actionKind: 'record.create' | 'record.update' | 'task.create' | 'reminder.request'; status: 'proposed' | 'pending_confirmation' | 'confirmed' | 'executed' | 'conflicted' | 'denied'; message: string }
export type AgentRunEvent =
  | { event: 'status'; runId: string; eventId: string; sequence: number; phase: AgentRunPhase; message: string }
  | { event: 'artifact_ready'; runId: string; eventId: string; sequence: number; artifactRef: string; label: string }
  | { event: 'result'; runId: string; eventId: string; sequence: number; artifactRef: string; safeView: Stage08AssistantSafeView }
  | { event: 'error'; runId: string; eventId: string; sequence: number; code: string; message: string }
  | { event: 'done'; runId: string; eventId: string; sequence: number; status: 'completed' | 'degraded' | 'failed' | 'cancelled' | 'timed_out' }
  | AgentObjectiveEvent
  | AgentActionEvent

export type AgentRunState = {
  runId: string
  lastSequence: number
  appliedEventIds: readonly string[]
  artifacts: readonly { artifactRef: string; label: string }[]
  phase: AgentRunPhase | null
  result: Stage08AssistantSafeView | null
  terminalStatus: 'completed' | 'degraded' | 'failed' | 'cancelled' | 'timed_out' | null
  errorCode: string | null
  objectives: readonly AgentObjectiveEvent[]
  actions: readonly AgentActionEvent[]
}

const MAX_EVENT_BYTES = 64 * 1024
const MAX_RESPONSE_BYTES = 1024 * 1024
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const privateIdentifierPattern = /(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])/i
const phases = new Set<AgentRunPhase>(['accepted', 'queued', 'running', 'waiting_approval'])
const terminalStatuses = new Set(['completed', 'degraded', 'failed', 'cancelled', 'timed_out'])
const assistantStatuses = new Set<Stage08AssistantStatus>(['completed', 'draft_pending', 'degraded', 'denied', 'failed', 'cancelled', 'timed_out'])
const citationLabels = new Set<Stage08CitationLabel>(['business_data', 'confirmed_memory', 'group_context', 'retrieved_material', 'analysis_from_current_material', 'general_advice'])
const degradationCodes = new Set<Stage08DegradationCode>(['context_unavailable', 'retrieval_unavailable', 'compression_unavailable', 'analysis_unavailable', 'no_evidence', 'policy_denied', 'cancelled', 'timed_out', 'internal_failure'])
const objectiveStatuses = new Set(['queued', 'running', 'completed', 'degraded', 'denied'])
const actionStatuses = new Set(['proposed', 'pending_confirmation', 'confirmed', 'executed', 'conflicted', 'denied'])
const actionKinds = new Set(['record.create', 'record.update', 'task.create', 'reminder.request'])
const answerSources = new Set<Stage12AnswerSource>(['real_provider', 'deterministic_fallback'])
const providerResultStatuses = new Set<Stage12ProviderResultStatus>(['completed', 'transport_failed', 'schema_failed', 'grounding_failed', 'language_failed'])

function invalidStream(): Error {
  return new Error('Invalid agent run stream')
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw invalidStream()
  return value as Record<string, unknown>
}

function hasExactKeys(value: Record<string, unknown>, keys: string[]): boolean {
  const actual = Object.keys(value).sort()
  const expected = [...keys].sort()
  return actual.length === expected.length && actual.every((key, index) => key === expected[index])
}

function boundedString(value: unknown, maxLength: number): string {
  if (typeof value !== 'string' || value.length < 1 || value.length > maxLength) throw invalidStream()
  return value
}

function uuid(value: unknown): string {
  const parsed = boundedString(value, 36)
  if (!uuidPattern.test(parsed)) throw invalidStream()
  return parsed
}

function safeView(value: unknown): Stage08AssistantSafeView {
  const item = record(value)
  const legacyKeys = ['status', 'answer', 'citations', 'degradation_codes', 'draft_id', 'skill']
  const stage12Keys = [...legacyKeys, 'answer_source', 'provider_result_status']
  if (!hasExactKeys(item, legacyKeys) && !hasExactKeys(item, stage12Keys)) throw invalidStream()
  if (typeof item.status !== 'string' || !assistantStatuses.has(item.status as Stage08AssistantStatus)) throw invalidStream()
  if (item.answer !== null && (typeof item.answer !== 'string' || item.answer.length > 2000 || privateIdentifierPattern.test(item.answer))) throw invalidStream()
  if (!Array.isArray(item.citations) || !Array.isArray(item.degradation_codes)) throw invalidStream()
  const citations = item.citations.map((value) => {
    const citation = record(value)
    if (!hasExactKeys(citation, ['ordinal', 'label']) || typeof citation.ordinal !== 'number' || !Number.isInteger(citation.ordinal) || citation.ordinal < 1 || citation.ordinal > 12 || typeof citation.label !== 'string' || !citationLabels.has(citation.label as Stage08CitationLabel)) throw invalidStream()
    return { ordinal: citation.ordinal, label: citation.label as Stage08CitationLabel }
  })
  const safeDegradationCodes = item.degradation_codes.map((code) => {
    if (typeof code !== 'string' || !degradationCodes.has(code as Stage08DegradationCode)) throw invalidStream()
    return code as Stage08DegradationCode
  })
  if (new Set(citations.map((citation) => citation.ordinal)).size !== citations.length || new Set(safeDegradationCodes).size !== safeDegradationCodes.length) throw invalidStream()
  if (item.draft_id !== null && typeof item.draft_id !== 'string') throw invalidStream()
  if ((item.status === 'draft_pending') !== Boolean(item.draft_id)) throw invalidStream()
  let answerSource: Stage12AnswerSource | undefined
  let providerResultStatus: Stage12ProviderResultStatus | undefined
  if ('answer_source' in item || 'provider_result_status' in item) {
    if (typeof item.answer_source !== 'string' || !answerSources.has(item.answer_source as Stage12AnswerSource)) throw invalidStream()
    if (typeof item.provider_result_status !== 'string' || !providerResultStatuses.has(item.provider_result_status as Stage12ProviderResultStatus)) throw invalidStream()
    answerSource = item.answer_source as Stage12AnswerSource
    providerResultStatus = item.provider_result_status as Stage12ProviderResultStatus
    if ((answerSource === 'real_provider') !== (providerResultStatus === 'completed')) throw invalidStream()
  }
  let skill: Stage08AssistantSafeView['skill'] = null
  if (item.skill !== null) {
    const value = record(item.skill)
    if (!hasExactKeys(value, ['skill_id', 'label', 'manifest_version', 'selection_mode']) || (value.selection_mode !== 'explicit' && value.selection_mode !== 'auto')) throw invalidStream()
    skill = {
      skillId: boundedString(value.skill_id, 120),
      label: boundedString(value.label, 120),
      manifestVersion: boundedString(value.manifest_version, 120),
      selectionMode: value.selection_mode,
    }
  }
  return {
    status: item.status as Stage08AssistantStatus,
    answer: item.answer as string | null,
    citations,
    degradationCodes: safeDegradationCodes,
    draftId: item.draft_id as string | null,
    skill,
    answerSource,
    providerResultStatus,
  }
}

function parseBlock(block: string, expectedRunId: string): AgentRunEvent {
  let sseId = ''
  let eventField = ''
  const data: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(':')) continue
    const separator = line.indexOf(':')
    const field = separator < 0 ? line : line.slice(0, separator)
    const rawValue = separator < 0 ? '' : line.slice(separator + 1)
    const value = rawValue.startsWith(' ') ? rawValue.slice(1) : rawValue
    if (field === 'id') sseId = value
    else if (field === 'event') eventField = value
    else if (field === 'data') data.push(value)
  }
  let decoded: unknown
  try {
    decoded = JSON.parse(data.join('\n'))
  } catch {
    throw invalidStream()
  }
  const item = record(decoded)
  const runId = uuid(item.run_id)
  const eventId = uuid(item.event_id)
  if (runId !== expectedRunId || typeof item.sequence !== 'number' || !Number.isInteger(item.sequence) || item.sequence < 1 || sseId !== String(item.sequence) || item.event !== eventField) throw invalidStream()
  const common = { runId, eventId, sequence: item.sequence }
  if (item.event === 'status') {
    if (!hasExactKeys(item, ['run_id', 'event_id', 'sequence', 'event', 'phase', 'message']) || typeof item.phase !== 'string' || !phases.has(item.phase as AgentRunPhase)) throw invalidStream()
    return { ...common, event: 'status', phase: item.phase as AgentRunPhase, message: boundedString(item.message, 240) }
  }
  if (item.event === 'result') {
    if (!hasExactKeys(item, ['run_id', 'event_id', 'sequence', 'event', 'artifact_ref', 'safe_view'])) throw invalidStream()
    return { ...common, event: 'result', artifactRef: uuid(item.artifact_ref), safeView: safeView(item.safe_view) }
  }
  if (item.event === 'artifact_ready') {
    if (!hasExactKeys(item, ['run_id', 'event_id', 'sequence', 'event', 'artifact_ref', 'label'])) throw invalidStream()
    return { ...common, event: 'artifact_ready', artifactRef: uuid(item.artifact_ref), label: boundedString(item.label, 120) }
  }
  if (item.event === 'error') {
    if (!hasExactKeys(item, ['run_id', 'event_id', 'sequence', 'event', 'code', 'message'])) throw invalidStream()
    return { ...common, event: 'error', code: boundedString(item.code, 120), message: boundedString(item.message, 200) }
  }
  if (item.event === 'done') {
    if (!hasExactKeys(item, ['run_id', 'event_id', 'sequence', 'event', 'status']) || typeof item.status !== 'string' || !terminalStatuses.has(item.status)) throw invalidStream()
    return { ...common, event: 'done', status: item.status as 'completed' | 'degraded' | 'failed' | 'cancelled' | 'timed_out' }
  }
  if (item.event === 'objective') {
    if (!hasExactKeys(item, ['run_id', 'event_id', 'sequence', 'event', 'event_type', 'objective_id', 'objective_key', 'kind', 'status', 'message']) || typeof item.status !== 'string' || !objectiveStatuses.has(item.status)) throw invalidStream()
    const status = item.status as AgentObjectiveEvent['status']
    if (item.event_type !== `objective.${status === 'running' ? 'started' : status}`) throw invalidStream()
    return { ...common, event: 'objective', eventType: boundedString(item.event_type, 80), objectiveId: uuid(item.objective_id), objectiveKey: boundedString(item.objective_key, 80), kind: boundedString(item.kind, 40), status, message: boundedString(item.message, 240) }
  }
  if (item.event === 'action') {
    if (!hasExactKeys(item, ['run_id', 'event_id', 'sequence', 'event', 'event_type', 'slot_id', 'objective_id', 'action_kind', 'status', 'message']) || typeof item.status !== 'string' || !actionStatuses.has(item.status) || typeof item.action_kind !== 'string' || !actionKinds.has(item.action_kind)) throw invalidStream()
    const status = item.status as AgentActionEvent['status']
    if (item.event_type !== `action.${status}`) throw invalidStream()
    return { ...common, event: 'action', eventType: boundedString(item.event_type, 80), slotId: uuid(item.slot_id), objectiveId: uuid(item.objective_id), actionKind: item.action_kind as AgentActionEvent['actionKind'], status, message: boundedString(item.message, 240) }
  }
  throw invalidStream()
}

export async function parseAgentRunEventStream(
  stream: ReadableStream<Uint8Array>,
  options: { runId: string; afterSequence: number; onEvent?: (event: AgentRunEvent) => void },
): Promise<AgentRunEvent[]> {
  if (!uuidPattern.test(options.runId) || !Number.isInteger(options.afterSequence) || options.afterSequence < 0) throw invalidStream()
  const reader = stream.getReader()
  const decoder = new TextDecoder('utf-8', { fatal: true })
  const encoder = new TextEncoder()
  let buffer = ''
  let totalBytes = 0
  let expectedSequence = options.afterSequence + 1
  const events: AgentRunEvent[] = []
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (value) {
        totalBytes += value.byteLength
        if (totalBytes > MAX_RESPONSE_BYTES) throw invalidStream()
        try { buffer += decoder.decode(value, { stream: true }) } catch { throw invalidStream() }
      }
      if (done) {
        try { buffer += decoder.decode() } catch { throw invalidStream() }
      }
      let delimiter = buffer.match(/\r?\n\r?\n/)
      while (delimiter?.index !== undefined) {
        const block = buffer.slice(0, delimiter.index)
        buffer = buffer.slice(delimiter.index + delimiter[0].length)
        if (encoder.encode(block).byteLength > MAX_EVENT_BYTES) throw invalidStream()
        const event = parseBlock(block, options.runId)
        if (event.sequence !== expectedSequence) throw invalidStream()
        expectedSequence += 1
        events.push(event)
        options.onEvent?.(event)
        delimiter = buffer.match(/\r?\n\r?\n/)
      }
      if (encoder.encode(buffer).byteLength > MAX_EVENT_BYTES) throw invalidStream()
      if (done) break
    }
    if (buffer.length > 0) throw invalidStream()
    return events
  } finally {
    reader.releaseLock()
  }
}

export function initialAgentRunState(runId: string): AgentRunState {
  if (!uuidPattern.test(runId)) throw new Error('Invalid agent run transition')
  return { runId, lastSequence: 0, appliedEventIds: [], artifacts: [], phase: null, result: null, terminalStatus: null, errorCode: null, objectives: [], actions: [] }
}

export function reduceAgentRunEvent(state: AgentRunState, event: AgentRunEvent): AgentRunState {
  if (event.runId !== state.runId) throw new Error('Invalid agent run transition')
  if (event.sequence <= state.lastSequence) {
    if (state.appliedEventIds.includes(event.eventId)) return state
    throw new Error('Invalid agent run transition')
  }
  if (event.sequence !== state.lastSequence + 1 || state.terminalStatus !== null) throw new Error('Invalid agent run transition')
  const base = { ...state, lastSequence: event.sequence, appliedEventIds: [...state.appliedEventIds, event.eventId] }
  if (event.event === 'status') return { ...base, phase: event.phase }
  if (event.event === 'artifact_ready') {
    if (state.artifacts.some((artifact) => artifact.artifactRef === event.artifactRef)) return base
    return { ...base, artifacts: [...state.artifacts, { artifactRef: event.artifactRef, label: event.label }] }
  }
  if (event.event === 'result') return { ...base, result: event.safeView }
  if (event.event === 'error') return { ...base, errorCode: event.code, terminalStatus: event.code === 'run_timed_out' ? 'timed_out' : 'failed' }
  if (event.event === 'objective') return { ...base, objectives: [...state.objectives.filter((item) => item.objectiveId !== event.objectiveId), event] }
  if (event.event === 'action') return { ...base, actions: [...state.actions.filter((item) => item.slotId !== event.slotId), event] }
  if (event.status === 'completed' && state.result === null) throw new Error('Invalid agent run transition')
  return { ...base, terminalStatus: event.status }
}
