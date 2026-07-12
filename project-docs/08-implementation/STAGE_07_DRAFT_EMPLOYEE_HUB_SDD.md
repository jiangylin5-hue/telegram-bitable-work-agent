# Stage07 Draft and Digital Employee Hub SDD

## Status

- Status: approved TD005 Option A technical specification; S5 implementation in progress.
- Scope: server-composed contact/draft models and controlled terminal commands over existing Stage06 runtime services.
- Current Progress: the approved contact/draft adapter, terminal draft revision/audit migration, locked confirm/reject path, safe Mini App parsers and Hub entry are implemented. The Home assistant entry loads only the safe contact directory; queue links load only the safe draft detail; terminal UI clears protected S5/home/record state and rereads the authoritative detail. The current code also rejects unsafe before-values instead of crashing, calls the actual `live_openrouter` runtime mode and reserves/replays `draft_update` invocations through the existing Stage06 idempotency ledger. This is implementation evidence only: PostgreSQL race/rollback coverage, live provider evidence, index measurement, Browser width matrix and DE-A01--DE-A10 reconciliation remain pending.

## Architecture

```text
Mini App protected query scope
-> S5 safe contact/context/draft endpoints
-> Stage06 authorization + employee scope validation
-> LangGraph-first runtime or deterministic test adapter
-> record_change_draft locked transition
-> record service + sanitized audit
-> safe terminal receipt reread
```

The S5 adapter is the only browser entry. Generic Stage06 runtime and draft endpoints remain supported backend contracts but are not Mini App data sources.

## Authorization

The adapter resolves identity using the current server identity dependency, then independently resolves workspace/Base/table/view/record ownership. It uses current fixed role actions for `digital_employee.invoke`, `record_change_draft.read`, `record_change_draft.confirm`, `record_change_draft.reject`, `record.read` and `record.update`; it never accepts a capability/role/action claim from the browser.

Employee invocation requires all of:

1. active employee and active membership;
2. selected Base matches employee Base and workspace;
3. requested view/record belongs to the selected Base;
4. employee configured table/view scope permits it;
5. caller current read scope permits source data;
6. server maps the closed S5 intent to an employee-permitted Stage06 action.

Draft confirmation additionally requires the current actor to write every proposed field. If any field is hidden, removed, unsupported or not writable, confirmation fails as one command. Field filtering in a prior GET is never authorization evidence.

## Draft Transition Transaction

The S5 Unit of Work adds `lock_record_change_draft_for_transition`. SQLAlchemy performs `SELECT ... FOR UPDATE`; in-memory behavior follows revision compare/update semantics. Confirm/reject run in one transaction with the existing idempotency ledger.

```text
lock draft
-> verify pending_confirmation + expected draft version
-> re-resolve caller/Base/table/record/field authorization
-> confirm: current record version + update_record
-> reject: skip record service
-> write sanitized audit, capture event ID
-> write terminal status/version/audit reference
-> complete idempotency receipt
```

No automatic expiration worker is introduced in S5. Existing non-pending/expired data is rendered only as a safe terminal state and cannot be transitioned.

## Safe Projections

### Contact

```ts
type SafeDigitalEmployeeContact = {
  id: string
  baseId: string
  name: string
  description: string
  status: 'active'
  availableIntents: ('summarize' | 'draft_update')[]
}
```

### Invocation

```ts
type SafeEmployeeInvocation =
  | { kind: 'summary'; answer: string; citations: SafeCitation[] }
  | { kind: 'draft'; draftId: string; status: 'pending_confirmation' }
```

`SafeCitation` may contain only a record ID and server-safe display label where already readable. It contains no field map, query, scope or runtime metadata.

### Draft

```ts
type SafeDraftDetail = {
  id: string; baseId: string; tableId: string; recordId: string | null
  draftType: 'update_record' | 'status_advance'
  status: 'pending_confirmation' | 'confirmed' | 'rejected' | 'expired'
  version: number
  fields: Array<{ key: string; label: string; fieldType: string; beforeValue?: SafeValue; proposedValue?: SafeValue }>
  actions: { canConfirm: boolean; canReject: boolean }
  terminalAuditEventId: string | null
}
```

Pydantic models use `extra='forbid'`; TypeScript parsing allowlists all enum values. The generic DTOs remain unmodified and are never forwarded through the adapter.

## Cache and Error Rules

All keys nest below `['stage07', userId, workspaceId, 's5', ...]`. A terminal mutation cancels/removes exact draft, Base queue, contact/context and active record/view paths, then rereads. `401` clears the complete protected workspace; `403` removes its S5 subtree; `404` removes exact resource keys; `409`/`422` retain typed local intent only; unknown failures map to a fixed generic failure.

### Implemented UI Boundary and Remaining Context Gap

The implemented Hub intentionally exposes only the already-approved safe contact directory and safe queue-draft review path. It does not render a fake Base/view/record selector and does not invoke an employee from the browser yet. TD005 authorizes the six listed routes but does not define a server-safe context-discovery projection for selectable Bases, views and records. Reusing generic Base/view/record endpoints as a hidden Hub data source would contradict this SDD's “S5 adapter is the only browser entry” rule. A later S5 addendum must explicitly choose one of these paths before that UI is implemented: a narrow server-composed S5 context projection, or a documented exception for an already-authorized non-S5 projection. That is an API-contract decision and is not silently implemented in this substage.

## Migration and Index

Migration adds only TD005's two columns. The pending queue index is created only after the accompanying PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` proves the existing Base/status scan is insufficient at the documented fixture size; otherwise it remains deferred. No broad policy/index migration is permitted.
