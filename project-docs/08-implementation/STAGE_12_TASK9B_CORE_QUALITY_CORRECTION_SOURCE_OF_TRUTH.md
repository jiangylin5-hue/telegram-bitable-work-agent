# Stage12 Task9B Core Quality Correction Source of Truth

## Status

- Status: `approved-implementation`
- Approved at: 2026-07-31, explicit user confirmation in-thread
- Parent stage: Stage12 architecture correction, Task9 final-answer acceptance
- Scope: Planner Objective semantics, Authorized Query result/join/aggregate semantics, ActionSlot parsing and authorized expansion
- Primary acceptance: the same frozen 48 Case set must pass the seven-dimensional final-answer hard gate without Gold entering runtime execution
- Production status: local isolated implementation only; Stage11/r76 remains production authority
- Current Progress: Task9B remains `implemented-local`; HG-01–HG-10 and Human Gold are `48/48`. The bounded deterministic-section correction removed the remaining runtime-trace collapse: the new real `48 × 3` campaign passed all returned-answer/Case gates `48/48` in every round, including `mixed_02`/`mixed_08`. Overall Stage12 release is still `FAIL` because Composer unavailable was `36/48`, `47/48`, `37/48` and total-latency P95 exceeded `8000 ms`. Current bundle `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`; effects `0/0/0`. Older pre-signoff and pre-correction counts are historical only.

## 1. Why This Correction Exists

The approved Task9 answer contract now measures the returned answer honestly. Its deterministic audit produced complete receipts and safety `48/48`, but only `30/48` final-answer hard-gate passes and `10/48` complete Case release-gate passes.

The 18 failures propagate from three upstream mechanisms:

1. Planner does not distinguish independent risk analysis from a risk phrase used only as an Action explanation, and creates one Objective per expanded action target.
2. Query projection conflates requested result identities with contextual evidence identities, and converts ungrouped aggregate `null` into the literal string `"null"`.
3. Action admission and trace projection lose resolved targets and requested-but-denied fields, and do not preserve controlled `blocked` semantics for no-send reminder requests.

This correction is not a new Stage. It is Task9B inside the already-approved Stage12 final-quality boundary.

## 2. Frozen Runtime Boundary

The execution input remains:

```text
raw Query
+ authorized schema/entity snapshot
+ runtime permission and record versions
```

Runtime code must not read:

- `case_id`;
- expected objectives, records, joins, aggregates or actions;
- Gold audit fields;
- fixture-only correction maps;
- answer-score output.

The 48 Case truth remains scorer-only. A production branch keyed by Case ID is forbidden.

## 3. Planner Semantic Contract

### 3.1 Risk Objective

Create an independent `risk_analysis` Objective when the user asks to derive, compare, rank, group, aggregate or judge risk, including cross-field discrepancy queries and risk-based ordering.

Do not create a separate `risk_analysis` Objective when:

- risk text appears only as a field value or relation label;
- the user requests a factual list of linked risk records;
- “解释风险依据” is subordinate to a concrete update proposal and can be satisfied by cited facts attached to that Action.

Restricted scope does not erase requested semantic Objectives. A query-plus-action outside scope still produces denied `restricted_request` plus the requested fact/risk/action Objectives so that the final answer can explicitly account for each instruction. An exclusively unauthorized write with no read instruction suppresses the synthetic default `fact_query` Objective.

### 3.2 Expanded Actions

One user action clause produces one logical action Objective. Expansion over multiple authorized entities produces multiple ActionSlots that reference the same Objective. Expansion must not duplicate `task_creation` or `reminder_request` Objectives.

### 3.3 Objective Graph

- every analysis/summary/action Objective depends on the factual Query Objective when one exists;
- a restricted-only action may depend on the restricted Objective instead of a fabricated fact Objective;
- conflict resolution remains independent from an allowed sibling Action;
- Objective count and ActionSlot count remain bounded by the existing maximums.

## 4. Authorized Query Semantic Contract

### 4.1 Result versus Evidence Roles

Result identity is determined from the requested projection and output contract, not from whether a record was mentioned as an entity or whether an Action also exists.

- explicitly requested identifiers and records are results;
- primary projected records are results;
- records used only to prove a relation, predicate, permission or Action target are evidence;
- the same identity cannot appear in both sets;
- linked paths may return requested endpoints from more than one table;
- Action presence must not demote an otherwise requested factual result to evidence.

### 4.2 Join Presentation

When a root entity scopes a query but the requested list is a linked target table, presentation must project the requested target records while retaining the root as evidence. Left joins must preserve zero-match roots only for aggregate truth and must not erase requested sibling records.

### 4.3 Aggregate Group Keys

Canonical JSON `null` means an ungrouped aggregate and must project as Python/JSON `null`, never the string `"null"`. String group keys remain strings; structured relation group keys retain their canonical structured value.

## 5. Action Semantic Contract

