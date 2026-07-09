# Stage 06 API Data Security Contract

## Status

- Document status: active Stage06 API/data/security contract
- Scope: API resources, data model, permission contract and audit behavior for Stage06
- Current Progress: 2026-07-10 The security-hardening contract is implemented and verified. Development identity is limited to local/test, production-like environments require a verified adapter, roles come from active workspace membership, tenant/resource chains are checked, notification policy is server-controlled, audit state is sanitized, imports/lists are bounded and protected mutations require `Idempotency-Key`.

## 1. API Principles

- REST first.
- All mutating APIs write audit events.
- All reads are permission-filtered.
- Digital employee tools call backend services, not raw SQL.
- JSON responses must avoid leaking hidden fields.
- Stage06 APIs are project-native; they do not imitate Feishu API URLs.
- Live LLM mode reuses the existing invoke routes and must record model provider/name/usage through AgentRun evidence.
- UI-facing API contracts may be stabilized, but frontend implementation is out of scope for the current backend-readiness pass.
- Stage06 roles are resolved from active workspace membership and are never accepted from request payloads or identity headers.
- In `staging` and `production`, an unavailable identity verifier is a `401` failure, not a system-admin fallback.
- `Idempotency-Key` is required for Stage06 multi-resource commit operations defined in this contract.

### 1.1 Identity Contract

The backend identity adapter returns a stable `user_id` and identity source. In `local` and `test`, `X-Stage06-User-Id` is the explicit development adapter. It is rejected in `staging` and `production`, where a verified adapter must be configured.

Telegram bindings must reference an active workspace member. Telegram chat/user identity provides context only; the bound member supplies caller permission.

Workspace creation may bootstrap only a workspace owned by the authenticated `user_id`.

## 2. Resource Groups

### 2.1 Workspace

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/workspaces` | Create workspace |
| `GET` | `/workspaces/{workspace_id}` | Read workspace |
| `GET` | `/workspaces/{workspace_id}/members` | List members |
| `POST` | `/workspaces/{workspace_id}/telegram-bindings` | Bind Telegram context |

### 2.2 Base/Table/Field/Record

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/workspaces/{workspace_id}/bases` | Create base |
| `GET` | `/bases/{base_id}` | Read base |
| `POST` | `/bases/{base_id}/tables` | Create table |
| `POST` | `/bases/{base_id}/views` | Create view |
| `GET` | `/tables/{table_id}/schema` | Schema introspection |
| `POST` | `/tables/{table_id}/fields` | Create field |
| `POST` | `/tables/{table_id}/records` | Create record |
| `PATCH` | `/records/{record_id}` | Update record |
| `GET` | `/views/{view_id}/records` | Read records through view |

### 2.3 Import/Template

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/workspaces/{workspace_id}/imports` | Create import job |
| `GET` | `/imports/{import_job_id}` | Read import preview/status |
| `POST` | `/imports/{import_job_id}/commit` | Commit import |
| `GET` | `/templates` | List templates |
| `POST` | `/workspaces/{workspace_id}/template-installations` | Install template |
| `POST` | `/bases/{base_id}/templates` | Save base as template |

### 2.4 Digital Employees

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/bases/{base_id}/digital-employees` | Create digital employee |
| `GET` | `/digital-employees/{employee_id}` | Read employee config |
| `PATCH` | `/digital-employees/{employee_id}` | Update employee config |
| `POST` | `/digital-employees/{employee_id}/invoke` | Invoke from UI |
| `POST` | `/telegram/mentions` | Resolve Telegram `@` invocation |

