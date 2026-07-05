# Stage Implementation Docs

## Status

- Document status: active implementation index
- Scope: Stage 02 历史入口与 Stage 03 当前阶段入口
- Current Progress: 2026-07-06 Stage 02 已冻结关闭；Stage 03 已确认转为 active。当前 Stage 03 已完成 Tasks 1-6 本地后端实施与 Task 7A 本地部署准备：真实 Telegram receive-only webhook、最小 customer binding、`telegram_inbox`、PostgreSQL outbox bridge、Redis Streams worker runtime、真实 Redis adapter 代码和 Stage03 compose/Caddy/env 文件已有自动化或文件证据；Task 7 腾讯云 staging rehearsal 仍等待真实服务器、DNS、Caddy 证书和 Telegram webhook 外部操作确认。

## 1. Read Order

Stage 02 已关闭，复盘或查历史时按这个顺序阅读：

1. [Stage 02 Source Of Truth](STAGE_02_SOURCE_OF_TRUTH.md)
2. [Stage 02 Backend Kernel And Vertical Slices Implementation Plan](STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md)
3. [Stage 02 SDD](STAGE_02_SDD.md)
4. [Stage 02 BDD](STAGE_02_BDD.md)
5. [Stage 02 Module Index](STAGE_02_MODULE_INDEX.md)
6. [Stage 02 Progress](STAGE_02_PROGRESS.md)
7. [Stage 02 Final Acceptance Report](STAGE_02_FINAL_ACCEPTANCE_REPORT.md)

其他产品、架构、Agent、数据库文档只作为引用，不作为日常执行入口。

Stage 03 开发前按这个顺序阅读：

1. [Stage 03 Direction Proposal](STAGE_03_DIRECTION_PROPOSAL.md)
2. [Stage 03 Source Of Truth](STAGE_03_SOURCE_OF_TRUTH.md)
3. [Stage 03 Backend Integration Plan](STAGE_03_BACKEND_INTEGRATION_PLAN.md)
4. [Stage 03 SDD](STAGE_03_SDD.md)
5. [Stage 03 BDD](STAGE_03_BDD.md)
6. [Stage 03 Acceptance Checklist](STAGE_03_ACCEPTANCE_CHECKLIST.md)
7. [Stage 03 Module Index](STAGE_03_MODULE_INDEX.md)
8. [Stage 03 API Contract](STAGE_03_API_CONTRACT.md)
9. [Stage 03 Database And Migration Design](STAGE_03_DATABASE_AND_MIGRATION_DESIGN.md)
10. [Stage 03 Security And Permission Design](STAGE_03_SECURITY_AND_PERMISSION_DESIGN.md)
11. [Stage 03 Test Plan](STAGE_03_TEST_PLAN.md)
12. [Stage 03 Tencent Cloud Staging Deployment](STAGE_03_TENCENT_CLOUD_STAGING_DEPLOYMENT.md)
13. [Stage 03 Operations Runbook](STAGE_03_OPERATIONS_RUNBOOK.md)
14. [Stage 03 Risk Register](STAGE_03_RISK_REGISTER.md)
15. [Stage 03 Task 7 Readiness Audit](STAGE_03_TASK7_READINESS_AUDIT.md)
16. [Stage 03 Progress](STAGE_03_PROGRESS.md)

Stage 03 complex module docs:

1. [Stage 03 Telegram Webhook Ingress Module](modules/STAGE_03_TELEGRAM_WEBHOOK_INGRESS.md)
2. [Stage 03 Customer Binding And Telegram Inbox Module](modules/STAGE_03_CUSTOMER_BINDING_AND_INBOX.md)
3. [Stage 03 Redis Streams Worker Module](modules/STAGE_03_REDIS_STREAMS_WORKER.md)

Stage 02 已于 2026-07-06 冻结关闭。Stage 03 已由用户于 2026-07-06 确认转为 active，补充决策：Telegram 只收不发、Worker 使用 PostgreSQL Outbox + Redis Streams、Stage 03 暂不调用 LLM、第一批业务场景为 Telegram 收件箱 / 客户消息登记、Webhook 使用 secret token + optional allowlist、做最小客户绑定、部署到腾讯云 CVM staging、HTTPS 使用 Caddy。当前 Tasks 1-6 和 Task 7A 本地部署准备已进入代码实施并提交候选；Task 7 真实 staging 前必须另行确认服务器、DNS、Telegram webhook 外部操作和 secret handling。

## 2. Stage 02 Scope

Stage 02 范围已经确认：

- 充值闭环。
- 账户库存。
- 客户日报和公司日报。
- Mock Telegram webhook。
- Mock/sandbox provider。
- 不做 `tenant_id`。
- 使用 outbox table。

## 3. Development Rule

开发时必须先确认当前任务属于 [Stage 02 Source Of Truth](STAGE_02_SOURCE_OF_TRUTH.md) 的范围。

如果任务不在 Stage 02 范围内：

- 不顺手实现。
- 记录为后续候选。
- 需要用户确认后才能变更阶段范围。

进入 Stage 03 代码开发前必须：

- Stage 03 文档包通过一致性检查。
- 用户确认从文档阶段进入代码开发。
- 不把真实 Bot Token、webhook secret、数据库密码或 Redis 密码写入仓库。
- 任何腾讯云服务器操作、DNS 修改或 Telegram webhook 设置都必须先单独确认。
