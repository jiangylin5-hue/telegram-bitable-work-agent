# Technical Decisions

## Status

- Document status: active technical decision record
- Scope: 技术选型、替代方案、确认状态和变更规则
- Current Progress: 2026-07-10 Added Stage06 platform-pivot decision and backend-readiness evidence: the active product is a generic Feishu-like multidimensional table, no-code workspace and table-bound digital employee platform. Core records move toward typed field metadata plus JSONB values; advertising-agency workflows become templates/samples, not platform core. Real OpenRouter summarize/draft smoke, local PostgreSQL migration smoke and real Telegram backend entry smoke have evidence for the current non-UI backend pass.
- Current Progress Update: 2026-07-22 用户确认 Stage09 不新增 Docker 部署；P1/P2 改用原生 Ubuntu `systemd` 服务与服务器本地 PostgreSQL/Redis，保留既有 Docker Caddy 仅作为未迁移 Stage03 的历史 HTTPS ingress，不能替换或重启它。
- Current Progress Update: 2026-07-29 Stage12-D focused real embedding benchmark completed for both OpenRouter candidates. Remote BGE-M3 passed 3/3 rounds; remote E5 failed the frozen 20-second warm-up gate; local BGE-M3 remains unmeasured because its pinned 2.27 GB weight did not download. The user explicitly accepted TDR-018 and authorized the fixed `vector(1024)` implementation boundary; production activation and real-workspace external embedding remain separate gates.
- Current Progress Update: 2026-07-30 Stage12-F local technical gate passed. The non-superuser PostgreSQL test account continues to have no extension-administration authority; `postgres` provisioned pgvector once in the test database's durable `extensions` schema, while application migrations and tests continue as `ads_agent` through `search_path=public,extensions`. This is local test provisioning only and does not grant `ads_agent` superuser rights or authorize production migration.
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

## TDR-016 Stage08 E3 Safe Execution Adapter

- Status: accepted — user confirmed on 2026-07-22.
- Decision: Stage08 E3 may use a private, default-off safe-execution adapter around the existing ticket, Tool Gateway and record-change-draft services. It adds an internal transaction/savepoint boundary, common current-state locks, hash-only trace replay and a safe audit mode; it does not add a public API, schema migration, direct record write or confirmation capability.
- Privacy rule: E3 `AgentRun`, `OpsAuditEvent`, tool summary, outbox/log/API-safe projection must contain only status/action/count/code/hash/latency/presence. They must not contain query, answer, C3/D4 material, field key/value, record/draft/ticket UUID or provider response. Business-table primary keys and foreign keys remain normal PostgreSQL state and are not audit payloads.
- Draft intent rule: the process-local sealed intent may carry exactly one JSON-safe proposed field/value, but it is revalidated against the current record/table/field/actor/employee/source scope under the transaction boundary and never serialized.
- Consistency rule: reject/cancel/timeout/provider-shape/Gateway failure rolls back the E3 savepoint so no ticket, idempotency reservation, draft or internal audit orphan remains. Same idempotency key revalidates current scope and replays the original safe outcome; different keys do not infer identity from a record-wide pending-draft count.
- Reference: `project-docs/08-implementation/decisions/STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md`.

- Terminal mapping update (2026-07-22): user confirmed a `degraded` E1 terminal status only for unavailable analysis providers. Invalid/forged provider output remains `failed`; no write-capable action is allowed from `degraded`.

## TDR-017 Stage09 Native Server Deployment And Local Database

