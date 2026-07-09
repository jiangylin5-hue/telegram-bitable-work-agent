# Bitable Schema Blueprint

## Status

- Document status: active platform blueprint
- Scope: Stage06 通用多维表格平台资源模型，包括 workspace、base、table、field、record、view、template、import、digital employee、draft、permission 和 audit
- Current Progress: 2026-07-09 Rewritten from fixed advertising-agency business tables into a generic Feishu-like multidimensional table platform blueprint. Advertising tables are now template-created ordinary tables, not core platform schema.

## 1. Purpose

This document is the active resource blueprint for the platform.

It defines the generic table system that Stage06 must build toward:

```text
workspace
-> base
-> table
-> field schema
-> record JSONB values
-> linked records / lookup
-> view / form-lite / dashboard-lite
-> template / import
-> permission
-> digital employee
-> record_change_draft
-> audit_event
```

All future vertical scenarios must be represented as templates or user-created bases on top of this resource model.

## 2. Non-Negotiable Rules

- Platform tables are generic; vertical business tables are template instances.
- PostgreSQL stores facts; JSONB stores generic record values; field metadata defines type and validation.
- A view is not only UI filtering. It is also a permission, task queue and Agent context surface.
- Digital employees must inspect schema and permission-filtered views before acting.
- Write-like Agent output defaults to `record_change_drafts`.
- Telegram answers are not durable completion evidence.
- Every material write, confirmation, denial, permission block, send request and Agent action must produce an audit event.

## 3. Core Resource Map

| Resource | Purpose | Stage06 priority |
| --- | --- | --- |
| `workspaces` | Organization/team boundary | Required |
| `workspace_members` | Users and roles in a workspace | Required |
| `telegram_bindings` | Telegram chat/user to workspace/base context | Required |
| `bases` | Business app/data app container | Required |
| `tables` | Generic table metadata | Required |
| `fields` | Field definitions and type metadata | Required |
| `records` | Generic record values in JSONB | Required |
| `record_links` | Linked record edges | Required |
| `views` | Grid, kanban, calendar, form-lite, dashboard-lite metadata | Required |
| `forms` | Form-lite input metadata | Required |
| `templates` | Reusable base/table/view/employee package | Required |
| `template_installations` | Template install records | Required |
| `import_jobs` | CSV/Excel import preview and commit | Required |
| `digital_employees` | Table-bound Agent configuration | Required |
| `record_change_drafts` | Pending write proposals | Required |
| `notification_requests` | Controlled Telegram/UI notifications | Required |
| `automation_events` | Queue/status/workflow events | Required |
| `audit_events` | Permission/action/tool/audit timeline | Required |
| `dashboard_blocks` | Dashboard-lite blocks | Reserved/minimal |
| `file_assets` | Attachment metadata | Reserved |

## 4. Table Blueprint

### 4.1 `workspaces`

Purpose: tenant-like team boundary.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | uuid | Workspace id |
| `name` | text | Display name |
| `slug` | text unique | Stable url/key |
| `owner_user_id` | uuid/text | Owner |
| `status` | status | active, disabled, archived |
| `settings` | jsonb | Workspace feature flags and safety switches |
| `created_at` / `updated_at` | datetime | Timestamps |

### 4.2 `workspace_members`

Purpose: membership and workspace-level roles.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `user_id` | uuid/text | User id |
| `role` | single_select | owner, admin, builder, operator, viewer |
| `status` | status | active, invited, disabled |
| `joined_at` | datetime nullable | Join time |

### 4.3 `telegram_bindings`

Purpose: bind Telegram chat/user context to workspace, base and default digital employee.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `telegram_chat_id` | text nullable | Chat id |
| `telegram_user_id` | text nullable | Telegram user id |
| `binding_type` | single_select | chat, user, chat_user |
| `default_base_id` | relation nullable | Default base for the chat/user |
| `default_digital_employee_id` | relation nullable | Default employee |
| `scope_policy` | jsonb | Chat/user allowed bases/views/actions |
| `status` | status | active, disabled, unknown |

Rule: Telegram identity is context, not final system permission.

### 4.4 `bases`

Purpose: application container inside a workspace.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `name` | text | Base name |
| `description` | text nullable | Description |
| `source_type` | single_select | blank, template, import, duplicated |
| `template_id` | relation nullable | Source template |
| `status` | status | active, archived |
| `settings` | jsonb | Base settings |

### 4.5 `tables`

Purpose: generic table metadata.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `base_id` | relation | Base |
| `name` | text | Table display name |
| `key` | text | Stable internal key |
| `description` | text nullable | Description |
| `primary_field_id` | relation nullable | Primary display field |
| `status` | status | active, archived |
| `settings` | jsonb | Table options |

### 4.6 `fields`

Purpose: typed field metadata.

Stage06 field types:

- `text`
- `number`
- `date`
- `status`
- `single_select`
- `multi_select`
- `user`
- `checkbox`
- `url`
- `email`
- `phone`
- `json`
- `linked_record`
- `lookup`

