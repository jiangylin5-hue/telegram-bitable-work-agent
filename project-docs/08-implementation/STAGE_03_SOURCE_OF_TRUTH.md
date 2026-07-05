# Stage 03 Source Of Truth

## Status

- Document status: candidate stage source of truth, pending user confirmation
- Scope: Stage 03 真实集成与运行时基础，包括真实 Telegram webhook、durable worker、Redis/job runtime、provider sandbox gateway、部署数据库演练和生产化配置边界
- Current Progress: 2026-07-05 从 Stage 02 剩余风险反推 Stage 03 候选范围。Stage 03 不继续扩 Stage 02 mock 闭环，而是把已验证的 PostgreSQL/Bitable/service/outbox 内核推进到真实 Telegram 接入、durable worker、sandbox provider gateway 和部署级验收。等待用户确认后转为 active stage。

## 1. Stage Goal

Stage 03 的目标不是重写 Stage 02，也不是直接接真实资金和真实 Meta 写入，而是把 Stage 02 已验证的后端内核从测试闭环推进到可运行集成环境：

```text
Stage 02 mock/sandbox backend kernel
-> real Telegram webhook ingress
-> durable worker runtime
-> Redis/job bridge over outbox
-> provider sandbox execution gateway
-> managed/local-like PostgreSQL migration rehearsal
-> operator-safe Bitable views and audit evidence
```

阶段完成标准：

- 真实 Telegram webhook 可以接收 Bot API update，并走现有消息入库、outbox、agent intent_extract、Bitable view。
- Worker 不再只是在测试里同步调用 dispatcher，而是有可启动的运行时入口和幂等处理循环。
- Outbox table 与 Redis/job runtime 的边界明确，DB commit 后再投递异步任务。
- Provider 调用只接 sandbox/fake adapter，不接真实资金、真实卡台、真实 Meta 写入。
- 部署级配置、secret、环境变量和 health/readiness 边界写清楚。
- PostgreSQL migration 至少完成一次“非测试 fixture 的 rehearsal”，但不要求接入正式生产库。
- 每条工作流终点仍然必须落回 Bitable record/view/status/audit。

## 2. In Scope

Stage 03 必做：

- Real Telegram Bot webhook endpoint。
- Telegram webhook secret / token 校验。
- Telegram update 去重、签名/来源校验、错误响应策略。
- Durable worker command/entrypoint。
- Outbox -> Redis/job bridge 或 Stage 03 可验收的可靠队列实现。
- Worker 幂等、retry、dead letter、audit persistence。
- `telegram.notify` mock/sandbox sender，可对接 Telegram sandbox 或 dry-run。
- Provider sandbox gateway interface，用于 recharge/readback/card-binding/BM invite 的受控模拟外部调用。
- Execution ticket 校验继续沿用 Stage 02。
- Deployment config 文档：env vars、secret categories、local compose、staging rehearsal。
- PostgreSQL migration rehearsal：在非 per-test reset 的数据库上执行 Alembic upgrade，验证表和关键约束。
- Bitable view read pagination/filter 基础 hardening：limit、cursor 或 deterministic ordering 的最小实现。
- Stage 03 BDD、SDD、acceptance checklist 和 progress log。

## 3. Out Of Scope

Stage 03 不做：

- 真实资金移动。
- 真实 Meta/BM/卡台/充值 provider 写入。
- raw card number、CVV、完整卡图存储。
- Telegram Mini App 前端。
- 完整 Web 管理台。
- 多租户 `tenant_id`。
- Temporal 迁移。
- 全量 LangGraph 多 Agent 生产编排。
- 自动投放优化。

如果用户明确要求提前接真实 provider 写入，必须先建立新的 Stage 04/Provider Execution 真源并二次确认权限、回滚、审计和人工确认策略。

## 4. Stage Boundaries

Stage 03 只允许把 Stage 02 已有业务闭环接到真实运行时边界，不允许凭空加新业务。

所有新增功能必须回答：

- 输入来自哪张 Bitable table/view 或 Telegram update？
- 输出落到哪张 table/view/status/audit？
- 是否改变现有权限模型？
- 是否需要人工确认？
- 是否只调用 sandbox provider？
- 失败如何落库、重试、dead letter 和 audit？

## 5. Source Order

Stage 03 执行优先级：

1. 用户当前确认的 Stage 03 范围。
2. `AGENTS.md`。
3. 本文件。
4. [Stage 03 Backend Integration Plan](STAGE_03_BACKEND_INTEGRATION_PLAN.md)。
5. [Stage 03 SDD](STAGE_03_SDD.md)。
6. [Stage 03 BDD](STAGE_03_BDD.md)。
7. [Stage 03 Acceptance Checklist](STAGE_03_ACCEPTANCE_CHECKLIST.md)。
8. Stage 02 文档和现有代码。
9. 架构、数据库、队列、权限等专项设计文档。

## 6. Entry Gate

进入 Stage 03 代码开发前必须满足：

- Stage 02 当前 hardening batch 已 commit，避免两个阶段混在一个提交里。
- Stage 03 文档由用户确认从 `candidate` 转为 `active`。
- Stage 03 第一批任务只选一个主线：推荐 `A. Real Telegram ingress + durable worker`。
- 不接真实 provider 写入，除非用户另建阶段确认。

## 7. Exit Gate

Stage 03 完成时必须证明：

- Real Telegram webhook 或等价 sandbox webhook 可以写入 `messages`。
- `messages -> outbox -> worker -> service_drafts` 路径在持久运行时中可重复执行且幂等。
- Worker retry/dead_letter 写 `ops_audit_events`。
- `telegram.notify` 只发送 mock/sandbox/dry-run 消息并写 delivery audit。
- Provider sandbox gateway 不触发真实资金或真实广告平台写入。
- Bitable views 能稳定读取关键记录，并具备最小分页/排序边界。
- PostgreSQL migration rehearsal 有命令和结果。
- Stage 03 acceptance checklist 全部有证据。

