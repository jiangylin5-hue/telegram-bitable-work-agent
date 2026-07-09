# Permission And Security Model

## Status

- Document status: active security model
- Scope: Stage06 generic workspace/base/table/view/field/action/digital employee permissions, Telegram context and audit
- Current Progress: 2026-07-10 Updated for the approved Stage06 security-hardening direction. Request identity is separated from workspace role, every workspace-owned action resolves an active member, Telegram bindings reference members, tenant/resource ownership is validated before access, audit values are redacted and notification policy is server-controlled and fail-closed.

## 1. Permission Principles

- Telegram identity is context, not system permission.
- Digital employees are permissioned actors, not privileged bypasses.
- Permissions are layered: workspace, base, table, view, field, record, action, digital employee and Telegram chat scope.
- Field masking is a first-class security feature.
- Agent context must be built after permission filtering.
- Write-like digital employee actions default to draft-confirmation.
- Every denial, confirmation, write, notification and high-risk tool call must be audited.

## 2. Generic Roles

| Role | Default meaning |
| --- | --- |
| owner | Owns workspace, can manage billing/safety/ownership-level settings when implemented |
| admin | Manages workspace members, bases, permissions, templates and audit |
| builder | Creates bases, tables, fields, views, imports and templates |
| operator | Reads and updates permitted records and confirms permitted drafts |
| viewer | Reads permitted bases/views/fields |
| digital_employee | Acts only through configured scopes and runtime permission intersection |

Templates may define suggested roles such as sales, finance or support, but those are template roles mapped to generic permissions, not platform hardcoding.

## 3. Permission Layers

### 3.1 Workspace Permission

Controls:

- workspace visibility;
- member management;
- base creation;
- template installation;
- global safety switches;
- audit visibility.

### 3.2 Base Permission

Controls:

- base visibility;
- table creation;
- template save/install actions;
- base-level digital employee creation;
- base-level export when implemented.

### 3.3 Table Permission

Controls:

- table visibility;
- record create/update/archive;
- field management;
- view management.

### 3.4 View Permission

Controls:

- whether a user or digital employee can see a view;
- filters that must be applied;
- view-specific actions such as status advance.

### 3.5 Field Permission

Field modes:

- hidden;
- read;
- read_masked;
- aggregate_only;
- write;
- admin_only.

Field permission applies to:

- API responses;
- Mini App UI;
- desktop UI;
- digital employee context;
- import preview;
- notification rendering.

### 3.6 Record Permission

Stage06 should support at least:

- all records in permitted table/view;
- records created by the user;
- records assigned to the user;
- records matching view filter;
- records allowed by template-defined scope policy.

### 3.7 Action Permission

Core actions:

- `workspace.manage`
- `base.create`
- `base.read`
- `table.create`
- `field.manage`
- `record.create`
- `record.update`
- `record.archive`
- `view.manage`
- `import.create`
- `import.commit`
- `template.install`
- `template.save`
- `digital_employee.create`
- `digital_employee.invoke`
- `record_change_draft.confirm`
- `notification_request.confirm`
- `audit.read`

### 3.8 Digital Employee Permission

Digital employee scope includes:

- configured maximum scope;
- callable actions;
- readable tables/views;
- readable fields;
- writable draft types;
- confirmation policy;
- Telegram alias/chat binding.

Runtime scope:

```text
agent_configured_scope
∩ caller_user_scope
∩ telegram_chat_scope
```

## 4. Sensitive Data Policy

Generic sensitive data categories:

- credentials and tokens;
- payment data;
- private contact data;
- raw Telegram text when marked sensitive;
- private notes;
- provider/external error payloads;
- files and attachments when attachment support is enabled.

Stage06 rules:

- do not store raw secrets in records;
- do not expose masked fields to digital employees as raw context;
- do not include hidden fields in LLM prompts;
- write permission-denied audit events without leaking the denied field value.

## 5. Confirmation Policy

Default confirmation requirements:

| Action | Default |
| --- | --- |
| record query | no confirmation |
| summarize | no confirmation |
| create record draft by digital employee | confirmation required before commit |
| update record draft by digital employee | confirmation required before commit |
| status advance by digital employee | confirmation required unless explicitly configured direct-safe |
| notification request | confirmation required unless dry-run/internal |
| permission change | human admin only |
| external provider write | out of Stage06 default scope |

Digital employees never confirm their own write-like actions.

## 6. Telegram Security

Telegram binding resolves:

- workspace context;
- optional default base;
- optional default digital employee;
- chat-level allowed bases/views/actions.

Telegram binding does not grant:

- workspace membership by itself;
- field access by itself;
- write permission by itself;
- send permission by itself.

If Telegram user identity is unknown, the system should either:

- route to a safe onboarding/binding flow; or
- return a permission-safe message and write audit.

## 7. Audit Policy

Must audit:

- workspace/base/table/view permission denial;
- field masking denial;
- digital employee invocation;
- schema inspection by digital employee;
- record query by digital employee at summary level;
- draft creation/update;
- human confirmation/rejection;
- record write;
- import commit;
- template install/save;
- Telegram binding changes;
- notification request creation/send/block;
- safety switch changes;
- LLM output rejected by schema or policy.

## 8. Acceptance Criteria

- Every API response is permission-filtered.
- Digital employee context never contains fields the caller cannot read.
- Telegram scope is intersected with user and agent scope.
- Write-like digital employee actions become drafts before commit.
- Permission denials write audit events.
- Hidden/masked fields are not leaked through summaries or notifications.
- Template roles map to generic permissions rather than hardcoded vertical roles.

## 9. Stage06 Identity Adapter

Stage06 uses a replaceable identity adapter rather than a fixed system actor.

- `local` and `test` may accept the explicit `X-Stage06-User-Id` development identity header.
- `staging` and `production` reject that development adapter and return `401` unless a verified adapter is configured.
- Identity supplies a user id, not a role.
- The effective role comes from an active `workspace_members` row for the resolved workspace.
- Telegram bindings reference a concrete workspace member; Telegram identity never grants a role directly.
- Workspace creation is the only bootstrap path and may create a workspace only for the authenticated user.

An unavailable verifier, missing membership, inactive membership, cross-workspace resource or inconsistent base/table/view/record chain fails closed.
