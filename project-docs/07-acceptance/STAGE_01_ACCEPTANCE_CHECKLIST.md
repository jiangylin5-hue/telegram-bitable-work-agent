# Stage 01 Acceptance Checklist

## Status

- Document status: acceptance draft
- Scope: 顶层文档设计阶段验收
- Current Progress: 2026-07-04 完成后端开发前文档设计验收清单，用户已确认 Stage 02 范围和 mock/sandbox 策略。

## 1. Stage Goal

Stage 01 的目标是完成 Telegram 多维表格和工作智能体后端开发前的顶层文档设计。

本阶段不写业务代码，不创建数据库迁移，不接入真实 Telegram/Meta/卡台/充值 provider。

## 2. Required Documents

| Document | Required | Status |
| --- | --- | --- |
| `AGENTS.md` | yes | drafted |
| `IMPLEMENTATION_SOURCE_OF_TRUTH.md` | yes | drafted |
| `TECHNICAL_DECISIONS.md` | yes | drafted |
| `SDD_BACKEND_ARCHITECTURE.md` | yes | drafted |
| `MULTI_AGENT_ORCHESTRATION.md` | yes | drafted |
| `BITABLE_SCHEMA_BLUEPRINT.md` | yes | drafted |
| `BUSINESS_SCENARIOS_INDEX.md` | yes | drafted |
| Complex scenario documents | yes | drafted |
| Module documents | yes | drafted |
| Agent documents | yes | drafted |
| `POSTGRES_DATABASE_DESIGN.md` | yes | drafted |
| `PERMISSION_AND_SECURITY_MODEL.md` | yes | drafted |
| `REDIS_QUEUE_AND_WORKER_DESIGN.md` | yes | drafted |

## 3. Technical Acceptance

- Backend language confirmed as Python 3.12+。
- Backend framework confirmed as FastAPI。
- ORM confirmed as SQLAlchemy 2.x。
- Migration confirmed as Alembic。
- Database confirmed as PostgreSQL。
- Vector search confirmed as pgvector。
- Queue/cache confirmed as Redis。
- Agent orchestration confirmed as LangGraph-first。
- LLM Provider confirmed as OpenRouter-compatible API。
- Telegram integration confirmed as Bot API + Webhook + Mini App。

## 4. Business Acceptance

- 核心业务场景有索引。
- 多维表格总蓝图覆盖所有已确认业务场景。
- 每个业务场景都有 Bitable endpoint：table、field、linked record、view、automation。
- 每个业务场景都能在 `BITABLE_SCHEMA_BLUEPRINT.md` 中找到 table、view、automation 和 Agent landing point。
- 充值闭环有单独文档。
- 账户库存管理有单独文档。
- 分户/BM invite 有单独文档。
- 卡台/绑卡有单独文档。
- 客户日报和公司日报有单独文档。
- 消耗风险统计有单独文档。
- 每个场景写明做什么、不做什么、数据处理、权限校验、LLM 使用和失败处理。

## 5. Agent Acceptance

- 每个 Agent 有独立文档。
- 每个 Agent 说明职责边界。
- 每个 Agent 说明 context、memory、state、search/retrieval state、LLM、tools、skills、禁止行为。
- 每个 Agent 说明读取哪些多维表格 table/view，更新哪些 record/status，触发哪些 automation/job，输出落到哪个 view。
- 每个 Agent 的出发点和落脚点都能在 `BITABLE_SCHEMA_BLUEPRINT.md` 中找到。
- Agent 高权限模型已明确：可通过授权工具查库和统计，可在人工确认后凭 `execution_ticket` 执行真实动作。
- OpenRouter 和 LangGraph 的职责区分清楚。

## 6. Data Acceptance

- PostgreSQL 核心表清楚。
- 表关系清楚。
- 唯一约束清楚。
- 敏感字段清楚。
- 事务边界清楚。
- pgvector 的用途和限制清楚。

## 7. Queue Acceptance

- Redis job envelope 清楚。
- job id、trace id、idempotency key 清楚。
- retry policy 清楚。
- dead letter 清楚。
- worker 边界清楚。

## 8. Safety Acceptance

- 所有 workflow 终点必须是多维表格记录、状态、视图、自动化、执行日志或审计事件。
- 不允许只停留在 Telegram 聊天、临时 Agent memory、未落表 JSON 或口头结论。
- Agent 不裸连数据库、不裸调 provider。
- Agent 可以在 human confirmation 后凭 `execution_ticket` 执行充值、分户、绑卡、卡台等动作。
- Telegram 身份不等于系统权限。
- execution log 是成功声明前提。
- 充值执行和余额回读分离。
- raw payment credential 不保存。
- 测试验收必须逐条对照文档，不允许口头宣称已完成。

## 9. Stage 02 Decisions

以下原 review items 已由用户以 `ABC A A A A` 确认：

- Stage 02 不只做充值闭环，而是覆盖充值闭环、账户库存、客户/公司日报三个切片。
- Telegram 第一版先 mock webhook。
- 外部 provider 第一版先 sandbox/mock adapter。
- 第一版不做多租户 `tenant_id`。
- 第一版采用 outbox table 保证 DB 与 Redis enqueue 一致。

Stage 02 实现前仍需处理：

- LLM prompt 保存策略：Stage 02 默认只保存脱敏摘要，完整 prompt 存储留到后续安全评审。
- 是否初始化/修复 Git 仓库。Stage 02 开发前必须处理，因为当前 `git status` 不可用。
