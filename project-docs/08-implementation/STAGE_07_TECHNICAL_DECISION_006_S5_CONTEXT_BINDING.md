# Stage07 Technical Decision 006: S5 Context Binding for Employee Invocation

## Status

- Decision status: proposed; not approved and not implemented.
- Scope: resolve the approved TD005 gap between a safe contact directory and the explicit `base_id` / `view_id` / `record_id` required by S5 employee invocation.
- Authority: `AGENTS.md`, Stage07 source of truth, TD005, the approved S5 SDD/BDD and the product constitution.

## Problem Statement

TD005 approves six narrow S5 routes. The contact route exposes only a safe contact plus `base_id`; the invocation route correctly requires a view for `summarize` and a view plus record for `draft_update`. It intentionally does not accept browser-selected actions, raw values or broad scope.

No approved route, however, provides a safe discovery model for selectable Base, view or record context. Reusing generic Stage06 Base/view/record routes inside the Hub would make the S5 UI a wrapper around generic browser contracts, contradicting TD005's safe-adapter requirement. Inventing a new picker from local storage or chat history would violate the explicit-context and no-client-persistence rules.

The already-implemented S5 Hub therefore correctly supports contact reading and queue-draft review, but deliberately has no invocation control. This decision chooses the only allowed next boundary; it does not alter the existing safe draft loop.

## Non-Negotiable Constraints

- No raw record fields, employee configuration, runtime metadata, trace, provider data, Telegram data or browser role claims enter the Hub.
- No schema, permission-model, external provider, queue, memory or Telegram change is bundled into this decision.
- The server remains the sole authority for Base/view/record membership and employee/caller scope intersection.
- The Hub never persists context in localStorage, URL query parameters or chat history.
- Existing Home queue-to-safe-draft review stays available regardless of the selected option.

## Options

| Option | Boundary | What the user can do | Cost and risk | Decision state |
| --- | --- | --- | --- | --- |
| A — bind only the current authorized Base canvas **(recommended)** | Add no endpoint. The App root passes only `{baseId, viewId, recordId?}` from the already-open, current Canvas; the Hub neither fetches nor stores generic context. | From an open Base/view, choose a visible contact and run `summarize`; from an open record, run `draft_update`. From Home, the Hub states that no context is selected and still permits draft review. | Lowest scope and no new API/schema. It needs an explicit, narrow S5 exception documenting that the App root may pass opaque current-canvas IDs, because the S5 SDD currently says the adapter is the only Hub browser entry. It does not offer a standalone Home record picker. | Proposed recommendation. |
| B — add a server-composed S5 context projection | Add one or more new Mini App read routes that return only currently permitted Base/view/record display summaries for the selected employee. | Select context from Home or the Hub, then invoke. | API-contract expansion, pagination/search design, display-label redaction and more authorization/cleanup proofs. It cannot be merged into TD005 without explicit approval. | Proposed alternative. |
| C — consume generic Stage06 context endpoints directly | No new contract; query generic Base/view/record data from the Hub. | Apparent fastest path. | Rejected. It bypasses the TD005 safe-adapter boundary and makes raw/generic projections a new hidden source for the Hub. | Rejected. |

## Recommended Option A: Exact SDD Boundary

### Input model passed by App root

```ts
type CurrentCanvasInvocationContext = {
  baseId: string
  viewId: string
  recordId: string | null
}
```

This is not persisted and is not a permission claim. It is derived only when the current Canvas has already loaded an authorized Base, active view and, for a draft target, an open record. The Hub receives no table schema, record field map, view rule, role, capability or generic response object.

### Invocation rules

| Intent | Required current Canvas state | Browser request | Server remains responsible for |
| --- | --- | --- | --- |
| `summarize` | active Base and view | `{intent:'summarize', base_id, view_id, instruction?}` | employee action/scope, caller read scope, Base/view relationship and safe response projection |
| `draft_update` | active Base/view and open record | `{intent:'draft_update', base_id, view_id, record_id, instruction?}` plus a new client idempotency key | employee action/scope, caller read scope, record/Base/view relationship, proposal-only result and idempotent replay |

The App must not render an invocation submit control for an empty or incomplete context. Contact selection changes only local transient selection; it cannot change the current Canvas or infer another Base. A user returns to Home with no context after leaving the Canvas.

### Explicit S5 exception

After approval, TD005 SDD's “S5 adapter is the only browser entry” sentence will be amended only as follows: the S5 adapter remains the only **network data source** for the Hub; the App root may pass the opaque current-canvas IDs above as transient invocation input. The Hub itself does not call generic endpoints or retain generic response data.

## Option B Boundary if Chosen Instead

Option B requires a separate API/data contract before code. At minimum it must specify:

1. whether the first projection lists Bases, views, records or a constrained sequence;
2. pagination, search and stale-cursor semantics for record choices;
3. the closed safe record display-label algorithm and field-redaction rule;
4. every `401` / `403` / `404` / `409` / `422` cleanup rule;
5. employee scope intersection and cross-Base denial proof;
6. no UI fallback to generic Stage06 reads.

No endpoint, schema or index is authorized by this proposal.

## Approval Request

Choose one option for the remaining S5 invocation surface:

- **A — current Canvas binding (recommended):** no new endpoint; bounded initial-product path.
- **B — server S5 context projection:** wider API design before implementation.

Approval changes only the context-binding boundary. It does not approve memory, knowledge, contact lifecycle, Telegram handoff, external action, generic chat or S6 work.
