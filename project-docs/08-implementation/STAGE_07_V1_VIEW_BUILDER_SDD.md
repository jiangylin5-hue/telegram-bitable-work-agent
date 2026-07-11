# Stage07 V1 Saved View Builder SDD

## Status

- Document status: user-approved technical design; approved implementation in progress
- Scope: durable V1 view ownership/ACL/configuration, safe server commands/read models and Mini App module boundary
- Current Progress: V1-1/2 local persistence and strict typed-schema foundations are implemented; service authorization/canonicalization, query, route and Mini App tasks remain pending. Optional access/list indexes remain deferred until the Task 7 PostgreSQL `EXPLAIN` evidence gate.

## 1. Architecture

```text
Mini App ViewBuilder / BaseCanvas / ViewSurface
-> typed V1 API client
-> FastAPI V1 view command/read routes
-> authorization + active membership + field filter
-> V1 View Service / Unit of Work
-> PlatformView + ViewMemberGrant + idempotency + audit
-> PostgreSQL
```

The V1 service sits beside existing `stage06_platform` primitives. It reuses the Stage06 `PlatformView` resource, P3/F1/F2 idempotency and audit transaction patterns, existing table/field/record authorization and TD001 protected-query behavior. It does not create a separate query engine, permission engine, ORM, queue or browser cache.

## 2. Backend Units And Responsibilities

| Unit | Responsibility | Must not do |
| --- | --- | --- |
| `view_builder_routes` | parse strict Pydantic commands, resolve identity/UoW, map safe error codes | expose raw config/policy or trust client role/scope |
| `view_builder_service` | validate typed config, compute effective view ACL, create/edit/replace grants, emit safe projections | evaluate client expressions or mutate Base/Table/Field permission |
| `view_config` validator | normalize typed field IDs/keys/operators/order into canonical config | accept arbitrary JSON/document keys |
| `view_query` adapter | apply validated filters/sorts before existing pagination; produce view-specific grouping metadata | run raw SQL or reorder browser windows |
| `safe_view_projection` | produce summary/presentation/builder context from current caller authority | leak owner/policy/raw member state |
| Mini App `ViewBuilderPanel` | collect only typed safe inputs and render server results | derive accessible fields/members or persist cache outside TD001 |
| Mini App `ViewAccessPanel` | owner-only member grant UI | infer roles or expose inactive member data |

## 3. Proposed Data Changes

### 3.1 `views` extension

| Column | Type | Rule |
| --- | --- | --- |
| `owner_user_id` | nullable string/identity reference | null only for migrated `system_default`; immutable after creation in V1 |
| `scope` | enum/text | `system_default`, `private`, `restricted` only |
| `version` | integer | starts at 1; increments for presentation/ACL mutation; used by `expected_version` |

Existing `permission_policy` is legacy/server-internal. V1 does not expose, accept or reinterpret it as user/member ACL. Existing default view rows migrate to `system_default`, preserve `is_default=true`, and do not receive grants.

### 3.2 `view_member_grants`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | UUID | server generated |
| `view_id` | FK `views.id` | same workspace/Base/table chain as view |
| `user_id` | stable user identity | must be active workspace member at mutation time |
| `access_level` | enum/text | `editor` or `viewer` only |
| `status` | text | active only in V1; future revocation uses normal status, not hard client state |
| timestamps | server owned | audit support only |

### 3.3 Required physical constraints/indexes

| Name | Purpose | Evidence required before migration acceptance |
| --- | --- | --- |
| `uq_view_member_grants_view_user` | one active recipient grant per view/user | concurrent replacement test in real PostgreSQL |
| `ix_view_member_grants_user_status` | efficient accessible-view membership lookup | explain/query evidence using realistic view count |
| `ix_views_table_scope_status` | safe table view list by active scope/status | explain/query evidence |
| existing `uq_views_one_default_per_table` | retain one default Grid invariant | migration regression, no duplicate default |

The detailed logical/physical index inventory is maintained separately in `STAGE_07_V1_VIEW_BUILDER_COMPLEX_FEATURE_INDEX.md`. No index enters a migration merely because it is listed here.

## 4. Authorization Algorithm

```text
resolve view -> resolve workspace/base/table
-> require active workspace membership
-> require base/table action for requested operation
-> if system_default: require table read for read, view.manage for config
-> if private/restricted: compare actor identity to owner or active grant
-> require owner/editor/viewer operation level
-> re-check record/field authority
-> emit only safe projection
```

| Operation | System default | Private/restricted owner | Editor | Viewer |
| --- | --- | --- | --- | --- |
| list/read summary/presentation/records | underlying read authority | yes, underlying read authority | yes, underlying read authority | yes, underlying read authority |
| builder read | `view.manage` | owner | editor | no |
| create view | no special owner rule; requires `view.manage` on table | caller becomes owner | n/a | n/a |
| edit presentation | `view.manage` | owner | editor | no |
| replace grants | never | owner | no | no |
| default mutation | not in V1 | not in V1 | not in V1 | not in V1 |

