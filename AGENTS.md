# AGENTS.md

## Status

- Document status: active project collaboration rule
- Scope: Telegram 多维表格和工作智能体项目
- Current Progress: 2026-07-04 建立项目级协作规则，写入多维表格宪法、高权限 Agent 边界、文档优先和逐项验收规则。

## 1. 项目定位

本项目是一个面向广告代理商业务的 Telegram 多维表格和工作智能体系统。目标是效仿飞书多维表格和多维表格智能体的成熟机制，把 Telegram 消息、多维业务数据、AI 工作智能体、权限、人工确认、后端受控执行和审计日志结合起来。

本项目不是通用飞书竞品，不是纯聊天机器人，不是 AI 自动投放系统，也不是允许 AI 直接执行真实充值、绑卡、下户或账户写入的 autopilot。

## 2. Bitable Constitution

多维表格是本项目的底层参照和产品宪法。所有设计必须从飞书多维表格和多维表格智能体的核心机制反推，而不是凭空创造需求。

设计顺序必须是：

```text
业务对象
-> 多维表格 table
-> 字段和字段类型
-> 关联记录
-> 视图
-> 权限
-> 自动化
-> Agent 能力
-> 执行工具
```

禁止的设计方式：

```text
先凭空设计 Agent
-> 再想它应该做什么
-> 最后找地方存结果
```

所有业务场景和工作流的终点必须回到多维表格，具体表现为：

- 新增或更新一条业务记录，例如客户、账户库存、服务草稿、服务记录、充值记录、日报、审计事件。
- 改变一条记录的状态，例如 `unused`、`allocated`、`pending_confirmation`、`executing`、`succeeded`、`readback_failed`。
- 进入一个明确视图，例如 Telegram 收件箱、账户库存表、充值视图、客户日报视图、公司日报视图、审计视图。
- 触发一个基于表格记录的自动化，例如提醒、日报发送、人工确认、执行 ticket、异常升级。

任何停留在 Telegram 聊天、临时 Agent 记忆、口头结论、未落表 JSON、未审计工具调用里的结果，都不算完成。

Agent 不是独立于多维表格之外的机器人。Agent 是运行在多维表格业务数据、视图、权限和自动化之上的数字员工：

- Agent 的输入来自多维表格记录、Telegram 消息记录、视图上下文和授权检索。
- Agent 的中间状态必须能关联到 workflow、record、view、audit event。
- Agent 的输出必须落回多维表格记录、状态、视图、日报或执行日志。
- Agent 的能力边界由多维表格权限、字段权限、动作权限和执行 ticket 决定。

新增业务需求前必须先回答：

- 它对应哪张表？
- 需要哪些字段？
- 和哪些记录关联？
- 由哪个视图承载？
- 谁能看、谁能改、谁能确认、谁能执行？
- 是否需要 Agent？
- Agent 输出落到哪条记录或哪个视图？
- 成功/失败如何在多维表格中表现？

具体落地以 `project-docs/03-modules/BITABLE_SCHEMA_BLUEPRINT.md` 为多维表格总蓝图。后续业务场景、Agent、数据库、API、队列和前端视图设计都必须能追溯到该蓝图。

## 3. Language

- 默认使用中文沟通。
- 代码、API、数据库表名、字段名、命令、技术名词保持英文。
- 文档中文为主，但稳定状态字段使用英文，例如 `Status`、`Scope`、`Current Progress`、`Acceptance Criteria`。

## 4. Documentation First

本项目当前阶段是后端开发前的顶层文档设计阶段。任何后端实现、依赖安装、代码脚手架、数据库迁移、真实外部系统写入之前，必须先完成并确认对应文档。

必须先写文档的内容包括：

- 技术选型和架构方案。
- Agent 编排、context、memory、state、tool、MCP、vector retrieval 方案。
- 数据库 schema、权限模型、事务、唯一值、敏感字段。
- Redis queue、job id、失败处理、worker 设计。
- 业务场景和业务边界，且必须说明对应的多维表格 table、view、record、automation endpoint。
- 每个 Agent / 子 Agent 的职责边界和工具边界。

## 5. Confirmed Technical Baseline

已确认采用方案 A：

