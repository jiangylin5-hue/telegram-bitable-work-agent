# Agent Event Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a durable, permission-safe supervisor/sub-agent control plane whose internal events are projected to reconnectable browser SSE.

**Architecture:** PostgreSQL owns runs, checkpoints, commands, events, a short-lived encrypted private-input store and an outbox; Redis Streams provides at-least-once delivery; independent publisher/specialist processes perform the work; a supervisor validates typed child events and the SSE projector exposes only safe projections. LangGraph remains request-private and reconstructs context after recovery rather than serializing graph state.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis Streams, LangGraph, React/Vite/TypeScript.

## Global Constraints

- Follow `AGENTS.md`, `AGENT_EVENT_RUNTIME_PROPOSAL.md` and existing Stage06 authorization, Tool Gateway, draft-confirmation and audit boundaries.
- No raw prompt, model response, group text, private retrieval evidence, credential, authority object or hidden field may enter checkpoint, Redis, audit, SSE or browser storage. The bounded query may exist only as authenticated ciphertext in the expiring private-input table.
- All write-capable work remains draft/ticket-only and requires current-scope confirmation.
- Preserve `/api/stage08/assistant/query` and `/query-stream` until feature-flagged migration acceptance completes.
- Approval receipt: the user explicitly approved architecture/technical review followed by implementation on 2026-07-28.
- Execution receipt: the user explicitly approved distributed wiring, isolated deployment and real PostgreSQL/Redis/OpenRouter/browser acceptance on 2026-07-28. Public cutover, Telegram sends and business writes remain excluded.

---

## File Map

| File | Responsibility |
| --- | --- |
| `backend/alembic/versions/<revision>_agent_event_runtime.py` | create run/control-plane tables and constraints |
| `backend/app/models/agent_event_runtime.py` | SQLAlchemy models only |
| `backend/app/schemas/agent_event_runtime.py` | strict command/event/checkpoint/SSE schemas |
| `backend/app/services/agent_event_runtime.py` | transactional state machine, leases, idempotency and outbox |
| `backend/app/queues/agent_event_streams.py` | Redis Stream publish, consume and pending-claim adapter |
| `backend/app/services/agent_orchestrator.py` | supervisor fan-out/fan-in and capability registry enforcement |
| `backend/app/services/agent_sse_projection.py` | authorization-aware internal-event to SSE projection |
| `backend/app/api/routes/agent_runs.py` | feature-flagged run creation/read/SSE endpoints |
| `backend/app/services/agent_private_inputs.py` | strict AES-GCM seal/open and expiry policy |
| `backend/app/workers/agent_event_outbox_runtime.py` | due outbox polling, validated publish and retry bookkeeping |
| `backend/app/workers/agent_tabular_runtime.py` | pending recovery, current-scope reauthorization, private-input reconstruction, execution and post-commit ack |
| `backend/tests/unit/test_agent_event_runtime.py` | transition, lease, protocol and redaction tests |
| `backend/tests/integration/test_agent_event_runtime_postgres.py` | real transaction/recovery/outbox tests |
| `backend/tests/integration/test_agent_event_streams_redis.py` | Redis pending-claim and duplicate-delivery tests |
| `mini-app/src/app/agent-run-events.ts` | strict browser event parser/reconnect reducer |
| `mini-app/src/test/agent-run-events.test.ts` | browser replay/order/revocation tests |

### Task 1: Approve protocol and add strict schemas

**Files:**
- Create: `backend/app/schemas/agent_event_runtime.py`
- Test: `backend/tests/unit/test_agent_event_runtime.py`

**Interfaces:**
- Produces: `AgentCommandEnvelope`, `AgentEventEnvelope`, `RunCheckpointControl`, `SafeRunStreamEvent`.
- Rejects: extra fields, raw text payloads, invalid UUIDs, non-monotonic sequences and unregistered capability names.

- [x] Write failing schema tests for a valid command/event and rejection of `prompt`, `raw_result`, `record_values` and unknown event types.
- [x] Run `python -m pytest backend/tests/unit/test_agent_event_runtime.py -q`; expect schema-import failure.
- [x] Implement Pydantic strict models with `extra='forbid'`, UUID IDs, fixed enums, bounded summaries and hash/reference fields only.
- [x] Run the same command; expect all schema cases to pass.

### Task 2: Add durable run/checkpoint/outbox data model

**Files:**
- Create: `backend/app/models/agent_event_runtime.py`
- Create: `backend/alembic/versions/<revision>_agent_event_runtime.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/integration/test_agent_event_runtime_postgres.py`

