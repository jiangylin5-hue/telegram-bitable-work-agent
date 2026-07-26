import { expect, test } from 'vitest'

import { parseStage08AssistantStream } from '../app/stage08-collaboration-stream'
import type { Stage08AssistantStreamEvent } from '../app/stage08-collaboration-types'

const safeView = {
  status: 'completed',
  answer: '最终安全结果',
  citations: [{ ordinal: 1, label: 'general_advice' }],
  degradation_codes: [],
  draft_id: null,
}

const noAnswerSafeView = { ...safeView, answer: null }

function sse(event: string, data: unknown, newline = '\n', includeEventField = false): string {
  const eventField = includeEventField ? `event: ${event}${newline}` : ''
  return `${eventField}data: ${JSON.stringify(data)}${newline}${newline}`
}

function byteStream(source: string, splitAt: number[]): ReadableStream<Uint8Array> {
  const encoded = new TextEncoder().encode(source)
  const boundaries = [0, ...splitAt, encoded.length]
  return new ReadableStream({
    start(controller) {
      for (let index = 0; index < boundaries.length - 1; index += 1) {
        controller.enqueue(encoded.slice(boundaries[index], boundaries[index + 1]))
      }
      controller.close()
    },
  })
}

function completeStream(newline = '\n'): string {
  return [
    sse('status', { event: 'status', sequence: 1, request_id: 'req-1', phase: 'authorizing' }, newline),
    sse('answer_delta', { event: 'answer_delta', sequence: 2, request_id: 'req-1', text: '最终安全结果' }, newline),
    sse('result', { event: 'result', sequence: 3, request_id: 'req-1', safe_view: safeView }, newline),
    sse('done', { event: 'done', sequence: 4, request_id: 'req-1' }, newline),
  ].join('')
}

test.each(['\n', '\r\n'])('parses %j-delimited SSE split inside UTF-8 and field boundaries', async (newline) => {
  const source = completeStream(newline)
  const encoded = new TextEncoder().encode(source)
  const utf8Split = encoded.findIndex((value) => value > 0x7f) + 1
  const fieldSplit = new TextEncoder().encode('da').length
  const events: Stage08AssistantStreamEvent[] = []

  const result = await parseStage08AssistantStream(
    byteStream(source, [fieldSplit, utf8Split]),
    (event) => events.push(event),
  )

  expect(events.map((event) => event.event)).toEqual(['status', 'answer_delta', 'result', 'done'])
  expect(events[1]).toEqual({
    event: 'answer_delta',
    sequence: 2,
    requestId: 'req-1',
    text: '最终安全结果',
  })
  expect(result).toEqual({
    status: 'completed',
    answer: '最终安全结果',
    citations: [{ ordinal: 1, label: 'general_advice' }],
    degradationCodes: [],
    draftId: null,
  })
})

test('joins multi-line data fields with a newline before decoding JSON', async () => {
  const source = [
    'event: status\n',
    'data: {"event":"status",\n',
    'data: "sequence":1,"request_id":"req-1","phase":"authorizing"}\n\n',
    sse('result', { event: 'result', sequence: 2, request_id: 'req-1', safe_view: noAnswerSafeView }),
    sse('done', { event: 'done', sequence: 3, request_id: 'req-1' }),
  ].join('')
  const events: Stage08AssistantStreamEvent[] = []

  await parseStage08AssistantStream(byteStream(source, []), (event) => events.push(event))

  expect(events[0]).toEqual({
    event: 'status',
    sequence: 1,
    requestId: 'req-1',
    phase: 'authorizing',
  })
})

test('uses the payload event discriminant and ignores unknown events without rendering them', async () => {
  const source = [
    sse('future_internal_event', { event: 'future_internal_event', raw_internal_body: 'do not render' }),
    sse('result', { event: 'result', sequence: 1, request_id: 'req-1', safe_view: noAnswerSafeView }),
    sse('done', { event: 'done', sequence: 2, request_id: 'req-1' }),
  ].join('')
  const events: Stage08AssistantStreamEvent[] = []

  await expect(parseStage08AssistantStream(
    byteStream(source, []),
    (event) => events.push(event),
  )).resolves.toMatchObject({ answer: null })
  expect(events.map((event) => event.event)).toEqual(['result', 'done'])
})

