# 多 Agent 事件运行时与安全恢复方案（提案）

## Status

- Status: distributed execution extension approved and in progress on 2026-07-28; local compatibility runtime exists, real publisher/worker and isolated deployment gates are being implemented
- Scope: supervisor/sub-agent command and event protocol, durable orchestration state, recovery checkpoint, Redis Streams transport and browser SSE projection
- Excluded: changing table/draft permission rules, Telegram sending, provider-side writes, raw prompt retention, autonomous record writes and a general-purpose agent framework
- Decision receipt: the user explicitly requested a full architecture/technical review followed by implementation on 2026-07-28; schema, API and permission-boundary work in this document is approved within the stated scope

### 2026-07-28 implementation audit

- Stage naming: the new durable run API and migration are Stage10; existing Stage08 synchronous/SSE APIs remain compatibility paths until Stage10 browser and recovery acceptance pass.
- Checkpoint boundary: v1 keeps LangGraph `checkpointer=None`; only redacted control-plane checkpoints are durable. An encrypted raw graph-state checkpointer is not implicitly approved.
- Capability boundary: v1 implements one read-only `platform.tabular.analyse` specialist. Draft and external-action specialists remain outside the first activation gate.
- Artifact boundary: v1 stores validated safe artifact metadata or existing safe result references. It does not introduce an arbitrary blob/content store.
- Delivery boundary: PostgreSQL is authoritative; Redis Streams is at-least-once transport. Exactly-once effects are produced by database uniqueness and idempotent state transitions, not by assuming exactly-once queue delivery.
- Commit boundary: implementation tasks remain uncommitted until whole-stage tests, recovery acceptance, security audit and documentation review pass; then one final commit may be created.
- Deployment receipt: after reviewing the remaining Redis/worker/deployment gates, the user explicitly instructed execution on 2026-07-28. This approves an isolated Stage10 acceptance deployment, real Redis/PostgreSQL/OpenRouter verification and one final commit after all gates pass. It does not approve Telegram sends, provider-side writes, autonomous table writes or an unreviewed public cutover.

## 1. Problem Statement

The current Stage08 graph has a secure request-local workflow and Stage09 exposes its safe terminal result through SSE. It deliberately compiles LangGraph with `checkpointer=None`; raw model material, retrieval evidence and group context remain process-private.

This is correct for a bounded synchronous assistant query, but it does not provide durable child-agent dispatch, worker recovery, disconnect recovery, queue isolation, supervisor leases or replayable user-facing progress for a multi-agent runtime. The target is not to let agents exchange conversational prose. The target is a durable, typed control plane where an LLM may create an approved artifact but never becomes the authority for routing or completion.

## 2. Architecture Decisions

### 2.1 Separate internal events from browser SSE

```text
Command API / Telegram ingress
  -> Task Gateway
  -> PostgreSQL transaction: AgentRun + OutboxEvent
  -> Redis Stream command topic
  -> supervisor / specialist worker
  -> PostgreSQL transaction: checkpoint + AgentEvent + OutboxEvent
  -> Redis Stream event topic
  -> SSE projector
  -> permission-filtered browser event
```

- Internal command/event messages are durable, typed and idempotent.
- Browser SSE is an untrusted presentation projection. It must never carry the internal payload, raw tool output, provider response, stack trace, authority proof or private checkpoint data.
- A sub-agent does not maintain a free-form conversation with its supervisor. It consumes a command and emits lifecycle/domain events. Natural-language output is an artifact referenced by ID and validated by the supervisor.

### 2.2 The supervisor is a control-plane service, not an unrestricted LLM

The supervisor owns run routing, dependency checks, timeout policy, cancellation, human-confirmation gates and terminal-state transition. It may use an LLM only to propose a bounded route from a registry-provided candidate list; deterministic policy validates that proposal before any command is persisted.