**Interfaces:**
- Consumes: Task 1 envelopes.
- Produces: `AgentWorkflowRun`, `AgentRunCheckpoint`, `AgentCommand`, `AgentEvent`, `AgentOutboxEvent`.

- [x] Write failing PostgreSQL tests for unique checkpoint/sequence constraints and one transaction that creates a run plus outbox row.
- [x] Run the focused integration test; expect absent table/model failure.
- [x] Implement models and one Alembic migration with foreign keys, indexes, constraints and no raw-content columns.
- [x] Run Alembic offline SQL plus the focused PostgreSQL test; expect pass.

### Task 3: Implement transactional state machine and leases

**Files:**
- Create: `backend/app/services/agent_event_runtime.py`
- Test: `backend/tests/unit/test_agent_event_runtime.py`
- Test: `backend/tests/integration/test_agent_event_runtime_postgres.py`

**Interfaces:**
- Produces: `create_run`, `claim_run_lease`, `append_checkpoint_and_event`, `complete_command`, `cancel_run`, `replay_safe_events`.

- [x] Write failing tests for duplicate command delivery, expired lease takeover, sequence conflict, cancellation and scope-hash drift.
- [x] Run focused tests; expect service-import failure.
- [x] Implement locked/optimistic transitions; each successful transition appends checkpoint, event and outbox in one transaction.
- [x] Run focused unit and PostgreSQL tests; expect exactly-once durable transitions under duplicate delivery.

### Task 4: Add Redis Stream outbox bridge

**Files:**
- Create: `backend/app/queues/agent_event_streams.py`
- Modify: existing worker/bridge bootstrap only after inspection
- Test: `backend/tests/integration/test_agent_event_streams_redis.py`

**Interfaces:**
- Consumes: unpublished `AgentOutboxEvent`.
- Produces: stream messages on `agent.commands.*`, `agent.events` and safe `agent.sse`.

- [x] Write failing tests for publish retry, pending-entry claim and consumer acknowledgement only after durable event commit.
- [x] Run focused Redis integration test; expect adapter-import failure.
- [x] Implement a bounded adapter that serializes only Task 1 envelopes and records publish attempts transactionally.
- [x] Run focused tests; expect duplicate stream deliveries to cause no duplicate database event. Real Redis remains an environment-gated deployment check.

### Task 5: Build supervisor and one read-only specialist path

**Files:**
- Create: `backend/app/services/agent_orchestrator.py`
- Modify: `backend/app/services/stage08_collaboration.py`
- Test: `backend/tests/unit/test_agent_orchestrator.py`

**Interfaces:**
- Consumes: `AgentCommandEnvelope`, existing Stage06 authorization and registered skill capabilities.
- Produces: child commands/events for `platform.tabular.analyse` only.

- [x] Write failing tests proving an unregistered capability, stale scope proof and child `run.completed` event are rejected.
- [x] Run the focused test; expect orchestrator-import failure.
- [x] Implement deterministic candidate selection, supervisor fan-in validation and a LangGraph adapter that rebuilds private context after claiming a lease.
- [x] Run focused tests; expect one read-only child result to create a safe supervisor result without business writes.

### Task 6: Add safe SSE projector and reconnect API

**Files:**
- Create: `backend/app/services/agent_sse_projection.py`
- Create: `backend/app/api/routes/agent_runs.py`
- Modify: API router registration
- Test: `backend/tests/api/test_agent_run_events_api.py`

**Interfaces:**
- Produces: `POST /api/stage10/agent-runs`, `GET /api/stage10/agent-runs/{run_id}/events`.
- Reads: `Last-Event-ID` and safe persisted `AgentEvent` rows.

- [x] Write failing API tests for sequence ordering, reconnect replay, revoked permission and no raw field in stream output.
- [x] Run the focused API test; expect route-not-found failure.
- [x] Implement feature-flagged routes and projection whitelist (`status`, `artifact_ready`, `result`, `error`, `done`).
- [x] Run focused API tests; expect reconnect to replay only still-authorized safe events.

### Task 7: Add Mini App run-event client behind a feature flag

**Files:**
- Create: `mini-app/src/app/agent-run-events.ts`
- Modify: `mini-app/src/app/CollaborationWorkbench.tsx`
- Test: `mini-app/src/test/agent-run-events.test.ts`

**Interfaces:**
- Consumes: Task 6 `SafeRunStreamEvent` only.
- Produces: ordered timeline state, reconnect cursor and explicit terminal UI state.

