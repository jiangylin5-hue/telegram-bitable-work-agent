# Stage12-E Typed Specialist and Provider V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shared tabular execution path with four typed Specialist handlers, a role-bound Provider gateway and deterministic ClaimGraph fan-in while keeping Stage11 V1 as the only user-answer authority.

**Architecture:** Stage12-E stores strict typed payloads in existing Stage06 idempotency `response_ref` owners and keeps `AgentArtifact` as validated metadata. Safe input artifact UUIDs travel in the existing sealed command envelope and durable outbox row. Capability-specific handlers consume only authorized A–D artifacts through named ports; Supervisor validates their outputs and composes one terminal safe result.

**Tech Stack:** Python 3.12+, Pydantic v2, SQLAlchemy 2.x, PostgreSQL JSONB, Redis Streams, existing Stage10 command/event runtime, `httpx`, OpenRouter-compatible chat completions, pytest.

## Current Execution Status

- Stage12-A/B/C/D are accepted local technical gates.
- Stage11 V1 remains the only production dispatch and answer authority.
- Source audit proved that tabular/risk/daily streams all call `process_agent_tabular_command()` and the current fan-in selects the last safe artifact instead of validating typed artifacts.
- Existing `AgentCommandEnvelope.input_artifact_refs`, `AgentOutboxEvent.payload_json`, `AgentArtifact` metadata and `Stage06IdempotencyRecord.response_ref` are sufficient for E without a new database table.
- Stage12-E source is `project-docs/08-implementation/STAGE_12_E_TYPED_SPECIALIST_PROVIDER_SOURCE_OF_TRUTH.md`.

## Global Constraints

- Strict TDD: every behavior change starts with a focused failing test whose failure reason is recorded.
- No migration, public API/SSE change, Mini App change, production deployment, real-workspace external Provider input, business write or Telegram send.
- Do not implement Stage12-F candidate expansion, durable proposal rows or confirmation UI.
- Tabular owns deterministic facts only; embedding/LLM may not compute identifiers, filters, joins, counts, groups, sums, permissions or action targets.
- Risk and Daily consume upstream typed artifacts and must not rescan the workspace.
- Action consumes an already-authorized candidate set and cannot expand targets or call a write tool.
- Provider calls go only through `ModelGatewayV1`; maximum two attempts inside one total deadline and maximum one validation repair.
- Checkpoints, events, logs, observations and SSE must not retain query text, prompt, field values, provider response, candidate IDs, evidence text, vectors, credentials or stack traces.
- Shadow is `off` by default, UUID allowlisted and observational. Stage11 V1 bytes and state remain authoritative.
- The full 48-case ×3 real-LLM campaign remains the final Stage12 gate; E uses a focused synthetic corpus only.
- The repository one-final-commit rule overrides generic per-task commit guidance. Do not commit during Tasks 1–8.

---

## File Map

