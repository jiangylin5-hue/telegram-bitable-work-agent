# Stage 05 Source Of Truth

## Status

- Document status: active stage source of truth draft
- Scope: Stage 05 以真实 OpenRouter + LangGraph Supervisor / 子 Agent 为主线，把 Stage 04 `intent_ready` 升级为多意图 Agent 草稿闭环，并补入账户库存异常管理边界。
- Current Progress: 2026-07-07 Stage05 文档包草稿已完成；随后根据用户补充，将飞书官方 `larksuite/cli` Skills 作为高相似度结构参考写入 Agent skills/capabilities 模块，并明确 Skills 只保留文档说明，不进入 Stage05 当前实施和验收阻塞项。Stage05 本地/non-staging 主链路已完成到 Task12 前置 readiness：runtime config、AgentRun evidence、Router schema、LangGraph Supervisor、子 Draft Agents、多 draft、API + Bitable-like views、Account Inventory Agent、confirmation/no-op、customer_reply linked send request、deployment config gate 和 redacted runtime summary command 均有本地证据。当前范围仍为 Agent 能力优先型：真实 OpenRouter 主路径、LangGraph Supervisor + 子 Agent、多意图、多 draft、API + Bitable-like views、Tencent Cloud staging；Account Inventory Agent 不生产账户，只负责账户分发、库存管理和异常处理；高确定性风控/封号可自动标记异常状态，但不自动替换分发账户。

## 1. Stage Goal

Implementation Update: 2026-07-07 local code implementation has completed through Phase 05.6 Task11 Local Acceptance Audit, plus Task12 local staging-contract preflight, deployment config gate and redacted runtime summary command. Local/non-staging acceptance evidence includes focused Stage05 tests 82 passed / 190 deselected, full backend suite 255 passed / 17 skipped, staging contract 5 passed, scope guard 4 passed, runtime summary 3 passed, Alembic offline SQL, secret scan and whitespace check. The local staging-contract preflight and runtime summary command passed without external calls. Remaining Stage05 work includes real Tencent Cloud staging rehearsal and safety close, both requiring explicit approval before any staging env change, real OpenRouter call or real Telegram send.

Task12 Approval Update: 2026-07-08 User explicitly approved the bounded `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` action subset at `2026-07-08 00:15:10 +08:00`. The approval allows staging-only deployment, Stage05 migration, server-side real OpenRouter, temporary restricted Telegram private test-chat send, business no-op evidence, controlled account exception evidence, redacted evidence capture and safety close. It still forbids production, real customer chat, customer groups, provider writes, funds movement, account production, automatic replacement and secret/raw allowlist recording.

Stage 05 的目标是把 Stage 04 已验收的真实 Telegram 入站和 `intent_ready` placeholder 升级为真实 Agent 工作流：

```text
real Telegram message
-> bound telegram_inbox
-> intent_ready
-> Operations Supervisor graph
-> Message Intake Router
-> selected child agents
-> service_drafts / account status events / manual_review
-> human confirmation
-> allowlisted staging test send or no-op service evidence
-> Bitable-like views + audit + agent run evidence
```

Stage 05 不是生产上线阶段，也不是真实业务执行阶段。它必须证明：

- 真实 OpenRouter 能在 staging 中作为主路径解析中英混合 Telegram 业务消息。
- LangGraph-first 的 Supervisor / child agent 雏形能稳定把一条消息拆成多个业务意图。
- 多个子 Agent 能分别生成候选草稿或库存异常事件，并把结果落回多维表格记录、状态、视图和审计。
- Account Inventory Agent 能管理不稳定账户库存，识别明确风控、封号、不可用等高危状态，并通过后端 service 自动标记异常，但不自动替换分发。
- `customer_reply` 草稿经人工确认后，只能发送到 staging allowlisted private test chat。
- `recharge`、`card_binding`、`bm_invite`、`account_assignment` 等业务草稿经人工确认后，只生成 service record 或 no-op execution evidence，不触发真实 provider。

