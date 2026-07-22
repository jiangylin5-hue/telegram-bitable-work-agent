# Stage07 Visual Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every existing Stage07 Mini App screen faithfully follow the approved Work Queue Atlas, Workspace Ledger, Conversation Desk and new Digital Employee visual references without changing the backend contract.

**Architecture:** Retain the current React component hierarchy, query lifecycle and API adapter. Consolidate the visual language as a scoped CSS token layer and reusable shell/rail primitives, then restyle each existing functional surface around its matching reference. The Digital Employee management adapter remains the existing TD010 browser-safe contract; only its route presentation and visual layout change.

**Tech Stack:** React, TypeScript, Vite, Vitest, Testing Library, CSS, existing lucide-react icon set, FastAPI-backed existing Stage07 Mini App routes.

## Global Constraints

- The generated and selected Digital Employee image must exist at `project-docs/08-implementation/assets/stage07/digital-employee-workbench-reference-v1.png` before Task 2 begins.
- Do not add or change database migrations, FastAPI routes, API DTOs, permissions, capability fields, Telegram routing, provider settings or deployment files.
- Preserve existing test-visible labels, aria roles, focus-return behavior, mutation confirmation paths, protected-query cleanup and server-authoritative rereads.
- The visual baseline is light, dense and table-first: true white, cool gray dividers, restrained azure selection, 8px-radius controls, no gradients/glows/card walls/wizard treatment.
- Validate 1440px, 1280px, 430px and 390px; keep each current user workflow functioning.

## File Structure

| File | Responsibility |
| --- | --- |
| `mini-app/src/styles.css` | shared design tokens, responsive shell rules and each restyled surface selector |
| `mini-app/src/app/AppShell.tsx` | persistent navigation and active workspace chrome; it does not create a cross-Base Digital Employee route |
| `mini-app/src/app/WorkspaceHome.tsx` | Work Queue Atlas hierarchy and durable queue/recent-Base/assistant layout |
| `mini-app/src/app/BaseCanvas.tsx` | Workspace Ledger toolbar, table/view band and dense canvas structure |
| `mini-app/src/app/TeamBotWorkbench.tsx` | Conversation Desk team-assistant layout |
| `mini-app/src/app/AssistantContextWorkbench.tsx` | Conversation Desk personal-assistant layout |
| `mini-app/src/app/DraftEmployeeHub.tsx` | contextual draft review/confirmation rail |
| `mini-app/src/app/DigitalEmployeeManagementWorkbench.tsx` | Digital Employee directory, central work-scope canvas and status/audit rail |
| `mini-app/src/app/App.tsx` | visual-surface entry/return focus only; no API/authority behavior change |
| `mini-app/src/test/visual-rebaseline.test.tsx` | static semantic regression coverage for all reference families |
| existing component tests under `mini-app/src/test/` | preserved behavior and targeted keyboard/mobile regression assertions |
| `mini-app/design-qa.md` | same-viewport visual comparison results and remaining P3 notes |
| `project-docs/08-implementation/STAGE_07_VISUAL_REFERENCE_MANIFEST.md` | approved new Digital Employee asset and comparison role after generation |

### Task 1: Create the selected Digital Employee visual target and record the visual baseline

**Files:**
- Create: `project-docs/08-implementation/assets/stage07/digital-employee-workbench-reference-v1.png`
- Modify: `project-docs/08-implementation/STAGE_07_VISUAL_REFERENCE_MANIFEST.md`
- Modify: `docs/superpowers/specs/2026-07-16-stage07-visual-rebaseline-design.md`

**Interfaces:**
- Consumes: the three retained Stage07 reference images and TD010's existing management fields.
- Produces: one selected desktop image target with no implied contract change.

- [ ] **Step 1: Generate one original 16:10 desktop Digital Employee management mock.**

Run the configured image-generation command with an original prompt that includes a 64px global rail, 260px employee directory, central profile/work-scope canvas, 300px confirmation/audit rail, Chinese labels for `数字员工`, `运营协调员`, `今日待处理事项`, `已授权的数据与视图`, `运行状态`, `等待确认的草稿` and `创建数字员工`, and the light Stage07 visual contract.

- [ ] **Step 2: Inspect the generated image before accepting it.**

Reject it if it contains a vendor mark, copied identity, dark/purple AI presentation, gradient/glow treatment, a card-wall dashboard or an unreadable employee-management hierarchy.

- [ ] **Step 3: Copy the selected file into the Stage07 asset directory and register it.**