Specialists own one capability only, such as `platform.base.read`, `platform.tabular.analyse`, `platform.task.draft` or `platform.telegram.context.read`. They cannot invoke another specialist directly, write records directly or select their own authority.

### 2.3 Checkpoint the control plane, not private evidence

`RunCheckpoint` may persist:

- `run_id`, `checkpoint_no`, `workflow_version`, `node_key`, `run_status`;
- parent/child dependency completion flags, bounded counters, deadline and retry number;
- idempotency key/hash, command schema version, selected capability and safe artifact reference;
- authorization/scope version hashes and current-record version hashes needed to detect drift;
- a redacted error/degradation code and the next deterministic action.

It must not persist raw query text, prompts, provider response, retrieved field values, group text, embeddings, private LangGraph state, tool credentials or implicit authority. Recovery reauthorizes, rereads required facts and reconstructs private context; it does not deserialize an old graph state.

### 2.4 Short-lived encrypted input is separate from the control plane

A distributed worker cannot reconstruct a user request from an idempotency hash. Therefore Stage10 adds one narrowly scoped private-input store; otherwise the apparent Redis worker would still depend on the API process's memory and would not be recoverable.

The store persists only AES-256-GCM ciphertext, a 96-bit nonce, key version, AAD hash, scope hash, expiry and consumption timestamps. The authenticated additional data binds `run_id`, `command_id`, `workspace_id`, `scope_hash` and schema version, so ciphertext cannot be moved to another run or scope. The environment provides a 32-byte base64 key; the key and plaintext never enter PostgreSQL, Redis, checkpoints, events, logs, metrics, SSE or browser storage. Decryption is allowed only inside the registered specialist worker after current authorization, command, deadline and scope checks.

This is not a LangGraph checkpointer and does not persist graph state, retrieval evidence, provider responses or chain-of-thought. The plaintext payload is a strict, versioned reconstruction request containing the original bounded assistant request and caller user ID. Rows expire after a short retention window and are marked consumed after a terminal durable transition; cleanup is a separate idempotent maintenance operation.

## 3. Domain Model and Persistence Contract

The new data model is intentionally separate from the existing safe `AgentRun` audit summary. It needs a new Alembic migration and explicit approval.

| Table | Purpose | Required columns | Sensitive-data rule |
| --- | --- | --- | --- |
| `agent_workflow_runs` | one root supervisor run | `id`, `workspace_id`, `root_employee_id`, `target_record_id`, `parent_run_id`, `workflow_version`, `status`, `scope_hash`, `deadline_at`, `lease_owner`, `lease_expires_at`, `idempotency_key_hash`, `safe_result_ref`, timestamps | no query/prompt/private evidence; target ID is retained so reconnect can reauthorize the original record scope |
| `agent_run_checkpoints` | append-only recovery control state | `id`, `run_id`, `checkpoint_no`, `node_key`, `status`, `control_json`, `authorization_hash`, `data_version_hash`, timestamps | `control_json` has an allowlist only |
| `agent_commands` | immutable work items | `id`, `run_id`, `parent_command_id`, `target_capability`, `command_type`, `sequence`, `payload_ref`, `deadline_at`, `idempotency_key_hash`, `status` | payload is a safe opaque reference, not raw content |
| `agent_events` | append-only lifecycle/domain facts | `id`, `run_id`, `command_id`, `event_type`, `sequence`, `causation_id`, `correlation_id`, `safe_summary`, `artifact_ref`, `metrics_json`, timestamps | no raw artifact or tool result |
| `agent_artifacts` | validated, access-controlled output metadata | `id`, `run_id`, `kind`, `storage_ref`, `content_hash`, `visibility_scope_hash`, `validation_status`, expiry | actual content follows its existing durable owner; no duplicate secret copy |
| `agent_outbox_events` | transactional handoff to Redis | `id`, `aggregate_type`, `aggregate_id`, `topic`, `event_id`, `payload_json`, `published_at`, retry fields | only sealed command/event envelopes |
| `agent_private_inputs` | short-lived encrypted worker reconstruction input | `id`, `run_id`, `command_id`, `ciphertext`, `nonce`, `key_version`, `aad_hash`, `scope_hash`, `expires_at`, `consumed_at` | no plaintext column; AES-GCM only; never published to Redis/SSE/audit |

