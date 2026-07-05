# Implementation Source Of Truth

## Status

- Document status: active source of truth draft
- Scope: 当前项目顶层目标、边界、阶段、技术基线和安全约束
- Current Progress: 2026-07-04 确认方案 A、OpenRouter、多维表格宪法、高权限 Agent 受控执行模型、多维表格总蓝图和 Stage 02 开发范围。

## 1. 项目目标

本项目要开发一个基于飞书多维表格和多维表格智能体理念的 Telegram 多维表格和工作智能体系统。

项目目标是把广告代理商日常业务中的客户服务、账户生产、分户/BM invite、绑卡/卡台、充值、消耗统计、风险观察、服务审计和日报汇总，沉淀成可视化、可权限控制、可审计、可由 AI 协助处理的业务操作系统。

## 2. 核心产品形态

```text
Telegram Bot / Group / Mini App
-> message ingestion
-> AI intent extraction
-> multidimensional business records
-> multidimensional table views
-> service draft queue
-> human confirmation
-> controlled backend service
-> execution log and audit event
-> table record/status/view update
-> Telegram result callback
```

## 2.1 Bitable Constitution

多维表格是本项目的底层参照。所有需求、Agent、工作流、数据库表和执行工具都必须从多维表格机制反推：

```text
table
-> field
-> linked record
-> view
-> permission
-> automation
-> agent
-> controlled execution
```

所有业务流程的终点必须是多维表格中的某种可见、可查、可审计结果：

- 一条记录被创建。
- 一条记录状态被更新。
- 一个视图中出现待处理项。
- 一个自动化被触发。
- 一个执行日志或审计事件被关联到服务记录。
- 一个客户日报或公司日报被生成并可在视图中查看。

任何只停留在聊天消息、临时 Agent memory、未落表 JSON 或口头回复里的结果，都不算完成。

新增业务场景必须先说明它对应的 table、field、record relation、view、permission 和 automation endpoint，并更新 [Bitable Schema Blueprint](../03-modules/BITABLE_SCHEMA_BLUEPRINT.md)。

## 3. 已确认技术基线

| Area | Decision |
| --- | --- |
| Backend language | Python 3.12+ |
| Backend framework | FastAPI |
| API style | REST first, async jobs for long work |
| ORM | SQLAlchemy 2.x |
| Migration | Alembic |
| Primary database | PostgreSQL |
| Vector extension | pgvector |
| Queue/cache | Redis |
| Queue pattern | Redis Streams / reliable job queue first, Temporal as future upgrade candidate |
| Agent orchestration | LangGraph-first |
| LLM provider | OpenRouter-compatible API |
| LLM model binding | Runtime config, not hard-coded in business logic |
| Telegram integration | Bot API + Webhook + Mini App |
| Observability | Audit events, execution logs, job logs, agent trace ids |

## 4. 不依赖旧 SaaS 的内容

本项目是新项目，可以重新开发。以下旧项目内容只作为背景，不是强制约束：

- 旧项目的 Stage 07。
- 旧项目的 `/api/employee-ops/...`。
- 旧项目的数据库 schema。
- 旧项目的 employee-only 权限模型。
- 旧项目的前端 `/app`。

## 5. 必须保留的业务边界

迁移文档中这些业务边界仍然有效：

- Agent 可以通过授权工具访问数据库读模型、统计视图和检索工具。
- Agent 可以在人工确认后，通过 `execution_ticket` 调用受控执行工具真实执行 Meta、卡台、充值、绑卡、BM invite 等动作。
- 充值必须区分收款证据、充值执行和余额回读。
- 服务成功声明必须有 execution log。
- Telegram 群成员身份不能直接等同于系统权限。
- 禁止的是裸数据库连接、裸 SQL 写入、裸 provider key、绕过权限和绕过人工确认，不是禁止 Agent 查库或执行。
- 客户、账户、服务、充值、风险、消息、审计要结构化建模。
- 敏感支付凭证必须脱敏或 tokenized，不保存 raw card number / CVV。

## 6. Agent Authority Model

本项目采用高权限 Agent 模型：

```text
Agent request
-> permission-scoped database/query/statistics tool
-> structured decision state
-> proposed action or direct low-risk update
-> human confirmation for real-world write
-> execution_ticket
-> controlled execution tool
-> execution log + audit event + readback
```

Agent 可访问：

