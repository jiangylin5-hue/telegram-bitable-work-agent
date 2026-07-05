# Agents Index

## Status

- Document status: agent index draft
- Scope: 高权限工作智能体目录、命名、职责、协作关系
- Current Progress: 2026-07-04 根据真实岗位分工重命名并重写 Agent 架构，并要求所有 Agent 以多维表格总蓝图为起点和落点。

## 1. Naming Principles

Agent 命名必须贴近真实业务岗位和数据职责，而不是泛泛的技术能力。

旧命名问题：

- `Stats Risk Agent` 不清楚具体岗位价值。
- `Recharge Agent` 没有覆盖 Meta 绑卡、账户余额登记、一卡一户。
- `Account Production Agent` 没有明确账户库存、未启用、已分配、给到谁、当前状态。
- `Card Platform Agent` 没有区分卡资源管理和真实绑卡执行。

新命名：

| Agent | Chinese name | Primary role |
| --- | --- | --- |
| Operations Supervisor Agent | 运营主管 Agent | 调度、路由、协作、确认点、执行票据 |
| Message Intake Router Agent | 消息入口路由 Agent | Telegram 消息分类、客户识别、任务路由 |
| Account Inventory Agent | 账户库存 Agent | 管理账户库存、生产账户、分配状态、客户归属 |
| Recharge And Binding Agent | 充值绑卡执行 Agent | Meta 后台绑卡、充值、余额登记、一卡一户 |
| Finance Reconciliation Agent | 财务核对 Agent | 收款、金额、币种、财务异常、充值前财务确认 |
| Card Resource Agent | 卡资源 Agent | 卡台资源、tokenized profile、卡状态、额度和可用性 |
| Customer Reporting Agent | 客户日报与消耗 Agent | 每个客户每日账户消耗、客户日报、公司全局日报 |

## 2. Global Agent Authority

Agent 可以：

- 通过授权 database/query tools 查客户、账户、库存、余额、消耗、绑卡、充值、服务记录。
- 通过 statistics tools 聚合客户日报、公司日报、账户库存状态。
- 通过 mutation tools 写草稿、任务、日报、风险事件、账户库存状态。
- 通过 execution ticket 调用 controlled execution tools 执行真实动作。

Agent 不可以：

- 裸连数据库。
- 裸写 SQL。
- 裸调 Meta、卡台、充值 provider。
- 无人工确认执行高风险动作。
- 读取 raw card / CVV / 未脱敏支付凭证。

## 2.1 Bitable Endpoint Rule

每个 Agent 必须说明：

- 读取哪些多维表格 table/view。
- 更新哪些多维表格 record/status。
- 触发哪些 automation/job。
- 输出最终落到哪个 table/view。

Agent 的最终价值不是“回答了什么”，而是“让多维表格中的业务记录、状态、视图、日报或审计发生了什么可追踪变化”。

每个 Agent 的 start view、read tables、write tables、automation 和 landing point 必须与 [Bitable Schema Blueprint](../03-modules/BITABLE_SCHEMA_BLUEPRINT.md) 保持一致。

## 3. Collaboration Map

```text
Message Intake Router
    -> Account Inventory Agent
    -> Recharge And Binding Agent
    -> Finance Reconciliation Agent
    -> Card Resource Agent
    -> Customer Reporting Agent

Operations Supervisor
    -> decides collaboration sequence
    -> requests human confirmation
    -> issues or validates execution ticket
    -> monitors execution and reporting
```

## 4. Agent Documents

- [Operations Supervisor Agent](OPERATIONS_SUPERVISOR_AGENT.md)
- [Message Intake Router Agent](MESSAGE_INTAKE_ROUTER_AGENT.md)
- [Account Inventory Agent](ACCOUNT_INVENTORY_AGENT.md)
- [Recharge And Binding Agent](RECHARGE_AND_BINDING_AGENT.md)
- [Finance Reconciliation Agent](FINANCE_RECONCILIATION_AGENT.md)
- [Card Resource Agent](CARD_RESOURCE_AGENT.md)
- [Customer Reporting Agent](CUSTOMER_REPORTING_AGENT.md)

## 5. Legacy Documents

以下旧文档保留为兼容入口，但已不再作为主设计：

- `TELEGRAM_TRIAGE_AGENT.md`
- `RECHARGE_AGENT.md`
- `FINANCE_AGENT.md`
- `ACCOUNT_PRODUCTION_AGENT.md`
- `CARD_PLATFORM_AGENT.md`
- `STATS_RISK_AGENT.md`
