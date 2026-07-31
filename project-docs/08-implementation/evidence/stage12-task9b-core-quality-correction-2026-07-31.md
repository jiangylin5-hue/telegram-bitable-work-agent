# Stage12 Task9B Core Quality Correction Evidence

## Status

- Status: `implemented-local-technical-gate`
- Scope: approved Planner Objective, Authorized Query result/join/aggregate and ActionSlot parsing/authorized expansion correction
- Production status: unchanged; Stage11/r76 remains the only production answer authority
- Human Gold: `0/48`
- Real Provider campaign: `0/3` rounds
- External effects: confirmed Action `0`, production business write `0`, Telegram/external send `0`

## Scope Freeze

`BusinessContextPack`、通用业务术语/指标/SOP 上下文和泛化 Agent memory 已明确标记为 **OUT OF STAGE12**。Task9B 没有实现其 persistence、API/schema、permission contract、retrieval injection 或 acceptance dependency；后续必须另立阶段、另写真源并取得用户确认。

## Changed Files

- `backend/app/services/agent_task_planner_v2.py`
- `backend/app/services/authorized_table_query.py`
- `backend/app/services/stage12_action_admission.py`
- `backend/scripts/stage12_isolated_af_runner.py`
- `backend/scripts/stage12_planner_v2_evaluation.py`
- `backend/scripts/stage12_query_engine_evaluation.py`
- `backend/scripts/stage12_quality_evaluation.py`
- `backend/tests/fixtures/stage12_complex_cases_v2.json`
- `backend/tests/fixtures/stage12_complex_cases_v2.audit.json`
- `backend/tests/unit/test_agent_task_planner_v2.py`
- `backend/tests/unit/test_authorized_table_query.py`
- `backend/tests/unit/test_stage12_isolated_af_runner.py`
- `backend/tests/unit/test_stage12_query_engine_evaluation.py`
- `backend/tests/unit/test_stage12_quality_answer_action_safety_scores.py`
- `backend/tests/unit/test_stage12_quality_truth_cases.py`
- `docs/superpowers/plans/2026-07-31-stage12-task9b-core-quality-correction.md`
- `project-docs/08-implementation/STAGE_12_TASK9B_CORE_QUALITY_CORRECTION_SOURCE_OF_TRUTH.md`
- `project-docs/08-implementation/STAGE_12_HUMAN_GOLD_DECISION_ADDENDUM.md`
- active Stage12 index/progress/handoff documents

## What Changed

- Planner uses clause-aware risk semantics, suppresses synthetic fact Objectives for restricted writes, preserves denied multi-intent queries and keeps expanded targets under one logical Action Objective.
- Authorized Query preserves requested result identities separately from supporting evidence, merges independent traversal branches, normalizes ungrouped aggregate keys to JSON `null` and retains deterministic relation/aggregate provenance.
- Action admission preserves explicit targets and requested denied/conflicted fields, binds authorized relation-derived create context, denies ambiguous highest-risk expansion and represents explicit no-send reminders as blocked proposals with zero send authority.
- Approved HG-01–HG-10 corrections are now applied. Denied/conflicted values are minimized, unauthorized-write retrieval is not applicable, send-capable reminders without an authorized recipient mapping are denied, stale Planner predicate/group/edge Gold is corrected only where source semantics support it, UTC Action deadlines are scored exactly, and relative-day semantics use the fixed Case clock.
- The production Planner now derives `due_date` from `request.timezone_name` rather than from the timezone attached to the caller's clock value. This closes the real API/action-admission path where an aware UTC clock previously shifted an `Asia/Shanghai` calendar deadline backward by one day; a focused UTC-clock regression test covers the production path.
- Durable create/task linked-record assignments now resolve business codes and `project_owner` selectors to authorized record UUID collections before encryption/materialization; the evaluator-only trace projects those UUIDs back to business codes.
- Outside-workspace fact/risk/task Objectives now all fail closed behind `restricted_request` instead of remaining misleadingly `planned`.
- Explicit daily/report output retains requested rows as results; pure Action target discovery remains evidence. Optional relation context no longer demotes or promotes records across these roles.
- Direct reminder targets prefer the explicitly named work item, preserve its authorized `owner_link`, and never infer Telegram recipient authority from an owner business code.
- Version-conflict trace materialization now resolves both singular `record_code` and plural `record_codes`; focused RED proved `fault_02` lost `MT-014` and its version, while GREEN preserves `target_code=MT-014`, `record_version=1` and the fail-closed `record_version_conflict` denial.
- Expanded reminder traces now project the authorized concrete owner/source pair from executed query provenance instead of retaining the Planner's deferred selector. Focused RED exposed the mismatch; GREEN covers `reminder_03`, `mixed_03` and `mixed_07` without changing blocked status, external-effect count or Gold.
- Denied Action traces now clear proposed values consistently while retaining selected fields, target provenance and denial reason. Focused RED exposed the `mixed_01` ambiguous-target value leak; GREEN preserves fail-closed semantics without changing Gold or release scoring.
- Query component evaluation and the isolated A–F runner now share the same semantic relation-path projection. A focused RED proved `mixed_07` incorrectly counted an Action-only risk evidence path as a result Join; GREEN removed the evaluator/runtime projection drift without changing Gold.
- No Case ID, Gold truth or expected score was added to production services.

