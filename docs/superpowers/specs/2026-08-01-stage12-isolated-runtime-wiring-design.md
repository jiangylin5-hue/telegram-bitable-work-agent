# Stage12 Isolated Runtime Wiring Design

## Status

- Document status: `written-pending-user-review`
- Scope: isolated Stage12 FastAPI, LangGraph, PostgreSQL/pgvector, Redis typed-specialist, Grounded Provider and SSE wiring
- Production-wide activation: excluded
- Public endpoint expansion: none
- Database migration: not expected; existing revisions `20260729_0035` through `20260730_0039` remain authoritative
- Approved direction: the user approved the recommended isolated-runtime approach on 2026-08-01; implementation still waits for review of this written specification

## 1. Problem Statement

The native r79 candidate proves that the Stage12 Grounded Provider can produce
`36/36` accepted representative answers with `answer_source=real_provider` and
zero fallback, unauthorized effects, production writes or Telegram sends.
That evidence is Provider-layer evidence, not deployed end-to-end evidence.

The current `stage12_final_provider_campaign` invokes
`IsolatedAFExecutor`, which creates an in-memory Stage12 fixture. The public
Agent Run API still dispatches the Stage11/Stage08 private-input path. The
typed-specialist worker path exists, but its production data source and
Grounded Provider fan-in are not wired. The current fan-in calls deterministic
`compose_claim_graph()`, and SSE only resolves Stage08 `AssistantQuerySafeView`
artifacts.

Therefore the following acceptance claim is currently false and must remain
blocked:

```text
FastAPI
-> LangGraph admission
-> PostgreSQL/pgvector authorized data
-> durable outbox
-> Redis typed Specialist workers
-> ClaimGraph fan-in
-> real Grounded Provider
-> safe SSE result with answer_source
```

The goal of this design is to make that path real for one isolated evaluation
workspace without changing global production answer authority.

## 2. Considered Approaches

### 2.1 Separate evaluation endpoint

Add a private `/stage12/evaluate` route that directly invokes the in-memory
runner.

Rejected because it expands the API, bypasses the existing Agent Run identity,
durability and SSE contracts, and still would not exercise real workspace data
or Redis Specialist workers.

### 2.2 Server-side campaign script only

Keep the current campaign and separately run component tests for FastAPI,
PostgreSQL, Redis and SSE.

Rejected because independently green components do not prove the Stage12
answer travelled through them. It would preserve the exact acceptance gap that
Task11 and Task12 prohibit.

### 2.3 Existing Agent Run API with explicit isolated runtime mode

Reuse the existing Agent Run request and SSE endpoints. Add one fail-closed
Stage12 runtime mode and one workspace allowlist. For an allowlisted workspace,
admission builds authorized Stage12 artifacts from PostgreSQL, persists typed
inputs, and dispatches them through the existing outbox and Redis streams.
The last Specialist fan-in invokes the fixed Grounded Provider and publishes a
safe SSE result. All other workspaces continue using Stage11/Stage08.

Selected because it proves the real deployed topology, introduces no new
public endpoint, preserves existing identity and permission intersection, and
can be disabled by one configuration change.

## 3. Runtime Activation Contract

Add two server-only settings:

```text
STAGE12_RUNTIME_MODE=off|isolated
STAGE12_RUNTIME_WORKSPACE_ALLOWLIST=<comma-separated UUIDs>
```

Rules:

1. The default is `off`.
2. `isolated` requires exactly one or more valid workspace UUIDs.
3. `off` requires an empty allowlist.
4. An allowlisted request must also satisfy the existing Agent Event Runtime,
   caller identity, digital-employee scope, table/view/field permission and
   chat scope checks.
5. `isolated` requires the existing confirmed Stage12 Provider profile,
   OpenRouter credential, Redis-worker runtime, private-input encryption key,
   retrieval profile and PostgreSQL runtime to validate at startup.
6. Component `shadow` flags do not activate this path and cannot change an
   answer. The new runtime mode is the only Stage12 answer-authority switch.
7. There is no `active`, `global` or wildcard mode in Stage12.

The native production profile remains:

```text
STAGE12_RUNTIME_MODE=off
STAGE12_RUNTIME_WORKSPACE_ALLOWLIST=
```

