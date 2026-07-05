# Recharge And Binding Agent

## Status

- Document status: agent draft
- Scope: Meta 后台绑卡、充值、账户 ID/余额/绑定卡登记、一卡一户约束
- Current Progress: 2026-07-04 重写原 Recharge Agent，合并真实绑卡充值执行职责。

## 1. Business Role

Recharge And Binding Agent 负责围绕 Meta 账户完成绑卡和充值执行。它不是只生成充值草稿，而是在人工确认后可以通过受控工具真实执行：

- 在 Meta 后台给账户绑卡。
- 给账户充值。
- 登记每个账户的 Meta account id。
- 记录账户余额。
- 记录账户绑定的是哪张卡。
- 遵守“一卡一户”或业务配置里的卡账户绑定策略。

## 2. Collaboration

依赖：

- Account Inventory Agent 提供账户库存和账户归属。
- Card Resource Agent 提供可用 tokenized card profile。
- Finance Reconciliation Agent 提供收款确认。
- Operations Supervisor Agent 提供 execution ticket。

## 2.1 Bitable Endpoint

Recharge And Binding Agent 的所有输出必须回到多维表格：

| Output | Table / View |
| --- | --- |
| 绑卡计划 | service draft / 充值视图 / 卡资源视图 |
| 充值计划 | `recharge_records` draft / 充值视图 |
| 账户绑定卡结果 | account binding fields / 账户资产表 / 卡资源视图 |
| 账户余额回读 | `account_assets` + `account_daily_metrics` / 账户资产表 |
| 充值执行结果 | `execution_logs` / 审计视图 |
| readback_failed | `recharge_records.readback_status` / 充值视图 |

## 3. Workflow: Card Binding

```text
request bind card
-> query account inventory/status
-> query card resource candidates
-> validate one-card-one-account policy
-> create binding plan
-> human confirms
-> execution_ticket issued
-> execute_meta_card_binding
-> write execution log
-> update account card binding
-> audit event
```

## 4. Workflow: Recharge

```text
request recharge
-> query account and current balance
-> query card binding
-> query finance collection status
-> validate amount/currency/policy
-> human confirms
-> execution_ticket issued
-> execute_meta_recharge
-> write execution log
-> execute_balance_readback
-> update balance and recharge record
-> Telegram callback
```

## 5. State

```text
RechargeBindingState
- customer_id
- account_id
- meta_account_id
- current_balance
- requested_amount
- currency
- bound_payment_profile_id
- card_binding_status
- one_card_one_account_policy_result
- finance_confirmation_status
- execution_ticket_id
- execution_status
- readback_status
```

## 6. Tools

Read:

- `query_account_inventory`
- `query_account_balance_and_spend`
- `query_account_card_binding`
- `query_recharge_records`
- `query_finance_collection_status`
- `query_payment_profile_usage`

Mutation:

- `create_recharge_plan`
- `create_card_binding_plan`
- `update_account_balance_snapshot`
- `update_account_card_binding`
- `create_recharge_record`

Execution:

- `execute_meta_card_binding`
- `execute_meta_recharge`
- `execute_balance_readback`

Execution tools require valid `execution_ticket`。

## 7. LLM Usage

允许：

- 抽取充值金额、币种、账户 ID。
- 识别绑卡意图。
- 总结缺失信息。
- 生成客户回复草稿。
- 解释执行日志和回读状态。

禁止：

- 无 ticket 直接执行。
- 编造余额或绑卡状态。
- 接触 raw card。
- 绕过财务确认。

## 8. Required Skills

- payment/account binding reasoning。
- amount and currency parsing。
- one-card-one-account policy checking。
- execution planning。
- provider error triage。
- balance readback interpretation。

## 9. Acceptance Criteria

- 能查询账户 ID、余额、绑定卡。
- 能判断账户是否已绑卡。
- 能遵守一卡一户策略。
- 能在人工确认后执行绑卡/充值工具。
- 能写 execution log 和 readback 状态。
