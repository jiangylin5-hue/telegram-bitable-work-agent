# Stage07 Existing-Contract Navigation Closure Design

## Status

- Status: user-approved design direction; implementation requires this specification review and a subsequent detailed plan.
- Scope: make the existing authorized workspace-to-Base navigation path operable from the Stage07 shell without adding a schema, API endpoint, permission rule, persistent browser state or synthetic business queue.
- Current Progress: discovery confirms `AppShell` renders Home/Bases/Bots/More as presentation navigation, while the existing `WorkspaceHome` and `openBase` path already safely opens a selected Base. The approved `GET /workspaces/{workspace_id}/bases` safe summary route is not yet consumed as a shell-level Base directory.
- Source of truth: `AGENTS.md`, `STAGE_07_SOURCE_OF_TRUTH.md`, `STAGE_07_SDD.md`, `STAGE_07_API_DATA_SECURITY_CONTRACT.md` and `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`.

## 1. Product Outcome

An active workspace member can choose Home or Bases from desktop and mobile navigation. Bases opens a server-authorized directory of only the Base summaries already permitted to that member. Selecting an item reuses the existing Base opening flow and its protected reads. Returning to Home must not recreate stale workspace state.

This package closes an interaction gap in the current first product: Home and Base Canvas are real surfaces, but navigation links for Bases are currently only anchors. It does **not** claim that every navigation item implies a product module exists.

## 2. Confirmed Boundary

### In scope

- Explicit client route state limited to `home` or `bases`, held only in React memory.
- One protected Base-directory query using the existing `GET /workspaces/{workspace_id}/bases` response: `{ id, name, source_type, status }`.
- Desktop and mobile Home/Bases navigation controls that use the same route-state transition.
- A server-authorized Base directory with loading, empty, denied, missing-workspace and retryable failure states.
- Reuse of existing `openBase`, cancellation generations, user/workspace query keys and cache removal rules.
- A safe transition from directory selection to the existing Base Canvas; the client must not infer a table, view or record from Base metadata.
- Existing-capability governance entry remains functional; no new management link is implied.

### Explicitly out of scope

- New queue types: assigned records, `@` mentions and controlled notifications require durable models/read contracts and are not inferred from arbitrary record fields.
- Team Bot lifecycle, published contact binding, group handoff, personal assistant context, knowledge retrieval and memory. These remain Package 4 contract-gated.
- Any new Base creation, import/template, view, field or record mutation behavior. Existing surfaces remain independently scoped.
- URL routing, localStorage/sessionStorage persistence, browser-provided authorization claims, a global search implementation, client-side Base filtering that reveals hidden resources, or generic navigation analytics.
- Schema/API/permission changes, new dependencies, public sharing and production/Telegram evidence.

## 3. Alternatives Considered

### A. Existing-contract Base directory (selected)

Use the existing safe Base-summary endpoint and existing `openBase` callback. This is the narrowest coherent product completion: it turns a visible navigation item into a usable authorized route without changing backend authority.

### B. Build a richer Workspace Queue first (not selected)

Expose assigned records, mentions and notification rows. This would better fulfil the eventual Work Queue Atlas composition, but needs new durable source models, row destinations, cursor/read contract and authorization review. It cannot start in this package.

### C. Infer directories and queues from Canvas data (rejected)

Reusing recent Bases, unfiltered records or browser-side merged data would create incomplete navigation and risks revealing inaccessible resources. The browser must consume only the dedicated safe Base summary response.

## 4. Architecture and Data Flow

```text
AppShell desktop/mobile Home or Bases control
-> AppContent route state (memory only)
-> protected query key [stage07, user, workspace, bases]
-> GET /workspaces/{workspace_id}/bases
-> server membership + base.read authorization
-> safe Base summary directory
-> user selects one Base ID
-> existing openBase(BaseSummary)
-> existing tables/views/schema/records protected reads
-> BaseCanvas
```

The directory route receives Base summaries only. It never sees a schema, fields, records, view configuration, policies, owner identity, audit body or queue-internal state. `openBase` remains responsible for resolving the authoritative table/view state from later permitted reads.

## 5. UI Composition

### Desktop

- The left primary navigation exposes Home and Bases as buttons, not fragment anchors.
- The active item reflects the memory-only route state.
- The Base directory uses the established Workspace Ledger visual language: page heading, small safe workspace context, compact Base rows and a clear empty state.
- Selecting a Base has a labelled button/row action and preserves keyboard reachability.

### Mobile

- Home and Bases use the existing bottom navigation positions.
- The same directory is rendered as a single-column mobile list; no hover-only action is required.
- Returning to Home uses the same route state and must leave no modal or stale Base Canvas selection behind.

### Bots and More