- Status: accepted — user confirmed on 2026-07-22.
- Decision: Stage09 P1/P2 不创建新的 Docker Compose、容器或 Docker 数据卷。新 Stage09 服务使用专用 Linux 用户、Python virtualenv 和 `systemd` 运行；PostgreSQL、Redis 与 pgvector 使用目标 Ubuntu 服务器上的原生服务与本机 socket/loopback。当前历史 Stage03 Docker/Caddy 保持运行且不被 Stage09 替换、重启或迁移。
- Ingress transition: 在 Stage09 还与历史 Stage03 共用该服务器时，既有 Caddy 仅可在已授权的独立 hostname 下新增一个反向代理 host；它把流量转给本机受限端口的原生 Stage09 Web/API。它不是 Stage09 的新 Docker 依赖，也不能改动 Stage03 既有 host、端口、容器、数据库或 Redis。完全移除现有 Docker ingress 是一项独立迁移，不与 P1 合并。
- Database decision: P1/P2 默认使用服务器本地 PostgreSQL（匹配的原生 pgvector extension）和本地 Redis，不购买托管数据库。数据库和 Redis 不对公网监听；应用通过 Unix socket 或 `127.0.0.1` 连接。P3 前必须具备异机加密备份、定期恢复演练、磁盘/连接/复制或恢复告警。达到任一触发条件后再评估托管 PostgreSQL：多节点或高可用目标、业务数据不能接受单机/单可用区故障、恢复目标需要小于当前实测恢复时间、运维无法稳定完成备份恢复，或数据库负载超出单机容量/SLO。
- Redis account boundary: P1 Redis 使用独立 `stage09-redis:stage09-redis-socket`，固定为私有 Unix socket；应用 `stage09-p1` 只作为 socket 补充组成员，不拥有 Redis data dir，Redis unit 不读取 application runtime env。
- Rationale:
  - 当前服务器仍承载历史 Stage03 Docker 服务；在同一个变更窗口内同时迁移旧 ingress 和上线 Stage09 会扩大故障域。
  - P1/P2 是空数据、受控验证和有限真实 smoke，服务器本地 PostgreSQL 的成本、延迟和运维复杂度最低。
  - pgvector 是 PostgreSQL 扩展，可随匹配 PostgreSQL 版本原生安装并在每个新库中显式 `CREATE EXTENSION vector`；不需要先采购外部向量数据库。
  - 服务器本地数据库不是长期高可用方案，因此用异机备份与恢复演练作为扩展/采购前的硬门。
- Guardrails:
  - 不复用、升级、读取或迁移 Stage03 Docker PostgreSQL、Redis、volume、env 或网络。
  - P1 worker/outbox unit 仅允许各自在唯一 `ExecStart` 行精确使用
    `app.workers.stage03_runtime` 或
    `app.workers.stage03_outbox_bridge_runtime`。这是保留的 Python **代码兼容名**，
    不是 Stage03 操作依赖；它们只能使用 N1 已验证的 P1 runtime 和 P1 原生
    PostgreSQL/Redis，不能连接、读取、迁移或复用 Stage03 Docker 资源。除此两个
    精确入口外拒绝所有 `stage03` 文本，并拒绝所有 Stage03 目录、systemd service、
    Docker service/container/network/volume/env 变量以及 Stage07 标记。
  - 不创建 `deploy/stage09-p1/compose.yml`；此前仅处于本地计划状态的 Docker P1 资产未落地，已明确废止。
  - P1 全程保持 `TELEGRAM_SEND_MODE=dry_run`、`LLM_ENABLED=false`、`AGENT_WORKFLOW_MODE=fake`、`PROVIDER_MODE=disabled`，所有 Telegram allowlist 为空。
  - 不因本决定自动授权远程安装、数据库初始化、Caddy 改动、迁移或 Telegram 写入；这些仍按 Stage09 分层门禁逐项执行。
  - 无秘密 Nginx fixture 在缺少本地 Nginx binary 时必须报告 `SKIPPED`，不得声称
    `nginx -t` 已通过；目标服务器的真实 `nginx -t` 仍由 P0a/P1-B 环境证据门承担。
- Reference: `project-docs/08-implementation/STAGE_09_NATIVE_SERVER_DEPLOYMENT_PLAN.md`.

## TDR-018 Stage12-D Fixed Embedding Profile

