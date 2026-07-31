# Stage12 Integrated Specialist / Observability Completion Audit

## Status

- Status: `implemented-local; human-gold-complete; real-provider-release-fail`
- Date: 2026-07-31
- Scope: completion audit against the already-approved Stage12 correction packages 7–9 and the literal observability contract
- Architecture decision: ISO-01 internal evaluation trace contract approved by the user on 2026-07-31; no public API, database schema, permission semantic, model/embedding profile or production activation changes
- Production status: unchanged; Stage11/r76 remains the only production answer authority

## Audit Result

The HG-01–HG-10 deterministic result is `48/48`, but that result alone does not prove every Stage12 architecture requirement. Direct source inspection found two implementation-evidence gaps and two document-state gaps:

1. The isolated A–F runner executes `TabularSpecialistV2` for structured query artifacts, but does not execute `RiskSpecialistV2` or `DailySpecialistV2` in the same raw-Query pipeline. Action admission executes the durable F path directly and therefore does not directly prove the typed `ActionSpecialistV2` preflight contract in the integrated path.
2. `IsolatedAFRunObservationV1` records coarse per-stage hashes/counts/latency and Provider attempts, but does not expose the complete literal trace ledger from `07_SECURITY_OBSERVABILITY_AND_SLO.md`: planner/task/query identities, candidate/evidence/relation counts, token totals, objective/action status counts and scope revalidation count.
3. `docs/superpowers/plans/2026-07-30-stage12-architecture-correction.md` still contains the pre-Task9B `30/48` Task 9 state and an obsolete manifest hash.
4. `docs/superpowers/plans/2026-07-30-stage12-final-quality-campaign.md` still leaves Tasks 2–7 unchecked even though their implementation evidence exists. Task 8 Human Gold and Task 9 real Provider must remain unchecked.

These are not reasons to discard the current deterministic result. They mean integrated Specialist specialization and the full observability contract remain unproven and must be closed before final Stage12 acceptance.

## TDD Findings After Initial Correction

- RED: Risk, Daily and Action typed handler invocation counts were all zero; the trace ledger was absent; Action Specialist proposed an already-conflicted slot and threw for an unauthorized field. Result: `6 failed`.
- GREEN: Risk and Daily now execute from sealed Tabular facts in the raw-Query runner. Source audit proved integrated A–F Actions already use the F durable Action Specialist for every dispatchable action; `record.create`, `record.update` and `task.create` have direct spy evidence, while reminders without an authorized recipient fail closed before worker dispatch. The duplicate E-only non-durable Action preflight was removed from the integrated runner instead of becoming a third Action contract.
- RED/GREEN: grouped Daily aggregates reused `daily:aggregate:{aggregate_id}` and failed `DailyBriefV1` validation when the same aggregate had multiple `group_key` values. Statement identity and text now preserve `(aggregate_id, group_key)`.
- The complete approved trace/latency ledger is now emitted and covered by focused tests.
- Fresh deterministic recomputation remains `48/48` only while Risk assessments are retained as sealed Specialist artifacts and not projected as final answer claims.

The audit identified two internal contract findings; both are now closed locally:

1. `RuntimeTraceV2` now exposes distinct Specialist artifact/fact traces. ClaimGraph validates `RiskAssessmentSetV1`; Answer scoring grounds against Query facts plus validated Specialist-derived facts, while Query scoring remains Query-only.
2. The E-only `AuthorizedCandidateSetV1` / `ControlledActionProposalV1` assumes an existing target record, but F already supersedes that bounded non-durable component in integrated A–F execution. F's `DurableAuthorizedCandidateSetV1 + ActionPrivatePayloadV1 + propose_durable_action()` correctly distinguishes `target_table_ids`, existing candidates and create assignments without fake record IDs. Therefore this is an authority-selection/documentation issue, not a reason to add another contract.

## Approved Internal Contract Amendment

### ISO-01 — Specialist trace and derived-fact grounding

- Add a strict `RuntimeSpecialistTraceV1` to `RuntimeTraceV2`.
- Record typed artifact kind/version/hash/status and independently derived `RuntimeFact` values with their owning Specialist objective.
- Answer grounding uses the union of Query facts and validated Specialist-derived facts while preserving origin; Query scoring continues to use Query facts only.
- Daily statements that merely render existing aggregates/risks do not create new facts.

### ISO-02 — Resolved by existing F authority; no new contract

- Integrated A–F uses the F durable candidate, encrypted private payload and `propose_durable_action()` semantic validator.
- The runner does not call the E-only non-durable Action handler as a second preflight.
- Direct tests prove existing-record update and create/task target-table semantics; reminders with no recipient stop before dispatch as required.
- E's bounded component artifact remains for historical/component compatibility but is not cited as integrated Action authority.

The user explicitly approved closing the current gap on 2026-07-31. ISO-01 is implemented locally under this frozen boundary. ISO-02 needs no schema/API/permission decision.

## Required Correction

