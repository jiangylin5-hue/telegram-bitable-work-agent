# Stage07 V1 Saved View Builder BDD And Acceptance

## Status

- Document status: user-approved detailed V1 behavior and acceptance source; approved implementation in progress
- Scope: saved Grid/Kanban/Calendar/Form creation and configuration, personal/restricted member view access, safe query/presentation behavior and responsive Mini App surface
- Current Progress: V1-1/2 local durability and typed command/read-schema foundations are implemented: `PlatformView` ownership/scope/version, `ViewMemberGrant`, migration `20260711_0022`, narrow UoW methods, discriminated view presentation commands, bounded flat filter/sort/member inputs and raw-state-free safe view models. It has no real PostgreSQL acceptance yet and does not implement a V1 endpoint, authorization/configuration behavior or Mini App state.
- Design companion: `docs/superpowers/specs/2026-07-11-stage07-v1-saved-view-builder-design.md`

## 1. Actor And Resource Vocabulary

| Term | Meaning |
| --- | --- |
| `system_default` | Existing P3-created shared Grid with one-per-table invariant; no user owner or ACL grants. |
| `private` | User-created view visible only to active owner with underlying resource authority. |
| `restricted` | User-created view visible to active owner plus explicit `editor`/`viewer` grants, always intersected with underlying authority. |
| owner | Server-derived creator of private/restricted view. May edit presentation and replace member grants. |
| editor | Explicit active-member grant. May edit presentation, but cannot change member grants, scope or default state. |
| viewer | Explicit active-member grant. May read safe summary/presentation/records only. |
| safe presentation | Server-filtered, typed view semantics; never raw JSONB config, permission policy, owner identity or hidden field key. |
| filter draft | Browser-local typed data that has not persisted; it is discarded on scope/session replacement. |

Effective authority is always:

```text
view scope/grant -> active workspace member -> base/table/record action -> field read filter -> mutation/read
```

## 2. BDD Scenarios

### V1-01: New view starts private and is atomically durable

Given an active member has `view.manage` and table read authority
When they submit a valid typed Grid, Kanban, Calendar or Form view with an idempotency key
Then the server creates exactly one `private` view owned by that member with version `1`
And stores normalized presentation, completed idempotency receipt and sanitized audit in one transaction
And returns only a safe receipt, not raw config/policy/owner metadata.

### V1-02: Same-key replay and changed-payload conflict are deterministic

Given a completed view initialization key scoped to actor and table
When the same normalized payload is submitted
Then it returns the original safe receipt with `200` and no second view/audit/grant is written.
When the same key is submitted with a changed name, type or presentation
Then it returns `409`, creates nothing and the Builder locks until closed.

### V1-03: Creation rollback leaves no partial view or ACL

Given a valid initialization reaches view insertion
When grant validation, audit or idempotency write fails
Then the transaction rolls back the private view, audit event and completed idempotency record together.
No other user can list or open a partial resource.

### V1-04: System default view stays the only default shared Grid

Given a table has the P3 system default Grid
When a user creates, edits or shares another view
Then the default Grid remains unchanged and the new view is never default.
When a non-Grid/private/restricted view attempts default state
Then it receives `view_default_ineligible` without mutation.
V1 does not add default reassignment.

### V1-05: Owner grants constrained member access

Given a private view owner and an active member of the same workspace
When owner replaces grants with that member as `editor` or `viewer`
Then the view becomes `restricted`, increments version and writes one sanitized audit event.
When the last grant is removed
Then it returns to `private`.
An owner cannot grant themselves, an inactive/non-member recipient, an unsupported access level or an unknown user.

### V1-06: ACL never widens table or field authority

Given an editor/viewer grant exists
When recipient lacks active membership, Base/Table/Record read authority or the configured field is hidden
Then safe view access is denied or the field is omitted according to the underlying decision.
The grant never reveals a summary, raw config, field key, record value or candidate outside that authority.

### V1-07: Owner/editor/viewer operations are separated

Given a restricted view
When owner edits presentation or members, both may proceed subject to version.
When editor edits presentation, it may proceed but member replacement/default/scope mutation is denied.
When viewer attempts any mutation, it is denied before parsing payload.
System-default configuration requires existing `view.manage`, not an owner grant.

### V1-08: Field visibility and presentation order are server owned

Given a valid configuration names readable fields in order
When it is saved
Then the same normalized order appears in safe presentation and record projection.
Given a field is hidden, missing, duplicated or belongs to another table
When it is named in a mutation
Then `view_field_not_visible` is returned without a partial update.
When a previously readable configured field later becomes hidden
Then it is omitted from the next read rather than substituted.

### V1-09: Flat typed filters execute only on the server

Given a configured view contains at most twelve type-valid conditions joined by literal `and`
When records are read
Then the server evaluates the conditions before pagination and returns a filtered safe window.
When client payload includes `or`, nested groups, expression text, an unsupported operator or an untyped value
Then `view_filter_invalid` is returned.
The client never filters a larger authorised page locally to imitate saved semantics.

