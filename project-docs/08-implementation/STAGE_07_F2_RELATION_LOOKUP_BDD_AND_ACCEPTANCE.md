# Stage 07 F2 Relation / Lookup BDD And Acceptance

## Status

- Document status: active detailed F2 behavior and acceptance source
- Scope: Stage07 Package 2 / F2 same-Base multi-select relation, bounded nested/aggregated lookup, safe candidate selection and record create/direct-edit follow-through
- Current Progress: approved F2 backend transport/initializers/read-write/lookup work and the bounded Mini App Picker, create/direct-edit, safe-rendering and Builder paths have local commits. The frontend has fresh `17` files / `87` tests and a passing production build after task-level independent review. No F2 end-to-end fixture acceptance, executable PostgreSQL acceptance or four-width Browser acceptance is claimed.
- Preconditions: approved F2 choices recorded in `docs/superpowers/specs/2026-07-11-stage07-f2-relation-lookup-design.md`; this document makes their behavior and evidence measurable.

## 1. Scope and Outcome

F2 adds durable table relationships without making the browser a data-join engine or a schema-policy console.

```text
authorised source table
-> one server-owned linked_record field
-> safe server-filtered candidate picker
-> versioned record relation IDs + RecordLink projection
-> one server-owned lookup field
-> server-only bounded evaluation
-> safe values in Grid, Detail and Form
```

F2 is complete only when each relevant scenario has automated evidence, real local PostgreSQL evidence where stated, and four-width Mini App evidence. A committed local branch is not acceptance.

Out of scope: reverse fields, cross-Base relation, third lookup level, arbitrary formula/aggregation DSL, field edit/delete UI, automatic unlink/cascade delete, V1 view configuration, import/template, Bot, Telegram, production rollout, a new role/capability, package or migration.

## 2. Actors, State Vocabulary and Terminal Rules

| Term | Meaning |
| --- | --- |
| builder | Active workspace member authorised by existing `field.manage`; UI visibility is only a hint. |
| reader/editor | Active member whose existing table/record/field policies allow the particular read or write. |
| relation field | `linked_record` field on one source table, storing an ordered de-duplicated list of opaque target record IDs. |
| lookup field | read-only `lookup` whose internal configuration identifies one source relation, target field and fixed aggregation. |
| absent lookup | The field key is omitted from a safe record/view response. It is a fail-closed permission/configuration result, not `null`. |
| numeric-empty lookup | A permitted numeric aggregation with no readable numeric values; it returns `null`. |
| replay | Same scoped idempotency key and normalized request returns the original safe receipt with HTTP `200`; no second mutation occurs. |
| conflict | Same scoped key with a changed normalized request returns HTTP `409`; browser locks the active builder until it is explicitly closed. |

No client state may turn a denied, cancelled, stale-scope or unknown outcome into success. A successful field receipt is only a navigation/cache pointer; the exact field must appear in an authorised reread before UI rendering.

## 3. BDD Scenarios

### F2-01: Builder creates one same-Base relation atomically

Given a builder has `field.manage` on source table A and `table.read` on target table B in the same Base  
When the builder submits a valid relation name, B's opaque ID and required flag with an `Idempotency-Key`  
Then one `linked_record` field is persisted with a server-generated key/order and server-only target-table configuration  
And it is appended once only to each active same-table view that has an explicit field list  
And one sanitized audit event and completed idempotency receipt commit in the same transaction  
And the browser receives only the safe field receipt with `options: {}`.

### F2-02: Relation initialization replay, conflict and rollback are distinguishable

Given an F2 relation initialization request has a scoped idempotency key  
When the same normalized request is repeated after completion  
Then the original receipt is returned with `200` and no second field/view/audit exists.  
When the key is reused with a changed name, target or required flag  
Then it returns `409` and nothing new is written.  
When a view update, audit write or database operation fails  
Then field, changed view configuration, completed idempotency record and initialization audit all roll back.

### F2-03: Relation schema authority and scope fail closed

