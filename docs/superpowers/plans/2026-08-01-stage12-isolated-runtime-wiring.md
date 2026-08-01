# Stage12 Isolated Runtime Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task by task. Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before any completion claim.

**Goal:** Wire the approved Stage12 architecture into the existing deployed Agent Run API so one exact allowlisted workspace can travel through FastAPI, bounded LangGraph admission, PostgreSQL/pgvector, durable outbox, Redis typed Specialists, ClaimGraph, the real Grounded Provider and safe replayable SSE without changing production-wide Stage11 authority.

**Architecture:** Keep the public Agent Run request and SSE endpoints unchanged. A fail-closed server-only activation selector routes only exact allowlisted workspaces into a new bounded SQL-backed LangGraph admission service. Admission persists authorized typed artifacts and one encrypted private input per command atomically, then uses the existing durable outbox and Redis worker topology. Typed fan-in invokes the fixed Grounded Provider profile, persists a safe result envelope, emits it before `done`, and replays it without another Provider call. All non-allowlisted traffic remains byte-for-byte on the existing Stage11/Stage08 path.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL JSONB/pgvector, Redis Streams, LangGraph, OpenRouter-compatible HTTP, pytest, React/Vite/TypeScript, native systemd/Nginx deployment.

## Global Constraints

- Follow the approved design in `docs/superpowers/specs/2026-08-01-stage12-isolated-runtime-wiring-design.md`; any architecture, schema, API, permission or Provider-selection change stops for user confirmation.
- Do not add a public endpoint, database migration, Docker/Compose path, global activation mode, model router, model failover, business-record write or confirmed Action.
- Do not persist raw Query, Prompt, Provider response, secret, internal UUID or hidden field in Redis, SSE, audit or retained campaign evidence.
- `SqlAlchemyStage06PlatformUnitOfWork` and real PostgreSQL are mandatory for deployed Stage12 admission. `InMemoryStage06PlatformUnitOfWork` remains unit-test/campaign-fixture infrastructure and cannot count as deployed acceptance.
- Preserve the legacy `stage08-idempotency:` typed test path until final regression. The new runtime uses `agent-private-input:<id>` plus an authorized objective artifact reference.
- Preserve Stage11/Stage08 behavior and response shape when both new Stage12 safe fields are omitted.
- Public safe answers remain within the existing 2,000-character bound. An oversized Grounded result fails closed to a visible deterministic fallback; it is never silently truncated because that would invalidate the receipt.
- Execute exactly one server P3 (`48 x 3`) only after deployed public-API/SSE P2 is fully green. Never rerun P3 merely to improve a score.
- Commit coherent completed tasks; push the implementation and immutable deployment artifacts only after their corresponding checks pass.
- Run backend pytest commands from `backend/` so the existing Python path and pytest configuration are authoritative. Run Mini App commands from `mini-app/`.

---

## Task 1: Fail-closed runtime activation contract

**Files:**

- Modify: `backend/app/core/config.py`
- Create: `backend/app/services/agent_stage12_runtime_activation.py`
- Modify: `backend/tests/unit/test_stage05_config.py`
- Create: `backend/tests/unit/test_agent_stage12_runtime_activation.py`

**Interfaces:**

```python
Stage12RuntimeMode = Literal["off", "isolated"]

@dataclass(frozen=True, slots=True)
class Stage12RuntimeProfile:
    mode: Stage12RuntimeMode
    workspace_allowlist: frozenset[UUID]

def build_stage12_runtime_profile(settings: Settings) -> Stage12RuntimeProfile: ...

def stage12_runtime_enabled(
    profile: Stage12RuntimeProfile,
    *,
    workspace_id: UUID,
) -> bool: ...
```

- Add `stage12_runtime_mode: Literal["off", "isolated"] = "off"` and `stage12_runtime_workspace_allowlist: str = ""` to `Settings` with `STAGE12_RUNTIME_*` aliases.
- `off` plus any allowlist is invalid. `isolated` plus an empty/invalid UUID list is invalid. Duplicates normalize to one UUID; wildcard-like tokens are invalid.
- `isolated` validates existing Agent Event Runtime, Redis publisher/typed worker, AES-GCM private-input key, SQL/PostgreSQL, retrieval and fixed Grounded Provider prerequisites. It must reject shadow-only or missing-key configurations before serving a request.

