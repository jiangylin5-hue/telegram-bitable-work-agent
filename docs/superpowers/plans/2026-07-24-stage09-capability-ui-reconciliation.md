# Stage09 Capability-to-UI Reconciliation Implementation Plan

> **For Codex:** Execute this plan task-by-task. Preserve the current Stage07/08 contracts; do not create browser-side permission, group-context or provider bypasses.

**Goal:** Turn the already implemented Stage07/Stage08 table and agent capabilities into discoverable, controlled Mini App workflows, then verify them in a real browser and deployed environment.

**Architecture:** React workbenches remain thin typed clients of the existing FastAPI safe projections. Existing Stage07 panels remain the only writer for table, draft and governance actions. Stage08 collaboration renders only `AssistantQuerySafeView`; group context stays process-private and becomes visible only through an allowed citation/status signal. Missing lifecycle/bulk/export features remain a separately specified follow-on package.

**Tech Stack:** React, TypeScript, TanStack Query, FastAPI, SQLAlchemy, PostgreSQL, LangGraph, existing Stage07/08 contracts.

---

## Task 1: Capability registry and navigation contracts

**Files:**
- Create: `mini-app/src/app/capability-registry.ts`
- Modify: `mini-app/src/app/AppShell.tsx`
- Modify: `mini-app/src/app/WorkspaceHome.tsx`
- Test: `mini-app/src/test/capability-registry.test.ts`
- Test: `mini-app/src/test/workspace-home.test.tsx`

**Step 1: Write the failing test**

Assert that each actionable table capability maps to a real route/action and each future item has `availability: "planned"` rather than a navigable placeholder.

**Step 2: Run test to verify it fails**

Run `npm.cmd test -- --run src/test/capability-registry.test.ts src/test/workspace-home.test.tsx` from `mini-app`.

**Step 3: Write minimal implementation**

Create a typed registry for existing actions: create Base/table/field/view/record, import, templates, save template, employees, drafts, governance, collaboration, memory and knowledge. Connect only existing App routes or panel open callbacks. Render Chinese labels, short explanations, availability and permission-aware disabled state.

**Step 4: Run test to verify it passes**

Run the focused suite again.

**Step 5: Commit**

`git add mini-app/src/app/capability-registry.ts mini-app/src/app/AppShell.tsx mini-app/src/app/WorkspaceHome.tsx mini-app/src/test/capability-registry.test.ts mini-app/src/test/workspace-home.test.tsx`

`git commit -m "feat(mini-app): expose supported workspace actions"`

## Task 2: Table Operation Center reusing existing controllers

**Files:**
- Create: `mini-app/src/app/TableOperationCenter.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/app/BaseCanvas.tsx`
- Test: `mini-app/src/test/table-operation-center.test.tsx`
- Test: `mini-app/src/test/app-flow.test.tsx`

**Step 1: Write failing tests**

Cover Home and Canvas entry, every available action dispatching its existing panel, and no route/button for lifecycle, export or bulk features that are not implemented.

**Step 2: Run test to verify it fails**

Run `npm.cmd test -- --run src/test/table-operation-center.test.tsx src/test/app-flow.test.tsx`.

**Step 3: Implement**

Build a compact workbench grouped as Base, Table, View, Record and Data exchange. It receives controlled callbacks from `App.tsx`; it must not issue raw fetches or synthesize identifiers. Existing `BuilderCreatePanel`, `FieldBuilderPanel`, `ViewBuilderPanel`, `CreateRecordPanel`, `TemplateImportHub`, `ImportWizard` and `SaveTemplatePanel` remain the execution surfaces.

**Step 4: Verify**

Run focused tests, then `npm.cmd run build`.

## Task 3: Stage08 collaboration workbench

