# Stage07 Acceptance-Evidence Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete every compatible, already-approved Stage07 function and acceptance condition with executable code/tests/evidence, and leave only genuinely unavailable external authority or explicitly contract-gated work open.

**Architecture:** Preserve the existing FastAPI → SQLAlchemy/PostgreSQL → typed Mini App transport architecture. Browser evidence must exercise the built Mini App against a local FastAPI fixture or real local PostgreSQL where the BDD requires it; it cannot be replaced by a mocked component test. External paths remain single-purpose and bounded: the Team Bot literal UI → provider proof may call the existing safe summary route, while Telegram delivery is not repeated.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, React, Vite, TypeScript, Vitest, Testing Library, existing OpenRouter-compatible Stage06 runtime.

## Global Constraints

- Do not add Customer group binding, customer intake, broad/group Telegram, RAG/memory/files/public sharing, generic Bot direct writes, multi-Base employees, schema/API/permission expansion or production deployment.
- Preserve server-owned authorization, field filtering, version/idempotency semantics, draft-confirmation-only writes, audit and fail-closed safe error rendering.
- Use failing tests before any production behavior change. Evidence-only test/fixture work must still fail first when it detects an unimplemented BDD branch.
- Use only the Codex in-app Browser for browser observation; never control the user's Chrome.
- TD007/TD008 external delivery/identity evidence is historical and cleaned. Do not resend or recreate it.
- Do not claim a BDD row complete until its named test, local PostgreSQL/Built Browser observation or explicitly allowed provider run is recorded by requirement ID.

## Work Packages and Traceability

| Package | Original IDs | Closure artifact | Completion condition |
| --- | --- | --- | --- |
| A | V1-A02/A05/A07/A08/A10; TI-A04/A06/A08 | V1/template test and Browser evidence | denied/invalid/stale/type-specific/four-width behavior uses safe local backend and no raw error/policy/ID leak occurs |
| B | GR-A03; GW-A07; DE-A03/A04/A05/A08/A09; CB-A01--A06; DEM-A01--A10 | governance/draft/context/management test and Browser evidence | BDD normal, denial, conflict/re-read, replacement and responsive paths run against the owning endpoint boundary |
| C | ACD-06/A07/A08; ACD-A03/A10 | PostgreSQL and App-flow evidence | authorization intersection/revocation and delayed replacement are transactionally verified; UI clears only scoped state |
| D | TBK-A01--A09, especially A04--A08 | literal UI → API → real provider record | one non-empty selected view is reread, one safe provider response/citation/audit is produced, no direct record write/raw prompt/response occurs |
| E | all active BDD/SDD/checklist rows | requirement-ID evidence matrix | each original item is `accepted`, `contract-gated`, or `blocked` with executable/reproducible evidence |

### Task 1: Establish the requirement-ID execution ledger

**Files:**
- Modify: `project-docs/08-implementation/STAGE_07_FINAL_AUDIT_REPORT.md`
- Create: `project-docs/08-implementation/evidence/stage07-acceptance-evidence-matrix.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`

**Interfaces:**
- Consumes: original IDs listed in the active V1, Template, Governance, TD005, TD006, TD009, TD010 and TD011 BDDs.
- Produces: one row per ID: `Requirement ID`, `test/browser/provider command`, `evidence path`, `safe-data boundary`, `current disposition`.

- [ ] **Step 1: Write the ledger rows as `pending` before treating any prior aggregate evidence as closing them.**

```markdown
| Requirement ID | Required evidence | Command / observation | Disposition |
| --- | --- | --- | --- |
| TBK-A04--A08 | one literal UI → safe API → provider flow | pending | pending |
```

- [ ] **Step 2: Verify the ledger has every original acceptance ID.**

Run: `rg -n "\| (V1-A|TI-A|GR-A|GW-A|DE-A|CB-A|ACD-A|DEM-A|TBK-A)" project-docs/08-implementation`

Expected: every active BDD row has exactly one ledger row.

### Task 2: Close V1 and Template/Import user-visible invalid, denied and responsive states

**Files:**
- Modify: `mini-app/src/test/view-builder-app-flow.test.tsx` or the owning `view-builder-*.test.tsx` files.
- Modify: `mini-app/src/test/template-import-*.test.tsx`.
- Modify only if a test demonstrates a real gap: `mini-app/src/app/BaseCanvas.tsx`, `mini-app/src/app/App.tsx`, or their existing child components.
- Create: `project-docs/08-implementation/evidence/stage07-v1-template-acceptance.md`.

