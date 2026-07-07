# Stage 04 Source Of Truth

## Status

- Document status: active stage source of truth
- Scope: Stage 04 以 Telegram 收件箱运营、客户绑定管理、受控测试发送、无 LLM 的 intent placeholder 和 staging 验收为主线。
- Current Progress: 2026-07-07 Tasks 1-9 are implemented locally and verified with `pytest tests -q` reporting 172 passed / 17 skipped after the staging compose send-mode gate test was added. [Stage 04 Local Acceptance Audit](STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md) records the local readiness evidence. Stage 04 still requires Task 10 Tencent Cloud staging rehearsal before final acceptance; no staging env change or real Telegram send has been executed in this local batch.

## 1. Stage Goal

Stage 04 的目标是把 Stage 03 已打通的真实 Telegram 收件入口升级为可运营入口：

```text
real Telegram message
-> telegram_inbox
-> internal binding management API
-> new messages resolve customer_id
-> intent placeholder / agent job boundary
-> optional telegram_send_requests smoke
-> manual confirmation
-> allowlisted test chat only
-> audit + Bitable view evidence
```

Stage 04 不是客户通知阶段，也不是 Agent 生产阶段。它只证明：

- 运维人员可以通过内部 API 管理 Telegram chat/user/customer 绑定。
- 新消息在绑定后能自动进入 `bound` 状态并关联 `customer_id`。
- 无绑定、冲突、禁用绑定都能在多维表格视图和审计中明确呈现。
- 系统已经为后续 `agent.intent_extract` 预留可靠的状态、outbox/job 边界和审计证据，但不调用 LLM。
- 系统可以在人工确认后向 allowlisted test chat 发送一条真实 Telegram 测试消息，并把请求、确认、发送结果、Telegram response 摘要和 audit 落表。

所有结果仍必须落回多维表格记录、状态、视图、outbox 或审计事件。只停留在 Telegram 聊天、临时内存或未落表日志中不算完成。

## 1.1 Confirmed User Choices

用户于 2026-07-06 逐项确认以下 Stage 04 决策：

| Question | User Decision | Stage 04 Meaning |
| --- | --- | --- |
| Stage 04 主目标 | A. Telegram 收件箱运营和客户绑定管理 | 先让真实入口可运营，而不是直接做 provider 或生产 Agent |
| UI 范围 | A. 暂不做 UI，只做 authenticated internal API + 文档验收 | 不做 Web 管理页、Mini App 或 Telegram 命令管理 |
| 绑定粒度 | C. 支持 `chat_id`、`user_id`、`chat_id + user_id` | 复用并加固 Stage 03 `telegram_customer_bindings` |
| 绑定后历史消息 | A. 只影响新消息 | 不自动回放或重算历史 unbound 消息 |
| LLM | A. 不启用，继续 rule-based | 仅做 intent placeholder / job boundary，不调用 OpenRouter |
| 验收环境 | B. 本地测试 + staging 部署验证 | 使用 Stage 03 腾讯云 staging 形态继续验收 |
| Telegram 发送 | C + 限制 A | 允许人工确认后真实发送到 allowlisted test chat / 测试私聊，不发客户群或运营群 |
| Telegram send table | 确认新增 | 新增 `telegram_send_requests`，作为测试发送请求和执行证据表 |
| 方案范围 | A + B + C | 绑定运营底座 + 最小 test send + 无 LLM intent 预留 |

## 2. In Scope

Stage 04 必做：

- Internal authenticated API for Telegram binding management。
- `telegram_customer_bindings` 创建、禁用、查询、冲突识别和审计。
- 支持 `binding_scope = chat`、`user`、`chat_user`。
- 绑定后只影响新收到的 Telegram message，不自动改写历史消息。
- `telegram_inbox` 增加运营字段或筛选，使 unbound / conflict / bound 状态可查。
- 新增 `telegram_bindings` Bitable-like view。
- 新增 `telegram_intent_queue` 或等价 view，展示无 LLM intent placeholder 状态。
- 新增 `telegram_send_requests` 表、service、API、outbox event、worker handler 和 view。
- Telegram test send 只允许人工确认后发送到配置 allowlist 中的 test chat。
- 发送结果必须写入 `telegram_send_requests.status`、Telegram response 摘要和 `ops_audit_events`。
- Staging 验收：绑定后新消息变为 bound；测试发送能在 allowlisted test chat 收到；intent placeholder 不调用 LLM。
- Stage 04 SDD、BDD、API、DB、安全、测试、验收、进度、风险、runbook 和模块文档。

## 3. Out Of Scope

Stage 04 不做：

