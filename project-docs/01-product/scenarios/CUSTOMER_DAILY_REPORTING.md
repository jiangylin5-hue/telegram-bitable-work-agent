# Customer Daily Reporting

## Status

- Document status: scenario draft
- Scope: 每个客户每日账户消耗、客户日报、公司全局日报
- Current Progress: 2026-07-04 新增客户日报和公司日报场景，并补充 Bitable endpoint。

## 1. Business Value

当前没有专门负责统计每个客户每日账户消耗的岗位。本系统应让 Customer Reporting Agent 自动承担这项工作，并每天向客户和公司管理者生成日报。

## 1.1 Bitable Endpoint

客户日报和公司日报的终点必须是多维表格中的日报记录、发送状态、失败原因和审计日志更新。

| Layer | Endpoint |
| --- | --- |
| Main table | `customer_daily_reports` and `company_daily_reports` |
| Linked records | `customers`、`account_daily_metrics`、`recharge_records`、`account_assignments`、`account_assets`、`execution_logs` |
| Views | 客户日报视图、公司日报视图、风险看板、账户资产表、充值视图 |
| Key statuses | `draft`、`review_required`、`queued`、`sent`、`failed`、`stale_data` |
| Automation | 定时日报 job、权限过滤、人工复核队列、Telegram 发送、失败重试 |
| Agent output | customer daily report、company daily report、delivery status、review note |

## 2. Customer Daily Report

客户日报包含：

- 客户名。
- 日期。
- 名下账户列表。
- 每个账户今日消耗。
- 每个账户余额。
- 每个账户状态。
- 今日充值记录。
- 今日绑卡/换卡记录。
- 异常：低余额、封户、readback_failed、stale data。
- 需要客户补充的信息。

## 3. Company Daily Report

公司全局日报包含：

- 所有客户今日总消耗。
- 客户消耗排行。
- 低余额客户。
- 今日充值总额。
- 充值成功/失败/readback_failed。
- 账户库存：新增、未启用、已分配、异常。
- 绑卡成功/失败。
- 需要人工处理的 blocked/manual_review 任务。

## 4. Workflow

```text
daily scheduled job
-> Customer Reporting Agent queries customer accounts
-> aggregate spend/balance by customer
-> merge recharge/binding/account inventory status
-> generate customer-facing report
-> generate company-wide report
-> permission check
-> send Telegram report or queue for review
```

## 5. Data Handling

关键表：

- `account_assets`
- `account_daily_metrics`
- `customer_daily_reports`
- `company_daily_reports`
- `recharge_records`
- `account_assignments`
- `execution_logs`

所有消耗和余额数据必须带 `metric_date`、`freshness_at`、`source`。

## 6. Permission Checks

- 客户只能看到自己的日报。
- Sales 只能看自己客户或授权客户。
- Manager/Admin 可看全局日报。
- Agent 生成日报前必须按收件人权限过滤字段。

## 7. LLM Usage

允许：

- 把结构化统计转为客户可读文字。
- 总结公司全局日报。
- 解释数据缺失和 stale data。

禁止：

- 编造消耗。
- 把 stale data 当作 0。
- 泄露其他客户数据。
- 承诺未完成的充值/绑卡。

## 8. Acceptance Criteria

- 能生成客户级日报。
- 能生成公司全局日报。
- 每个数值有数据来源和 freshness。
- 报告按权限过滤。
- Telegram 发送前可配置是否需要人工复核。