Recipient grants never substitute for a member’s table/record permission. A hidden field remains hidden in every safe response, even when its key is present in persisted canonical configuration.

## 5. Command Contracts

All V1 request models use `extra="forbid"`. UI-facing endpoints return safe models only.

```ts
type ViewInitializationRequest = {
  name: string
  view_type: 'grid' | 'kanban' | 'calendar' | 'form'
  presentation: ViewPresentationCommand
}

type ViewPresentationUpdateRequest = {
  expected_version: number
  name?: string
  presentation: ViewPresentationCommand
}

type ViewMembersReplaceRequest = {
  expected_version: number
  members: Array<{ user_id: string; access_level: 'editor' | 'viewer' }>
}
```

`ViewPresentationCommand` is a discriminated union by `view_type`. It accepts only `visible_field_keys`, flat `filters`, `sort_rules`, `group_by_field_key`, `date_field_key` and `form_field_keys` allowed for that type. It does not accept `config`, policy, owner, scope, default, status, raw field option or arbitrary layout key.

### Create sequence

1. Route resolves caller identity/workspace/table and independently checks `view.manage`.
2. Service validates name, view type, all field keys and type-specific semantics.
3. It locks table-level view mutation state, creates private owner row/version 1, writes idempotency and sanitized audit in one transaction.
4. On success route returns safe receipt; client invalidates exact protected table-view resources and rereads them.

### Presentation update sequence

1. Route resolves current view and caller edit authority before parsing sensitive context.
2. Service locks the view row, compares expected version, validates full typed presentation against current readable table fields and writes one normalized config/version/audit update.
3. Client invalidates exact presentation/records and rereads authorized resources. No optimistic saved configuration enters Canvas.

### Grant replacement sequence

1. Owner-only route locks view row and compares expected version.
2. It verifies every distinct recipient is active in the same workspace and is not owner.
3. It replaces all grants atomically, derives private/restricted scope, increments version and writes sanitized audit.
4. It clears exact protected view list/presentation/builder queries for owner and affected recipient scopes; old grants cannot remain rendered.

## 6. Query Semantics

The service parses canonical conditions, maps them to SQLAlchemy expression builders and applies them before cursor pagination. It may only use static field-type/operator mappings defined by V1; it may not interpolate a field key, operator or value into raw SQL.

```text
authorized table fields
-> canonical allowed condition list (AND)
-> SQLAlchemy typed predicate composition
-> stable sort tuple(s) + record ID tie-breaker
-> cursor pagination
-> field-filtered safe record projection
-> view-specific renderer metadata
```

Relation `contains_record` validates selected target identity through the existing linked-field service. Numeric lookup relies on existing safe computed value semantics; nonnumeric lookup is never made sortable/filterable by V1. Grouping is presentation metadata over the filtered/sorted safe record window and only accepts status/single-select/user fields.

## 7. Client Integration

| Client area | V1 responsibility |
| --- | --- |
| `api.ts` | typed V1 client functions and safe response types; no raw config/policy shape |
| `protectedQuery.ts` | query keys include verified user/workspace/table/view/version scope; exact invalidation/removal helpers |
| `App.tsx` | authorize entry visibility from server hints only, manage builder lifecycle and stale response cancellation |
| `BaseCanvas.tsx` | real Filter/Sort/Group controls open typed server-backed editor; view tabs show only accessible safe summaries |
| `ViewBuilderPanel.tsx` | create/edit form, four type-specific sections, idempotency/conflict/retry behavior |
| `ViewAccessPanel.tsx` | owner-only member replacement and safe candidate rendering |
| `ViewSurface.tsx` | consumes server-projected presentation/records; no semantic transformation of record data |

Desktop uses a left/right workspace drawer appropriate to existing BaseCanvas styling. Mobile uses one full-screen sheet per Builder or access flow, with panel state owned by protected current scope. The same server command is used at all widths.

## 8. Failure Handling

| Condition | Service response | Client behavior |
| --- | --- | --- |
| invalid name/type/field/filter/sort/group/date/form | `422` fixed code | retain typed draft, local fixed text only |
| recipient inactive/invalid | `422` fixed code | retain unrelated grant rows; no server detail |
| permission/membership denial | generic `403` | clear affected scope and generic denied boundary |
| missing view/resource | non-disclosing `404` | remove exact view and Builder query state |
| stale expected version | `409` | conflict-lock until close/reload; no blind retry |
| create network/5xx | retryable failure | retain one creation idempotency key for explicit retry |
| edit/ACL network/5xx | retryable failure | retain local draft but never replay implicitly |

## 9. Non-Goals And Compatibility

- Existing legacy raw view API remains intact for server-side/historical compatibility but is not a V1 Mini App contract.
- Existing system default Grid remains readable in the current renderer during migration; no data backfill changes fields/records.
- No new third-party package, permission engine, task queue, browser storage, SQL executor or generic rules language is introduced.
- View deletion, default reassignment and public forms are deferred and require later design/approval.
