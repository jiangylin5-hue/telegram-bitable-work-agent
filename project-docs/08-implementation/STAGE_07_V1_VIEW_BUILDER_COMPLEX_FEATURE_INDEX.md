# Stage07 V1 Saved View Builder Complex Feature Index

## Status

- Document status: user-approved complexity/index inventory; approved implementation in progress
- Scope: V1 configuration/ACL/query state, logical indexes, proposed physical PostgreSQL indexes and evidence ownership
- Current Progress: V1-1 through V1-8 create the correctness-critical grant uniqueness constraint, strict typed command/read boundary, canonical safe query-shape projection, service-owned Grid filter/group/stable-sort ordering before cursor pagination, five safe HTTP route boundaries, real PostgreSQL security/index-plan evidence and typed browser transport that strips unknown response data before protected query state. Task 7 measured the access query using existing `ix_stage06_views_table_id` and `uq_view_member_grants_view_user`; `ix_view_member_grants_user_status` and `ix_views_table_scope_status` remain explicitly deferred, not merely unimplemented.

## 1. Purpose

V1 crosses view configuration, member ACL, field-level visibility, typed filtering/sorting and protected client state. This index prevents two mistakes:

1. treating JSON configuration as an arbitrary client document; and
2. adding database indexes before a query shape and real PostgreSQL evidence justify them.

## 2. Resource And Dependency Graph

```text
WorkspaceMember(active)
-> BitableBase
-> PlatformTable
-> PlatformField(field policy)
-> PlatformView(scope, owner, version, canonical presentation)
   -> ViewMemberGrant(editor/viewer)
   -> filter/sort/group/date/form field references
-> safe presentation and filtered record window
-> audit/idempotency
```

Every stored field reference is validated on mutation. Read paths re-evaluate current field visibility instead of trusting historical configuration.

## 3. Logical Indexes

| Logical key | Consumer | Invariant |
| --- | --- | --- |
| `(table_id, is_default=true)` | Base open/default view | exactly one system default Grid per table; existing physical partial unique index owns this |
| `(view_id, user_id)` | ACL lookup/grant replacement | one recipient grant only; owner is not a grant |
| `(owner_user_id, scope, status)` | owner private/restricted view list | inactive owner cannot access/orphan view |
| `(workspace_id, table_id, actor_id, builder capability)` | Builder context | no context crosses active member/table authority |
| `(view_id, version)` | presentation/member optimistic concurrency | `expected_version` must match locked server row |
| `(view_id, field_key)` | canonical configuration validation | every configured key belongs to view table and is readable at read time |
| `(field_id, readable actor, select-like type)` | Builder discrete filter choices | only validated readable `status`/`single_select`/`multi_select` choices project as `filter_values`; no raw options cross the boundary |
| `(field_id, visible relation field, caller scope)` | F2 relation filter candidate selection | Builder carries only the safe existing field resource ID; the F2 route still enforces relationship and record visibility |
| `(view_id, cursor, verified user/workspace)` | protected records cache | no cursor page crosses identity/scope |
| `(relation_field_id, candidate query, cursor)` | F2 filter value picker | only F2 safe candidate projection supplies relation filter values |

## 4. Proposed Physical PostgreSQL Indexes

| Candidate index | Query it serves | Required proof before migration | Current state |
| --- | --- | --- | --- |
| `uq_view_member_grants_view_user` | replace/read grants safely | concurrent duplicate-grant test and migration rollback proof | implemented; real PostgreSQL proves physical uniqueness |
| `ix_view_member_grants_user_status` | list restricted views accessible to recipient | `EXPLAIN (ANALYZE, BUFFERS)` with realistic recipient grant cardinality | explicitly deferred after Task 7; existing unique grant index serviced measured access query |
| `ix_views_table_scope_status` | list system/private/restricted active views for table | explain evidence against table with mixed scopes | explicitly deferred after Task 7; existing table index serviced measured access query |
| optional JSONB configuration index | no baseline query is approved | only if a measured server-side canonical config lookup requires it | explicitly not proposed |
| record filter/sort field index | table data query | one migration decision per field/query pattern after workload measurement | explicitly deferred |