任何仅停留在 LLM 返回 JSON、LangGraph 内存状态、Telegram 对话、未落表日志或未审计工具调用里的结果，都不算 Stage 05 完成。

## 2. Confirmed User Choices

| Topic | User Decision | Stage 05 Meaning |
| --- | --- | --- |
| 后端方向 | 系统架构与后端阶段 | 继续沿用 Python/FastAPI/PostgreSQL/Redis 后端主线 |
| 第一闭环 | Agent 工作流 + Telegram 入库 | Stage04 入站后接真实 Agent |
| 主业务场景 | 客户消息识别与服务草稿 + 智能分拣 | 从 Telegram 客户消息生成业务草稿和回复草稿 |
| 交付深度 | 文档 + 后端骨架 + 可运行 MVP 闭环 | 先写完整 Stage05 文档，再进入代码实施 |
| 草稿类型 | `customer_reply` + `recharge` + `card_binding` + `bm_invite` | 第一批业务 Agent 直接贴近广告代理核心操作，但不执行真实外部动作 |
| LLM | 真实 OpenRouter 主路径 | 本地可 fake，staging 必须真实 OpenRouter 验收 |
| LangGraph | Supervisor + 子 Agent 雏形 | 不只做单 service 调 LLM |
| 客户回复发送 | staging allowlisted test chat 真实发送 | 不允许真实客户 chat 或客户群发送 |
| UI | 只做 API + Bitable-like views | 不做 Web UI / Mini App |
| 验收环境 | 本地测试 + staging 真实 OpenRouter + allowlisted Telegram test send | 沿用 Stage04 Tencent Cloud staging |
| 多意图 | Supervisor 自动分派多个子 Agent，各自生成候选 draft | 一条消息可产生多个 draft candidates |
| 缺字段和低置信度 | 组合策略 | 意图明确但缺字段生成 `needs_more_info`；意图不明/高风险进 `manual_review` |
| Retrieval | 不引入 pgvector / RAG | 只用结构化数据库和最近消息上下文，后续迭代升级 |
| 人工确认 | `customer_reply` 可发 allowlisted test chat；业务 draft 只生成 service/no-op evidence | 不创建真实外部执行 |
| Views | 业务处理优先 | `service_drafts`、`agent_review_queue`、`pending_confirmation`、`customer_reply_send_requests` 是主视图 |
| LLM 证据 | 脱敏摘要 + 结构化结果 | 不长期保存完整 prompt 和完整 raw response 到运营视图 |
| LLM 成本 | 只记录成本字段 | 记录 model/token/cost/latency，不做每日预算和复杂限流 |
| Staging | 沿用 Stage04 Tencent Cloud staging | 复用 webhook、PostgreSQL、Redis、Caddy、Bot |
| 生产上线 | 不纳入 Stage05 | 生产发布另开 Stage06 |
| 验收消息 | 中英混合 + 业务缩写 | 覆盖账号、金额、BM、卡、充值、客户回复等真实聊天形态 |
| 总体推进 | Agent 能力优先型 | 强化多意图、多子 Agent、真实 LLM 输出和复杂样例 |
| 账户库存 Agent | 不生产账户，只分发和管理库存 | 账户生产由人或其他系统负责，Agent 不创建生产账户 |
| 账户异常 | 明确高危可自动标记 | 高确定性风控/封号可自动改状态并审计 |
| 客户替换账户 | 只标记异常，不自动推荐、预留或替换 | 替换账户进入人工处理或后续阶段 |

## 3. In Scope

Stage 05 必做：

