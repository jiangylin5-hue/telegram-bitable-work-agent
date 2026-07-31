# Stage12 Task 7 Isolated A–F Evidence

## Status

- Status: `implemented-local`
- Scope: Task 7 isolated raw-Query execution, sanitized observability, atomic artifacts and non-destructive PostgreSQL evidence
- Production boundary: no deployment, activation, production migration, confirmed Action, business write, notification delivery or Telegram send

## What Changed

- Execution input is restricted to raw `query`, `round_id` and isolated runtime context with an opaque execution ID.
- The isolated path executes Planner V2, authorized Query, Retrieval applicability, typed Tabular facts, ClaimGraph/Composer and disposable Action admission.
- Every stage emits input/output hashes, item count, applicability/status, safe error code and latency.
- Blind Action admission now resolves Planner-authorized `record_codes` without an injected API target.
- Authorized Query snapshot revalidation preserves the Stage12 field-policy V2 requirement before and after execution.
- Grouped aggregate identity is `(aggregate_id, group_key)`; overlapping facts from multiple QueryIntents merge provenance and remain unique.
- The CLI writes sanitized `round-XX.json`, `aggregate.json` and `aggregate.md` through same-directory atomic replacement and removes temporary files in `finally`.
- The former PostgreSQL test no longer drops or recreates `public`; it creates a unique schema inside a transaction and rolls the schema and all rows back.

## Verification

- Task 7 focused slice:
  - `python -m pytest tests/unit/test_stage12_isolated_af_runner.py tests/unit/test_stage12_real_quality_report.py tests/unit/test_stage12_action_admission.py tests/unit/test_authorized_table_query.py tests/unit/test_agent_specialist_results.py tests/unit/test_agent_tabular_specialist_v2.py tests/unit/test_agent_task_planner_v2.py tests/unit/test_agent_event_runtime_migration.py -q`
  - Result: `102 passed in 6.08s`
- Full backend unit/API regression:
  - `python -m pytest tests/unit tests/api -q`
  - Result: `2071 passed in 126.15s`
- Local disposable PostgreSQL:
  - Database: `ads_agent_stage12_test`
  - Upgraded locally from `0035` to project head `20260730_0039` before evidence execution.
  - `python -m pytest tests/integration/test_agent_event_runtime_postgres.py -q`
  - Result: `1 passed in 2.38s`
  - Post-check: `public.alembic_version=20260730_0039`; schemas matching `stage12_runtime_%` = `0`.
- Atomic deterministic campaign:
  - `python -m scripts.stage12_isolated_af_runner --output-dir ../project-docs/08-implementation/evidence/stage12-task7-isolated-af-2026-07-30 --rounds 1`
  - Result: `48/48 completed`; failures `0`; confirmed actions `0`; production writes `0`; Telegram sends `0`.
  - Retained sanitized artifacts: `stage12-task7-isolated-af-2026-07-30/round-01.json`, `aggregate.json`, `aggregate.md`.

## Skipped Tests

- Real Redis duplicate delivery/crash/pending-claim/ack evidence is Task 8 and was not run here.
- Human Gold approval and the exact three-round real-Provider campaign are Task 9 and were not run here.
- Full Mini App/build and all PostgreSQL/pgvector suites remain Task 10 full-regression work.
- No production or real-workspace execution was attempted.

## Remaining Risks

- The Task 7 Composer is deterministic and validates integration/safety, not real-Provider Chinese answer quality.
- Structured Query Cases mark Retrieval as not applicable; Retrieval V2 candidate quality still relies on Task 5 evidence until the final campaign exercises the required retrieval subset.
- Redis durability remains unaccepted until Task 8.
- Stage12 remains default-off/local-only; Stage11/r76 remains production authority.

## Temporary Cleanup

- Atomic `.tmp` report files: none remain.
- PostgreSQL temporary schemas: none remain.
- In-memory fixtures and executor observation caches are cleared after each campaign.
- Sanitized round/aggregate reports are intentionally retained as acceptance evidence.
