# Account Inventory Workflow

## Status

- Document status: scenario draft
- Scope: 账户库存、生产账户、未启用账户、分配给客户、账户状态流转
- Current Progress: 2026-07-07 根据 Stage05 用户确认补充边界：Account Inventory Agent 不生产账户，只负责账户分发、库存管理和异常状态处理；高确定性风控/封号可自动标记状态，但不自动替换分发。

## 0. Stage 05 Clarification

2026-07-07 用户明确：

- 本项目中的 Account Inventory Agent 不生产账户。
- 账户生产由人工生产人员、外部系统或后续独立流程负责。
- Account Inventory Agent 的核心职责是分发账户、管理库存、识别异常、维护账户状态。
- 账户经常不稳定，可能风控、封号或不可用，因此库存工作流必须覆盖异常状态管理。
- Stage05 允许 Agent 对高确定性异常自动标记 `blocked`、`disabled` 或 `risk_controlled`，但必须有账户记录、来源证据、状态事件和审计。
- Stage05 不自动推荐替代账户、不自动预留账户、不自动重新分配账户；替换需求进入人工处理或后续阶段。

后文中关于 Production 生产账户的段落，表示“库存表接收生产结果”的业务背景，不表示 Stage05 Agent 负责生产账户。

## 1. Business Value

公司每天有人专门负责生产广告账户。账户生产出来后，如果没有系统管理，就会出现库存不清、分配不清、状态不清、给了哪个客户不清、是否已启用不清等问题。

账户库存场景的目标是让所有账户像多维表格库存一样被管理：

- 哪些账户刚生产出来。
- 哪些账户未启用。
- 哪些账户已保留。
- 哪些账户已分配给客户。
- 分给了哪个客户、由谁负责。
- 当前是否已绑卡、是否已充值、是否有消耗。
- 是否被封、停用、回收或归档。

## 1.1 Bitable Endpoint

账户库存流程的终点必须是多维表格中的库存账户记录、分配记录、状态事件和库存视图更新。

| Layer | Endpoint |
| --- | --- |
| Main table | `account_inventory` |
| Linked records | `customers`、`account_assignments`、`account_assets`、`account_status_events`、`recharge_records`、`execution_logs` |
| Views | 账户库存视图、未启用账户视图、客户账户视图、账户资产表、公司日报视图 |
| Key statuses | `produced`、`unused`、`reserved`、`allocated`、`activated`、`blocked`、`recycled` |
| Automation | 库存不足提醒、账户分配确认、状态审计、库存日报、客户账户视图刷新 |
| Agent output | inventory account record、assignment record、status event、inventory summary |

## 2. Actors

| Actor | Responsibility |
| --- | --- |
| Production | 生产账户、导入账户、更新账户状态 |
| Sales | 申请给客户分配账户 |
| Account Inventory Agent | 管理库存、推荐候选账户、生成库存日报 |
| Recharge And Binding Agent | 查询账户后执行绑卡充值 |
| Manager/Admin | 查看库存总览和异常 |

## 3. Workflow

```text
Production produces accounts
-> Account Inventory Agent imports/validates accounts
-> status = unused
-> Sales/customer requests account
-> Agent searches candidate unused accounts
-> human confirms assignment
-> account assigned to customer
-> status = allocated / activated
-> later binding/recharge/spend update account state
```

## 4. Data Handling

关键表：

- `account_inventory`
- `account_assignments`
- `account_status_events`
- `account_assets`
- `customers`
- `ops_audit_events`

唯一值：

- `platform + external_account_id`
- `inventory_account_code` if used

敏感字段：

- 账户外部 ID、客户归属、BM 权限、状态原因。

## 5. Permission Checks

- Production 可以创建和更新库存账户。
- Sales 可以申请账户，但不能直接修改库存归属。
- Manager/Admin 可以查看全局库存。
- Agent 可以通过授权工具查询库存和推荐账户。
- 分配账户必须人工确认并写 audit。

## 6. LLM Usage

允许：

- 从生产消息中抽取账户 ID 和批次。
- 从客户需求中推荐候选账户。
- 总结库存日报。
- 解释账户状态。

禁止：

- 编造账户是否可用。
- 无确认直接分配账户。
- 把库存账户分配给无权限客户。

## 7. Acceptance Criteria

- 能查询未启用账户。
- 能查询账户分给了谁。
- 能查询客户名下账户。
- 能按状态统计库存。
- 分配和状态变更必须有 audit。
