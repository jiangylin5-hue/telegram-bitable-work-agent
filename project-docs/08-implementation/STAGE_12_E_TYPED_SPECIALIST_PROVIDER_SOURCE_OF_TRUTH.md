# Stage12-E Typed Specialist / Provider V2 Source of Truth

## Status

- Document status: implementation audit reopened; not accepted and production activation remains closed
- Stage: Stage12-E Typed Specialist, Provider V2 and Supervisor fan-in
- Date: 2026-07-30
- Runtime authority: Stage11 V1 remains the only dispatch and user-answer authority until a separate activation gate
- Deployment status: not authorized
- Parent architecture: `project-docs/02-architecture/stage12-quality-v2/05_SPECIALISTS_PROVIDERS_AND_MODELS.md`
- Code-level plan: `docs/superpowers/plans/2026-07-30-stage12-e-typed-specialist-provider-v2.md`
- Audit correction: `STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md` proves risk/daily are unavailable in the real worker, the cited PostgreSQL test is not typed E fan-in, ClaimGraph trusts arbitrary values and Composer accepts unsupported prose

## 1. Goal

Stage12-E replaces the current “different stream names, same tabular worker” implementation with four typed Specialist handlers and a deterministic Supervisor fan-in. Providers receive only versioned authorized artifacts, never raw workspace scans or flat unbounded chunks.

The stage is complete only when:

1. `platform.tabular.analyse`, `platform.risk.analyse`, `platform.daily.summarise` and `platform.action.propose` resolve to different registered handler factories;
2. Tabular consumes Stage12-C structured query artifacts and emits `StructuredFactSetV1` without an LLM;
3. Risk consumes facts plus an authorized risk policy and emits `RiskAssessmentSetV1` without rescanning the workspace;
4. Daily consumes deterministic facts/aggregates and risk assessments, and does not recount records;
5. Action consumes `ActionSlotV1 + AuthorizedCandidateSetV1 + EvidenceBundleV2 + current versions`, never expands candidates and never writes;
6. all model calls go through a role-bound `ModelGatewayV1`, strict validation and bounded repair;
7. Supervisor validates typed artifacts, constructs a ClaimGraph, handles stale/conflicting/partial results, and emits one safe terminal result;
8. default-off shadow and focused synthetic diagnostics prove the new chain without changing Stage11 V1 answer bytes, actions, records or sends.

## 2. Existing-Code Audit

The current implementation confirms the Stage12 problem statement:

- `backend/app/workers/agent_specialist_runtime.py` creates three capability-specific Redis consumers but injects the same `process` callback into all of them.
- `main()` routes every capability to `process_agent_tabular_command()`.
- `process_agent_tabular_command()` rebuilds the same Stage08 `AssistantQueryRequest` and executes the same `complete_assistant_query()` graph for tabular, risk and daily.
- `agent_capability_registry.py` gives risk and daily different labels/tools, but both still use `execution_skill_id=platform-tabular-analysis` and no handler-factory readiness check exists.
- `execute_read_only_specialist()` writes only artifact metadata and makes the last completed artifact the run result; it does not read typed payloads, validate upstream kinds or build a ClaimGraph.
- `AgentCommandEnvelope.input_artifact_refs` exists, but current dispatch always writes an empty tuple. The sealed envelope is already durably retained in PostgreSQL outbox rows.
- `agent_artifacts` intentionally stores metadata only. Existing Stage06 idempotency records own durable JSON `response_ref` payloads and are already referenced by `stage08-idempotency:<uuid>`.

## 3. Locked Architecture

```text
TaskSpecV2
+ AuthorizedQueryPlanV1 / StructuredQueryResultV1
+ EvidenceBundleV2
-> ObjectiveExecutionInputV1 artifacts
-> capability-specific sealed commands
-> independent typed handlers
   -> StructuredFactSetV1
   -> RiskAssessmentSetV1
   -> DailyBriefV1
   -> ControlledActionProposalV1
-> validated artifact metadata + durable typed payload owner
-> ClaimGraphV1
-> ComposerResultV1
-> one safe terminal result
```

Stage12-E reuses existing durable structures instead of adding a new blob table:

- strict typed payload JSON is stored in a dedicated `Stage06IdempotencyRecord.response_ref` owned by operation `stage12.specialist-artifact.v1`;
- `AgentArtifact.storage_ref` remains `stage08-idempotency:<record-id>`;
- `AgentArtifact` retains content hash, scope hash, kind and validation status;
- `AgentCommandEnvelope.input_artifact_refs` contains only safe artifact UUIDs and remains durable in `agent_outbox_events.payload_json`;
- worker recovery reloads the sealed envelope through the durable outbox record, never reconstructing dependency refs from Redis memory.

No new database table or public API/SSE field is required by this Stage12-E plan. If implementation proves that existing durable owners cannot preserve typed payload integrity or recovery, work must pause before proposing a migration.

## 4. Contract Boundary

New internal contracts are versioned and strict:

- `objective-specialist-input.v1`
- `structured-fact-set.v1`
- `risk-assessment-set.v1`
- `daily-brief.v1`
- `authorized-candidate-set.v1`
- `controlled-action-proposal.v1`
- `claim-graph.v1`
- `composer-result.v1`
- `model-profile.v1`
- `provider-attempt.v1`

Every typed artifact carries:

- `objective_id` or explicit run-level ownership;
- `scope_hash`;
- `schema_hash` and/or source version proof when applicable;
- stable evidence references;
- `content_hash` computed from canonical JSON excluding the hash field;
- completeness/truncation or status semantics appropriate to the artifact.