Add the asset table row with the exact path, `Digital Employee workbench` visual role and the QA target `TD010 management at desktop widths`.

- [ ] **Step 4: Verify asset reachability.**

Run: `Test-Path project-docs/08-implementation/assets/stage07/digital-employee-workbench-reference-v1.png`

Expected: `True`.

### Task 2: Establish shared visual tokens and shell semantics

**Files:**
- Modify: `mini-app/src/styles.css`
- Modify: `mini-app/src/app/AppShell.tsx`
- Create: `mini-app/src/test/visual-rebaseline.test.tsx`
- Test: `mini-app/src/test/app-shell.test.tsx`

**Interfaces:**
- Consumes: `AppShellRoute`, existing workspace capability hints and current navigation callbacks.
- Produces: a named light-workbench token layer and stable shell landmarks used by every later task, while the existing Base-bound employee-management entry remains authoritative.

- [ ] **Step 1: Write failing shell/reference coverage.**

```tsx
it('exposes the compact workbench shell without introducing a global employee-management action', () => {
  render(<AppShell workspace={workspace} workspaces={[workspace]} activeRoute="home" onWorkspaceChange={vi.fn()} onNavigate={vi.fn()}>{<main>content</main>}</AppShell>)
  expect(screen.getByLabelText('主导航')).toBeVisible()
  expect(screen.queryByRole('button', { name: '数字员工管理' })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run the test and confirm it fails before changing the shell.**

Run: `npm.cmd test -- --run src/test/visual-rebaseline.test.tsx src/test/app-shell.test.tsx`

Expected: baseline passes before shell restyling; any later failure proves the visual work introduced an unauthorized global management action.

- [ ] **Step 3: Add the token layer and shell entry without changing route authority.**

Define CSS custom properties for `--surface-canvas`, `--surface-subtle`, `--line-subtle`, `--text-primary`, `--text-secondary`, `--accent-azure`, `--radius-control` and `--shadow-floating`. Rework `AppShell` into a narrow desktop rail, content canvas and mobile dock without adding an employee-management callback, endpoint or cross-Base route. Keep the existing management entry in the Base Canvas.

- [ ] **Step 4: Run the focused tests.**

Run: `npm.cmd test -- --run src/test/visual-rebaseline.test.tsx src/test/app-shell.test.tsx src/test/app-shell-navigation.test.tsx`

Expected: all selected tests pass.

### Task 3: Rebuild Workspace Home and Base Canvas around the two table-product references

**Files:**
- Modify: `mini-app/src/app/WorkspaceHome.tsx`
- Modify: `mini-app/src/app/BaseCanvas.tsx`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/workspace-navigation.test.tsx`
- Test: `mini-app/src/test/table-switch.test.tsx`
- Test: `mini-app/src/test/view-renderers.test.tsx`

**Interfaces:**
- Consumes: existing `WorkspaceHomeData`, `BaseSummary`, view renderer data and current callbacks.
- Produces: a queue-first home and table-first dense canvas with no changed data flow.

- [ ] **Step 1: Write a failing behavior-preservation test for the queue and grid entry.**

```tsx
it('keeps durable queue and Base destinations interactive after the visual rebuild', async () => {
  render(<WorkspaceHome home={home} workspace={workspace} onOpenBase={openBase} onOpenDraftHub={openDraft} />)
  await user.click(screen.getByRole('link', { name: /查看草稿/ }))
  expect(openDraft).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('link', { name: recentBase.name }))
  expect(openBase).toHaveBeenCalledWith(recentBase)
})
```

- [ ] **Step 2: Run it and confirm it fails only when markup changes remove the existing destinations.**

Run: `npm.cmd test -- --run src/test/workspace-navigation.test.tsx src/test/table-switch.test.tsx src/test/view-renderers.test.tsx`

Expected: baseline passes before the redesign; any failure after markup work identifies a removed interaction.

- [ ] **Step 3: Implement the two matching visual structures.**

Keep the Home queue rows table-aligned, move Base previews to a slim supporting rail and make the assistant dock informational. Keep Base Canvas title, saved-view selector and schema controls in one compact band above the high-density grid. Do not turn data rows into cards or move builder actions away from the table/view controls.

- [ ] **Step 4: Run focused behavior tests.**

Run: `npm.cmd test -- --run src/test/workspace-navigation.test.tsx src/test/base-canvas-management.test.tsx src/test/table-switch.test.tsx src/test/view-renderers.test.tsx`

Expected: all selected tests pass.

### Task 4: Convert assistant and draft surfaces from wizard-modal styling to Conversation Desk

