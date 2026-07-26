import type {
  Stage08AssistantCitation,
  Stage08AssistantSafeView,
  Stage08AssistantStatus,
  Stage08AssistantStreamEvent,
  Stage08AssistantStreamPhase,
  Stage08CitationLabel,
  Stage08DegradationCode,
  Stage08SkillSummary,
} from './stage08-collaboration-types'

const MAX_EVENT_BYTES = 64 * 1024
const MAX_RESPONSE_BYTES = 1024 * 1024
const knownEvents = new Set<Stage08AssistantStreamEvent['event']>([
  'status',
  'answer_delta',
  'result',
  'error',
  'done',
])
const phases = new Set<Stage08AssistantStreamPhase>([
  'authorizing',
  'planning_context',
  'analysing',
  'creating_draft',
  'completed',
])
const statuses = new Set<Stage08AssistantStatus>([
  'completed',
  'draft_pending',
  'degraded',
  'denied',
  'failed',
  'cancelled',
  'timed_out',
])
const citationLabels = new Set<Stage08CitationLabel>([
  'business_data',
  'confirmed_memory',
  'group_context',
  'retrieved_material',
  'analysis_from_current_material',
  'general_advice',
])
const degradationCodes = new Set<Stage08DegradationCode>([
  'context_unavailable',
  'retrieval_unavailable',
  'compression_unavailable',
  'analysis_unavailable',
  'no_evidence',
  'policy_denied',
  'cancelled',
  'timed_out',
  'internal_failure',
])
const privateIdentifierPattern = /(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])/i

function invalidStream(): Error {
  return new Error('Invalid assistant stream')
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

function sequenceValue(value: unknown): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 1) throw invalidStream()
  return value
}

function safeCitation(value: unknown): Stage08AssistantCitation {
  const item = record(value)
  if (!hasExactKeys(item, ['ordinal', 'label'])) throw invalidStream()
  if (typeof item.ordinal !== 'number' || !Number.isInteger(item.ordinal) || item.ordinal < 1 || item.ordinal > 12) throw invalidStream()
  if (typeof item.label !== 'string' || !citationLabels.has(item.label as Stage08CitationLabel)) throw invalidStream()
  return { ordinal: item.ordinal, label: item.label as Stage08CitationLabel }
}

function safeSkillSummary(value: unknown): Stage08SkillSummary | null {
  if (value === null || value === undefined) return null
  const item = record(value)
  if (!hasExactKeys(item, ['skill_id', 'label', 'manifest_version', 'selection_mode']) || typeof item.skill_id !== 'string' || typeof item.label !== 'string' || typeof item.manifest_version !== 'string' || (item.selection_mode !== 'explicit' && item.selection_mode !== 'auto')) throw invalidStream()
  return { skillId: boundedString(item.skill_id, 120), label: boundedString(item.label, 120), manifestVersion: boundedString(item.manifest_version, 120), selectionMode: item.selection_mode }
}

function safeView(value: unknown): Stage08AssistantSafeView {
  const item = record(value)
  if (!hasExactKeys(item, ['status', 'answer', 'citations', 'degradation_codes', 'draft_id']) && !hasExactKeys(item, ['status', 'answer', 'citations', 'degradation_codes', 'draft_id', 'skill'])) throw invalidStream()
  if (typeof item.status !== 'string' || !statuses.has(item.status as Stage08AssistantStatus)) throw invalidStream()
  if (item.answer !== null && (typeof item.answer !== 'string' || item.answer.length > 2000 || privateIdentifierPattern.test(item.answer))) throw invalidStream()
  if (!Array.isArray(item.citations) || !Array.isArray(item.degradation_codes)) throw invalidStream()
  const citations = item.citations.map(safeCitation)
  const safeDegradationCodes = item.degradation_codes.map((code) => {
    if (typeof code !== 'string' || !degradationCodes.has(code as Stage08DegradationCode)) throw invalidStream()
    return code as Stage08DegradationCode
  })
  if (new Set(citations.map(({ ordinal }) => ordinal)).size !== citations.length || new Set(safeDegradationCodes).size !== safeDegradationCodes.length) throw invalidStream()
  if (item.draft_id !== null && (typeof item.draft_id !== 'string' || item.draft_id.length < 1 || item.draft_id.length > 120)) throw invalidStream()
  if ((item.status === 'draft_pending') !== Boolean(item.draft_id)) throw invalidStream()
  return {
    status: item.status as Stage08AssistantStatus,
    answer: item.answer as string | null,
    citations,
    degradationCodes: safeDegradationCodes,
    draftId: item.draft_id as string | null,
    ...(item.skill === undefined ? {} : { skill: safeSkillSummary(item.skill) }),
  }
}

function eventFields(block: string): { eventName: string; data: string } {
  let eventName = ''
  const data: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(':')) continue
    const separator = line.indexOf(':')
    const field = separator < 0 ? line : line.slice(0, separator)
    let value = separator < 0 ? '' : line.slice(separator + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') eventName = value
    if (field === 'data') data.push(value)
  }
  return { eventName, data: data.join('\n') }
}

