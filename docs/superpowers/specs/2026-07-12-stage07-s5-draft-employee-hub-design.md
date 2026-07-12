# Stage07 S5 Draft and Digital Employee Hub Design

## Status and Scope

- Status: proposed design pending TD005 approval.
- Product outcome: a table-bound assistant can safely summarize a selected view or propose a record update; a human sees a field-filtered immutable diff and confirms or rejects it through one audited server command.
- Product grammar: `workspace -> base -> employee -> explicit context -> invocation -> record_change_draft -> terminal audit`.

This design reuses the existing Stage06 LangGraph-first runtime, FastAPI/SQLAlchemy services, idempotency ledger, record update validation, audit sanitizer and React/TanStack Query architecture. It does not create an agent framework, chat database, permission engine or raw runtime client.

## User Journeys

### Team digital employee

1. A member opens the Digital Employee Hub from an existing authorized workspace.
2. The server returns only active contacts accessible from that workspace/Base; no scope IDs, action maps, alias or configuration are rendered.
3. The member selects one contact and an explicit Base/view for summary or Base/record for a draft proposal.
4. The server verifies employee scope ∩ caller scope, executes the fixed server intent and returns either a safe summary or a pending draft pointer.
5. The member opens the draft, sees only fields readable to them and may confirm/reject only when the server says the action is currently available.

### Draft review

1. Home queue or Hub opens a safe draft summary.
2. Detail reads a safe, field-filtered diff. It does not reconstruct a diff from cache, agent output or generic runtime JSON.
3. Confirm/reject requires explicit confirmation, expected draft revision and an idempotency key.
4. The server re-evaluates membership, resource chain, draft status, revision and record/field write authority under lock.
5. The client rereads the terminal safe receipt; only then does it show confirmed/rejected plus opaque audit reference.

## State Model

| State | Contact / invocation | Draft review | Client rule |
| --- | --- | --- | --- |
| unavailable | no authorized contacts or runtime disabled | no fake assistant | fixed explanation; no local simulation |
| loading | labelled contact/context loading | labelled diff loading | submit unavailable |
| no-context | selected contact but no Base/view/record | n/a | explain that no workspace data is in context |
| ready | fixed intent available from safe contact model | immutable safe diff and action availability | user may type bounded instruction / select one terminal action |
| pending invocation | one intent disabled | n/a | no duplicate invocation; cancellation cannot claim success |
| pending draft command | n/a | only submitted terminal command disabled | no optimistic status change |
| terminal | safe answer/draft pointer | confirmed/rejected receipt | canonical reread before render |
| stale | invocation/draft reference obsolete | revision mismatch | retain typed draft intent; explicit reread only |
| denied/expired | safe generic boundary | safe generic boundary | protected cache removal precedes rendering |
| invalid/network | fixed local feedback/retry | fixed local feedback/retry | never display server message/detail |

## Responsive and Accessibility Rules

Desktop uses a three-zone work surface: contact list, explicit context/instruction, draft/response detail. Mobile uses full-height sheets in sequence; contact, context and confirm buttons have 44px targets. Every selection has an accessible label; diff rows state field label, before and proposed safe values. The first heading receives focus on opening, pending commands retain focus safely, and close returns to the origin. No hover-only contact, drag-only context, color-only status or hidden desktop-only confirm path exists.

## Data Exposure Rules

The browser never receives employee configuration, `accessible_tables`, `accessible_views`, `allowed_actions`, `field_policy`, confirmation policy, provider/runtime metadata, skill evidence, raw AgentRun output, trace IDs, generic draft raw values, creator identity or expected record version. It receives only the server-composed safe DTOs in TD005.

Draft values are filtered twice: field visibility controls whether a row exists; current write scope controls whether confirm is available. A hidden/unsupported field is never transformed into a masked placeholder because its presence itself leaks schema/draft intent. A draft that becomes unconfirmable due to current permissions fails as a whole; it is never silently partially applied.

## Out of Scope

No Telegram handoff, memory, knowledge retrieval, employee administration, raw conversation persistence, notifications or external action occurs in S5. They remain S6 or later separately approved work.