**Files:**
- Modify: `mini-app/src/app/TeamBotWorkbench.tsx`
- Modify: `mini-app/src/app/AssistantContextWorkbench.tsx`
- Modify: `mini-app/src/app/DraftEmployeeHub.tsx`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/team-bot-workbench.test.tsx`
- Test: `mini-app/src/test/assistant-context-workbench.test.tsx`
- Test: `mini-app/src/test/draft-employee-hub.test.tsx`

**Interfaces:**
- Consumes: existing safe contacts, selected view, summary, draft detail and confirm/reject callbacks.
- Produces: a calm assistant/contact navigation, context/conversation canvas and review rail while retaining existing safe action buttons.

- [ ] **Step 1: Write a failing landmark/order test for the three-pane Conversation Desk.**

```tsx
it('keeps contact choice, selected context and confirmation review as separate labelled regions', () => {
  render(<DraftEmployeeHub {...props} />)
  expect(screen.getByLabelText('员工联系人')).toBeVisible()
  expect(screen.getByLabelText('当前上下文')).toBeVisible()
  expect(screen.getByLabelText('草稿确认')).toBeVisible()
})
```

- [ ] **Step 2: Run the focused tests and record existing accessibility labels.**

Run: `npm.cmd test -- --run src/test/team-bot-workbench.test.tsx src/test/assistant-context-workbench.test.tsx src/test/draft-employee-hub.test.tsx`

Expected: baseline passes before replacement; after markup changes, test failures identify lost labels or disabled actions.

- [ ] **Step 3: Implement Conversation Desk visual hierarchy.**

Use a persistent contact rail, central selected context/conversation surface and right review rail at desktop width. At mobile width, stack the same labelled regions in order and retain visible confirm/reject semantics. Remove `STEP` copy, thick accent strips and generic wizard card treatment.

- [ ] **Step 4: Run focused behavior and query tests.**

Run: `npm.cmd test -- --run src/test/team-bot-workbench.test.tsx src/test/team-bot-app-flow.test.tsx src/test/assistant-context-workbench.test.tsx src/test/assistant-context-app-flow.test.tsx src/test/draft-employee-hub.test.tsx src/test/draft-employee-app-flow.test.tsx`

Expected: all selected tests pass.

### Task 5: Implement the Digital Employee management workbench from its selected reference

**Files:**
- Modify: `mini-app/src/app/DigitalEmployeeManagementWorkbench.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/digital-employee-management-workbench.test.tsx`
- Test: `mini-app/src/test/digital-employee-management-app-flow.test.tsx`

**Interfaces:**
- Consumes: existing `ManagedEmployeeManagementContext`, `ManagedEmployeeDirectory`, `ManagedEmployeeDetail`, lifecycle callbacks and focus-return trigger.
- Produces: a desktop directory/employee-canvas/audit-rail workbench and an ordered mobile equivalent; it makes no new management request.

- [ ] **Step 1: Write failing reference-specific semantic coverage.**

```tsx
it('separates directory, work scope and review rail without widening management actions', () => {
  render(<DigitalEmployeeManagementWorkbench {...props} />)
  expect(screen.getByLabelText('员工目录')).toBeVisible()
  expect(screen.getByLabelText('员工配置')).toBeVisible()
  expect(screen.getByLabelText('运行状态与审计')).toBeVisible()
  expect(screen.getByRole('button', { name: '激活员工' })).toBeDisabled()
})
```

- [ ] **Step 2: Run the employee tests and confirm the pre-change lifecycle guard.**

Run: `npm.cmd test -- --run src/test/digital-employee-management-workbench.test.tsx src/test/digital-employee-management-app-flow.test.tsx src/test/digital-employee-management-query.test.ts`

Expected: current safety tests pass; the new region assertion fails until the workbench has its review rail.

- [ ] **Step 3: Implement the selected four-column desktop composition.**

Use the current directory for employee selection, preserve editable name/description/scope/intents/access-mode/member controls in the central work surface, and derive the rail only from already returned safe status/version/member/scope data. Keep create, save, grant replacement, activate, pause, retry and close handlers unchanged. The App entry must restore focus to its trigger after close.

- [ ] **Step 4: Run all TD010 frontend tests.**

Run: `npm.cmd test -- --run src/test/digital-employee-management-api.test.ts src/test/digital-employee-management-query.test.ts src/test/digital-employee-management-workbench.test.tsx src/test/digital-employee-management-app-flow.test.tsx`

Expected: all selected tests pass.

### Task 6: Apply the same light-workbench system to all remaining current panels and mobile states

**Files:**
- Modify: `mini-app/src/app/BaseDirectory.tsx`
- Modify: `mini-app/src/app/BuilderCreatePanel.tsx`
- Modify: `mini-app/src/app/FieldBuilderPanel.tsx`
- Modify: `mini-app/src/app/RelationLookupFieldBuilderPanel.tsx`
- Modify: `mini-app/src/app/ViewBuilderPanel.tsx`
- Modify: `mini-app/src/app/TemplateImportHub.tsx`
- Modify: `mini-app/src/app/ImportWizard.tsx`
- Modify: `mini-app/src/app/SaveTemplatePanel.tsx`
- Modify: `mini-app/src/app/GovernanceWorkbench.tsx`
- Modify: `mini-app/src/app/GovernanceWriteWorkbench.tsx`
- Modify: `mini-app/src/app/RecordDetail.tsx`
- Modify: `mini-app/src/app/CreateRecordPanel.tsx`
- Modify: `mini-app/src/styles.css`
- Test: all matching `mini-app/src/test/*` component and app-flow tests

**Interfaces:**
- Consumes: every existing callback/aria label/capability gate.
- Produces: consistent drawers, sheets, editors, empty states and errors without generic card/wizard treatment.

- [ ] **Step 1: Run the complete frontend suite as the interaction baseline.**

Run: `npm.cmd test -- --run`

Expected: all current tests pass before restyling the remaining surfaces.

- [ ] **Step 2: Restyle panels by functional family.**

Keep table/schema tools adjacent to the canvas, make import/template flows use restrained task sheets rather than card stacks, make governance a member/permission ledger, and preserve record detail/create as focused contextual panels. On mobile, convert modal dimensions to full-height sheets only where existing behavior requires it, preserving 44px minimum interactive control heights.

- [ ] **Step 3: Run the complete suite after each functional family.**

Run: `npm.cmd test -- --run src/test/field-builder-panel.test.tsx src/test/view-builder-panel.test.tsx src/test/template-import-query.test.ts src/test/governance-workbench.test.tsx src/test/record-detail.test.tsx`

Expected: selected tests pass after the matching family is complete.

- [ ] **Step 4: Run the whole frontend suite.**

Run: `npm.cmd test -- --run`

Expected: all tests pass.

### Task 7: Compare the rendered app against the four references and close quality gates

**Files:**
- Modify: `mini-app/design-qa.md`
- Modify: `project-docs/08-implementation/evidence/stage07-ui-closure-regressions-2026-07-16.md`
- Modify: `project-docs/08-implementation/STAGE_07_VISUAL_REFERENCE_MANIFEST.md`

**Interfaces:**
- Consumes: four source assets, local rendered states and existing frontend workflows.
- Produces: evidence-backed visual status; it does not alter acceptance status for untested Telegram/provider/deployment paths.

- [ ] **Step 1: Start local frontend and backend only with safe local fixtures.**

Run: `npm.cmd run dev -- --host 127.0.0.1 --port 5173`

Expected: Vite reports the local development server is ready; do not use a user Chrome profile.

- [ ] **Step 2: Capture comparable desktop states.**

Capture Home at 1440px against Work Queue Atlas, Base Canvas at 1440px against Workspace Ledger, Team Bot/Draft at 1440px against Conversation Desk, and Digital Employee management at 1440px against its selected generated reference.

- [ ] **Step 3: Capture responsive states.**

Capture each covered family at 1280px, 430px and 390px. Verify no page-level horizontal scroll, clipped primary action, lost focus target or relevant browser console error.

- [ ] **Step 4: Write `mini-app/design-qa.md` with explicit pass/fail results.**

Mark `final result: passed` only when every P0/P1/P2 visual mismatch is fixed. If a source asset, local fixture or browser comparison is unavailable, write `final result: blocked` with the concrete missing item.

- [ ] **Step 5: Run final mechanical verification.**

Run: `npm.cmd test -- --run; npm.cmd run build; git diff --check`

Expected: all tests pass, the TypeScript/Vite production build succeeds and `git diff --check` reports no whitespace errors.

## Plan Self-Review

- The plan covers all current frontend page families, including the previously drifting Team Bot/draft surfaces and the new Digital Employee reference.
- The only prerequisite outside local code is the selected generated Digital Employee image; it is explicitly task one and no code task begins before it exists.
- Every behavior-preserving task names its files, test command and expected result. No backend or authority surface is included.