**Interfaces:**
- Consumes: existing typed `/views/*`, `/tables/*`, template preview/commit endpoints and `ApiError` safe error mapping.
- Produces: fixed local copy for `401/403/404/409/422/503`, authoritative reread only after explicit recovery, and safe panel/sheet operation at `1440`, `1280`, `430`, `390` widths.

- [ ] **Step 1: Add one failing Vitest case for each currently unobserved branch.**

```tsx
test('keeps Builder data closed on a denied V1 context', async () => {
  // return 403 { detail: 'private diagnostic' } from the existing context request
  // assert the fixed denied copy is visible and neither detail nor field ID is rendered
})

test('requires an explicit reread after a stale numeric lookup mutation', async () => {
  // return 409 for the existing typed mutation
  // assert no optimistic success, safe conflict copy, then one authoritative reread after click
})
```

- [ ] **Step 2: Run each new test to prove it fails for the missing UI behavior.**

Run: `npm.cmd run test:run -- src/test/<owning-test>.test.tsx`

Expected: a behavior assertion fails, not a fixture/bootstrap error.

- [ ] **Step 3: Implement only the missing safe state or use the existing state if the RED result shows it was already present but untested.**

```ts
// Existing typed client contract remains the boundary.
// Recovery must call the existing authoritative reread callback and must never render error.detail.
setPanelError('无法继续操作，请重新读取后再试。')
```

- [ ] **Step 4: Verify Vitest, then observe the built Mini App in the in-app Browser at each required width.**

Run: `npm.cmd run test:run -- src/test/<owning-test>.test.tsx`

Expected: pass; captured observation records route, role, width, status, fixed copy and a no-raw-data assertion.

### Task 3: Close Governance, Draft Hub, Context Binding and Employee Management paths

**Files:**
- Modify: `mini-app/src/test/governance-write-app-flow.test.tsx`, `mini-app/src/test/draft-employee-app-flow.test.tsx`, `mini-app/src/test/digital-employee-management-app-flow.test.tsx`, and their owning workbench tests.
- Modify only if RED exposes a real gap: `mini-app/src/app/App.tsx` plus existing `*Workbench.tsx` components.
- Create: `project-docs/08-implementation/evidence/stage07-governance-draft-management-acceptance.md`.

**Interfaces:**
- Consumes: existing governance versioned commands, Draft `confirm/reject`, TD006 opaque `{base_id,view_id,record_id?}` context, TD010 management endpoints.
- Produces: fixed `401/403/404/409/422/503` copy, scoped protected-query cleanup, explicit reread/focus return, one-field-safe Draft display and `draft → active → paused` UI lifecycle.

- [ ] **Step 1: Add failing tests for exact safe terminal behavior.**

```tsx
test('does not render a field-policy 409 diagnostic and rereads only on request', async () => { /* 409 then click reread */ })
test('renders only the permitted draft field after a post-creation field revocation', async () => { /* detail reread */ })
test('returns management from active read-only to paused editable state without a direct invocation', async () => { /* activate then pause */ })
```

- [ ] **Step 2: Run RED tests and repair only demonstrated behavior gaps.**

Run: `npm.cmd run test:run -- src/test/governance-write-app-flow.test.tsx src/test/draft-employee-app-flow.test.tsx src/test/digital-employee-management-app-flow.test.tsx`

Expected: each new assertion fails before its minimal implementation and passes afterwards.

- [ ] **Step 3: Execute existing disposable PostgreSQL suites for command atomicity and add a focused test only for a missing CB/DE/DEM server invariant.**

Run: `$env:STAGE06_DATABASE_URL='<disposable-local-postgres-url>'; python -m pytest tests/integration/test_stage07_governance_postgres.py tests/integration/test_stage07_digital_employee_management_postgres.py -q`

Expected: pass; this is the evidence for lock/idempotency/rollback, not a Browser substitute.

- [ ] **Step 4: Observe desktop and `390x844` management/draft/governance paths in the in-app Browser and record any unavailable server capability as a blocker.**

### Task 4: Close TD009 authorization/replacement and TD011 literal safe UI-to-provider evidence

