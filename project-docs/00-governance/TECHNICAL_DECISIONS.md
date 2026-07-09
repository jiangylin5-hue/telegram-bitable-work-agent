# Technical Decisions

## Status

- Document status: active technical decision record
- Scope: 技术选型、替代方案、确认状态和变更规则
- Current Progress: 2026-07-10 Added Stage06 platform-pivot decision and backend-readiness evidence: the active product is a generic Feishu-like multidimensional table, no-code workspace and table-bound digital employee platform. Core records move toward typed field metadata plus JSONB values; advertising-agency workflows become templates/samples, not platform core. Real OpenRouter summarize/draft smoke, local PostgreSQL migration smoke and real Telegram backend entry smoke have evidence for the current non-UI backend pass.
- Current Progress Update: 2026-07-04 用户确认方案 A、OpenRouter、Agent 查库统计、人工确认后受控执行模型，以及 Stage 02 开发范围和 mock/sandbox 策略。

## TDR-001 Backend Language

- Status: accepted
- Decision: Python 3.12+
- Rationale:
  - Python 在 AI agent、LangGraph、数据处理、PostgreSQL 工具链方面生态成熟。
  - 与 FastAPI、SQLAlchemy、Alembic、Pydantic、Redis、OpenRouter SDK/HTTP client 搭配自然。
  - 适合快速写出可测试、可审计的业务服务层。
- Rejected alternatives:
  - Node.js/NestJS: Telegram 和实时任务开发方便，但 AI/数据生态不如 Python 主线集中。
  - Go: 性能好，但 Agent 编排生态和文档阶段开发速度不如 Python。

## TDR-002 Backend Framework

- Status: accepted
- Decision: FastAPI
- Rationale:
  - 类型友好，适合 Pydantic schema、OpenAPI、REST API。
  - 支持 async endpoint，适合 Telegram webhook、后台任务触发、长任务入队。
  - 社区成熟，易与 SQLAlchemy 2.x、Redis、鉴权中间件集成。

## TDR-003 ORM And Migration

- Status: accepted
- Decision: SQLAlchemy 2.x + Alembic
- Rationale:
  - SQLAlchemy 负责用 Python 模型表达 PostgreSQL 表、关系、事务和查询。
  - Alembic 负责数据库 schema 版本化迁移，保证本地、测试、生产环境结构一致。
  - 本项目有大量核心表、唯一约束、外键、敏感字段、审计关系和事务边界，需要成熟迁移工具。

## TDR-004 Database

- Status: accepted
- Decision: PostgreSQL + pgvector
- Rationale:
  - PostgreSQL 适合复杂关系数据、事务、审计、约束、JSONB、索引。
  - pgvector 可以在同一数据库内支持 SOP、历史服务记录、消息摘要、客户上下文的向量检索。
  - 第一阶段优先使用传统关系模型，向量检索只作为 Agent 辅助上下文，不作为业务事实来源。

## TDR-005 Queue And Worker

- Status: accepted with staged adoption
- Decision: Redis first, Temporal as future candidate
- Rationale:
  - 第一阶段需要消息入队、AI 草稿生成、日报生成、回传 Telegram、执行状态轮询等任务。
  - Redis 适合快速搭建 job queue、锁、幂等缓存和短期状态。
  - Temporal 更适合复杂长事务、补偿流程和强可恢复工作流，但第一阶段引入成本较高。
- Stage 1 default:
  - Redis Streams 或可靠任务队列。
  - 每个 job 必须有 `job_id`、`idempotency_key`、`trace_id`、`attempt_count`、`status`、`last_error`。

## TDR-006 Agent Orchestration

- Status: accepted
- Decision: LangGraph-first
- Rationale:
  - 本项目的 Agent 工作不是简单一问一答，而是有状态、多节点、可恢复、human-in-the-loop 的流程。
  - LangGraph 适合把 triage、draft、permission check、human confirmation、execution gate、reporting 拆成图节点。
  - 每个节点可以有明确 state、input、output、tool boundary 和失败处理。
