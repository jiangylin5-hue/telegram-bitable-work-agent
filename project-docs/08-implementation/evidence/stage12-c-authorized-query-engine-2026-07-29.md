# Stage12-C Authorized Query Engine Evidence

## Result

Stage12-C passed its local technical gate on 2026-07-29. The bounded structured-query diagnostic is `46/46 exact`; this is a Query/Join/Aggregate result, not a claim about current production answer quality.

## Verification Matrix

| Verification | Result |
| --- | --- |
| Bounded C diagnostic | 48 raw, 46 applicable, 46 exact |
| Join Gold | 8/8 exact |
| Aggregates | 11/11 exact |
| Sorts | 2/2 exact |
| Safety | 48/48 |
| Focused A/B/C | 288 passed in 12.08s |
| Real local PostgreSQL C test | 1 passed in 3.85s |
| Full backend under documented boundary | 1928 passed, 133 skipped in 142.57s |
| Compile | passed |
| Alembic | one head: 20260728_0034 |
| Diff check | passed |
| Added credential/developer path scan | zero hits |
| Ruff | unavailable; no lint result claimed |

## Boundaries

- Provider calls: 0
- Action expansions: 0
- Business writes after fixture setup: 0
- External sends: 0
- Production deploy: not run
- Public HTTP/SSE contract: unchanged
- Stage11 V1 dispatch: unchanged and authoritative

## PostgreSQL

The authorized local PostgreSQL instance retained `pgvector 0.8.3` and Alembic head `20260728_0034`. The C integration uses a transaction rollback and verifies JSONB fields, forward/reverse links, view and field scope, cross-workspace refusal, replay hashes and source-version change. It retained no fixture business records.

## Evaluation Fixture Consistency

`work_items.risk_level` was corrected from `text` to `single_select` because the frozen sort truth already required the ordered domain `high`, `medium`, `low`. Generated truth and audit hashes were refreshed; record-result truth was unchanged. The new source fixture hash is `eac654ca303bd9438515aceffd87204de8f8f9e64caab1e384ffa4f47dee4252`. Human Gold sign-off remains pending.

## Disclosed Non-C Gaps

The latest Planner-only metric remains above its stage gate but is not perfect: Predicate exact is `44/48`, with raw differences in `join_04`, `daily_03`, `mixed_02` and `mixed_04`. Objective has `11` truth-review-required rows. These differences remain visible and are not counted as C Query execution failures.

Stage12-D/E/F, large real-LLM evaluation, production activation, deployment and Telegram sends were not performed.
