# Stage07 Governance Write SDD

## Status

- Status: proposed technical specification; implementation is gated on user approval of TD004.
- Scope: server-owned member-role and field-policy commands plus UI reuse of existing V1 view grants.

## Backend Design

### Authorization actions

Add fixed actions only:

- `member.manage`: owner and admin receive it; service applies the stricter target-role matrix from TD004.
- `field.permission.manage`: owner and admin receive it; `field.manage` alone remains insufficient for policy replacement.

No caller submits an action name, role action map or resource policy expression.

### Unit of work and locking

Extend the current Stage06 platform unit of work with exact lookup-and-lock methods for `WorkspaceMember` and `PlatformField`. SQLAlchemy uses `SELECT ... FOR UPDATE`; memory UOW follows the same compare/update semantics for deterministic tests. The route performs authorization before the mutation service; the service repeats resource and invariant validation under lock.

### Revisions and migrations

The Alembic migration adds `workspace_members.version` and `fields.permission_version`, both non-null default `1`. It upgrades existing rows deterministically and downgrades by dropping only those columns. The migration adds no index because existing UUID lookup/row lock paths already identify the targets.

### Normalization

`normalize_field_permission_policy` accepts a mapping with exactly the fixed role keys and values. It returns a canonical ordered JSON object. It rejects unknown/missing keys, non-strings, aliases, booleans and owner values other than `write`. The record read/write helpers remain the sole enforcement functions; their existing fixed-action intersection is regression-tested.

### Idempotency and audit

Use the current `begin_idempotent_operation`, request fingerprint and completion records. Trace IDs stay server-generated. Audit uses only stable event, workspace/table/field/member identifiers, before/after role or normalized mode map and revision numbers; audit sanitizer remains in the path.

## HTTP Contract

All S4 endpoints live under `/mini-app/.../governance/` and use Pydantic models with `extra="forbid"`. Limit remains `1..100`. `Idempotency-Key` is required for writes and never placed in logs/UI.

| Route | Success | Fixed failure classes |
| --- | --- | --- |
| `GET .../member-editor` | paged safe editable rows | 401, 403, 404, invalid cursor 422 |
| `PATCH .../members/{member_id}/role` | closed receipt, 200 for accepted command or identical replay | 401, 403, 404, stale 409, idempotency 409, invariant 422 |
| `GET .../field-permissions` | safe fixed policy summaries | 401, 403, 404 |
| `PUT .../fields/{field_id}/permission-policy` | closed receipt, 200 for accepted command or identical replay | 401, 403, 404, stale 409, idempotency 409, malformed/invariant 422 |

Error bodies expose only stable code plus existing fixed client mapping. They never return policy snapshots, member action maps, actor data or raw database messages.

## Frontend Design

Create closed TypeScript DTOs for the four routes. Parser acceptance is allowlisted: role, status, field type and policy mode must match the contract; an invalid response becomes a generic safe error. Protected keys nest by user/workspace and then table/member target. Mutations use no optimistic updates.

On success, invalidate/cancel the exact governance context plus workspace bootstrap, Base/table schema, current view presentation and record-detail keys that can contain field visibility. The client refetches safe server state before closing the panel. On 409 it leaves safe unsent selection in the local dialog and exposes fixed `数据已更新，请重新读取后再提交。`; it never resubmits automatically.

## Security and Non-Disclosure

- Route authorization, target scope and revision compare occur server-side and in transaction.
- Browser never receives an action map, arbitrary policy JSON, audit snapshots or hidden field value.
- A user whose role changes can lose access only after a subsequent server response; client invalidation is hygiene, not authorization.
- No mutation URL includes target user ID other than the path resource ID already authorized; no policy is encoded into query string.
- View grants stay at their existing resource-owner boundary and do not read workspace roles into the browser.

## Verification Design

Test red/green before each service/route. Run focused service/API suites, migration upgrade/downgrade smoke and local disposable PostgreSQL concurrency/replay/rollback tests. Run typed frontend parser/query/Application suites and production build. Browser evidence uses synthetic local data only at 1440/1280/430/390 and must observe one role success, policy success, stale conflict, denied response, focus return and final console scan. A later evidence document maps GW-A01 through GW-A08 one-by-one.