Provider-facing payloads may contain authorized values needed for the assigned objective, but provider observations, events, checkpoints, logs and SSE may contain only stable classes, counts, latency, usage and hashes.

## 5. Handler Boundary

All handlers implement one protocol:

```python
class SpecialistHandler(Protocol):
    capability_id: str
    input_schema_version: str
    output_schema_version: str

    def execute(
        self,
        command: AuthorizedSpecialistCommandV2,
        context: SpecialistExecutionContextV2,
    ) -> SpecialistHandlerResultV2: ...
```

`SpecialistExecutionContextV2` exposes only named ports: `artifact_reader`, `authorized_query_gateway`, `risk_policy_reader`, `model_gateway`, `clock`, `metrics`, and `tool_gateway` for the Action handler only. It must not expose a SQLAlchemy session, raw repository, Redis client, provider key or arbitrary callable map.

Registry readiness validates one factory per capability, exact input/output versions, allowed ports, required upstream kinds, Provider-call limit, token budget and failure policy. Missing or mismatched factories fail worker readiness; no capability may fall back to tabular.

## 6. Provider Boundary

All Stage12-E model calls use `ModelGatewayV1` and a fixed role-to-profile mapping. The gateway owns Provider URL/key access, total deadline, per-role semaphore, attempt count, timeout, usage observation and stable error classification.

Allowed terminal error classes are:

```text
provider_timeout
provider_rate_limited
provider_quota_exhausted
provider_http_error
provider_schema_invalid
provider_semantic_invalid
provider_language_invalid
provider_citation_invalid
insufficient_evidence
ambiguous_target
action_not_allowed
field_not_allowed
deadline_exhausted
```

Only timeout, 429 and recoverable 5xx may retry within the total deadline, with at most two Provider attempts. Schema/semantic invalid may receive one repair attempt containing only the original schema, objective, validation path and prior bounded output. Permission denial, ambiguity and insufficient evidence do not retry. Deterministic fallback must never be counted as a successful Provider invocation.

The Stage11 `google/gemini-2.5-flash` profile is retained as baseline. A focused synthetic role benchmark may compare candidate profiles, but changing the bound Stage12 role profile requires a measured Technical Decision and user confirmation.

## 7. Fan-in Boundary

Supervisor fan-in is deterministic before optional Composer rendering:

1. load terminal Objective/command state and referenced typed artifacts;
2. revalidate scope, artifact hash, schema version and data/source versions;
3. build claims keyed by `(subject_ref, predicate, canonical_value)`;
4. deduplicate identical claims and union evidence/objective ownership;
5. mark older-source claims stale;
6. mark same-version contradictions conflicted without selecting a winner;
7. deny Action proposals that depend on stale/conflicted/missing required claims;
8. preserve verified facts when an optional risk/daily/provider branch fails;
9. validate the rendered Chinese answer against the ClaimGraph;
10. emit exactly one terminal safe artifact/event.

## 8. Explicit Exclusions

Stage12-E does not:

- add `agent_objective_runs` or `agent_action_slots` tables;
- expand deferred ActionSlot candidates or persist proposals;
- execute Tool Gateway writes, record changes, notifications or Telegram sends;
- change public API/SSE contracts or Mini App UI;
- activate Retrieval V2 or Typed Specialists for production/real workspaces;
- run the full 48-case ×3 real-LLM campaign;
- deploy migration `0035` or any E code.

Those boundaries remain Stage12-F or final Stage12 acceptance work.

## 9. Acceptance Criteria

- Distinct handler readiness and no-fallback tests pass for all four capabilities.
- Tabular exact facts/aggregates match Stage12-C artifacts and perform zero Provider calls.
- Risk and Daily never invoke authorized query/retrieval ports when their required fact artifacts are supplied.
- Action never expands candidates, writes records, creates drafts or sends externally.
- Provider taxonomy, deadlines, retry, one repair, language, citation, candidate and completion-claim validation pass.
- ClaimGraph deduplication, stale/conflict handling, required/optional partial failure and one-terminal-event behavior pass.
- Redis worker duplicate delivery, pending claim, terminal sibling cancellation and checkpoint resume remain compatible.
- Focused real Provider evidence uses synthetic authorized artifacts only and reports actual provider/model/profile, attempts, latency and stable failures.
- Full backend regression, static/security checks and local PostgreSQL/Redis tests retain the documented boundaries.
- Acceptance reports changed files, verification, skipped tests, remaining risks and temporary cleanup.

## 10. Current Progress

The comprehensive audit reopened the earlier local acceptance, and architecture-correction Task 6 is now `implemented-local` on 2026-07-30. The real worker registry owns four distinct typed processors; durable outbox/input reconstruction, capability-specific typed output persistence, sealed value/evidence/version ClaimGraph checks, deterministic Composer validation and optional-last-failure convergence now have direct tests. Fresh evidence is E-focused `84 passed`, unit/API `2061 passed`, real local PostgreSQL typed Risk fan-in `1 passed`, and retained `google/gemini-2.5-flash` synthetic Provider smoke `3/3`. Stage11 remains runtime authority; Task 7 isolated A–F integration, E activation and final 48-case ×3 acceptance remain open. See `STAGE_12_E_TYPED_SPECIALIST_PROVIDER_ACCEPTANCE.md` and `evidence/stage12-task6-typed-worker-composer-2026-07-30.md`.