- OpenRouter relationship:
  - LangGraph 负责编排。
  - OpenRouter 负责模型调用入口。
  - 业务工具调用必须经过后端 tool gateway，不允许 LLM 直接访问数据库或外部写入系统。

## TDR-007 LLM Provider

- Status: accepted
- Decision: OpenRouter-compatible API
- Rationale:
  - 可以通过统一 API 路由不同模型，避免把业务代码绑定到单一模型供应商。
  - 模型选择通过配置管理，例如按任务选择强推理模型、便宜摘要模型、结构化抽取模型。
  - 所有 prompt、模型名、温度、JSON schema、tool policy 必须可审计。
- Guardrail:
  - OpenRouter 只替代 LLM Provider，不替代权限、业务规则、数据库事务和执行审计。

## TDR-008 Telegram Integration

- Status: accepted
- Decision: Telegram Bot API + Webhook + Mini App
- Rationale:
  - Bot 负责群消息接入、提醒、审批入口和结果回传。
  - Webhook 负责可靠接收更新。
  - Mini App 负责承载复杂多维表格视图和确认操作。
- Guardrail:
  - Telegram user / group identity 只能作为身份线索，不能直接等同于系统权限。

## TDR-009 Agent Database And Execution Authority

- Status: accepted
- Decision: Agent 可以通过授权 Tool Gateway 访问数据库读模型、统计视图和检索能力；Agent 可以在人工确认后通过 `execution_ticket` 调用受控执行工具真实执行动作。
- Rationale:
  - 业务目标是让 Agent 成为数字员工，不是只生成草稿的聊天助手。
  - Agent 必须能查客户信息、账户库存、账户余额、客户消耗、服务记录、卡资源脱敏状态，才能完成统计、日报、分配和异常跟进。
  - 充值、绑卡、BM invite、卡台等动作在人工确认后应由系统自动执行，执行者可以是 Agent 调用受控工具，但工具必须受后端 service、权限、幂等和审计保护。
- Guardrail:
  - 禁止 LLM 裸连数据库。
  - 禁止 LLM 裸写 SQL。
  - 禁止 LLM 持有 Meta token、卡台 key、充值 provider key。
  - 禁止无人工确认和无 `execution_ticket` 的真实外部写入。
  - 所有高权限工具必须记录 audit event、tool call log、execution log。

## TDR-010 Mature Architecture Reuse

- Status: accepted
- Decision: 优先复用 GitHub 和官方生态中成熟的框架与架构模式。
- Reuse baseline:
  - LangGraph graph/state/checkpoint/human-in-the-loop/supervisor 模式。
  - OpenRouter OpenAI-compatible API 模式。
  - FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL + Redis。
- Rationale:
  - 项目复杂度来自业务编排、权限、状态、审计和执行安全，不应自研底层框架消耗精力。
  - 成熟框架让后续测试、扩展、排障和团队协作更稳。

## TDR-011 Stage 02 Scope And Integration Strategy

- Status: accepted
- Decision: Stage 02 采用 `Backend Kernel + Recharge + Account Inventory + Customer Reporting` 范围。
- Confirmed options:
  - Business scope: `A+B+C`，即充值闭环、账户库存、客户/公司日报都进入 Stage 02。
  - Telegram: first implementation uses mock webhook, not real Telegram Bot.
  - External providers: first implementation uses mock/sandbox adapters, not real Meta/BM/card/recharge provider writes.
  - Multi-tenancy: first implementation does not include `tenant_id`.
  - DB/queue consistency: first implementation uses outbox table.
- Rationale:
  - `A+B+C` 覆盖用户最关心的三个高价值业务面：充值执行、账户库存、每日客户消耗统计。
  - mock Telegram 和 mock provider 可以先验证业务状态机、权限、审计、outbox、Agent 工具边界，避免过早接触真实资金和账户操作。
  - 第一版不做 `tenant_id` 可以降低 schema、权限和测试复杂度。
  - outbox table 能保证数据库事务和异步任务投递一致，是后续真实 provider 接入的可靠基础。
- Implementation plan:
  - [Stage 02 Backend Kernel And Vertical Slices Implementation Plan](../08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md)。

## TDR-012 Stage06 Platform Pivot

