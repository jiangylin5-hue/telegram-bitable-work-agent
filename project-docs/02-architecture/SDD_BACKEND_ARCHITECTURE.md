# SDD Backend Architecture

## Status

- Document status: backend SDD draft
- Scope: Telegram 多维表格和工作智能体后端架构
- Current Progress: 2026-07-04 基于方案 A 完成后端顶层 SDD，并接入多维表格总蓝图作为业务、工作流和 Agent 的架构输入。

## 1. System Purpose

后端系统负责把 Telegram 消息、多维业务数据、AI 工作智能体、人工确认、受控执行、审计日志和任务队列连接成可靠闭环。

后端不是简单 CRUD，也不是直接给 AI 开数据库权限。后端必须承担：

- 身份认证和授权。
- Telegram webhook 接收和消息规范化。
- 多维表格业务对象建模。
- 确保所有业务 workflow 最终落到多维表格记录、状态、视图、自动化或审计事件。
- 服务草稿生成和确认状态机。
- Agent 编排入口、授权数据库工具、统计工具、执行工具网关。
- PostgreSQL 事务和审计。
- Redis 队列和 worker 调度。
- OpenRouter LLM 调用审计。
- execution log 和可追踪结果回传。

## 2. Architecture Overview

```text
Telegram Bot / Mini App
        |
        v
FastAPI API Layer
        |
        +--> Auth / Permission Layer
        |
        +--> Telegram Ingestion Module
        |
        +--> Multidimensional Table Module
        |
        +--> Service Draft And Confirmation Module
        |
        +--> Agent Gateway / LangGraph Runtime
        |
        +--> Controlled Execution Services
        |
        +--> Audit / Execution Log Module
        |
        v
PostgreSQL + pgvector
        |
        v
Redis Queue / Workers
```

## 2.1 Bitable-First Architecture Rule

后端架构必须以多维表格为底层参照反推：

```text
business object
-> PostgreSQL table
-> field type and constraints
-> linked records
-> role-based views
-> automations and jobs
-> Agent tools
-> controlled execution
-> updated table record/view
```

任何模块如果不能说明自己的输出落到哪张表、哪个字段、哪条记录、哪个视图或哪个审计事件，就不能进入实现。

后端模块、API、service、Agent tool、worker 和前端视图的具体业务对象必须优先引用 [Bitable Schema Blueprint](../03-modules/BITABLE_SCHEMA_BLUEPRINT.md)，再反推 PostgreSQL schema、Pydantic schema、权限策略和队列任务。

## 3. Backend Layers

### 3.1 API Layer

Framework: FastAPI。

Responsibilities:

- 暴露 Telegram webhook endpoint。
- 暴露 Mini App / Web 后端 API。
- 暴露内部 agent/job callback API。
- 输入校验使用 Pydantic schema。
- 所有 API 返回稳定错误码和 `trace_id`。

API 原则：

- 外部请求不直接操作数据库模型。
- route handler 只做鉴权、校验、调用 service、返回 response。
- 业务规则放在 service layer。
- 长任务必须入队，不在 HTTP 请求里直接跑完。

### 3.2 Service Layer

Responsibilities:

- 执行业务状态机。
- 管理事务边界。
- 执行权限校验。
- 创建 audit event。
- 创建/更新 service draft、service record、execution log。
- 发起 Redis job。

Service layer 是真实业务行为的唯一入口。AI、Telegram、Mini App、worker 都不能绕过 service layer 直接修改核心表。

### 3.3 Repository / ORM Layer

Tools: SQLAlchemy 2.x。

Responsibilities:

- 定义 ORM models。
- 封装常用查询。
- 管理关系加载。
- 承载事务 session。

不得在 repository 层写业务判断。repository 只表达数据读写，不决定“是否允许执行充值”。

### 3.4 Migration Layer

Tools: Alembic。

Responsibilities:

- 维护数据库 schema 迁移历史。
- 新增表、字段、索引、唯一约束、外键。
- 支持版本化升级和回滚。

所有核心 schema 变更必须先写入 `POSTGRES_DATABASE_DESIGN.md`，再写 migration。

### 3.5 Agent Runtime Layer

Tools: LangGraph-first, OpenRouter-compatible API。

Responsibilities:

- 将 Telegram triage、intent extraction、draft generation、permission precheck、report generation 等流程编排为 graph。
- 管理 agent state。
- 调用 LLM。
- 调用 tool gateway。
- 输出结构化结果。

Agent runtime 不能直接写核心业务表。它必须通过 service layer 创建草稿、写 agent trace、写建议结果。

### 3.6 Tool Gateway Layer

Tool Gateway 是 Agent 访问数据库、统计视图、检索系统和受控执行能力的唯一入口。

Tool Gateway 提供三类工具：

- Query tools: 查询客户、账户库存、账户状态、余额、消耗、服务记录、执行日志。
- Mutation tools: 创建草稿、更新低风险内部记录、写日报、写风险事件。
- Execution tools: 在 `execution_ticket` 存在且有效时执行 Meta、卡台、充值、绑卡、BM invite 等动作。

Tool Gateway 必须校验：

- agent identity。
- tool permission。
- record scope。
- field permission。
- action permission。
- execution ticket。
- idempotency key。

禁止：

- LLM 裸 SQL。
- LLM 直接拿数据库连接。
- LLM 直接拿 provider secret。

