# Stage 07 API Data Security Contract

## Status

- Document status: contract design; existing versus proposed endpoints must be distinguished during implementation
- Scope: frontend API consumption, UI read models and security invariants

## 1. Contract Principles

- Server identity and active workspace membership are authoritative; the browser submits proof, never role claims.
- Every resource request is scoped by workspace/base/table/view/record ownership and field permissions.
- UI receives only safe, permission-filtered view models. Frontend cache keys include workspace and resource identity and are cleared on membership/session change.
- Mutations use server concurrency/version behavior and `Idempotency-Key` where Stage06 supports it. Confirmation is never optimistically committed.

## 2. Existing Stage06 Resource Consumption

| UI capability | Required server resource group | UI contract |
| --- | --- | --- |
| Workspace/Base/table/view navigation | workspace, base, table, view list/read endpoints | server-filtered names, IDs and capabilities |
| View canvas | view schema plus paginated records | typed field metadata, masked values, cursor state |
| Record detail | record read/update | visible fields, version and validation errors only |
| Template/import | template/install and import endpoints | limits, preview/commit status and safe errors |
| Draft review | record-change draft read/confirm/reject | field diff, terminal status and audit reference |
| Audit | paginated authorized audit readback | sanitized metadata only |

## 3. UI Read-Model Requirements

The implementation may add backend read models only after approval when existing primitive endpoints cannot safely or efficiently form a screen. A queue read model must include safe row label, destination, resource type, action availability, time/status and cursor; it must exclude raw record bodies and inaccessible references.

## 4. Approved Read-Only Mini App Contract

The following endpoints are approved for Package 1 and the beginning of Package 2. They do not change the Stage06 schema, roles or authorization rules. They are server-composed, read-only view models; their purpose is to prevent the browser from deriving a workspace list, navigation rights or a queue from unsafe primitive resources.

| Endpoint | Response boundary | Authorization rule |
| --- | --- | --- |
| `GET /mini-app/bootstrap` | verified identity source plus the caller's active workspace memberships and four navigation capabilities | includes only active memberships of the resolved server identity; capabilities are derived by the server from the member role, never accepted from the client |
| `GET /workspaces/{workspace_id}/home` | active Base metadata and pending `record_change_draft` queue summaries | requires `workspace.read`; Base list requires `base.read`; draft summaries require `record_change_draft.read` and contain no proposed/before field values, creator, trace or policy payload |
| `GET /workspaces/{workspace_id}/bases` | permitted Base summaries `{ id, name, source_type, status }` | requires active membership plus `base.read`; does not return Base description/settings |
| `GET /bases/{base_id}/tables` | permitted Table summaries `{ id, base_id, name, key, status }` | resolves Base ownership then requires `table.read` |
| `GET /bases/{base_id}/views` | saved-view summaries `{ id, base_id, table_id, name, view_type, status }` | resolves Base ownership then requires `table.read`; excludes view config and permission policy |
| `GET /tables/{table_id}/schema` | safe Canvas table + field schema; fields expose only `{ id, table_id, name, key, field_type, required, options.choices?, order_index }` | requires `table.read`; applies the same field-read filter and never returns a field policy, default, unique flag, raw option key or technical status |
| `GET /views/{view_id}/presentation` | normalized saved-view semantics `{ view_type, visible_field_keys, group_by_field_key?, date_field_key?, form_field_keys }` | requires `record.read` plus view-resource visibility; every returned field key must pass field read policy; raw config and policy are excluded |
| `GET /records/{record_id}` | detail `{ id, table_id, values, record_status, version }` | resolves record ownership then requires `record.read`; values contain only field-read-permitted keys |

`/mini-app/bootstrap` response identity is `{ user_id, source }`; it does not contain Telegram init data, headers, raw membership records or a client-supplied role claim. Workspace capability names are stable UI hints only: `can_read_bases`, `can_manage_workspace`, `can_manage_schema`, `can_review_drafts`. Every later resource request must still pass its normal server authorization check.

`/workspaces/{workspace_id}/home` queue rows are limited to `{ id, kind, title, status, destination, action_availability }`. `destination` contains only durable resource IDs. The initial Stage06-compatible queue only exposes pending draft-confirmation items; assigned records and `@` mentions wait for durable backend models rather than being inferred from arbitrary record fields.