**Steps:**

- [ ] Add RED tests for default-off, off-with-list rejection, isolated-empty rejection, invalid/wildcard UUID rejection, prerequisite rejection, exact member true and non-member false.
- [ ] From `backend/`, run `python -m pytest -q tests/unit/test_stage05_config.py tests/unit/test_agent_stage12_runtime_activation.py`; verify the new tests fail for missing settings/service.
- [ ] Implement the minimal settings fields, profile builder and pure selector.
- [ ] Rerun the focused tests and verify all pass.
- [ ] From `backend/`, run `python -m pytest -q tests/unit/test_stage05_config.py tests/unit/test_agent_stage12_runtime_activation.py tests/unit/test_stage12_grounded_answer_preflight.py` to prove existing Stage12 preflight compatibility.
- [ ] Commit: `feat(stage12): add isolated runtime activation contract`.

## Task 2: Runtime admission contracts and typed artifact ownership

**Files:**

- Modify: `backend/app/schemas/agent_specialist_results.py`
- Modify: `backend/app/services/agent_typed_artifacts.py`
- Create: `backend/app/schemas/agent_stage12_runtime.py`
- Create: `backend/app/services/agent_stage12_fixture_resolution.py`
- Create: `backend/tests/unit/test_agent_stage12_runtime_contracts.py`
- Create: `backend/tests/unit/test_agent_stage12_fixture_resolution.py`

**Interfaces:**

```python
class Stage12RuntimeAdmissionRequest(BaseModel):
    run_id: UUID
    actor_user_id: UUID
    workspace_id: UUID
    digital_employee_id: UUID
    query: str
    authorization_hash: str
    deadline_at: datetime

class Stage12ObjectiveDispatchV1(BaseModel):
    objective: ObjectiveSpecialistInputV1
    objective_artifact_ref: str
    dependency_artifact_refs: tuple[str, ...]
    private_input_ref: str

class Stage12RuntimeAdmissionResult(BaseModel):
    task_spec_ref: str
    schema_ref: str
    objective_dispatches: tuple[Stage12ObjectiveDispatchV1, ...]
    data_version_hash: str

def resolve_stage12_isolated_fixture(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    actor_user_id: UUID,
    digital_employee_id: UUID,
) -> Stage12EvaluationFixture: ...
```

- Add an explicit artifact kind/storage-owner convention for `objective_specialist_input`, `task_spec_v2`, authorized schema, structured query/evidence, ClaimGraph and final grounded result without changing the database schema.
- A command's durable `payload_ref` remains its encrypted private-input ref. `input_artifact_refs` contains exactly one objective artifact and its declared dependency refs; validate ownership, scope hash and content hash before execution.
- Fixture resolution must load the already-materialized isolated workspace by stable evaluation markers and permissions, reject zero/multiple/mismatched fixtures, and never create records during request admission.

**Steps:**

- [ ] Add RED contract tests for objective-owner/dependency separation, content-hash mismatch, duplicate owner, cross-workspace ref and plaintext-query rejection.
- [ ] Add RED fixture-resolution tests using a fake read-only UOW surface; cover exact fixture, missing fixture, ambiguous fixture and unauthorized actor/employee.
- [ ] Run both new unit files and capture the expected failures.
- [ ] Implement strict frozen models, artifact parsing/validation helpers and read-only fixture resolution.
- [ ] Rerun both unit files plus `backend/tests/unit/test_agent_typed_artifacts.py` and existing Stage12 fixture tests.
- [ ] Commit: `feat(stage12): define isolated runtime artifact contracts`.

## Task 3: SQL-backed bounded LangGraph admission

**Files:**

- Create: `backend/app/agents/stage12_runtime_admission.py`
- Create: `backend/app/services/agent_stage12_runtime_admission.py`
- Modify: `backend/app/api/routes/agent_runs.py`
- Create: `backend/tests/unit/test_agent_stage12_runtime_admission.py`
- Create: `backend/tests/integration/test_agent_stage12_runtime_postgres.py`

**Interfaces:**

