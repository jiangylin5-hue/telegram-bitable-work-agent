# Stage 07 Technical Decision 001: Protected Query State

## Status

- Decision status: approved by user on 2026-07-10 — implementation may begin only within this document's scope
- Scope: Mini App/desktop React server-state cache, request cancellation, workspace/session/revocation clearing and mutation refresh
- Non-scope: backend schema/API/role/permission changes; local persistence; Bot/knowledge/memory implementation
- Implementation progress: bootstrap, Workspace Home, the initial Base-open dependency tree, saved-view switching, record-detail opening, cursor follow-up pages and direct-edit/conflict refresh are migrated. The Base-open tree covers Base tables/views, the default table schema, the default view presentation and every fetched cursor window. Direct-record continuation now observes a session-expiry latch and request generations; record/view disposal cancels the exact rereads. This decision is implemented for the approved existing Package 1/2 read/edit path; later Package 2/3/4 contracts remain separate.

## 1. Problem

The current Mini App uses hand-managed `useState` composition in `App.tsx`. It is sufficient for the implemented vertical path, but it cannot reliably provide all Stage07 requirements as more routes arrive:

- workspace/resource-keyed protected state;
- cancellation during workspace switch or route disposal;
- removal on identity expiry, membership revocation and 403 denial;
- exact refresh after record, import, template, governance and draft mutations;
- consistent loading/error/retry semantics without retaining stale privileged data.

The Stage07 SDD, API/data/security contract, App Shell module and requirement audit all require this boundary. This decision selects an implementation mechanism; it does not relax any server-side authorization rule.

## 2. Decision Drivers

| Driver | Required result |
| --- | --- |
| Permission safety | No protected payload survives user/workspace/session boundary changes. |
| Scope correctness | Every cache key is isolated by verified identity and workspace before resource-specific IDs. |
| Cancellation | In-flight requests cannot repopulate a previous workspace after a switch or revocation. |
| Mutation integrity | Record/draft/import/governance results come from the server; affected data is refetched or precisely replaced. |
| Mature reuse | Use a maintained React server-state library rather than invent a query/cache framework. |
| No persistence | No protected query cache is written to localStorage, sessionStorage, IndexedDB, telemetry or URL state. |

## 3. Options Considered

| Option | Assessment | Decision |
| --- | --- | --- |
| A. `@tanstack/react-query` v5, memory-only | Mature query keys, targeted invalidation, mutation lifecycle and AbortSignal support directly cover Stage07 needs. | **Recommended** |
| B. Continue handcrafted `useState`/effects | Requires custom cache keys, cancellation, eviction, invalidation and race handling; the current mount-effect race already demonstrated this risk. | Rejected |
| C. Build an internal cache/reducer library | Duplicates mature behavior, broadens maintenance/security surface and violates the reuse preference. | Rejected |
| D. Persist any client query cache | Revocation/session risk; forbidden by API/data/security contract. | Rejected |

## 4. Recommended Design (Option A)

### 4.1 Library Boundary

- Add `@tanstack/react-query` v5 only for **server state**.
- Keep ephemeral presentation state local: open drawer, edit mode, unsaved input, dialog visibility and mobile-sheet state.
- Do not install a query persistence plugin or browser Devtools in the production bundle.
- Continue using the existing typed `api` transport; query functions pass the library-provided `AbortSignal` into `fetch`.

### 4.2 Key Contract

All protected keys begin with a stable Stage07 namespace, verified `userId`, then `workspaceId`:

```text
['stage07', userId, workspaceId, 'home']
['stage07', userId, workspaceId, 'base', baseId, 'tables']
['stage07', userId, workspaceId, 'base', baseId, 'views']
['stage07', userId, workspaceId, 'table', tableId, 'schema']
['stage07', userId, workspaceId, 'view', viewId, 'presentation']
['stage07', userId, workspaceId, 'view', viewId, 'records', cursor]
['stage07', userId, workspaceId, 'record', recordId]
```

The client never uses a role, URL hint, Base name or unverified Telegram value as a key authority dimension.

### 4.3 Security Lifecycle

| Event | Required cache behavior |
| --- | --- |
| Workspace switch | cancel and remove the previous `[stage07, userId, oldWorkspaceId]` prefix before loading the target workspace. |
| Identity change, expiry or logout | cancel all Stage07 queries and remove all Stage07 cache before restarting bootstrap. |
| 401 | treat as expired identity: cancel/remove Stage07 cache and return the safe session-recovery surface. |
| 403 | remove the affected workspace prefix; render generic denied state without resource existence inference. |
| 404 on a current resource | remove the exact resource and route to safe recovery; do not retain stale detail values. |
| Component unmount/view replacement | consume `AbortSignal`; obsolete request completions cannot restore a discarded screen. |