Unique constraints: `(run_id, checkpoint_no)`, `(run_id, sequence)` for events, `(run_id, idempotency_key_hash)` for root requests and `(command_id, event_type, sequence)` for worker emission. All state transition updates use `SELECT ... FOR UPDATE` or optimistic versioning; a lease can be claimed only after expiry.

## 4. Typed Protocol

### 4.1 Command envelope

```json
{
  "schema_version": "agent-command.v1",
  "command_id": "uuid",
  "run_id": "uuid",
  "parent_command_id": "uuid-or-null",
  "causation_id": "uuid",
  "correlation_id": "uuid",
  "sequence": 7,
  "target_capability": "platform.tabular.analyse",
  "command_type": "analyse_visible_records",
  "scope_proof_ref": "safe-reference",
  "input_artifact_refs": ["uuid"],
  "deadline_at": "RFC3339",
  "idempotency_key_hash": "sha256"
}
```

Workers must reject unknown schema versions, missing causal links, expired deadlines, stale leases, unsupported capabilities, scope-proof mismatch and duplicate command IDs. They may resolve the safe references only through the Tool Gateway and must reauthorize at consumption time.

### 4.2 Event envelope

```json
{
  "schema_version": "agent-event.v1",
  "event_id": "uuid",
  "run_id": "uuid",
  "command_id": "uuid",
  "causation_id": "uuid",
  "correlation_id": "uuid",
  "sequence": 8,
  "event_type": "agent.completed",
  "status": "completed",
  "safe_summary": "完成已授权记录的汇总",
  "artifact_ref": "uuid-or-null",
  "metrics": {"records_read": 12},
  "occurred_at": "RFC3339"
}
```

Allowed lifecycle events are `run.accepted`, `command.dispatched`, `agent.started`, `agent.progressed`, `agent.completed`, `agent.degraded`, `agent.failed`, `run.waiting_approval`, `run.cancelled`, `run.timed_out` and `run.completed`. A specialist cannot emit any `run.*` event, issue execution tickets or mark a draft confirmed.

## 5. Redis Stream Topology and Delivery Semantics

| Stream | Producer | Consumer group | Purpose |
| --- | --- | --- | --- |
| `agent.commands.supervisor` | Task Gateway/Supervisor | `supervisor-workers` | root routing and resume commands |
| `agent.commands.<capability>` | Supervisor | capability-specific workers | specialist commands |
| `agent.events` | workers via outbox bridge | `orchestrator` | state transition and fan-in |
| `agent.sse` | SSE projector | browser connections | short-retention safe progress projection |

The database transaction writes state and `agent_outbox_events` together. A bridge publishes the outbox row to Redis and marks it published only after the stream write succeeds. Consumers acknowledge only after their state transition and emitted event are committed. Re-delivery is safe because each command/event has unique IDs and transitions are idempotent.

Redis is not the source of truth. PostgreSQL is authoritative for run state and checkpoints; a worker crash after stream delivery is recovered by pending-entry claim plus lease expiry.

### 5.1 Executable service topology

The compatibility API path is not counted as distributed acceptance. The accepted deployment topology contains two new independently restartable processes:

1. `stage10-agent-outbox-publisher`: selects due unpublished rows with `FOR UPDATE SKIP LOCKED`, validates their strict envelope, performs idempotent `XADD`, and records `published_at` only after success. Failure records only a bounded stable code and a retry timestamp.
2. `stage10-tabular-worker`: reads `agent.commands.platform.tabular.analyse` through a capability-specific consumer group, tries `XAUTOCLAIM` for idle pending entries before new entries, validates the envelope against the durable command/run, reauthorizes, decrypts the private input, executes the existing Stage08 read-only path, commits durable events/artifact metadata, and only then sends `XACK`.

