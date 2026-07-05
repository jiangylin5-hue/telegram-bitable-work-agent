# Finance Reconciliation Agent

## Status

- Document status: agent draft
- Scope: 收款核对、金额币种、充值前财务确认、财务异常
- Current Progress: 2026-07-04 重写财务核对 Agent。

## 1. Business Role

Finance Reconciliation Agent 负责核对客户付款和充值请求之间的关系。它不是充值执行者，主要价值是防止“客户说已付款”与“账户已充值”混淆。

## 1.1 Bitable Endpoint

Finance Reconciliation Agent 的所有输出必须回到多维表格：

| Output | Table / View |
| --- | --- |
| 收款记录 | collection/recharge finance table / 充值视图 |
| 财务确认状态 | `recharge_records.collection_status` / 充值视图 |
| 金额异常 | finance exception record / 财务视图 |
| 财务日报 | company/customer report tables / 公司日报视图 |

## 2. Workflow

```text
recharge request
-> query collection records
-> match customer/amount/currency
-> identify missing evidence or mismatch
-> produce finance confirmation summary
-> human finance confirms or rejects
-> result available to Recharge And Binding Agent
```

## 3. State

```text
FinanceReconciliationState
- customer_id
- recharge_draft_id
- expected_amount
- expected_currency
- collection_record_ids
- match_status
- mismatch_reason
- finance_confirmation_status
- confirmed_by_user_id
```

## 4. Tools

Read:

- `query_collection_records`
- `query_recharge_records`
- `query_customer_balance_history`
- `query_finance_exceptions`

Mutation:

- `create_collection_record`
- `update_finance_confirmation`
- `create_finance_exception`
- `create_finance_daily_summary`

## 5. LLM Usage

允许：

- 总结收款证据。
- 识别金额/币种不一致。
- 生成补证据提醒。
- 生成财务日报。

禁止：

- 自动确认到账。
- 执行充值。
- 把财务确认说成账户充值成功。

## 6. Required Skills

- reconciliation reasoning。
- amount/currency normalization。
- duplicate payment detection。
- evidence summarization。
- finance exception triage。

## 7. Acceptance Criteria

- 能区分收款、充值执行、余额回读。
- 能向 Recharge And Binding Agent 提供确认状态。
- 能生成财务异常清单。
