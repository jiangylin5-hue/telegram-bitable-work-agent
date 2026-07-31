# Stage12-D Retrieval / Embedding / Chunk V2 Acceptance

## Status

- Document status: accepted local technical gate
- Stage: Stage12-D Retrieval, Embedding and Chunk V2
- Acceptance date: 2026-07-30
- Runtime authority: Stage11 V1 remains the only dispatch authority; Retrieval V2 is `off` by default and cannot change answer, HTTP/SSE output, action candidates, records or sends
- Deployment status: not deployed or activated
- Next stage: Stage12-E Typed Specialist and Provider V2 documentation and code-level planning

## Acceptance Decision

**ACCEPTED LOCALLY.** Stage12-D now provides permission-preserving schema/record/relation projections, a fixed 1024-dimensional pgvector profile, reference-only two-stage projection outbox, versioned indexing and revoke-first lifecycle, authorization-first bounded hybrid retrieval, and fresh-authority `EvidenceBundleV2` assembly. A real OpenRouter call against the frozen synthetic-only corpus passed the focused retrieval diagnostic.

This decision does not claim improved production answers. The route-level V2 materialization seam intentionally remains unavailable, the default mode is `off`, and Stage11 V1 remains the only dispatch source. Stage12-E must make typed Specialists and Provider V2 consume `TaskSpecV2`, `StructuredQueryResultV1` and `EvidenceBundleV2` before answer quality can change; activation and deployment require a later explicit gate.

## Gate Evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Confirmed embedding profile | PASS | `stage12.openrouter-bge-m3-v1`; revision `baai/bge-m3-20251117`; dimension `1024`; L2 normalization; cosine distance; batch `64`; max tokens `8192` |
| Real focused OpenRouter diagnostic | PASS | `1/1` round completed; Recall@20 `1.0`; MRR@20 `0.9583333333`; forbidden `0`; P95 `2498.3266 ms`; Provider calls `4` |
| Explicit truncation | PASS WITH DISCLOSURE | `12/12` focused cases reported `truncated=true` because the deterministic corpus exceeds Top 20; no complete aggregate is inferred from truncated retrieval |
| Safety counters | PASS | Action expansions `0`; post-fixture record writes `0`; external sends `0` |
| Task8 and D focused tests | PASS | `91 passed in 6.56s` |
| Real local PostgreSQL C+D integration | PASS | `2 passed in 5.45s` against disposable `ads_agent_stage12_test` |
| Unit and API regression | PASS | `1906 passed in 155.27s` |
| Full backend regression | PASS with documented boundary | `2005 passed, 134 skipped in 158.48s`; the four historical PostgreSQL-only files listed below were explicitly excluded |
| Migration lifecycle | PASS | migration `0035` upgrade/downgrade/re-upgrade covered by the D PostgreSQL integration; Alembic has one head `20260729_0035` |
| Static/format/security checks | PASS | `compileall`, Black check for 12 changed D files, `git diff --check`, report JSON/hash validation, credential scan and changed/new-file developer-path scan passed |
| Ruff | UNAVAILABLE | `No module named ruff`; no Ruff pass is claimed |

Machine-readable and narrative evidence:

- `evidence/stage12-d-retrieval-embedding-2026-07-29.json`
- `evidence/stage12-d-retrieval-embedding-2026-07-29.md`
- focused report hash: `ca31249995b42a4354ddb4544a846298ffdb9dd11cc404d61e27518aeca89de5`

## RED / GREEN Evidence

1. Contracts, projection, adapters, profile benchmark, pgvector models, indexing lifecycle, hybrid retrieval, EvidenceBundle, shadow and focused evaluation were implemented task-by-task from failing tests.
2. Task7 RED produced two collection errors because `retrieval_v2_hybrid` and `retrieval_v2_evidence` did not exist; its GREEN suite is `9 passed`.
3. Task8 evaluation RED failed because `stage12_retrieval_v2_evaluation` did not exist; its GREEN unit suite is `2 passed`.
4. The first real OpenRouter focused run failed closed with `embedding_model_revision_mismatch`. The response returned `BAAI/bge-m3` while the configured base identity was `baai/bge-m3`; a new failing regression test reproduced the case-only variation. The adapter now compares the response model identity case-insensitively while still rejecting a different model or revision. All embedding adapter tests then passed `18/18`, and the real focused diagnostic passed on rerun.

## Implemented Scope

