# Stage12-B Planner V2 Evidence — 2026-07-29

## Boundary

- Base commit: `09b9d5f70895d18efe307ba952c46775cd716dd2`
- Branch: `codex/stage09-ai-conversation-sse`
- Deterministic cases: 48 observed, 0 planning errors
- Diagnostic execution: 0 Provider calls, 0 Query executions, 0 business record writes, 0 external sends
- Not included: Stage12-C Query execution, Stage12-F concrete action expansion/persistence, PostgreSQL replay, real-LLM campaign, deployment or Telegram send

## Planner metrics

| Metric | Raw | Stage12-B applicable |
| --- | ---: | ---: |
| Objective exact | `37/48` | `37/37 = 1.0`; 11 truth-review cases retained |
| Objective precision mean | `0.9791666667` | informational |
| Objective recall mean | `0.9274305556` | informational |
| Predicate exact | `46/48` | `0.9583333333` |
| Action template exact | legacy structure `37/48` | `24/24 = 1.0` action-bearing cases |

The Stage12-B action projection scores action kind, static authorized target, `query_spec_ref`, `expansion_policy`, `resolution_status`, confirmation policy and planning-time local denial. It deliberately defers query-result concrete targets, result count, data-derived fields/values, record versions, persistence and external effects.

## Objective truth review queue

| Case | Reason |
| --- | --- |
| `risk_01`, `risk_02`, `risk_05`, `risk_06` | Gold risk Objective conflicts with the confirmed semantic trigger rule |
| `draft_03` | Gold omits an explicitly requested risk explanation Objective |
| `permission_02` | Fact Objective boundary requires human review |
| `permission_03` | Outside-workspace risk Objective boundary requires human review |
| `mixed_01` | Confirmed deferred target replaces the old Gold conflict Objective |
| `mixed_02` | Fact-vs-risk-analysis boundary requires human review |
| `mixed_03` | Field-value-vs-risk-analysis boundary requires human review |
| `mixed_04` | Gold single action Objective conflicts with one ActionSlot/one action Objective |

Raw Predicate mismatches are `join_04` and `daily_03`. They remain failures in the 48-case raw metric.

## Commands

Focused Stage12-A/B plus compatibility suite:

```text
169 passed in 7.00s
```

Full backend under the documented Stage12-A non-PostgreSQL boundary:

```text
$env:STAGE06_LOCAL_DATABASE_URL=$null
$env:STAGE02_ONLINE_DATABASE_URL=$null
python -m pytest -q \
  --ignore=tests/integration/test_stage07_draft_employee_hub_postgres.py \
  --ignore=tests/integration/test_stage07_governance_write_postgres.py \
  --ignore=tests/integration/test_stage07_telegram_deep_link_delivery_postgres.py \
  --ignore=tests/integration/test_stage07_telegram_deep_link_postgres.py

1814 passed, 132 skipped in 140.97s
```

Static/repository checks:

```text
python -m compileall -q app scripts                 PASS
python -m alembic heads                            20260728_0034 (head)
git diff --check                                   PASS
Stage12 new runtime/evaluator/test secret scan       no matches
Stage12 new runtime/evaluator/test path scan         no matches
python -m ruff --version                           unavailable: No module named ruff
```

The final focused count includes eight review-driven tests covering five Important findings: ambiguity decisions are applied to the bound QueryIntent; syntactic but unauthorized source codes cannot become resolved create targets; create assignments enforce field writability; duplicate table/entity names produce constrained ambiguity; and multiple updates extract values only from their own action spans.

## Runtime identity

- One captured authorized-schema hash: `c7db4c4a65ce1f415a153e4abb2085ab46ad3b3ffc747cda1f0af6d30e1c71d6`
- The in-memory materializer creates runtime UUIDs, so this hash identifies the recorded run rather than a cross-run stable fixture ID.
- Canonical Stage12-A fixture truth remains hash-frozen separately.

## Infrastructure limits

The 132 skips retain their existing PostgreSQL/Redis/pgvector environment gates. The configured local PostgreSQL role still cannot create the `vector` extension. No PostgreSQL or real-Provider success is inferred from the passing non-PostgreSQL suite.