Protected queries are memory-only, `staleTime: 0`, `gcTime: 0` once unobserved, and do not retry authorization failures. This favors correct authorization/reload behavior over avoiding an additional request when a user returns to a previous protected screen.

### 4.4 Mutation Rules

- Direct human record edits keep `expected_version`; success uses the authoritative response only after filtering it through the permitted schema.
- A record mutation invalidates/refetches the exact record and active-view record window. A version conflict follows the same authoritative reload path already implemented.
- Import/template/draft/governance mutations receive an `Idempotency-Key` only where their existing Stage06 endpoint requires it; success invalidates exact workspace/Base/table/view prefixes.
- No Bot, draft, permission or confirmation mutation is added by this decision. Their contracts remain independently gated.

### 4.5 Failure Policy

- `401`, `403`, `404` do not retry automatically.
- Transient network failures may retry once only if the query remains current and has no authorization error.
- A mutation never displays success before its server response; idempotent replay displays the returned terminal state.
- Error telemetry may record route/resource type/status code only; it must not contain record values, field names that were not returned, prompts, Bot text, knowledge content or memory.

## 5. Implementation Sequence After Approval

1. Write red tests for workspace-switch cancellation/removal, 401/403 eviction, cursor key isolation and no local persistence.
2. Add the dependency and a memory-only `QueryClient` boundary.
3. Refactor bootstrap/Home/Base/view/record reads in small vertical slices, retaining existing server contracts and field filtering.
4. Migrate the existing record-edit/conflict path to targeted invalidation/refetch.
5. Browser-test switch, denied, conflict and mobile detail paths; run full frontend/backend regression.
6. Update the Stage07 requirement audit with actual evidence before moving to Form/create or builder work.

## 6. Acceptance Criteria

- Tests prove a previous workspace's queries are cancelled and removed before target content renders.
- Tests prove 401/403/404 remove the applicable protected state and never show old record/base values.
- Query keys always contain verified user/workspace IDs before resource IDs/cursors.
- No persistence integration, storage write or raw protected payload appears in client telemetry.
- Existing 409 record conflict recovery and field filtering continue to pass.
- Browser QA covers desktop and mobile workspace switch, denied/revoked recovery and record conflict states.

## 7. Approval Boundary

The user approved Option A on 2026-07-10. The approval authorizes only adding `@tanstack/react-query` v5 as a memory-only protected server-state layer and refactoring the already-approved Package 1/2 reads to it. It does **not** authorize a backend contract change, local persistence, governance permissions, Bot/knowledge/memory work or Telegram production verification.

## 8. Mature Architecture References

- TanStack Query React official documentation: [queries and query keys](https://tanstack.com/query/latest/docs/framework/react/guides/queries), [targeted invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation), and [AbortSignal cancellation](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation).
- The proposal deliberately applies only those maintained server-state primitives; it does not copy a third-party product UI or introduce an unreviewed persistence layer.

## 9. Implemented Slice Evidence

- The first Base-open query migration uses the approved verified-user/workspace keys for Base tables, Base views, table schema, view presentation and the first view-record window. Each query function receives and forwards TanStack Query's `AbortSignal` to the existing typed transport.
- A test first demonstrated the actual race: delayed tables/views for `workspace-1` could restore the previous Base canvas after a user selected `workspace-2`. The migration adds a canvas request generation boundary and query cancellation/removal on the old workspace scope; the test now proves the new workspace Home remains visible when the delayed responses resolve.
- Saved-view switching now applies the same protected keys and canvas request generation. A red/green application test proves delayed view presentation/record responses cannot restore the prior Base after a workspace switch.
- Record detail opening now uses the same protected scope with an exact record key and a dedicated request generation. A red/green application test proves a delayed record response cannot reopen the old workspace's detail panel after a workspace switch.
- Cursor continuation now uses a protected view-record key containing the opaque server cursor and forwards the cancellation signal. Its existing record-ID deduplication and active-view/cursor state guard remain intact.
- Existing direct record edits and `409` conflict recovery now invalidate/remove the exact record and active-view first-window keys before authority is reread through the protected query transport. No optimistic client write or new mutation contract was introduced.
- A 2026-07-11 red/green repair closes direct-mutation races within this approved scope: 401 latches the session and invalidates all request generations before cache removal; a late same-workspace 403 fails closed even if a record/view generation changed; TanStack `CancelledError` is recognized as cancellation; 404, detail close and table/view/record replacement cancel/remove only the exact record/current first-window rereads. No API/schema/permission/dependency change was made.
- Fresh verification after the repair: `npm.cmd test -- --run` passed 14 files / 67 tests and `npm.cmd run build` passed. A disposable local UI fixture opened a record, delayed PATCH, switched workspace and proved the old mutation could not restore prior content; final console warnings/errors were empty. The fixture/proxy/server were deleted/stopped.