The Base Canvas composes these summaries with authorized `GET /tables/{table_id}/schema` and `GET /views/{view_id}/records` calls. Table schema, view presentation, record list and record detail must all use the same field-read filter. A view's raw configuration and permission policy never travel to the browser; the browser cannot reconstruct an unapproved field scope from list metadata.

`group_by_field_key` and `date_field_key` are returned only when the configured field is visible to the caller. A non-visible or invalid configured key is omitted rather than replaced with a guessed client-side field. `form_field_keys` preserves the authorized view field order; it is not a raw form configuration or arbitrary layout payload.

## 5. Proposed Contract Extensions

| Extension | Why UI needs it | Approval required |
| --- | --- | --- |
| workspace employee scopes | team contacts can span explicit Bases/tables/views | schema, API and authorization |
| employee lifecycle/contact binding | draft/test/published contact and Telegram group `@` behavior | schema and API |
| knowledge sources | explicit Bases/views/documents and permission-filtered retrieval | schema, API, data retention |
| user memory partition | isolate personal conversation memory per caller | schema, security, retention |
| Mini App bootstrap/deep link | verify Telegram proof and resolve target safely | identity/API contract |

## 5.1 Approved Form/Create Contract

`GET /tables/{table_id}/create-form` is approved for the scalar Form/create slice. It requires existing `record.create` authorization and returns only `{ table_id, can_create, fields[] }`, where every field is server-filtered for the actor's writable scope and exposes only `key`, `name`, `field_type`, `required`, filtered `options` and `order_index`. `status`, `single_select` and approved F1 `multi_select` fields may expose a validated string-array `options.choices`; all other options are `{}`. `can_create` is `false` when a required field cannot be safely edited in this slice, so the browser cannot submit an inevitably incomplete record. It never returns raw `permission_policy`, hidden field metadata, view config, inaccessible linked values or a role claim.

The existing `POST /tables/{table_id}/records` remains the only create mutation. The browser submits only returned field keys; Stage06 remains authoritative for validation, normalization, audit and version-1 record creation. This approval does not cover complex field editors, builder, imports, drafts, Bot writes or Telegram actions.

## 5.2 Approved P3 Atomic Base/Table Builder Contract

This bounded P3 contract is implemented for the creation of an empty Base or one empty table only. It is not a Field Builder, additional View Builder, import/template contract, permission editor or general-purpose schema mutation surface.

| Endpoint | Browser request boundary | Server authority and atomic result |
| --- | --- | --- |
| `POST /workspaces/{workspace_id}/base-initializations` | body `{ base_name, table_name }`; required `Idempotency-Key` header | resolves active workspace membership, then independently checks `base.create`, `table.create` and `view.manage`; one transaction creates the Base, first table and its default Grid view, the required parent/resource audit events and the idempotency record |
| `POST /bases/{base_id}/table-initializations` | body `{ table_name }`; required `Idempotency-Key` header | resolves parent Base ownership before independently checking `table.create` and `view.manage`; one transaction creates the table, its default Grid view, required audit events and the idempotency record |

Both endpoints return only the safe receipt below. They never return a raw view configuration, permission policy, fields, audit bodies, idempotency storage details, role/capability claims or provider credentials.

```ts
type BuilderInitializationReceipt = {
  base: { id: string; name: string; source_type: string; status: string }
  table: { id: string; base_id: string; name: string; key: string; status: string }
  default_view: { id: string; base_id: string; table_id: string; name: string; view_type: 'grid'; status: string }
}
```

The server normalizes names, derives the table key and default Grid configuration itself, and keeps the new table fieldless. PostgreSQL migration `20260710_0021` adds the partial unique invariant `uq_views_one_default_per_table` so later code cannot create two default views for one table. The Mini App sends display names only and has no parameter for a key, default flag, configuration, policy, audit payload or permission claim.

The idempotency key is scoped to the endpoint/actor/resource context by the server. A first success returns `201`; the same key with the same normalized payload returns the original safe receipt; the same key with a different payload returns `409`. The client preserves the same key only for an explicit network/5xx retry. A `409` locks the current panel and requires the user to close it before a new attempt receives a new key. Validation errors remain in the panel; `401` clears all protected state, while `403` clears the affected workspace scope and shows a generic denied boundary without a resource preview.

