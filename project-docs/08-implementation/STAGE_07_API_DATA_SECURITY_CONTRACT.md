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

## 6. Client Security Rules

- Do not derive permissions from navigation visibility or cached role strings.
- Do not store raw Bot context, hidden fields, audit values or knowledge content in local storage, analytics or error reports.
- On `401`, expired bootstrap or membership revocation, remove protected query cache before re-authentication.
- On `403`, show a generic denied state; do not infer resource existence from client retries.
- Confirmation controls require server-provided draft/action state and the current user confirmation action. A stale action result is discarded and reloaded.

## 7. Acceptance Contract

Before any proposed extension ships, tests must prove cross-workspace denial, cross-user memory denial, hidden-field denial, group/chat scope denial, draft idempotency and sanitized audit/telemetry behavior.

For the approved read-only Mini App contract, tests must additionally prove that inactive memberships and other users' workspaces are absent from bootstrap; non-members cannot load a workspace Home; and Home queue responses do not contain draft field values or trace metadata.
