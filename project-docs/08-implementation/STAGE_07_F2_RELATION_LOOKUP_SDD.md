# Stage 07 F2 Relation / Lookup SDD

## Status

- Document status: detailed F2 design source; implementation is paused pending documentation reconciliation review
- Scope: service, API, data flow, permission, graph, projection, frontend boundary and verification design for F2 only
- Authority: this document refines but never overrides `AGENTS.md`, Stage07 source, approved F2 design specification and the API/security contract.

## 1. Architecture and Ownership

```text
Mini App builder / create panel / record detail
-> protected API transport and verified user+workspace query boundary
-> FastAPI F2 dedicated initializer or existing record create/PATCH route
-> Stage06 authorization + idempotency + transactional UoW
-> PlatformField.options / PlatformRecord.values / RecordLink / PlatformView / audit
-> safe schema, candidate, view/detail read models
```

The browser owns local input, display and explicit user intent only. It never owns relation target discovery, lookup join/evaluation, aggregation, field order/key generation, role/field policy interpretation, candidate label selection, idempotency completion or durable link maintenance.

## 2. Durable Data Design

| Resource | F2 use | Browser exposure |
| --- | --- | --- |
| `PlatformField(field_type=linked_record)` | internal `options={ target_table_id }`; ordered multi-select relation metadata | safe schema/receipt gives `options: {}`, never target table ID |
| `PlatformField(field_type=lookup)` | internal `options={ source_field_id, target_field_id, aggregation }` | safe schema/receipt gives `options: {}`, never dependency IDs/aggregation |
| `PlatformRecord.values` | linked field stores opaque target record ID array; lookup is derived and never written | relation safe output is `[{id,label}]`; lookup is normalized values/number/null or absent |
| `RecordLink` | source record/field to target record/table projection used for guards | never a browser endpoint or cache model |
| `PlatformView.config.fields` | explicit active same-table list gains generated field key once | raw config never reaches browser |
| idempotency/audit | atomic initializer replay and sanitized evidence | safe receipt only; no storage/audit body |

Stable field IDs are the F2 configuration reference. Legacy `source_field_key`/`target_field_key` lookup configurations remain readable as legacy input during graph/read resolution; F2 never writes them. Renaming preserves dependency identity; a future deletion path must call guards rather than silently repair dependencies.

## 3. Service Interfaces and Invariants

```python
initialize_relation_field(
    uow, table_id, *, name, target_table_id, required, actor
) -> FieldInitializationResult

initialize_lookup_field(
    uow, table_id, *, name, source_relation_field_id,
    target_field_id, aggregation, actor
) -> FieldInitializationResult

list_relation_candidates(
    uow, field_id, *, actor, query, cursor, limit
) -> dict[str, Any]

assert_record_has_no_incoming_relation_links(uow, record_id) -> None
assert_field_has_no_relation_lookup_dependents(uow, field_id) -> None
```

Initializers lock the source table and share this transaction order: resolve/authorise; normalize; idempotency reserve/replay; validate same-Base and dependency rules; create exactly one generated field; append active explicit views; audit safe metadata; persist safe receipt; commit. Any failure rolls all parts back. Target-table state is revalidated before persistence; target IDs/names do not enter receipt or audit after-state.

## 4. Request and Read Contracts

| Endpoint/route | Input | Successful output | Prohibited output |
| --- | --- | --- | --- |
| `POST /tables/{table_id}/relation-field-initializations` | `name,target_table_id,required` + key | safe field receipt | target config, policy, view config, audit/idempotency body |
| `POST /tables/{table_id}/lookup-field-initializations` | `name,source_relation_field_id,target_field_id,aggregation` + key | same safe receipt | relation/target IDs, aggregation, policy |
| `GET /fields/{field_id}/relation-candidates` | bounded `q`, opaque `cursor` | `field_id, records:[{id,label}], next_cursor,has_more` | record body, label-field ID, table/view choice, policy/filter DSL |
| existing create/PATCH | returned field keys + values; PATCH expected version | safe actor-projected record | raw relation IDs without labels, raw lookup config/hidden hop |
| existing create form/schema/view/detail | existing authorized IDs | linked field opaque ID only when writable/picker-safe; safe relation/lookup values | candidate list, relation/lookup config, raw policies |

Pydantic mutation requests reject extra keys. Browser transport uses local fixed error-code allowlist; it never parses backend messages into UI text.

## 5. Authorization and Fail-Closed Decision Order

