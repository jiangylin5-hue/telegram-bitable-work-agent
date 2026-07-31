# Stage12 Task 6 Typed Worker / Safe Composer Evidence

## Status

- Status: `implemented-local`
- Date: 2026-07-30
- Scope: real typed worker routing, durable typed input/output ownership, sealed ClaimGraph, safe Composer and optional-failure convergence
- Runtime/deployment: Stage11 remains user-answer authority; no deployment or Stage12 activation performed

## Changed Files

- `backend/app/workers/agent_specialist_runtime.py`
- `backend/app/services/agent_typed_artifacts.py`
- `backend/app/services/agent_claim_graph.py`
- `backend/app/services/agent_composer_v2.py`
- `backend/app/services/agent_orchestrator.py`
- `backend/scripts/stage12_specialist_provider_evaluation.py`
- `backend/scripts/stage12_query_engine_evaluation.py`
- focused unit and PostgreSQL tests under `backend/tests/`
- Stage12 correction plan/source/acceptance documents

## What Changed

1. The real Specialist worker registry constructs four distinct typed handler instances and no longer maps Risk/Daily to an unavailable placeholder or to the tabular implementation.
2. A typed command is reconstructed from its durable outbox envelope and sealed `ObjectiveSpecialistInputV1` owner; capability, scope, deadline, idempotency and upstream artifact identities must match exactly.
3. Typed owners now support `bundle_hash`, content-addressed versioned payloads without an intrinsic hash, and the versionless `ActionSlotV1` through the explicit owner payload version `action-slot.v1`.
4. Capability-specific outputs persist as `structured_fact_set`, `risk_assessment_set`, `daily_brief` or `controlled_action_proposal`; Supervisor persists a separate `claim_graph` and terminal `composer_result`.
5. ClaimGraph verifies record-field, aggregate and risk claims against sealed typed values, evidence subsets and source versions before merging or conflict resolution.
6. Composer Provider output must select every validated claim exactly, cite the exact selected evidence union and equal the deterministic fact renderer for that ordering. Arbitrary prose with otherwise valid IDs is rejected as `provider_semantic_invalid`.
7. When the last optional Specialist fails, fan-in now emits one safe `run.degraded` terminal event and one final result instead of leaving the run non-terminal.
8. The Stage12-C diagnostic now uses the shared authorized Entity Linker after full unit/API collection exposed its stale deleted helper import.

## RED Evidence

The first focused run failed exactly as intended:

- three ClaimGraph mutations failed because `source_artifacts` was unsupported;
- the controlled “该公司即将破产，预算已经全部耗尽” Provider draft incorrectly returned `completed`;
- optional-last failure rejected the missing `fan_in` argument and left no terminal result;
- the real worker registry import failed because no typed process registry existed.

Recorded result: `5 failed` for the grounding/composition/terminal slice, plus one collection error for the missing worker registry.

## GREEN Verification

- Task 6 / Stage12-E focused: `84 passed in 7.64s`.
- Related handler/worker/ClaimGraph/Composer slice after formatting: `46 passed in 3.09s`.
- Real local PostgreSQL typed Risk worker: `1 passed in 2.62s`.
- Full unit/API: `2061 passed in 135.46s`.
- Stage12-C stale evaluation import correction: `11 passed in 2.67s`.
- Synthetic Specialist diagnostic: handlers `4`, exact contracts `4/4`, claims `2`, partial failure safe `true`, actions `1`, writes/sends `0/0`.
- Real OpenRouter-compatible focused Provider smoke using `google/gemini-2.5-flash`: `3/3` passed, attempts `3`, failures `0`, mean latency `2676.33 ms`, P95 `3144 ms`, tokens `207/127`.
- Black check: `14 files would be left unchanged`.
- `compileall`: passed.
- Alembic: one head, `20260730_0039`.
- `git diff --check`: passed; only existing Windows LF/CRLF conversion warnings were emitted.
- Touched-file credential scan: passed.
- Ruff: skipped/unavailable (`No module named ruff`).

## Skipped Tests

- No test in the `tests/unit tests/api` run was skipped.
- Real Redis integration is deliberately Task 8 and was not claimed here.
- The full 48 Case ×3 real Provider campaign is deliberately deferred until Tasks 7–9.
- Mini App/build was not rerun because Task 6 changes no public HTTP/SSE or frontend contract; final Stage12 acceptance will rerun it.

## Remaining Risks

1. `TYPED_SPECIALISTS_V2_MODE` remains default `off` and allowlist-gated; Stage11 is still the only user-answer authority.
2. Task 6 proves typed command execution, but raw Chinese Query → A–F isolated execution is Task 7 and is not yet accepted.
3. Daily and Action handlers retain direct contract/unit coverage and distinct real-worker registration; the fresh PostgreSQL runtime smoke exercises Risk as the non-tabular representative.
4. Real Redis crash/pending/ack-once evidence, human Gold sign-off and three full Provider rounds remain open.

## Temporary Cleanup

- Provider credentials were loaded only into the process environment and were not written to evidence.
- PostgreSQL evidence used unique disposable rows and rolled back the session.
- Temporary JSON diagnostics under `backend/.tmp` are removed after evidence transcription.
- No record change, draft confirmation, notification, Telegram send, deployment or production migration occurred.
