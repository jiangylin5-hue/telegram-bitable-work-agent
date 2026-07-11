# Stage07 V1 Saved View Builder Design

## Status

- Document status: user-approved comprehensive V1 design; detailed implementation plan awaiting user approval
- Scope: all saved view types (`grid`, `kanban`, `calendar`, `form`), server-owned presentation semantics, personal/restricted member view access, safe creation/configuration and responsive Mini App work surface
- Current Progress: user-approved design and detailed TDD plan only. No V1 runtime code, migration, endpoint, dependency or role/capability change has been made.
- Prerequisites: Stage07 P3, F1 and F2 are bounded `implemented-local` evidence; this proposal must not be interpreted as widening their accepted contracts.

## 1. Goal And Product Boundary

V1 turns the current read-only view renderer into a durable saved-view system. It must let an authorised user create and configure Grid, Kanban, Calendar and Form views without ever giving the browser raw view configuration, raw permission policy, hidden field metadata or a way to invent query semantics.

```text
verified identity + active workspace member
-> table/Base authority and field-read filtering
-> accessible saved view summary
-> server-projected presentation and server-filtered record window
-> owner/editor/viewer view ACL intersection
-> audited, versioned configuration mutation
```

The durable table remains the source of records. A view is a bounded, permission-filtered query and presentation resource; it is not a client-side copy of records, a free-form SQL/query builder or a way to bypass Base/Table/Field authority.

### In scope

1. Saved `grid`, `kanban`, `calendar` and `form` views for one table in one Base.
2. Personal private views, restricted member-shared views and the existing system default Grid.
3. View ACL levels `owner`, `editor`, `viewer`, intersected with underlying active membership, Base/Table/Record/Field authorization.
4. Server-owned field visibility/order, flat `AND` filters, up to three sorts, one group field, Calendar date field and Form field order.
5. Safe create, edit, ACL-management and default-view administration flows with idempotency, version conflict and audit evidence.
6. Desktop builder workbench and complete mobile sheet/reader paths.

### Explicitly out of scope

- Public links, anonymous access, member groups, delegated sharing, role mutation, ACL inheritance and cross-workspace/Base/table views.
- `OR`, nested filter groups, arbitrary expressions, SQL-like syntax, formulas, client-side filtering/sorting/grouping, dashboards and charts.
- Card/layout designers, custom form pages, public form submission, record automation, view deletion/restore UI, import/template, Bot/Telegram, production rollout and any data retention change.
- Changing the F2 relation/lookup contract. V1 only consumes its safe relation cells, candidate picker and lookup projections.

## 2. Confirmed Decisions

| Topic | Adopted V1 rule |
| --- | --- |
| Scope | Complete V1 designs all four view types; Grid is the first implementation slice, but Kanban/Calendar/Form are specified now so they do not grow incompatible contracts later. |
| New views | Every user-created view starts `private`; its creator is its server-owned `owner`. |
| Sharing | An owner can add active workspace members as `editor` or `viewer`, making the resource `restricted`. There is no general “share with all Base members” toggle. |
| ACL | Owner changes configuration and ACL; editor changes only configuration; viewer reads only. Every operation still requires underlying workspace/Base/Table/Record/Field authority. |
| Default | The existing system default view remains the only default: it must be a shared Grid, is not private, and does not move when a personal/restricted view is created. V1 adds no default reassignment flow. |
| Grid | Visible fields/order, flat `AND` filtering, at most three stable server sorts and one group field. |
| Filters | Fixed per-field-type operators and typed values only; no `OR`, nested group or expression language. |
| F2 fields | Relation supports only safe “contains permitted record” filter via the existing candidate Picker. Numeric lookup supports typed filter/sort. Relation and lookup never group. |
| Error UX | Browser maps a documented fixed code allowlist to local text and never renders backend `detail.message`. |
| Persistence | View ownership, scope, version and ACL are durable server data. The browser retains only protected QueryClient state; it has no persistent view cache. |

## 3. Mature Architecture Reuse And Rejected Alternatives

The product grammar deliberately follows mature Base patterns: a table owns records, while each saved view owns a constrained presentation/query definition. NocoDB and Baserow provide useful product precedent for view-local filter/sort/group semantics; Lark CLI remains a capability-organization reference only, not a compatibility target.

| Approach | Assessment | Decision |
| --- | --- | --- |
| Reuse raw `POST /bases/{base_id}/views` and expose `config`/`permission_policy` | Fast but violates Stage07 safe-browser contract; client could submit raw policy or unsupported configuration. | Rejected. The route remains legacy/server-only. |
| Generic JSON Patch for a view document | Flexible but opaque, hard to validate/audit, permits accidental future key leakage and weakens typed error behavior. | Rejected. |
| Dedicated typed commands plus safe read projections | Reuses P3/F1/F2 idempotency, field filtering, protected-query and audit patterns. Every configuration branch is server validated and serializable. | Adopted. |