- Status: accepted — user explicitly confirmed on 2026-07-29.
- Decision: use `stage12.openrouter-bge-m3-v1` / `baai/bge-m3-20251117`, 1024 dimensions, L2 normalization, cosine distance, batch size 64 and maximum input 8192 for the Stage12-D fixed vector schema.
- Provider boundary: OpenRouter requests require `data_collection=deny`, `zdr=true`, `allow_fallbacks=false`, exact catalog revision validation and a 20-second request timeout. Synthetic benchmark permission does not authorize real workspace data to leave the machine.
- Evidence: remote BGE-M3 completed 3/3 measured rounds after warm-up with Recall@20 `1.0`, MRR@20 `0.9583`, P95 `3.93s` and zero forbidden candidates. Remote E5 failed the 20-second warm-up hard gate. Local BGE-M3 runtime was prepared, but the pinned 2.27 GB weight download stalled, so it has no measured result and cannot be ranked.
- Gate: migration `0035`, models and default-off provider configuration are now authorized for Stage12-D implementation. This decision does not authorize deployment, production activation or sending real workspace data to OpenRouter. If local data residency becomes mandatory, resume and complete the local BGE-M3 benchmark under a new confirmed decision.
- Reference: `project-docs/08-implementation/evidence/stage12-d-embedding-profile-benchmark-2026-07-29.md`.

## TDR-019 Stage12-D Two-Stage Authorized Projection Outbox

- Status: accepted — user explicitly confirmed on 2026-07-30.
- Problem: a Stage06 record/schema/link mutation knows which durable resource and version changed, but it does not know the future effective retrieval authority `agent scope ∩ caller scope ∩ chat/view scope`. It therefore cannot safely compute caller-specific canonical text, `content_hash`, `visibility_profile_hash` or `scope_hash` inside the mutation transaction.
- Proposed decision: split invalidation and authorized projection into two internal outbox stages.
  1. The Stage06 mutation transaction emits `stage12.retrieval_source.changed` with stable resource references, source version and a hashed trace reference only. It never includes field values, canonical text, field IDs, vectors or caller-specific hashes.
  2. An authorization-aware indexing coordinator expands the reference over currently materialized or explicitly registered effective visibility profiles, re-reads each current authorized source and emits one existing `stage12.retrieval_projection.requested` event per validated projection.
  3. A missing visibility profile is built lazily from a current authorized request; it must not fall back to a broader profile. Until the profile is ready, structured Stage12-C facts or current-authority lexical retrieval may serve the request, but a broader vector may not be reused.
  4. Permission contraction and deletion synchronously revoke affected Stage12 source/chunk rows before asynchronous expansion or vector cleanup. Ordinary content updates retain the previous active version for rollback, while retrieval must revalidate current record/source version and authority before evidence release.
- Idempotency: mutation identity is `(workspace_id, source_type, source_identity, source_version, mutation_kind)`; projection identity remains `(workspace_id, source_type, source_identity, source_version, visibility_profile_hash, content_hash)`.
- Rejected alternatives:
  - Build a maximum-authority projection in the mutation transaction: derived-sensitive-data leak risk.
  - Build only the mutating actor's projection: incomplete for other legitimate authority profiles and incorrect for system mutations.
  - Put canonical text or field IDs in the generic outbox event: violates the Stage12-D reference-only and data-minimization boundary.
- Compatibility: internal-only outbox contract refinement; no public HTTP/SSE API, production activation, deployment, external send or business-write authority change.
- Implementation gate: the new internal event type and Stage06 mutation integration are authorized for local Stage12-D implementation and verification. This does not authorize deployment, production activation, real-workspace external embedding, public API/SSE changes or broader write/send authority. Task6 may be marked complete only after its documented RED/GREEN, real PostgreSQL and permission-contraction acceptance evidence passes.

## TDR-020 Stage12 Architecture Correction V2.1