| Layer | Decision |
| --- | --- |
| Backend language | Python 3.12+ |
| Backend framework | FastAPI |
| ORM | SQLAlchemy 2.x |
| Migration | Alembic |
| Primary database | PostgreSQL |
| Vector search | pgvector |
| Queue/cache | Redis |
| Agent orchestration | LangGraph-first |
| LLM provider | OpenRouter-compatible API |
| Telegram | Bot API + Webhook + Mini App |

这些是当前项目后续后端开发的默认基线。若要更改，需要先写入技术决策文档并由用户确认。

## 6. Agent Authority And Safety Boundaries

本项目的 Agent 不是弱助手，而是带权限边界的数字员工。Agent 可以通过后端授权工具访问数据库读模型、统计视图、检索索引和受控执行工具，但不能裸连数据库、不能裸写 SQL、不能裸调 Meta/卡台/充值 provider。

Agent 允许：

- 通过 Tool Gateway 查询客户、账户、账户库存、余额、消耗、充值、绑卡、服务记录、审计记录。
- 统计客户每日账户消耗、账户余额、客户日报、公司全局日报。
- 生成和更新服务草稿、任务建议、日报草稿、风险提示。
- 在人工确认后，使用带过期时间和权限快照的 `execution_ticket` 调用受控执行工具。
- 执行通过确认的 Meta、卡台、充值、绑卡、BM invite 等动作。
- 写入执行结果、回读状态、执行日志和审计事件，但必须通过后端 service/tool 完成。

Agent 禁止：

- 裸连接 PostgreSQL 或使用未授权 SQL。
- 绕过 Tool Gateway 直接拿数据库账号、Meta token、卡台 key 或充值 provider key。
- 自己判断“已确认”并执行真实动作。
- 绕过人工确认、权限校验、策略校验、幂等检查、execution ticket 和审计日志。
- 接触 raw card number、CVV、完整卡图或未脱敏支付凭证。
- 把 unknown、stale data、missing permission 编造成确定事实。
- 在没有 execution log 的情况下声称真实操作成功。

技术表达：

```text
Agent
-> authorized database/query/statistics tools
-> authorized draft/update/report tools
-> human confirmation
-> execution_ticket
-> controlled execution tools
-> execution log + audit event
```

## 7. Development Rules

- 当前阶段只写文档，不写业务代码。
- 任何阶段开始前必须有明确 `Scope` 和 `Acceptance Criteria`。
- 复杂业务场景必须单独建文档，并由索引文件链接。
- 每个文档更新后必须维护 `Current Progress`。
- 不做无关重构，不引入未讨论的新业务场景。
- 不凭空创造业务场景；任何场景都必须能追溯到用户真实业务、迁移立项文档、飞书多维表格机制或用户当前明确指令。
- 任何 workflow 如果没有多维表格 endpoint，不允许进入实现计划。
- 所有真实外部系统写入必须先讨论并确认。
- 文档中如果存在假设，必须标记为 `Assumption`。
- 测试和验收时不能口头宣称“已做完”或“已测试”，必须对照对应文档逐项核对。
- 每个阶段必须制定可执行验收标准，并记录哪些通过、哪些未通过、哪些未测试以及原因。
- 验收报告必须引用文档条目、测试命令、测试结果或人工核对证据。

## 8. Architecture Reuse Rule

优先复用 GitHub 和官方生态中成熟的架构与框架：

- Agent 编排优先复用 LangGraph 的 graph、state、checkpoint、human-in-the-loop、supervisor / sub-agent 模式。
- LLM 访问优先使用 OpenRouter 的 OpenAI-compatible API 方式，不在业务层绑定单一模型。
- 后端优先使用 FastAPI、SQLAlchemy 2.x、Alembic、PostgreSQL、Redis 等成熟组合。
- 除非文档说明必要，不自研通用 agent framework、ORM、迁移系统、队列系统或权限引擎。

## 9. Source Of Truth Order

项目内文档优先级：

1. 用户当前明确指令。
2. 本文件 `AGENTS.md`。
3. `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`。
4. `project-docs/03-modules/BITABLE_SCHEMA_BLUEPRINT.md`。
5. `project-docs/00-governance/TECHNICAL_DECISIONS.md`。
6. 架构、业务场景、Agent、数据库、队列等专项文档。
7. 迁移版旧项目立项文档，仅作为背景参考。

## 10. Completion Rule

任何阶段交付说明必须包含：

- Changed files。
- What changed。
- Verification。
- Skipped tests。
- Remaining risks。
