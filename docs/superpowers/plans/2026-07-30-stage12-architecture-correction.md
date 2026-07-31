# Stage12 Architecture Correction Implementation Plan

## Status

- Status: Tasks 1–9, Task9B, HG-01–HG-10 and ISO-01 are `implemented-local`; deterministic release is `48/48`; full local audit is green and Human Gold remains pending
- Source: `project-docs/08-implementation/STAGE_12_ARCHITECTURE_CORRECTION_SOURCE_OF_TRUTH.md`
- Method: strict TDD, one behavioral slice at a time
- Workspace: existing isolated worktree `codex/stage09-ai-conversation-sse`
- Safety: synthetic/disposable local data only; no production activation, confirmed Action, external notification or Telegram send
- Primary acceptance: final answer quality across the full real Case campaign; component metrics diagnose causes but do not determine release on their own

## Dependency order

```text
V2.1 fact contract
-> authorized Entity Linker + relation correction
-> Stage12 field policy + blind Action
-> retrieval materialization/runtime loader
-> typed workers + safe Composer
-> isolated A–F runner/observability
-> real Redis
-> human Gold
-> 48 Case x 3 real Provider
-> full acceptance
```

## Task 1 — Documentation and contract freeze

1. Record TDR-020 and user approval.
2. Update Stage12 index, implementation index, audit and final-campaign plan.
3. Enumerate every changed public/internal contract and rollback flag.
4. Verify links and source-of-truth ordering.

Acceptance: documents agree that implementation is approved locally but integrated/production acceptance is open.

## Task 2 — Evaluation/trace V2.1

1. RED: a claim using an allowed evidence ID but a wrong canonical value must fail the Answer gate.
2. RED: result IDs and evidence IDs cannot be substituted for one another.
3. RED: a normal terminal Case with no injected fault must not fail durability because `recovered=false`.
4. Add typed fact and recovery-applicability contracts with strict validation.
5. Update scorers and trace adapters without parsing answer prose for record identity.
6. Run focused A tests and mutation checks.

Acceptance: wrong-value controlled trace fails; normal/fault recovery cases score according to declared applicability.

## Task 3 — Authorized Entity Linker and generic relations

1. RED: the runtime path for `join_01` must resolve the same authorized entity identities as evaluation without fixture injection.
2. RED: a non-`PRJ-`/`MT-` table identity must resolve using configured schema identity fields/aliases.
3. RED: hidden identity fields and cross-workspace candidates must never be emitted.
4. Implement one Entity Linker service and route evaluator/runtime through it.
5. Remove production prefix inference and fixture-specific candidate builders.
6. RED: a valid same-table relation projection must persist and traverse within cycle/budget limits.
7. Add migration `0037` to remove only the invalid same-table relation constraint; preserve all authorization/version constraints.
8. Run B/C/D focused and real PostgreSQL/pgvector tests.

Acceptance: evaluator/runtime parity is exact for the same authorized snapshot; same-table relation works without weakening cross-workspace/permission controls.

## Task 4 — Stage12 field-policy V2 and blind Action admission

1. RED: Stage12 read/Provider/proposal/confirm must reject an employee with no V2 field policy.
2. RED: readable and writable field contraction after proposal must fail closed.
3. Add versioned V2 policy parser/scope proof and apply intersections at all four boundaries.
4. Preserve V1 employee behavior outside Stage12 active/isolated execution.
5. RED: `requested_action=auto` discovers multiple ActionSlots from raw Query with no explicit action/target.
6. RED: final-case execution context rejects action/target/field/value truth hints.
7. Implement backward-compatible admission and authorized target expansion.
8. Run API, worker, persistence, SSE and Mini App focused tests.

Acceptance: blind Action resolution is independently scored; zero confirmation/write/send remains invariant.

## Task 5 — Retrieval materialization and runtime loader

**Current status (2026-07-30):** `implemented-local`. TDR-021 and TDR-022 are closed locally: reversible `0038` relation identity, effective view/whole-table retrieval scope, reversible `0039` registration, current-authority coordinator, relation synchronization, revoke-before-rebuild, stale projection/continuation rejection, new-registration bootstrap catch-up and a default-off event/workspace-filtered SQL runtime. Fresh evidence is bootstrap/runtime `12 passed`, Retrieval V2 `106 passed`, Stage12 API/action/query `124 passed`, and full Retrieval V2 disposable PostgreSQL/pgvector `3 passed`. No deployment or activation is included.

1. RED: a reference-only source-change event is consumed into only currently registered authorized projections.
2. RED: permission contraction revokes before embedding/cleanup and stale events cannot reactivate data.
3. RED: route shadow retrieves real authorized candidates instead of `source_unavailable` when data exists.
4. Implement the two-stage coordinator, outbox worker callback and authorized SQL loader.
5. Revalidate current scope, field visibility, content/source version and active profile before evidence release.
6. Run projection, hybrid, worker and real PostgreSQL/pgvector integration.

Acceptance: application path can observe Retrieval V2 candidates; no broader vector fallback or forbidden candidate appears.

## Task 6 — Typed worker/fan-in and safe Composer

**Current status (2026-07-30):** `implemented-local`. The real Redis worker registry now owns four distinct typed handler instances while retaining bounded V1 tabular/durable-action compatibility. Typed commands are reconstructed from the durable outbox, read sealed owner/input artifacts, persist capability-specific typed results, build a source-validated ClaimGraph and emit one Composer terminal result. Claim value/evidence/version drift and the controlled bankruptcy/budget hallucination fail closed. Optional-last failure now converges to one degraded terminal result. Fresh evidence: Task6/E focused `84 passed`, related worker/handler slice `46 passed`, real PostgreSQL typed Risk fan-in `1 passed`, and real synthetic Provider smoke `3/3` with zero failures. Runtime activation remains default-off; Task 7 now supplies isolated A–F integration evidence.