Given a request names a missing, hidden, cross-workspace or different-Base target  
When the relation initializer resolves the target  
Then it performs no durable write and returns only the existing generic error boundary.  
Given the caller lacks `field.manage` or the required existing table read authority  
When the browser route is called directly  
Then the server denies it before starting idempotency work and response/error/cache never expose target name, target policy or raw configuration.

### F2-04: Candidate Picker returns safe, pageable labels only

Given a readable relation field has a fixed target table  
When an authorised reader searches with bounded `q` and follows an opaque cursor  
Then the backend filters target records and derives labels from a readable target primary field, otherwise first readable independent text-like field in durable order  
And each candidate is exactly `{ id, label }`  
And records with no safe label, hidden target record, hidden label field or invalid target scope are absent.  
When the cursor is exhausted, response is `records: []`, `next_cursor: null`, `has_more: false`; no client-side table/view query is attempted.

### F2-05: Record create and direct edit enforce relation write semantics

Given a writable relation field is returned by the safe create-form or record detail model  
When a user submits ordered target IDs through existing create or versioned PATCH  
Then the server rechecks source write authority, relation field write authority, target existence, same-Base/fixed-target-table membership, target readability and duplicate IDs.  
Given a source record is being edited  
When its own ID appears in a same-table relation value  
Then validation rejects `relation_self_reference` without mutation.  
Given a required relation is being created or explicitly PATCHed as `null`/empty list  
Then validation rejects it; an old record may omit that field in a partial PATCH so F2 never backfills historical data.

### F2-06: Relation reads do not leak raw target data

Given a reader can see a relation field and each linked target has a safe label  
When Grid, Kanban, Calendar, Form or Detail is read  
Then relation value is the server-composed ordered list `[{ id, label }]`.  
When any listed target cannot be safely labeled  
Then that target is absent; no ID placeholder, raw record, raw field value or client fallback is emitted.  
The opaque ID exists only to preload the permitted editor; it is not a target-table discovery API.

### F2-07: Builder creates a lookup only over an eligible relation and target

Given a builder has the existing source `field.manage`, source relation read, target table read and target field read authority  
When they submit relation field ID, target field ID and one fixed aggregation  
Then the server verifies that the relation is on the source table, points to a same-Base target table and the target field belongs to that table  
And persists only stable `source_field_id`, `target_field_id` and aggregation internally  
And returns the same redacted initialization receipt shape as a relation field.

### F2-08: Lookup graph is bounded and cyclic definitions are rejected

Given a proposed lookup targets another lookup  
When the resulting dependency path contains current lookup plus at most one nested lookup  
Then creation may proceed if every resolved hop is valid.  
When the path would contain three lookup nodes  
Then it returns `lookup_depth_exceeded` before field/audit/view/idempotency completion.  
When stored stable-ID or legacy key configuration forms a cycle  
Then it returns `lookup_dependency_cycle`; it does not try to evaluate, repair or partially persist the graph.

### F2-09: Fixed aggregation semantics are stable

Given readable linked target records and an eligible target field  
When aggregation is `values`  
Then server returns a stable ordered, one-dimensional safe primitive list.  
When it is `count`  
Then it returns the number of readable linked records.  
When it is `count_distinct`  
Then it returns the number of normalized distinct safe values.  
When it is `sum`, `average`, `min` or `max`  
Then target output must resolve to `number`; result is a number or permitted numeric-empty `null`.  
No aggregation accepts arbitrary expression text; `linked_record`, `json` and formula fields are ineligible target values.

### F2-10: Lookup permission/configuration degradation is whole-field fail-closed

Given a lookup is otherwise visible  
When a relation target, target record, target field, nested lookup, graph hop or configuration is unreadable/invalid/missing  
Then the current lookup key is omitted entirely from safe view/detail output.  
It must not return a partial aggregate, masked item, inferred zero, error string or raw dependency information.  
Only the permitted numeric-empty case in F2-09 returns `null`.

### F2-11: Delete protection is a conflict guard, not automatic mutation