Relevant reuse references: [NocoDB Views](https://nocodb.com/docs/product-docs/views), [Baserow Views](https://baserow.io/user-docs/overview-of-baserow-views), and [larksuite/cli](https://github.com/larksuite/cli).

## 4. Durable Resource Model

### 4.1 View scope and ownership

The existing `views` table receives three server-owned attributes:

```text
owner_user_id: nullable stable user identity
scope: system_default | private | restricted
version: positive integer
```

- Existing P3-created default Grid rows migrate as `system_default`, keep `is_default=true`, and have no user owner.
- A V1-created row receives the caller as `owner_user_id`, `scope=private`, `is_default=false`, `version=1`.
- Adding the first ACL recipient changes only the server-owned scope to `restricted`; removing the last recipient returns it to `private`.
- A default view cannot be private/restricted, cannot have user ACL rows and is only configurable by a caller who passes existing `view.manage` and table/field checks.
- If a user owner is no longer an active workspace member, a private/restricted view is inaccessible to every caller and returns the normal non-disclosing missing/denied boundary. V1 has no ownership transfer path.

### 4.2 Member grants

New durable `view_member_grants` rows contain only:

```text
view_id, user_id, access_level(editor | viewer), status, created_at, updated_at
```

The owner is not duplicated as a grant. Each `(view_id, user_id)` is unique. A grant becomes ineffective immediately when its recipient is inactive, removed from the workspace, denied table access or denied every required field/resource decision. No stale grant may expose a summary, presentation, records or Builder metadata.

### 4.3 Effective authority

```text
view scope / ACL decision
-> active workspace membership
-> base/table action authorization
-> record read or view manage action
-> field read filter
-> requested operation
```

View ACL can reduce access, never expand it. A view `editor` who lacks `table.read` cannot read it; a user who can read the view but loses a configured field sees that field omitted from the projection, not substituted with another field.

## 5. Typed Presentation Grammar

Every persisted configuration is parsed, normalized and re-emitted by the server. The browser receives `SafeViewPresentation`, never the underlying JSONB document.

```ts
type SafeViewPresentation = {
  view_id: string
  table_id: string
  view_type: 'grid' | 'kanban' | 'calendar' | 'form'
  visible_field_keys: string[]
  filters: SafeFilterCondition[]
  sort_rules: SafeSortRule[]
  group_by_field_key: string | null
  date_field_key: string | null
  form_field_keys: string[]
}

type SafeFilterCondition = {
  field_key: string
  operator: string
  value: string | number | boolean | string[] | null
}

type SafeSortRule = { field_key: string; direction: 'asc' | 'desc' }
```

The canonical internal configuration may use stable field IDs, but safe output always uses only field keys that pass the current field-read decision. Invalid/hidden configured fields are omitted on read; a mutation that explicitly attempts to configure them is rejected before persistence.

### 5.1 Shared grammar

| Rule | Limit |
| --- | --- |
| visible field keys | ordered, de-duplicated, readable keys; no guessed fallback key |
| filter conjunction | literal `and` only |
| filter conditions | at most 12, all independently type validated |
| sort rules | at most 3, unique field keys, deterministic configured order |
| group | zero or one eligible field |
| date | exactly one eligible `date` field for Calendar; zero for other types |
| Form order | ordered readable/editable field keys; Form does not add public submission semantics |

### 5.2 Filter and sort eligibility

| Field family | Filter operators | Sort | Group |
| --- | --- | --- |
| text/url/email/phone | `equals`, `not_equals`, `contains`, `is_empty`, `is_not_empty` | yes | no |
| number and numeric lookup | `equals`, `not_equals`, `gt`, `gte`, `lt`, `lte`, `is_empty`, `is_not_empty` | yes | no for lookup; number no group |
| date | `equals`, `before`, `on_or_before`, `after`, `on_or_after`, `is_empty`, `is_not_empty` | yes | no |
| status/single_select | `is`, `is_not`, `is_empty`, `is_not_empty` using safe choices | yes | yes |
| multi_select | `contains_any`, `contains_all`, `is_empty`, `is_not_empty` using safe choices | yes | no |
| checkbox | `is_true`, `is_false` | yes | no |
| user | `is`, `is_not`, `is_empty`, `is_not_empty` using permitted stable IDs | yes | yes |
| linked_record | `contains_record`, `is_empty`, `is_not_empty`; selection comes only from F2 candidate API | no | no |
| nonnumeric lookup | no V1 filter/sort/group operation | no | no |
| json/formula/unknown/hidden | no V1 filter/sort/group operation | no | no |

The server applies filters, stable sorts and grouping before pagination. The Mini App never reorders a received window to imitate view semantics.

### 5.3 Per-view presentation

| View | Required keys | Optional keys | Prohibited V1 behavior |
| --- | --- | --- | --- |
| Grid | visible keys | filters, up to three sorts, one group | formula, client query, multiple group levels |
| Kanban | one eligible `group_by_field_key`, visible keys | filters, sorts | arbitrary card layouts, relation/lookup grouping |
| Calendar | one readable `date_field_key`, visible keys | filters, sorts | range query language or multiple dates |
| Form | ordered `form_field_keys` | visible keys only as a read projection | public submission, custom page layout, hidden default values |

## 6. Proposed Safe API Boundary

These are proposed V1 contracts, not current endpoints. They replace Mini App use of the legacy raw view route.

| Endpoint | Caller input | Server rule | Safe output |
| --- | --- | --- | --- |
| `GET /tables/{table_id}/view-builder-context` | none | requires active membership, table read and existing `view.manage`; filters all fields and member candidates | table summary, safe fields with allowed V1 operations, accessible views, safe active-member candidates `{id,label}` only when caller can manage ACL |
| `POST /tables/{table_id}/view-initializations` | `name`, `view_type`, typed presentation; `Idempotency-Key` | caller needs `view.manage`; server creates private owner view, validates config, writes audit and receipt atomically | `{ view: SafeViewSummary, affected_view_ids: string[] }` |
| `PATCH /views/{view_id}/presentation` | `expected_version`, `name?`, typed presentation | owner/editor or system-default `view.manage`; validates every key/value and increments version atomically | `{ view: SafeViewSummary, version }` |
| `PUT /views/{view_id}/members` | `expected_version`, full member list | owner only; recipients must be active members; normalizes scope private/restricted and increments version atomically | `{ view: SafeViewSummary, members: SafeViewMember[] , version }` |
| `GET /views/{view_id}/builder` | none | owner/editor only; underlying table/field filters still apply | safe editable presentation, version, scope and owner-visible grants |

`SafeViewSummary` contains only id, Base/table ids, name, type, scope, caller access level, status and default marker. `SafeViewMember` contains only recipient id, server-derived label and `editor`/`viewer`; it never returns raw membership, workspace role, policy or activity history.

No V1 client route sends `config`, `permission_policy`, `is_default`, owner ID, raw field option, raw member role or audit payload. Legacy `POST /bases/{base_id}/views` remains outside Mini App use until a later server-only compatibility decision.

## 7. Atomicity, Concurrency And Audit

| Mutation | Transactional unit | Replay/conflict rule | Audit event |
| --- | --- | --- | --- |
| initialize view | private view, idempotency record, audit | same normalized key/payload -> `200` original receipt; changed payload -> `409` | `stage07.view_initialized` |
| edit presentation | view row version + sanitized diff + audit | expected version mismatch -> `409`; no partial config | `stage07.view_presentation_updated` |
| replace members | view row lock, grants replacement, scope normalization, audit | expected version mismatch -> `409`; all-or-nothing recipient validation | `stage07.view_members_replaced` |

Audit stores resource ids, normalized view type/scope and changed safe configuration categories, never filter values that could be sensitive, raw ACL policy, field values, record output or user identity claims beyond stable audit actor/resource references.

## 8. Error And Failure Policy

The browser receives fixed local text only for this allowlist: `view_name_invalid`, `view_type_unsupported`, `view_version_conflict`, `view_member_not_active`, `view_member_invalid`, `view_member_grant_forbidden`, `view_field_not_visible`, `view_filter_invalid`, `view_sort_invalid`, `view_group_invalid`, `view_date_field_invalid`, `view_form_field_invalid`, `view_default_ineligible`.

- `401`: remove all protected state and enter existing expired-session boundary.
- `403`: remove only the affected workspace/view scope and render generic denied state.
- `404`: remove exact view/builder/query keys without previewing a parent/Base/table.
- `409`: preserve entered safe draft, lock the active panel until close/reload, never retry mutation implicitly.
- `422`: preserve the locally entered safe draft and render only fixed local feedback.
- network/5xx: retain a creation idempotency key for one explicit retry; edit/ACL changes are not implicitly retried.

## 9. Responsive Work Surface

Desktop shows saved-view tabs, an explicit new-view control, server-backed Filter/Sort/Group controls and an owner/editor settings drawer. Mobile retains the selected view, presents controls in labelled full-screen sheets, and never hides a required action behind hover. Read-only viewers see presentation controls only when they are no-op navigation state; mutation controls are absent.

The creation Builder progresses through one typed draft for identity/type and presentation, then submits one durable private-view command. Only after authoritative reread may its owner open the separate member-access panel; member replacement is its own atomic command, not a partially persisted creation step. It does not request records or candidate data outside the selected authorised table/view scope.

## 10. Acceptance Definition

V1 is not accepted by this design document. The user has approved this package and its linked BDD/SDD/module/index documents; the detailed TDD implementation plan now requires separate user approval before implementation may begin.

V1 local acceptance requires every V1-A row in the companion BDD matrix, real disposable PostgreSQL rollback/concurrency evidence, safe contract/authorization tests, all four width Browser scenarios, final console inspection and temporary-fixture cleanup. Telegram, production, broader Stage07 and Package 3/4 remain separate gates.
