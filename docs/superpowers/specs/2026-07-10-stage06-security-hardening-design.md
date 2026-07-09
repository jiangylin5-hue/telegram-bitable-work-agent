# Stage06 Security Hardening Design

## Status

- Document status: approved design, awaiting written-spec review
- Scope: Stage06 identity, authorization, tenant isolation, audit redaction, notification safety, import limits, pagination, idempotency, database constraints and security evidence
- Approved direction: Option A, backend identity abstraction with Telegram-to-workspace-member resolution and production fail-closed behavior

## 1. Goal

Close the gap between the implemented Stage06 backend prototype and the existing Stage06 permission/security contract without selecting an external authentication vendor or starting the deferred Mini App UI.

The hardening package must make this authority chain executable:

```text
verified request or Telegram identity
-> active workspace member
-> workspace/base/table/view/record action permission
-> field read/write/mask permission
-> digital employee configured scope
-> Telegram chat scope when applicable
-> backend service action
-> redacted audit evidence
```

## 2. Considered Approaches

### Option A: Backend Identity Adapter And Fail-Closed Authorization

Selected.

- Add a replaceable Stage06 request-identity dependency.
- Permit an explicit development identity header only in `local` and `test` environments.
- Require a configured verified identity adapter in `staging` and `production`; otherwise return `401`.
- Resolve the effective role from an active `WorkspaceMember` for every workspace-owned resource.
- Bind Telegram users to a concrete workspace member and derive the caller from that binding.
- Keep future Telegram Mini App `initData` or OIDC verification behind the same adapter.

This option fixes the Stage06 contract now without introducing a new authentication provider.

### Option B: Telegram Mini App Identity Now

Rejected for this package because the Mini App is explicitly deferred and desktop-browser authentication would remain unresolved.

### Option C: External OIDC/JWT Provider Now

Rejected because it changes the confirmed technical baseline, adds an external dependency and requires a separate product/vendor decision.

## 3. Identity And Authorization Architecture

### 3.1 Request Identity

Introduce `Stage06RequestIdentity` with stable fields:

```text
user_id
source = development_header | verified_adapter | telegram_binding
telegram_user_id (optional)
```

The identity object never contains a caller-supplied role. Roles are loaded from `workspace_members`.

Environment behavior:

| Environment | Identity behavior |
| --- | --- |
| `local`, `test` | Accept `X-Stage06-User-Id` through the development adapter; tests may override the dependency |
| `staging`, `production` | Reject the development header; require a configured verified adapter; fail with `401` when absent |

Workspace creation is a bootstrap exception: an authenticated identity may create a workspace only for its own `user_id` and becomes its owner.

### 3.2 Workspace Membership

Every workspace-owned action resolves an active `WorkspaceMember`. Inactive, missing or cross-workspace members are denied.

Stage06 role defaults:

| Role | Default action boundary |
| --- | --- |
| `owner` | All Stage06 workspace actions |
| `admin` | Member-independent platform administration, templates, audit and digital employee configuration |
| `builder` | Base/table/field/view/import/template/digital employee construction |
| `operator` | Permitted record reads/writes, draft confirmation and controlled notification actions |
| `viewer` | Permission-filtered reads only |

Field, view, record and Telegram policies can only narrow these defaults.

### 3.3 Central Authorization Service

Create a Stage06 authorization module responsible for:

- mapping any base/table/view/record/draft/import/employee/notification resource to a workspace;
- resolving the active member and effective `Actor`;
- checking the action matrix;
- enforcing resource ownership consistency;
- recording a sanitized denial audit event.

Routes depend on identity, while services receive the resolved `Actor` plus the authorized resource context. The fixed `get_system_actor` dependency is not used by Stage06 routes after this package.

## 4. Tenant And Resource Boundaries

Required invariants:

- a table belongs to the base named in the route;
- a view's table belongs to the same base as the view;
- an import job's optional base belongs to the import workspace;
- a template installation writes only inside its target workspace;
- a digital employee's tables and views belong to its configured base;
- digital employee configured scope cannot exceed the creator's scope;
- an empty digital employee table/view scope grants no resource access;
- a record-change draft and its record/table/base/workspace chain must agree;
- linked-record and lookup targets remain inside the permitted base for Stage06;
- lookup reads re-check target table, target field and masking permissions.

Cross-boundary requests return `403` or `422` according to whether the resource is unauthorized or internally inconsistent. Responses must not reveal the existence of inaccessible resources beyond the stable error code.

## 5. Audit And Notification Safety

### 5.1 Audit Redaction

Audit events may store identifiers, changed field keys, versions, counts and safe status metadata. They must not store or return raw record values, hidden field values, import rows, notification message bodies, Telegram raw text or LLM raw prompt/response.

