# Stage 03 Direction Decision Record

## Status

- Document status: historical direction decision record
- Scope: 记录 Stage 02 结束后，用户如何选择 Stage 03 方向；当前执行真源以 `STAGE_03_SOURCE_OF_TRUTH.md` 为准。
- Current Progress: 2026-07-06 用户已完成 Stage 03 方向选择。本文件不再提出待答问题，只保留决策依据和最终结果。

## 1. Decision Context

Stage 02 已关闭，交付了一个可测试、可审计的 mock/sandbox 后端内核：

- 后端内核：FastAPI + SQLAlchemy UOW + Alembic（`0001`~`0009`）+ 权限/审计/字段脱敏 + outbox + Bitable view API。
- 三条垂直切片：充值闭环、账户库存、客户/公司日报。
- 最终证据：`STAGE_02_FINAL_ACCEPTANCE_REPORT.md` 记录 fresh online PostgreSQL smoke 17 passed、全量 102 passed、Alembic offline SQL 至 `20260705_0009`。

Stage 02 明确留下的后续方向包括：

| Deferred item | Stage 03 Treatment |
| --- | --- |
| 真实 Telegram webhook | 纳入 Stage 03 第一批 |
| 生产级 worker / Redis 队列运行时 | 纳入 Stage 03 第一批，采用 Redis Streams |
| 真实 OpenRouter LLM 调用 | 不纳入 Stage 03 第一批 |
| LangGraph 真实编排 | 不纳入 Stage 03 第一批 |
| 真实 Meta/卡台/充值 provider 写入 | 不纳入 Stage 03 |
| Telegram Mini App / Web 管理台 | 不纳入 Stage 03 |
| 托管/云端运行环境 | Stage 03 使用腾讯云 CVM staging |

## 2. Options Discussed

### Option A: Real Telegram Ingress And Runtime Loop

Build the first real ingress/runtime loop:

```text
Telegram webhook
-> FastAPI
-> PostgreSQL messages/audit/outbox
-> Redis Streams worker
-> Bitable telegram_inbox
```

This was selected.

### Option B: LLM / Agent Upgrade

Introduce OpenRouter and LangGraph for real intent extraction. This was deferred because the system first needs a stable real message ingress and worker runtime.

### Option C: UI / Mini App

Build Mini App or Web UI first. This was deferred because Stage 03 needs the backend receive/runtime loop and Bitable inbox foundation before UI work.

### Option D: More Business Slices

Add more recharge/account/card-platform flows. This was deferred because Stage 03 should not expand business surface before real ingress and runtime are stable.

## 3. Final User Decisions

| Question | User Decision | Stage 03 Meaning |
| --- | --- | --- |
| Stage 03 主方向 | A. 真实 Telegram 入口 + 持久 Worker + 多维表格落表闭环 | 第一阶段从真实消息入口和运行时闭环做起 |
| Telegram 闭环范围 | A. 只接收真实 webhook，不发送消息 | 不实现真实回复发送 |
| Worker / Queue | B. PostgreSQL Outbox + Redis Streams worker | 数据库是真源，Redis Streams 是投递/消费层 |
| LLM / Agent | A. 暂不调用 LLM，只做规则化分流和落表 | OpenRouter、LangGraph 真实 Agent 留到后续阶段 |
| 第一批业务场景 | A. Telegram 收件箱 / 客户消息登记 | 不先做充值、账户库存或卡台执行 |
| Webhook 安全 | A. Secret Token 校验 + allowlist chat/user 可选 | 使用 Telegram secret header 和配置型 allowlist |
| 客户绑定 | A. 做最小客户绑定表 / 绑定逻辑 | 建立 Telegram chat/user 到 customer 的最小映射 |
| 验收环境 | C. 云服务器 / staging 环境真实 webhook 联调 | 使用真实云服务器验收 webhook |
| 部署方式 | 腾讯云服务器部署 | 使用腾讯云 CVM 单机 staging |
| HTTPS 入口 | A. 域名子域名 + Caddy 自动 HTTPS 反代 | Caddy 负责 TLS 和反代到 FastAPI |
| 开发节奏 | C. 先只写完整 Stage 03 文档，不写代码 | 当前批次只完成文档真源、设计、验收和部署方案 |

## 4. Resulting Stage 03 Scope

Stage 03 active scope is:

```text
Tencent Cloud CVM staging
-> Caddy HTTPS
-> receive-only Telegram webhook
-> webhook secret + allowlist
-> minimal customer binding
-> PostgreSQL messages/audit/outbox
-> Redis Streams worker
-> Bitable telegram_inbox
-> documented acceptance evidence
```

Stage 03 excludes:

- Real Telegram send.
- OpenRouter LLM.
- LangGraph production Agent.
- Provider execution.
- Real funds movement.
- Mini App or full Web UI.

## 5. Follow-Up

After Stage 03 documentation is accepted, the next user decision should be whether to begin Stage 03 implementation. Implementation must follow:

1. `STAGE_03_SOURCE_OF_TRUTH.md`
2. `STAGE_03_BACKEND_INTEGRATION_PLAN.md`
3. `STAGE_03_MODULE_INDEX.md`
4. Stage 03专项设计文档
5. `STAGE_03_ACCEPTANCE_CHECKLIST.md`