`AGENT_EVENT_RUNTIME_MODE=embedded|redis_worker` controls execution. `embedded` is a local/test compatibility mode; production-like environments may enable Stage10 only with `redis_worker`, a configured encryption key and an explicit workspace allowlist. `AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS` is deny-by-default when Stage10 is enabled in staging/production. A workspace outside the allowlist receives the normal Stage08 path through frontend fallback and cannot enqueue Stage10 work.

## 6. LangGraph Integration

LangGraph remains a local decision graph inside the supervisor or specialist worker. It should be compiled with `checkpointer=None` at first. A graph node is adapted as:

```text
claim Run lease
-> load redacted checkpoint control fields
-> reauthorize and reread current source versions
-> rebuild private context in memory
-> invoke bounded LangGraph node/graph
-> validate output through capability schema and Tool Gateway
-> transactionally append checkpoint + AgentEvent + OutboxEvent
-> release or renew lease
```

This preserves the current private-state safety guarantee while adding process recovery. A future encrypted LangGraph checkpointer is not part of v1; it would require a separate data-classification, key-management, retention and incident-response approval.

## 7. SSE Projection and Reconnect

The existing `POST /api/stage08/assistant/query-stream` remains compatible during migration. The new run API uses `GET /api/stage10/agent-runs/{run_id}/events` with `Last-Event-ID`.

The SSE projector validates that the browser caller still has workspace/employee/record scope at every connect and replay. It transforms only allowlisted internal events into:

- `status`: stable public phase and sequence;
- `artifact_ready`: safe artifact label/ref, never content by default;
- `result`: validated `SafeView` or draft reference;
- `error`: stable code/message;
- `done`: terminal event.

If the gap cannot be replayed from the short SSE stream, the projector rereads `agent_events` from PostgreSQL and emits only events still authorized for that caller. Event sequence is per run, monotonically increasing and immutable.

## 8. Safety and Human-in-the-loop Rules

- Only `Tool Gateway` resolves artifact references into authorized reads or controlled actions.
- Any write-capable command can create only a draft or execution ticket. Confirmation is a separate actor-bound command with current-scope revalidation.
- Supervisor fan-in accepts a child result only when the child capability, parent command, scope hash, artifact validation and sequence are valid.
- Cancellation prevents new commands and marks the run terminal only after active child leases either stop or expire; it never claims a provider/tool operation was cancelled without a provider receipt.
- A timeout/degradation event is terminal for its command; supervisor may route an explicitly permitted fallback capability, but cannot silently widen scope or invoke a higher-risk tool.

## 9. Incremental Migration

1. Add schema, migration, protocol models and state-transition tests without routing traffic.
2. Add outbox bridge and Redis Stream contract tests; keep current synchronous assistant path unchanged.
3. Introduce a read-only supervisor capability that dispatches one table-analysis specialist and emits safe events; no draft route.
4. Add durable SSE projector and browser reconnect behind a feature flag, while retaining current `/query-stream` fallback.
5. Add draft/ticket command only after a standalone permission and human-confirmation review.
6. Migrate selected skills one by one; do not create a generic unrestricted `delegate_to_agent` tool.

## 10. Acceptance Criteria

- A worker restart recovers a leased read-only run without replaying completed child commands or exposing private context.
- Duplicate delivery produces exactly one durable checkpoint/event transition and one safe UI result.
- Scope or data-version drift prevents continuation and produces a redacted terminal event.
- SSE reconnect resumes from `Last-Event-ID` or safe PostgreSQL replay; it cannot replay a result after permission revocation.
- Specialist agents cannot write business records, self-confirm drafts, issue tickets or invoke non-registered capabilities.
- Tests cover lease contention, outbox publish retry, Redis pending claim, sequence gap, cancellation, timeout, authorization revocation, artifact validation and browser reconnect.