1. Added strict retrieval profile, source, chunk, score, relation, candidate and evidence contracts plus a frozen 12-case Chinese retrieval corpus.
2. Added canonical schema, record, long-field and relation projections with field-level minimization; hidden fields do not enter canonical text, hash or vector input.
3. Added validated local/remote embedding adapters and sanitized same-corpus profile diagnostics. TDR-018 freezes the OpenRouter BGE-M3 profile; the accepted local-profile measurement exception remains explicit.
4. Added fixed-dimension `vector(1024)` PostgreSQL models and additive migration `0035` for profile, source, chunk and relation indexes.
5. Added TDR-019 two-stage lifecycle: Stage06 mutations emit reference-only events, a coordinator fans out only to registered materialized visibility/scope profiles, and permission contraction revokes synchronously before rebuild.
6. Added exact/keyword/semantic/entity/freshness hybrid scoring after authorization, per-objective/table quotas, verified-edge expansion, stable ties, non-inventing rerank and score explanations.
7. Added EvidenceBundle assembly that revalidates current schema, authority, active source version, record version, safe fields and relation proof; citations and bundle hashes are backend-generated.
8. Added default-off, UUID-allowlisted Retrieval V2 shadow observation and a sanitized focused diagnostic. Observation failures do not affect V1 dispatch or user-visible bytes.

## Changed Files

The D delivery adds or updates:

- retrieval contracts and PostgreSQL models under `backend/app/schemas/` and `backend/app/models/`;
- projection, embedding, indexing, hybrid, evidence and shadow services under `backend/app/services/`;
- additive Alembic migration `20260729_0035_stage12_retrieval_v2.py`;
- Stage06 mutation hooks, configuration and route-level observational integration;
- focused benchmark/evaluation scripts, unit/API/PostgreSQL tests and synthetic fixtures;
- TDR-018/TDR-019, implementation plan, evidence, acceptance, governance and handoff documents.

No Mini App, public API/SSE schema, Specialist worker, action persistence, production configuration or deployment file was changed by D.

## Verification

Fresh verification for the completed D tree includes:

- D focused explicit selection: `91 passed in 6.56s`.
- C+D real PostgreSQL integration: `2 passed in 5.45s`.
- complete unit/API regression: `1906 passed in 155.27s`.
- full backend under the documented four-file boundary: `2005 passed, 134 skipped in 158.48s`.
- `python -m compileall -q app scripts`: exit `0`.
- `python -m alembic heads`: one head, `20260729_0035`.
- Black check: 12 selected D files unchanged.
- `git diff --check`: exit `0`.
- report JSON parsing, pass/hash verification, credential scan and changed/new-file developer-path scan: passed.
- disposable `stage06_smoke` restoration audit after a historical test reset: Alembic `20260729_0035`, `vector`, core `fields`, and all four Stage12-D retrieval tables present.

## Skipped Tests

The full regression retained `134` existing environment-gated skips. It explicitly excluded the same four historical PostgreSQL-only files used by the prior accepted boundary:

- `tests/integration/test_stage07_draft_employee_hub_postgres.py`
- `tests/integration/test_stage07_governance_write_postgres.py`
- `tests/integration/test_stage07_telegram_deep_link_delivery_postgres.py`
- `tests/integration/test_stage07_telegram_deep_link_postgres.py`

Local pinned BGE-M3 was not measured because its weight transfer stalled; this is the user-confirmed TDR-018 exception, not a passing local benchmark. Ruff was unavailable. No production migration, deployment, real-workspace embedding, public API/SSE activation, Specialist execution, action write or external send test is claimed.

## Remaining Risks

1. The route-level Retrieval V2 candidate loader is intentionally unavailable. Shadow is default-off, so runtime materialization and production recall are not yet proven.
2. All 12 focused cases hit the explicit Top 20 truncation flag. Recall remained `1.0`, but exhaustive fact, count, group and aggregate claims must continue to come from a complete Stage12-C structured result.
3. Only the confirmed remote BGE-M3 profile passed the hard benchmark; the accepted local-profile comparison remains unmeasured.
4. Migration `0035` has not been applied to production and no real workspace content has been sent to the external embedding provider.
5. User-visible answer quality cannot improve until Stage12-E consumes the structured query and evidence artifacts, followed by an explicit activation/deployment decision.
6. Gold human sign-off, Stage12-E/F and the 48-case three-round real-LLM campaign remain open Stage12 gates.

## Temporary Cleanup

- The OpenRouter key was loaded only into the real diagnostic process from the ignored local env file; it was not printed, written to evidence or retained in tracked files.
- Synthetic diagnostic JSON/Markdown reports are retained as acceptance evidence; no raw query, record text, vector or candidate ID is stored in their observation payload.
- A first full-suite attempt inherited `STAGE06_LOCAL_DATABASE_URL` and caused historical integration tests to reset the disposable `stage06_smoke` schema. The run was discarded, the database was recreated with `vector`, Alembic upgraded to `20260729_0035`, ownership restored to `ads_agent`, and the final regression was rerun with that environment variable explicitly removed.
- The project database `ads_agent`, production, Telegram and real workspace records were not modified.
- No temporary evidence file, process, deployment or external message remains. No commit was created; the repository one-final-commit rule remains active.

## Next Gate

Stage12-E must be documented and planned before implementation. It may consume the accepted A-D contracts but must not silently change schema, API, permissions, model profile, dispatch authority or the confirmed no-write/no-send boundaries.