## Current Generated Deterministic 48-Case Result

| Gate | Result |
| --- | ---: |
| Planner | `48/48` |
| Query | `48/48` |
| Retrieval | `48/48` |
| Answer typed-fact gate | `48/48` |
| Seven-dimensional final-answer hard gate | `48/48` |
| Action | `48/48` |
| Safety | `48/48` |
| Durability | `48/48` |
| Complete Case release gate | `48/48` |

HG-09 now projects and exactly scores the existing `ActionSlotV1.deadline_start_utc`/`deadline_end_utc` fields and removes the synthetic reminder `due_date`. HG-10 aligns every Isolated AF replan to the fixed Case clock, defines “明天之前” through the end of the next local calendar day, and makes production `due_date` projection honor the declared workspace timezone even when the runtime clock is UTC. No schema, API, permission, confirmation, persistence or send contract changed.

The regenerated fixture, audit hashes and reviewer manifest remain `agent_audited_pending_human_signoff`; no Human Gold status was self-approved.

## Verification

```text
expanded Stage12/Planner regression after production UTC-clock timezone coverage
271 passed in 11.18s

current Stage12 unit files
185 passed in 11.35s

current full backend regression
2366 passed, 40 skipped in 373.30s

current real local PostgreSQL/pgvector Stage12 integration
7 passed in 7.19s
database = stage06_smoke
PostgreSQL = 18.4
pgvector = 0.8.3
Alembic current/head = 20260730_0039
temporary schemas after tests = 0

generated deterministic raw-query diagnostic
Planner/Query/Retrieval/Answer/final-answer/Action/Safety/Durability = 48/48
complete release = 48/48
task_02/reminder_01/mixed_08 deadline_accuracy = 1.0

Black formatting + compileall
passed

current Mini App full regression
79 test files, 413 tests passed in 266.09s

current Mini App production build
passed; 1853 modules transformed

production Case-ID/Gold-key scan
NO_PRODUCTION_CASE_IDS_OR_GOLD_KEYS

credential-literal scan
only the pre-existing documented local ads_agent default in backend/app/core/config.py
no new Stage12 credential literal

all post-HG-10 final local gates rerun and passed

isolated Action/final-answer focused regression after target projection
58 passed in 7.37s

Query evaluator + isolated A–F projection regression
47 passed in 7.54s

Black check
10 files would be left unchanged

compileall
passed

production Case-ID scan
NO_PRODUCTION_CASE_IDS

credential-pattern scan
NO_CREDENTIAL_PATTERNS
```

## Skipped Tests

- 3 real Redis tests were skipped in the current full run because `STAGE10_REDIS_URL` was absent. The Python `redis` package is installed, but the current Windows identity cannot start `com.docker.service`. No permission bypass was attempted. Retained Task8 evidence still records real disposable Redis `3 passed`, DB residue `0`, container removed and Docker stopped.
- 17 Stage02 online PostgreSQL tests require `STAGE02_ONLINE_DATABASE_URL`.
- 3 Stage08 collaboration PostgreSQL tests and 17 Stage08 RAG/pgvector tests require the independent `STAGE08_RAG_DATABASE_URL`.
- These 40 skips do not include the Stage12 PostgreSQL/pgvector suite, which passed `7/7` in this run.

## Remaining Risks and Next Gate

- Human Gold remains `0/48`; the regenerated manifest cannot be self-approved by runtime code or the evaluator.
- Complete deterministic release is `48/48`; the separate regenerated manifest still needs explicit 48/48 Human Gold sign-off.
- Exactly three real Provider rounds remain blocked until explicit Human Gold sign-off.
- Stage12 is uncommitted, undeployed and inactive. Production migration, worker/UI activation, real workspace data, confirmed business writes and Telegram sends remain unauthorized.

## Temporary Cleanup

- The three generated files under `backend/.tmp/stage12-task9b-20260731` were removed after verification. The empty directory may remain because the current execution policy rejects directory deletion; it contains zero files.
- No disposable PostgreSQL schema remains.
- No Redis container or service was started in this pass.
