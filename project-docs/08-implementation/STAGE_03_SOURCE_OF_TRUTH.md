# Stage 03 Source Of Truth

## Status

- Document status: active stage source of truth (confirmed by user 2026-07-06)
- Scope: Stage 03 以真实 Telegram 收件入口、PostgreSQL Outbox、Redis Streams worker、最小客户绑定、多维表格 Telegram Inbox 视图、腾讯云 CVM staging 部署和 Caddy HTTPS 入口为主线。
- Current Progress: 2026-07-06 已进入 Stage 03 代码实施。已完成 runtime config safety gate、Telegram update parser、receive-only webhook route、secret/allowlist validation、`telegram.message_received` outbox event、Minimal Customer Binding、Stage03 `telegram_inbox` projection 和 Outbox To Redis Streams Bridge local/backend slice；下一步按阶段计划进入 Durable Worker Runtime。Stage 03 仍保持真实 Telegram 只收不发、不调用 LLM、不执行 provider、不移动资金，腾讯云 staging/DNS/真实 webhook 设置仍需单独确认。

## 1. Stage Goal

Stage 03 的目标不是扩展新业务，也不是接真实充值、真实 Meta、真实卡台或真实 Telegram 发送，而是把 Stage 02 已验证的后端内核推进到第一个可部署、可联调、可审计的真实入口闭环：

```text
Telegram Bot webhook
-> Caddy HTTPS reverse proxy on Tencent Cloud CVM
-> FastAPI webhook endpoint
-> webhook secret / allowlist validation
-> PostgreSQL transaction: messages + audit + outbox_events
-> Redis Streams delivery bridge
-> durable worker
-> rule-based message registration / customer binding resolution
-> Bitable Telegram Inbox view
-> audit evidence
```

阶段完成后，系统应该能证明：

- 真实 Telegram Bot update 可以通过腾讯云 staging 入口进入后端。
- 后端不会在 webhook 请求内做真实发送、真实充值、真实外部 provider 写入或 LLM 调用。
- 每条有效消息都会进入数据库，并在多维表格 `telegram_inbox` 视图中可见。
- 消息可以通过最小客户绑定逻辑关联到 `customer_id`，无法绑定时明确显示为 `unbound` 或 `needs_manual_binding`。
- `messages -> outbox_events -> Redis Streams -> worker -> status/audit/view` 链路可重复执行且幂等。
- 所有结果必须落回多维表格记录、状态、视图或审计事件；只停留在 Telegram 聊天或临时内存中不算完成。

## 1.1 Confirmed User Choices

用户于 2026-07-06 逐项确认以下 Stage 03 决策：

| Question | User Decision | Stage 03 Meaning |
| --- | --- | --- |
| Stage 03 主方向 | A. 真实 Telegram 入口 + 持久 Worker + 多维表格落表闭环 | 第一阶段从真实消息入口和运行时闭环做起，不先做 UI、LLM 或 provider 执行 |
| Telegram 闭环范围 | A. 只接收真实 webhook，不发送消息 | `telegram.notify` 和真实回复发送不进入 Stage 03 第一批 |
| Worker / Queue | B. PostgreSQL Outbox + Redis Streams worker | 数据库仍是真源，Redis Streams 作为任务投递和消费层 |
| LLM / Agent | A. 暂不调用 LLM，只做规则化分流和落表 | OpenRouter、LangGraph 真实 Agent 留到后续阶段 |
| 第一批业务场景 | A. Telegram 收件箱 / 客户消息登记 | Stage 03 不做充值、账户库存或卡台执行切片 |
| Webhook 安全 | A. Secret Token 校验 + allowlist chat/user 可选 | 使用 `X-Telegram-Bot-Api-Secret-Token` 和配置型 allowlist |
| 客户绑定 | A. 做最小客户绑定表 / 绑定逻辑 | 建立 Telegram chat/user 到 customer 的最小映射能力 |
| 验收环境 | C. 云服务器 / staging 环境真实 webhook 联调 | Stage 03 需要部署到腾讯云 staging，而不只做本地模拟 |
| 部署方式 | 腾讯云服务器部署 | 使用腾讯云 CVM 单机 staging 承载 Stage 03 验收 |
| HTTPS 入口 | A. 域名子域名 + Caddy 自动 HTTPS 反代 | Caddy 负责 TLS 和反向代理到 FastAPI |
| 开发节奏 | 已从 docs-first 转入代码实施 | 用户已确认开始实施；每个 Task 必须按阶段真源、TDD、验收清单和进度日志推进 |

## 2. In Scope

Stage 03 第一批必做：

- 真实 Telegram webhook endpoint 设计和实现计划。
- Telegram webhook secret token 校验设计。
- `chat_id` / `user_id` allowlist 策略设计。
- Telegram update 去重、幂等、错误响应和敏感信息脱敏。
- 最小客户绑定模型：Telegram chat/user 到客户记录的映射。
- PostgreSQL Outbox 到 Redis Streams 的投递边界。
- Redis Streams worker 的消费、幂等、retry、dead letter、审计写入。
- Rule-based message registration：基于 Telegram payload、绑定关系和简单规则更新消息状态。
- 多维表格 `telegram_inbox` 视图：显示消息、客户绑定状态、处理状态、审计状态。
- 腾讯云 CVM staging 部署设计。
- Docker Compose 单机编排设计：FastAPI、worker、PostgreSQL、Redis、Caddy。
- Caddy 自动 HTTPS 反代设计。
- Stage 03 SDD、BDD、Acceptance Checklist、Progress Log 和部署文档。