test.each([
  ['duplicate', [1, 1]],
  ['gapped', [1, 3]],
  ['decreasing', [2, 1]],
])('fails closed on a %s sequence', async (_name, sequences) => {
  const source = [
    sse('status', { event: 'status', sequence: sequences[0], request_id: 'req-1', phase: 'authorizing' }),
    sse('result', { event: 'result', sequence: sequences[1], request_id: 'req-1', safe_view: noAnswerSafeView }),
    sse('done', { event: 'done', sequence: sequences[1] + 1, request_id: 'req-1' }),
  ].join('')

  await expect(parseStage08AssistantStream(byteStream(source, []), () => undefined))
    .rejects.toThrow('Invalid assistant stream')
})

test('rejects done without a result event', async () => {
  const source = [
    sse('status', { event: 'status', sequence: 1, request_id: 'req-1', phase: 'authorizing' }),
    sse('done', { event: 'done', sequence: 2, request_id: 'req-1' }),
  ].join('')

  const events: Stage08AssistantStreamEvent[] = []
  await expect(parseStage08AssistantStream(byteStream(source, []), (event) => events.push(event)))
    .rejects.toThrow('Invalid assistant stream')
  expect(events.map((event) => event.event)).not.toContain('done')
})

test('returns the unique final safe_view after matching all answer deltas', async () => {
  const result = await parseStage08AssistantStream(
    byteStream(completeStream(), []),
    () => undefined,
  )

  expect(result.answer).toBe('最终安全结果')
})

test('rejects oversized event blocks and full responses with one stable error', async () => {
  const oversizedBlock = `event: future\n${'x'.repeat((64 * 1024) + 1)}`
  await expect(parseStage08AssistantStream(byteStream(oversizedBlock, []), () => undefined))
    .rejects.toThrow('Invalid assistant stream')

  const unknownBlock = `data: ${JSON.stringify({ event: 'future', value: 'x'.repeat(60 * 1024) })}\n\n`
  const oversizedResponse = unknownBlock.repeat(18)
  await expect(parseStage08AssistantStream(byteStream(oversizedResponse, []), () => undefined))
    .rejects.toThrow('Invalid assistant stream')
})

test('rejects invalid UTF-8 instead of decoding replacement characters', async () => {
  const prefix = new TextEncoder().encode('event: answer_delta\ndata: {"event":"answer_delta","sequence":1,"request_id":"req-1","text":"')
  const suffix = new TextEncoder().encode([
    '"}\n\n',
    sse('result', { event: 'result', sequence: 2, request_id: 'req-1', safe_view: safeView }),
    sse('done', { event: 'done', sequence: 3, request_id: 'req-1' }),
  ].join(''))
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(prefix)
      controller.enqueue(Uint8Array.from([0xc3, 0x28]))
      controller.enqueue(suffix)
      controller.close()
    },
  })

  await expect(parseStage08AssistantStream(stream, () => undefined))
    .rejects.toThrow('Invalid assistant stream')
})

test('emits a validated error event and rejects with a stable public failure', async () => {
  const events: Stage08AssistantStreamEvent[] = []
  const source = sse('error', {
    event: 'error',
    sequence: 1,
    request_id: 'req-1',
    code: 'stage08_collaboration_scope_denied',
    message: 'stage08_collaboration_scope_denied',
  })

  await expect(parseStage08AssistantStream(
    byteStream(source, []),
    (event) => events.push(event),
  )).rejects.toThrow('Assistant stream failed')
  expect(events).toEqual([{
    event: 'error',
    sequence: 1,
    requestId: 'req-1',
    code: 'stage08_collaboration_scope_denied',
    message: 'stage08_collaboration_scope_denied',
  }])
})

test('requires an optional SSE event field to match the payload discriminant', async () => {
  const source = sse(
    'status',
    { event: 'status', sequence: 1, request_id: 'req-1', phase: 'authorizing' },
    '\n',
    true,
  ).replace('event: status', 'event: answer_delta')

  await expect(parseStage08AssistantStream(byteStream(source, []), () => undefined))
    .rejects.toThrow('Invalid assistant stream')
})