- Web UI / Web 管理页。
- Telegram Mini App。
- Telegram 命令式绑定管理。
- 自动重算或回放历史 unbound 消息。
- OpenRouter 真实 LLM 调用。
- LangGraph production agent graph。
- 真实生成正式 `service_drafts`。
- 客户群真实发送、内部运营群真实发送、客户回复草稿和客户通知。
- Meta、BM、卡台、充值 provider 写入。
- 真实资金移动。
- 账户外部写入。
- 多租户 `tenant_id`。
- Temporal。
- 生产数据库切换、备份/PITR 和正式生产发布。

如果后续用户要求将 Stage 04 扩展为客户群真实通知、OpenRouter/LLM、LangGraph、历史消息回放、provider sandbox 或真实外部业务执行，必须另开 Stage 04 extension 或 Stage 05 真源，并重新确认权限、审计、回滚和人工确认边界。

## 4. Bitable Endpoint Rule

Stage 04 所有工作流必须以多维表格为终点：

| Workflow | Bitable Endpoint |
| --- | --- |
| Create binding | `telegram_bindings` 新增 active binding，并写 `ops_audit_events` |
| Disable binding | `telegram_bindings.status = inactive`，并写 audit |
| Binding conflict | `telegram_inbox.binding_status = binding_conflict` 或 `telegram_bindings` conflict view |
| New message after binding | `telegram_inbox.customer_id` / `binding_status = bound` |
| Intent placeholder | `telegram_intent_queue` 显示 `intent_status = intent_ready` 或 `intent_pending` |
| Test send requested | `telegram_send_requests.status = draft` 或 `pending_confirmation` |
| Test send confirmed | `telegram_send_requests.status = confirmed`，并写 outbox event |
| Test send blocked | `telegram_send_requests.status = blocked`，记录 allowlist 或 permission failure |
| Test send sent | `telegram_send_requests.status = sent`，写 Telegram response 摘要和 audit |
| Test send failed | `telegram_send_requests.status = failed`，写 safe error code 和 audit |

任何没有 Bitable 视图、状态或审计落点的 Stage 04 实现都不得进入代码计划。

## 5. Source Order

Stage 04 执行优先级：

1. 用户当前明确指令。
2. `AGENTS.md`。
3. 本文件。
4. [Stage 04 Implementation Plan](STAGE_04_IMPLEMENTATION_PLAN.md)。
5. [Stage 04 SDD](STAGE_04_SDD.md)。
6. [Stage 04 BDD](STAGE_04_BDD.md)。
7. [Stage 04 Acceptance Checklist](STAGE_04_ACCEPTANCE_CHECKLIST.md)。
8. [Stage 04 Local Acceptance Audit](STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md)。
9. [Stage 04 Module Index](STAGE_04_MODULE_INDEX.md)。
10. [Stage 04 API Contract](STAGE_04_API_CONTRACT.md)。
11. [Stage 04 Database And Migration Design](STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md)。
12. [Stage 04 Security And Permission Design](STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md)。
13. [Stage 04 Test Plan](STAGE_04_TEST_PLAN.md)。
14. [Stage 04 Operations Runbook](STAGE_04_OPERATIONS_RUNBOOK.md)。
15. [Stage 04 Risk Register](STAGE_04_RISK_REGISTER.md)。
16. Stage 04 module docs under `modules/`。
17. Stage 03 final acceptance docs and existing code。
18. Architecture, database, permission, queue and Agent专项文档。

## 6. Entry Gate

进入 Stage 04 代码开发前必须满足：

- Stage 03 已提交并关闭，最终验收以 `STAGE_03_FINAL_ACCEPTANCE_REPORT.md` 为准。
- Stage 04 文档包通过用户确认。
- 用户明确确认从文档阶段进入代码实施。
- 不把真实 Bot Token、webhook secret、数据库密码、Redis 密码或 test chat id 秘密写入仓库。
- 任何腾讯云服务器操作、staging 环境变更或 Telegram `sendMessage` 真实发送都必须单独确认。
- Stage 04 配置必须 fail closed：未配置 allowlisted test chat 时不得真实发送。

## 7. Exit Gate

Stage 04 完成时必须证明：

- Binding management API 有权限校验、审计和自动化测试。
- `chat`、`user`、`chat_user` 三种 active binding 能被新消息解析。
- inactive binding 不参与解析。
- conflict 不猜客户，进入人工处理状态。
- 新消息在绑定后进入 `telegram_inbox` 的 bound 状态。
- Intent placeholder 形成 outbox/job/audit 或状态证据，但没有 LLM call。
- `telegram_send_requests` 支持 request、confirm、blocked、sent、failed 状态。
- 真实发送只发生在 allowlisted test chat，且需要人工确认。
- Staging 记录至少一条绑定后新消息证据和一条 test send 证据。
- 全量 backend suite 通过，或未运行项明确说明原因。
- 未发生客户群真实发送、OpenRouter 调用、provider 写入或资金移动。
