# Stage 07 Progress

## Status

- Document status: active progress log
- Current Progress: 2026-07-10 Package 1/2 has an implemented, verified vertical path: approved Mini App bootstrap, authorization-filtered Workspace Home, responsive App Shell and workspace switching; permission-filtered Base/table/view canvas; read-only Grid/Kanban/Calendar/Form presentation; Record Detail; and version-aware scalar direct edits. Governance, imports/templates, Bot surface, draft confirmation and final Stage07 acceptance remain incomplete.

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

### 2026-07-10: Version-Aware Direct Record Edit Slice Verified

- Reused the existing Stage06 `PATCH /records/{record_id}` request and its mandatory `expected_version`; no migration, Bot write path, schema contract or permission-model change was introduced.
- Record Detail now offers direct human edits for scalar field types already validated by Stage06 (`text`, status/select-like strings, `date`, `number` and `checkbox`). It submits only values changed by the user, so readable but unmodified fields are never accidentally included in a write request.
- The client passes the authoritative returned version/value back into the current detail and the rendered record window. The stored client response is reduced to keys present in the already server-filtered schema; it does not retain arbitrary fields returned by a primitive update route.
- A `409` version conflict is visibly distinct from a successful save. It remains a manual retry state in this slice; automatic authoritative reload and general protected-query invalidation are still pending.
- Complex `multi_select`, `linked_record`, `json` and `lookup` field values remain read-only in this direct-edit surface rather than being coerced into unsafe string writes. Their typed editor requires a separately documented interaction/data contract.
- Verification: initial focused tests were observed failing for the missing edit UI, all-field payload behavior and string-number serialization; after the implementation, 6 frontend interaction tests and the production Vite build passed. Full frontend regression subsequently passed (`9 passed`), and the full backend regression passed (`406 passed, 19 skipped` for unavailable historical online/local PostgreSQL environment variables).
- Browser QA used a disposable local contract fixture that was removed after the check. On desktop: Home -> Base -> record detail -> direct change of `Ada Co` / `12` to `Ada Labs` / `42` advanced the displayed and grid values to version `4`. At `390x844`, the latest versioned record opened in the full-width detail panel. No relevant browser console warnings or errors were observed; the temporary server and fixture were stopped/removed.

### 2026-07-10: Detailed Stage Documentation Package Requested

- User required Stage07 to follow prior-stage documentation depth, including SDD, BDD, contract, module index, test plan, risks and explicit component interactions.
- The approved design remains queue-first Home, table-first Base canvas, contextual Bot/draft surface, responsive desktop/mobile behavior and fail-closed UI safety.
- Contract extensions for workspace Bot contacts, knowledge sources, memory partitions and Mini App identity remain pending explicit approval.

### 2026-07-10: Requirement Traceability Audit Added

- Added `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`, mapping each required Stage07 package, BDD flow, contract gate, safety requirement and acceptance evidence to actual current source and tests.
- The audit corrects stale planning wording in earlier design documents: a limited Package 1/2 vertical path exists, but it does not prove Package 2 completion and does not authorize Package 3/4 work.
- The audit explicitly records the remaining non-negotiable gates: protected-state/cache architecture decision; typed Form/create and builder interaction specifications; governance permission contract; field-filtered draft review contract; Package 4 Bot/knowledge/memory/Telegram decision; four-width visual QA; and approved real Telegram Mini App smoke.

### 2026-07-10: Authoritative Record Conflict Recovery Verified

- The Stage07 direct-edit path now treats `409` as stale local state: it rereads the authorized record detail and the active saved-view record window, then replaces the drawer/grid with the server-returned version before allowing another edit.
- `403` or `404` during this recovery enters the generic denied boundary instead of retaining the stale record surface. The refreshed record is filtered through the already field-filtered schema before it becomes client state.
- TDD evidence: an application integration test initially exposed a real mount-effect race that could close the editor immediately after an edit click. The synchronization effect now runs only after the record ID/version actually changes. The new application test proves one failed `PATCH`, a detail reread, a view-window reread and authoritative version `4` rendering.
- Verification: `npm.cmd run test:run` => `10 passed`; `npm.cmd run build` passed. Browser QA through a disposable local contract fixture produced `409`, reread `Ada Global`/version `4` into both Grid and Record Detail, displayed the retry notice and had no relevant console warning/error. The fixture/server were deleted/stopped after the run.

### 2026-07-10: Protected Query State Decision Proposal Prepared

- Prepared, but did not implement, `STAGE_07_TECHNICAL_DECISION_001_PROTECTED_QUERY_STATE.md` for user discussion. It recommends a memory-only `@tanstack/react-query` v5 boundary with verified user/workspace-prefixed keys, cancellation/removal on identity/workspace changes and no browser persistence.
- This is a technical selection gate. No dependency, cache migration, local persistence, API/schema/permission change or Package 4 behavior was added by the proposal.

### 2026-07-10: Server-Cursor View Pagination Verified

- Reused the existing Stage06 `next_cursor`/`has_more` view-record contract; no client filter, sort, group, hidden-field reconstruction or API/permission change was added.
- Base Canvas renders a load-more control only when the server returns a cursor. The next request sends that exact encoded cursor, appends only new record IDs and retains the previous authorized window if the next-page request fails so the user can retry.
- `403` during pagination transitions to the generic denied boundary; stale pages cannot overwrite a replaced view/workspace because each completion verifies the active view/cursor before updating local state.
- Verification: component and application tests cover server-cursor forwarding, deduplication and failure/retry presentation; focused frontend run passed `9 passed`; build passed. Browser QA with a disposable local contract fixture loaded page 2 (`Northstar`) at desktop and `390x844` mobile with no relevant console warning/error. The fixture/server were removed after the check.

### 2026-07-10: Protected Query State Decision Approved

- User approved Technical Decision 001. The next subphase may add the documented memory-only `@tanstack/react-query` v5 boundary after red tests prove user/workspace key isolation, request cancellation and 401/403/404 cache removal.
- The approval does not extend to browser persistence, backend API/schema/permission changes, governance, Bot/knowledge/memory or Telegram production verification.

## Next Step

Run the full frontend/backend regression and browser QA for the version-aware edit path. Then prepare and seek approval for the workspace-level Bot, knowledge, memory and Telegram lifecycle contract; complex typed field editors, conflict reload and cache invalidation remain separate, documented work items.
