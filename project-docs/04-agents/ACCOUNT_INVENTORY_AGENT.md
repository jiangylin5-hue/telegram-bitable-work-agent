# Account Inventory Agent

## Status

- Document status: agent draft
- Scope: 账户库存、生产账户、未启用账户、已分配账户、客户归属、账户状态
- Current Progress: 2026-07-04 根据用户真实岗位描述新增账户库存 Agent。

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