Reserved field types:

- `formula`
- `attachment`

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `table_id` | relation | Table |
| `name` | text | Display name |
| `key` | text | Stable key |
| `field_type` | single_select | Type |
| `required` | checkbox | Required flag |
| `unique` | checkbox | Unique constraint flag |
| `options` | jsonb | Select options, format, link config, lookup config |
| `default_value` | jsonb nullable | Default value |
| `permission_policy` | jsonb | Field-level read/write/mask |
| `order_index` | number | Display order |
| `status` | status | active, hidden, archived |

### 4.7 `records`

Purpose: generic row values.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `table_id` | relation | Table |
| `values` | jsonb | Field-keyed values |
| `record_status` | status | active, archived |
| `created_by_user_id` | uuid/text nullable | Creator |
| `updated_by_user_id` | uuid/text nullable | Last updater |
| `created_at` / `updated_at` | datetime | Timestamps |
| `version` | number | Optimistic concurrency |

Rules:

- All values must validate against `fields`.
- Backend services must never return fields the caller cannot read.
- Updates should support field-level patch semantics.

### 4.8 `record_links`

Purpose: normalized edge store for linked records.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `source_table_id` | relation | Source table |
| `source_record_id` | relation | Source record |
| `source_field_id` | relation | Link field |
| `target_table_id` | relation | Target table |
| `target_record_id` | relation | Target record |
| `created_at` | datetime | Timestamp |

### 4.9 `views`

Purpose: saved table surfaces and Agent context surfaces.

Stage06 view types:

- `grid`
- `kanban`
- `calendar`
- `form`
- `dashboard_lite`

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `base_id` | relation | Base |
| `table_id` | relation nullable | Main table |
| `name` | text | View name |
| `view_type` | single_select | grid, kanban, calendar, form, dashboard_lite |
| `config` | jsonb | columns, filters, groups, sorts, calendar date, kanban status |
| `permission_policy` | jsonb | View visibility and action rules |
| `is_default` | checkbox | Default view |
| `status` | status | active, archived |

### 4.10 `forms`

Purpose: form-lite data collection over a table.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `view_id` | relation | Form view |
| `table_id` | relation | Target table |
| `form_config` | jsonb | Field order, labels, helper text, required overrides |
| `submit_policy` | jsonb | Public/internal, confirmation, audit |
| `status` | status | active, disabled |

### 4.11 `templates`

Purpose: reusable starter packages.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | text | Template name |
| `category` | single_select | crm, project, ticket, inventory, sample, custom |
| `description` | text | Description |
| `version` | text | Template version |
| `manifest` | jsonb | Tables, fields, views, sample data, employees |
| `status` | status | draft, published, archived |

Required official templates:

- CRM / Customer Management.
- Project / Task.
- Customer Service / Ticket.
- Inventory / Asset.
- Advertising Agency Sample as a weak sample.

### 4.12 `template_installations`

Purpose: track template installs and generated resources.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `base_id` | relation | Created base |
| `template_id` | relation | Template |
| `template_version` | text | Version |
| `resource_map` | jsonb | Template ids to created ids |
| `installed_by_user_id` | uuid/text | Installer |
| `installed_at` | datetime | Timestamp |

### 4.13 `import_jobs`

Purpose: CSV/Excel import preview and commit.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `base_id` | relation nullable | Target/new base |
| `source_type` | single_select | csv, excel |
| `file_ref` | text/jsonb | Local/staged file reference or metadata |
| `detected_schema` | jsonb | Inferred fields |
| `preview_rows` | jsonb | Sample rows |
| `mapping` | jsonb | User-confirmed field mapping |
| `status` | status | uploaded, inferred, awaiting_confirmation, committed, failed |
| `created_by_user_id` | uuid/text | Creator |
| `error_summary` | text nullable | Redacted error |

### 4.14 `digital_employees`

Purpose: configurable table-bound Agent.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `base_id` | relation | Default base |
| `name` | text | Display name |
| `description` | text | Purpose |
| `telegram_alias` | text nullable | Mention alias |
| `accessible_tables` | jsonb | Configured max table scope |
| `accessible_views` | jsonb | Configured max view scope |
| `field_policy` | jsonb | Field read/write/mask policy |
| `allowed_actions` | jsonb | query, summarize, draft_create, draft_update, status_advance, notify |
| `confirmation_policy` | jsonb | Actions requiring confirmation |
| `response_style` | jsonb | Tone and format preferences |
| `status` | status | draft, active, disabled |

### 4.15 `record_change_drafts`

Purpose: proposed write changes before commit.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `base_id` | relation | Base |
| `table_id` | relation | Table |
| `record_id` | relation nullable | Existing record for update |
| `draft_type` | single_select | create_record, update_record, status_advance, notification |
| `proposed_values` | jsonb | Proposed field values |
| `before_values` | jsonb nullable | Snapshot for update |
| `created_by_type` | single_select | user, digital_employee, system |
| `created_by_id` | text | Actor |
| `status` | status | draft, pending_confirmation, confirmed, rejected, expired |
| `confirmation_policy` | jsonb | Required confirmation info |
| `trace_id` | text | Trace id |