| File | Responsibility |
| --- | --- |
| `backend/app/schemas/agent_specialist_results.py` | Strict Objective input, facts, risk, daily, candidate, proposal, claim graph, composer and Provider observation contracts |
| `backend/app/services/agent_typed_artifacts.py` | Canonical payload hash, Stage06 idempotency durable owner, `AgentArtifact` resolution and scope/version validation |
| `backend/app/services/agent_specialists_v2/base.py` | Handler protocol, restricted execution context and result wrapper |
| `backend/app/services/agent_specialists_v2/tabular.py` | Deterministic Stage12-C result to `StructuredFactSetV1` |
| `backend/app/services/agent_specialists_v2/risk.py` | Fact/risk-policy to `RiskAssessmentSetV1` |
| `backend/app/services/agent_specialists_v2/daily.py` | Fact/aggregate/risk to `DailyBriefV1` |
| `backend/app/services/agent_specialists_v2/action.py` | ActionSlot/candidate/evidence validation to non-durable `ControlledActionProposalV1` |
| `backend/app/services/agent_specialist_registry_v2.py` | Capability metadata, handler factories and readiness validation |
| `backend/app/services/agent_model_gateway.py` | Role/profile routing, deadline, semaphore, OpenRouter transport and attempt observation |
| `backend/app/services/agent_provider_validation.py` | Strict parse, semantic validation, stable error taxonomy and one repair instruction |
| `backend/app/services/agent_claim_graph.py` | Typed claim extraction, deduplication, stale/conflict and dependency status |
| `backend/app/services/agent_composer_v2.py` | Deterministic safe answer model plus optional grounded Composer rendering |
| `backend/app/workers/agent_specialist_runtime.py` | Capability-specific worker shell and handler dispatch |
| `backend/app/services/agent_orchestrator.py` | Durable input-artifact refs, repeated capability commands and Supervisor fan-in |
| `backend/app/core/config.py` | Default-off E shadow and fixed role profile settings |
| `backend/app/api/routes/agent_runs.py` | Allowlisted observation only; no V1 response mutation |
| `backend/scripts/stage12_specialist_provider_evaluation.py` | Focused synthetic end-to-end E diagnostic |

---

### Task 1: Freeze typed Specialist and fan-in contracts

**Files:**
- Create: `backend/app/schemas/agent_specialist_results.py`
- Create: `backend/tests/unit/test_agent_specialist_results.py`
- Modify: `backend/app/schemas/__init__.py`

**Interfaces:**
- Consumes: `TaskObjectiveV2`, `ActionSlotV1`, `StructuredRecord`, `StructuredGroup`, `StructuredAggregate`, `RelationPathProof`, `SourceRecordVersion`, `EvidenceBundleV2`.
- Produces: `ObjectiveSpecialistInputV1`, `StructuredFactSetV1`, `RiskAssessmentV1`, `RiskAssessmentSetV1`, `DailyBriefV1`, `AuthorizedCandidateSetV1`, `ControlledActionProposalV1`, `ClaimV1`, `ClaimGraphV1`, `ComposerResultV1`, `ProviderAttemptObservationV1` and `specialist_payload_sha256()`.

- [x] **Step 1: Write strict RED contract tests**

  Cover exact version literals, frozen/extra-forbid behavior, canonical hash mismatch, duplicate evidence/claim IDs, scope mismatch, incomplete facts used for exact aggregate claims, risk evidence not present in the fact set, Daily facts that invent aggregate values, Action proposal targets/fields outside the candidate set, deny-with-proposal, proposed-with-completion-claim, same-version conflicting ClaimGraph values and Chinese Composer output.

  Core test shape:

  ```python
  def test_action_proposal_cannot_expand_authorized_candidates() -> None:
      with pytest.raises(ValueError, match="specialist_action_candidate_invalid"):
          ControlledActionProposalV1.model_validate(
              proposal_payload(target_record_ids=(uuid4(),), candidate_set=authorized)
          )
  ```

