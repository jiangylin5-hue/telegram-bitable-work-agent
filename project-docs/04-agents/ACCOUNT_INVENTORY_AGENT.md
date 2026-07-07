# Account Inventory Agent

## Status

- Document status: agent draft
- Scope: 账户库存、生产账户、未启用账户、已分配账户、客户归属、账户状态
- Current Progress: 2026-07-07 根据 Stage05 用户确认更新职责边界：Account Inventory Agent 不生产账户，只负责账户分发、库存管理、异常状态处理和高确定性风控/封号自动标记。

## 0. Stage 05 Clarification

2026-07-07 用户明确修正本 Agent 边界：

- Account Inventory Agent 不负责生产账户。
- 账户生产、导入、生产批次创建属于人工生产角色、外部系统或后续单独流程。
- Account Inventory Agent 负责账户分发、库存管理、库存状态解释和异常处理。
- 因账户经常不稳定、经常风控、经常封号，Agent 需要能识别账户异常并维护库存状态。
- 高确定性异常，例如明确封号、明确风控、明确不可用，可以通过后端受控 service 自动标记为 `blocked`、`disabled` 或 `risk_controlled`，并必须写 `account_status_events` 和 `ops_audit_events`。
- 不明确的异常必须进入人工复核。
- 自动标记异常后，Stage05 不自动推荐替换账户、不自动预留候选账户、不自动重新分发账户。

本文旧章节中涉及 `Production creates or imports account`、`create_inventory_account` 的内容，只作为账户库存表如何接收外部生产结果的背景，不代表 Account Inventory Agent 在 Stage05 负责生产账户。

## 1. Business Role

Account Inventory Agent 负责管理广告账户库存。公司每天有人专门生产账户，这些账户需要被结构化记录在多维表格中，并明确：

- 哪些账户未启用。
- 哪些账户已分配。
- 分给了哪个客户。
- 分配给了谁负责。
- 当前账户状态是什么。
- 是否已绑卡。
- 是否已有余额和消耗。
- 是否可继续分配或需要回收。

## 2. Core Business Tables

- `account_inventory`
- `account_assets`
- `customers`
- `account_assignments`
- `account_status_events`
- `service_records`
- `ops_audit_events`

## 2.1 Bitable Endpoint

Account Inventory Agent 的所有工作必须落到多维表格：

| Output | Table / View |
| --- | --- |
| 新生产账户 | `account_inventory` table / 账户库存表 |
| 未启用账户列表 | 账户库存表 filtered by `inventory_status = unused` |
| 账户分配给客户 | `account_assignments` table / 客户总表 / 账户库存表 |
| 账户状态变化 | `account_status_events` table / 账户库存表 |
| 库存日报 | 账户库存表 summary view / 公司日报视图 |
| 审计 | `ops_audit_events` / 审计视图 |

## 3. Workflow: New Account Production

```text
Production creates or imports account
-> Account Inventory Agent validates required fields
-> status = produced / unused
-> inventory table updated
-> audit event recorded
-> account appears in unused inventory view
```

## 4. Workflow: Account Assignment

```text
Sales/customer requests account
-> Router detects account request
-> Account Inventory Agent searches unused inventory
-> filters by account status, risk, channel, customer constraints
-> proposes candidate accounts
-> human confirms assignment
-> account status = allocated
-> customer_id and owner_user_id assigned
-> audit event records assignment
```

## 5. State

```text
AccountInventoryState
- inventory_account_id
- external_account_id
- inventory_status
- assigned_customer_id
- assigned_user_id
- account_health_status
- card_binding_status
- balance_status
- spend_status
- production_batch_id
- last_state_change_at
```

Inventory statuses:

- `produced`
- `unused`
- `reserved`
- `allocated`
- `activated`
- `disabled`
- `blocked`
- `recycled`
- `archived`

## 6. Tools

Read:

- `query_account_inventory`
- `query_unused_accounts`
- `query_customer_assigned_accounts`
- `query_account_status_history`
- `query_account_binding_status`

Mutation:

- `create_inventory_account`
- `update_inventory_status`
- `assign_account_to_customer`
- `reserve_account`
- `release_reserved_account`
- `create_account_status_event`

Execution:

- Account Inventory Agent 本身不执行 Meta 写入。需要 BM invite 或 Meta 操作时，交给 Recharge And Binding Agent 或 controlled execution tools。

## 7. LLM Usage

允许：

- 从生产人员消息中提取账户 ID、批次、状态。
- 从客户需求中匹配候选库存账户。
- 总结库存日报。
- 提醒库存不足或状态异常。

禁止：

- 编造账户状态。
- 未确认就分配账户。
- 把 Telegram 群成员身份当作客户归属依据。

## 8. Required Skills

- inventory management。
- account lifecycle modeling。
- entity matching。
- status transition reasoning。
- audit-aware assignment。

## 9. Acceptance Criteria

- 能维护账户库存状态。
- 能查询未启用账户。
- 能查询账户分给了谁。
- 能生成账户库存日报。
- 分配账户必须记录 audit。