A receipt is a navigation pointer, never optimistic client state. After a success the client invalidates Home and the affected Base table/view lists, rereads those authorized lists, verifies the exact receipt IDs and their Base/table relationship, and only then opens the new Grid. It must not choose the first item in a list, cache a synthetic resource or offer fake field/record creation in a zero-field table.

## 5.3 Approved F1 Atomic Field Builder Contract

F1 creates one independent field at a time. It is not a raw Stage06 primitive-field client, a field-permission editor, relationship/lookup builder, JSON editor, field edit/reorder/delete surface or additional-view Builder.

| Endpoint | Browser request boundary | Server authority and atomic result |
| --- | --- | --- |
| `POST /tables/{table_id}/field-initializations` | `{ name, field_type, required, choices? }` plus required `Idempotency-Key`; request extra fields are forbidden | resolves table ownership, requires active membership + `field.manage`, validates the F1 type/choice allowlist, locks the table row, generates a key and order, creates the field under default policy, appends it once to explicit active same-table view field lists, writes sanitized audit and stores a completed safe receipt in one transaction |

The field type allowlist is exactly `text`, `number`, `date`, `status`, `single_select`, `multi_select`, `user`, `checkbox`, `url`, `email` and `phone`. `status`, `single_select` and `multi_select` require `1..100` ordered nonblank unique choices no longer than 64 characters. Other F1 types reject choices. `linked_record`, `lookup` and `json` are not accepted by this endpoint.

```ts
type FieldInitializationReceipt = {
  field: {
    id: string; table_id: string; name: string; key: string
    field_type: string; required: boolean
    options: { choices?: string[] }; order_index: number
  }
  affected_view_ids: string[]
}
```

The receipt excludes policy, raw options/configuration, default values, roles, idempotency storage, audit body and record data. New field keys and `order_index` are server owned. Existing records receive no synthetic value. A table's primary field is not selected or changed by F1.

First success returns `201`, matching completed key/payload returns `200` with the same receipt, and a changed payload under the same key returns `409`. Validation failure is `422`; membership/action denial is generic `403`; `401` clears protected state; `404` does not reveal parent resources. A database or view-update failure rolls back the field, view changes, audit and incomplete idempotency state together. The browser retains a key only for explicit network/`5xx` retry, locks a `409` panel until close, and rereads authorized schema/presentation/records/create-form before it renders the field.

For the approved duplicate-name feedback refinement, the transport may inspect only `422.detail.code === "duplicate_field_name"` and map it locally to the fixed message `字段名称已存在，请使用其他名称。`. It must not display `detail.message`, retain the response body, infer any other validation code, or treat an unknown/malformed error body as specific feedback; every other failure remains the existing generic safe error. This is an error-presentation allowlist, not a new browser write parameter, schema field, permission signal or resource-disclosure channel.

## 5.4 Approved F2 Relation / Lookup Boundary

F2 uses two dedicated field-initialization routes, one relation-candidate read route, and the existing record-create/versioned-PATCH routes. Relation request shape is name, target_table_id and required; lookup request shape is name, source_relation_field_id, target_field_id and one fixed aggregation from values, count, count_distinct, sum, average, min or max. Both require Idempotency-Key and forbid extra keys. They return the existing safe field receipt only: generated field identity/metadata, empty safe options and affected view IDs.

Internal relation/lookup options, target table/field IDs, aggregation, policy, raw view configuration, audit bodies and idempotency records never reach the browser. Candidate response is only field_id, opaque id/label records, next_cursor and has_more. Relation display is server-projected opaque id/label cells. Lookup display is server-normalized values, number or permitted numeric-empty null; an unreadable or invalid hop omits the complete lookup value. Browser joins, arbitrary target-table reads, aggregate expressions and raw error messages are forbidden.

The full F2 endpoint/state/permission matrix is defined in STAGE_07_F2_RELATION_LOOKUP_SDD.md and STAGE_07_F2_RELATION_LOOKUP_BDD_AND_ACCEPTANCE.md. F2 adds no migration, physical database index, role/capability, persistent browser cache, DELETE endpoint/UI or cascade behavior.

## 5.5 V1 Saved View Builder Contract

