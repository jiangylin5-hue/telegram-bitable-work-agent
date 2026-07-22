# Stage07 R1-R3 Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete every compatible originally approved Stage07 R1-R3 feature that is unfinished or half-delivered, close its evidence/documentation gaps around the internal Telegram-first Customer/Opportunity -> Project -> Task operating scenario, and avoid only genuinely new Telegram group operations.

**Architecture:** Reuse the current FastAPI/SQLAlchemy service boundaries, existing safe Mini App DTOs/React query state, existing Stage07 builders/views/drafts/employee/Telegram identity seams, and disposable local PostgreSQL. R1 adds only scenario-focused regression/acceptance coverage and repairs a current-contract defect if a red test proves one. R2 does the same for governance/draft/employee/Team Bot behavior. R3 reconciles the observed bounded Telegram result and final evidence without creating any new external side effect.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, React, TypeScript, Vite, Vitest, existing LangGraph/OpenRouter and Telegram contracts.

## Global Constraints

- R0 documents and `STAGE_07_R0_CLOSURE_MATRIX.md` are the active closure boundary, but original Stage07 technical decisions/BDD/SDD/work-surface/implementation plans remain binding for compatible approved work.
- Before deferring any item, inspect its original documents. A `not-started` or `partial-local` compatible behavior must be implemented in R1/R2/R3; it cannot be moved to later scope for convenience.
- Do not add a schema migration, API route, permission action, Telegram group binding, Bot direct write, customer account, RAG, memory, file store, public sharing or production deployment.
- Reuse existing Customer/Opportunity -> Project -> Task relations through generic Base/Table/Field/Record services; fixture names and values remain synthetic.
- Use test-first repair: add/focus a failing regression before any product-code repair; do not refactor unrelated files.
- Never print or persist Telegram identifiers, tokens, raw `initData`, deep links, raw provider prompt/response or synthetic record values in evidence.
- No new outbound Telegram request is allowed. S6.3 remains cleaned; Stage03 must not be modified.
- Browser observation, if used, is Codex in-app Browser only. Do not control the user's Chrome browser.
- Do not rerun broad suites merely to create volume: run focused tests for each changed/accepted row and one final proportional regression per layer.

---

### Task 1: Inventory original R1-R3 contracts, reconcile R0 and create the customer-project acceptance fixture contract

**Files:**
- Modify: `project-docs/08-implementation/STAGE_07_R0_CLOSURE_MATRIX.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Read: every linked original R1/R2/R3 technical decision, BDD, SDD, work-surface and implementation plan
- Create: `backend/tests/unit/test_stage07_customer_project_core_api.py`
- Create: `mini-app/src/test/customer-project-core-app-flow.test.tsx`

**Consumes:** existing workspace/Base/table/field/record/view APIs, safe Home DTO, Base Canvas routes and existing protected query behavior.

**Produces:** one synthetic Customer/Opportunity -> Project -> Task scenario contract that proves only authorized safe read/navigation/draft handoff behavior.

- [x] Write backend tests that create one synthetic workspace, one Base and Customer/Project/Task tables through existing API routes; use same-Base relations only; assert viewer projection omits an internal field and non-member requests fail closed.
- [x] Compare every original R1/R2/R3 document requirement to the R0 matrix. Reclassify a row as `requires-implementation` whenever approved behavior is absent or half-delivered; do not use a later-scope label unless the original contract did not authorize it.
- [x] Write a Mini App flow test that enters Home, opens the Project Base, selects a saved Project view, opens a Task Record and returns through existing in-memory navigation without rendering opaque IDs or a raw error.
- [x] Run both tests before repair. The backend fixture initially omitted the relation field from the configured Project view; relation candidates/authorization were correct, so the fixture was corrected and no production repair was necessary.
- [x] Run the focused backend and Mini App tests; safe evidence is backend `1 passed` and Mini App `1 passed`.

### Task 2: Close R1 navigation, queue, view and import evidence without contract expansion

**Files:**
- Modify if RED proves a defect: `backend/app/services/stage07_mini_app.py`, `mini-app/src/app/App.tsx`, `mini-app/src/app/WorkspaceHome.tsx`
- Modify if RED proves a defect: `mini-app/src/app/BaseCanvas.tsx`, `mini-app/src/app/ImportWizard.tsx`
- Test: `backend/tests/unit/test_stage07_mini_app_api.py`
- Test: `mini-app/src/test/workspace-navigation.test.tsx`
- Test: `mini-app/src/test/record-detail.test.tsx`
- Test: `mini-app/src/test/view-builder-*.test.tsx`
- Test: `mini-app/src/test/template-*.test.tsx`, `mini-app/src/test/import-*.test.tsx`

**Consumes:** current safe Home queue destination, Base/Table/View/Record routes, V1 typed presentation and template/import preview/commit routes.

**Produces:** evidence that the existing Customer/Project/Task core can navigate safely, reread conflicts and expose only authorized controls.

- [x] Run the focused current-contract tests for Home queue/draft handoff, Base/Table/View/Record navigation, V1 errors and template/import flow: backend `39 passed`; Mini App `11 files / 53 tests passed`.
- [x] No existing-contract test failed in this pass; therefore no production repair was justified. The Task 1 fixture-only red/green correction remains documented there.
- [x] Run the selected backend V1/template/import tests and disposable PostgreSQL tests: builder `11 passed`; template/import authorization `6 passed`.
- [x] Build the Mini App: `npm.cmd run build` passed.

### Task 3: Obtain R1 safe UI evidence from the built application

**Files:**
- Create temporarily then delete: a synthetic R1 local fixture/proxy only if existing test fixtures cannot start the built app safely.
- Modify: `project-docs/08-implementation/evidence/stage07-r1-customer-project-core.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Modify: `project-docs/08-implementation/STAGE_07_R0_CLOSURE_MATRIX.md`