- `record.update` preserves its explicit authorized record code as the target.
- denied field requests retain the requested field key in the safe trace and receipt, but never expose or write a forbidden value.
- conflict-denied assignments retain the conflicting field key and denial reason.
- a `task.create` clause may use relation-derived Query results to bind its source work item or project; the Planner may defer this binding but must not invent an identity.
- “最高风险项” with multiple equally valid authorized candidates is denied as `ambiguous_highest_risk_target`.
- “分别/每个” expands over the complete authorized candidate set with one logical Objective.
- reminder requests with an explicit no-send instruction remain `blocked` proposals; they are not reported as successful sends or generic permission denials.
- confirmation, write and external-send counts remain zero during isolated acceptance.

## 6. Allowed Files and Non-Goals

Expected implementation files:

- `backend/app/services/agent_query_lexical.py`
- `backend/app/services/agent_task_planner_v2.py`
- `backend/app/services/authorized_query_compiler.py`
- `backend/app/services/authorized_table_query.py`
- `backend/app/services/agent_action_candidates.py`
- `backend/app/services/stage12_action_admission.py`
- `backend/scripts/stage12_isolated_af_runner.py`
- focused unit/integration tests for the same contracts

Non-goals:

- changing public API, database schema, migration head or permission model;
- changing the frozen Gold to match runtime output;
- adding a new model/provider/profile;
- prompt tuning or free-form Provider repair;
- production activation, deployment, Telegram send or confirmed Action;
- starting Human Gold or real Provider rounds before the deterministic technical gate passes.

## 7. Acceptance Criteria

1. Every production behavior change has a RED test observed before implementation.
2. No production code contains any of the 48 Case IDs or imports evaluation truth.
3. The 18 previously failing Cases are rerun through the raw-query isolated A–F path.
4. All 48 Cases pass every applicable final-answer dimension and safety gate before Human Gold starts.
5. Complete Case release-gate failures, if any, are reported separately and cannot be averaged away.
6. Stage12 unit, focused Planner/Query/Action, Black, compile and secret scans pass; unavailable tools and deferred integration suites are listed explicitly.
7. Evidence records Changed files, Verification, Skipped tests, Remaining risks and Temporary cleanup.

## 8. Post-Stage12 Business-Context Architecture Candidate

> **Scope Freeze — OUT OF STAGE12:** `BusinessContextPack`、通用业务术语/指标/SOP 上下文和泛化 Agent memory 均不属于 Stage12。禁止在 Stage12 实现、迁移、接入、隐式补齐或把它作为验收前置条件；后续必须另立阶段、另写真源并取得用户明确确认。

The user identified a separate real-quality risk on 2026-07-31: production questions may lack the business definitions needed to interpret risk, time windows, metrics, priorities, SOP and action policy. On 2026-07-31 the user explicitly confirmed that this work is outside Stage12 and must be designed separately in a later stage. It must not become a Stage12 acceptance dependency or implementation excuse.

A future, separately approved design may introduce a table-bound, versioned and permission-filtered `BusinessContextPack` containing metric definitions, risk rules, terminology/aliases, SOP, time semantics, applicable workspace/base/table scope and provenance. Embedding may discover relevant context candidates but must not calculate structured facts or silently define business rules.

Stage12 and Task9B do not implement this candidate. Adding its persistence, contract or permission semantics requires a future-stage source-of-truth, separate design document, acceptance criteria and explicit user confirmation. Stage12 must finish against its existing technical architecture and frozen quality boundary without `BusinessContextPack`.

### 8.1 Evidence discovered during Task9B

The remaining Action component failures provide concrete evidence that this candidate is not theoretical:

- task intent is structurally recognized, but several task titles remain the complete action clause instead of the business object name;
- `project_owner` is still a semantic selector in some task proposals rather than a fully resolved authorized owner identity;
- linked-record assignments may retain business codes or selector objects where the durable write path ultimately needs authorized record identities;
- the same phrase, such as “评审任务” or “风险依据”, needs table-specific naming and SOP semantics that schema metadata alone does not define.

These are not Embedding recall failures. They require a permission-filtered context contract containing terminology, entity-role rules, naming templates, state/SOP definitions and provenance. Task9B must not hide them with Case-specific title maps or Gold-derived corrections.

## 9. Current Verification Snapshot (2026-07-31)

- deterministic raw-query final-answer hard gate: `48/48`;
- deterministic safety gate: `48/48`;
- complete Case release gate: `48/48`;
- expanded Stage12/Planner unit regression: `271 passed`;
- Stage12 unit files: `185 passed`;
- real local PostgreSQL/pgvector Stage12 integration: `7 passed`;
- full backend regression: `2366 passed, 40 skipped`;
- Mini App full regression: `413 passed`; production build passed;
- confirmed/write/external-send effects: `0` in isolated acceptance;
- Black formatted the changed Python files;
- Human Gold: `48/48`;
- real Provider rounds: `0`.

Direct evidence: `evidence/stage12-task9b-core-quality-correction-2026-07-31.md`.

Applied Human Gold correction decisions are consolidated in `STAGE_12_HUMAN_GOLD_DECISION_ADDENDUM.md`. The correction approvals do not equal the separate final 48-Case Human Gold sign-off and do not authorize Provider execution.

There are no remaining deterministic release failures. The regenerated manifest remains pending explicit Human Gold sign-off; no Gold or Case ID was added to production runtime.