- Status: accepted — user explicitly confirmed on 2026-07-30 after the comprehensive architecture audit.
- Decision: implement the complete nine-package correction defined by `STAGE_12_ARCHITECTURE_CORRECTION_SOURCE_OF_TRUTH.md` before any Stage12 integrated acceptance claim.
- Contract decisions:
  - Evaluation separates result identities, supporting evidence and independently produced canonical typed facts; recovery is applicability-scoped.
  - Runtime and evaluation share one authorized Entity Linker; fixture injection and business-prefix entity typing are prohibited.
  - Valid same-table relation edges are supported; relation permission, cycle and budget checks remain mandatory.
  - Stage12 uses a versioned explicit Digital Employee readable/writable field policy and fails closed when absent; V1 is unchanged until explicit migration.
  - Public Action admission adds backward-compatible `requested_action=auto`; final blind Cases omit action, target, field and value hints.
  - Retrieval materialization, typed Specialist workers, validated-fact-only ClaimGraph/Composer and the A–F isolated runner become required runtime components rather than test-only adapters.
- Acceptance decisions:
  - final answer quality is the primary product acceptance criterion; component metrics are diagnostic only and cannot compensate for a wrong, incomplete, unsupported or instruction-misaligned final answer;
  - real Redis duplicate/pending/recovery/ack-once evidence is mandatory;
  - human Gold approval remains distinct from agent audit;
  - final acceptance is exactly three real Provider rounds over all 48 Cases with mean, worst round, population variance, safety failures and P95.
- Guardrails: local isolated/synthetic implementation only. No production migration, activation, real-workspace external embedding/Provider data, confirmed Action, business write, notification delivery or Telegram send is authorized.
- References:
  - `project-docs/08-implementation/STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md`
  - `project-docs/08-implementation/STAGE_12_ARCHITECTURE_CORRECTION_SOURCE_OF_TRUTH.md`
  - `docs/superpowers/plans/2026-07-30-stage12-architecture-correction.md`

## TDR-021 Stage12 Retrieval Registration And Relation Edge Identity

- Status: accepted for bounded local implementation; explicitly confirmed by the user on 2026-07-30
- Date: 2026-07-30
- Trigger: Task 5 runtime wiring proved that the current component contracts cannot materialize a complete, authorization-reconstructable Relation Index.
- Confirmed problems:
  1. `uq_s12_relation_version_visibility` omits `source_record_id` and `target_record_id`. Because `relation_id` identifies the linked-record field, two distinct edges under that field with equal endpoint versions and visibility hash collide. The table therefore cannot persist an ordinary multi-record relation.
  2. `stage12.retrieval_source.changed` is correctly reference-only, but no durable authorized-projection registration exists. An asynchronous worker cannot reconstruct `employee_id`, actor identity/current role or chat/view scope from the irreversible `scope_hash`.
  3. `AuthorizedSchemaSnapshot.scope_hash` proves schema/employee/actor/field-policy scope but does not bind `AuthorizedQueryContext.scope_view_ids` or `allow_whole_table`. Runtime reread currently prevents candidate release outside the current view, but persisted projection identity is not a complete proof of effective `agent ∩ caller ∩ chat/view` authority.
- Recommended bounded decision:
  1. Add migration `0038` replacing the relation uniqueness columns with `workspace_id, relation_id, source_record_id, target_record_id, direction, source_version, target_version, visibility_profile_hash, scope_hash`.
  2. Add a durable, expiring, revocable Stage12 retrieval-scope registration containing only resource/identity references and hashes required for an authorized reread: workspace/base/employee, actor identity, current view IDs or whole-table marker, schema/field-policy proof, effective retrieval-scope hash, lifecycle and timestamps. It must not store canonical text, record values, credentials or Provider payloads.
  3. Derive the effective retrieval-scope hash from the existing schema scope plus sorted current view IDs and the whole-table marker. Bind that proof into projection/index/request/release checks without changing V1 execution.
  4. A current authorized request creates or refreshes the registration. The coordinator fans out only through active registrations, reconstructs the current actor role from platform membership, rebuilds the current snapshot/context and rejects any scope/hash drift before reading source values.
  5. Permission, employee, table, view or field-policy contraction revokes affected source/chunk/relation rows and registrations before rebuild. No broader profile fallback is allowed.
