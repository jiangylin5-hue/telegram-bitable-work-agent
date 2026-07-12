# Stage07 Technical Decision 005: Draft Review and Digital Employee Hub

## Status

- Decision status: approved Option A for S5 implementation on 2026-07-12. Approval authorizes only the boundary stated below.
- Scope: a coherent S5 Mini App vertical slice for safe digital-employee contacts, explicit context, field-filtered record-change draft review and controlled confirm/reject.
- Authority: Stage07 source of truth, Stage06 runtime baseline, TD001 protected state, TD004 governance boundary and the product constitution.

## Existing Evidence and Gap

Stage06 already persists `digital_employees`, `record_change_drafts`, `agent_runs` and audit events; its LangGraph-first runtime can summarize permitted view records and create an update draft. It also has generic create/read/update/invoke endpoints and generic draft list/confirm/reject commands.

Those generic contracts are not safe Mini App contracts:

- `DigitalEmployeeResponse` exposes configured table/view IDs and action configuration.
- `RecordChangeDraftResponse` exposes raw `proposed_values`, `before_values`, creator identity, trace and expected record version.
- Generic invocation accepts client-selected `action`, `runtime_mode` and direct proposed-value payloads.
- Generic reject lacks idempotency and draft transitions have no dedicated revision or durable terminal audit reference for a UI receipt.

S5 therefore cannot legally be implemented as a browser wrapper around these routes.

## Considered Options

| Option | Description | Advantages | Risks / decision |
| --- | --- | --- | --- |
| A — bounded safe projection and command adapter **(recommended)** | Reuse Stage06 employee runtime, LangGraph, record-update, idempotency and audit services. Add only safe Mini App projections/commands plus `record_change_drafts.version`, `terminal_audit_event_id` and one pending-queue index. | Completes one coherent product loop: contact → explicit context → summary/draft → filtered diff → confirm/reject → audit receipt. No new agent framework or memory system. | Requires one additive migration and six narrow Mini App endpoints; must be approved. |
| B — render existing Stage06 runtime/draft routes directly | Add frontend components over existing routes without server projections or migration. | Lowest apparent implementation effort. | Rejected: leaks configuration/raw draft values and cannot give safe idempotent reject, revision or durable audit receipt. |
| C — full Bot contacts, published lifecycle, personal memory, knowledge sources and Telegram deep links | Implement the entire Package 4/S6 surface before draft review. | Broad feature coverage. | Rejected for S5: requires new lifecycle, retention, memory, identity and Telegram contracts; it expands into S6 and delays the usable draft loop. |

## Proposed Option A Contract

### Additive persistence

| Resource | Addition | Rule |
| --- | --- | --- |
| `record_change_drafts` | `version INTEGER NOT NULL DEFAULT 1` | increments once on accepted terminal confirm/reject transition; it is checked under a row lock. |
| `record_change_drafts` | `terminal_audit_event_id UUID NULL` | set exactly once when a terminal transition writes its audit event; the Mini App receives it only as an opaque audit receipt reference. |
| `record_change_drafts` | partial/composite index candidate `(base_id, created_at DESC, id DESC) WHERE status = 'pending_confirmation'` | supports the only S5 queue list if measured necessary. The approved local I-A measurement retained the existing `ix_stage06_drafts_base_status`; no S5 index migration is created. |

No new employee table, role table, group membership, message/memory table, knowledge table, chat history store or client persistence is proposed.

### Fixed Mini App intents and context

The browser sends an intent, not a runtime mode/action/tool call:

| UI intent | Server mapping | Permitted result |
| --- | --- | --- |
| `summarize` | existing configured employee summarize action | field-filtered answer and safe citations only |
| `draft_update` | existing configured employee draft action | a pending `record_change_draft` pointer only |

The request may contain one explicit current `base_id`, plus an allowed `view_id` for summary and `record_id` for draft update, and a bounded instruction string. It never accepts employee action arrays, runtime mode, raw provider options, direct `proposed_values`, source-table/view scope, field policy, provider credentials, Telegram IDs or browser role claims.

Effective authority remains:

```text
employee configured scope
-> current caller membership and field/record scope
-> no Telegram/chat expansion in S5
```

The backend resolves every resource relationship and performs the intersection before reading or invoking anything. Empty/invalid scope, cross-Base context, inactive employee, unavailable runtime and hidden/writable-field mismatch fail closed.

### Safe endpoints

| Route | Browser boundary | Server result |
| --- | --- | --- |
| `GET /mini-app/workspaces/{workspace_id}/digital-employee-contacts` | optional `base_id`, cursor | active authorized contacts `{id,base_id,name,description,status,available_intents}` only |
| `POST /mini-app/digital-employees/{employee_id}/invocations` | strict `{intent,base_id,view_id?,record_id?,instruction?}`, `Idempotency-Key` for draft intent | safe summary or `{draft_id,status}`; never raw records/runtime/skill evidence |
| `GET /mini-app/bases/{base_id}/drafts` | cursor | safe pending queue summaries only, newest-first keyset pagination; terminal state is read by explicit safe draft detail |
| `GET /mini-app/drafts/{draft_id}` | none | field-filtered immutable diff, current action availability and opaque terminal audit reference |
| `POST /mini-app/drafts/{draft_id}/confirm` | `{expected_version}`, `Idempotency-Key` | safe terminal receipt after server recheck/write/audit |
| `POST /mini-app/drafts/{draft_id}/reject` | `{expected_version}`, `Idempotency-Key` | safe terminal receipt after server recheck/audit; no record write |

Safe draft fields are a closed display model `{key,label,field_type,before_value?,proposed_value?}`. Values use the current safe Record Detail render contract: hidden/unreadable fields are omitted, linked records are label-only, lookup stays read-only, and unsupported JSON/technical state is omitted rather than serialized. A confirmer must be able to write every proposed field at confirmation time; otherwise the entire terminal command fails without partial update.

### Lifecycle and audit

`pending_confirmation -> confirmed|rejected` is a single locked terminal transition. Both actions are idempotent only for the identical actor/command/revision and return the same safe receipt on replay; changed reuse conflicts. Confirm rechecks record version plus current caller field-write scope before calling the existing record service. Reject never calls the record service. Both write one sanitized audit event and persist its opaque ID in `terminal_audit_event_id`.

The client has no optimistic draft/result transition. It clears only the current user/workspace/base/draft/contact/invocation protected keys, rereads the server state and displays a terminal receipt only after that reread. `401` removes all Stage07 protected state; `403` removes the current workspace subtree; `404` removes exact draft/contact context; `409` retains only typed unsent intent and offers explicit reread; `422`, `5xx` and network errors never render server detail.

## Explicit S5 Non-Goals

- employee create/edit/publish/disable lifecycle UI;
- personal memory, knowledge sources, shared chat history or browser persistence;
- Bot contact public sharing, group routing, Telegram `@` handoff, deep links or Telegram identity proof;
- generic chat, arbitrary tool/action selection, provider/runtime selection or raw prompt/record export;
- automatic draft confirmation, agent self-confirmation, notification send or external action;
- field/schema/record direct edit bypass, custom RBAC, groups or a general policy engine;
- deployment, production or S6 acceptance.

## Approval Boundary

Approving Option A authorizes only the two draft columns, the measured pending-queue index if justified, six narrow Mini App endpoints, fixed `summarize|draft_update` intents, safe draft/contact projections, versioned/idempotent confirm/reject and their UI. It does not authorize any S5 non-goal above.
