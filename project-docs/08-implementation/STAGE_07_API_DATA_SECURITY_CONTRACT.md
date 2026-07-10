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

## 4. Proposed Contract Extensions

| Extension | Why UI needs it | Approval required |
| --- | --- | --- |
| workspace employee scopes | team contacts can span explicit Bases/tables/views | schema, API and authorization |
| employee lifecycle/contact binding | draft/test/published contact and Telegram group `@` behavior | schema and API |
| knowledge sources | explicit Bases/views/documents and permission-filtered retrieval | schema, API, data retention |
| user memory partition | isolate personal conversation memory per caller | schema, security, retention |
| Mini App bootstrap/deep link | verify Telegram proof and resolve target safely | identity/API contract |

## 5. Client Security Rules

- Do not derive permissions from navigation visibility or cached role strings.
- Do not store raw Bot context, hidden fields, audit values or knowledge content in local storage, analytics or error reports.
- On `401`, expired bootstrap or membership revocation, remove protected query cache before re-authentication.
- On `403`, show a generic denied state; do not infer resource existence from client retries.
- Confirmation controls require server-provided draft/action state and the current user confirmation action. A stale action result is discarded and reloaded.

## 6. Acceptance Contract

Before any proposed extension ships, tests must prove cross-workspace denial, cross-user memory denial, hidden-field denial, group/chat scope denial, draft idempotency and sanitized audit/telemetry behavior.
