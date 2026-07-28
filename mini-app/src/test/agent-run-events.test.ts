import { expect, test } from 'vitest'

import {
  initialAgentRunState,
  parseAgentRunEventStream,
  reduceAgentRunEvent,
} from '../app/agent-run-events'


const runId = '11111111-1111-4111-8111-111111111111'
const eventId = (sequence: number) => `22222222-2222-4222-8222-${String(sequence).padStart(12, '0')}`
const safeView = {
  status: 'completed',
  answer: '建议继续跟进。',
  citations: [{ ordinal: 1, label: 'business_data' }],
  degradation_codes: [],
  draft_id: null,
  skill: {
    skill_id: 'platform-tabular-analysis',
    label: '汇总分析',
    manifest_version: 'stage06-larksuite-skills-v1',
    selection_mode: 'explicit',
  },
}

function stream(events: Record<string, unknown>[]) {
  const body = events.map((event) => [
    `id: ${event.sequence}`,
    `event: ${event.event}`,
    `data: ${JSON.stringify(event)}`,
    '',
    '',
  ].join('\n')).join('')
  return new Response(body).body!
}

test('parses ordered safe events after a reconnect cursor', async () => {
  const events = await parseAgentRunEventStream(stream([
    {
      run_id: runId,
      event_id: eventId(3),
      sequence: 3,
      event: 'status',
      phase: 'running',
      message: '正在分析',
    },
    {
      run_id: runId,
      event_id: eventId(4),
      sequence: 4,
      event: 'result',
      artifact_ref: '33333333-3333-4333-8333-333333333333',
      safe_view: safeView,
    },
    {
      run_id: runId,
      event_id: eventId(5),
      sequence: 5,
      event: 'done',
      status: 'completed',
    },
  ]), { runId, afterSequence: 2 })

  expect(events.map((event) => event.event)).toEqual(['status', 'result', 'done'])
  expect(events[1]).toMatchObject({ event: 'result', safeView: { answer: '建议继续跟进。' } })
})

test('parses and retains a validated artifact-ready event', async () => {
  const artifactRef = '33333333-3333-4333-8333-333333333333'
  const events = await parseAgentRunEventStream(stream([{
    run_id: runId,
    event_id: eventId(1),
    sequence: 1,
    event: 'artifact_ready',
    artifact_ref: artifactRef,
    label: 'Safe analysis result',
  }]), { runId, afterSequence: 0 })

  const state = reduceAgentRunEvent(initialAgentRunState(runId), events[0])
  expect(events[0]).toMatchObject({ event: 'artifact_ready', artifactRef })
  expect(state.artifacts).toEqual([{ artifactRef, label: 'Safe analysis result' }])
})

test('rejects duplicate, gap, mismatched SSE id, and private extra fields', async () => {
  const base = {
    run_id: runId,
    event_id: eventId(1),
    sequence: 1,
    event: 'status',
    phase: 'accepted',
    message: '已受理',
  }
  await expect(parseAgentRunEventStream(stream([base, base]), { runId, afterSequence: 0 })).rejects.toThrow('Invalid agent run stream')
  await expect(parseAgentRunEventStream(stream([{ ...base, sequence: 2, event_id: eventId(2) }]), { runId, afterSequence: 0 })).rejects.toThrow('Invalid agent run stream')
  await expect(parseAgentRunEventStream(stream([{ ...base, prompt: 'private' }]), { runId, afterSequence: 0 })).rejects.toThrow('Invalid agent run stream')
})

test('reducer ignores already applied events and rejects done without a result', () => {
  const status = {
    runId,
    eventId: eventId(1),
    sequence: 1,
    event: 'status' as const,
    phase: 'accepted' as const,
    message: '已受理',
  }
  const once = reduceAgentRunEvent(initialAgentRunState(runId), status)
  expect(reduceAgentRunEvent(once, status)).toBe(once)
  expect(() => reduceAgentRunEvent(once, {
    runId,
    eventId: eventId(2),
    sequence: 2,
    event: 'done',
    status: 'completed',
  })).toThrow('Invalid agent run transition')
})

test('maps a stable timeout error to the timed-out terminal state', async () => {
  const [event] = await parseAgentRunEventStream(stream([{
    run_id: runId,
    event_id: eventId(1),
    sequence: 1,
    event: 'error',
    code: 'run_timed_out',
    message: 'Run timed out',
  }]), { runId, afterSequence: 0 })

  const state = reduceAgentRunEvent(initialAgentRunState(runId), event)
  expect(state.terminalStatus).toBe('timed_out')
  expect(state.errorCode).toBe('run_timed_out')
})