function parseEventBlock(eventField: string, data: string): Stage08AssistantStreamEvent | null {
  let decoded: unknown
  try {
    decoded = JSON.parse(data)
  } catch {
    throw invalidStream()
  }
  const item = record(decoded)
  if (typeof item.event !== 'string' || (eventField && eventField !== item.event)) throw invalidStream()
  if (!knownEvents.has(item.event as Stage08AssistantStreamEvent['event'])) return null
  const eventName = item.event as Stage08AssistantStreamEvent['event']
  const sequence = sequenceValue(item.sequence)
  const requestId = boundedString(item.request_id, 64)
  if (eventName === 'status') {
    if (!hasExactKeys(item, ['event', 'sequence', 'request_id', 'phase']) || typeof item.phase !== 'string' || !phases.has(item.phase as Stage08AssistantStreamPhase)) throw invalidStream()
    return { event: eventName, sequence, requestId, phase: item.phase as Stage08AssistantStreamPhase }
  }
  if (eventName === 'answer_delta') {
    if (!hasExactKeys(item, ['event', 'sequence', 'request_id', 'text'])) throw invalidStream()
    return { event: eventName, sequence, requestId, text: boundedString(item.text, 512) }
  }
  if (eventName === 'result') {
    if (!hasExactKeys(item, ['event', 'sequence', 'request_id', 'safe_view'])) throw invalidStream()
    return { event: eventName, sequence, requestId, safeView: safeView(item.safe_view) }
  }
  if (eventName === 'error') {
    if (!hasExactKeys(item, ['event', 'sequence', 'request_id', 'code', 'message'])) throw invalidStream()
    return {
      event: eventName,
      sequence,
      requestId,
      code: boundedString(item.code, 120),
      message: boundedString(item.message, 200),
    }
  }
  if (!hasExactKeys(item, ['event', 'sequence', 'request_id'])) throw invalidStream()
  return { event: eventName, sequence, requestId }
}

export async function parseStage08AssistantStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: Stage08AssistantStreamEvent) => void,
): Promise<Stage08AssistantSafeView> {
  const decoder = new TextDecoder('utf-8', { fatal: true })
  const encoder = new TextEncoder()
  const reader = stream.getReader()
  let buffer = ''
  let responseBytes = 0
  let expectedSequence = 1
  let requestId: string | null = null
  let result: Stage08AssistantSafeView | null = null
  let deltaText = ''
  let terminal: Extract<Stage08AssistantStreamEvent, { event: 'done' | 'error' }> | null = null
  let reachedEof = false

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (value?.byteLength) {
        if (terminal) throw invalidStream()
        responseBytes += value.byteLength
        if (responseBytes > MAX_RESPONSE_BYTES) throw invalidStream()
        try {
          buffer += decoder.decode(value, { stream: true })
        } catch {
          throw invalidStream()
        }
      }
      if (done) {
        reachedEof = true
        try {
          buffer += decoder.decode()
        } catch {
          throw invalidStream()
        }
      }

      let delimiter = buffer.match(/\r?\n\r?\n/)
      while (delimiter?.index !== undefined) {
        const block = buffer.slice(0, delimiter.index)
        buffer = buffer.slice(delimiter.index + delimiter[0].length)
        if (encoder.encode(block).byteLength > MAX_EVENT_BYTES) throw invalidStream()
        const { eventName, data } = eventFields(block)
        const event = parseEventBlock(eventName, data)
        if (event) {
          if (event.sequence !== expectedSequence || (requestId !== null && event.requestId !== requestId)) throw invalidStream()
          expectedSequence += 1
          requestId ??= event.requestId
          if (event.event === 'answer_delta') {
            if (result || terminal) throw invalidStream()
            const nextDeltaText = deltaText + event.text
            if (nextDeltaText.length > 2000 || privateIdentifierPattern.test(nextDeltaText)) throw invalidStream()
            deltaText = nextDeltaText
            onEvent(event)
          } else if (event.event === 'result') {
            if (result || terminal || (event.safeView.answer ?? '') !== deltaText) throw invalidStream()
            result = event.safeView
            onEvent(event)
          } else if (event.event === 'done') {
            if (!result || terminal) throw invalidStream()
            terminal = event
          } else if (event.event === 'error') {
            if (result || terminal) throw invalidStream()
            terminal = event
          } else {
            if (terminal) throw invalidStream()
            onEvent(event)
          }
          if (terminal) {
            if (buffer.length > 0) throw invalidStream()
            delimiter = null
            break
          }
        }
        delimiter = buffer.match(/\r?\n\r?\n/)
      }
      if (encoder.encode(buffer).byteLength > MAX_EVENT_BYTES) throw invalidStream()
      if (done) break
    }
    if (buffer.length > 0 || !terminal) throw invalidStream()
    onEvent(terminal)
    if (terminal.event === 'error') throw new Error('Assistant stream failed')
    if (!result) throw invalidStream()
    return result
  } finally {
    if (!reachedEof) {
      try {
        await reader.cancel()
      } catch {
        // The stream error is intentionally normalized by the parser/API boundary.
      }
    }
    reader.releaseLock()
  }
}