- 客户资料。
- 账户库存。
- 账户余额和消耗。
- 账户绑定卡信息的脱敏视图。
- 服务记录和执行日志。
- 每日客户消耗统计。
- 公司全局日报数据。

Agent 可执行：

- 低风险内部记录更新，例如生成日报、更新草稿状态、创建待办、写摘要。
- 人工确认后的真实外部操作，例如 Meta 后台绑卡/充值、卡台操作、BM invite。

Agent 不可执行：

- 无人工确认的高风险外部写入。
- 无权限 scope 的数据查询。
- raw card / CVV / 未脱敏支付凭证读取。
- 无 execution_ticket 的 provider 写入。

## 7. Stage 02 Confirmed Implementation Scope

用户已确认 Stage 02 采用 `ABC A A A A`：

| Area | Decision |
| --- | --- |
| Business slices | 充值闭环 + 账户库存 + 客户/公司日报 |
| Telegram | 先 mock webhook |
| Provider execution | 先 mock/sandbox adapter |
| Multi-tenancy | 第一版不做 `tenant_id` |
| DB + Redis consistency | 采用 outbox table |

Stage 02 聚焦：

```text
Mock Telegram message
-> message ingestion
-> AI/mock intent extraction
-> 生成 service draft
-> 写入多维表格服务草稿记录
-> 多维表格待确认队列
-> 财务/生产/管理确认
-> 生成 execution_ticket
-> Agent/worker 调用 mock controlled execution tool 执行或 blocked
-> execution log + audit
-> 更新多维表格 service/recharge/account/inventory/report 视图
-> mock Telegram 回传或 notification outbox
```

Stage 02 不同时铺开所有真实外部集成。开发顺序是：

1. 后端内核：FastAPI、SQLAlchemy、Alembic、权限、审计、outbox、Bitable view API。
2. 充值闭环：mock Telegram 到充值草稿、确认、execution ticket、mock 执行、execution log、readback。
3. 账户库存：生产账户、未启用账户、分配给客户、状态事件。
4. 客户/公司日报：每日账户消耗、freshness、客户日报、公司全局日报。

Stage 02 开发必须先读取 [Stage 02 Source Of Truth](../08-implementation/STAGE_02_SOURCE_OF_TRUTH.md)，再按 [Stage 02 Backend Kernel And Vertical Slices Implementation Plan](../08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md) 执行。模块设计以 [Stage 02 SDD](../08-implementation/STAGE_02_SDD.md) 为准，行为验收以 [Stage 02 BDD](../08-implementation/STAGE_02_BDD.md) 为准，复杂模块边界以 [Stage 02 Module Index](../08-implementation/STAGE_02_MODULE_INDEX.md) 为准，子阶段完成记录写入 [Stage 02 Progress](../08-implementation/STAGE_02_PROGRESS.md)。

## 8. 当前不做

- 不写业务代码。
- Stage 02 之前不写业务代码。
- Stage 02 不接入真实 Telegram bot。
- Stage 02 不接入真实 Meta/BM/卡台/充值 provider。
- Stage 02 不执行真实资金和账户写入。
- 不实现完整财务账本、发票、结算。
- 不做 AI 自动投放优化。
- 不保存 raw payment credential。

## 9. 文档体系

当前项目文档按以下目录组织：

- `00-governance`: 真源、技术决策、项目协作规则。
- `00-research`: 飞书、Telegram、Agent 等外部调研。
- `01-product`: 产品简报、业务场景、复杂场景文档。
- `02-architecture`: 后端 SDD、multi-agent 编排、系统边界。
- `03-modules`: Telegram、多维表格、草稿确认等模块设计，其中 `BITABLE_SCHEMA_BLUEPRINT.md` 是业务表格、视图、权限、自动化和 Agent 落点总蓝图。
- `04-agents`: Agent / 子 Agent 详细开发文档。
- `05-data`: PostgreSQL、权限、安全、向量检索。
- `06-queue`: Redis queue、worker、job、失败处理。
- `07-acceptance`: 阶段验收清单。
- `08-implementation`: 实施计划、阶段开发切片和阶段验收。

## 10. Confirmation Rule

以下内容变更前必须先向用户确认：

- 后端语言或框架。
- ORM、迁移工具、数据库、队列、Agent 编排框架。
- LLM provider 或模型路由原则。
- 权限模型。
- 数据库 schema 的核心实体和关系。
- 真实外部系统写入策略。
- AI 能否从草稿升级为自动执行。