```text
request identity
-> source resource resolves workspace
-> active membership
-> existing action (field.manage / table.read / record.*)
-> source relation/field read-write policy
-> same Base and fixed target-table ownership
-> target table/record/field readability
-> graph/type/required/version validation
-> transaction or safe projection
```

For lookup read, all required hops must be readable. One unreadable target record, field, nested lookup, invalid/missing configuration, cycle or depth breach makes the current lookup key absent. The evaluator never computes a partial count/sum from what remains visible.

## 6. Dependency Graph and Aggregation Model

The graph node is a lookup field; its edge is its resolved target when target type is `lookup`. Stable-ID configurations resolve by field IDs; legacy configurations resolve source relation key in the owning table, then target field key in the relation target table. Graph validation detects cycles before applying depth rejection, then permits at most two nodes counting the field being created.

Fixed aggregation domain:

| Aggregation | Eligible result source | Output |
| --- | --- | --- |
| `values` | permitted primitive/scalar/multi-select values, flattened one dimension | ordered safe list |
| `count` | readable linked target records | integer |
| `count_distinct` | normalized safe values | integer |
| `sum`, `average`, `min`, `max` | output resolving to `number` | number or numeric-empty `null` |

`linked_record`, `json` and formula fields are not lookup target values. No expression text, callback, SQL fragment or arbitrary aggregation is accepted.

## 7. Relation Write and Projection Flow

```text
create/PATCH values
-> field type + required/partial semantics
-> validate each opaque target ID and de-duplicate/order rules
-> target record/table/base/readability + self-reference checks
-> normalize IDs
-> persist versioned record
-> rebuild source RecordLink rows
-> audit
-> authoritative safe actor reread
```

Create requires every required relation to be nonempty. PATCH permits omitted required relation for a historical record but rejects explicit null/empty. Self-reference is checked only when an existing source record ID exists. Relation projection invokes the server label algorithm and retains only safe `id,label` cells; lookup projection invokes the server evaluator and never calls browser code to traverse IDs.

## 8. Frontend Module Design

| Module | Responsibility | Must not do |
| --- | --- | --- |
| `RelationLookupFieldBuilderPanel` | local name/required/allowlisted aggregation input; submits dedicated endpoint | expose config IDs, raw policy or arbitrary formulas |
| `RelationPicker` | protected server search/cursor, ordered selection/removal, cancellation | query arbitrary table/view or retain candidates persistently |
| `CreateRecordPanel` | render writable linked field by safe field ID and Picker | guess relation target table or write lookup |
| `RecordDetail` | chip relation display/direct edit, read-only lookup presentation | resolve labels/aggregates locally |
| `BaseCanvas` | safe relation/lookup cells in all existing renderers | reconstruct hidden field/value |
| `AppShell/App` | TD001 generation/cancellation/reread/invalidation lifecycle | apply late receipt to a changed scope |

Candidate keys must be `['stage07', userId, workspaceId, 'relation-candidates', fieldId, query, cursor]`. Session/workspace reset cancels and removes them exactly as other protected queries.

## 9. State Machines

```text
Builder: idle -> local-valid -> pending
pending -> reread-required(success|replay) -> verified-rendered
pending -> conflict-locked | generic-error | denied | cancelled | scope-invalidated

Picker: idle -> first-page-loading -> available -> next-page-loading -> available|exhausted
any -> empty | denied | session-expired | cancelled | stale-response-discarded

Lookup: configured -> graph-valid -> evaluated-visible
configured/evaluated -> absent (unreadable hop | invalid config | missing resource | cycle | depth)
numeric evaluated-visible -> null only when permitted input is empty
```

No transition exists from denied/unknown/cancelled/stale directly to success. No transition exists from lookup output to record write.

## 10. Verification and Operational Boundary

Unit/API tests prove model extra-key rejection, authorization, relation/lookup initializer replay/conflict/rollback, graph bounds, aggregation types, candidates, write rechecks, safe projections and delete guards. Disposable local PostgreSQL proves transaction rollback, source-table lock serialization, replay and guards. Frontend tests prove transport redaction, protected cache, builders, picker, create/edit and error boundaries. Actual UI verification uses 1440, 1280, 430 and 390 widths with console scan.

No physical database index, migration, dependency, persistent browser storage, new capability, DELETE route or deletion UI is authorised by this SDD. Logical/data-access index requirements and future physical-index decision gates are isolated in the companion complex-feature index.
