# Stage07 Final Acceptance Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. The already-approved Stage07 contracts are authoritative; this plan adds acceptance evidence and smallest defect repairs only.

**Goal:** Close every acceptance item that is inside an approved Stage07 contract, with direct local/PostgreSQL/UI/OpenRouter/Telegram evidence; leave only explicitly unapproved product scope or unavailable external authority as blocked with exact prerequisites.

**Architecture:** Reuse the existing FastAPI development-header identity only for a disposable local PostgreSQL fixture, the existing Stage06/07 UoW and authorization services, the built Vite Mini App, and the existing Stage06 OpenRouter/Telegram smoke entry points. A temporary same-origin proxy may inject one synthetic local actor header into local FastAPI traffic; it must not expose credentials, policies, raw API failures, or fixture data to the browser. No product route, schema, permission action, dependency, browser persistence, memory, RAG, or general agent framework is introduced by this closure package.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, disposable local PostgreSQL, React/Vite/TypeScript/Vitest, existing LangGraph/OpenRouter runtime, existing Telegram Bot API smoke scripts, Codex in-app Browser.

## Global Constraints

- Treat `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`, the named BDD/SDD documents and `STAGE_07_ACCEPTANCE_CHECKLIST.md` as the acceptance source; do not promote a row without direct current evidence.
- Use `STAGE06_LOCAL_DATABASE_URL` only as an already-authorized disposable local database. Never print its value or target an unspecified database.
- UI testing uses Codex in-app Browser only. Do not claim a user-browser test or interact with the user's Chrome profile.
- Real OpenRouter requires the already-approved, non-production `OPENROUTER_API_KEY`; real Telegram requires one restricted non-production Bot token and exactly one private allowlisted test chat/user. Never put values in Markdown, logs, screenshots, commits, or browser state.
- Do not mutate BotFather, a webhook, an external destination, or a real chat without the supplied restricted configuration and the user authorization recorded in this task. The existing scripts retain their fail-closed preflight and no-send defaults.
- Do not treat separately unapproved Team Bot memory, generic knowledge/RAG/files, broader lifecycle, multi-Base scope, Telegram group delivery, staging, production, or deployment as acceptance work. Record these as `contract-gated`, not as missing implementation.

---

### Task 1: Freeze the closure matrix before touching behavior