### 4.16 `notification_requests`

Purpose: controlled Telegram/UI notification requests.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `base_id` | relation nullable | Base |
| `source_record_id` | relation nullable | Related record |
| `channel` | single_select | telegram, in_app |
| `target` | jsonb | Chat/user target, permission filtered |
| `message_payload` | jsonb | Redacted message body |
| `send_policy` | jsonb | dry_run, allowlist, confirmation |
| `status` | status | draft, pending_confirmation, queued, sent, blocked, failed |
| `trace_id` | text | Trace id |

### 4.17 `automation_events`

Purpose: status changes and queue events.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `base_id` | relation nullable | Base |
| `event_type` | text | Event type |
| `source_entity_type` | text | Source entity |
| `source_entity_id` | uuid/text | Source id |
| `payload` | jsonb | Event payload |
| `status` | status | pending, processed, failed, ignored |
| `trace_id` | text | Trace id |

### 4.18 `audit_events`

Purpose: authoritative audit timeline.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | relation | Workspace |
| `base_id` | relation nullable | Base |
| `actor_type` | single_select | user, digital_employee, system, worker |
| `actor_id` | text | Actor id |
| `event_type` | text | Event |
| `entity_type` | text | Resource type |
| `entity_id` | uuid/text nullable | Resource id |
| `before_state` | jsonb nullable | Redacted before |
| `after_state` | jsonb nullable | Redacted after |
| `permission_snapshot` | jsonb nullable | Effective permission |
| `trace_id` | text | Trace id |
| `created_at` | datetime | Timestamp |

## 5. Required Views

Every base should support:

- default grid view;
- optional kanban view when a status field exists;
- optional calendar view when a date field exists;
- optional form-lite view for record creation;
- dashboard-lite metadata reservation.

Stage06 platform admin views:

| View | Main resource | Purpose |
| --- | --- | --- |
| Workspace members | `workspace_members` | Membership and role visibility |
| Bases | `bases` | Base list |
| Tables | `tables` | Table builder |
| Fields | `fields` | Field configuration |
| Imports | `import_jobs` | Import preview and commit |
| Templates | `templates` | Template installation |
| Digital employees | `digital_employees` | Agent configuration |
| Draft confirmations | `record_change_drafts` | Confirm/reject changes |
| Audit | `audit_events` | Action evidence |

## 6. Digital Employee Start And Landing Matrix

| Action | Starts from | Reads | Writes / lands on | Confirmation |
| --- | --- | --- | --- | --- |
| Schema inspect | base/table/view | `tables`, `fields`, `views` | `audit_events` | No |
| Record query | view/table | `records` filtered by permission | `audit_events` | No |
| Summarize | view/table | filtered records | `agent_runs`, `audit_events` | No |
| Create record proposal | table/view/chat context | schema + permitted context | `record_change_drafts` | Yes |
| Update record proposal | record/view | record snapshot | `record_change_drafts` | Yes |
| Status advance proposal | queue view | record + status field | `record_change_drafts` | Yes by default |
| Notification proposal | record/view/chat | permitted summary | `notification_requests` | Yes unless dry-run internal |

## 7. Permission Blueprint

Permission layers:

```text
workspace
base
table
view
field
record
action
digital_employee
telegram_chat_scope
```

Effective digital employee scope:

```text
agent_configured_scope
∩ caller_user_scope
∩ telegram_chat_scope
```

Field policy must support:

- hidden;
- read-only;
- writable;
- masked;
- aggregate-only.

## 8. Template-To-Platform Rule

Templates do not create special backend behavior. They install regular platform resources:

```text
template manifest
-> base
-> tables
-> fields
-> views/forms
-> sample records
-> permissions
-> optional digital employees
```

Advertising-agency workflows must follow this rule if reintroduced in Stage06.

## 9. Implementation Notes

- Stage06 may add generic platform tables alongside existing Stage02-05 tables; it should not destroy historical data during migration.
- Existing Stage02-05 tables can later be wrapped as an advertising sample template or migrated into generic records.
- The Stage06 pilot may use seed templates rather than a full marketplace.
- Formula, attachment, full dashboard and full workflow should be schema-reserved but not implemented as full engines.

## 10. Acceptance Criteria

- A generic base can be created without any advertising template.
- A table can define typed fields and store records in JSONB.
- Linked record and lookup are represented in metadata and link rows.
- Grid, kanban, calendar and form-lite views have persisted configuration.
- CSV/Excel import can create a table after preview confirmation.
- Templates create ordinary platform resources.
- A digital employee can be configured from a base/table/view.
- Digital employee reads are permission-filtered.
- Digital employee writes create `record_change_drafts`.
- Confirmed drafts update records and write audit events.
- Telegram context does not bypass workspace/base/table/view permissions.
