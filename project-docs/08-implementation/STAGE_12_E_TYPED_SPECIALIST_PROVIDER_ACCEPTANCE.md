# Stage12-E Typed Specialist / Provider V2 Acceptance

## Status

- Status: Task 6 and Grounded per-slot P2 `implemented-local-p2-passed`; integrated Stage12 release remains `FAIL` until P3/native gates
- Date: 2026-07-31
- Scope: typed Specialist contracts and handlers, durable typed artifact ownership, sealed command inputs, Provider V2, ClaimGraph, grounded Composer and default-off shadow
- Runtime authority: Stage11 V1 remains the only user-answer and dispatch authority
- Deployment status: isolated/default-off native candidate authorized after P1/P2/full regression; not performed
- Superseding audit: `STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md`; Task 6 now supplies fresh direct evidence for the previously disproved runtime-wiring and unsupported-fact claims, but Task 7 A–F execution and final Case acceptance remain open
- Current integrated result: the post-correction real campaign passed all final-answer/Case gates `144/144`, but Composer availability regressed to unavailable `36/48`, `47/48`, `37/48`, dominated by schema-invalid responses. The deterministic fallback is complete and safe; real Provider composition is not release-reliable.

## 2026-07-31 Grounded Answer P1 Status

Grounded Answer Provider V2 contracts, request projection, deterministic grounding validation/rendering, real adapter, real-origin scoring and the exact 12-call P1 runner are implemented locally. Focused verification is `37 passed`. P1 remains `FAIL`; P2/P3 and deployment have not started.

Immutable failed attempts are retained under `evidence/stage12-grounded-answer-p1-2026-07-31-attempt-01-failed` through `attempt-05-failed`:

- Gemini: HTTP `0/12`, upstream schema serving-state limit.
- Qwen 235B before prompt correction: real grounded `7/12`.
- Qwen Next 80B: real grounded `2/12`.
- DeepSeek V3.2 best attempt: real grounded `11/12`, one token-cap JSON truncation.
- DeepSeek fixed-seed experiment: regressed to `9/12`; the experiment was rejected and reverted.

Current measured root causes are long private Provider handles/output-token pressure and the absence of a true wall-clock transport deadline. No failed attempt used fallback, selective retry, business data, confirmed Action, write or Telegram send. The private contract correction was held at its confirmation gate until the user approved it.

The user explicitly confirmed the compact-reference and hard-deadline correction on 2026-08-01. Local implementation is authorized under `STAGE_12_GROUNDED_PROVIDER_COMPACT_REFERENCE_DECISION.md`; this does not authorize P2/P3 bypass, deployment, production activation, business writes or Telegram sends.

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
6. Human Gold is signed `48/48`, but Grounded V2 implementation, P1/P2, native server validation, P3, Telegram and final activation remain open.

## Temporary Cleanup

- Local OpenRouter credentials were transient and never persisted to tracked evidence.
- The disposable PostgreSQL database was restored to migration `0035`; no fixture business records or temporary files were retained.
- No deployment, Telegram send, record write, draft creation or production migration occurred.

## Grounded Answer V2 Reopened Gate

The `144/144` returned-answer result cannot be cited as real-model acceptance because only `24/144` cases completed the real Composer path and `120/144` used deterministic fallback. The failure taxonomy contains 240 schema-invalid attempts and the total-latency P95 gate also failed. Stage12-E therefore remains `FAIL` until the approved Grounded Answer Provider V2 produces real model-authored answers and passes P1/P2/P3 with zero fallback in P3.

## 2026-08-01 RenderSlot V3 Local Status

The user-approved TDR-027 RenderSlot correction is `implemented-local-deterministic-verified`. The active adapter now accepts only ordered text-only `GroundedAnswerPlanV3` output and the backend owns all section/statement/reference closures. Fresh focused evidence is `143 passed`, including a deterministic 48 × 3 campaign at `144/144` real-origin-shaped answers with zero fallback; full unit is `2167 passed`. This deterministic result is not real Provider acceptance.

Real status correction: V3 P1 passed `12/12`, but exact P2 failed twice at `26/36` and `24/36` real/final answers with zero unauthorized effects/writes/sends. Both failures are retained; fallback remains an acceptance failure. The proposed per-slot isolated Provider topology awaits explicit confirmation, so full campaign, native server and Telegram remain blocked.

## 2026-08-01 Per-Slot P1/P2 Acceptance Update

The user approved TDR-028 and the per-slot topology is now implemented. The
Provider receives one slot and only that slot's closure; maximum slots are
three, concurrency is two, all calls share the 50-second answer deadline, and
any slot failure rejects the complete Provider result. Partial Provider text is
never mixed with fallback. Final-code verification is focused `140 passed`,
all unit `2176 passed`, compileall and diff check.

Fresh real P1 passed `12/12` HTTP/schema/grounding/real Provider with fallback
`0` (hash `af9b1c69a817611bdae1103b89e4ac89b98bdd86d9304c7d91fb1f190e6fa989`).
The accepted exact P2 passed `36/36` real Provider/final-answer, fallback `0`,
mean/p95 `3086/4385 ms`, zero unauthorized effects, zero production writes and
zero Telegram sends (hash
`54de9da4eb0e7ae7eb65d62bbb85807d5382af05a2b795a29628dc10eecc86cc`).
Failed intermediate `31/36` and `35/36` results are retained. They led to
slot-kind-specific instructions without weakening language, canonical atom or
Action non-execution validation.

This closes the bounded P1/P2 gate only. P3 `144/144`, native server release
candidate verification, runtime activation and real Telegram testing remain
open; Stage11 remains production authority.