1. Route every applicable raw-Query objective through the existing typed handlers:
   - `fact_query` -> `TabularSpecialistV2`;
   - `risk_analysis` -> `RiskSpecialistV2`, consuming sealed structured facts and an authorized synthetic risk policy;
   - `daily_summary` -> `DailySpecialistV2`, consuming sealed structured facts and, when declared by the TaskSpec dependency graph, risk assessments;
   - action objectives -> the existing F durable Action Specialist over `DurableAuthorizedCandidateSetV1 + ActionPrivatePayloadV1`, with pre-dispatch denial preserved.
2. Preserve the current deterministic fact authority. Risk/Daily/Action handlers may consume sealed upstream artifacts but may not rescan the original Query, broaden permissions or become a second source of structured table truth.
3. Extend the isolated observation with the complete approved trace ledger and exact latency segment names. Every count must be derived from runtime artifacts, not Gold.
4. Add RED/GREEN tests proving the handler classes are actually invoked by the raw-Query runner, input artifacts are sealed, failed typed preflight fails closed, and observability fields are complete and sanitized.
5. Rerun deterministic `48/48`, Stage12-focused, full backend and affected integration gates. Regenerate reviewer artifacts only if truth-bearing runtime output changes.

## Non-Goals

- no Business Context architecture;
- no new Provider or embedding profile;
- no production migration, deployment or feature-flag activation;
- no confirmed Action, business write, notification delivery or Telegram send;
- no Human Gold status mutation and no real Provider campaign before explicit sign-off.

## Acceptance Criteria

- At least one risk Case and one daily Case prove the corresponding distinct handler executes in the same raw-Query A–F path.
- Every dispatchable action proves F durable Action Specialist validation before disposable materialization; pre-dispatch denial remains explicit and stable.
- ClaimGraph/final answer remains grounded only in sealed typed artifacts; no Specialist rereads the raw Query or database outside its declared ports.
- Each isolated run records all trace and latency fields required by `07_SECURITY_OBSERVABILITY_AND_SLO.md`.
- Deterministic complete release remains `48/48`, with confirmed actions/writes/sends `0/0/0`.
- Documentation status and hashes agree; Human Gold remains `0/48` until explicit user sign-off.

## Current Verification

Post-signoff update (2026-07-31): Human Gold is `48/48`; the real auditable `48 × 3` campaign completed with release `FAIL`. Retrieval passed all three rounds, Composer unavailable was `34/48`, `35/48`, `34/48`, and `mixed_02`/`mixed_08` failed closed in every round. Bundle hash: `1642b7ff5124f710477033b6d29c76a2328f0b57d976971723f2d9f515cb13e6`. The earlier pending-signoff evidence below is retained as the pre-signoff audit snapshot.

```text
initial integrated-handler/ledger/Action fail-closed RED
6 failed

grouped Daily aggregate identity RED
1 failed, 1 passed

ISO-01 contract/runner focused
113 passed in 8.23s

expanded Stage12/Planner
307 passed in 12.51s

fresh deterministic raw-query recomputation
Planner/Query/Retrieval/Answer/final-answer/Action/Safety/Durability = 48/48
complete release = 48/48
confirmed actions / production writes / Telegram sends = 0 / 0 / 0

full backend
2377 passed, 40 skipped in 358.94s

real local PostgreSQL/pgvector
7 passed in 7.24s
PostgreSQL 18.4 / pgvector 0.8.3
Alembic current/head 20260730_0039
temporary schemas 0

Mini App
79 files / 413 tests passed

production build
PASS / 1853 modules transformed

Black check
7 files unchanged after formatting

compileall
passed

git diff --check
passed (existing Windows LF/CRLF warnings only)
```

Production Case-ID/Gold-key scans are empty. The regenerated 48-Case manifest retains fixture hash `eac654ca303bd9438515aceffd87204de8f8f9e64caab1e384ffa4f47dee4252`, manifest hash `499d3a0c02651ad2472866d21880fe56182d46e84fc3b53823bbfc5afcd9fa95`, and `pending_explicit_human_signoff` status.

## Temporary Cleanup

- Twelve audit/pytest temporary trees created by this completion pass were emptied and removed. The pre-existing retained `stage12-task9b-20260731` marker remains unchanged.
- No database, Redis, Provider session, proposal confirmation, business write, notification or Telegram resource was created.

## 2026-07-31 Real Provider Reopen

Human Gold subsequently reached `48/48`, and the bounded deterministic-section correction fixed collapsed final answers. The real post-correction Campaign nevertheless proves a hard failure: only `24/144` cases completed the real Composer result, `120/144` used fallback, schema-invalid attempts reached `240`, Provider unavailable mean was `0.833333`, and total-latency P95 mean was `11636.716667 ms`.

The audit is therefore not green for Stage12 release. The user approved Grounded Answer Provider V2, zero-fallback real-model acceptance, Git push after P1/P2/full regression, native server candidate validation and bounded real Telegram testing. Until those direct gates pass, Stage11/r76 remains production answer authority.