- Stage 05 文档包、模块文档、验收标准和 runbook。
- `langgraph` 依赖和 Supervisor graph 雏形。
- `Operations Supervisor` 调度逻辑。
- `Message Intake Router` 真实 OpenRouter 多意图识别。
- `Recharge Draft Agent` 生成 `recharge` draft。
- `Card Binding Draft Agent` 生成 `card_binding` draft。
- `BM Invite Draft Agent` 生成 `bm_invite` draft。
- `Customer Reply Draft Agent` 生成 `customer_reply` draft。
- `Account Inventory Agent` 管理账户分发、库存状态和高危异常标记。
- 一条 Telegram 消息生成多个 draft candidates。
- 意图明确但缺字段时创建 `needs_more_info` draft。
- 意图不明、冲突、风险高时进入 `manual_review` 或 `agent_review_queue`。
- 明确风控、封号、不可用等高确定性账户异常自动标记为 `blocked`、`disabled` 或 `risk_controlled`，并写 `account_status_events` 和 `ops_audit_events`。
- 账户异常只标记，不自动推荐替代账户、不自动 reserve、不自动重新分配。
- `service_drafts` API 支持过滤、确认、拒绝、请求更多信息、升级人工复核。
- `customer_reply` 确认后复用受控 Telegram send request，只发 staging allowlisted private test chat。
- 业务 draft 确认后创建 `service_records` 或 no-op `execution_logs` evidence，不调用 provider。
- `agent_runs` 保存脱敏摘要、结构化输出、模型元数据、usage/cost/latency、错误码和 draft ids。
- 保留 Agent skills/capabilities 文档说明，结构上高度参考飞书官方 `larksuite/cli` Skills 的 use/non-use、权限、安全门禁、错误恢复和 reference 索引模式；但 Stage05 主链路验收前不实现 runtime registry、不新增 capability tests、不作为验收阻塞项。
- Bitable-like views：`service_drafts`、`agent_review_queue`、`pending_confirmation`、`customer_reply_send_requests`、增强 `telegram_inbox` 和 `account_inventory`。
- 本地自动化测试和 Stage03/Stage04 回归。
- Tencent Cloud staging 真实 OpenRouter + allowlisted Telegram test send 验收。
- Staging 验收结束后的安全关闭。

## 4. Out Of Scope

Stage 05 不做：

- Web UI。
- Telegram Mini App。
- pgvector / RAG / SOP 向量检索。
- 生产上线准备和生产切换。
- 真实客户 chat 发送。
- 客户群发送。
- 自动替换账户、自动预留账户、自动重新分发账户。
- 账户生产、账户导入和生产批次自动创建。
- Meta / BM / 卡台 / 充值 provider 写入。
- 资金动作。
- 完整 execution_ticket 生产执行框架。
- Stage05 主链路验收前的 Agent skills/capabilities runtime registry、动态 skill 系统或 capability 测试；该项保留文档说明，待 Stage05 做完并验收检查后单独纳入。
- 模型 fallback、预算告警、每日/每客户 LLM 上限。
- 多租户 `tenant_id`。
- 高并发压测、HA、备份/PITR 和生产监控。

## 5. Bitable Endpoint Rule

Stage 05 所有 workflow 必须落回多维表格记录、状态、视图、自动化或审计事件。

| Workflow | Bitable Endpoint |
| --- | --- |
| Router 多意图识别 | `agent_runs.output_summary`、`messages.intent_status`、`ops_audit_events` |
| 生成充值草稿 | `service_drafts.draft_type = recharge` |
| 生成绑卡草稿 | `service_drafts.draft_type = card_binding` |
| 生成 BM invite 草稿 | `service_drafts.draft_type = bm_invite` |
| 生成客户回复草稿 | `service_drafts.draft_type = customer_reply` |
| 账户分发草稿 | `service_drafts.draft_type = account_assignment`，仅候选，不自动分发 |
| 高危账户自动标记 | `account_inventory.inventory_status` + `account_status_events` + audit |
| 低置信度或风险消息 | `agent_review_queue` view，来源为 message/draft/agent run 状态 |
| 缺字段草稿 | `service_drafts.status = needs_more_info` + `missing_fields` |
| 待确认草稿 | `pending_confirmation` view |
| 客户回复确认 | `telegram_send_requests` 关联 `customer_reply` draft |
| 客户回复发送成功/失败 | `customer_reply_send_requests` view + `telegram_send_requests.status` + audit |
| 业务 draft 确认 | `service_records` 或 no-op `execution_logs` evidence |
| OpenRouter 调用证据 | `agent_runs` 中的脱敏摘要、结构化输出、usage/cost/latency |