until an isolated evaluation workspace has been prepared and explicitly added.

## 4. Admission and LangGraph Boundary

The existing `POST /api/stage10/agent-runs` request contract remains unchanged.
After normal identity and permission checks, the route chooses exactly one
path:

```text
not allowlisted -> existing Stage11/Stage08 dispatch
allowlisted + isolated -> Stage12 isolated admission
invalid config/scope -> fail closed before dispatch
```

Stage12 isolated admission uses a small LangGraph state graph with explicit
nodes:

```text
authorize_schema
-> plan_task
-> execute_structured_query / authorized retrieval
-> persist_typed_inputs
-> dispatch_commands
```

The graph runs only bounded admission work. Long-running Specialist and
Provider execution remains in the durable worker topology. The graph state
contains typed models and hashes; it is not persisted as raw Query, Prompt or
Provider output.

Admission must:

- use `SqlAlchemyStage06PlatformUnitOfWork`, never the in-memory fixture UOW;
- build `AuthorizedSchemaSnapshot`, entity candidates, `TaskSpecV2`, restricted
  query plans and structured query artifacts from the real isolated workspace;
- call pgvector retrieval only when the TaskSpec needs semantic evidence;
  exact structured cases may truthfully record retrieval as not applicable;
- persist typed artifact owners plus `AgentArtifact` metadata under the current
  authorization hash;
- create `ObjectiveSpecialistInputV1` for the exact required/optional DAG;
- dispatch only registered typed capabilities;
- commit run, artifacts, commands, outbox and audit atomically.

No business record is created or updated during read-only admission.

## 5. Private Query and Typed Command Contract

Raw Query must not be stored in a plaintext typed artifact. Each dispatched
typed command receives its own existing AES-GCM `AgentPrivateInputPayload`.
The command keeps `payload_ref=agent-private-input:<id>`. Its
`input_artifact_refs` include exactly one persisted
`objective_specialist_input` metadata artifact plus the objective's authorized
query/evidence/risk-policy dependencies.

The worker must:

1. validate the durable Redis envelope against the PostgreSQL command;
2. decrypt and scope-check the command-private input;
3. read the objective only through the authorized artifact reference;
4. revalidate workspace, employee, scope hash and deadline;
5. execute the matching typed handler;
6. mark the private input consumed after the command has safely completed or
   reached a terminal failure;
7. never put Query, plaintext private input or Provider payload into Redis,
   audit, SSE or retained evidence.

The existing legacy `stage08-idempotency:` typed test path remains compatible
until the isolated runtime is accepted. It is not used as the new production
input contract.

## 6. Redis Specialists and Durable Fan-in

The existing capability-specific handlers remain authoritative:

- `platform.tabular.analyse` -> `StructuredFactSetV1`
- `platform.risk.analyse` -> `RiskAssessmentSetV1`
- `platform.daily.summarise` -> `DailyBriefV1`
- `platform.action.propose` -> pending/denied controlled proposal only

Commands are delivered through the existing outbox publisher and Redis
consumer groups. PostgreSQL remains the source of truth for command status,
leases, checkpoints, artifacts and terminal state. Redis delivery alone never
proves completion.

Fan-in runs only when all required commands are terminal. It rebuilds the
ClaimGraph exclusively from validated typed artifacts and records partial
failure separately. A required Specialist failure prevents a real answer. An
optional failure may produce a safe degraded result, but it cannot pass P2/P3.

## 7. Grounded Provider Fan-in

The final fan-in replaces the deterministic-only call with:

```text
TaskSpecV2
+ authorized schema
+ ClaimGraphV1
+ typed Specialist findings
+ pending/denied Action state
+ decrypted request-local Query
-> GroundedAnswerProviderRequestV3
-> fixed z-ai/glm-5.2 profile
-> per-RenderSlot Provider calls
-> validation and render
-> GroundedComposerResultV2
```

The Provider receives only the already implemented isolated slot closures. It
cannot create facts, joins, aggregates, permissions, record versions, Action
targets or execution tickets.

Provider transport/schema/grounding/language failure returns a deterministic
safe fallback with:

```text
answer_source=deterministic_fallback
provider_result_status=<exact failure class>
```

Fallback remains a runtime availability behavior and fails every P2/P3 gate.
There is no model failover, per-Case model selection or selective retry.

