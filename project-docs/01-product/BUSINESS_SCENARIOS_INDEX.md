# Business Scenarios Index

## Status

- Document status: product scenario index draft
- Scope: 当前项目核心业务场景索引和阶段优先级
- Current Progress: 2026-07-04 建立核心业务场景索引，并要求所有场景对齐多维表格总蓝图的 table、view、automation 和 Agent landing point。

## 1. Scenario Principles

所有业务场景必须遵守：

- 所有业务场景从多维表格反推，不从 Agent 想象反推。
- 每个场景必须明确最终落在哪张表、哪个视图、哪类记录、哪种状态。
- Telegram 消息是入口，不是权限来源。
- Agent 可以识别、整理、摘要、生成草稿、查询授权数据；在人工确认后可以凭 `execution_ticket` 调用受控工具执行真实动作。
- 禁止的是绕过权限、人工确认、幂等、审计和 Tool Gateway 的裸写入。
- 真实执行必须经过用户身份、客户/账户 scope、动作权限、字段权限、幂等、风险策略和人工确认。
- 所有关键动作必须有 audit event。
- 所有外部写入成功必须有 execution log。
- unknown、stale data、missing permission 不能被 AI 编造成确定事实。

## 1.1 Bitable Endpoint Rule

每个场景必须定义 Bitable endpoint：

| Concept | Required answer |
| --- | --- |
| Table | 该场景的主数据表是什么 |
| Fields | 核心字段和字段类型是什么 |
| Linked records | 关联客户、账户、消息、服务、审计中的哪些记录 |
| Views | 由哪些视图承载 |
| Automation | 哪些状态变化触发提醒、日报、确认、执行 |
| Agent output | Agent 输出最终写入哪条记录 |

没有 Bitable endpoint 的场景不得进入实现。

具体 table、field、linked record、view、permission、automation 和 Agent 起点/落点以 [Bitable Schema Blueprint](../03-modules/BITABLE_SCHEMA_BLUEPRINT.md) 为准。场景文档不得定义与蓝图冲突的表格终点。

## 2. Priority Scenarios

| Priority | Scenario | Document | Why |
| --- | --- | --- | --- |
| P0 | 充值闭环 | [RECHARGE_WORKFLOW.md](scenarios/RECHARGE_WORKFLOW.md) | 同时验证销售、财务、生产、金额、权限、幂等、执行、回读和审计 |
| P0 | Telegram 消息转服务草稿 | [TELEGRAM_INGESTION_MODULE.md](../03-modules/TELEGRAM_INGESTION_MODULE.md) | 所有 AI 工作智能体的入口 |
| P1 | 账户库存管理 | [ACCOUNT_INVENTORY_WORKFLOW.md](scenarios/ACCOUNT_INVENTORY_WORKFLOW.md) | 管理生产账户、未启用账户、已分配账户、客户归属和状态 |
| P1 | 分户 / BM invite / 账户生产 | [BM_INVITE_AND_ACCOUNT_PRODUCTION.md](scenarios/BM_INVITE_AND_ACCOUNT_PRODUCTION.md) | 广告账户服务核心动作 |
| P1 | 卡资源 / 卡台 | [CARD_PLATFORM_WORKFLOW.md](scenarios/CARD_PLATFORM_WORKFLOW.md) | 管理 tokenized profile、卡状态、额度和可用性 |
| P1 | 客户日报和公司日报 | [CUSTOMER_DAILY_REPORTING.md](scenarios/CUSTOMER_DAILY_REPORTING.md) | 每日统计客户账户消耗并自动发送客户/公司日报 |
| P2 | 消耗与风险统计 | [SPEND_RISK_STATISTICS.md](scenarios/SPEND_RISK_STATISTICS.md) | 支持低余额、异常消耗、stale data 和风险提示 |

## 3. MVP Scenario

第一阶段推荐只承诺一条主闭环：

```text
客户充值请求
-> Telegram 消息识别
-> recharge draft
-> 财务确认收款证据
-> 生产确认账户和执行条件
-> controlled recharge execution
-> execution log
-> balance readback
-> Telegram 回传
```

该场景不要求第一版完成真实外部 provider 写入，可以先以 controlled service mock / sandbox adapter 方式验证状态机、权限、队列、审计和 Agent 输出。

## 4. Scenario Document Requirements

每个复杂场景文档必须包含：

- Bitable endpoint。
- Business value。
- Actors。
- Preconditions。
- Trigger。
- Workflow。
- Data handling。
- Permission checks。
- LLM usage。
- What we do。
- What we do not do。
- Failure handling。
- Audit and execution evidence。
- Acceptance Criteria。
