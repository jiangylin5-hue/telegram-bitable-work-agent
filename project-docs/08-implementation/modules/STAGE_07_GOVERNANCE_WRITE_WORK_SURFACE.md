# Stage07 Governance Write Work Surface

## Status

- Status: implemented-local work surface; role and field-policy mutations are protected across terminal outcomes, while Browser negative-lifecycle acceptance remains partial.
- Functional ownership: S4 owns only safe governance command forms and cache lifecycle, never authorization evaluation.

## Functional Modules

| Surface | Authorized user can do | Deliberately cannot do |
| --- | --- | --- |
| Member roles | select an allowed replacement role for one existing active editable member and confirm | invite, remove, activate, self-change, change owner, transfer owner, create custom role |
| Field access | replace the fixed five-role `hidden/read/write` matrix for one field | edit field configuration/data, create per-user policy, set arbitrary JSON/action rule |
| View access | open/reuse existing V1 owner-only member grant editor | create public links, manage system-default access, transfer ownership, create general view role policy |

## State Contract

| State | Required behavior |
| --- | --- |
| unavailable capability | no editor trigger; server remains final authority |
| loading | labelled progress; confirm unavailable |
| no editable target | fixed empty text; no create/invite affordance |
| clean | current safe values only; no raw audit/policy serialization |
| changed | local typed intent only; a confirm action names the target and selected mode/role |
| pending | only the submitted command is disabled; cancel/Escape cannot turn into a write |
| success | exact query removal, authoritative reread, fixed confirmation, focus return |
| 409 | safe local intent retained; fixed reread action; no automatic retry |
| 422 | safe local intent retained; fixed allowlisted text only |
| 401/403/404 | protected-state removal matches SDD and no stale editor remains |
| 5xx/network | generic retry; no server detail or guessed data |

## Accessibility and Responsive Rules

The desktop role list/policy matrix has visible labels and one confirm path. At 430/390 it becomes a full-height sheet with headings, per-control labels, 44px touch targets, independent content scrolling and sticky actions. Focus enters the heading, remains scoped to the dialog, and returns to the originating Governance control after close/success/denial. No color-only role/mode state, hover-only action, drag-only reorder or hidden desktop-only confirm control is allowed.

## Data Boundary

The work surface consumes only S4 safe DTOs and existing V1 safe builder data. It must never consume the generic member endpoint as an editable authority source, generic audit payload, `ROLE_ACTIONS`, raw `permission_policy` beyond the fixed normalized matrix, field values, relation target data, member profile/invitation data or a client-generated permission result.

## Acceptance Ownership

This module owns GW-A06 and GW-A07 UI evidence, contributes negative rendering proof to GW-A01/GW-A03/GW-A04, and has no authority to mark backend authorization or production/Telegram acceptance complete. The delayed old-workspace role and field-policy `401/403/404/409` App matrices prove no replacement-workspace denial or stale repopulation. The current built-client pass proves the labelled write success paths, V1 reuse and four widths; it does not claim the remaining stale/denied/retry/focus-return Browser permutations.
