# Stage 07 Progress

## Status

- Document status: active progress log
- Current Progress: 2026-07-10 Package 1/2 first vertical slice is implemented and verified: approved read-only Mini App bootstrap, authorization-filtered Workspace Home, responsive App Shell and workspace switching. Bitable canvas, governance, Bot surface and final visual-browser QA remain incomplete.

## Progress Log

### 2026-07-10: Package 1 Frontend Scaffold Verified

- Created the isolated `codex/stage07-mini-app-ui` worktree and preserved the Stage06 backend baseline (`400 passed, 19 skipped`).
- Added `mini-app/` React + Vite + TypeScript scaffold with Tailwind Vite integration, lucide-react, shadcn-compatible utility dependencies, Vitest and Testing Library.
- Added the first TDD smoke test for the `工作台` landmark. It was first observed failing because `App` did not exist, then passed after the minimal App/entry/build configuration was added.
- Verified `npm.cmd run test:run` and `npm.cmd run build` from `mini-app`.
- This checkpoint does not implement Workspace Home queues, Stage06 API transport, Base/table/view rendering, governance, Bot contacts, Mini App identity bootstrap or any proposed backend contract extension.

### 2026-07-10: Approved Read-Only Bootstrap And Home Slice Verified

- The user approved the minimal read-only API decision documented in `STAGE_07_API_DATA_SECURITY_CONTRACT.md`: `GET /mini-app/bootstrap` and `GET /workspaces/{workspace_id}/home`. No migration, Stage06 role change or new client-supplied permission claim was introduced.
- Added server-composed bootstrap data: only the verified identity's active memberships, active workspaces and server-derived navigation capabilities are returned. Inactive memberships and inaccessible workspaces are absent.
- Added a Workspace Home view model: active Base metadata and `pending_confirmation` draft summaries only. It deliberately excludes draft before/proposed field values, policies, creator identity and trace IDs.
- Added React API transport, App Shell, desktop sidebar, mobile navigation, Home queue, recent-Base rail, personal-assistant entry and workspace switching. The client renders only server-provided management capabilities and replaces the old Home before loading a switched workspace.
- TDD evidence: three backend contract/security tests first failed with missing routes and then passed; two frontend tests cover server-authorized visibility and workspace switch data replacement.
- Verification: `python -m pytest -q` in `backend` => `403 passed, 19 skipped`; `npm.cmd run test:run` => `2 passed`; `npm.cmd run build` passed.
- Rendered UI QA: the in-app Browser loaded the local contract fixture at desktop and `390x844` mobile viewport. Both displayed meaningful Home content with no Vite overlay or relevant console warnings/errors. Desktop and mobile workspace pickers were each exercised; selecting `项目中心` removed `客户管理` and rendered only `项目追踪`.
- Still not complete: browser screenshot comparison at desktop/mobile dimensions, protected query cache invalidation, Base/table/view canvas, record detail, templates/imports, governance, final draft review, Team Bot/personal assistant contract gate and live Telegram identity verification.

### 2026-07-10: Base Canvas Grid Slice Verified

- User approved the documented, read-only Base navigation extension. Added `GET /workspaces/{workspace_id}/bases`, `GET /bases/{base_id}/tables` and `GET /bases/{base_id}/views`; all reuse Stage06 membership/resource authorization and add no migration or write capability.
- Navigation summaries are deliberately narrower than primitive resources: Base lists exclude description/settings, and saved-view lists exclude `config` and `permission_policy`. Cross-workspace callers receive denial before any summary is returned.
- Home now opens a Base Canvas, loads authorized table/view navigation, then reuses existing schema and paginated view-record APIs to render the selected Grid with field labels and permission-filtered record values.
- Rendered UI QA: Home -> `客户管理` -> `客户表` -> `全部客户` produced the expected Grid at desktop and `390x844`; mobile retains a horizontally scrollable table instead of replacing it with cards. No relevant console warnings/errors were observed.
- Verification so far: 5 Stage07 backend API/security tests and 3 frontend interaction tests pass. Full backend regression and final Stage07 acceptance are still pending this slice's checkpoint.
- Not implemented in this slice: saved Kanban/Calendar/Form renderers. The safe navigation summary correctly excludes view presentation configuration, so choosing grouping/date/form fields in the browser would violate the approved contract. This requires a later separately approved, permission-filtered view-presentation contract.

### 2026-07-10: Field-Filtered View Presentation And Record Detail Slice Verified

- User approved the read-only View Presentation and Record Detail contract. Added `GET /views/{view_id}/presentation` and `GET /records/{record_id}` without schema, migration or write-permission changes.
- Corrected the pre-existing frontend contract leak in `GET /tables/{table_id}/schema`: route-level schemas now use the same field-read decision as view records, view presentation and record detail. Hidden field keys, metadata and values no longer reach a caller who cannot read them.
- Presentation returns normalized, permission-filtered field semantics only: visible field order; optional visible Kanban group field; optional visible Calendar date field; and Form field order. It never returns raw `config` or `permission_policy`.
- Base Canvas now permits switching saved views on the active table, renders Grid/Kanban/Calendar/Form according to normalized server semantics, and opens a field-filtered, versioned Record Detail panel from a record.
- Verification: 16 focused backend tests passed; 6 frontend interaction/render tests passed; browser QA confirmed desktop Grid -> Kanban -> Record Detail and `390x844` full-screen mobile Record Detail with no relevant console warnings/errors.
- Still incomplete: Form submission/editing workflow, filter/sort/group mutations, cursor pagination controls, conflict recovery, cache invalidation, imports/templates, governance and all Digital Employee/draft confirmation surfaces. Those must continue to use explicit authorized contracts and are not claimed by this slice.

### 2026-07-10: Detailed Stage Documentation Package Requested

- User required Stage07 to follow prior-stage documentation depth, including SDD, BDD, contract, module index, test plan, risks and explicit component interactions.
- The approved design remains queue-first Home, table-first Base canvas, contextual Bot/draft surface, responsive desktop/mobile behavior and fail-closed UI safety.
- Contract extensions for workspace Bot contacts, knowledge sources, memory partitions and Mini App identity remain pending explicit approval.

## Next Step

Implement the permission-filtered Base/table/view work surface without expanding the approved schema/API boundary. Before Package 4, prepare and seek approval for the workspace-level Bot, knowledge, memory and Telegram lifecycle contract.
