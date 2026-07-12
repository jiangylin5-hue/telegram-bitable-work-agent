# Stage07 Governance Readback SDD

## Status And Invariants

- Status: proposed safe API/UI boundary; implementation waits for user approval
- Invariant 1: a browser may receive only the DTOs in Technical Decision 003.
- Invariant 2: each request is independently authorised; capability hints are never authority.
- Invariant 3: all reads are cursor-paged and deterministic through the existing Stage06 pagination helper.
- Invariant 4: Governance is read-only in this package.

## Backend Design

### Route ownership

The Mini App route layer owns the two new DTO projections. It reuses:

- `get_stage06_request_identity` for verified identity;
- existing UoWs and `authorize_workspace_action` for membership/action checks;
- `workspace_id_for_base` / Base resolution for audit scope;
- `list_workspace_members`, `list_base_audit_events` and `paginate_items` for data and opaque cursors;
- existing audit sanitizer before the final strict DTO projection.

It must not widen the generic Stage06 routes or accept a user-supplied role, event filter, Base ID outside the selected path, audit field list, trace or raw state selector.

### Closed DTO rules

The Pydantic response schemas use strict, explicitly declared fields. The audit projection is constructed server-side from the event object; it does not transform the legacy HTTP response. `occurred_at` uses a timezone-aware RFC3339 string. Unknown event codes remain an allowed opaque stable code at transport level but receive only fixed generic UI text unless client mapping specifically permits them.

### Pagination and ordering

Both projections call `paginate_items(..., preserve_order=False)`. Cursor payload remains opaque. `limit` defaults to `50`, accepts `1..100` for this Mini App route, and a bad/foreign/expired cursor returns a fixed `422 governance_invalid_cursor`. Cursor error never discloses a member/event identifier.

## Frontend Design

### Safe types and API

`governance-types.ts` contains closed `GovernanceMember`, `GovernanceMemberPage`, `GovernanceAuditEvent`, `GovernanceAuditPage` types. `api.ts` parsers reject extra required-shape violations and retain only approved scalar fields. They never import or parse `AuditEventResponse` from the generic runtime API.

### Protected query keys

```text
['stage07', userId, workspaceId, 'governance', 'members', cursor]
['stage07', userId, workspaceId, 'governance', 'audit', baseId, cursor]
```

`clearGovernanceQueries(scope, baseId?)` cancels/removes members and all governance audit pages for the scope, or one Base audit subtree when the exact Base becomes missing/replaced. It follows the existing no-persistence QueryClient configuration.

### App lifecycle

The App owns `governancePanel` and a request generation. Opening captures the current workspace. Base selection removes prior Base audit keys before requesting the new page. Close/unmount/workspace replacement increments generation, cancels relevant queries and clears local selected Base/page error state. A late response is discarded unless identity, workspace and selected Base still match.

## UI Safety

- rows render text nodes, never server HTML;
- role/status/event code use fixed label maps; unknown values use `未知状态` or `已记录系统操作`;
- no copy/export action, URL parameter or client filter writes a row payload;
- member and audit error states use existing generic safe boundaries;
- focus returns to the opener after close; pending continuation disables only its own `加载更多` control.

## Test Design

1. backend DTO tests reject raw audit fields and prove 401/403/cross-workspace/Base denial;
2. pagination tests cover member/audit order, cursor failure and no duplicate append;
3. frontend parser/query/component tests cover safe parsing, cancellation, 401/403/404, selection replacement, unknown event labels and continuation failure;
4. disposable PostgreSQL proves real authorization/redaction/cursor readback;
5. Browser uses synthetic data only, verifies membership/audit render, denied/error state, console `[]` and required widths.

## Non-Goals

No migration is required by the proposed read models. No write endpoint, idempotency key, member/editor role mutation, permission policy model, new index, cache persistence, telemetry integration or third-party dependency is in scope.