The persisted result contains only safe answer text, safe citations, hashes,
Provider identity, exact failure class, latency/usage and receipt metadata. Raw
Prompt, raw Provider response and hidden fields are not persisted.

## 8. SSE Safe Contract

The existing SSE endpoint and event names remain. `AssistantQuerySafeView`
gains two optional, paired fields:

```text
answer_source: real_provider|deterministic_fallback|null
provider_result_status: completed|transport_failed|schema_failed|
                        grounding_failed|language_failed|null
```

Rules:

- Stage08 results omit both fields and remain backward compatible.
- Stage12 results require both fields.
- `real_provider` requires `completed`.
- `deterministic_fallback` forbids `completed`.
- the safe result carries at most 12 public citation ordinals and no internal
  UUID, handle, Prompt, raw response or hidden field;
- an explicit safe result event is appended before the terminal done event;
- `Last-Event-ID` replay returns the same result and never triggers another
  Provider call.

The Mini App may display the answer without UI changes. Exposing a visual
source badge is outside this wiring task.

## 9. Failure, Recovery and Idempotency

- Duplicate Agent Run admission replays the existing run and does not create a
  second command or Provider call.
- Duplicate Redis delivery replays the completed command artifact.
- A worker crash before commit leaves the command recoverable by the existing
  pending/claim path.
- A crash after Provider success but before terminal commit may repeat the
  Provider call only within the command's existing idempotent recovery budget;
  the retained attempt ledger must expose this and P3 still applies its exact
  attempt/fallback gates.
- Scope, schema or record-version drift fails before Provider invocation.
- Provider failure persists a safe fallback result; it is visible in SSE and
  fails acceptance.
- Any unauthorized write, confirmed Action or Telegram send fails the run and
  the release gate.

## 10. Security and Side-effect Boundary

The isolated runtime may create only evaluation run, command, checkpoint,
artifact, audit and pending/denied Action metadata. It must not:

- update or create business records;
- confirm an Action;
- send Telegram or call a provider write API;
- expose raw database credentials or Provider keys;
- allow a workspace outside the exact UUID allowlist;
- use Docker or Compose;
- change global Stage11 answer authority.

## 11. Verification and Acceptance

Implementation is accepted only in this order:

1. RED/GREEN settings and allowlist tests.
2. RED/GREEN SQL admission tests proving real authorized schema/query artifacts
   and zero business-record writes.
3. RED/GREEN Redis typed-command, recovery and ack-once tests with encrypted
   private input.
4. RED/GREEN Provider fan-in tests proving real-origin and fallback-visible
   paths.
5. RED/GREEN SSE result/replay tests including `answer_source`.
6. Real disposable PostgreSQL/pgvector and Redis integration tests.
7. Full backend, Mini App, production build and native asset regression.
8. New immutable native candidate, default-off activation and rollback proof.
9. Deployed representative P2 through the public FastAPI/SSE path:
   `36/36 real_provider`, fallback `0`, no unauthorized effects/writes/sends.
10. Exactly one server P3: `48 x 3`, `144/144 real_provider`, fallback `0`, all
    quality/safety gates and worst-round p95 `<=8000 ms`.
11. One bounded real Telegram inbound read-only query, followed by cleanup and
    restoration to the safe runtime profile.

No component-only result or in-memory campaign substitutes for steps 9 or 10.

## 12. Rollback

Rollback requires no database downgrade or data deletion:

1. set `STAGE12_RUNTIME_MODE=off`;
2. clear `STAGE12_RUNTIME_WORKSPACE_ALLOWLIST`;
3. restart only the native Stage09 API/worker/outbox/publisher/Specialist units;
4. verify Stage11/Stage08 handles the same non-evaluation request;
5. if code rollback is needed, atomically restore the previous source, venv and
   static pointers;
6. retain immutable run/audit evidence and the additive Stage12 tables.

## 13. Explicit Non-scope

- production-wide Stage12 activation;
- new public API endpoints;
- UI source badges or new Mini App workflow;
- business-context enrichment beyond authorized table data;
- multi-model routing or automatic Provider failover;
- new database tables unless implementation proves the existing encrypted
  private-input and typed-artifact contracts cannot satisfy this design;
- Telegram outbound delivery or any confirmed Action.
