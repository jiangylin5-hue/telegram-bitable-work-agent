# Stage07 Mini App UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved responsive Workspace Home and Base/table UI against Stage06 without weakening authorization or controlled-draft behavior.

**Architecture:** Create a new `mini-app/` React + Vite + TypeScript application. Keep routing, API transport, server-filtered view models and feature UI separate. Implement existing Stage06 resources first; do not build queue aggregation, verified Mini App bootstrap, team-Bot scope/lifecycle, knowledge or memory extensions until their API/permission decision is approved.

**Tech Stack:** React, Vite, TypeScript, Tailwind CSS, shadcn/ui, lucide-react, Vitest, React Testing Library, Playwright.

## Global Constraints

- Preserve the confirmed React + Vite + TypeScript + Tailwind + shadcn/ui + lucide-react baseline.
- UI is true white/cool gray/azure, 8px radii, no dark AI-dashboard, gradient, glow or card-wall treatment.
- Browser role claims are never authoritative; render only permission-filtered server models.
- Bot writes remain `record_change_draft` until explicit server confirmation and audit outcome.
- Proposed schema/API/permission extensions require separate user approval before code.

## File Structure

| Path | Responsibility |
| --- | --- |
| `mini-app/src/app/App.tsx` | route composition only |
| `mini-app/src/app/AppShell.tsx` | desktop/mobile navigation and route context |
| `mini-app/src/api/client.ts` | typed HTTP client, identity header adapter and error normalization |
| `mini-app/src/api/stage06.ts` | typed existing Stage06 endpoint calls only |
| `mini-app/src/features/base/*` | Base/table/view/record UI |
| `mini-app/src/features/drafts/*` | draft diff and confirm/reject UI |
| `mini-app/src/features/home/*` | Home rendering after approved queue contract exists |
| `mini-app/src/test/*` | unit/integration tests |
| `mini-app/e2e/*` | Playwright responsive flows |

### Task 1: Create the isolated frontend workspace and test harness

**Files:** Create `mini-app/package.json`, `mini-app/vite.config.ts`, `mini-app/src/main.tsx`, `mini-app/src/test/setup.ts`, `mini-app/src/test/smoke.test.tsx`.

- [ ] Add the Vite React TypeScript project with `dev`, `build`, `test`, `test:coverage` and `test:e2e` scripts.
- [ ] Add Tailwind, shadcn/ui and lucide-react without replacing the backend toolchain.
- [ ] Write a smoke test that renders `App` and asserts the application landmark exists.
- [ ] Run `npm run test -- --run` and `npm run build` from `mini-app`.
- [ ] Commit only the scaffold and test harness.

### Task 2: Implement typed Stage06 transport and safe route context

**Files:** Create `mini-app/src/api/client.ts`, `mini-app/src/api/stage06.ts`, `mini-app/src/api/types.ts`, `mini-app/src/app/RouteState.tsx`; test `mini-app/src/api/stage06.test.ts`.

- [ ] Write failing tests for normalizing `401`, `403`, validation and network failures without response-body leakage.
- [ ] Implement `ApiClient.request<T>(path, init): Promise<T>` and Stage06 calls for workspace, members, Base, table, view records, drafts and audit endpoints already present in backend routes.
- [ ] Implement a route state that accepts only server-returned workspace/resource IDs and clears data on `401` or workspace switch.
- [ ] Run `npm run test -- --run src/api/stage06.test.ts`.
- [ ] Commit typed transport and route state.

### Task 3: Build AppShell and responsive navigation from capability data

**Files:** Create `mini-app/src/app/AppShell.tsx`, `mini-app/src/app/navigation.ts`, `mini-app/src/components/StateScreen.tsx`; test `mini-app/src/app/AppShell.test.tsx`.

- [ ] Write tests covering desktop sidebar, mobile bottom navigation, absent management entry and denied/expired state screens.
- [ ] Implement `AppShell` using only navigation items supplied by an approved capability model; until the bootstrap endpoint is approved, use an explicit local-development adapter guarded from production builds.
- [ ] Implement no-data, denied, expired and retry state screens; never preserve protected page content behind them.
- [ ] Verify at 1440px and 390px with Playwright screenshot assertions.
- [ ] Commit the shell and responsive tests.

### Task 4: Build BaseCanvas and RecordDetail against existing Stage06 resources

**Files:** Create `mini-app/src/features/base/BaseCanvas.tsx`, `RecordGrid.tsx`, `RecordDetail.tsx`, `ViewTabs.tsx`; test `mini-app/src/features/base/BaseCanvas.test.tsx`.

- [ ] Write failing tests for paged grid rendering, hidden-field omission, mobile horizontal access and record-detail opening.
- [ ] Implement Grid first using server field metadata and paginated record windows; do not locally invent field visibility.
- [ ] Add Kanban/Calendar/Form adapters only after their saved-view payloads are confirmed by backend fixtures; keep unavailable views explicit rather than silently substituting cards.
- [ ] Run unit tests and Playwright desktop/mobile visual checks.
- [ ] Commit the table/record vertical slice.

### Task 5: Build DraftConfirmation from existing record-change drafts

**Files:** Create `mini-app/src/features/drafts/DraftConfirmation.tsx`, `DraftDiff.tsx`; test `mini-app/src/features/drafts/DraftConfirmation.test.tsx`.

- [ ] Write failing tests for before/proposed field diff, reject, confirm success, expired and conflict response states.
- [ ] Implement an idempotent confirm/reject action that disables duplicate submission and displays only server terminal state plus audit reference.
- [ ] Reject rendering if the draft contains a field absent from the permitted record schema.
- [ ] Run draft tests and a browser interaction test.
- [ ] Commit the controlled-draft slice.

### Task 6: Contract decision gate for Workspace Home and Mini App bootstrap

**Files:** Modify `project-docs/08-implementation/STAGE_07_API_DATA_SECURITY_CONTRACT.md`; create a separate approved technical-decision document before code changes.

- [ ] Obtain explicit user approval for a verified Mini App/desktop bootstrap endpoint, workspace capability/navigation model and safe queue read model.
- [ ] Define exact request/response schemas, authorization checks, cursor behavior, cache invalidation and audit fields in the decision document.
- [ ] Add backend contract tests before endpoint implementation.
- [ ] Do not begin Home aggregation code until this gate is complete.

### Task 7: Contract decision gate for team Bot contacts, knowledge and memory

**Files:** Modify the Stage07 contract/SDD documents; create migration/API/security decision documents before code changes.

- [ ] Obtain separate explicit approval for employee kind/lifecycle, multi-resource scope, curated knowledge, user memory partitions, retention and Telegram group binding.
- [ ] Define migrations, endpoint contracts, authorization intersection, audit redaction and deletion/retention behavior.
- [ ] Add backend negative tests for cross-workspace, cross-user-memory, hidden-field and chat-scope denial before implementation.
- [ ] Only then implement `BotHub` beyond unavailable-state presentation.

## Plan Self-Review

- Existing Stage06 APIs are used only where current routes exist; queue/bootstrap/Bot extensions are gated rather than assumed.
- Every implementation task has a focused test cycle and commit boundary.
- The plan covers desktop/mobile, authorization, hidden fields, drafts and visual direction; no unapproved schema/API/permission work is scheduled as executable code.
