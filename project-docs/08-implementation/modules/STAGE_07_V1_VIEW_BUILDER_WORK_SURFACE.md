# Stage07 V1 Saved View Builder Work Surface

## Status

- Document status: user-approved module/work-surface contract; approved implementation in progress
- Scope: every V1 user-facing saved-view state in BaseCanvas, desktop and mobile
- Current Progress: V1-1 through V1-8 durable persistence, typed schema, canonicalization, ACL/versioned mutation, server-owned Grid filter/group/sort ordering, five safe HTTP routes, PostgreSQL security/index proof and typed safe Mini App transport are implemented without Builder UI effect. Current toolbar buttons remain non-mutating until the panel tasks complete; the browser must not infer query semantics or consume page-local group metadata from the backend path.

## 1. Module Purpose

`V1 View Builder` makes saved view semantics visible and operable without turning the browser into a query or permission engine. It owns only view intent, safe draft state and server response rendering. It does not own records, field permissions, role membership or raw configuration.

```text
BaseCanvas
-> accessible view tabs and current safe presentation
-> ViewBuilderPanel / ViewAccessPanel
-> protected typed V1 request
-> authoritative safe reread
-> ViewSurface
```

## 2. Visible Entry Points

| Entry | Availability | Action | Forbidden behavior |
| --- | --- | --- | --- |
| saved view tab | any caller who receives summary | open selected safe view | infer/view hidden summaries |
| `新建视图` | server-hinted builder + endpoint authorization | open private-view builder | create synthetic local tab |
| Filter / Sort / Group | owner/editor of current configurable view | open typed configuration section | client-side record transform |
| `视图设置` | owner/editor | edit name/presentation | show raw config/policy |
| `访问成员` | owner only | open grant replacement section | expose workspace roles or inactive members |
| default view indicator | any caller reading system default | render read-only default marker | promote private/restricted view |

The existing `筛选`、`排序`、`分组` controls are presentation placeholders before implementation. V1 replaces them only after the server returns builder capability/context; it never makes their current client-only behavior authoritative.

## 3. Builder Information Architecture

The creation Builder contains identity/type and presentation only; desktop may show them as a drawer stepper while mobile uses a full-screen sheet. Submission remains one typed durable private-view command. Member access is available only after authoritative reread in a separate owner-only atomic panel.

| Section | Fields | Who may edit | Validation before request |
| --- | --- | --- | --- |
| Identity and type | name, Grid/Kanban/Calendar/Form | owner on create; owner/editor name update | nonempty normalized name, allowed type |
| Presentation | visible field order, filters, sorts, group/date/form keys | owner/editor | only context-returned fields/operators/values; `filter_values` is available only for readable select-like fields; max counts |

### Type-specific panels

| Type | Desktop/Mobile controls | Required browser state |
| --- | --- | --- |
| Grid | field list drag/reorder alternative with accessible move controls; filter rows; sort rows; one group select | all current fields visible in draft but only safe eligible actions enabled |
| Kanban | eligible group field select; fields; filter/sort | missing/hidden group cannot be locally guessed |
| Calendar | date field select; fields; filter/sort | only safe `date` keys are candidates |
| Form | ordered form field list | no public/share/submit layout control in V1 |

The visual grammar remains Workspace Ledger: white canvas, cool gray separators, restrained azure active state, compact tables and 8px radii. It must not introduce card-wall dashboards or a free-form “AI query” editor.

## 4. Field Control Semantics

### 4.1 Visibility/order

- Source is only `view-builder-context.safe_fields`.
- Hidden/missing fields never enter the field list; the draft cannot retain a field key after a context/permission reread omits it.
- Accessible keyboard commands move fields up/down; drag interaction may be added only as an enhancement, not as sole control.
- Form field order uses the same safe source and does not grant edit permission.

### 4.2 Filters

Each row contains a safe field select, a server-listed fixed operator select and a typed value editor. There is always an `AND` label; no UI for `OR`, brackets or expressions.

| Selected field | Value editor |
| --- | --- |
| scalar text/date/number/checkbox | controlled typed primitive input only |
| status/single_select/multi_select | controlled choice sourced only from the field's safe `filter_values`; no free-text option entry |
| user | controlled choice sourced only from active safe member candidates |
| linked relation | F2 `RelationPicker`; it returns opaque permitted IDs only |
| numeric lookup | numeric editor only |
| ineligible field | no filter row may be added |

Removing a row removes only local draft state. Saving validates the entire set on server; an error leaves the local safe row values visible but does not reveal backend message/detail.

### 4.3 Sort and group

- Sort rows cap at three; each row has safe eligible field and direction.
- Duplicate sort fields are immediately marked invalid locally and rejected server-side.
- Group has exactly one optional safe select. It may be status, single select or user; relation/lookup/multi-select do not appear.
- The current record grid is never sorted/grouped in browser JavaScript after response. Server-projected metadata and record order drive `ViewSurface`.

## 5. Access Member Panel

After private view creation has completed and reread, the owner sees only safe active member candidates `{id,label}`. No raw workspace role, invitation state, policy or account metadata is rendered.

| State | Required behavior |
| --- | --- |
| private/no grant | show owner-only explanation and empty member list |
| candidate search | debounced/cancelled protected request, exact current workspace only |
| grant row | selected safe label plus editor/viewer selector and remove action |
| pending replace | disable save/close/cancel action that would discard uncertain state; keep sheet/drawer visible |
| success | server reread decides private/restricted marker and visible recipients |
| editor/viewer | member panel omitted entirely, not merely disabled |
| 401/403/404 | remove exact scope and show existing safe boundary |

## 6. Protected Query Lifecycle

| Query | Key must include | Removal trigger |
| --- | --- | --- |
| builder context | verified user, workspace, table | workspace/table replacement, 401, close |
| editable view | verified user, workspace, view, version | view replacement, 401/403/404, close |
| member candidates | verified user, workspace, view/table, query/cursor | access panel close, workspace/view replacement, denial |
| view records | verified user, workspace, view, cursor and presentation version | configuration success, view replacement, permission loss |

Receipt success is a pointer only. Client invalidates exact table view list, view builder/presentation and current records, rereads each, verifies returned view/table relationship and then opens/renders it. An old response cannot open a view after owner scope, workspace, Base, table or selected view changed.

## 7. Responsive Matrix

| Width | Required V1 behavior |
| --- | --- |
| 1440 | table tabs, view tabs, toolbar and settings drawer usable; Grid preserves column density |
| 1280 | Builder/access drawer remains complete without toolbar overflow hiding an authorised control |
| 430 | new/configure/access opens labelled full-screen sheet; safe field/filter rows scroll independently |
| 390 | same command path; relation Picker/search and fixed error text remain visible without raw IDs/details |

All four widths need fresh Browser evidence for private create, restricted share, editor/viewer separation, a typed filter/sort/group state, a type-specific view, denial/conflict containment and final console scan. Existing F1/F2 Browser artifacts do not count as V1 evidence.

## 8. Deliberately Not Shipped By This Module

- personal last-opened-view browser preference;
- public sharing, link copies, member groups, owner transfer or role editor;
- deleting/restoring views or changing default view;
- query expressions, saved search, dashboards, charts or formula configuration;
- record mutation beyond existing authorized create/PATCH and Form field order presentation;
- import/template, Bot/draft/Telegram work.