## 6. Source Order

Stage 05 执行优先级：

1. 用户当前明确指令。
2. `AGENTS.md`。
3. 本文件。
4. [Stage 05 Implementation Plan](STAGE_05_IMPLEMENTATION_PLAN.md)。
5. [Stage 05 SDD](STAGE_05_SDD.md)。
6. [Stage 05 BDD](STAGE_05_BDD.md)。
7. [Stage 05 Acceptance Checklist](STAGE_05_ACCEPTANCE_CHECKLIST.md)。
8. [Stage 05 Module Index](STAGE_05_MODULE_INDEX.md)。
9. [Stage 05 API Contract](STAGE_05_API_CONTRACT.md)。
10. [Stage 05 Database And Migration Design](STAGE_05_DATABASE_AND_MIGRATION_DESIGN.md)。
11. [Stage 05 Security And Permission Design](STAGE_05_SECURITY_AND_PERMISSION_DESIGN.md)。
12. [Stage 05 Test Plan](STAGE_05_TEST_PLAN.md)。
13. [Stage 05 Operations Runbook](STAGE_05_OPERATIONS_RUNBOOK.md)。
14. [Stage 05 Risk Register](STAGE_05_RISK_REGISTER.md)。
15. Stage 05 module docs under `modules/`。
16. Stage 04 final acceptance docs and existing code。
17. Architecture, Agent, database, permission, queue and product scenario docs。

## 7. Entry Gate

进入 Stage 05 代码开发前必须满足：

- Stage 04 已完成最终验收。
- Stage 05 文档包通过用户 review。
- 用户明确确认从文档阶段进入代码实施。
- 不把 OpenRouter key、Telegram Bot token、webhook secret、数据库密码、Redis 密码、test chat allowlist 写入 git 或文档。
- 任何 Tencent Cloud staging env 修改、真实 OpenRouter 调用、Telegram `sendMessage` 真实发送都必须在对应子阶段前再次确认。
- provider 仍保持 disabled。
- `customer_reply` 真实发送只能指向 allowlisted private test chat。

## 8. Exit Gate

Stage 05 完成时必须证明：

- 本地完整 backend suite 通过，或未运行项有明确原因。
- Stage05 focused tests 覆盖 Router、多子 Agent、OpenRouter fake path、draft 落表、账户异常自动标记、confirmation、send/no-op evidence、views 和安全边界。
- Alembic offline SQL 到达 Stage05 migration。
- Staging 使用真实 OpenRouter 处理一条中英混合 Telegram 测试消息。
- Staging 至少生成多个 Stage05 draft：`recharge`、`customer_reply`，以及 `card_binding` 或 `bm_invite`。
- Staging 账户异常样例能形成 `account_status_events` 或人工复核证据；若测试消息未包含账户异常，验收报告必须说明未触发原因并用 API/fixture 证明该分支。
- Staging `customer_reply` 经人工确认后发送到 allowlisted private test chat。
- Staging 业务 draft 经人工确认后只生成 service/no-op evidence，不调用 provider。
- `agent_runs` 记录真实 OpenRouter 模型、usage/cost/latency、脱敏摘要和结构化结果。
- Views 能展示 `service_drafts`、`agent_review_queue`、`pending_confirmation`、`customer_reply_send_requests`。
- 没有真实客户发送、客户群发送、provider 写入、资金动作、自动替换账户或生产上线动作。
- Staging 结束后恢复安全配置。