- Rejected alternatives:
  - Process-local callback registry: unavailable to a separate worker and lost on restart.
  - Guess actor/employee from `scope_hash`: impossible and unsafe.
  - Enumerate every user/employee/chat scope on each mutation: unbounded and cannot reconstruct chat/view authority reliably.
  - Synchronous request-time indexing without the outbox: violates TDR-019 durability and failure isolation.
  - Encode endpoint IDs into `relation_id`: breaks the stable relation-definition identity and path audit contract.
- Implementation boundary: use reversible migration `0038` for relation-edge identity and a separate reversible migration `0039` for retrieval-scope registration. Task 5 remains `in_progress` until focused and real disposable PostgreSQL/pgvector evidence passes. This decision does not authorize Stage12 activation, production migration, real-workspace external embedding, business writes or sends.

## TDR-022 Stage12 Retrieval Registration Bootstrap And Worker Runtime

- Status: accepted for local implementation; explicitly confirmed by the user on 2026-07-30
- Date: 2026-07-30
- Trigger: TDR-021 RED/GREEN implementation proved that an active durable registration can safely rebuild a source mutation and that queued projection events cannot reactivate a contracted scope. Final end-to-end review then found that a first registration has no durable catch-up path for sources whose mutation events were already consumed before the registration existed. The registered handler factory also has no allowlist-filtered SQL worker loop.
- Confirmed failure mode:
  1. Existing records/schema may predate the registration.
  2. Their reference-only `stage12.retrieval_source.changed` events may already be `processed/discarded` because no authorized registration existed then.
  3. Creating the registration does not replay those events.
  4. If the data does not mutate again, Retrieval V2 remains empty indefinitely even though the route, registration and worker callbacks are individually valid.
- Recommended bounded decision:
  1. Add internal reference-only event `stage12.retrieval_scope.bootstrap_requested`, emitted only when a new registration generation is created, not on an idempotent refresh.
  2. The payload may contain only `workspace_id`, `registration_id`, a bounded resource-reference cursor, `page_size` and `trace_id`; it must not contain canonical text, record values, credentials, Provider payloads or Gold/expected answers.
  3. The worker revalidates the active, unexpired registration and current membership/employee/view/field-policy/schema proof before every page. It enumerates at most `200` current authorized schema/record/long-field source references per page, emits existing `stage12.retrieval_projection.requested` events, synchronizes current relation edges and emits a continuation bootstrap event when more sources remain.
  4. A revoked, expired or drifted registration discards the current page and all stale continuations. Permission contraction continues to revoke source/chunk/relation rows before any rebuild.
  5. Add a default-off `retrieval_v2_outbox_runtime` entry that queries only Stage12 Retrieval event types and only `RETRIEVAL_V2_WORKSPACE_ALLOWLIST` workspaces. It must not consume or dead-letter unrelated application Outbox rows. No deployment/process activation is included.
- Rejected alternatives:
  - Synchronously enumerate and enqueue every source inside the user request: unbounded request latency and transaction size.
  - Wait for the next business mutation: leaves stable existing data permanently unindexed.
  - Reset or replay every historical source-change event: broad, duplicate-prone and not registration-scoped.
  - Let a generic Outbox worker consume all event types with missing handlers: it can dead-letter unrelated product events.
- Gate: local RED/GREEN implementation is authorized. Task 5 remains `in_progress` until bootstrap catch-up, filtered worker runtime and requirement-level regression evidence pass; no Stage12 production activation is authorized.
- Implementation evidence: Task 5 completed locally on 2026-07-30. New-registration-only bootstrap, page/continuation authority revalidation, stale-continuation discard and query-level event/workspace filtering pass unit and real disposable PostgreSQL evidence. The runtime remains default-off and no deployment/activation is authorized. See `project-docs/08-implementation/evidence/stage12-task5-retrieval-runtime-2026-07-30.md`.