The existing `uq_views_one_default_per_table` from `20260710_0021` remains. V1 must prove it still rejects two defaults and that no migration changes an existing default into a private/restricted view.

## 5. Configuration Dependency Constraints

| Configuration reference | Validation at save | Read degradation |
| --- | --- | --- |
| visible field | active, table-owned, field-readable, de-duplicated | omit hidden/missing key; never substitute |
| filter field/operator/value | type eligible, operator allowlisted, typed literal/candidate permitted | invalid historical condition yields no leaked raw config; safe generic view failure/omission policy from V1 service |
| sort field | eligible, unique, at most three | omit invalid historical sort; server does not let browser sort instead |
| group field | one status/single-select/user field | omit group metadata when unreadable/invalid |
| Calendar date | one readable date field | Calendar safe unavailable state; no guessed date |
| Form field | readable, ordered form-compatible field | omit invalid field; no hidden value |
| grant recipient | active member in same workspace, not owner | grant ineffective/remove from safe response if member inactive |

## 6. State Transition Index

| From | Event | To | Server action |
| --- | --- | --- | --- |
| none | initialise valid view | private/version 1 | insert view + idempotency + audit atomically |
| private | replace nonempty grants | restricted/version+1 | replace grants + scope + audit atomically |
| restricted | replace empty grants | private/version+1 | delete grants + scope + audit atomically |
| private/restricted | valid presentation patch | same scope/version+1 | row lock, validate canonical presentation, audit |
| any V1 user view | owner leaves/inactivates | inaccessible | deny all safe reads/mutations; no ownership transfer |
| system_default | configuration by `view.manage` | system_default/version+1 | update allowed presentation only; no grants/scope change |
| any | expected version mismatch | unchanged | return `view_version_conflict` |

## 7. Error-Code Index

| Code | Owning validator | Browser treatment |
| --- | --- | --- |
| `view_name_invalid` | normalized name | fixed local text |
| `view_type_unsupported` | type union | fixed local text |
| `view_version_conflict` | locked version check | conflict lock; no implicit retry |
| `view_member_not_active` / `view_member_invalid` | member grant validator | fixed local text, no member detail |
| `view_member_grant_forbidden` | owner/editor/viewer guard | generic safe denial |
| `view_field_not_visible` | field/table scope validator | fixed local text, no hidden key disclosure |
| `view_filter_invalid` | typed condition grammar | fixed local text |
| `view_sort_invalid` | sort cap/eligibility | fixed local text |
| `view_group_invalid` | grouping eligibility | fixed local text |
| `view_date_field_invalid` | Calendar date validator | fixed local text |
| `view_form_field_invalid` | Form field validator | fixed local text |
| `view_default_ineligible` | system default invariant | fixed local text |

Unknown/malformed error bodies, 401/403/404 and provider/database errors do not add specific client wording or server `detail.message` rendering.

## 8. Test Ownership Index

| Risk | Primary tests | Mandatory evidence |
| --- | --- | --- |
| ACL escalation | service/API negative tests | owner/editor/viewer plus lost underlying authority |
| atomic create/grant rollback | real PostgreSQL integration | no view/grant/audit/idempotency residue |
| duplicate grants/concurrent update | real PostgreSQL integration | unique constraint and one version winner |
| config grammar | unit/API parameter matrix | every field/operator/type rule |
| execution correctness | integration query tests | filter/sort before pagination, deterministic tie-break |
| hidden field leakage | response scans and revocation tests | summary/presentation/records/builder all omit it |
| stale state | Mini App application tests | view/workspace/session replacement cancels exact keys |
| responsive safety | actual Browser fixture | 1440/1280/430/390, console `[]` |

## 9. Explicit Non-Indexes

- no client-owned localStorage/sessionStorage view cache;
- no broad JSONB GIN index for arbitrary config searching;
- no generic query plan cache or expression index;
- no automatic record-field indexes implied by a view configuration;
- no index that exposes ACL membership or hidden field metadata to a client.
