# Stage12 Final Real Provider Campaign Audit

## Status

- Status: `FAIL`
- Scope: frozen 48 Human-Gold Cases, exactly three auditable real Retrieval/Composer rounds
- Human Gold: `48/48`
- Bundle hash: `1642b7ff5124f710477033b6d29c76a2328f0b57d976971723f2d9f515cb13e6`
- Production activation: unchanged; Stage11/r76 remains authoritative

## Result

All three real BGE-M3 Retrieval rounds completed with Recall@20 `1.0`, MRR@20 `0.958333`, forbidden candidates `0`, and action/write/send effects `0/0/0`.

Composer did not meet the availability gate:

| Round | Required | Unavailable | Attempts | Schema invalid | Semantic invalid | HTTP error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 48 | 34 | 84 | 57 | 13 | 0 |
| 02 | 48 | 35 | 86 | 59 | 13 | 1 |
| 03 | 48 | 34 | 83 | 54 | 15 | 0 |

`mixed_02` and `mixed_08` produced fail-closed traces in all three rounds. Consequently the core end-to-end dimensions were `46/48 = 0.958333` in each round. Unsupported claim rate remained `0`, and confirmed actions, production writes and Telegram sends remained `0`.

Total-latency P95 was `13540.5`, `14783.0`, and `15101.8 ms`; mean of round P95 values was `14475.083333 ms`. This exceeds the `8000 ms` gate.

## Audit history

An earlier real invocation completed its external calls but was rejected before report creation because the new runner compared the Retrieval stable profile ID (`stage12.openrouter-bge-m3-v1`) against the CLI alias (`openrouter-bge-m3`). It produced no acceptable bundle and is excluded from the statistics above. The validator now uses the frozen profile's stable ID and runs before Composer calls.

The accepted failed bundle is immutable evidence. No selective retry or extra round was merged into it.

## Corrections completed after the campaign

- `ComposerAnswerPlanV2` now rejects duplicate `section_kind` values before receipt rendering, preventing a schema-valid Provider plan from escaping the fallback boundary and collapsing the entire Case trace.
- Future Provider round aggregation includes isolated execution failure codes in `failure_counts` instead of retaining only Provider-attempt failures.
- Focused post-correction verification: `95 passed`.

## Bounded deterministic-section correction

The user approved the bounded deterministic-section option. It is now implemented locally:

- deterministic code owns all Objective, Claim, evidence and Action references;
- the Provider receives only sanitized section handles, kinds, status classes, ranks, connector allowlists and authorization-proof hashes;
- the Provider may return only an exact handle permutation plus allowlisted connector codes;
- server code expands validated handles back to immutable sections;
- every Provider failure preserves the complete deterministic answer and receipt;
- `mixed_02` and `mixed_08` no longer collapse under an invalid ordering response in local regression;
- public API, database schema, permissions, Action authority, Mini App, Stage11 dispatch and production activation are unchanged.

Local acceptance on the corrected boundary:

- focused affected matrix: `113 passed`;
- expanded Stage12 regression: `446 passed, 1627 deselected`;
- deterministic Human-Gold hard gate: all `48/48` Cases passed all dimensions with effects `0/0/0`;
- full backend: `2411 passed, 40 skipped` with every skip classified as an unavailable independent environment;
- disposable PostgreSQL/pgvector: `7 passed`, PostgreSQL `18.4`, pgvector `0.8.3`, Alembic current/head `20260730_0039`, temporary schemas `0`;
- formatting, compile, diff, production Gold/Case and precise secret-value checks passed;
- no new retained temporary directory, deployment, production migration, business write or Telegram send.

## Remaining real acceptance

The immutable bundle above remains the pre-correction `FAIL` baseline. Local evidence is not a claim of real Provider improvement. One new independent real `48 × 3` campaign is still required; it must keep the same Human Gold, retrieval profile, model profile, three-round accounting, hard gates and zero-effect constraints. The new result must be retained and reported honestly as `PASS` or `FAIL` without selective retries or merging.