### V1-10: Filter eligibility protects complex fields

Given a relation field is visible
When owner/editor configures `contains_record` with a target selected through the existing F2 candidate route
Then the server validates the relation table and readable candidate before saving.
Given a numeric lookup is visible
When one numeric filter operator is used
Then it may be saved.
Nonnumeric lookup, hidden field, JSON, formula and unknown types cannot be V1 filter operands.

### V1-11: Stable server sorting and grouping remain bounded

Given a saved view has zero to three valid sort rules and zero or one valid group key
When its records are read
Then server applies the configured stable sort before pagination and the renderer consumes only that sequence.
When a duplicate sort field, fourth rule, relation sort, lookup group or ineligible group field is supplied
Then it returns `view_sort_invalid` or `view_group_invalid` without mutating the view.

### V1-12: View-type-specific keys are valid and fail closed

Given a Kanban view
When it is saved
Then it must have one eligible group key.
Given a Calendar view
When it is saved
Then it must have one readable `date` key.
Given a Form view
When it is saved
Then its ordered form keys are readable/editable under existing record form rules.
An invalid/missing key returns the fixed type-specific error and does not create or partially update the view.

### V1-13: Safe read models do not expose raw configuration or ACL

Given any accessible view
When list, presentation, record or Builder context is requested
Then response is limited to the documented safe summary/presentation/eligible-field/member-candidate models.
It never exposes `permission_policy`, raw JSONB `config`, raw membership role/status, owner identity, audit body, record values outside field filter or hidden field metadata.

### V1-14: Version conflict, denial and session replacement fail closed

Given an owner/editor has a Builder draft
When a conflicting update changes the server version
Then `409` locks the panel until reload/close and no blind retry occurs.
When 401/403/404, workspace switch, table switch, view switch or unmount occurs
Then exact protected builder/member/candidate/query state is cancelled or removed; a delayed response cannot restore the prior view or grant list.

### V1-15: Desktop and mobile use the same durable command

Given desktop width 1440/1280 or mobile width 430/390
When owner/editor opens the V1 Builder or viewer opens a saved view
Then they use the same typed, server-authorized resource and error semantics.
Desktop uses the documented drawer/workbench; mobile uses labelled full-screen sheets.
No required mutation is hover-only, and no mobile path turns a denied/partial response into a successful local view.

## 3. State And Error Matrix

| Surface | Required states | Terminal rule |
| --- | --- | --- |
| new view Builder | idle, locally-invalid, pending, success-awaiting-reread, replayed, conflict-locked, validation, denied, missing, retryable, cancelled, scope-invalidated | only authoritative safe list/context reread makes a new view visible |
| presentation editor | idle, dirty, field-ineligible, pending, conflict-locked, saved, denied, stale-response-discarded | no optimistic tab/config insertion; version is authoritative |
| member editor | owner-readable, no-recipient, recipient-search, invalid-recipient, pending, conflict-locked, saved-private, saved-restricted, denied | grants replace atomically; editor/viewer never see owner controls |
| view reader | loading, empty, filtered, grouped, denied, hidden-field-omitted, expired, missing | server ordering/filtering and field projection are rendered as received |
| default view | existing-system-default, inaccessible-config, management-denied | never converted to private/restricted or reassigned by V1 |

## 4. Acceptance Evidence Matrix

| ID | Requirement | Minimum evidence | Current status |
| --- | --- | --- | --- |
| V1-A01 | safe private initialization/replay/rollback | unit/API + real PostgreSQL | approved-design-unimplemented |
| V1-A02 | scope/owner/member ACL intersection | service/API negative tests + PostgreSQL unique grants | approved-design-unimplemented |
| V1-A03 | owner/editor/viewer mutation separation | service/API tests | approved-design-unimplemented |
| V1-A04 | existing default Grid invariant | migration + integration tests | approved-design-unimplemented |
| V1-A05 | typed configuration validation and safe projection | unit/API response scans | approved-design-unimplemented |
| V1-A06 | server filter/sort/group before pagination | unit/integration + real PostgreSQL | approved-design-unimplemented |
| V1-A07 | F2 relation/numeric lookup eligibility | unit/API + Picker contract tests | approved-design-unimplemented |
| V1-A08 | Kanban/Calendar/Form configuration validation | unit/API tests | approved-design-unimplemented |
| V1-A09 | protected query/cancellation/error containment | Mini App component/application tests | approved-design-unimplemented |
| V1-A10 | four-width actual Browser matrix | disposable local fixture + console scan | approved-design-unimplemented |

## 5. Completion Report Requirements

The V1 report must enumerate every V1-A result, changed files, schema/API/permission decisions, migration/index evidence, exact test/build/browser commands, skipped cases, fixture cleanup and remaining Stage07/Telegram/production gaps. It must not claim V1 or Stage07 production readiness without all listed evidence.
