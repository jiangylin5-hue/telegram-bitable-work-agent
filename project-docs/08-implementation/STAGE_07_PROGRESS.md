# Stage 07 Progress

## Status

- Document status: active progress log
- Current Progress: 2026-07-10 Package 1/2 has an implemented, verified vertical path: approved Mini App bootstrap, authorization-filtered Workspace Home, responsive App Shell and workspace switching; permission-filtered Base/table/view canvas including authorized in-Base table switching; read-only Grid/Kanban/Calendar/Form presentation; Record Detail; version-aware scalar direct edits; and a server-filtered scalar record-create drawer. Protected Query now covers bootstrap, Workspace Home, Base/view opening, table/view/record selection, cursor continuation and create-form loading. Governance, imports/templates, Bot surface, draft confirmation, mobile create browser evidence and final Stage07 acceptance remain incomplete.

## Progress Log

### 2026-07-10: Authorized In-Base Table Switch Is Implemented-Local

- Added an explicit Package 2 substage plan, `STAGE_07_SUBSTAGE_P2_TABLE_SWITCH_PLAN.md`, before code. It uses only the already-approved table/view/schema/presentation/record read contracts; builder, table creation, filters/sorts/groups, import/template, governance and Package 4 remain out of scope.
- `BaseCanvas` now renders only server-returned table summaries as accessible table tabs. Selecting a table chooses only that table's first server-returned saved view, then reads its schema, presentation and first authorized record window under the established protected-query keys.
- If no server-returned saved view belongs to the selected table, the UI enters the existing safe empty canvas without guessing a view ID or issuing schema/presentation/record reads. A table transition clears record-detail/create-drawer state and discards stale responses through the existing canvas/create-form generations.
- Tests cover tab selection, second-table authorized data replacement and the no-saved-view no-request boundary. Fresh checks: backend `407 passed, 19 skipped`; frontend `29 passed`; production build passed. A disposable desktop browser fixture confirmed Customers/All customers/Ada Co becomes Projects/All projects/Apollo, with the old cell absent. The fixture source/server were deleted/stopped.

### 2026-07-10: Server-Filtered Scalar Record Create Is Partial-Local

- Added the approved `GET /tables/{table_id}/create-form` contract to the Mini App and connected its only mutation path to existing `POST /tables/{table_id}/records`.
- The server filters writable first-slice scalar fields and removes raw options. Only validated `status` / `single_select` string choices may reach the browser; all other options are empty. If a required field is inaccessible or unsupported, `can_create: false` renders an unavailable state instead of an inevitably failing POST. This preserves the rule that browser schema visibility never becomes write authority.
- The Base view toolbar exposes the entry only through the application callback. The app loads the protected server model, discards stale workspace/Base/view responses, clears protected state on `401` / `403`, and clears all active-view cursor windows before it reads the authoritative first window after creation.
- Added backend options-redaction/unsupported-required regression coverage; frontend component, integration and renderer tests cover permitted form rendering, unavailable state, required validation, status choice submission, POST payload and view reload. Fresh full checks: backend `407 passed, 19 skipped`; frontend `26 passed`; production build passed.
- Disposable local browser fixture evidence covered desktop create-form rendering, required-field feedback, status select, successful record appearance after reload and the denied create boundary. Fixture server/code were stopped/deleted. The in-app browser did not apply a `390x844` viewport request (reported `1280x720`), therefore mobile create browser QA remains pending and is not counted as acceptance evidence.

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

### 2026-07-10: Protected Query Bootstrap/Home Slice Verified

- Installed the approved `@tanstack/react-query@5.101.2` without a persistence or Devtools plugin. `protectedQuery.ts` defines in-memory `QueryClient` defaults (`staleTime: 0`, `gcTime: 0`, no automatic retry), verified user/workspace-prefixed keys and scoped/all-Stage07 cancellation/removal helpers.
- Migrated Mini App bootstrap and Workspace Home only. Bootstrap receives a query cancellation signal; Home uses the verified identity/workspace key and forwards the signal to `fetch`. A workspace switch increments the request generation, cancels/removes the old workspace scope before starting the target Home request; 401 clears all Stage07 queries and 403 clears the affected workspace scope before a safe denied state.
- No browser storage, cache persister, backend endpoint/schema/permission change, governance screen, Bot feature or Telegram production flow was added. Base/table/view/record reads deliberately remain on the existing local state path until their own migration test slice.
- Verification: Query-key/scope-removal/default tests and API AbortSignal test passed; full frontend suite passed `17 passed`; production build passed. Browser QA switched from `运营中心` to `项目中心`, rendered only the new authorized Base and removed the old Base link with no relevant console warning/error. Static scan found no `localStorage`, `sessionStorage` or `persistQueryClient` usage.