**Files:**
- Create: `project-docs/08-implementation/evidence/stage07-final-acceptance-closure.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Read: every `STAGE_07_*_BDD_AND_ACCEPTANCE.md`, `STAGE_07_*_SDD.md`, `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`

**Consumes:** approved BDD rows, existing evidence and test files.

**Produces:** one matrix with exactly `implemented`, `partial`, `blocked-external-authority`, or `contract-gated` per row, plus a command or observation required to change the status.

- [ ] List all unchecked global-checklist rows and every `partial-local` row in the dedicated evidence files.
- [ ] Classify a row as implementation defect only if its approved BDD says it must exist and current source/test evidence is absent; classify all external credential/chat/environment work as `blocked-external-authority` until its preflight passes.
- [ ] Record the initial, sanitized preflight result from:

```powershell
cd backend
python scripts/stage06_live_openrouter_smoke.py
python scripts/stage06_telegram_entry_smoke.py
```

Expected before credentials: exit `2`, a `blocked` JSON status and only missing variable names.

### Task 2: Add the remaining Team Bot and employee lifecycle acceptance tests first

**Files:**
- Modify: `backend/tests/unit/test_stage07_team_bot_knowledge_service.py`
- Modify: `backend/tests/unit/test_stage07_team_bot_knowledge_api.py`
- Modify: `backend/tests/integration/test_stage07_team_bot_knowledge_postgres.py`
- Modify: `mini-app/src/test/team-bot-app-flow.test.tsx`
- Modify only if a failing test proves it necessary: `backend/app/services/stage07_team_bot_knowledge.py`, `mini-app/src/app/App.tsx`, `mini-app/src/app/TeamBotWorkbench.tsx`

**Consumes:** TD010 active/paused/assigned-member eligibility, TD011 selected-view reread, the existing Stage06 idempotency ledger, safe DTOs and protected query helpers.

**Produces:** direct coverage for revoked/paused/assigned grant/cross-Base failure, changed-idempotency-payload conflict and delayed `401/403/404/409/422` UI replacement without raw API data or stale context.

- [ ] **RED:** Write a service/API test that creates an active scoped employee, then pauses it or removes the caller grant before `summarize_team_bot`; assert the request is denied before runtime invocation and the response contains no view record values.
- [ ] **RED:** Write a cross-Base selected-view test; pass a valid opaque view ID outside the employee Base and assert the service refuses it before window construction.
- [ ] **RED:** Reuse an idempotency key with a changed `view_id` or instruction and assert the existing versioned ledger produces conflict rather than a second agent/audit outcome.
- [ ] **RED:** Defer each protected summary request in the App test, replace the workspace/selection, resolve `401`, `403`, `404`, `409` and `422`, and assert no old answer, citation, selected view or remote error text replaces the current surface. For `409`/`422`, retain only the local instruction and offer reread/retry.
- [ ] Run each new focused test and confirm it fails because the guard/recovery is absent, not because a fixture is malformed.
- [ ] **GREEN:** make the smallest existing-contract repair necessary for the failing test. The server remains authority for lifecycle/grant/Base/view checks; the client retains only typed local instruction text and clears server-derived context on terminal invalidation.
- [ ] Run:

```powershell
cd backend
python -m pytest -q tests/unit/test_stage07_team_bot_knowledge_service.py tests/unit/test_stage07_team_bot_knowledge_api.py tests/integration/test_stage07_team_bot_knowledge_postgres.py -m postgres
cd ..\mini-app
npm.cmd test -- --run src/test/team-bot-app-flow.test.tsx src/test/team-bot-workbench.test.tsx src/test/team-bot-api.test.ts
```

Expected: every selected test passes and no response asserts or prints raw record values.

### Task 3: Run the approved local PostgreSQL contention and safety matrix

**Files:**
- Read/Run: `backend/tests/integration/test_stage07_digital_employee_management_postgres.py`
- Read/Run: `backend/tests/integration/test_stage07_draft_employee_hub_postgres.py`
- Read/Run: `backend/tests/integration/test_stage07_telegram_deep_link_postgres.py`
- Read/Run: `backend/tests/integration/test_stage07_telegram_deep_link_delivery_postgres.py`
- Read/Run: `backend/tests/integration/test_stage07_view_builder_postgres.py`
- Read/Run: `backend/tests/integration/test_stage07_view_builder_security_postgres.py`
- Modify: the specific integration test that lacks the approved concurrency/revocation assertion, then the smallest owning service only if its RED test proves a defect.

**Consumes:** the local PostgreSQL fixture and approved migration head.

**Produces:** migration replay plus two-session (or equivalent concurrent transaction) evidence for employee lifecycle, Team Bot revocation, V1 access/query and Telegram pointer/delivery reservation safety.

- [ ] Run the existing PostgreSQL suite using the configured local fixture; retain the exact passing/skipped count.
- [ ] For any explicitly approved but unobserved contention row, add a two-session test using the repository's existing PostgreSQL fixture pattern. It must prove one authoritative terminal outcome, not merely two mocked calls.
- [ ] Re-run the full PostgreSQL matrix after each repair. Do not add a new physical index unless a measured `EXPLAIN` shows a documented query requirement is unmet.

```powershell
cd backend
python -m pytest -q tests/integration/test_stage07_digital_employee_management_postgres.py tests/integration/test_stage07_draft_employee_hub_postgres.py tests/integration/test_stage07_team_bot_knowledge_postgres.py tests/integration/test_stage07_telegram_deep_link_postgres.py tests/integration/test_stage07_telegram_deep_link_delivery_postgres.py tests/integration/test_stage07_view_builder_postgres.py tests/integration/test_stage07_view_builder_security_postgres.py -m postgres
```

### Task 4: Observe the real local Mini App through the in-app Browser

**Files:**
- Create temporarily, then delete: `backend/scripts/stage07_final_acceptance_seed.py`
- Create temporarily, then delete: `mini-app/scripts/stage07-final-acceptance-proxy.mjs`
- Modify: `project-docs/08-implementation/evidence/stage07-final-acceptance-closure.md`

**Consumes:** real FastAPI, compiled `mini-app/dist`, disposable PostgreSQL, existing `X-Stage06-User-Id` local-only identity adapter and approved safe UI routes.

**Produces:** one seeded local UI pass at `1440x900`, `1280x720`, `430x932`, and `390x844` recording only rendered safe labels/states, console errors/warnings and success/denial outcomes.

- [ ] Seed only synthetic owner/editor/viewer data using existing platform/governance/employee services. Give the fixture an active personal assistant, active Team Bot, one paused employee, one pending draft, an allowed/hidden field pair, a permitted relation/lookup record and an opaque Telegram pointer. Print only opaque IDs and fixture status.
- [ ] Start FastAPI with `DATABASE_URL=$env:STAGE06_LOCAL_DATABASE_URL`, `APP_ENV=local` and a local port. Build the Mini App, serve it from a same-origin local proxy and inject only one fixture actor per path. The proxy must not log headers, body, raw errors, field values or URL tokens.
- [ ] In the Codex in-app Browser, observe all four widths. For the current actor, verify: capability-derived Home navigation; Base/record safe projection; a relation detail edit and authoritative reread; role separation; draft review; personal assistant safe select/reread; Team Bot selected-view summary/receipt/Base handoff; lifecycle pause/denial; Telegram safe recovery path.
- [ ] Check Browser console at the final stable state for `error`, `warn` and `warning`. Capture only sanitized visual evidence if it contains no private identifiers, raw payloads or secrets.
- [ ] Stop local servers, delete temporary fixture/proxy sources and logs, reset the disposable database and verify the ports are closed before documentation is updated.

### Task 5: Perform real provider and Telegram smoke only after preflight is ready

**Files:**
- Read/Run: `backend/scripts/stage06_live_openrouter_smoke.py`
- Read/Run: `backend/scripts/stage06_telegram_entry_smoke.py`
- Read/Run: `backend/app/services/stage07_telegram_deep_link_delivery.py`
- Modify: `project-docs/08-implementation/evidence/stage07-final-acceptance-closure.md`

**Consumes:** `OPENROUTER_API_KEY`; `TELEGRAM_BOT_TOKEN`; `STAGE06_TELEGRAM_TEST_CHAT_ID`; `STAGE06_TELEGRAM_TEST_USER_ID`; `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`; `TELEGRAM_SEND_MODE=restricted_test`; current Telegram Mini App test URL/HTTPS configuration.

**Produces:** sanitized, non-production evidence of one permission-filtered provider summary and one private Telegram Mini App identity/deep-link/delivery observation. No credential, raw update, chat text, token, URL or provider prompt/response is retained.

- [ ] Run OpenRouter with only the five existing safe cases: `summarize_basic`, `hidden_field_guard`, `citations_required`, `draft_update_status`, `unsafe_commit_refusal`. Verify no record write occurs before the explicit confirmation path.

```powershell
$env:STAGE06_OPENROUTER_SMOKE_CASES = 'summarize_basic,hidden_field_guard,citations_required,draft_update_status,unsafe_commit_refusal'
cd backend
python scripts/stage06_live_openrouter_smoke.py
```

- [ ] Run Telegram preflight. If it is ready, use one private allowlisted chat and send the existing mention form `@<configured alias> summarize`; record only redacted outcome metadata. Do not enable temporary polling or change a webhook unless the existing script's config explicitly enables it and its restoration evidence is available.

```powershell
cd backend
python scripts/stage06_telegram_entry_smoke.py
```

- [ ] Verify the real Mini App launch only via official signed `initData`, then resolve one opaque pointer and reread its authorized target. If an actual delivery is configured, use the existing confirmation/outbox/worker path once and verify the persisted safe terminal receipt; do not make a second send attempt.
- [ ] If any required variable, HTTPS Mini App URL, bot/test-chat binding, or manual test message is unavailable, mark the row `blocked-external-authority` with that exact missing prerequisite; do not substitute a mock or claim the test passed.

### Task 6: Run final regressions, clean up, and reconcile every source document

**Files:**
- Modify: `AGENTS.md`
- Modify: `HANDOFF.md`
- Modify: `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_07_SUBSTAGE_DELIVERY_ROADMAP.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Modify: only the BDD/SDD/evidence documents whose rows received direct fresh evidence

