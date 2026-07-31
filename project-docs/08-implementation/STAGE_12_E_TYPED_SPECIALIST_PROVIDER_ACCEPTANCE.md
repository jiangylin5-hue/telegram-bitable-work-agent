# Stage12-E Typed Specialist / Provider V2 Acceptance

## Status

- Status: Task 6 and bounded Composer corrections `implemented-local`; integrated Stage12 release remains `FAIL`
- Date: 2026-07-30
- Scope: typed Specialist contracts and handlers, durable typed artifact ownership, sealed command inputs, Provider V2, ClaimGraph, grounded Composer and default-off shadow
- Runtime authority: Stage11 V1 remains the only user-answer and dispatch authority
- Deployment status: not authorized and not performed
- Superseding audit: `STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md`; Task 6 now supplies fresh direct evidence for the previously disproved runtime-wiring and unsupported-fact claims, but Task 7 A–F execution and final Case acceptance remain open
- Current integrated result: the post-correction real campaign passed all final-answer/Case gates `144/144`, but Composer availability regressed to unavailable `36/48`, `47/48`, `37/48`, dominated by schema-invalid responses. The deterministic fallback is complete and safe; real Provider composition is not release-reliable.

## 2026-07-30 Audit Correction Result

| Reopened requirement | Result | Fresh evidence |
| --- | --- | --- |
| Real worker has distinct typed Tabular/Risk/Daily/Action processors with no unavailable placeholder | PASS local | worker registry/process tests; real typed Tabular and Risk execution |
| ClaimGraph accepts only values/evidence/source versions sealed by typed facts | PASS local | three controlled mutation cases reject with `claim_graph_claim_unsupported` |
| Composer rejects unsupported prose even with valid claim/evidence IDs | PASS local | controlled “破产/预算耗尽” output becomes `provider_semantic_invalid` and deterministic fallback |
| Optional-last failure produces one safe terminal result | PASS local | fan-in persists one `composer_result` and one `run.degraded` |
| PostgreSQL persists a real non-tabular typed fan-in | PASS local | Risk input → `risk_assessment_set` → `claim_graph` → `composer_result`, `1 passed` |
| Unit/API compatibility | PASS local | `2061 passed` |
| Integrated raw Query A–F runtime and final-answer Case quality | OPEN | Task 7 and final campaign |

## Acceptance Result

| Requirement | Result | Evidence |
| --- | --- | --- |
| Four capabilities resolve to distinct handler factories | PASS | registry readiness and no-fallback tests; E focused suite `78 passed` |
| Tabular copies Stage12-C records/aggregates exactly without an LLM | PASS | exact/truncation/scope tests; Provider calls `0` |
| Risk consumes facts plus authorized policy without query/retrieval rescan | PASS | deterministic rule and scope tests; Provider calls `0` |
| Daily consumes supplied aggregates/risk without recounting | PASS | aggregate/risk/recommendation tests; Provider calls `0` |
| Action uses only supplied slot/candidates/evidence/current versions and never writes | PASS | proposal/denial/version/scope tests; writes `0`, sends `0` |
| Typed payloads are durable and recoverable | PASS | `Stage06IdempotencyRecord.response_ref` owner, hash/scope/kind/status checks and PostgreSQL fan-in artifact recovery |
| Command inputs are sealed and replay-safe | PASS | durable outbox envelope reconstruction, same-capability objective separation and duplicate-ref rejection |
| Provider taxonomy, deadline, retry, repair, citation, language and semantic gates | PASS | timeout/429/recoverable-5xx only, 400 no retry, one bounded repair, semaphore and fail-closed tests |
| ClaimGraph handles duplicate, stale and same-version conflict without choosing a winner | PASS | claim graph tests and conflicted-action denial |
| Composer cannot introduce unsupported facts or false completion | PASS | deterministic fallback with `provider_semantic_invalid` and grounded claim/evidence subsets |
| Supervisor owns one final artifact/event | PASS | one `composer_result`, one terminal event and idempotent replay tests |
| Public HTTP/SSE and V1 dispatch are unchanged | PASS | route shadow compatibility tests; comparison hash remains audit-only |
| Real focused Provider evidence exists | PASS | baseline `google/gemini-2.5-flash`, risk/daily/composer `3/3`, three attempts, zero failures |

## Changed Files

Stage12-E adds or changes:

- contracts in `backend/app/schemas/agent_specialist_results.py`;
- durable artifact, registry, four handlers, Provider validation/gateway, risk policy, ClaimGraph, Composer and shadow services under `backend/app/services/`;
- sealed dispatch/fan-in behavior in `backend/app/services/agent_orchestrator.py`, `agent_event_runtime.py`, `stage06_platform.py` and `backend/app/workers/agent_specialist_runtime.py`;
- default-off internal configuration and audit-only shadow seam in `backend/app/core/config.py` and `backend/app/api/routes/agent_runs.py`;
- focused Provider and Specialist diagnostics under `backend/scripts/`;
- unit/API/PostgreSQL tests under `backend/tests/`;
- this source, plan, acceptance and sanitized evidence package.

No Stage12-E database migration, public response/SSE field, Mini App contract, production config or external write authority was added.

## Verification

- E focused: `78 passed in 7.54s`.
- Real local PostgreSQL event/fan-in artifact: `1 passed in 2.69s`.
- Unit/API: `1966 passed in 146.04s`.
- Full backend with only the documented four historical PostgreSQL files excluded: `2065 passed, 134 skipped in 151.07s`.
- Real Provider profile benchmark: `3/3` completed, attempts `3`, failures `0`, mean `3465 ms`, p95 `4957 ms`, tokens `207/125`.
- Synthetic Specialist diagnostic: handlers `4`, contract exact `4/4`, typed artifacts `6`, claims `2`, action proposals `1`, writes/sends `0/0`.
- Compile, migration-head, formatting, whitespace, report-hash and secret/path checks passed.

Detailed evidence: `evidence/stage12-e-typed-specialist-provider-2026-07-30.md`.

## Skipped Tests

- Redis integration was skipped because neither `STAGE10_REDIS_URL` nor the Python `redis` package was available.
- The full suite retained `134` existing environment-gated skips and the same four explicitly documented historical PostgreSQL-file exclusions used by Stage12-C/D.
- Ruff was unavailable.
- The 48-case ×3 real-LLM campaign was intentionally not run; it remains the final Stage12 gate after core architecture.

## Remaining Risks

1. `TYPED_SPECIALISTS_V2_MODE` defaults to `off`; the API shadow loader is intentionally unavailable without injected synthetic/isolated A-D artifacts.
2. The distinct handler registry and shadow pipeline are locally proven, but the deployed Stage11 worker still owns production answers. Non-tabular Stage12 worker activation remains closed rather than falling back to tabular.
3. The real Provider benchmark contains only three focused synthetic cases. It confirms transport/schema/grounding behavior, not product-wide answer quality or variance.
4. Retrieval V2 is still not materialized into the live answer path, so users cannot yet receive the complete A-D-E chain.
5. Action execution, draft persistence, confirmation UI, record-version conflict at commit time and durable external side-effect controls belong to Stage12-F.
6. Human Gold sign-off, production migration/activation and the 48-case three-round real-model campaign remain open.

## Temporary Cleanup

- Local OpenRouter credentials were transient and never persisted to tracked evidence.
- The disposable PostgreSQL database was restored to migration `0035`; no fixture business records or temporary files were retained.
- No deployment, Telegram send, record write, draft creation or production migration occurred.