### 2.5 Drafts, Notifications, Audit

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/bases/{base_id}/record-change-drafts` | List drafts |
| `POST` | `/record-change-drafts/{draft_id}/confirm` | Confirm draft |
| `POST` | `/record-change-drafts/{draft_id}/reject` | Reject draft |
| `GET` | `/bases/{base_id}/notification-requests` | List controlled notifications |
| `POST` | `/notification-requests/{request_id}/confirm` | Confirm notification |
| `GET` | `/bases/{base_id}/audit-events` | Read audit |

List responses for view records, drafts, notifications and audit accept `limit` and `cursor`, use a default limit of 50 and reject limits above 200. Existing item arrays remain; `next_cursor` and `has_more` are additive response fields.

`Idempotency-Key` applies to import create/commit, template installation, notification request creation and draft confirmation. Reusing a key with different request content returns `409`.

## 3. Data Contract

Generic record:

```json
{
  "id": "rec_x",
  "table_id": "tbl_x",
  "values": {
    "customer_name": "Example Co",
    "status": "active",
    "next_follow_up": "2026-07-10"
  },
  "record_status": "active",
  "version": 3
}
```

Field schema:

```json
{
  "id": "fld_x",
  "table_id": "tbl_x",
  "key": "status",
  "name": "Status",
  "field_type": "status",
  "required": true,
  "options": {
    "choices": ["new", "active", "blocked", "archived"]
  },
  "permission_policy": {
    "default": "read",
    "operator": "write"
  }
}
```

Record-change draft:

```json
{
  "id": "draft_x",
  "table_id": "tbl_x",
  "record_id": "rec_x",
  "draft_type": "update_record",
  "proposed_values": {
    "status": "active"
  },
  "status": "pending_confirmation",
  "created_by_type": "digital_employee",
  "created_by_id": "emp_x",
  "trace_id": "trace_x"
}
```

Live digital employee invocation response:

```json
{
  "action": "summarize",
  "employee_id": "emp_x",
  "view_id": "view_x",
  "record_count": 3,
  "answer": "Three open Telegram tasks need review.",
  "citations": [
    {"record_id": "rec_x", "field_keys": ["message", "status"]}
  ],
  "runtime": {
    "mode": "live_openrouter",
    "graph_name": "stage06_live_digital_employee",
    "model_provider": "openrouter",
    "model_name": "openrouter/auto"
  }
}
```

## 4. Permission Contract

All reads must apply:

```text
workspace permission
-> base permission
-> table permission
-> view permission
-> record scope
-> field read/mask policy
```

All writes must apply:

```text
workspace permission
-> base permission
-> table permission
-> field write policy
-> action permission
-> optimistic concurrency check
-> audit event
```

Digital employee scope:

```text
agent_configured_scope
∩ caller_user_scope
∩ telegram_chat_scope
```

An empty configured table/view scope grants no access. All referenced resources must belong to the employee base and the creator's permitted scope.

Lookup values must re-check the target table and target field permission. A readable lookup field cannot reveal a hidden target field.

## 5. Migration Contract

Stage06 migrations should add generic platform tables without destructive changes to Stage02-05 tables.

Required migration groups:

1. workspace and membership;
2. base/table/field/record/view/form;
3. template/import;
4. digital employee/draft/notification;
5. audit alignment through the existing `ops_audit_events` bridge unless a later package requires a dedicated Stage06 audit table.

Stage02-05 vertical tables may be left intact. Future migration into generic records should be a separate stage or explicit task.

## 6. Security Contract

- No raw secrets in repo or records.
- No raw SQL from digital employees.
- No hidden fields in LLM context.
- No broad Telegram sends by default.
- Notification send mode must support dry-run and allowlist.
- Provider/external writes disabled in Stage06 default.
- Every permission denial writes audit without leaking denied values.
- Every confirmation re-checks permission and record version.
- Real LLM calls are allowed only with permission-filtered context and must not persist raw prompt/response by default.
- Audit events and audit responses must not contain raw record values, import rows, notification bodies, Telegram raw text or LLM raw payloads.
- Notification effective policy is the intersection of server policy and request policy; request policy cannot enable a disabled or non-allowlisted send.
- Import payloads are limited to 5 MiB CSV, 10 MiB Excel, 10,000 rows, 200 columns and 64 KiB per text cell.
- Cross-workspace/base/table/view/record resource combinations are rejected before data access.
- Stage06 list endpoints use stable cursor pagination and a maximum page size of 200.

## 7. Acceptance Contract

An implementation passes this contract only if:

- API tests prove permission-filtered view reads;
- field masking applies to records and digital employee context;
- import preview does not commit before confirmation;
- digital employee write creates draft first;
- live digital employee mode calls LangGraph/OpenRouter when credentials are configured and records AgentRun evidence;
- draft confirmation writes record and audit;
- Telegram mention path respects chat scope;
- safety switch can block notifications;
- API tests prove unauthenticated requests fail and cross-tenant requests do not disclose or mutate data;
- audit readback is owner/admin only and redacted;
- notification requests remain blocked when request payload attempts to weaken server policy;
- import limit, pagination, idempotency and PostgreSQL concurrency tests pass.