**Consumes:** exact output from Tasks 1–5.

**Produces:** a truthful Stage07 exit status and an explicit residual list. Stage07 is marked complete only if no approved acceptance row remains `partial` or `blocked-external-authority`.

- [ ] Run the complete backend suite, then full Mini App suite and production build:

```powershell
cd backend
python -m pytest -q
cd ..\mini-app
npm.cmd test -- --run
npm.cmd run build
```

- [ ] Run integrity and cleanup checks:

```powershell
git diff --check
Get-NetTCPConnection -LocalPort 8001,4176 -State Listen -ErrorAction SilentlyContinue
rg --files backend/scripts mini-app/scripts | Select-String -Pattern 'stage07_final_acceptance_seed|stage07-final-acceptance-proxy'
git status --short
```

- [ ] Update each acceptance row only with observed evidence. Explicitly distinguish `implemented-local`, real non-production provider/Telegram evidence, `blocked-external-authority`, and `contract-gated`; do not use a blanket “done” label.
- [ ] Commit only after the full command output and document cross-check support every stated claim.

## Plan Self-Review

- Existing contract coverage: Team Bot, employee lifecycle, V1, S5/TD009, S6.1/S6.2, UI, local PostgreSQL and full regressions each have an owning task.
- External boundaries: OpenRouter/Telegram have explicit fail-closed preflight and no substitute evidence.
- Scope protection: no new memory/RAG/files/general Bot capability, schema/API/permission contract, staging or production work appears in the plan.
- Completion rule: blocked credentials/configuration are reported as blockers rather than silently treated as passed.