### 3.7 Queue / Worker Layer

Tools: Redis。

Responsibilities:

- 异步处理 Telegram 消息解析。
- 异步生成 AI 草稿。
- 异步生成日报。
- 异步回传 Telegram。
- 异步执行外部 provider polling。
- 失败重试和 dead letter 记录。

## 4. Core Modules

| Module | Responsibility |
| --- | --- |
| Auth & Permission | 用户、角色、scope、字段权限、动作权限、Agent 权限 |
| Telegram Ingestion | webhook 接收、消息去重、群绑定、sender 解析 |
| Multidimensional Table | base/table/view/record 抽象和业务视图 |
| Service Draft | AI/人工草稿、补资料、确认、驳回、升级 |
| Confirmation | human-in-the-loop 确认、复核、审批 |
| Agent Gateway | LangGraph 调用、OpenRouter 调用、tool policy |
| Retrieval | pgvector 检索 SOP、历史服务、客户上下文 |
| Execution Gateway | 受控执行入口，封装 Meta/BM/卡台/充值 provider |
| Audit | audit events、trace id、actor、before/after |
| Execution Log | 真实外部执行证据、provider response、readback |
| Queue | Redis job、retry、worker、dead letter |

## 5. Data Flow: Telegram Message To Draft

```text
1. Telegram sends webhook update.
2. FastAPI validates webhook secret.
3. Telegram Ingestion service normalizes message.
4. Message is inserted with source ids and idempotency key.
5. Redis job is created: `agent.intent_extract`.
6. Worker loads message, customer group, permissions and recent context.
7. LangGraph triage graph calls OpenRouter.
8. Agent returns structured intent candidate.
9. Service Draft service validates fields and permissions.
10. Draft is created as a multidimensional table record with `draft` or `needs_more_info` state.
11. The record appears in a table view such as AI 草稿队列 or 充值视图.
12. Audit event is written and linked to the record.
13. Telegram notification job is created.
```

## 6. Data Flow: Draft To Controlled Execution

```text
1. Authorized human opens Mini App confirmation queue.
2. API checks actor permission and draft state.
3. User confirms, rejects, supplements data, or escalates.
4. Confirmation service creates service_record.
5. Execution policy decides `execute`, `blocked`, or `manual_review`.
6. If executable, Redis job is created for controlled execution.
7. Worker calls execution gateway.
8. Execution gateway calls provider adapter.
9. execution_log is written.
10. service_record status is updated.
11. readback job is created if needed.
12. Multidimensional table views are updated: service board, recharge view, account view, audit view.
13. Telegram callback reports result with evidence.
```

## 7. Transaction Rules

核心事务规则：

- 创建 message 和 message audit 必须同事务。
- 创建 service draft 和 draft audit 必须同事务。
- 确认 draft、创建 service record、写 confirmation audit 必须同事务。
- 执行外部 provider 调用不能放在数据库事务里。
- 外部 provider 调用完成后必须以 execution result 事务写入 execution log。
- 幂等键命中时不得重复执行真实写入，只能返回已存在结果或进入人工复核。

## 8. Permission Rules

每个业务动作必须至少校验：

- actor 是否是系统用户。
- actor 是否绑定 Telegram identity。
- actor 是否在客户/账户 scope 内。
- actor 是否有动作权限。
- actor 是否有字段可见权限。
- agent 是否被允许读取相关 message、record、field。
- 当前 service state 是否允许该动作。

## 9. Error Handling

错误分层：

| Error Type | Behavior |
| --- | --- |
| validation_error | 返回 400，写 request log，不创建业务记录 |
| permission_denied | 返回 403，写 audit event |
| state_conflict | 返回 409，提示当前状态不可操作 |
| idempotency_hit | 返回已有记录或安全提示 |
| provider_unavailable | job retry，超过阈值后 failed safely |
| llm_parse_failed | draft 进入 needs_review，不自动执行 |
| readback_failed | 执行成功和余额回读分离展示 |

## 10. Observability

每条链路必须可追踪：

- `trace_id`: 从 Telegram update 到 Agent、job、service、execution log 贯穿。
- `job_id`: 每个异步任务唯一。
- `idempotency_key`: 防止重复写入。
- `agent_run_id`: 每次 LangGraph run 唯一。
- `llm_request_id`: 每次 OpenRouter 调用记录。
- `actor_id`: 人类或 agent。
- `source_message_id`: Telegram 原始消息引用。

## 11. Testing Strategy

文档阶段后的测试要求：

- Unit tests: service state machine、permission policy、idempotency。
- Integration tests: API + database transaction + queue enqueue。
- Agent tests: prompt input/output JSON schema、tool policy、failure fallback。
- Migration tests: Alembic upgrade/downgrade smoke test。
- Queue tests: retry、dead letter、worker idempotency。
- Security tests: field permission、agent permission、Telegram identity spoofing。

## 12. Acceptance Criteria

后端架构设计被认为可进入实施计划，必须满足：

- 技术栈明确。
- 模块边界明确。
- 业务写入只经过 service layer。
- 高权限 Agent 边界明确：可查库、可统计、可在人工确认后通过 execution ticket 执行。
- 事务和外部调用边界明确。
- 数据库、队列、Agent 文档都有对应专项文档。
- 第一阶段业务切片明确。
