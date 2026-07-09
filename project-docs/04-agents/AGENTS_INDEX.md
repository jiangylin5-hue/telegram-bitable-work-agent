# Digital Employees Index

## Status

- Document status: active digital employee index
- Scope: Stage06 通用平台数字员工模型、权限、运行入口和历史 Agent 文档入口
- Current Progress: 2026-07-09 Rewritten for the Stage06 platform pivot. The active model is now configurable table-bound digital employees. Stage02-05 role Agents remain historical capability references and optional template presets.

## 1. Naming Principle

Stage06 no longer starts from fixed business-role Agents. It starts from user-created digital employees bound to platform resources.

Digital employee naming should describe:

- which base/table/view it works on;
- what outcome it supports;
- what actions it can perform;
- whether writes require confirmation.

Examples:

| Digital employee | Bound context | Purpose |
| --- | --- | --- |
| CRM Follow-up Assistant | CRM base, customers and follow-ups views | Summarize customers and draft follow-up updates |
| Project Coordinator | Project/task base, task kanban and calendar | Summarize overdue work and draft status changes |
| Ticket Triage Assistant | Customer service base, ticket queue | Classify tickets and draft replies/status changes |
| Inventory Clerk | Inventory/asset base, stock and exception views | Summarize stock and draft allocation/status changes |
| Advertising Ops Assistant | Advertising sample base | Historical vertical sample, not default platform center |

## 2. Required Configuration

Every digital employee must have:

| Field | Meaning |
| --- | --- |
| `id` | digital employee id |
| `workspace_id` | owning workspace |
| `base_id` | default base |
| `name` | display name |
| `description` | user-facing purpose |
| `telegram_alias` | optional `@` alias |
| `accessible_tables` | max table scope |
| `accessible_views` | max view scope |
| `field_policy` | field visibility and masking |
| `allowed_actions` | query, summarize, draft_create, draft_update, status_advance, notify |
| `confirmation_policy` | which actions require confirmation |
| `response_style` | concise, operational, formal, support-oriented |
| `status` | active, disabled, draft |

## 3. Runtime Permission Rule

Effective scope is always:

```text
agent_configured_scope
∩ caller_user_scope
∩ telegram_chat_scope
```

If any layer does not permit a read or action, the digital employee must return a permission-safe response and write an audit event.

## 4. Allowed Actions

Stage06 allows:

- `schema.inspect`
- `record.query`
- `record.summarize`
- `record_change_draft.create`
- `record_change_draft.update`
- `queue.status_advance_draft`
- `notification_request.create`

Stage06 does not allow by default:

- raw SQL;
- direct database writes by LLM;
- permission mutation by digital employee;
- broad Telegram sends;
- real external provider writes;
- funds/account operations.

## 5. Interaction Surfaces

| Surface | Role |
| --- | --- |
| Telegram group/private chat | `@digital_employee` mention, quick questions, confirmation prompts |
| Telegram Mini App | workspace/base/table UI, confirmation, permission-aware views |
| Desktop browser route | import, table building, template installation, permission configuration |
| Backend API | controlled tool surface and audit |

## 6. Historical Agent Documents

These documents remain useful as Stage02-05 implementation history and future template presets:

- [Operations Supervisor Agent](OPERATIONS_SUPERVISOR_AGENT.md)
- [Message Intake Router Agent](MESSAGE_INTAKE_ROUTER_AGENT.md)
- [Account Inventory Agent](ACCOUNT_INVENTORY_AGENT.md)
- [Recharge And Binding Agent](RECHARGE_AND_BINDING_AGENT.md)
- [Finance Reconciliation Agent](FINANCE_RECONCILIATION_AGENT.md)
- [Card Resource Agent](CARD_RESOURCE_AGENT.md)
- [Customer Reporting Agent](CUSTOMER_REPORTING_AGENT.md)

They are not the default Stage06 architecture. If reused, they should be expressed as digital employee presets installed by a template.

## 7. Completion Definition

A digital employee action is complete only when:

- the base/table/view context is resolved;
- effective scope is computed;
- all reads use permission-filtered records;
- any write-like output becomes a `record_change_draft` unless explicitly direct-safe;
- confirmation is recorded where required;
- final record/status/audit change is persisted;
- Telegram response references persisted state rather than unsupported claims.
