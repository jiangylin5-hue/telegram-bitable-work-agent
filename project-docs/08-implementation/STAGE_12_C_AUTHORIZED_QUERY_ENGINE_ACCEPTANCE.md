# Stage12-C Authorized Query Engine Acceptance

## Status

- Document status: accepted local technical gate
- Stage: Stage12-C Authorized Query Engine
- Acceptance date: 2026-07-29
- Runtime authority: Stage11 V1 remains the only dispatch authority; Planner V2 and Query Engine observation remain default-off and workspace allowlisted
- Deployment status: not deployed
- Next stage: Stage12-D Embedding/Chunk V2 planning and profile decision

## Acceptance Decision

**ACCEPTED LOCALLY.** Stage12-C now deterministically compiles and executes permission-preserving single-table and multi-table Query plans, including independent required/optional/existence paths, forward/reverse linked-record traversal, cross-table grouped aggregates, stable enum ordering, bounded provenance and versioned result hashes. The bounded C diagnostic is `46/46 exact` for all applicable structured-query cases.

This decision does not claim improved production answers yet. Provider, Retrieval V2, typed Specialist handlers, durable Action expansion, Mini App changes and deployment are outside C and remain unchanged.

## Gate Evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| C-applicable exact Query result | PASS | `46/46`, accuracy `1.00` |
| Join Gold slice | PASS | `8/8 exact` |
| Aggregate contract | PASS | `11/11 exact` |
| Stable sort contract | PASS | `2/2 exact` |
| Permission/safety | PASS | `48/48`; forbidden-record intersection is empty |
| Runtime boundary | PASS | Provider `0`, Action expansion `0`, post-fixture writes `0`, external sends `0` |
| Focused A/B/C compatibility | PASS | `288 passed in 12.08s` |
| Real local PostgreSQL C integration | PASS | `1 passed in 3.85s` |
| Full backend regression | PASS | `1928 passed, 133 skipped in 142.57s`; the same four historical PostgreSQL-only files were explicitly excluded |
| Compile/migration/diff | PASS | `compileall` passed; one Alembic head `20260728_0034`; `git diff --check` passed |
| Credential/developer-path scan | PASS | zero added-line or untracked-file hits |
| Ruff | UNAVAILABLE | module is not installed; no lint pass is claimed |

Machine-readable and narrative evidence:

- `evidence/stage12-c-authorized-query-engine-2026-07-29.json`
- `evidence/stage12-c-authorized-query-engine-2026-07-29.md`

## Implemented Scope

1. Added strict `AuthorizedQueryPlanV1`, predicate, traversal, aggregate, sort, result, provenance and hash contracts.
2. Added additive `QueryExecutionIntentV1.join_intents[]` and `AuthorizedQueryPlanV1.traversal_paths[]` after explicit user approval of the internal Join amendment.
3. Added schema-owned record identity fields so exact codes bind to the correct root table without scanning records in Planner.
4. Added authorized record/view scanning, field projection, entity resolution, linked-record traversal and scope/schema/version revalidation.
5. Added independent `inner`, `left` and `semi` traversal paths with depth, scan and edge budgets.
6. Added same-table and cross-table grouped aggregation, aggregate-local filtering, HAVING, stable sorting and contribution-bounded evidence.
7. Added lazy execution for optional context-only paths so a relation can be represented without polluting evidence with unused records.
8. Added default-off, workspace-allowlisted Query shadow observation that cannot alter V1 dispatch or HTTP/SSE output.

## Evaluation Consistency Correction

During C regression, the frozen fixture described `work_items.risk_level` as free text while its sort Gold required the enum order `high -> medium -> low`. The fixture was corrected to `single_select`, the source snapshot hash became `eac654ca303bd9438515aceffd87204de8f8f9e64caab1e384ffa4f47dee4252`, and the generated truth/audit files were regenerated. Record-result Gold was not changed by this correction. Gold remains `agent_audited_pending_human_signoff`.

The latest Planner-only disclosure remains separate from C acceptance:

- Objective: `37/37` applicable pass, with `11` truth-review-required cases.
- Predicate: `44/48` (`0.9167`); raw mismatches are `join_04`, `daily_03`, `mixed_02`, `mixed_04`.
- Action template: `24/24` applicable pass.

These Planner differences are not hidden by the C `46/46` result.

## Changed Files

The C delivery adds or updates:

- Query/TaskSpec schemas under `backend/app/schemas/`;
- Planner, compiler, validator, authorized record/relation/aggregate/executor and shadow services under `backend/app/services/`;
- bounded evaluation/materialization scripts under `backend/scripts/`;
- unit, API and PostgreSQL integration tests under `backend/tests/`;
- Stage12 architecture, plan, evidence, acceptance, governance and handoff documents.

No migration, Mini App, deployment or production configuration file was added by C.

## Skipped Tests

The full regression contains `133` existing environment-gated skips for online PostgreSQL, Redis, pgvector and other external evidence. C separately passed its authorized local PostgreSQL integration.

The historical full-suite boundary explicitly excludes:

- `tests/integration/test_stage07_draft_employee_hub_postgres.py`
- `tests/integration/test_stage07_governance_write_postgres.py`
- `tests/integration/test_stage07_telegram_deep_link_delivery_postgres.py`
- `tests/integration/test_stage07_telegram_deep_link_postgres.py`

Without that documented exclusion, the same run produced `1928 passed, 133 skipped` plus `15` setup errors caused only by the deliberately absent `STAGE06_LOCAL_DATABASE_URL`.

## Remaining Risks

1. Stage12-C is local and shadow-only; it is not connected to the production answer path.
2. Stage12-D must prove schema/record/relation indexing, Chinese semantic recall, data minimization, profile dimension and rollback.
3. Stage12-E must give each Specialist a distinct typed handler and make Provider consume structured facts.
4. Stage12-F must resolve Action candidates without Gold injection and prove persistence, confirmation, version conflict and zero-send safety.
5. Gold human sign-off and the three-round real-LLM campaign remain final Stage12 gates.

## Temporary Cleanup

- The C PostgreSQL test runs inside a rollback boundary and retained no Stage12 fixture workspace or business records.
- The installed `pgvector 0.8.3` extension and Alembic head `20260728_0034` are retained required infrastructure, not temporary artifacts.
- No temporary process, deployment, external message or generated database was retained.
- No commit was created; the repository one-final-commit rule remains active.