```python
class Stage12AdmissionState(TypedDict):
    request: Stage12RuntimeAdmissionRequest
    fixture: Stage12EvaluationFixture | None
    schema_snapshot: AuthorizedSchemaSnapshotV1 | None
    task_spec: TaskSpecV2 | None
    query_artifacts: tuple[AgentTypedArtifactEnvelope, ...]
    objective_dispatches: tuple[Stage12ObjectiveDispatchV1, ...]

def build_stage12_admission_graph(
    dependencies: Stage12AdmissionDependencies,
) -> CompiledStateGraph: ...

def admit_stage12_runtime_run(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    *,
    request: Stage12RuntimeAdmissionRequest,
    dependencies: Stage12AdmissionDependencies,
) -> Stage12RuntimeAdmissionResult: ...
```

- Graph nodes are exactly `authorize_schema`, `plan_task`, `execute_authorized_inputs`, `persist_typed_inputs`, `dispatch_commands`.
- Reuse existing `build_authorized_schema_snapshot`, `build_authorized_entity_candidates`, `plan_task_v2`, `compile_authorized_query_plan`, `execute_authorized_query` and authorized retrieval services. Move only fixture-independent helpers out of scripts when required; application code must not import `backend/scripts/*`.
- Route selection happens after existing identity/scope validation and before legacy Stage11/Stage08 command construction. Non-allowlisted requests do not invoke the new graph. Allowlisted failures return the existing safe error form and never fall through to legacy answer authority.
- Persist run, task/schema/query/objective artifacts, one encrypted private input per command, commands, outbox events and audit in one SQL transaction. Record counts in the isolated business tables must remain unchanged.

**Steps:**

- [ ] Add RED unit tests proving node order, exact dependency injection, no script import, structured-only retrieval N/A and semantic retrieval invocation.
- [ ] Add RED route tests for non-allowlisted legacy parity, allowlisted admission, fail-closed invalid admission and idempotent replay.
- [ ] Add a PostgreSQL integration test that snapshots business-record counts, admits a real isolated run, reads persisted typed artifacts/commands/private inputs/outbox/audit, verifies ciphertext has no Query substring, then verifies unchanged business-record counts.
- [ ] Run the focused unit tests first and record RED.
- [ ] Implement the graph/service and the smallest route branch.
- [ ] Run focused unit tests to GREEN.
- [ ] Run the PostgreSQL test against a disposable real PostgreSQL/pgvector database; do not mark it passed if the environment is absent.
- [ ] From `backend/`, run `python -m pytest -q tests/api/test_agent_run_events_api.py tests/unit/test_stage10_distributed_acceptance.py tests/unit/test_stage11_complex_coordination_eval.py tests/unit/test_stage12_stage11_trace_adapter.py` to prove legacy route, authorization and coordination compatibility.
- [ ] Commit: `feat(stage12): wire sql backed langgraph admission`.

## Task 4: Encrypted typed Redis command execution

**Files:**

- Modify: `backend/app/workers/agent_specialist_runtime.py`
- Modify: `backend/app/services/agent_orchestrator.py`
- Modify: `backend/app/services/agent_private_inputs.py`
- Create: `backend/tests/unit/test_agent_stage12_typed_private_input.py`
- Modify: `backend/tests/unit/test_agent_typed_specialist_runtime.py`
- Modify: `backend/tests/integration/test_agent_event_runtime_postgres.py`
- Create: `backend/tests/integration/test_agent_stage12_typed_redis.py`

**Interfaces:**

```python
def load_stage12_objective_dispatch(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    command: AgentCommand,
    private_input: AgentPrivateInputPayload,
) -> Stage12ObjectiveDispatchV1: ...

def process_stage12_typed_specialist_command(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    envelope: AgentCommandEnvelope,
    settings: Settings,
) -> AgentCommandExecutionResult: ...
```

- Dispatch selection recognizes the Stage12 isolated run marker plus `agent-private-input:` ref; it does not infer typed mode from a user-controlled capability alone.
- Validate Redis envelope identity against the SQL command before decryption. Validate private-input AAD, workspace/employee/scope, objective owner/dependencies, deadline, lease and capability before handler execution.
- Mark the private input consumed only after a terminal command commit. Duplicate delivery returns the persisted artifact and does not rerun the handler. Crash/reclaim follows the existing pending/claim path.
- Preserve the legacy `stage08-idempotency:` path and all existing worker behavior.