- [x] **Step 2: Run the contract tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_agent_specialist_results.py`

  Expected: collection error because `app.schemas.agent_specialist_results` does not exist.

- [x] **Step 3: Implement canonical strict contracts**

  Use the repository strict model style:

  ```python
  class StructuredFactSetV1(_StrictFrozenModel):
      version: Literal["structured-fact-set.v1"]
      objective_id: NonEmptyStr
      records: tuple[StructuredRecord, ...]
      groups: tuple[StructuredGroup, ...]
      aggregates: tuple[StructuredAggregate, ...]
      relation_paths: tuple[RelationPathProof, ...]
      source_versions: tuple[SourceRecordVersion, ...]
      evidence_refs: tuple[NonEmptyStr, ...]
      scope_hash: Sha256Hex
      schema_hash: Sha256Hex
      complete: StrictBool
      truncated: StrictBool
      content_hash: Sha256Hex
  ```

  Hash the canonical `model_dump(mode="json", exclude={"content_hash"})`. Cross-artifact validators must compare scope, known evidence, candidate records/fields, current record versions and status/payload exclusivity.

- [x] **Step 4: Run contract and A–D schema compatibility tests**

  Run: `python -m pytest -q tests/unit/test_agent_specialist_results.py tests/unit/test_agent_task_spec_v2.py tests/unit/test_authorized_query_plan.py tests/unit/test_retrieval_v2_contracts.py`

  Expected: PASS with no A–D contract modification.

### Task 2: Add durable typed artifact ownership and handler readiness

**Files:**
- Create: `backend/app/services/agent_typed_artifacts.py`
- Create: `backend/app/services/agent_specialist_registry_v2.py`
- Create: `backend/app/services/agent_specialists_v2/__init__.py`
- Create: `backend/app/services/agent_specialists_v2/base.py`
- Modify: `backend/app/agents/agent_capability_registry.py`
- Modify: `backend/app/services/agent_event_runtime.py`
- Modify: `backend/app/services/stage06_platform.py`
- Create: `backend/tests/unit/test_agent_typed_artifacts.py`
- Create: `backend/tests/unit/test_agent_specialist_registry_v2.py`

**Interfaces:**
- Consumes: Stage06 idempotency UOW, existing `AgentArtifact`, handler factory map.
- Produces: `persist_typed_artifact()`, `read_typed_artifact()`, `SpecialistHandler`, `SpecialistExecutionContextV2`, `SpecialistHandlerResultV2`, `validate_specialist_readiness()`.

- [x] **Step 1: Write RED artifact and readiness tests**

  Assert operation is exactly `stage12.specialist-artifact.v1`; replay requires identical fingerprint/hash; scope/hash/kind/version drift fails closed; payload is read only through `stage08-idempotency:<uuid>`; missing, duplicate or version-mismatched handler factory blocks readiness; risk/daily contexts reject query/retrieval ports; only Action may receive `tool_gateway`; no handler receives session, Redis or Provider key.

- [x] **Step 2: Run tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_agent_typed_artifacts.py tests/unit/test_agent_specialist_registry_v2.py`

  Expected: collection errors for both new services.

- [x] **Step 3: Implement the existing-owner artifact repository**

  Persist a payload envelope in `Stage06IdempotencyRecord.response_ref`:

  ```json
  {
    "version": "typed-artifact-owner.v1",
    "artifact_kind": "structured_fact_set",
    "payload_version": "structured-fact-set.v1",
    "scope_hash": "sha256",
    "content_hash": "sha256",
    "payload": {}
  }
  ```

  The returned storage reference is `stage08-idempotency:<record-id>`. Add the narrow `get_idempotency_record_by_id()` method to the existing Stage06 UOW protocol/in-memory/SQLAlchemy implementations; do not expose the session. On read, require completed owner status, exact key set, artifact metadata identity, current scope hash and Pydantic payload validation before returning content.

- [x] **Step 4: Extend registry metadata and validate factories**

  Add `allowed_ports`, `required_upstream_artifact_kinds`, `max_provider_calls`, `max_input_tokens` and `failure_policy` to `AgentCapabilityDefinition`. Do not change existing capability IDs or write permissions. Register distinct factory IDs:

  ```text
  stage12.tabular.v2
  stage12.risk.v2
  stage12.daily.v2
  stage12.action.v2
  ```

  No fallback factory is legal.

- [x] **Step 5: Run focused tests and existing registry/runtime regressions**

  Run: `python -m pytest -q tests/unit/test_agent_typed_artifacts.py tests/unit/test_agent_specialist_registry_v2.py tests/unit/test_agent_orchestrator.py tests/unit/test_agent_event_runtime.py`

  Expected: PASS without migration.

### Task 3: Preserve Objective dependencies in durable command dispatch