**Files:**
- Create: `mini-app/src/app/stage08-collaboration-types.ts`
- Create: `mini-app/src/app/CollaborationWorkbench.tsx`
- Modify: `mini-app/src/app/api.ts`
- Modify: `mini-app/src/app/App.tsx`
- Test: `mini-app/src/test/stage08-collaboration-api.test.ts`
- Test: `mini-app/src/test/collaboration-workbench.test.tsx`
- Test: `backend/tests/unit/test_stage08_collaboration_api.py` (only if a safe client contract test is absent)

**Step 1: Write failing tests**

Assert request validation, fresh idempotency key, safe response parsing, denied/degraded states, citation label rendering, and a `draft_id` handoff to the existing draft hub. Assert no raw error detail, provider output, UUID in answer or group fragment can render.

**Step 2: Run test to verify it fails**

Run focused Mini App and backend collaboration API tests.

**Step 3: Implement**

Add `api.queryStage08Assistant`. The workbench may send only the approved request shape. The only selectable context is the current authorized workspace, managed employee and optionally already-open current record. Render statuses in Chinese. `group_context` means “已使用受权群聊上下文作为证据”; it never opens group text. `draft_pending` opens existing controlled review.

**Step 4: Verify**

Run focused tests, full Mini App suite, build and selected backend collaboration tests.

## Task 4: Memory and knowledge workbench

**Files:**
- Create: `mini-app/src/app/stage08-memory-knowledge-types.ts`
- Create: `mini-app/src/app/MemoryKnowledgeWorkbench.tsx`
- Modify: `mini-app/src/app/api.ts`
- Modify: `mini-app/src/app/App.tsx`
- Test: `mini-app/src/test/stage08-memory-knowledge-api.test.ts`
- Test: `mini-app/src/test/memory-knowledge-workbench.test.tsx`

**Step 1: Write failing tests**

Cover typed list parsing, explicit user revoke with version, denied/409 reread state, manager-only reindex confirmation, ticket response and no automatic write on page load.

**Step 2: Run test to verify it fails**

Run the focused suite.

**Step 3: Implement**

List only safe memory projections. Explain that memory guides work but table data is the source of changing facts. Revoke requires a deliberate UI confirmation. Reindex only accepts an already safe source choice from existing authorized data; if no safe source directory API exists, keep a read-only availability explanation and do not invent client-side IDs.

**Step 4: Verify**

Run focused tests and build.

## Task 5: Browser and deployment acceptance

**Files:**
- Create: `project-docs/08-implementation/evidence/stage09-capability-ui-reconciliation.md`
- Modify: `project-docs/08-implementation/STAGE_09_CAPABILITY_UI_RECONCILIATION_AUDIT.md`

**Step 1: Local real runtime**

Run real local FastAPI/PostgreSQL and the built Mini App. At 1440, 1280, 430 and 390 widths, exercise operation center, an existing table authoring entry, import dialog, collaboration read-only query, draft handoff, denied/degraded behavior and tooltip/navigation discoverability.

**Step 2: Production-like deployment**

After source tests and review are clean, commit/push. Deploy the sealed release to the existing native server release path, run service health and same-origin API checks, then inspect the real domain in browser. Do not alter unrelated Stage03 Docker or public routes.

**Step 3: Controlled Telegram Mini App pass**

Open the real Mini App from the bot. Verify desktop handoff/window comfort, operation center, real existing workspace navigation and a safe Stage08 read-only query. Do not create a record, import data, revoke memory or confirm a draft unless the user deliberately performs that UI action.

**Step 4: Record exact evidence**

Document commands, statuses, screenshots/DOM observations, API result class and remaining gaps. Mark all no-evidence areas as open rather than inferred.

## Follow-on package: Lifecycle, copy, export and bulk operations

Before implementation write a distinct decision and contract for Base/Table/Field/View/Record rename, copy, archive/delete/recovery, export and bulk changes. It must define versioning, relation integrity, saved-view fallout, field masking, role rules, audit, recovery window, import/export limits and asynchronous jobs. It is deliberately outside this package because no existing API can safely be wired to the UI.