**Steps:**

- [ ] Add RED tests for valid encrypted dispatch, wrong command/run/workspace/employee/scope, missing/duplicate objective owner, expired deadline, duplicate delivery and crash-before-commit recovery.
- [ ] Add a RED real Redis/PostgreSQL integration test that publishes a typed command through the existing outbox/stream, consumes it with the capability worker, and proves PostgreSQL terminal state plus one consumed private input.
- [ ] Run focused unit tests and record RED.
- [ ] Implement the isolated selector, private-input load/validation and terminal consumption ordering.
- [ ] Run focused unit tests to GREEN.
- [ ] Run real PostgreSQL/Redis integration; verify exactly-once persisted outcome even if delivery is repeated.
- [ ] Rerun existing orchestrator, private-input, publisher and all typed Specialist tests.
- [ ] Commit: `feat(stage12): execute encrypted typed redis commands`.

## Task 5: Grounded Provider fan-in and visible fallback

**Files:**

- Create: `backend/app/services/agent_stage12_grounded_fan_in.py`
- Modify: `backend/app/workers/agent_specialist_runtime.py`
- Modify: `backend/app/services/agent_orchestrator.py`
- Create: `backend/tests/unit/test_agent_stage12_grounded_fan_in.py`
- Modify: `backend/tests/unit/test_agent_typed_specialist_runtime.py`
- Create: `backend/tests/integration/test_agent_stage12_grounded_provider_runtime.py`

**Interfaces:**

```python
def compose_stage12_grounded_result(
    uow: AgentEventRuntimeUnitOfWork,
    *,
    run: AgentRun,
    command_private_input: AgentPrivateInputPayload,
    settings: Settings,
    provider: GroundedAnswerProviderAdapterV2,
) -> AgentArtifact: ...

def build_stage12_safe_fallback(
    *,
    claim_graph: ClaimGraphV1,
    status: ProviderResultStatus,
    scope_hash: str,
    data_version_hash: str,
) -> GroundedComposerResultV2: ...
```

- Rebuild ClaimGraph only from validated required/optional typed artifacts. Required failure blocks a real Provider call; optional failure may return a degraded fallback but cannot pass P2/P3.
- Build the existing `GroundedAnswerProviderRequestV3`, fixed `z-ai/glm-5.2` per-slot calls and validation pipeline. No selective retry, alternate model or per-case routing.
- Persist `GroundedComposerResultV2` and safe diagnostics only. Provider Prompt/raw response stay process-local. Reject answer length above 2,000 and persist a deterministic fallback with the exact failure status.
- Replace deterministic `compose_claim_graph()` only for isolated Stage12 runs; retain it for legacy/shadow tests.
- Append an explicit result event that references the grounded result artifact before the terminal run event. Terminal transaction owns the final artifact, event and run status atomically.

**Steps:**

- [ ] Add RED unit tests for real Provider success, transport/schema/grounding/language/oversize failures, required Specialist failure, optional degradation, raw-output non-persistence, fixed model and exactly-once fan-in.
- [ ] Run focused tests and record RED.
- [ ] Implement the isolated fan-in service and minimal worker/orchestrator branch.
- [ ] Run focused tests to GREEN, including all existing Grounded Provider contract/validation tests.
- [ ] Run one bounded integration smoke using the real configured Provider and disposable PostgreSQL/Redis; assert `answer_source=real_provider`, `provider_result_status=completed`, one retained Provider receipt and no raw Prompt/response.
- [ ] Commit: `feat(stage12): ground typed fan in with real provider`.

## Task 6: Safe SSE result, replay and frontend compatibility

**Files:**

- Modify: `backend/app/runtime/stage08_collaboration_contracts.py`
- Modify: `backend/app/schemas/agent_event_runtime.py`
- Modify: `backend/app/services/agent_sse_projection.py`
- Modify: `backend/app/api/routes/agent_runs.py`
- Modify: `mini-app/src/app/stage08-collaboration-types.ts`
- Modify: `mini-app/src/app/agent-run-events.ts`
- Modify: `mini-app/src/test/agent-run-events.test.ts`
- Modify: `backend/tests/unit/test_stage08_collaboration_contracts.py`
- Modify: `backend/tests/unit/test_agent_sse_projection.py`
- Create: `backend/tests/unit/test_agent_stage12_sse_projection.py`