V1's design and detailed implementation plan are user-approved. V1-6 now exposes the five approved FastAPI endpoints with strict Pydantic commands and independently composed safe responses; this is local backend API evidence only, not a Mini App/browser acceptance. The legacy `POST /bases/{base_id}/views` response contains raw `config` and `permission_policy`; it is not a Mini App contract and remains untouched.

V1 implements these typed server commands:

| Endpoint | Required authority | Browser input | Safe response |
| --- | --- | --- | --- |
| `GET /tables/{table_id}/view-builder-context` | active member + table read + existing `view.manage` | none | safe field eligibility, accessible summaries and owner-only safe member candidates |
| `POST /tables/{table_id}/view-initializations` | active member + `view.manage` | name, view type, typed presentation, `Idempotency-Key` | safe private-view receipt and affected ids |
| `GET /views/{view_id}/builder` | owner/editor; system default requires `view.manage` | none | typed editable presentation, version, safe scope/access and owner-only grants |
| `PATCH /views/{view_id}/presentation` | owner/editor; system default requires `view.manage` | expected version, optional name, typed presentation | safe summary/version |
| `PUT /views/{view_id}/members` | owner only | expected version, full editor/viewer member list | safe summary, safe grants and version |

`Idempotency-Key` is accepted only by initialization. `expected_version` is accepted only as a strict JSON property of PATCH/PUT. V1 route errors emit fixed `view_*` codes rather than exception text; current proof covers `403/view_access_denied`, `409/view_version_conflict` and strict `422` rejection of unknown `scope`. The browser must never send raw `config`, `permission_policy`, `is_default`, owner identity, raw member role/status, raw field option, hidden field key or audit body. A safe summary may read only the documented default marker; no V1 route accepts it as mutation input. The server owns `scope` (`system_default`, `private`, `restricted`), owner derivation, version increment, canonical configuration and default-view invariant. A view ACL intersects with existing workspace/Base/Table/Record/Field authority; it cannot grant a resource permission.

V1-8 uses a dedicated browser type module and reconstructs every V1 context/receipt from allowlisted fields before it reaches protected query state. All V1 transport keys start with the verified user/workspace scope; paths use `encodeURIComponent`; unknown server error/message content maps to one fixed local message. No V1 cache is persisted and no V1 mutation uses an optimistic browser update.

Safe V1 presentation is limited to view/table/type, ordered safe visible/form keys, up to twelve flat `AND` filter conditions with fixed typed operators, up to three sorts, at most one group key and one Calendar date key. It excludes query text, `OR`, nested condition groups, formulas, client query semantics and arbitrary layout data. Relation filter values reuse F2 candidate projection; numeric lookup has bounded numeric filter/sort; relation/lookup never group.

V1 requires an approved migration for durable owner/scope/version and a `view_member_grants` table. The existing one-default-per-table Grid invariant remains; V1 creates private views by default, may restrict them through explicit member grants, and does not provide a general Base-wide sharing or default reassignment path.

## 6. Client Security Rules

- Do not derive permissions from navigation visibility or cached role strings.
- Do not store raw Bot context, hidden fields, audit values or knowledge content in local storage, analytics or error reports.
- On `401`, expired bootstrap or membership revocation, remove protected query cache before re-authentication.
- On `403`, show a generic denied state; do not infer resource existence from client retries.
- For P3 Builder initialization, preserve one idempotency key only across explicit network/5xx retry; lock a `409` conflict until the panel is closed, and never retry a denied request.
- For F1 field initialization, use the same retry/`409`/denial discipline and never render a field from a receipt until its exact ID exists in the reread safe schema.
- While an F1 request is pending, the modal remains modal and its close/cancel controls are disabled, so a user cannot force a background workspace/view switch through an open write dialog. Browser QA observes those disabled controls; the existing application test remains the authoritative simulation proving a delayed receipt cannot restore an old workspace after a scope switch.
- Confirmation controls require server-provided draft/action state and the current user confirmation action. A stale action result is discarded and reloaded.

## 7. Acceptance Contract

Before any proposed extension ships, tests must prove cross-workspace denial, cross-user memory denial, hidden-field denial, group/chat scope denial, draft idempotency and sanitized audit/telemetry behavior.

For the approved read-only Mini App contract, tests must additionally prove that inactive memberships and other users' workspaces are absent from bootstrap; non-members cannot load a workspace Home; and Home queue responses do not contain draft field values or trace metadata.
