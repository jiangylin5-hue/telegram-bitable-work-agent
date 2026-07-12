# Stage07 Existing-Contract Navigation Closure BDD and Acceptance

## Status

- Status: approved design, detailed implementation specification pending execution.
- Scope: Home/Bases navigation and safe Base directory over existing contracts only.
- Current Progress: `AppShell`, `api.workspaceBases`, protected query keys and `openBase` already exist. This package makes their connection explicit; no runtime change is claimed in this document.

## BDD Scenarios

### NC-01 Home and Bases are real route states

Given an authenticated active workspace member is on a desktop or mobile shell
When they select Home or Bases
Then the shell exposes the selected memory-only route state with one active navigation control
And Bases causes no server request until it is selected.

### NC-02 Base directory is a closed server projection

Given Bases is selected for Workspace A
When the existing Base directory endpoint succeeds
Then the UI renders only server-returned `{ id, name, source_type, status? }` items
And it never derives a Base from recent Bases, Canvas cache, records, tables, views, query text or a browser-supplied ID.

### NC-03 Selecting a row reuses the existing Base handoff

Given a safe Base row is visible
When the member activates it
Then the app calls existing `openBase(BaseSummary)`
And only the existing authorized table, view, schema and record reads choose the Canvas state.

### NC-04 Directory failure is scoped and fail-closed

Given a Base-directory request is loading
When it receives `401`, active-workspace `403`, `404`, malformed data, network failure or a `5xx`
Then the existing session/workspace/resource cleanup rule applies for `401`/`403`/`404`
And malformed/network/`5xx` display fixed retry copy without a raw response, prior rows or inferred fallback resource.

### NC-05 Workspace replacement discards stale directory data

Given a Workspace A directory request is unresolved
When the user switches to Workspace B or unmounts the shell
Then the old protected key is cancelled/removed and its late result cannot render rows or open a Base in Workspace B.

### NC-06 Empty directory does not invent a capability

Given Workspace A has no permitted Base summaries
When Bases renders
Then it shows a fixed empty state only
And it does not show an unapproved create, import, Bot, queue or management action.

### NC-07 Navigation does not broaden product modules

Given the member selects Bots or More
When no approved matching surface/capability exists
Then this package adds no team Bot directory, personal assistant, knowledge, memory, generic search, queue type or management route.

## State Matrix

| State | Trigger | Rendered data | Required action | Cleanup rule |
| --- | --- | --- | --- | --- |
| `home` | bootstrap/Home selection | existing Home model | open Base or existing approved action | no directory request |
| `bases-loading` | Bases selection | none | none | request scoped to user/workspace |
| `bases-ready` | safe response | safe Base summaries only | open exact row | later reads reauthorize |
| `bases-empty` | permitted empty response | no business data | return Home | no synthetic Base |
| `bases-retryable` | malformed/network/5xx | fixed local copy only | retry exact query | no raw error/past rows |
| `bases-denied` | 403 | generic denied boundary | existing recovery | remove active workspace scope |
| `bases-missing` | 404 | fixed recovery | Home | remove exact directory query |
| `session-expired` | 401 | fixed expiry boundary | existing re-entry | remove all protected Stage07 state |
| `scope-replaced` | workspace switch/unmount | target state only | target Home/Bases action | late old result discarded |

## Acceptance Matrix

| ID | Requirement | Required evidence | Status |
| --- | --- | --- | --- |
| NC-A01 | desktop/mobile Home and Bases controls are real accessible route actions | component and App flow tests | planned |
| NC-A02 | directory uses only `api.workspaceBases` safe projection | parser/API and component negative tests | planned |
| NC-A03 | selection delegates to existing `openBase` and no local table/view is invented | App flow request-order test | planned |
| NC-A04 | empty/retryable/401/403/404 state matrix fails closed | App flow delayed/error tests | planned |
| NC-A05 | workspace replacement/unmount discards old result | delayed promise and cancellation regression | planned |
| NC-A06 | no Bot/queue/management/contract expansion | source/API inventory and review | planned |
| NC-A07 | Mini App build includes the route without type or bundle failure | `npm.cmd run build` | planned |

## Non-Goals

- Assigned, mention and notification queues.
- Team Bot lifecycle, personal assistant, knowledge, memory and contact/group binding.
- URL routing, browser persistence, generic search and telemetry.
- New backend API/schema/permission/dependency work.
- Browser-controlled visual acceptance, external provider, Telegram, staging or production evidence.