**Files:**
- Modify: `backend/app/services/agent_orchestrator.py`
- Modify: `backend/app/services/agent_event_runtime.py`
- Modify: `backend/app/workers/agent_specialist_runtime.py`
- Modify: `backend/tests/unit/test_agent_orchestrator.py`
- Modify: `backend/tests/unit/test_agent_event_workers.py`
- Modify: `backend/tests/integration/test_agent_event_runtime_postgres.py`
- Modify: `backend/tests/integration/test_agent_event_streams_redis.py`

**Interfaces:**
- Consumes: `SpecialistCommandDispatch.input_artifact_refs`, durable outbox envelope, handler registry.
- Produces: repeated same-capability commands keyed by Objective artifact identity, recovered sealed envelopes and capability-specific handler execution.

- [x] **Step 1: Write RED command-DAG and worker-shell tests**

  Assert input artifact UUIDs are present in `AgentCommandEnvelope` and durable outbox JSON; dispatch permits two tabular commands for two Objective inputs but rejects duplicate `(capability, input_artifact_refs)`; replay compares full sealed envelopes; recovery reads the original outbox payload; terminal runs ack/cancel sibling deliveries before handler execution; handler factory is selected by capability; no code path calls `process_agent_tabular_command` for risk/daily/action.

- [x] **Step 2: Run tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_agent_orchestrator.py tests/unit/test_agent_event_workers.py`

  Expected: failures because dispatch writes empty refs, duplicate capabilities are rejected and the pool has one shared callback.

- [x] **Step 3: Implement artifact-aware dispatch without schema change**

  Extend the existing dataclass only:

  ```python
  @dataclass(frozen=True, slots=True)
  class SpecialistCommandDispatch:
      target_capability: str
      payload_ref: str
      input_artifact_refs: tuple[UUID, ...]
      required: bool = True
      command_id: UUID | None = None
  ```

  Store refs in the already-durable outbox envelope. Add an event-runtime UOW lookup by `event_id=command.id` for recovery. Preserve the existing `AgentCommand` table and `agent-command.v1` wire version.

- [x] **Step 4: Replace the shared callback with a common shell plus distinct handlers**

  `AgentSpecialistWorkerPool` must construct each consumer with the factory resolved for that capability. The common shell owns parse, durable validation, lease, transaction, retry, checkpoint, ack and failure mapping; it calls exactly one handler with restricted ports. During Tasks 3–5, capabilities whose V2 handler is not yet implemented must fail with `stage12_specialist_handler_not_ready`; they must never call the tabular compatibility handler.

- [x] **Step 5: Run unit, PostgreSQL and Redis compatibility tests**

  Run the two unit files, `tests/integration/test_agent_event_runtime_postgres.py` and `tests/integration/test_agent_event_streams_redis.py` with their existing environment gates. Record skips rather than claiming external coverage when services are absent.

### Task 4: Implement deterministic Tabular Specialist

**Files:**
- Create: `backend/app/services/agent_specialists_v2/tabular.py`
- Create: `backend/tests/unit/test_agent_tabular_specialist_v2.py`
- Modify: `backend/app/services/agent_specialist_registry_v2.py`

**Interfaces:**
- Consumes: `ObjectiveSpecialistInputV1` containing one planned tabular Objective, `StructuredQueryArtifactV1`, optional `EvidenceBundleV2` with identical scope/objective.
- Produces: `StructuredFactSetV1`; Provider calls always `0`.

- [x] **Step 1: Write RED exactness and safety tests**

  Cover records/groups/aggregates/relation paths/source versions copied exactly, stable evidence refs, complete/truncated propagation, mismatched objective/plan/scope/schema/version denial, incomplete retrieval never overriding complete C aggregates, and a fake Model Gateway that raises if called.

- [x] **Step 2: Run tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_agent_tabular_specialist_v2.py`

  Expected: collection error because the tabular V2 handler does not exist.

- [x] **Step 3: Implement the pure handler**

  The handler validates current artifact metadata, copies deterministic C outputs, attaches only authorized evidence IDs and derives `complete = not result.truncated` for facts while preserving explicit retrieval truncation separately. It performs no record scan, retrieval, LLM call or text answer generation.

