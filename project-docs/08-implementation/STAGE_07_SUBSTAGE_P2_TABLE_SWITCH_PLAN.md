# Stage 07 P2: Authorized Table Switch Implementation Plan

> **For agentic workers:** Execute inline with the existing Stage07 worktree. Each code task follows test-first, then focused verification, then the full Stage07 regression gate before its coherent commit.

## Status

- Document status: active approved-scope substage plan
- Scope: Package 2, selecting an already-authorized table inside an already-open Base
- Decision boundary: no new schema, API, permission, cache-technology or visual-direction decision is introduced
- Source alignment: `STAGE_07_SOURCE_OF_TRUTH.md` §4/§5, `STAGE_07_SDD.md` §5, `STAGE_07_BITABLE_WORK_SURFACE.md`, API Contract §4 and the requirement traceability audit Package 2 row “Authorized Base/table/view navigation”

## Goal

Let a user switch among the server-returned tables in an open Base, then render the first authorized saved view of that table using only existing Stage06 read models and the established protected-query rules.

## Architecture

`BaseCanvas` renders the server-returned table summaries as tab controls. `AppContent.selectTable(tableId)` is the sole transition owner: it selects the first returned saved view for that table, requests that table's authorized schema plus the selected view's presentation/first record window, and commits all three only if the current workspace/Base/table request generation is still authoritative. It reuses the existing memory-only TanStack Query client and user/workspace-scoped protected query keys; no table/view model is persisted in browser storage.

## Contract And Security Invariants

- Input tables come only from `GET /bases/{base_id}/tables`; views come only from `GET /bases/{base_id}/views`.
- A table tab must never synthesize a view ID, field list, record list or permission result.
- The default active view is the first server-returned `views` item whose `table_id` equals the selected table ID. If none exists, the canvas shows the existing empty safe state and makes no schema/presentation/record request.
- Schema uses `GET /tables/{table_id}/schema`; presentation and records use the selected server view ID. Every query key stays scoped through `protectedQueryKey({ userId, workspaceId }, ...)`.
- Table changes invalidate the active canvas request generation and create-form request generation. A late response from the previous table, Base or workspace cannot restore stale fields/records/create UI.
- `401` clears all protected queries; `403` clears only the affected workspace and renders the generic denied state. Other errors render the existing generic error state.
- This substage does **not** implement table creation, schema/view builder, filters/sorts/groups, import/template, role/permission editing, Bot/draft actions, deep links or client-side field filtering.

## Interaction Sequence

1. User opens a Base; existing code requests its authorized table and view summaries.
2. `BaseCanvas` shows one tab per returned table and marks only `canvas.table.id` as selected.
3. User activates another tab. `selectTable` increments `canvasRequestVersion` and clears any open record detail or create drawer.
4. The client finds that table's first server-returned saved view. If absent, it commits the safe empty canvas for that table without guessing a view.
5. Otherwise it fetches schema, presentation and the first cursor page in parallel under the new protected keys.
6. Only an unchanged request generation and matching workspace/Base/table may commit the replacement canvas state.
7. The selected table's saved views, field-filtered renderer and record navigation operate exactly as in the existing initial-table path.

## Files And Responsibilities

| File | Change |
| --- | --- |
| `mini-app/src/app/BaseCanvas.tsx` | Render server-returned table summaries as accessible table tabs and dispatch the selected table ID without deriving resources. |
| `mini-app/src/app/App.tsx` | Add the generation-protected `selectTable` transition and provide it to `BaseCanvas`. |
| `mini-app/src/test/view-renderers.test.tsx` | Prove visible tab state and callback dispatch for authorized supplied table summaries. |
| `mini-app/src/test/app-shell.test.tsx` | Prove a second authorized table loads only its server-selected view/schema/records and that old table content does not persist. |
| `project-docs/08-implementation/STAGE_07_PROGRESS.md` | Record implementation/evidence only after verification. |
| `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md` | Update only the affected Package 2 row and remaining evidence limits. |

## Test-First Tasks

### Task 1: Canvas table tabs

- [x] Add a component test with two supplied authorized tables, an active second table and `onSelectTable` spy.
- [x] Assert both table names are buttons, the active table has `aria-selected="true"`, and clicking the first calls `onSelectTable(firstTableId)` exactly once.
- [x] Run `npm.cmd test -- --run src/test/view-renderers.test.tsx` and confirm the test fails because the current canvas only renders one inert table button.
- [x] Add the minimal `BaseCanvasProps.onSelectTable(tableId)` API and tab rendering to pass the test.
- [x] Re-run the focused test and preserve the existing saved-view tab behavior.

### Task 2: Protected table transition

- [x] Add an App integration test whose Base has two authorized tables and one server-returned saved view each.
- [x] Open the Base, activate the second table and assert requests occur for only `/tables/table-2/schema`, `/views/view-2/presentation` and `/views/view-2/records`; assert the second table's record is rendered and the first table's record is absent.
- [x] Run `npm.cmd test -- --run src/test/table-switch.test.tsx` and confirm it fails because the canvas has no table-selection callback.
- [x] Add the minimal generation-protected `selectTable` transition described above. Reuse existing `ApiError`, cancellation and protected-query handling; do not create a new cache/state system.
- [x] Re-run the focused App test and confirm the original navigation/conflict/cursor tests remain green.

### Task 3: Documentation And full verification

- [x] Update progress/audit with exact new evidence and any remaining limitation (notably no builder and no server-side filter/sort/group operation).
- [x] Run `python -m pytest -q` in `backend`, `npm.cmd test -- --run` and `npm.cmd run build` in `mini-app`, plus `git diff --check`.
- [x] Run a disposable local browser fixture for the two-table desktop path. Record only sanitized visible table/view/record labels; stop the fixture and delete all fixture code afterward.
- [x] Commit only the plan, implementation, tests and Stage07 progress/audit changes as one coherent P2 table-switch slice. Do not push without a user request.

## Acceptance Criteria

- The user can select every table that the authorized table-list endpoint returns for the open Base.
- Selecting a table uses only that table's server-returned saved view, schema, presentation and permitted records.
- No view/schema/records query occurs if the selected table has no authorized saved view.
- A prior table/Base/workspace response cannot overwrite a later table selection.
- The UI never presents an unreturned table, raw view config, field permission policy or client-derived records.
- Automated component/integration tests, backend full regression, frontend full regression/build and a disposable fixture browser check provide fresh evidence.
- This substage improves Package 2 only; it is not Stage07 acceptance and does not authorize builder, imports, governance or Package 4 work.