**Contract:**

```python
class AssistantQuerySafeView(BaseModel):
    # existing fields unchanged
    answer_source: Literal["real_provider", "deterministic_fallback"] | None = None
    provider_result_status: ProviderResultStatus | None = None
```

- Both new fields are absent/null together or populated together. `real_provider` pairs only with `completed`; fallback forbids `completed`.
- Stage08 serialization omits both fields to preserve clients and snapshots. Stage12 projection maps the safe grounded artifact to the existing result event, then emits `done`.
- Projection exposes at most 12 citation ordinals and no internal IDs/hashes not already public. `Last-Event-ID` replay reads the persisted safe result and cannot invoke admission, Specialists or Provider.

**Steps:**

- [ ] Add RED backend tests for paired fields, invalid pairings, Stage08 omission, Stage12 real/fallback projection, result-before-done order, disconnect/reconnect replay and zero extra Provider calls.
- [ ] Add RED frontend type/parser tests for both legacy and Stage12 result payloads.
- [ ] Run focused backend/frontend tests and record RED.
- [ ] Implement the minimal contract and projection changes.
- [ ] Rerun focused backend/frontend tests to GREEN.
- [ ] Run the complete Agent Run/SSE backend suite and Mini App unit suite.
- [ ] Commit: `feat(stage12): project grounded answers through safe sse`.

## Task 7: Deployed public-path campaign and sanitized evidence

**Files:**

- Create: `backend/scripts/stage12_deployed_provider_campaign.py`
- Create: `backend/tests/unit/test_stage12_deployed_provider_campaign.py`
- Modify: `project-docs/08-implementation/STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/08_DELIVERY_TEST_AND_ACCEPTANCE.md`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class DeployedCampaignConfig:
    base_url: str
    workspace_id: UUID
    employee_id: UUID
    rounds: int
    case_ids: tuple[str, ...]
    output_dir: Path