Given a target record has incoming durable `RecordLink` references  
When a future authorised deletion path calls the reusable guard  
Then it receives `record_is_referenced` and leaves relation values/links intact.  
Given a relation or lookup field is referenced by F2 configuration  
When a future deletion path calls the field guard  
Then it receives `field_has_dependencies`.  
F2 adds no public DELETE endpoint, delete UI, auto-unlink, cascade or version bypass.

### F2-12: Responsive UI and protected-query state cannot restore stale scope

Given desktop widths 1440/1280 or Telegram widths 430/390  
When a builder opens relation/lookup builder, candidate picker or relation editor  
Then desktop uses the documented drawer and mobile uses labelled full-screen sheet/picker with keyboard-accessible controls.  
When workspace/session changes, request cancels, 401/403/404 arrives, or a late response resolves  
Then candidate/cache/receipt state is scoped by verified user and workspace, removed or ignored under TD001 rules, and never restores an old relation label, field or record selection.

## 4. Explicit State and Error Matrix

| Surface | Allowed states | Required result |
| --- | --- | --- |
| relation/lookup builder | idle, locally-invalid, pending, success-awaiting-reread, replayed, conflict-locked, generic-validation, denied, missing, network-retryable, cancelled, scope-invalidated | only exact safe receipt+reread enters success; all other states preserve/clear only permitted local input |
| candidate picker | idle, loading-first-page, loading-next-page, available, empty, exhausted, denied, session-expired, cancelled, stale-response-discarded | no arbitrary table/view fallback; labels/IDs never persist outside protected query memory |
| relation write | omitted-legacy-patch, valid-nonempty, invalid-type, duplicate-ID, wrong-target, unreadable-target, self-reference, required-empty, version-conflict, accepted | accepted write still follows normal record/audit/version path |
| lookup evaluation | visible-value, numeric-empty-null, absent-unreadable-hop, absent-invalid-config, absent-cycle/depth, field-hidden | only visible-value or numeric-empty is serialized; every fail-closed case omits key |
| initializer transaction | new, replay, conflict, in-progress, rolled-back, committed | exactly one terminal durable mutation for a successful key/payload pair |

The fixed browser error-code allowlist is only: `relation_self_reference`, `lookup_source_not_relation`, `lookup_target_incompatible`, `lookup_dependency_cycle`, `lookup_depth_exceeded`, `record_is_referenced`, `field_has_dependencies`, plus already-approved `duplicate_field_name`. The browser maps these to fixed local text and never shows `detail.message`. 401/403/404 and unknown/malformed error bodies use existing safe boundaries.

## 5. Acceptance Evidence Matrix

| ID | Requirement | Minimum evidence | Current status |
| --- | --- | --- | --- |
| F2-A01 | relation same-Base atomic initializer | unit/API replay/conflict/rollback + PostgreSQL | in progress |
| F2-A02 | safe receipt/schema/audit redaction | unit/API response scans | in progress |
| F2-A03 | candidate label/search/cursor/permission behavior | service/API tests | not implemented |
| F2-A04 | relation create/PATCH required/self/visibility rechecks | service/API tests | not implemented |
| F2-A05 | safe relation projection and whole-field lookup omission | unit/API tests | not implemented |
| F2-A06 | all seven aggregation and nested graph bounds | unit tests + PostgreSQL | in progress |
| F2-A07 | incoming-link/dependent-field guards | service and PostgreSQL tests | not implemented |
| F2-A08 | protected candidate cache/error handling | frontend tests | not implemented |
| F2-A09 | relation/lookup Builder and Picker | component/integration tests | not implemented |
| F2-A10 | four-width actual Mini App QA | local fixture + browser screenshots + console scan | not implemented |

## 6. Completion Report Requirements

The F2 delivery report must list changed files, each F2-A status, exact test/build/browser commands and outputs, skipped evidence with reason, PostgreSQL target safety, retained/sanitized artifacts, temporary cleanup, remaining risks and explicit non-scope. It must not call F2 or Stage07 production-ready.
