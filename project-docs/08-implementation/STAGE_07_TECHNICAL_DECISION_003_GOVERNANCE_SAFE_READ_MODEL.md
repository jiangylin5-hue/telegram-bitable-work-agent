# Stage07 Technical Decision 003: Governance Safe Read Model

## Status

- Decision status: proposed — requires explicit user approval before implementation
- Scope: Stage07 Package 3 first coherent delivery, limited to member and audit **readback**
- Does not authorize: role mutation, member mutation, field/view policy mutation, Bot administration, draft confirmation, Telegram handoff or any production deployment

## Problem Evidence

The existing endpoints are valuable backend evidence but are not safe Mini App read models as-is.

| Existing route | What works | Why it cannot be sent directly to the browser |
| --- | --- | --- |
| `GET /workspaces/{workspace_id}/members` | server independently requires `member.read` and has a closed member shape | returns all members without a limit/cursor contract |
| `GET /bases/{base_id}/audit-events` | server independently requires `audit.read`, scopes the Base and applies state sanitization | response still contains `trace_id`, `actor_id`, `before_state`, `after_state` and `permission_snapshot`; the generic Stage07 contract forbids these in client state |

Client-side omission is rejected: data received by the browser has already crossed the disclosure boundary.

## Considered Approaches

| Option | Description | Advantages | Rejection / risk |
| --- | --- | --- | --- |
| A — client adapter only | Fetch existing endpoints and discard unsafe fields in TypeScript | no backend change | rejected: unsafe data reaches browser; member list remains unbounded |
| B — retrofit existing generic endpoints | change their response schemas and add pagination in place | one public route per resource | risky compatibility change for existing Stage06 clients; requires a wider contract audit |
| C — Mini App governance projections **(recommended)** | add two narrow Stage07 routes and response DTOs, reusing Stage06 authorization, Base resolution, audit sanitizer and cursor paginator | closed browser boundary, non-breaking to legacy routes, smallest durable contract | a new read-only API contract must be explicitly approved |

## Proposed Contract

### Members

`GET /mini-app/workspaces/{workspace_id}/governance/members?limit=1..100&cursor?`

Authorization sequence: resolve verified request identity → active workspace membership → `member.read` → paginate deterministic existing `WorkspaceMember` rows through the existing Stage06 cursor helper.

Safe response:

```json
{
  "workspace_id": "uuid",
  "members": [
    { "id": "uuid", "user_id": "stable-user-id", "role": "owner|admin|builder|operator|viewer", "status": "active|inactive" }
  ],
  "next_cursor": "opaque-or-null",
  "has_more": false
}
```

`workspace_id` is a scope-consistency assertion only. No email, phone, display profile, invitation, permission snapshot, timestamps, role-action list or mutation capability is emitted.

### Base Audit Timeline

`GET /mini-app/bases/{base_id}/governance/audit-events?limit=1..100&cursor?`

Authorization sequence: resolve Base → resolve workspace → active membership → `audit.read` → filter Base-related events using the existing service → deterministic existing cursor paginator.

Safe response:

```json
{
  "base_id": "uuid",
  "events": [
    {
      "id": "uuid",
      "occurred_at": "RFC3339 timestamp",
      "actor_type": "user|digital_employee|system",
      "event_type": "stable-stage06-event-code",
      "entity_type": "stable-resource-type"
    }
  ],
  "next_cursor": "opaque-or-null",
  "has_more": false
}
```

The projection never emits `trace_id`, `actor_id`, `entity_id`, any state snapshot, permission snapshot, raw notification/Telegram content, prompt, memory, record value or field key. The Mini App maps only an allowlisted event-code label; unknown codes render the fixed generic text `已记录系统操作`.

## Frontend Architecture

Reuse the existing React, TypeScript and TanStack Query protected-state architecture; no dependency, persistence layer, localStorage, analytics SDK or new state framework is proposed.

- Protected keys are under `['stage07', userId, workspaceId, 'governance', ...]`.
- Member pages are workspace-scoped. Audit pages are additionally Base-scoped.
- `401` clears every Stage07 protected key; `403` clears the active workspace key and uses the existing denied boundary; `404` clears only the exact Base audit key; request generation and `AbortSignal` prevent late pages crossing workspace/Base changes.
- The route is a read-only workbench opened only from server-derived `can_manage_workspace`; that hint never substitutes endpoint authorization. Audit tab availability is determined only by the actual endpoint response, because bootstrap does not currently expose a separate `audit.read` capability.

## Approval Required

Approval of Option C authorizes only the two new safe read routes, their DTOs, protected frontend transport and the read-only UI specified by the linked Governance package documents. It does **not** approve a permission engine change or any governance write operation.