**Consumes:** Task 1/2 tests and existing safe Mini App routes.

**Produces:** one in-app-Browser observation at required desktop/mobile widths for safe Customer -> Project -> Task navigation, field omission, authorized control visibility, conflict recovery and draft handoff.

- [x] Start a disposable local synthetic fixture with one internal actor; it exposed current safe DTOs only and was not a backend substitute.
- [x] Observe safe Home -> Base -> Project -> Task -> Record Detail -> Project at `1440`, then the Base workbench/tabs/project label at `1280`, `430` and `390`; retain labels/outcomes only.
- [x] Final console scan returned zero `error`/`warn` entries; the in-app Browser session was finalized, fixture process stopped, port `4179` verified closed and source deleted.
- [x] The in-app Browser reached the isolated local fixture. The evidence records its exact synthetic limitation and does not upgrade it to real-backend, identity or Telegram acceptance.

### Task 4: Close R2 governance, draft and employee acceptance gaps

**Files:**
- Modify if RED proves a defect: current owning Governance/Draft/Digital Employee/Team Bot service or Mini App component only.
- Test: `backend/tests/integration/test_stage07_governance_postgres.py`
- Test: `backend/tests/integration/test_stage07_governance_write_postgres.py`
- Test: `backend/tests/integration/test_stage07_draft_employee_hub_postgres.py`
- Test: `backend/tests/integration/test_stage07_digital_employee_management_postgres.py`
- Test: `backend/tests/integration/test_stage07_team_bot_knowledge_postgres.py`
- Test: `mini-app/src/test/governance-*.test.ts`, `mini-app/src/test/draft-employee-*.test.ts`, `mini-app/src/test/digital-employee-management-*.test.ts`, `mini-app/src/test/team-bot-*.test.ts`

**Consumes:** existing fixed actions, safe DTOs, draft terminal services, employee lifecycle/member grants and selected-view Team Bot services.

**Produces:** direct existing-contract safety evidence for hidden-field omission, lifecycle/revocation, draft terminality and non-empty permitted Team Bot summary.

- [x] Run focused unit/integration/UI tests by R2 package, not one broad command: backend unit `41 passed`, disposable PostgreSQL `11 passed`, Mini App `20 files / 62 tests passed`, build passed.
- [x] No existing-contract regression failed in this pass. The real-provider harness itself was created test-first: its missing-module test was red, then preflight/service/API tests were green (`9 passed`) before one live call.
- [x] Run real local PostgreSQL only for rows requiring persistence/concurrency proof: the five R2 integration packages passed `11 passed` against the approved disposable local database.
- [x] Use configured real OpenRouter once for the exact non-empty permitted Team Bot Mini App API route. Contacts/context/summary were `200`; summary was non-empty with one safe citation, audit/agent run present and no record mutation or raw prompt/response persistence. It is route-to-provider evidence, not Browser UI acceptance.
- [x] Reconcile each R2 row with explicit non-goals: no memory/RAG/files/direct writes/Telegram group behavior, schema/API/action permission change, provider selection change or browser persistence was added. See `evidence/stage07-r2-governance-draft-employee.md`.

### Task 5: Complete R3 truth corrections, selected visual matrix and final exit audit

**Files:**
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/STAGE_07_SUBSTAGE_DELIVERY_ROADMAP.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/evidence/stage07-final-acceptance-closure.md`
- Modify: `project-docs/08-implementation/STAGE_07_R0_CLOSURE_MATRIX.md`

**Consumes:** Task 1-4 evidence and the existing bounded S6.3 terminal/cleanup records.

**Produces:** one truthful Stage07 exit state: accepted only when every in-scope row closes; otherwise an explicit residual list with reason, owner and re-entry condition.

- [x] Mark TD007/TD008 real smoke rows as observed bounded evidence and mark S6.3 cleanup complete; retain non-production limitation and do not send again.
- [x] Reconcile R1/R2 evidence, all-width observations and test counts without upgrading unavailable evidence. R1/R2 evidence is recorded separately and residual visual/recovery rows remain explicit.
- [x] Run `git diff --check`, affected focused backend/Mini App regressions, the Mini App build and R1 temporary-fixture cleanup check. `git diff --check` and the R3 stale-state scan pass; R1 fixture source is absent and port `4179` is closed.
- [x] Update the Stage07 status only from direct evidence: the former R1/R2 visual/recovery residuals are now reconciled through the final focused backend/client checks and built-client observations. Stage07 R0-R3 is `accepted-bounded / non-production`; future production and contract-gated customer/group/agent capabilities remain outside this plan.

## Plan Self-Review

- Coverage: every R0 matrix row is owned by R1, R2, R3, `already-closed`, `contract-gated` or later decision.
- Scope: the plan adds no customer-group API, schema or permission behavior.
- Safety: external Telegram delivery is documentation-only; no extra message/retry is allowed.
- Evidence: tests are focused and proportional; visual/real-provider observations are not substituted by mocks.