- [x] Write failing Vitest cases for duplicate event IDs, sequence gap, reconnect, `done` without `result`, and authorization error.
- [x] Run `npm.cmd run test:run -- agent-run-events`; expect module-not-found failure.
- [x] Implement parser/reducer with server event whitelist and `Last-Event-ID`; retain legacy Stage08 stream fallback.
- [x] Run focused tests and `npm.cmd run build`; expect pass.

### Task 8: Security, recovery and deployment acceptance

**Files:**
- Modify: proposal evidence and Stage10 acceptance document created at implementation start
- Test: all Task 2–7 suites plus existing Stage08 collaboration suites

- [x] Write end-to-end failure tests for worker crash after command delivery, lease expiry, stream replay, cancellation, scope revocation and draft-route denial.
- [x] Run PostgreSQL/Redis acceptance suites; require each failure condition to produce a stable safe terminal event.
- [x] Run full backend tests, Mini App tests, production build, static artifact parity and a browser read-only reconnect smoke.
- [x] Perform independent security review of schema columns, event payloads, logs and SSE output before requesting deployment authorization.

### Task 9: Replace embedded compatibility execution with real distributed services

**Files:**
- Modify: `backend/alembic/versions/20260728_0034_agent_event_runtime.py`
- Modify: `backend/app/models/agent_event_runtime.py`
- Create: `backend/app/services/agent_private_inputs.py`
- Create: `backend/app/workers/agent_event_outbox_runtime.py`
- Create: `backend/app/workers/agent_tabular_runtime.py`
- Modify: `backend/app/api/routes/agent_runs.py`
- Modify: Stage09 native systemd/runtime/deployment assets
- Test: focused unit, PostgreSQL, Redis and process-recovery suites

- [x] Write failing tests for AES-GCM round-trip/AAD drift/expiry, staging fail-closed configuration and workspace allowlist.
- [x] Implement strict encrypted private-input persistence without plaintext columns or logging.
- [x] Write failing publisher tests for `SKIP LOCKED`, publish failure retry and mixed command/event topics.
- [x] Implement the publisher process and systemd unit.
- [x] Write failing worker tests for new delivery, crash before ack, `XAUTOCLAIM`, duplicate completed delivery, scope revocation and deadline failure.
- [x] Implement the specialist worker and commit-before-ack boundary.
- [x] Change the API so `redis_worker` returns after durable enqueue; retain `embedded` only for local compatibility.
- [x] Add deployment preflight requiring mode, key and workspace allowlist in production-like environments.

### Task 10: Isolated server and real quality acceptance

- [x] Create an isolated acceptance release/venv and service namespace without replacing the active public release.
- [x] Apply `20260728_0034` to the authorized isolated PostgreSQL target and verify one Alembic head.
- [x] Run real Redis XADD/XREADGROUP/XAUTOCLAIM/XACK recovery tests and capture sanitized evidence.
- [x] Import the approved multi-table fixture and run at least 20 Chinese OpenRouter cases through the distributed endpoint.
- [x] Report query, safe answer, selected skill, retrieval precision/recall/readiness, answer-quality score, latency and failure/degradation code.
- [x] Open the domain in a browser and verify chat entry, clicks, loading/progress, reconnect, result, empty/error states and console/network health.
- [x] Reproduce and fix the public-UI false-negative where auto-selected `platform-base` receives `general_advice`: add frontend routing/selection tests first, retain workspace-level `mixed`, expose `aria-pressed`, and keep skill selection from replacing the user query.
- [x] Rebuild and redeploy the corrected static/source artifact, then repeat the same Chinese multi-table question through the actual browser UI and require citations plus a data-grounded answer.
- [x] Run full backend/frontend/build/static/security regressions, remove obsolete skipped tests and temporary artifacts.
- [x] Audit the complete diff and create exactly one final commit only after every required gate passes.

## Self-Review

- Coverage: Tasks 1–3 cover protocol, schema, checkpoints and recovery; Task 4 covers event delivery; Task 5 covers supervisor/sub-agent routing; Tasks 6–7 cover SSE projection and UI; Task 8 covers safety and acceptance.
- Placeholder scan: no deferred placeholder or unspecified error-handling step is present.
- Type consistency: all tasks use the Task 1 envelope names and the Task 2 persistence model names.

## Execution Handoff

Approval is complete. Execute Tasks 9–10 inline without task-level commits. If isolated acceptance exposes a failure, fix and rerun the affected gate; create exactly one final audited commit only after all required gates pass.
