# Stage 03 Redis Streams Worker Module

## Status

- Document status: active module design
- Scope: Stage 03 PostgreSQL Outbox 到 Redis Streams 的投递桥接、worker runtime、retry/dead letter 和审计。
- Current Progress: 2026-07-06 Redis Streams bridge 和 worker runtime local/backend slice 已完成：新增 queue adapter interface、in-memory Redis Streams adapter、真实 Redis adapter 代码、outbox bridge、consumer-group-like read/ack/pending semantics、worker runner、Stage03 message handler、worker UOW、retry/dead letter、worker audit tests、worker runtime entrypoint 和 outbox bridge runtime entrypoint。live Redis consumer group rehearsal 和腾讯云 staging rehearsal 仍待后续确认与执行。

## 1. Scope

本模块负责把 Stage 03 的异步任务从 PostgreSQL outbox 安全投递到 Redis Streams，并由持久 worker 消费处理。

本模块做：

- Outbox to Redis Streams bridge。
- Redis Streams consumer group。
- Worker entrypoint。
- Bounded loop for tests。
- Continuous loop for staging runtime。
- Idempotent event handling。
- Retry and dead letter。
- Processing audit。

本模块不做：

- 不把 Redis 作为业务事实真源。
- 不绕过 service/UOW 写核心表。
- 不调用 LLM。
- 不调用真实 provider。
- 不发送 Telegram 消息。

## 2. Source Of Truth

PostgreSQL outbox 是一致性真源：

```text
business row + outbox_events row commit together
-> bridge sees committed outbox event
-> Redis Streams delivers job
-> worker processes
-> processing result written back to PostgreSQL
```

Redis Streams 是投递层，不是最终业务状态。Redis job 丢失、重复或重投都不能导致业务事实不可恢复。

## 3. Redis Streams Design

Recommended stream names:

| Environment | Stream |
| --- | --- |
| local test | `local:stage03:events` |
| staging | `staging:stage03:events` |

Consumer group:

```text
telegram-message-workers
```

Job envelope:

| Field | Required | Purpose |
| --- | --- | --- |
| `event_id` | yes | outbox event identity |
| `event_type` | yes | handler routing |
| `trace_id` | yes | cross-service tracing |
| `idempotency_key` | yes | duplicate protection |
| `message_id` | yes for message events | business record |
| `created_at` | yes | scheduling/debug |

## 4. Supported Event Types In Stage 03

| Event Type | Handler | Result |
| --- | --- | --- |
| `telegram.message_received` | message registration handler | update message processing status and audit |
| `telegram.message_reprocess` | same handler | safe reprocess after manual retry |

Out of scope:

- `telegram.notify`.
- `execution.recharge`.
- `readback.balance`.
- `agent.intent_extract` with real LLM.

## 5. Bridge Flow

```text
select pending outbox_events
-> for each event, build Redis job envelope
-> XADD into stream
-> mark outbox delivery status as enqueued
-> record delivery attempt/audit if needed
```

Rules:

- Bridge only reads committed outbox rows.
- Bridge must preserve event identity.
- Bridge failure leaves event retryable.
- Bridge retry must not create duplicate business effects.

## 6. Worker Flow

```text
XREADGROUP stream job
-> load outbox event and message
-> check idempotency
-> mark message processing_status = processing
-> run handler through service/UOW
-> update message processing_status = processed
-> write audit
-> XACK
```

Failure flow:

```text
handler error
-> classify retryable/non_retryable
-> increment attempt count
-> retry or dead_letter
-> write safe error code
-> write audit
-> reflect status in telegram_inbox
```

## 7. State Machines

### Outbox Delivery

| State | Event | Next |
| --- | --- | --- |
| `pending` | bridge enqueue success | `enqueued` |
| `pending` | bridge transient failure | `pending` or `retrying` |
| `enqueued` | worker success | `processed` |
| `enqueued` | worker retryable failure | `retrying` |
| `retrying` | attempts exhausted | `dead_letter` |
| `enqueued` | non-retryable failure | `dead_letter` |

### Message Processing

| State | Event | Next |
| --- | --- | --- |
| `received` | outbox created | `queued` |
| `queued` | worker claims | `processing` |
| `processing` | handler success | `processed` |
| `processing` | retryable failure | `queued` or `retrying` |
| `processing` | exhausted/non-retryable | `dead_letter` |

## 8. Implementation Files

| Purpose | File |
| --- | --- |
| Redis Streams adapter | `backend/app/queues/redis_streams.py` implemented for interface + in-memory test adapter + production `RedisStreamsClient` + read/ack/pending semantics |
| Queue package init | `backend/app/queues/__init__.py` implemented |
| Worker runner | `backend/app/workers/runner.py` implemented |
| Stage 03 handlers | `backend/app/workers/stage03_handlers.py` implemented |
| Outbox repository extension | `backend/app/repositories/outbox.py` |
| Outbox service extension | `backend/app/services/outbox.py` implemented bridge service |
| Bridge tests | `backend/tests/integration/test_stage03_redis_streams_bridge.py` implemented |
| Worker tests | `backend/tests/integration/test_stage03_worker_runtime.py` implemented |

## 9. Tests

Required tests:

- Committed outbox event becomes Redis Streams job. Passed in `test_stage03_redis_streams_bridge.py`.
- Rolled-back event is not enqueued. Passed in `test_stage03_redis_streams_bridge.py`.
- Re-running bridge is idempotent. Passed in `test_stage03_redis_streams_bridge.py`.
- Worker processes one bounded iteration. Passed in `test_stage03_worker_runtime.py`.
- Worker continuous loop can be bounded for staging smoke. Passed in `test_stage03_worker_runtime.py`.
- Worker rerun does not duplicate effects. Passed in `test_stage03_worker_runtime.py`.
- Retryable error increments attempt count. Passed in `test_stage03_worker_runtime.py`.
- Exhausted retry becomes dead letter. Passed in `test_stage03_worker_runtime.py`.
- Dead letter is visible in Bitable inbox and audit. Passed in `test_stage03_worker_runtime.py`.

## 10. Acceptance Criteria

- PostgreSQL outbox remains consistency anchor.
- Redis Streams worker can run through the queue protocol; live Redis rehearsal remains pending before Stage 03 close.
- Worker can be tested in bounded mode.
- Duplicate Redis delivery does not duplicate business rows.
- Failures are visible, retryable or dead-lettered with audit.