- [x] **Step 4: Run Tabular plus C/D compatibility tests**

  Run the new file plus authorized query aggregate/relation tests and retrieval evidence tests. Expected: exact values and stable hashes.

### Task 5: Implement Risk, Daily and Action Specialists

**Files:**
- Create: `backend/app/services/agent_specialists_v2/risk.py`
- Create: `backend/app/services/agent_specialists_v2/daily.py`
- Create: `backend/app/services/agent_specialists_v2/action.py`
- Create: `backend/app/services/agent_risk_policy.py`
- Create: `backend/tests/unit/test_agent_risk_specialist_v2.py`
- Create: `backend/tests/unit/test_agent_daily_specialist_v2.py`
- Create: `backend/tests/unit/test_agent_action_specialist_v2.py`
- Modify: `backend/app/services/agent_specialist_registry_v2.py`

**Interfaces:**
- Risk consumes `StructuredFactSetV1 + AuthorizedRiskPolicyV1` and produces `RiskAssessmentSetV1`.
- Daily consumes facts/aggregates and optional risk results and produces `DailyBriefV1`.
- Action consumes `ActionSlotV1 + AuthorizedCandidateSetV1 + EvidenceBundleV2 + CurrentVersionProofV1` and produces `ControlledActionProposalV1` without persistence or execution.

- [x] **Step 1: Write RED tests for true specialization**

  Risk: deterministic rules run before optional explanation Provider; evidence IDs must exist; no query/retrieval port call. Daily: counts and groups must equal upstream aggregates; recommendations are labelled and never “executed”; no query/retrieval port call. Action: exact candidate/field/value/version/scope validation; ambiguity/denial is non-retryable; tool gateway raises if called; no Gold candidate input helper is imported.

- [x] **Step 2: Run tests and verify RED**

  Run all three new test files. Expected: collection errors for the handlers.

- [x] **Step 3: Implement Risk and Daily**

  `AuthorizedRiskPolicyV1` is an explicit reader result with version, permitted reason codes, severity mapping and scope hash. Risk evaluates only supplied facts. Daily builds a typed brief from supplied aggregates and assessments; an optional Provider may phrase sections but validated typed values remain authoritative.

- [x] **Step 4: Implement Action as proposal-only**

  Validate that every target and assignment belongs to `AuthorizedCandidateSetV1`, all versions are current, evidence is in scope and `confirmation_policy=required`. Output status is `proposed`, `denied` or `deferred`; it cannot persist, confirm or execute.

- [x] **Step 5: Run all Specialist and zero-side-effect tests**

  Run Tasks 1–5 focused tests and assert Provider/query/retrieval/tool/write/send counters for each handler.

### Task 6: Add Model Gateway, Provider taxonomy and bounded repair

