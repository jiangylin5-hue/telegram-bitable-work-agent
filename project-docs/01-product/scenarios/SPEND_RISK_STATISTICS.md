# Spend Risk Statistics

## Status

- Document status: scenario draft
- Scope: 消耗、余额、风险观察、日报和异常提醒
- Current Progress: 2026-07-04 完成消耗风险统计场景设计，并补充 Bitable endpoint。

## 1. Business Value

消耗和风险统计帮助销售、生产和管理者及时发现低余额、封户、空耗、异常消耗、数据延迟、权限缺失和 readback_failed 等问题。

该场景的核心不是 AI 投放诊断，而是基于已有业务数据和 provider readback 做证据化提醒。

## 1.1 Bitable Endpoint

消耗、风险和日报流程的终点必须是多维表格中的指标记录、风险事件、日报记录和角色视图更新。

| Layer | Endpoint |
| --- | --- |
| Main table | `account_daily_metrics` and `risk_events` |
| Linked records | `customers`、`account_assets`、`recharge_records`、`customer_daily_reports`、`company_daily_reports`、`execution_logs` |
| Views | 客户日报视图、公司日报视图、风险看板、账户资产表、充值视图 |
| Key statuses | `fresh`、`stale_data`、`low_balance`、`zero_spend`、`missing_permission`、`blocked_account`、`readback_failed` |
| Automation | 定时指标采集、日报生成、低余额提醒、数据过期提醒、异常升级 |
| Agent output | customer daily report、company daily report、risk event、customer-safe explanation |

## 2. Actors

| Actor | Responsibility |
| --- | --- |
| Sales | 查看客户风险和服务进度，维护客户沟通 |
| Production/Ops | 处理账户风险和异常 |
| Manager/Admin | 查看全局风险、SLA、员工负载 |
| Customer Reporting Agent | 统计客户每日账户消耗、余额、客户日报和公司全局日报 |
| Account Inventory Agent | 提供账户库存和账户状态 |
| Recharge And Binding Agent | 提供充值、绑卡、余额回读和执行事实 |

## 3. Trigger

- 定时任务读取账户余额和 spend。
- 服务执行后触发 readback。
- Telegram 中客户询问“为什么没消耗”。
- 管理者请求日报/周报。

## 4. Workflow

```text
scheduled job / user query
-> load account metrics and freshness
-> classify risk events
-> Customer Reporting Agent summarizes evidence
-> create risk event or report
-> notify relevant role
```

## 5. Data Handling

关键数据：

- balance。
- spend today/yesterday/7d。
- status。
- risk status。
- freshness / last_read_at。
- readback status。
- permission status。
- provider error code。

所有指标必须带 freshness，不允许把 stale data 当作实时数据。

## 6. Permission Checks

必须校验：

- 用户是否能看该 customer/account。
- 用户是否能看金额字段。
- Agent 是否能读取 spend、balance、risk 字段。
- 管理日报是否允许全局聚合。

## 7. LLM Usage

允许：

- 汇总风险。
- 解释已有状态。
- 生成日报。
- 生成客户回复草稿。

禁止：

- 编造投放原因。
- 把 unknown/stale/missing_permission 说成 0 spend。
- 做自动投放优化建议。
- 承诺账户一定会恢复或一定可投放。

## 8. Risk Classification

| Risk | Meaning |
| --- | --- |
| low_balance | 余额低于阈值 |
| zero_spend | 新鲜数据下 spend 为 0 |
| stale_data | 数据过期，不可判断 |
| missing_permission | 缺少读取权限 |
| blocked_account | 账户被封或限制 |
| abnormal_spend | 消耗高于或低于策略阈值 |
| readback_failed | 执行后余额回读失败 |

## 9. What We Do

- 展示账户和客户风险。
- 生成角色化日报。
- 把异常进入待办或提醒。
- 对客户回复提供证据化草稿。

## 10. What We Do Not Do

- 不做 AI 自动投放诊断。
- 不自动调整预算。
- 不自动恢复账户。
- 不把缺数据说成确定结论。

## 11. Acceptance Criteria

- 风险事件必须有 source metric 和 freshness。
- stale data 必须单独展示。
- 金额字段受字段权限控制。
- 日报必须按角色过滤数据。
- AI 回复必须引用可见证据。
