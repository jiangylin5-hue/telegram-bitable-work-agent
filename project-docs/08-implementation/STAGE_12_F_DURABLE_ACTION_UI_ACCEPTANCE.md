# Stage12-F Durable Action 与确认 UI 验收

## Status

- Status: acceptance reopened; `partial-local`, not accepted
- Date: 2026-07-30
- Scope: Stage12-F Durable Objective/Action runtime、受控确认 API/SSE 与 Mini App UI
- Deployment status: not authorized and not performed
- Final Stage12 status: not complete; 48 Case × 3 real-LLM campaign remains open
- Superseding audit: `STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md`; historical browser/PostgreSQL evidence remains valid, but blind admission, effective field policy and Redis/runtime integration gates remain open

## Acceptance Result

| Requirement | Result | Evidence |
| --- | --- | --- |
| `agent_objective_runs` / `agent_action_slots` 与单 Alembic head | PASS | migration `20260730_0036`; real PostgreSQL current/head |
| Blind ActionSlot 与授权 candidate resolution | PASS | empty/multiple/view/field/required/version/local-conflict tests |
| Encrypted private payload and safe public projection | PASS | AAD/scope/expiry/tamper/redaction tests; API never exposes private refs or hidden targets |
| Independent durable Action worker | PASS | distinct topic/handler, lease/retry/recovery/idempotency and ack-once tests |
| Action Specialist semantic validation | PASS | exact slot/candidate/schema/scope/version/evidence checks before materialization |
| Tool Gateway remains the only materialization boundary | PASS | only pending draft or blocked notification is persisted before confirmation |
| Confirmation and rejection | PASS | reauthorization, editable fields, proposal/record versions, idempotency and conflict mapping |
| User-edited value reaches the real record write | PASS | PostgreSQL RED/GREEN regression plus repeated real browser flow |
| Objective/Action safe SSE | PASS | sequence, resume, minimized projection and terminal behavior tests |
| Mini App review/edit/confirm/reject | PASS | focused `25 passed`, full `412 passed`, build PASS, real browser acceptance |
| Real Action Provider call | PASS | one OpenRouter call using retained `google/gemini-2.5-flash`; strict schema/semantic gate |
| Confirmation-before-write safety | PASS | initial pending flow `records=0`; final flow record delta only after explicit confirmation |
| External-send safety | PASS | notification requests `0`; Telegram send requests `0` |
| Desktop and Telegram Mini App responsive behavior | PASS | real browser plus `390 × 844`, no horizontal overflow or error overlay |

## Changed Files

Stage12-F changes are grouped as follows:

- durable contracts/models/migration: `stage12_action_runtime.py`, `agent_event_runtime.py`, model exports and `20260730_0036_stage12_durable_actions.py`;
- candidate, private payload, materialization, confirmation and Action Specialist services under `backend/app/services/stage12_*` plus `agent_action_candidates.py`;
- action admission, route wiring and worker runtime in `agent_runs.py`, `stage12_agent_actions.py`, `stage12_action_runtime.py` and existing event/orchestrator services;
- Objective/Action SSE schemas and projections;
- Mini App API parser, event adapter, collaboration workbench, styles and tests;
- real Action Provider diagnostic and sanitized evidence;
- Stage12-F unit/API/PostgreSQL/browser tests and current truth/handoff/index documents.

The Stage12 A–E changes already present in this worktree remain part of the same uncommitted Stage12 delivery package. No unrelated product capability, action kind, permission system or external write provider was added.

## Verification

- Stage12-F focused: `49 passed in 11.67s`.
- Full backend with real local PostgreSQL: `2209 passed, 38 skipped in 442.18s`.
- Mini App focused: `25 passed`.
- Mini App full: `79 test files, 412 tests passed in 305.60s`.
- Mini App production build: PASS.
- Real Provider: `1/1`, provider calls `1`, failures `0`, writes/sends `0/0`.
- Real browser: pending card, explicit edit, explicit confirm, `executed`, PostgreSQL edited value verified, sends `0`.
- Migration/compile/format/whitespace/security scans: PASS.

Detailed machine-readable and narrative evidence:

- `evidence/stage12-f-durable-action-ui-2026-07-30.json`
- `evidence/stage12-f-durable-action-ui-2026-07-30.md`
- `evidence/stage12-f-real-action-provider-2026-07-30.json`

## Skipped Tests

- One real Redis integration: no local Redis listener or configured `STAGE10_REDIS_URL`.
- 17 online PostgreSQL smoke tests: no independent online database URL.
- Three Stage08 collaboration PostgreSQL tests: no independent `STAGE08_RAG_DATABASE_URL`.
- 17 Stage08 RAG/pgvector tests: no independent `STAGE08_RAG_DATABASE_URL`.
- Ruff: not installed.
- 48 Case × 3 real-model campaign: deliberately deferred by approved Stage12 scope.

## Remaining Risks

1. Stage12 A–F remain local and default-off relative to the deployed Stage11/r76 runtime; production activation and migration are not authorized.
2. Real Redis transport was not available locally. In-memory stream semantics are covered, but a production-like Redis worker smoke is still required before activation.
3. The real Action Provider gate is intentionally one focused synthetic case. It verifies transport/schema/semantic safety, not broad product quality or variance.
4. The full 48 Case × 3 real-model campaign and human Gold sign-off remain the final Stage12 acceptance gate.
5. No real Telegram send was performed; this is a safety result, not delivery-provider acceptance.

## Temporary Cleanup

- Browser Vite/API processes stopped.
- Disposable Stage12-F database dropped after evidence generation.
- Temporary browser logs removed after evidence generation.
- Local credentials remained in ignored environment files only.
- No production deployment, migration, record write, notification or Telegram send occurred.
