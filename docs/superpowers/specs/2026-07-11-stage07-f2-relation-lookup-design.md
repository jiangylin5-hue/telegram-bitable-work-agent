# Stage07 F2 Relation and Lookup Design

## Status

- Status: user-approved design specification; the detailed implementation plan awaits user review and runtime work still requires separate explicit API/read-model/permission-change authorization.
- Date: 2026-07-11
- Scope: Stage07 Package 2 F2 — safe same-Base `linked_record` and nested/aggregated `lookup` field creation, safe relation selection and use in record create/direct edit.
- Explicit non-scope: V1 additional View Builder, cross-Base relation, reverse fields, field edit/delete UI, more than two lookup levels, arbitrary formula/aggregation DSL, imports/templates, governance, Bot, draft confirmation, Telegram and production rollout.
- Source alignment: `AGENTS.md`; `HANDOFF.md`; `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`; `STAGE_07_SDD.md`; `STAGE_07_API_DATA_SECURITY_CONTRACT.md`; `modules/STAGE_07_BITABLE_WORK_SURFACE.md`; `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`; `STAGE_07_TEST_PLAN.md`; Stage06 platform model, authorization, audit and record-link services.
- Mature reference boundary: follow the official Lark Base grammar of separately managed fields, records and saved views, with lookup treated as read-only. The project does not copy Lark APIs, raw field JSON, source code or UI. See [official lark-base skill](https://raw.githubusercontent.com/larksuite/cli/main/skills/lark-base/SKILL.md).

## 1. Purpose

F1 creates independent fields but deliberately excludes relationships and derived values. F2 makes the table system capable of expressing durable, permission-filtered cross-table business relationships without turning the Mini App into a raw schema/policy console.

```text
authorized source table
-> create a same-Base linked-record field
-> choose authorized target records through a server-composed picker
-> persist versioned relation IDs and record links
-> create a read-only lookup over that relation
-> server evaluates visible nested/aggregated values
-> authorized Grid, Detail and Form render only safe projections
```

The durable model remains the project constitution:

```text
workspace -> base -> table -> field -> record -> saved view -> permission -> audit
```

No relationship result is completed by chat text, a client-side join, cached raw record data or an unpersisted JSON projection.

## 2. Confirmed Product Decisions

| Topic | Confirmed F2 rule |
| --- | --- |
| Relation scope | A `linked_record` target table must be in the same Base. The source and target table may be the same. Cross-Base relation and reverse-field creation are absent. |
| Cardinality | Relation fields store an ordered multi-select list of target record IDs. |
| Self relation | A record may not associate itself, even when the target table equals the source table. |
| Required | Relation fields retain the F1 `required` setting. Existing records are not backfilled; new record/create and direct-edit flows validate it. |
| Lookup scope | A lookup selects one source relation field and one readable target field. It is read-only. |
| Nesting | A lookup may resolve one nested lookup, for a maximum of two lookup levels. Schema-time and read-time dependency checks reject cycles. |
| Aggregation | Fixed enum only: `values`, `count`, `count_distinct`, `sum`, `average`, `min`, `max`. There is no formula/DSL. |
| Aggregation shape | `values` returns an ordered, one-dimensional safe value list. `count` counts readable linked records. `count_distinct` deduplicates normalized safe values. Numeric aggregations accept only numeric target fields and return a number or `null`. |
| Permission degradation | Any unreadable relation target, target field or nested lookup makes the entire current lookup result absent. It never returns a partial aggregate. |
| Display labels | Candidate and rendered relation labels use the target table's readable `primary_field_id` when possible; otherwise the first readable independent text-like field by durable order. A record with no safe label is not a picker candidate. |
| Writes | Relation values use existing versioned record create/PATCH semantics; the server rechecks every submitted target ID. |
| Deletes | A referenced target record cannot be deleted. A field used by relation/lookup configuration cannot be deleted. No hidden cascade mutation is allowed. |
| Saved views | New F2 fields are appended once to every active same-table view with an explicit field list, in the same transaction. Views without an explicit list continue their existing all-current-fields behavior. |
| Errors | The browser maps a small safe error-code allowlist to fixed local text. 401/403/404, unknown codes and backend messages never disclose resource or dependency details. |

## 3. Reuse and Technology Boundary

F2 extends existing project-native boundaries only.

| Existing asset | F2 reuse |
| --- | --- |
| `PlatformField.options` JSONB | Server-only relation/lookup configuration. No new database column is planned. |
| `RecordLink` model and link synchronization | Durable source/target link projection; F2 extends validation and deletion guards instead of adding a client-side join store. |
| F1/P3 initializers | Dedicated atomic endpoint, idempotency scope, table lock, safe receipt, affected-view update, sanitised audit and authoritative reread. |
| Existing record create/PATCH | `required`, type, version, ownership and audit path. F2 adds target-authorisation rechecks; it does not introduce a second record write protocol. |
| Stage07 Mini App safe read models | Permission-filtered schemas, views, records and details; no raw `options`, `permission_policy`, role or audit body reaches the browser. |
| `@tanstack/react-query` TD001 boundary | Verified user/workspace query keys, cancellation, cache removal and late-response protection. |
| Existing Builder/Detail/Create UI | Accessible desktop drawer, mobile sheet, direct edit and create panel. No form engine, DnD/grid engine or new UI dependency is added. |

F2 introduces no package, queue, cache persistence, client-side relation engine or permission role. If implementation demonstrates that a database migration or new permission capability is necessary, it must stop for a new user decision; this design does not authorize either change.

## 4. Server-Only Configuration and Safe Read Models

### 4.1 Stored configuration

The browser never receives these internal option structures through schema, receipt, view or audit responses:

```ts
// Server-owned PlatformField.options conceptual shapes.
type RelationOptions = {
  target_table_id: string
}

type LookupOptions = {
  source_field_id: string
  target_field_id: string
  aggregation: 'values' | 'count' | 'count_distinct' | 'sum' | 'average' | 'min' | 'max'
}
```

Lookup configuration uses stable field IDs. Existing Stage06 lookup configurations that use legacy field keys remain readable by existing backend code, but the F2 Mini App never writes legacy key configuration. Rename preserves the field key and ID; deletion is blocked while a dependency exists.

### 4.2 Safe schema and record projections

The Mini App safe schema continues to expose only field identity, display name, type, `required`, approved choice options and order. It does not expose `target_table_id`, lookup source/target IDs, aggregation, default values or policy.

Relation read values are projected only by the server:

```ts
type SafeRelationCell = { id: string; label: string }
type SafeLookupCell = unknown[] | number | null
```

For a permitted relation field, a record/view value is `SafeRelationCell[]` in the stored order. `id` is opaque and serves only as the current relation-field editing value; `label` is a permission-filtered display value. A relation target that cannot produce a readable label is absent rather than converted to an ID, placeholder or client-side fallback.

Lookup values are the server-normalized `SafeLookupCell` result. The browser displays them but neither resolves a relation, traverses nesting nor aggregates data.

`GET /tables/{table_id}/create-form` safely adds a field's opaque `id` to its existing writable field item only when the F2 picker is allowed to edit it. It does not add relation configuration or candidate records. This lets the client use the field-specific picker without guessing a field ID.

## 5. Proposed Safe API Contract

### 5.1 Relation field initializer

```http
POST /tables/{table_id}/relation-field-initializations
Idempotency-Key: <opaque non-empty value, max 160 characters>
Content-Type: application/json
```

```json
{
  "name": "关联客户",
  "target_table_id": "<opaque-table-id>",
  "required": true
}
```

The request forbids extra keys. It resolves the source table and target table server-side, verifies same-Base ownership and authorisation, normalizes the name and rejects an invalid/hidden target through generic denial semantics. It generates the field key and order itself.

### 5.2 Lookup field initializer

```http
POST /tables/{table_id}/lookup-field-initializations
Idempotency-Key: <opaque non-empty value, max 160 characters>
Content-Type: application/json
```

```json
{
  "name": "客户累计金额",
  "source_relation_field_id": "<opaque-field-id>",
  "target_field_id": "<opaque-field-id>",
  "aggregation": "sum"
}
```

The source field must be an allowed `linked_record` on the source table. The target field must belong to that relation's fixed target table, be currently readable to the caller and be type-compatible with the selected aggregation. `linked_record`, `json` and formula fields are not eligible target values. A lookup target may itself be an eligible lookup only when it satisfies the two-level graph bound and causes no dependency cycle.

### 5.3 Common safe receipt

Both initializers return only a safe navigation/cache receipt:

```ts
type F2FieldInitializationReceipt = {
  field: {
    id: string
    table_id: string
    name: string
    key: string
    field_type: 'linked_record' | 'lookup'
    required: boolean
    options: {}
    order_index: number
  }
  affected_view_ids: string[]
}
```

It excludes target table/field configuration, aggregation, policies, defaults, roles, idempotency storage, audit state, target records and values.

First success returns `201`; same key/same normalised request returns the original `200` receipt; same key/different request is `409`. The client retains an idempotency key only for an explicit network/5xx retry and locks a `409` dialog until close, matching P3/F1.

### 5.4 Relation Candidate Picker

```http
GET /fields/{field_id}/relation-candidates?q=<optional-safe-search>&cursor=<opaque-cursor>
```

The endpoint accepts one relation field ID, optional bounded search text and an opaque cursor. It returns:

```ts
type RelationCandidatePage = {
  field_id: string
  records: Array<{ id: string; label: string }>
  next_cursor: string | null
  has_more: boolean
}
```

The server resolves the relation field's fixed target table, checks the caller's active workspace membership and `record.read`, applies target record/field visibility, derives a readable label, filters server-side and paginates server-side. It never accepts an arbitrary table, view, label-field ID or raw filter DSL from the browser.

## 6. Authorization, Transaction and Evaluation Rules

### 6.1 Authorization matrix

| Operation | Required server checks |
| --- | --- |
| Create relation field | Active workspace membership; source `field.manage`; target `table.read`; same Base. |
| Create lookup field | Active membership; source `field.manage`; source relation `field.read`; target table `table.read`; target field `field.read`; same Base via the relation. |
| Candidate page | Active membership; source relation field readable; target `record.read`; target label field readable. |
| Record create/PATCH relation value | Existing create/update permission plus source relation writable; same Base; configured target table; every target record exists and is readable; source record is not one of its own submitted targets. |
| Relation/lookup render | Existing view/detail permission plus field-read permission at every hop. |
| Delete referenced record or dependency field | Existing delete action plus reference/dependency check; conflict when still referenced. |

Navigation visibility remains only a UI hint. Every route and evaluation rechecks server authority.

For a required relation field, record creation rejects `null` or an empty target-ID list. A direct PATCH may omit the field for an existing historical record, but may not explicitly set that required relation field to `null` or an empty list. This preserves F1's no-backfill rule while making a newly created/edited required relation real.

### 6.2 Atomic field creation

Each F2 initializer holds the source-table schema lock and performs all of the following in one transaction:

1. resolve and authorize all source/target resources;
2. normalize/validate request and reserve/replay idempotency;
3. construct the internal config, validate the lookup dependency graph and assign next durable `order_index`;
4. persist one field with default policy `{}`;
5. append its key once to eligible active same-table view explicit field lists;
6. write a sanitized resource audit event; and
7. store a completed safe receipt and commit.

Failure rolls back field, view config, audit and incomplete idempotency state together. Concurrent distinct F2 field creation serializes on the source table lock. No browser mutation of raw saved-view configuration occurs.

### 6.3 Lookup evaluation

Lookup evaluation resolves links in relation order. It validates the dependency graph at field creation and enforces the same graph/depth guard at read time. A nested lookup chain can contain at most two lookup nodes counting the current field. An invalid configuration, missing target, unreadable target record, unreadable target field or unreadable nested lookup returns an absent current lookup value rather than a partial, masked or inferred aggregate.

For permitted values, the server flattens valid primitive values into the stable one-dimensional `values` output. `count` uses readable linked-record cardinality. `count_distinct` uses normalized readable values. `sum`, `average`, `min` and `max` require a numeric target field and return a numeric value or `null` when no permitted numeric values exist.

### 6.4 Delete protection

Record deletion checks incoming `RecordLink` references before removing the target. A positive reference count returns an allowlisted conflict without exposing source resource identities. Field deletion checks relation/lookup dependencies by stable IDs, including F2 configurations, before removal. No automatic unlink, cascade delete, version bypass or silent cross-record write is permitted.

## 7. Mini App Interaction and Cache Contract

### 7.1 Builder

The existing capability-gated `添加字段` entry gains two F2 types:

- **关联记录**: name, target table and required toggle.
- **查找**: name, source relation, target field and fixed aggregation.

Target tables and fields are chosen only from existing server-filtered Base table/schema reads. The form never shows an internal ID, raw configuration, policy or arbitrary aggregation expression. Desktop uses the existing compact drawer; mobile uses the existing full-screen sheet.

### 7.2 Create and direct edit

`linked_record` fields render as label chips and use a shared Relation Picker. The Picker supports server-side search, cursor loading, ordered multi-select and chip removal. Direct edit submits the full ID array under existing record version semantics; create uses the existing record-create route. `lookup` fields are always read-only and display only server-projected values/aggregates.

Required relation fields receive local empty-value guidance, but the server is final authority. The UI does not support relation self-selection when editing an existing record.

### 7.3 Protected query lifecycle

Candidate keys are scoped as:

```text
['stage07', userId, workspaceId, 'relation-candidates', fieldId, query, cursor]
```

F2 field success clears/rereads exact table schema, affected view presentation/record windows and create-form model, then verifies the safe receipt ID before rendering. Relation-record success follows the existing TD001 direct-mutation path and rereads only the current record/current first view window. Workspace/session changes cancel/remove candidate and all other protected queries. No candidate label, relation ID, hidden field or aggregate is persisted to browser storage or telemetry.

### 7.4 Safe error UI

The client may map only these fixed safe validation/conflict codes to fixed Chinese messages: `relation_self_reference`, `lookup_source_not_relation`, `lookup_target_incompatible`, `lookup_dependency_cycle`, `lookup_depth_exceeded`, `record_is_referenced` and `field_has_dependencies`. It never renders backend `detail.message`, raw target IDs/names, dependency paths or unknown codes. 401/403/404 use the existing safe state boundaries.

## 8. Verification and Acceptance

### 8.1 Automated backend evidence

- relation initializer: permission, same-Base, same-table, invalid target, required, idempotency replay/conflict, order lock, affected-view append, sanitized audit and rollback;
- lookup initializer: all aggregation/type combinations, legacy-config compatibility, target/source authorization, two-level depth, self/cyclic dependency denial, idempotency, rollback and audit;
- Candidate Picker: field/resource authorization, server search, cursor, primary/fallback label, unreadable target/label omission, no raw fields/configuration;
- record creation/PATCH: allowed target writes, cross-Base/wrong-table/unreadable/missing/self target denial, required relation enforcement and link synchronization;
- lookup reads: normal values, all fixed aggregation semantics, nested allowed result, unreadable hop omission, numeric empty result and no target detail leak;
- delete guards: incoming link and dependent-field conflict, followed by success only after explicit relation/dependency removal.

### 8.2 Real PostgreSQL evidence

The authorised disposable local PostgreSQL matrix must prove table-lock serialization, F2 atomic rollback, same-key replay, lookup dependency/delete guards and concurrent relation update integrity. It must not run against development, staging or production because the stage smoke/reset workflow is destructive.

### 8.3 Frontend and UI evidence

- unit/application tests cover builders, safe API payloads, local error-code mapping, chip rendering, Picker search/pagination, required validation, direct-edit conflict, 401/403/404 cleanup and stale workspace response rejection;
- fresh production build and full Mini App suite pass;
- a disposable local transport fixture exercises both initializers, relation create/edit, nested lookup, each aggregation family, denied/invalid states and candidate pagination;
- actual Mini App Browser QA at 1440px, 1280px, 430px and 390px checks desktop drawer, mobile full-screen picker/sheet, no stale scope restoration and zero relevant console warnings/errors;
- all fixture code, servers and transient artifacts are removed or explicitly retained as sanitized evidence before commit.

## 9. Explicit Non-Goals and Stop Conditions

F2 must not silently implement reverse links, cross-Base targets, arbitrary view setup, formula DSL, more than two lookup levels, auto-unlink/delete cascades, field permission editing, field update/delete UI, import/template, governance, Bot/draft/Telegram paths or production deployment.

Implementation must stop and request a new user decision if it needs a database migration, new role/capability, persistent browser storage, an additional runtime dependency, an arbitrary config/DSL input, a third lookup level, a reverse field, automatic cascade mutation or a contract that exposes policy/raw field data to the browser.