**Files:**
- Create: `backend/app/services/agent_model_gateway.py`
- Create: `backend/app/services/agent_provider_validation.py`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/unit/test_agent_model_gateway.py`
- Create: `backend/tests/unit/test_agent_provider_validation.py`
- Modify: `backend/tests/unit/test_stage05_config.py`
- Create: `backend/scripts/stage12_provider_profile_benchmark.py`
- Create: `backend/tests/unit/test_stage12_provider_profile_benchmark.py`
- Modify: `project-docs/00-governance/TECHNICAL_DECISIONS.md` only after measured profile evidence and user confirmation

**Interfaces:**
- Consumes: role, fixed `ModelProfileV1`, strict response model, total deadline and permission-filtered prompt layers.
- Produces: validated typed payload or stable `ProviderFailureV1`; sanitized `ProviderAttemptObservationV1`.

- [x] **Step 1: Write RED gateway/validation/config tests**

  Assert business services cannot choose arbitrary model IDs; missing key/profile fails closed; deadline prevents a new attempt; timeout/429/recoverable 5xx retry at most twice; schema/semantic invalid gets one repair only; permission/ambiguity/evidence errors do not retry; exact taxonomy for HTTP/schema/semantic/language/citation; no prompt/output in observations; role semaphore caps concurrency.

- [x] **Step 2: Run tests and verify RED**

  Run the three new unit files plus `test_stage05_config.py`. Expected: missing modules/settings.

- [x] **Step 3: Implement gateway and validation pipeline**

  Validation order is fixed:

  ```text
  HTTP/usage -> JSON parse -> Pydantic schema -> enum normalization
  -> citation/evidence -> candidate/permission -> field type
  -> forbidden completion claim -> zh-Hans language
  ```

  Repair input contains only schema, objective, validation path and previous bounded output; it never adds evidence.

- [x] **Step 4: Implement and unit-test the focused profile benchmark**

  Use synthetic `EvidenceBundleV2` and expected typed outputs for risk, daily and composer roles. Report actual provider/model/profile, pass counts, schema/semantic/citation/language failures, attempts, latency and token usage; never report prompt, field values or provider response.

- [x] **Step 5: Run real synthetic-only Provider benchmark and pause on model change**

  Load the ignored local env key transiently. Compare the Stage11 baseline profile with only architecture-approved candidates. If a different role profile wins, write a measured TDR and pause for user confirmation before binding it. A failed/partial call is recorded, never relabelled deterministic success.

### Task 7: Implement ClaimGraph and Supervisor Composer fan-in

**Files:**
- Create: `backend/app/services/agent_claim_graph.py`
- Create: `backend/app/services/agent_composer_v2.py`
- Modify: `backend/app/services/agent_orchestrator.py`
- Create: `backend/tests/unit/test_agent_claim_graph.py`
- Create: `backend/tests/unit/test_agent_composer_v2.py`
- Modify: `backend/tests/unit/test_agent_coordination_runtime.py`

**Interfaces:**
- Consumes: TaskSpec dependency DAG, completed/failed Objective commands, validated typed artifacts and current scope/data versions.
- Produces: `ClaimGraphV1`, per-Objective/per-Action status and one `ComposerResultV1` safe terminal artifact.

- [x] **Step 1: Write RED fan-in tests**

  Cover duplicate claim merge, older-version stale marking, same-version conflict, required dependency blocking, optional risk/daily failure preserving facts, deadline degradation, action denial on conflicted claim, Provider composer adding unsupported claim, one terminal event, idempotent replay and terminal sibling cancellation.

- [x] **Step 2: Run tests and verify RED**

  Run the three focused files. Expected: missing ClaimGraph/Composer services and old “last artifact wins” assertions.

- [x] **Step 3: Implement deterministic ClaimGraph and status resolution**

  Key factual claims by `(subject_ref, predicate, canonical_value)`. Merge objective/evidence ownership; compare source versions before conflict; never choose a same-version winner. Resolve `completed`, `proposed`, `denied` and `degraded` from the dependency DAG before rendering.

- [x] **Step 4: Implement grounded Composer and terminal transition**

  Build a deterministic Chinese safe result first. Optional Composer Provider may improve phrasing, but every rendered factual claim and citation must map to ClaimGraph nodes; otherwise return the deterministic result with `provider_semantic_invalid`. Supervisor alone persists the final artifact and emits one `run.completed`, `run.degraded` or `run.failed` event.

- [x] **Step 5: Run fan-in, checkpoint and SSE compatibility tests**

  Run new tests plus existing coordination, runtime and API SSE projection tests. Public event shapes must remain unchanged.

### Task 8: Add default-off E shadow, focused diagnostic and local acceptance

**Files:**
- Create: `backend/app/services/agent_specialist_shadow_v2.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/routes/agent_runs.py`
- Create: `backend/tests/unit/test_agent_specialist_shadow_v2.py`
- Create: `backend/scripts/stage12_specialist_provider_evaluation.py`
- Create: `backend/tests/unit/test_stage12_specialist_provider_evaluation.py`
- Create: `project-docs/08-implementation/STAGE_12_E_TYPED_SPECIALIST_PROVIDER_ACCEPTANCE.md`
- Create: `project-docs/08-implementation/evidence/stage12-e-typed-specialist-provider-2026-07-30.json`
- Create: `project-docs/08-implementation/evidence/stage12-e-typed-specialist-provider-2026-07-30.md`
- Modify: Stage12 indexes, acceptance contract, governance truth, `AGENTS.md` and `HANDOFF.md`

**Interfaces:**
- Consumes: injected authorized A–D artifacts for allowlisted synthetic/isolated workspaces and V1 terminal observation.
- Produces: sanitized handler/provider/fan-in comparison metrics; never changes V1 response or state.

- [x] **Step 1: Write RED config/shadow/evaluation tests**

  Assert `TYPED_SPECIALISTS_V2_MODE=off|shadow`, default off, empty UUID allowlist, missing profile/key fail closed, no handler invocation outside gate, Provider failure isolation, no query/evidence/value/candidate/prompt in observations, identical HTTP/SSE/V1 dispatch bytes, action/write/send counters zero.

- [x] **Step 2: Implement shadow and focused diagnostic**

  The diagnostic materializes only the frozen synthetic A–D artifacts, executes tabular/risk/daily/action plus ClaimGraph/Composer, and reports contract exactness, evidence validity, partial-failure behavior, error taxonomy, Chinese answer grounding, latency, Provider attempts and zero-side-effect counters.

- [x] **Step 3: Run focused and infrastructure verification**

  Run the E focused tests, A–D compatibility tests, real local PostgreSQL event/artifact integration and Redis worker integration when configured. Then run unit/API and full backend with only the documented historical four-file PostgreSQL exclusion if still necessary.

- [x] **Step 4: Run structural/security checks**

  Run `python -m compileall -q app scripts`, `python -m alembic heads`, Black check, `git diff --check`, report JSON/hash validation, credential scan and changed/new-file developer-path scan. Run Ruff only if installed and report unavailable otherwise.

- [x] **Step 5: Write acceptance and synchronize truth documents**

  Report changed files, behavior, exact verification, skipped tests, remaining risks and cleanup. State explicitly whether a real Provider profile was confirmed and that Stage11 V1 still owns production answers. Do not declare E accepted if any capability still falls back to tabular, if typed payload recovery is not durable, or if the Composer can add unsupported facts.

## Self-Review Result

- Spec coverage: architecture sections 10.1–10.8 and 11.1–11.7 map to Tasks 1–8; all four handlers, restricted ports, registry readiness, parallel Objective commands, typed fan-in, Provider roles, taxonomy, retry/repair, token/deadline control and shadow gates have owners.
- Persistence boundary: the plan uses the confirmed existing-owner artifact pattern and existing sealed outbox envelope. It adds no database table, migration or public contract. Any discovered need for one is a stop-and-confirm condition.
- Placeholder scan: tasks identify concrete files, interfaces, RED failure reasons, implementations and commands; no unspecified error-handling or generic “add tests” step remains.
- Type consistency: `ObjectiveSpecialistInputV1`, four Specialist result types, `AuthorizedCandidateSetV1`, `ClaimGraphV1`, `ComposerResultV1`, `ModelProfileV1` and `ProviderAttemptObservationV1` are introduced once and consumed under the same names.
- Stage boundary: Action expansion/persistence/confirmation, API/SSE UI changes, production activation and the 48-case ×3 campaign remain outside E.

## Execution Handoff

The user previously confirmed inline execution. Execute Tasks 1–8 in this session with `superpowers:executing-plans`, beginning at Task 1 RED tests. Pause only for a measured model-profile change, a required migration/public contract change, or another deviation from the confirmed Stage12 architecture.