### 2026-07-10: Protected Query Base-Open Slice Verified

- Migrated only the initial Base-open dependency tree to the approved memory-only query boundary: Base tables, Base views, the default table schema, default view presentation and the first cursor record window. All keys retain the verified `userId`/`workspaceId` prefix and each query forwards its cancellation signal to the existing transport; no backend/API/schema/permission change was made.
- A new red application test reproduced an actual stale-data risk: delayed Base tables/views from `workspace-1` could complete after a switch to `workspace-2` and restore the old Base canvas. The test now passes because the canvas request generation is invalidated on workspace switch and the old protected scope is cancelled/removed before the target Home loads.
- Verification: targeted App shell test passed `5 passed`; full frontend suite passed `18 passed`; `npm.cmd run build` and `git diff --check` passed. Browser QA used a disposable fixture to confirm `运营中心` Home -> `客户管理` Base -> `全部客户` Grid, including `Northstar / 进行中`, with no console warning/error. The test fixture and local server were removed/stopped after the check.
- Not yet migrated: direct-edit mutation refresh and conflict recovery. These remain deliberately scoped follow-up migrations, not implied by this Base-open slice.

### 2026-07-10: Protected Query Saved-View Slice Verified

- Migrated saved-view selection to the same verified user/workspace query-key contract. A different table receives its protected schema query; every selected view receives protected presentation and first-window record queries with forwarded cancellation signals.
- A red application test showed that delayed view presentation/records could restore `客户管理` after the user selected another workspace. The canvas request generation and workspace-scope removal now keep the old Base absent until the new workspace Home renders.
- Verification: targeted App shell tests passed `6 passed`; full frontend suite passed `19 passed`; production build and `git diff --check` passed. This slice has no backend/API/schema/permission change and does not imply record-detail, cursor continuation or mutation invalidation migration.

### 2026-07-10: Protected Query Record-Detail Slice Verified

- Migrated record-detail opening to an exact protected record key with the verified user/workspace scope and transport cancellation signal. A dedicated record-request generation prevents a slower earlier record response from replacing a later selection.
- A red application test proved the previous failure mode: delayed `record-1` detail could reopen the old workspace drawer after the user switched workspaces. The green implementation invalidates record requests on switch and also checks the active canvas generation before rendering a detail.
- Verification: targeted App shell tests passed `7 passed`; full frontend suite passed `20 passed`; production build and `git diff --check` passed. This slice does not alter the backend/API/schema/permission model and does not migrate cursor continuation or direct-edit/conflict mutation refresh.

### 2026-07-10: Protected Query Cursor-Continuation Slice Verified

- Migrated every load-more request to the approved verified user/workspace/view/cursor query key and forwarded the cancellation signal to the existing server-cursor transport. The opaque server cursor remains the only cursor source; no client filtering, sorting or cursor construction was added.
- The existing active workspace/view/cursor guard, record-ID deduplication and failure-retry surface remain authoritative. A new red/green integration assertion proves the cursor request carries the cancellation signal.
- Verification: targeted App shell tests passed `7 passed`; full frontend suite passed `20 passed`; production build and `git diff --check` passed. Mutation invalidation and conflict-refresh migration are deliberately still unimplemented.

### 2026-07-10: Protected Query Mutation Refresh Slice Verified

- Existing `PATCH /records/{id}` success now invalidates/removes the exact protected record and active-view first-window keys, then rereads both through the protected transport before replacing the UI. Existing `409` recovery uses the same authority path.
- TDD evidence: a success-save regression first failed because no record/view reread occurred. The green path proves an additional exact record read and updates both grid and detail to the authoritative value; no optimistic write, API, schema or permission change was added.
- Verification: targeted App shell tests passed `7 passed`; full frontend suite passed `20 passed`; production build and `git diff --check` passed.

## Next Step

Complete targeted mutation invalidation/refetch for the existing direct-edit/conflict flow in an independently tested slice. Afterwards, prepare and seek approval for the workspace-level Bot, knowledge, memory and Telegram lifecycle contract; complex typed field editors remain a separate, documented work item.
