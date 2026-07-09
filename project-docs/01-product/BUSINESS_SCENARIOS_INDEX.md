# Templates And Scenarios Index

## Status

- Document status: active product template/scenario index
- Scope: Stage06 通用平台模板、示例业务场景和历史垂直场景入口
- Current Progress: 2026-07-09 Rewritten for the Stage06 platform pivot. The active index now prioritizes generic templates and platform scenarios. Advertising-agency workflows are retained as historical scenario documents and optional sample-template inputs.

## 1. Index Principle

Stage06 starts from platform resources, not vertical business assumptions.

Every template or scenario must answer:

| Concept | Required answer |
| --- | --- |
| Workspace/Base | 属于哪个 workspace/base |
| Tables | 创建哪些 table |
| Fields | 核心字段和字段类型 |
| Linked records | 哪些表之间有关联 |
| Views | grid/kanban/calendar/form-lite 如何承载 |
| Permissions | 谁能看、谁能写、谁能确认 |
| Digital employee | 是否需要默认数字员工 |
| Draft endpoint | Agent 写入是否进入 `record_change_drafts` |
| Audit endpoint | 哪些动作写 `audit_events` |

没有 table endpoint 的场景不得进入实现计划。

## 2. Stage06 Primary Templates

| Priority | Template | Purpose | Stage06 status |
| --- | --- | --- | --- |
| P0 | CRM / Customer Management | 客户、联系人、跟进、状态、负责人 | Required |
| P0 | Project / Task | 项目、任务、负责人、进度、截止日期 | Required |
| P0 | Customer Service / Ticket | 工单、优先级、状态、处理人、回复草稿 | Required |
| P0 | Inventory / Asset | 资产、库存、分配、异常、状态 | Required |
| P1 | Advertising Agency Sample | 充值、账户、绑卡、日报等历史能力样例 | Optional sample |

## 3. Platform Scenarios

| Scenario | Description | Required endpoint |
| --- | --- | --- |
| Create base from scratch | 用户手动创建 base/table/fields/views | `bases`、`tables`、`fields`、`views` |
| Import CSV/Excel | 用户上传表格，系统推断字段，用户确认后创建 table | `import_jobs`、`fields`、`records` |
| Save as template | 将已有 base/table/view/agent 配置保存为模板 | `templates` |
| Install template | 从官方模板创建 base | `template_installations`、`bases` |
| Configure permissions | 配置 workspace/base/table/view/field/action 权限 | `permission_bindings` |
| Create digital employee | 基于 base/table/view 创建数字员工 | `digital_employees` |
| Ask digital employee | Telegram 或 Mini App 中提问 | `agent_runs`、optional `record_change_drafts` |
| Confirm record draft | 用户确认数字员工生成的写入草稿 | `record_change_drafts`、`records`、`audit_events` |
| Controlled notification | 数字员工生成受控通知草稿或发送请求 | `notification_requests`、`audit_events` |

## 4. Template Requirements

Each official template should include:

- template metadata;
- table definitions;
- field definitions;
- linked record definitions;
- view definitions;
- sample records;
- default permission recommendations;
- default digital employee preset;
- import mapping hints;
- acceptance examples.

Templates must not hardcode platform rules. Installing a template creates ordinary bases, tables, fields, views and optional digital employees.

## 5. Historical Advertising Scenarios

The following documents are retained as historical Stage02-05 capability references and future template input:

- [Recharge Workflow](scenarios/RECHARGE_WORKFLOW.md)
- [Account Inventory Workflow](scenarios/ACCOUNT_INVENTORY_WORKFLOW.md)
- [BM Invite And Account Production](scenarios/BM_INVITE_AND_ACCOUNT_PRODUCTION.md)
- [Card Platform Workflow](scenarios/CARD_PLATFORM_WORKFLOW.md)
- [Customer Daily Reporting](scenarios/CUSTOMER_DAILY_REPORTING.md)
- [Spend Risk Statistics](scenarios/SPEND_RISK_STATISTICS.md)

They are not the Stage06 product center. If reused in Stage06, they must be converted into the `Advertising Agency Sample` template and expressed through generic platform resources.

## 6. Stage06 MVP Scenario

The Stage06 pilot should prove one generic path, not one advertising path:

```text
workspace created
-> base created from template or import
-> table fields confirmed
-> view configured
-> digital employee created from table/view
-> Telegram @ mention resolves context
-> digital employee reads permitted records
-> digital employee creates record_change_draft
-> user confirms
-> record updates
-> audit event written
```

## 7. Acceptance Criteria

- Generic templates appear before the advertising sample.
- A user can run the pilot without choosing the advertising sample.
- Every template maps to platform resources in [Bitable Schema Blueprint](../03-modules/BITABLE_SCHEMA_BLUEPRINT.md).
- Every Agent/digital employee action maps to [Agents Index](../04-agents/AGENTS_INDEX.md).
- Historical advertising documents are clearly marked as historical/template input.
