# Stage 07 F2 Relation / Lookup Work Surface Module

## Status

- Document status: active detailed module contract; execution paused for documentation reconciliation
- Scope: one F2 table-local relationship and derived-value surface across Builder, Canvas, Create and Detail
- Excludes: field edit/delete UI, reverse relations, cross-Base selectors, formula editor, imports, views V1, Bot and Telegram flows.

## 1. User-Facing Functions

| Function | Entry | Permitted user result | Durable landing point |
| --- | --- | --- | --- |
| add relation field | active table builder | one required/optional relation to a same-Base table | `PlatformField(linked_record)`, explicit view update, audit |
| add lookup field | active table builder | one read-only derived field over selected relation/field/aggregation | `PlatformField(lookup)`, explicit view update, audit |
| choose relation values | create form or direct record edit | ordered labelled target chips | existing record create/PATCH + RecordLink + audit |
| read relation | Grid/Kanban/Calendar/Form/Detail | safe labelled chips | server-composed record/view model |
| read lookup | Grid/Kanban/Calendar/Form/Detail | safe normalized list/number/null | server evaluator output only |

Every result either persists a resource/change/audit or is a safe rejected/omitted state. A chat answer, raw JSON, locally calculated join or optimistic selection alone is not a completed F2 result.

## 2. Builder Controls and State Rules

### Relation field

Inputs are display name, server-filtered same-Base target table and required toggle. The target table picker receives only ordinary safe table summaries already authorised for the current Base. It does not receive target field lists, target records, policy, Base ID editing or a reverse-field toggle.

### Lookup field

Inputs are display name, server-filtered source `linked_record` field, server-filtered target field and one fixed aggregation. The UI shows no dependency IDs, arbitrary code, SQL/formula, lookup depth setting or raw options. It may disable locally impossible choices for usability, but server validation is final.

### Builder outcomes

| Outcome | UI behavior |
| --- | --- |
| invalid local input | inline fixed guidance; no request |
| pending | disable close/cancel/submit per TD001 mutation safety |
| 201/200 receipt | invalidate exact schema/create-form/view windows, reread and verify receipt field ID |
| 409 | retain local values, lock dialog until explicit close/new key |
| approved allowlisted validation code | fixed local Chinese guidance only |
| 401/403/404/unknown | existing safe boundary; no backend message/resource preview |
| cancelled/scope change/late result | discard receipt and protected state; no navigation |

## 3. Candidate Picker Contract

The picker is a shared component for create and direct edit. It starts empty, loads candidate pages only after a valid relation field ID/current protected scope exists, debounces bounded search, supports cursor continuation, preserves selected order and removes chips without making an API write until parent form submit.

Candidate state cannot cross a workspace/user boundary. It never stores candidate data in local storage, telemetry or URL. A direct-edit picker additionally removes the current record ID from selectable values in the UI, while server self-reference validation remains mandatory.

## 4. Renderer Rules

| Field type | Grid/Kanban/Calendar/Form | Detail | Editability |
| --- | --- | --- | --- |
| `linked_record` | safe compact label chips; no raw ID label fallback | same chips and Picker for writable field | create + direct PATCH only |
| `lookup` `values` | server-provided compact scalar list | same normalized list | read-only |
| `lookup` numeric/count | server-provided number or permitted `null` empty state | same | read-only |
| absent lookup | cell/value omitted using existing hidden/missing-field convention | omitted | never editable |

Renderers do not parse internal options, dereference IDs, query target records or aggregate arrays. When safe response has no field key, they do not invent zero, empty string, “permission denied”, target table name or dependency path.

## 5. Permission and Failure Boundary

The module depends on existing `field.manage`, `table.read`, `record.read`, `record.create`, `record.update` and field read/write policy. It adds no relation/lookup capability, client role, permission editor or permission persistence.

Browser presentation state is not authority. Server always rechecks target scope/visibility on candidate read and record write; server rechecks every lookup hop for safe rendering. Any target/field/hop denial degrades by omission according to the F2 BDD, not by client filtering of raw payloads.

## 6. Responsive and Accessibility Boundary

At 1440/1280 the builder is a constrained desktop drawer and Picker remains keyboard navigable. At 430/390 builder and picker use a labelled full-screen sheet, large tap targets, visible selected-chip removal and no hover-only control. Focus returns to the invoking safe table/record control only when the same verified scope remains active.

## 7. Acceptance Links

- Behavior/edge cases: [F2 BDD and Acceptance](../STAGE_07_F2_RELATION_LOOKUP_BDD_AND_ACCEPTANCE.md)
- Service/API/data flows: [F2 SDD](../STAGE_07_F2_RELATION_LOOKUP_SDD.md)
- Requirement/state/code/evidence navigation: [F2 Complex Feature Index](../STAGE_07_F2_RELATION_LOOKUP_COMPLEX_FEATURE_INDEX.md)
- Approved request/read boundary: [Stage07 API Data Security Contract](../STAGE_07_API_DATA_SECURITY_CONTRACT.md)