- Bots does not become a fake team-Bot directory. It may keep the existing bounded S5 entry only where that entry already has an approved contact/context contract; otherwise it remains unavailable/not selected.
- More opens Governance only when the current server capability permits it. A caller without capability receives no management route from this package.

## 6. State and Failure Matrix

| State | Entry condition | Required user-visible behavior | Cache/authority rule |
| --- | --- | --- | --- |
| `home` | bootstrap or explicit Home action | existing Workspace Home | no new data request beyond Home model |
| `bases-loading` | Bases route selected | fixed loading copy; no synthetic rows | query scoped to verified user/workspace |
| `bases-ready` | safe list returns | rows render only server response | selecting a row calls existing `openBase` |
| `bases-empty` | permitted empty list | fixed explanatory empty state | no fake sample Base/create action |
| `bases-retryable-error` | network/5xx/malformed safe response | fixed retry control; no raw body | retry only reloads exact directory query |
| `bases-403` | active workspace Base read denied | generic denied boundary | remove active workspace protected state; no existence detail |
| `bases-404` | workspace/Base scope disappears | generic safe recovery to Home | remove exact directory key, do not invent another workspace |
| `bases-401` | identity expires | existing expired-session boundary | latch session and remove all Stage07 protected state |
| `workspace-replaced` | switch occurs while directory request is pending | target workspace Home or current route only | cancel/remove old user/workspace directory query; delayed result is discarded |
| `base-opening` | directory row selected | existing Base loading boundary | no directory-derived table/view selection |

## 7. BDD Acceptance

### NC-01: Navigation is a real bounded route

Given an active workspace member sees Home and Bases
When they select Bases on desktop or mobile
Then the route changes in memory and requests only the existing server-authorized Base directory.

### NC-02: Directory contents are server-authorized

Given the server returns permitted Base summaries
When the directory renders
Then every row uses only its safe summary fields and no hidden Base, table, view, record, field, policy or raw error is derived in the browser.

### NC-03: A Base selection uses existing authority

Given a member selects one Base row
When the Base opens
Then the existing `openBase` chain performs its normal authorized table/view/schema/record reads; the directory does not choose a default table or view locally.

### NC-04: Session and scope replacement fail closed

Given a directory request is pending
When workspace replacement, `401`, `403`, `404` or unmount occurs
Then old rows cannot render into the new scope, no stale directory action opens a Base, and the existing protected cleanup boundary is used.

### NC-05: Empty and retryable states do not invent capability

Given a permitted directory is empty or a retryable request fails
When the route renders
Then it uses fixed explanatory/retry copy only. It does not show an unapproved create/manage action or raw server error.

### NC-06: Existing non-navigation boundaries remain intact

Given a member selects Bots or More
When no matching approved capability/surface exists
Then this package adds no team Bot, personal assistant, queue, memory, knowledge, generic search or management capability.

## 8. Test and Evidence Plan

- Add focused API/transport tests only if the existing Base-directory parser/query lacks a current regression; do not duplicate mature endpoint coverage.
- Add component/application tests for desktop/mobile route selection, exact safe parser shape, empty/retry/401/403/404/workspace-replacement behavior and `openBase` handoff.
- Run the affected Mini App tests and production build; run backend tests only if backend source changes (which this design forbids).
- Keep Browser/manual UI inspection as a separately pending user-controlled acceptance step. No browser-control automation is authorized.
- Update the Stage07 traceability audit, acceptance checklist, SDD and progress log with exact evidence. Mark this package `implemented-local` only if its documented tests pass; do not use it to close whole-stage visual or Telegram gates.

## 9. Completion Criteria

The package is complete locally only when all are true:

1. Home and Bases are real, capability-safe navigation controls on desktop and mobile.
2. Base directory has no browser-inferred resource, cache persistence or raw error path.
3. Selection reuses `openBase` and its existing authorization/cancellation behavior.
4. The full state matrix has focused evidence, including delayed workspace replacement.
5. No schema, endpoint, role, permission, dependency or Package 4 feature changed.
6. Documentation names browser/manual visual inspection as pending under the user's no-browser-control boundary.

## 10. Risks and Controls

| Risk | Control |
| --- | --- |
| A directory result from Workspace A renders after Workspace B replaces it | existing protected key prefix, cancellation and generation checks; regression test delayed resolution |
| Browser treats a Base summary as permission to open resources | selection delegates to `openBase`; each later server call reauthorizes |
| Navigation suggests unavailable Bot/queue capabilities | no fake Bot/queue implementation; explicit non-goals and capability gating |
| Scope expands into generic routing/persistence | only two memory route states; no URL/storage router or dependency |
| Documentation overclaims visual evidence | no automated browser control and manual visual QA remains pending |
