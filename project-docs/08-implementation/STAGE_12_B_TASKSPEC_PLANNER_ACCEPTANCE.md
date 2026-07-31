# Stage12-B TaskSpec V2 / Planner Acceptance

## Status

- Stage: Stage12-B
- Decision: acceptance reopened by the 2026-07-30 comprehensive audit; component tests pass, runtime-parity gate fails
- Scope: TaskSpec V2, authorized schema binding, deterministic Planner V2, constrained ambiguity seam, record-scan-free ActionSlot templates and default-off V1/V2 shadow
- Base commit: `09b9d5f70895d18efe307ba952c46775cd716dd2`
- Date: 2026-07-29
- Superseding audit: `STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md` proves the evaluator supplies 40 fixture-derived entities while the real shadow supplies none, and production Planner logic contains `PRJ-`/`MT-` fixture prefixes

## Acceptance result

| Gate | Result | Evidence |
| --- | --- | --- |
| Strict TaskSpec / ActionSlot contracts | PASS | Static and `deferred_query_result` target invariants, DAG/reference/budget/timezone/hash validation |
| Authorized schema boundary | PASS | Snapshot uses public permission services; hidden fields are absent; entity table context only narrows authorized candidates |
| Planner record-scan boundary | PASS | Planner input contains query, authorized schema and authorized entity candidates only; no record/query executor or Gold import |
| Static Objective exact | PASS on applicable denominator | `37/37`; 11 raw-Gold conflicts are separately marked `truth_review_required` |
| Static Predicate exact | PASS | `46/48 = 0.9583333333` |
| Action template exact | PASS | `24/24`; data-dependent concrete targets are not injected from Gold |
| V1 dispatch authority | PASS | Shadow is disabled by default, UUID allowlisted and observational; API test proves V1 nodes remain authoritative |
| Safety / side effects | PASS | Diagnostic recorded 0 Provider calls, 0 Query executions, 0 business record writes and 0 external sends |
| Important review findings | PASS | Five findings were reproduced by eight RED tests, then fixed: applied ambiguity selection, authorized create source, create-field writability, duplicate table/entity ambiguity and action-local update values |
| Focused regression | PASS | `169 passed in 7.00s` |
| Full backend regression | PASS with existing infrastructure skips | `1814 passed, 132 skipped in 140.97s`; four historical PostgreSQL-only files explicitly excluded under the Stage12-A boundary |
| Static checks | PASS with unavailable lint | compileall passed; Alembic has one head `20260728_0034`; `git diff --check` passed; Stage12 new runtime/evaluator/test source secret/path scan passed; ruff is not installed |

The machine-readable evidence is [stage12-b-planner-v2-2026-07-29.json](evidence/stage12-b-planner-v2-2026-07-29.json). The readable command record is [stage12-b-planner-v2-2026-07-29.md](evidence/stage12-b-planner-v2-2026-07-29.md).

## Raw score disclosure

The same deterministic 48-case run produced the following unprojected values:

- Objective precision mean: `0.9791666667`
- Objective recall mean: `0.9274305556`
- Objective exact: `37/48`
- Predicate exact: `46/48`
- Legacy planner gate: `35/48`
- Legacy action-structure exact: `37/48`

These raw values remain in evidence. Stage12-B does not claim `48/48` Objective exact. Eleven cases require human Gold review because their Objective truth conflicts with the confirmed semantic-risk, one-ActionSlot/one-action-Objective, permission or deferred-target boundary. They are excluded only from the B-applicable Objective denominator and remain visible by case/reason.

## Confirmed deferred boundary

Stage12-B emits one logical template when an action target depends on query results:

```text
query_spec_ref
+ expansion_policy
+ resolution_status=deferred_query_result
```

Stage12-C must compute the authorized result set. Stage12-F must expand concrete candidates and revalidate target, field, value, version, count, permission, confirmation, persistence and external-effect safety. Those fields are not counted as passing in Stage12-B and remain final Stage12 release gates.

## Changed files

Runtime contracts and services:

- `backend/app/schemas/agent_task_spec_v2.py`
- `backend/app/services/agent_query_lexical.py`
- `backend/app/services/agent_schema_binding.py`
- `backend/app/services/agent_task_planner_v2.py`
- `backend/app/services/agent_task_planner_shadow.py`
- `backend/app/core/config.py`
- `backend/app/api/routes/agent_runs.py`

Evaluation and tests:

- `backend/scripts/stage12_planner_v2_evaluation.py`
- Stage12-A fixture/evaluator files retained and corrected where the public permission behavior required it
- five Stage12-B unit files plus config/API/gateway regression coverage, including the five Important review regressions

Documentation:

- Stage12 architecture package, Stage12-A/B plans, acceptance/evidence, governance truth and handoff documents

## Skipped tests

The full regression skipped 132 existing environment-gated PostgreSQL, Redis and pgvector tests. Four historical PostgreSQL-only files were explicitly excluded because they require `STAGE06_LOCAL_DATABASE_URL` without a local skip guard. The configured database role is still unable to create the `vector` extension, so no PostgreSQL replay pass is claimed.

## Remaining risks

1. Eleven Objective Gold entries still need human sign-off; raw results remain visible.
2. `join_04` and `daily_03` are the two remaining raw Predicate mismatches and require Gold semantic review.
3. Stage12-C must prove filters, Join, Aggregate, relation provenance, version and permission exactness against deterministic results.
4. Stage12-F must prove concrete Action target/field/value/persistence and external-effect gates.
5. The 48-case three-round real-LLM campaign remains deferred until the core Stage12 architecture is connected.
6. Ruff is unavailable, so no lint pass is claimed.

## Temporary cleanup

No temporary database, Provider session, Telegram resource, external artifact or business record was created. `compileall` bytecode is ignored build output. No commit, push, deployment or external send was performed.

## Next gate

The separate Stage12-C code-level plan is `docs/superpowers/plans/2026-07-29-stage12-c-authorized-query-engine.md`. No Stage12-C execution code is included in the Stage12-B diff.