test.each([
  ['mismatched', [sse('answer_delta', { event: 'answer_delta', sequence: 1, request_id: 'req-1', text: '不一致' })]],
  ['missing', []],
])('rejects %s deltas for a non-empty result answer', async (_name, deltaFrames) => {
  const source = [
    ...deltaFrames,
    sse('result', { event: 'result', sequence: deltaFrames.length + 1, request_id: 'req-1', safe_view: safeView }),
    sse('done', { event: 'done', sequence: deltaFrames.length + 2, request_id: 'req-1' }),
  ].join('')

  await expect(parseStage08AssistantStream(byteStream(source, []), () => undefined))
    .rejects.toThrow('Invalid assistant stream')
})

test('rejects answer deltas whose accumulated text exceeds the final answer boundary', async () => {
  const events: Stage08AssistantStreamEvent[] = []
  const frames = Array.from({ length: 5 }, (_, index) => sse('answer_delta', {
    event: 'answer_delta',
    sequence: index + 1,
    request_id: 'req-1',
    text: 'x'.repeat(index === 4 ? 1 : 500),
  }))

  await expect(parseStage08AssistantStream(byteStream(frames.join(''), []), (event) => events.push(event)))
    .rejects.toThrow('Invalid assistant stream')
  expect(events).toHaveLength(4)
})

test('rejects a private identifier split across answer delta chunks before rendering the completing chunk', async () => {
  const events: Stage08AssistantStreamEvent[] = []
  const source = [
    sse('answer_delta', { event: 'answer_delta', sequence: 1, request_id: 'req-1', text: 'private 550e8400-e29b-' }),
    sse('answer_delta', { event: 'answer_delta', sequence: 2, request_id: 'req-1', text: '41d4-a716-446655440000' }),
  ].join('')

  await expect(parseStage08AssistantStream(byteStream(source, []), (event) => events.push(event)))
    .rejects.toThrow('Invalid assistant stream')
  expect(events).toHaveLength(1)
})

test('rejects a duplicate result and any answer delta after result', async () => {
  const duplicate = [
    sse('result', { event: 'result', sequence: 1, request_id: 'req-1', safe_view: noAnswerSafeView }),
    sse('result', { event: 'result', sequence: 2, request_id: 'req-1', safe_view: noAnswerSafeView }),
    sse('done', { event: 'done', sequence: 3, request_id: 'req-1' }),
  ].join('')
  await expect(parseStage08AssistantStream(byteStream(duplicate, []), () => undefined))
    .rejects.toThrow('Invalid assistant stream')

  const deltaAfterResult = [
    sse('result', { event: 'result', sequence: 1, request_id: 'req-1', safe_view: noAnswerSafeView }),
    sse('answer_delta', { event: 'answer_delta', sequence: 2, request_id: 'req-1', text: 'late' }),
    sse('done', { event: 'done', sequence: 3, request_id: 'req-1' }),
  ].join('')
  await expect(parseStage08AssistantStream(byteStream(deltaAfterResult, []), () => undefined))
    .rejects.toThrow('Invalid assistant stream')
})

test.each(['same decoded buffer', 'later chunk'])('rejects bytes after done in the %s', async (placement) => {
  const throughDone = [
    sse('result', { event: 'result', sequence: 1, request_id: 'req-1', safe_view: noAnswerSafeView }),
    sse('done', { event: 'done', sequence: 2, request_id: 'req-1' }),
  ].join('')
  const source = `${throughDone}${sse('status', { event: 'status', sequence: 3, request_id: 'req-1', phase: 'completed' })}`
  const splitAt = placement === 'later chunk' ? [new TextEncoder().encode(throughDone).length] : []
  const events: Stage08AssistantStreamEvent[] = []

  await expect(parseStage08AssistantStream(byteStream(source, splitAt), (event) => events.push(event)))
    .rejects.toThrow('Invalid assistant stream')
  expect(events.map((event) => event.event)).not.toContain('done')
})

test('rejects bytes after error without publishing the terminal callback', async () => {
  const source = [
    sse('error', {
      event: 'error',
      sequence: 1,
      request_id: 'req-1',
      code: 'stage08_collaboration_scope_denied',
      message: 'stage08_collaboration_scope_denied',
    }),
    'x',
  ].join('')
  const events: Stage08AssistantStreamEvent[] = []

  await expect(parseStage08AssistantStream(byteStream(source, []), (event) => events.push(event)))
    .rejects.toThrow('Invalid assistant stream')
  expect(events).toEqual([])
})