**Files:**
- Modify: `backend/tests/integration/test_stage07_team_bot_knowledge_postgres.py` and add/extend a TD009 PostgreSQL integration test beside existing `test_stage07_assistant_context_*` coverage.
- Modify: `mini-app/src/test/assistant-context-app-flow.test.tsx`, `mini-app/src/test/team-bot-app-flow.test.tsx`.
- Modify only if RED exposes a real gap: the existing `stage07_assistant_context*`, `stage07_team_bot*` service/API modules and `mini-app/src/app/TeamBotWorkbench.tsx`.
- Modify: `backend/scripts/stage07_team_bot_live_openrouter_smoke.py` only to add a sanitized literal UI transport harness if the existing script cannot consume the generated UI request unchanged.
- Create: `project-docs/08-implementation/evidence/stage07-td009-td011-acceptance.md`.

**Interfaces:**
- TD009 request: `POST /mini-app/digital-employees/{employee_id}/invocations` with the existing fixed `summarize`, `base_id`, `view_id`, `instruction` shape.
- TD011 request: `POST /mini-app/team-bots/{employee_id}/summaries` with existing `{base_id, view_id, instruction}` and `Idempotency-Key`.
- Provider boundary: provider receives only the already permission-filtered fixed window; evidence records outcome/citation/audit IDs only, never secrets, raw prompts, raw responses, real records or Telegram identifiers.

- [ ] **Step 1: Add failing PostgreSQL/App-flow tests for TD009 catalog intersection, revoke-after-selection and delayed replacement.**

```python
def test_assistant_context_revoke_after_selection_denies_and_writes_no_invocation(...):
    # select an allowed view, revoke membership in a separate transaction,
    # invoke the existing route and assert 403 plus no invocation/audit success row
```

```tsx
test('clears only assistant context when selected-view reread returns 404 after workspace replacement', async () => {
  // resolve old response after switch; assert replacement workspace remains usable
})
```

- [ ] **Step 2: Run RED tests, minimally repair any actual authorization/query-cleanup defect, then run the selected PostgreSQL and Mini App tests.**

Run: `python -m pytest tests/integration/test_stage07_team_bot_knowledge_postgres.py tests/integration/test_stage07_assistant_context_postgres.py -q`

Expected: pass with a disposable local PostgreSQL URL; if the TD009 test path needs a different existing file, record the exact path in the evidence matrix rather than creating a parallel service.

- [ ] **Step 3: Run one newly authorized safe literal UI → local API → existing OpenRouter provider flow.**

Required checks: a selected non-empty permitted view is reread at summary time; answer/citations/audit receipt are non-empty and safe; record count/value is unchanged; no raw prompt/response appears in database/evidence; no Telegram call is made.

Run: existing local environment loader plus `python backend/scripts/stage07_team_bot_live_openrouter_smoke.py --ui-transport` only if the script supports an identical typed request; otherwise use the built local UI and inspect its safe terminal receipt.

Expected: one safe success or a documented environment blocker. Never replace it with a fixture response.

### Task 5: Reconcile the original documents and run final independent verification

**Files:**
- Modify: original BDD/SDD/test-plan/checklist files for V1, Template, TD003--TD011 and Stage07 root truth documents.
- Modify: `project-docs/08-implementation/STAGE_07_FINAL_AUDIT_REPORT.md`, `STAGE_07_PROGRESS.md`, `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`, `HANDOFF.md`.

**Interfaces:**
- Consumes: complete evidence matrix and command output from Tasks 1--4.
- Produces: only three final dispositions: `accepted`, `blocked` with cause/owner, or `contract-gated` with no implementation claim.

- [ ] **Step 1: Update every original BDD table row with a direct evidence link and exact disposition.**

- [ ] **Step 2: Run final independent verification.**

Run:

```powershell
Set-Location backend; python -m pytest -q
Set-Location ..\mini-app; npm.cmd run test:run; npm.cmd run build
Set-Location ..; git diff --check
Set-Location backend; alembic heads
```

Expected: no test failure, a single Alembic head, successful Mini App production build and no whitespace error.

- [ ] **Step 3: Write the final report without inferring success from aggregate counts.**

The report must list changed files, each accepted ID and its command/evidence, blocked IDs with exact reason, skipped tests, external actions, cleanup, residual risks and the next permitted substage.

## Plan Self-Review

- Spec coverage: every mandatory gap from `STAGE_07_FINAL_AUDIT_REPORT.md` maps to A--E; contract-gated items are deliberately excluded.
- Placeholder scan: no task may silently substitute a mock/fixture for a BDD-required PostgreSQL, built Browser or literal provider boundary.
- Type consistency: all calls reuse existing typed Stage07 routes and request models; no new endpoint or external capability is introduced.