- Status: accepted
- Decision: Stage06 active product direction is a generic Feishu-like multidimensional table, no-code workspace and table-bound digital employee platform.
- Data model direction:
  - Use generic `workspace -> base -> table -> field -> record -> view` platform resources.
  - Store generic record values in PostgreSQL JSONB.
  - Store field type, validation, relation, lookup, view and permission rules as metadata.
  - Treat vertical business tables as template-created ordinary tables unless a later document justifies a specialized backend table.
- Feishu/Lark relationship:
  - Imitate Feishu Base / Lark Base product grammar and `larksuite/cli` skill/capability organization.
  - Do not integrate Feishu/Lark APIs in Stage06.
  - Do not aim for Feishu API compatibility.
- Advertising-agency relationship:
  - Stage02 to Stage05 advertising workflows are retained as historical implementation evidence and optional official template input.
  - They are not the platform core.
- Digital employee decision:
  - Digital employees are configurable resources bound to bases, tables and views.
  - Effective scope is `agent_configured_scope ∩ caller_user_scope ∩ telegram_chat_scope`.
  - Write-like actions default to `record_change_drafts` and human confirmation before commit.
- Rationale:
  - The user confirmed the final product should resemble Feishu Base as a universal platform rather than a single advertising-agency tool.
  - Generic table metadata plus JSONB values lets users create and import arbitrary tables without a migration per business scenario.
  - Template-based vertical workflows preserve Stage02 to Stage05 work without letting it dominate the product.
- Reference:
  - [Stage 06 LarkSuite Benchmark Audit](../08-implementation/STAGE_06_LARKSUITE_BENCHMARK_AUDIT.md)
  - [Bitable Schema Blueprint](../03-modules/BITABLE_SCHEMA_BLUEPRINT.md)

## TDR-013 Stage06 Backend Readiness Before UI

- Status: accepted
- Decision: UI implementation is deferred until the backend readiness pass is complete and the user explicitly confirms a separate UI phase.
- Frontend target retained:
  - React + Vite + TypeScript + Tailwind + shadcn/ui + lucide-react.
  - Telegram Mini App first, desktop-browser-compatible route required.
- Current backend-readiness scope:
  - real LangGraph/OpenRouter digital employee invocation;
  - local PostgreSQL Alembic migration smoke against real PostgreSQL;
  - Telegram entry/backend smoke with test bot/allowlist when credentials are configured;
  - audit and safety readback.
- Rationale:
  - The user explicitly directed: "UI先不做，后端接好后，在等我确认后单独做".
  - Backend contracts and smoke evidence should stabilize before UI implementation depends on them.

## TDR-014 Stage06 Telegram Ecosystem Pilot Cut

- Status: accepted
- Decision: Stage06 pilot evidence should focus on Telegram ecosystem productivity, not an advertising-agency workflow.
- Required framing:
  - Telegram chats, mentions, tasks, notifications, table records, digital employee collaboration and audit readback are the pilot cut.
  - Advertising-agency examples remain optional templates/samples only.
  - No real business external systems are connected in Stage06.
- Rationale:
  - The product direction is a generic Telegram-first no-code workspace.
  - The user explicitly rejected using advertising operations as the Stage06 pilot entry.

## TDR-015 Stage06 Real LLM And Local PostgreSQL Smoke

- Status: accepted
- Decision: Stage06 backend readiness must include real LLM execution through LangGraph/OpenRouter and real PostgreSQL migration smoke against local PostgreSQL.
- LLM rules:
  - Deterministic backend tool gateway remains a test and fallback mode.
  - At least one real OpenRouter-compatible call must be possible when `OPENROUTER_API_KEY` is configured.
  - Real LLM outputs may answer, summarize or create drafts, but must not directly write records or bypass permissions.
- Database smoke rules:
  - Local PostgreSQL is acceptable for this backend-readiness pass.
  - SQLite or in-memory tests do not satisfy this smoke.
  - Local PostgreSQL smoke is not remote staging/production evidence.
- Rationale:
  - The user explicitly accepted local PostgreSQL for the fourth unresolved item.
  - The user explicitly required true LLM calls for the fifth unresolved item.