def run_deployed_provider_campaign(config: DeployedCampaignConfig) -> DeployedCampaignReport: ...
```

- Exercise only the existing public Agent Run POST and SSE URLs with real authentication. Never import or invoke `IsolatedAFExecutor` or an in-memory UOW.
- Refuse a pre-existing output directory before any HTTP/Provider call. Evidence stores Case ID, round, status, safe hashes, timings, `answer_source`, Provider status/call count, quality/safety verdicts and aggregate statistics; it stores no raw Query, answer, citation ID, UUID, token, Prompt or response.
- Verify result-before-done, replay identity, zero duplicate Provider calls, zero business writes, zero confirmed Actions, zero unauthorized effects and zero Telegram sends.
- P2 configuration is 12 approved representative cases x 3. P3 is exactly 48 approved cases x 3 and may execute once only after P2 passes.

**Steps:**

- [ ] Add RED unit tests for public HTTP/SSE-only behavior, preflight-before-call, sanitized schema, replay, gate failure and exact P2/P3 dimensions.
- [ ] Run the unit file and record RED.
- [ ] Implement the campaign runner and safe report writer.
- [ ] Rerun the unit file plus existing Stage12 campaign/report/evaluation contract tests.
- [ ] Update both authoritative Stage12 acceptance documents to distinguish historical component P2 from the required deployed public-path P2/P3.
- [ ] Commit: `test(stage12): add deployed provider campaign`.

## Task 8: Local integration, full regression and release audit

**Files:**

- Modify only files required by observed regressions.
- Update: approved Stage12 implementation/final-quality/handoff documents with exact evidence and `Current Progress`.

**Steps:**

- [ ] Run all Stage12 unit tests and require zero unexpected failures.
- [ ] Run real disposable PostgreSQL/pgvector integration, including schema head, vector extension, SQL admission and no-business-write assertions.
- [ ] Run real Redis integration for publisher, consumer group, reclaim, duplicate delivery and fan-in.
- [ ] Run the full backend suite. Report every skip by test name and reason; do not count skips as pass.
- [ ] Run the full Mini App test suite and production build.
- [ ] Run native release layout/assets/import/manifest/offline-migration/rollback-fixture/no-symlink gates.
- [ ] Search retained artifacts for raw Query, answer, secret, internal UUID and gold-key leakage.
- [ ] Verify `git diff --check`, inspect `git status --short`, audit all changed files against this plan and remove or document temporary artifacts.
- [ ] Update docs with changed files, verification, skipped tests, remaining risks and cleanup.
- [ ] Commit: `docs(stage12): record isolated runtime local acceptance`.

## Task 9: Native deployment, deployed P2, single P3 and Telegram proof

**Files:**

- No mutable source edits on the server.
- Retain immutable sanitized evidence under the server's approved Stage12 evidence root.
- Update local Stage12 acceptance/handoff documents only after evidence is copied or hashed.

**Steps:**

- [ ] Push the fully verified branch and record the exact commit SHA.
- [ ] Build a new immutable native candidate from that SHA; run sealed pre-activation gates and verify the default server profile is `STAGE12_RUNTIME_MODE=off` with an empty allowlist.
- [ ] Snapshot PostgreSQL counts/state and create the approved recoverable backup. Record candidate, source, venv, static and migration pointers.
- [ ] Materialize or verify exactly one isolated evaluation workspace in real PostgreSQL; record only safe markers and hashes.
- [ ] Set `STAGE12_RUNTIME_MODE=isolated` and the exact evaluation workspace UUID, restart only the native API/worker/outbox/publisher/Specialist units, and verify health/readiness.
- [ ] Prove a non-allowlisted request still uses Stage11/Stage08 and an allowlisted request enters Stage12.
- [ ] Run deployed public-path P2 (`12 x 3`). Require `36/36 real_provider`, fallback `0`, result-before-done, replay identity, unauthorized effects `0`, business writes `0`, confirmed Actions `0`, Telegram sends `0`.
- [ ] Review P2 answer-quality details and worst-round latency. If any gate fails, stop before P3, restore runtime `off`, diagnose and return to the relevant RED/GREEN task.
- [ ] If and only if P2 passes, run the one permitted server P3 (`48 x 3`) exactly once. Require `144/144 real_provider`, fallback `0`, all Human Gold/quality/safety gates, and worst-round p95 `<=8000 ms`.
- [ ] Run one explicitly bounded real Telegram inbound read-only query through the allowlisted workspace. Verify the Telegram-visible answer matches the safe SSE result, no outbound broadcast/business write/confirmed Action occurs, and retained evidence is sanitized.
- [ ] Restore `STAGE12_RUNTIME_MODE=off`, clear the allowlist, restart native units and verify Stage11/Stage08 authority plus health.
- [ ] Rehearse code-pointer rollback to the previous native candidate and forward recovery without a database downgrade or data deletion.
- [ ] Clean temporary upload/extraction/test artifacts; retain only approved immutable evidence, backup and release candidate.
- [ ] Update the final Stage12 documents with exact commit/candidate/hashes, commands, counts, skipped tests, remaining risks and rollback proof.
- [ ] Commit and push the evidence-only documentation update.

## Final Acceptance Checklist

- [ ] Every implementation task has witnessed RED then GREEN evidence.
- [ ] Non-allowlisted production traffic remains on Stage11/Stage08.
- [ ] Allowlisted Stage12 traffic proves the complete deployed FastAPI -> LangGraph -> PostgreSQL/pgvector -> outbox -> Redis -> typed Specialists -> ClaimGraph -> real Provider -> SSE path.
- [ ] P2 and the single P3 use the public API/SSE path and not an in-memory runner.
- [ ] Final accepted answers come from `real_provider`; deterministic fallback count is zero.
- [ ] No unauthorized effect, business write, confirmed Action, Telegram broadcast or secret/raw-content leak occurred.
- [ ] Full backend, PostgreSQL/pgvector, Redis, Mini App, production build and native release gates have actual evidence; all skips are enumerated.
- [ ] Native rollback and safe default-off restoration are proven.
- [ ] Stage12 docs and `Current Progress` match the repository and deployed evidence exactly.
