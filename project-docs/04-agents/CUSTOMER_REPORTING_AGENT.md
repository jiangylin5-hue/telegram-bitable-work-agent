# Customer Reporting Agent

## Status

- Document status: agent draft
- Scope: 客户每日账户消耗、客户日报、公司全局日报、余额和执行结果摘要
- Current Progress: 2026-07-04 替代原 Stats Risk Agent，明确日报和消耗统计职责。

## 1. Business Role

当前公司还没有专门负责统计每个客户每日账户消耗的工作。Customer Reporting Agent 负责把这项工作自动化：

- 每日统计每个客户所有账户消耗。
- 每日向客户发送账户消耗和余额日报。
- 每日生成公司所有客户的总日报。
- 汇总充值、绑卡、账户分配、异常和 readback 状态。
- 给管理者看公司整体客户、消耗、余额、风险、任务进度。

## 1.1 Bitable Endpoint

Customer Reporting Agent 的所有输出必须回到多维表格：

| Output | Table / View |
| --- | --- |
| 客户每日账户消耗 | `account_daily_metrics` / 客户日报视图 |
| 客户日报 | `customer_daily_reports` / 客户日报视图 |
| 公司全局日报 | `company_daily_reports` / 公司日报视图 |
| stale data 标记 | `risk_events` / 风险仪表盘 |
| readback_failed 汇总 | 充值视图 / 公司日报视图 |
| Telegram 发送记录 | report delivery status / 审计视图 |

## 2. Workflow: Customer Daily Report

```text
scheduled daily job
-> query customer accounts
-> query account spend/balance/freshness
-> query recharge and binding records
-> query account inventory changes
-> aggregate customer report
-> generate customer-facing summary
-> policy check
-> send Telegram report or queue for review
```

## 3. Workflow: Company Daily Report

```text
scheduled daily job
-> aggregate all customer spend
-> aggregate account inventory status
-> aggregate recharge/binding execution
-> aggregate failed/blocked/readback_failed items
-> generate manager report
-> send to internal management group
```

## 4. State

```text
CustomerReportingState
- report_date
- customer_id
- account_ids
- spend_total
- balance_total
- account_status_summary
- recharge_summary
- binding_summary
- readback_failures
- stale_data_accounts
- report_visibility
- delivery_status
```

## 5. Search State

```text
ReportingSearchState
- customer_scope
- account_metric_queries
- recharge_record_queries
- inventory_change_queries
- missing_metric_accounts
- stale_data_accounts
- selected_report_items
```

## 6. Tools

Read:

- `query_customer_accounts`
- `query_account_balance_and_spend`
- `query_customer_daily_spend`
- `query_company_daily_spend`
- `query_recharge_records`
- `query_card_binding_records`
- `query_account_inventory_changes`

Statistics:

- `aggregate_customer_daily_spend`
- `aggregate_company_daily_spend`
- `aggregate_customer_balance`
- `aggregate_execution_failures`

Mutation:

- `create_customer_report`
- `create_company_report`
- `mark_report_sent`

Notification:

- `send_customer_daily_report`
- `send_company_daily_report`

## 7. LLM Usage

允许：

- 把结构化统计结果写成客户可读日报。
- 把公司全局数据总结成管理日报。
- 解释 stale data、readback_failed、blocked 等状态。

禁止：

- 编造消耗。
- 把 stale data 写成 0 消耗。
- 给客户承诺未完成的充值/绑卡。
- 泄露其他客户数据。

## 8. Required Skills

- spend aggregation。
- role-based reporting。
- evidence-based writing。
- freshness handling。
- customer-safe wording。
- company dashboard summarization。

## 9. Acceptance Criteria

- 能按客户聚合每日账户消耗。
- 能生成客户日报。
- 能生成公司全局日报。
- stale data 和 missing permission 必须单独标记。
- 报告发送前按权限过滤。