## 3. Out Of Scope

Stage 03 第一批不做：

- 真实 Telegram 发送消息。
- Telegram Mini App 前端。
- 完整 Web 管理台。
- OpenRouter 真实 LLM 调用。
- LangGraph 真实 multi-agent 编排。
- 充值执行、绑卡执行、Meta/BM/card platform/provider 写入。
- 真实资金移动。
- Provider sandbox gateway 实现。
- 客户日报、公司日报、账户库存、卡台执行等新业务切片。
- 多租户 `tenant_id`。
- Temporal。
- 完整向量检索。
- raw card number、CVV、完整卡图或未脱敏支付凭证存储。

如果后续用户要求提前接入真实 Telegram 发送、OpenRouter LLM、provider sandbox 或真实外部写入，必须另开 Stage 03 extension 或 Stage 04 真源，并重新确认权限、审计、回滚和人工确认边界。

## 4. Bitable Endpoint Rule

Stage 03 所有工作流必须以多维表格为终点：

| Workflow | Bitable Endpoint |
| --- | --- |
| Telegram update received | `telegram_inbox` 新增或更新消息记录 |
| Customer binding resolved | `telegram_inbox.customer_id` / `binding_status` 更新 |
| Message queued | `telegram_inbox.processing_status = queued`，并写 `outbox_events` |
| Worker processed | `telegram_inbox.processing_status = processed` 或 `failed` |
| Invalid secret / blocked allowlist | 只写安全审计，不创建业务消息记录 |
| Duplicate update | 保持单条消息记录，写幂等审计或返回幂等成功 |
| Dead letter | `telegram_inbox.processing_status = dead_letter`，并写 `ops_audit_events` |

任何没有 Bitable 视图、状态或审计落点的实现都不得进入 Stage 03。

## 5. Source Order

Stage 03 执行优先级：

1. 用户当前明确指令。
2. `AGENTS.md`。
3. 本文件。
4. [Stage 03 Backend Integration Plan](STAGE_03_BACKEND_INTEGRATION_PLAN.md)。
5. [Stage 03 SDD](STAGE_03_SDD.md)。
6. [Stage 03 BDD](STAGE_03_BDD.md)。
7. [Stage 03 Acceptance Checklist](STAGE_03_ACCEPTANCE_CHECKLIST.md)。
8. [Stage 03 Module Index](STAGE_03_MODULE_INDEX.md)。
9. [Stage 03 API Contract](STAGE_03_API_CONTRACT.md)。
10. [Stage 03 Database And Migration Design](STAGE_03_DATABASE_AND_MIGRATION_DESIGN.md)。
11. [Stage 03 Security And Permission Design](STAGE_03_SECURITY_AND_PERMISSION_DESIGN.md)。
12. [Stage 03 Test Plan](STAGE_03_TEST_PLAN.md)。
13. [Stage 03 Tencent Cloud Staging Deployment](STAGE_03_TENCENT_CLOUD_STAGING_DEPLOYMENT.md)。
14. [Stage 03 Operations Runbook](STAGE_03_OPERATIONS_RUNBOOK.md)。
15. [Stage 03 Risk Register](STAGE_03_RISK_REGISTER.md)。
16. Stage 03 module docs under `modules/`。
17. Stage 02 文档和现有代码。
18. 架构、数据库、权限、队列和 Agent 专项文档。

## 6. Entry Gate

进入 Stage 03 代码开发前必须满足；截至 2026-07-06 代码实施已开始，以下 gate 继续作为执行约束：

- Stage 02 已冻结关闭，最终验收以 `STAGE_02_FINAL_ACCEPTANCE_REPORT.md` 为准。
- Stage 03 文档包已更新为本轮用户选择后的 active 真源。
- 用户已确认可以从“只写文档”转入代码开发。
- 部署敏感信息不写入仓库，包括 Telegram Bot Token、webhook secret、数据库密码、Redis 密码、域名证书材料。
- 若需要真实腾讯云服务器操作、DNS 修改、设置 Telegram webhook 或外部系统写入，必须先由用户单独确认。

## 7. Exit Gate

Stage 03 完成时必须证明：

- 腾讯云 staging 环境可以通过 HTTPS 接收真实 Telegram webhook。
- Secret token 校验和 allowlist 生效。
- 有效 Telegram update 只创建一条消息记录，重复 update 不重复写业务记录。
- 最小客户绑定可以把已绑定 chat/user 关联到客户，未绑定消息进入待绑定状态。
- `messages -> outbox_events -> Redis Streams -> worker -> Bitable view/audit` 闭环可运行。
- Redis Streams worker 具备幂等、retry、dead letter 和审计证据。
- `/views/telegram_inbox/records` 能展示 Stage 03 关键字段。
- 全量测试通过，部署联调证据写入验收清单。
- 未发生真实 Telegram 发送、真实资金移动、真实 provider 写入或真实 LLM 调用。