Audit readback is restricted to `owner` and `admin`, is paginated and passes through a shared sanitizer before serialization.

### 5.2 Notification Fail-Closed Policy

The effective notification policy is the intersection of server policy and request policy. Request payloads may narrow policy but cannot enable sending.

Server defaults:

```text
STAGE06_NOTIFICATION_MODE=disabled
STAGE06_NOTIFICATION_ALLOWED_CHAT_IDS=
```

State rules:

- `disabled` or `dry_run` produces `blocked`/`dry_run` evidence and never `queued`;
- `restricted_test` requires a server allowlist and an allowlisted target;
- confirmation does not bypass server mode or allowlist;
- `PROVIDER_MODE=disabled` remains mandatory for this Stage06 package;
- no real sender or broad send path is added.

## 6. Import, Pagination And Idempotency

### 6.1 Import Limits

Default hard limits:

- CSV payload: 5 MiB decoded;
- Excel payload: 10 MiB decoded;
- rows: 10,000;
- columns: 200;
- cell text: 64 KiB;
- preview rows: 20;
- ZIP entries are read only from required XLSX paths and total uncompressed required content is bounded.

Limit failures create no committed platform resources and return stable `import_*_limit_exceeded` codes without echoing file content.

### 6.2 Pagination

List endpoints for view records, drafts, notifications and audit accept `limit` and `cursor`:

- default limit: 50;
- maximum limit: 200;
- stable ordering: `(created_at, id)` or resource-specific equivalent;
- responses add optional `next_cursor` and `has_more` fields while preserving existing item arrays.

### 6.3 Idempotency And Concurrency

Mutating multi-resource operations accept `Idempotency-Key`:

- import creation and commit;
- template installation;
- notification request creation;
- draft confirmation.

A Stage06 idempotency table stores workspace, operation, key, request fingerprint, status and safe response reference. Reusing a key with a different fingerprint returns `409`.

PostgreSQL confirmation/commit paths lock the draft/import/notification/idempotency row before state transition. Unique constraints provide a second protection against races.

## 7. Database Hardening

Add one non-destructive Stage06 migration after `20260709_0019` for:

- `workspace_member_id` foreign key on Stage06 Telegram bindings;
- digital employee alias uniqueness within a base when alias is present;
- Telegram binding uniqueness for active workspace/chat/user tuples;
- indexes for Stage06 foreign keys and common list/read paths;
- unique trace identifiers where required;
- status and positive-version check constraints;
- Stage06 idempotency records;
- deferred foreign key from Telegram binding default employee to `digital_employees`.

No Stage02-05 tables are removed or rewritten.

## 8. Testing And Evidence

TDD coverage must include:

- API requests without identity return `401`;
- a member cannot access another workspace/base/table/view/record;
- a viewer cannot mutate records or create privileged resources;
- Telegram mention uses the bound workspace member role;
- cross-base view/import/employee scope is rejected;
- lookup cannot expose a hidden target field;
- audit readback does not contain hidden/raw values;
- request notification policy cannot override server fail-closed policy;
- import size/row/column/cell limits;
- pagination cursor stability;
- idempotent replay and conflicting-key behavior;
- concurrent PostgreSQL import/draft confirmation has one committed outcome.

Real PostgreSQL evidence is written as sanitized machine-readable JSON under `project-docs/08-implementation/evidence/`. Secrets, raw record values, raw Telegram text and raw LLM prompts/responses are prohibited in artifacts.

## 9. Delivery Packages

1. Identity, authorization, tenant isolation, lookup safety, audit redaction and notification fail-closed.
2. Import limits, pagination, idempotency, database constraints and PostgreSQL concurrency tests.
3. Sanitized evidence, Stage06 exit/progress reconciliation and reviewable branch commits.

Each package follows red-green-refactor and must keep the full backend regression green before the next package.

## 10. Explicit Non-Goals

- choosing or integrating Clerk, Auth0 or another OIDC vendor;
- implementing Telegram Mini App UI;
- enabling real notification/provider sends;
- implementing full formula, attachment, workflow or dashboard systems;
- rewriting Stage02-05 authorization paths outside the dependencies required by Stage06.

## 11. Exit Criteria

Stage06 backend readiness may be restored only when:

- all Stage06 routes use resolved identity and workspace membership;
- tenant/resource invariants have negative tests;
- permission-denial audit is safe and audit readback is authorized/redacted;
- notification defaults are fail-closed;
- import/pagination/idempotency limits pass unit and PostgreSQL tests;
- sanitized evidence is retained;
- Stage06 source, SDD, contract, BDD, progress, risk and exit documents agree.
