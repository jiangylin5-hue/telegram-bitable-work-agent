# Stage07 Draft and Digital Employee Hub SDD

## Status

- Status: approved TD005 Option A technical specification; S5 implementation in progress.
- Scope: server-composed contact/draft models and controlled terminal commands over existing Stage06 runtime services.
- Current Progress: the approved contact/draft adapter, terminal draft revision/audit migration, locked confirm/reject path, safe Mini App parsers and Hub entry are implemented. The Home assistant entry loads only the safe contact directory; queue links load only the safe draft detail; terminal UI clears protected S5/home/record state and rereads the authoritative detail. The current code also rejects unsafe before-values instead of crashing, calls the actual `live_openrouter` runtime mode and reserves/replays `draft_update` invocations through the existing Stage06 idempotency ledger. Summary citations are re-filtered against the current server-authorized view and emitted only as unique `{record_id}` values; the client allowlists that result and never receives citation fields/runtime metadata. TD006 Option A is now implemented: an open Canvas passes only transient Base/view/optional-record IDs to the Hub; the Hub adds no generic request, storage or picker. The pending queue now matches its approved predicate (pending-only, newest-first keyset), and its local index gate retained I-A without an index migration. A safe draft reread now recomputes `can_confirm` from the current field-write projection, so a post-creation hidden field both disappears and disables confirmation. The BDD now records DE-A01/A06/A07/A10 as `implemented-local` and the remaining provider/Browser/failure evidence as `partial-local`; live provider evidence and Browser width matrix remain pending.

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

All keys nest below `['stage07', userId, workspaceId, 's5', ...]`. A terminal mutation captures its request generation, then cancels/removes exact draft, Base queue, contact/context and active record/view paths before rereading only while that generation is current. A delayed terminal `401`/`403` from an old workspace clears only old scoped state and cannot deny or repopulate the replacement workspace. For current requests, `401` clears the complete protected workspace; `403` removes its S5 subtree; `404` removes exact resource keys; `409`/`422` retain typed local intent only; unknown failures map to a fixed generic failure.

### Implemented UI Boundary and Current-Canvas Context

The Hub exposes the already-approved safe contact directory and queue-draft review path. Under approved [TD006 Option A](STAGE_07_TECHNICAL_DECISION_006_S5_CONTEXT_BINDING.md), the App root may additionally pass only transient `{baseId, viewId, recordId?}` from the current authorized Canvas. The Hub uses those IDs only in its existing S5 invocation request; it neither receives Canvas query results nor calls generic Base/view/record endpoints. A selected contact can invoke server-derived `summarize` for the current Base/view; `draft_update` remains disabled until an open current record exists and carries a fresh idempotency key. Canvas replacement invalidates the invocation version and discards stale results. There is still no Home picker, generic browser source, localStorage/URL persistence or inferred context.

## Migration and Index

Migration adds only TD005's two columns. `GET /mini-app/bases/{base_id}/drafts` has its own narrow persistence query: `status='pending_confirmation'`, `created_at DESC, id DESC`, `LIMIT page_size + 1`. Its opaque cursor names the last pending draft; the server re-resolves that marker to the same Base/status and then applies the `(created_at, id)` keyset predicate. A missing, cross-Base or terminal cursor marker is a typed `422`; it cannot turn a terminal draft into queue data.

The documented local PostgreSQL measurement used `512` pending plus `1,536` terminal drafts for one Base and returned the first `50` rows through the safe route. PostgreSQL reused `ix_stage06_drafts_base_status` (`Bitmap Index Scan`, `0.913 ms` execution, `0` shared reads). Therefore the optional partial index is deliberately not created. No broad policy/index migration is permitted.