1. RED: real worker registry must execute distinct Tabular/Risk/Daily factories; no tabular fallback or unavailable placeholder.
2. RED: ClaimGraph rejects a claim value/evidence/version absent from sealed typed facts.
3. RED: Composer rejects unsupported factual prose even when claim/evidence IDs are valid.
4. Wire typed handlers into command execution and objective fan-in.
5. Deterministically render facts; restrict Provider composition to validated fact spans and bounded connectors.
6. Preserve partial-failure and one-terminal-result semantics.
7. Run unit, PostgreSQL persistence, worker and real synthetic Provider smoke.

Acceptance: the controlled bankruptcy/budget hallucination is rejected; real worker produces typed terminal artifacts.

## Task 7 — Isolated A–F runner and observability

**Current status (2026-07-30):** `implemented-local`. Raw Query is the only semantic execution input; all 48 deterministic Cases traverse Planner, authorized Query, retrieval applicability, typed facts, ClaimGraph/Composer and disposable Action admission with complete stage observations. The atomic CLI report records `48/48 completed`, confirmed actions/writes/sends `0/0/0`. Focused tests are `102 passed`, unit/API is `2071 passed`, and the PostgreSQL evidence uses a rolled-back unique schema while preserving head `0039` with residue `0`. Real-Provider final answer quality remains Task 9.

1. RED: execution callback receives only query, round ID and isolated runtime context.
2. RED: expected objectives/results/actions/targets/fields/values in execution input fail validation.
3. Execute Planner -> Query -> Retrieval applicability -> typed Specialists -> ClaimGraph/Composer -> disposable Action proposal.
4. Emit per-stage input/output hashes, counts, applicability, error class and latency segments.
5. Replace the shared-schema-reset PostgreSQL test with an isolated database/schema fixture and prove the project migration head survives.
6. Add atomic sanitized per-round/aggregate CLI artifacts and cleanup in `finally`.

Acceptance: all 48 deterministic Cases produce complete trace or explicit fail-closed error with zero shared-schema damage.

## Task 8 — Real Redis runtime evidence

**Current status (2026-07-30):** `implemented-local`. A disposable loopback Redis 7.4.10 container plus the production Streams worker proves duplicate suppression, crash-without-ACK, pending claim/recovery, ACK-once and required-failure sibling terminalization/drain. Real Redis integration is `3 passed`; the related runtime slice is `25 passed`; logical DB residue is `0`; the disposable container and Docker engine were stopped. Evidence is recorded in `project-docs/08-implementation/evidence/stage12-task8-real-redis-2026-07-30.md`.

1. Inspect the approved local native Redis/runtime and project dependency environment.
2. Install/start only with required system approval; do not reuse protected production resources.
3. Run duplicate delivery, consumer crash, pending claim/recovery, terminal sibling cancellation and ack-once tests.
4. Record version, connection boundary, commands, results and cleanup.

Acceptance: no Redis skip remains in the Stage12 runtime gate.

## Task 9 — Human Gold and three-round real campaign

**Current status (2026-07-31):** Task9, Task9B/HG-01–HG-10 and ISO-01 are `implemented-local`. Deterministic Planner/Query/Retrieval/Answer/final-answer/Action/Safety/Durability and complete release are `48/48`. Specialist-derived fact ownership and the existing F durable Action authority are verified. The reviewer manifest remains fixture hash `eac654ca303bd9438515aceffd87204de8f8f9e64caab1e384ffa4f47dee4252`, manifest hash `499d3a0c02651ad2472866d21880fe56182d46e84fc3b53823bbfc5afcd9fa95`, `human_approved_count=0`, with no audit-status mutation. Human Gold sign-off and real-Provider rounds remain open.

1. Generate a reviewer manifest showing query, independent fixture source, expected objectives/predicates/results/relations/aggregates/actions and source hash for all 48 Cases.
2. Obtain explicit user approval; only then write `human_approved` reviewer evidence.
3. Run exactly three real Provider rounds with synthetic Case data and frozen model/profile.
4. Stop immediately on permission/send/write/confirmation safety failure.
5. Score every final answer for factual correctness, required-result completeness, join/aggregate correctness, grounded citations, user-instruction/action satisfaction, Chinese clarity and appropriate refusal/degradation.
6. Report per-round and aggregate mean, minimum, population variance, failure rate and P95; retain component metrics only as diagnostic drill-down.

Acceptance: all literal safety and final-answer hard gates pass. A component-level pass cannot rescue a wrong, incomplete, unsupported or instruction-misaligned final answer; otherwise Stage12 remains reopened with failing Cases listed.

## Task 10 — Full regression and final acceptance

1. Run all focused A–F tests, full backend, Mini App tests/build, PostgreSQL/pgvector migration checks and real Redis checks.
2. Run formatting, compile, diff/secret scans and classify every skip/timeout.
3. Update every affected source/acceptance/evidence/index/handoff `Current Progress`.
4. Compare implementation against every row in the correction SOT and original Stage12 acceptance contract.
5. Do not activate or deploy; present the evidence and remaining risks for a separate release decision.

Acceptance: no requirement is marked complete without direct evidence; no oral completion claim.
