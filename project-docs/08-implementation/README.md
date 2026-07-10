# Stage Implementation Docs

## Status

- Document status: active implementation index
- Scope: Stage 02 / Stage 03 / Stage 04 / Stage 05 historical implementation entrypoints, Stage06 backend-stage evidence and Stage07 Mini App UI design entrypoint
- Current Progress: 2026-07-10 Stage06 backend-stage acceptance passed after correcting Stage06 work that remained in the Stage05 worktree. The Stage06 document set includes source, plan, SDD, contract, BDD, progress, backend exit and final stage acceptance. Fresh evidence is 129 Stage06-focused tests, 402 full-backend tests, Alembic `20260710_0020`, real local PostgreSQL isolation/redaction/concurrency smoke and sanitized evidence. Real OpenRouter and Telegram entry evidence is retained. Stage07 Mini App UI discovery, visual direction and detailed documentation package are ready for user review; explicit contract approval remains required before code. Stage05 LarkSuite documents remain historical.
- Current Progress Update: 2026-07-08 Stage 05 functional/staging acceptance has passed. Evidence includes local focused/full regression, staging migration `20260707_0016`, real OpenRouter AgentRun, service drafts, customer reply allowlisted send, business no-op evidence, controlled account exception, additional three-message Telegram exercise and safety close. Stage05 still is not production launch and does not approve real customer/group sends, provider writes, funds movement, account production or automatic replacement. Remaining follow-up is durable commit/artifact hygiene plus optional online smoke and later-stage reporting/balance support.
- Current Progress Update: 2026-07-07 Added Stage05 requirement traceability audit to distinguish locally verified requirements from pending Tencent Cloud staging, real OpenRouter, real Telegram receipt and safety-close evidence.
- Current Progress Update: 2026-07-07 Added Stage05 pre-staging approval packet as the single review entry before Task12 real staging rehearsal.
- Current Progress Update: 2026-07-07 Synchronized this implementation index with the then-latest local evidence; this historical note is superseded by the 2026-07-08 final staging acceptance update below.
- Current Progress Update: 2026-07-08 Synchronized this implementation index after Task12 staging acceptance and safety close. Historical pending notes remain historical only; current Stage05 closeout evidence lives in `STAGE_05_FINAL_ACCEPTANCE_REPORT.md`, `STAGE_05_ACCEPTANCE_CHECKLIST.md`, `STAGE_05_REQUIREMENT_TRACEABILITY_AUDIT.md` and `STAGE_05_PROGRESS.md`.
- Current Progress Update: 2026-07-09 Stage05 closeout phase completed with refreshed local tests, staging safety readback and an optional targeted real Telegram re-test for `card-binding-draft` and `account-exception-marking`. `STAGE_05_CLOSEOUT_AUDIT.md` is the final closeout gate before Stage06 planning.

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
17. [Stage 03 Final Acceptance Report](STAGE_03_FINAL_ACCEPTANCE_REPORT.md)

Stage 03 complex module docs:

1. [Stage 03 Telegram Webhook Ingress Module](modules/STAGE_03_TELEGRAM_WEBHOOK_INGRESS.md)
2. [Stage 03 Customer Binding And Telegram Inbox Module](modules/STAGE_03_CUSTOMER_BINDING_AND_INBOX.md)
3. [Stage 03 Redis Streams Worker Module](modules/STAGE_03_REDIS_STREAMS_WORKER.md)

Stage 04 开发前按这个顺序阅读：

1. [Stage 04 Source Of Truth](STAGE_04_SOURCE_OF_TRUTH.md)
2. [Stage 04 Implementation Plan](STAGE_04_IMPLEMENTATION_PLAN.md)
3. [Stage 04 SDD](STAGE_04_SDD.md)
4. [Stage 04 BDD](STAGE_04_BDD.md)
5. [Stage 04 Acceptance Checklist](STAGE_04_ACCEPTANCE_CHECKLIST.md)
6. [Stage 04 Local Acceptance Audit](STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md)
7. [Stage 04 Module Index](STAGE_04_MODULE_INDEX.md)
8. [Stage 04 API Contract](STAGE_04_API_CONTRACT.md)
9. [Stage 04 Database And Migration Design](STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md)
10. [Stage 04 Security And Permission Design](STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md)
11. [Stage 04 Test Plan](STAGE_04_TEST_PLAN.md)
12. [Stage 04 Operations Runbook](STAGE_04_OPERATIONS_RUNBOOK.md)
13. [Stage 04 Risk Register](STAGE_04_RISK_REGISTER.md)
14. [Stage 04 Progress](STAGE_04_PROGRESS.md)
15. [Stage 04 Final Acceptance Report](STAGE_04_FINAL_ACCEPTANCE_REPORT.md)

Stage 04 complex module docs:

1. [Stage 04 Binding Management Module](modules/STAGE_04_BINDING_MANAGEMENT.md)
2. [Stage 04 New Message Binding Module](modules/STAGE_04_NEW_MESSAGE_BINDING.md)
3. [Stage 04 Bitable Views Module](modules/STAGE_04_BITABLE_VIEWS.md)
4. [Stage 04 Restricted Test Send Module](modules/STAGE_04_RESTRICTED_TEST_SEND.md)
5. [Stage 04 Intent Placeholder Module](modules/STAGE_04_INTENT_PLACEHOLDER.md)

Stage 05 开发前按这个顺序阅读：

1. [Stage 05 Source Of Truth](STAGE_05_SOURCE_OF_TRUTH.md)
2. [Stage 05 Implementation Plan](STAGE_05_IMPLEMENTATION_PLAN.md)
3. [Stage 05 SDD](STAGE_05_SDD.md)
4. [Stage 05 BDD](STAGE_05_BDD.md)
5. [Stage 05 Acceptance Checklist](STAGE_05_ACCEPTANCE_CHECKLIST.md)
6. [Stage 05 Local Acceptance Audit](STAGE_05_LOCAL_ACCEPTANCE_AUDIT.md)
7. [Stage 05 Development Detail Completion Audit](STAGE_05_DEVELOPMENT_DETAIL_COMPLETION_AUDIT.md)
8. [Stage 05 Requirement Traceability Audit](STAGE_05_REQUIREMENT_TRACEABILITY_AUDIT.md)
9. [Stage 05 Module Index](STAGE_05_MODULE_INDEX.md)
10. [Stage 05 API Contract](STAGE_05_API_CONTRACT.md)
11. [Stage 05 Database And Migration Design](STAGE_05_DATABASE_AND_MIGRATION_DESIGN.md)
12. [Stage 05 Security And Permission Design](STAGE_05_SECURITY_AND_PERMISSION_DESIGN.md)
13. [Stage 05 Test Plan](STAGE_05_TEST_PLAN.md)
14. [Stage 05 Local Real Workflow Env](STAGE_05_LOCAL_REAL_WORKFLOW_ENV.md)
15. [Stage 05 Operations Runbook](STAGE_05_OPERATIONS_RUNBOOK.md)
16. [Stage 05 Pre-Staging Approval Packet](STAGE_05_PRE_STAGING_APPROVAL_PACKET.md)
17. [Stage 05 Risk Register](STAGE_05_RISK_REGISTER.md)
18. [Stage 05 Progress](STAGE_05_PROGRESS.md)
19. [Stage 05 Final Acceptance Report](STAGE_05_FINAL_ACCEPTANCE_REPORT.md)

Stage 05 core module docs:

1. [Stage 05 Agent Graph And Routing Module](modules/STAGE_05_AGENT_GRAPH_AND_ROUTING.md)
2. [Stage 05 Account Inventory Agent Module](modules/STAGE_05_ACCOUNT_INVENTORY_AGENT.md)
3. [Stage 05 Draft Agents Module](modules/STAGE_05_DRAFT_AGENTS.md)
4. [Stage 05 Confirmation And Send Module](modules/STAGE_05_CONFIRMATION_AND_SEND.md)
5. [Stage 05 Bitable Views Module](modules/STAGE_05_BITABLE_VIEWS.md)
6. [Stage 05 OpenRouter Evidence Module](modules/STAGE_05_OPENROUTER_EVIDENCE.md)

Stage 05 post-acceptance reference docs:

1. [Stage 05 Agent Skills And Capabilities Module](modules/STAGE_05_AGENT_SKILLS_AND_CAPABILITIES.md)
2. [Stage 05 LarkSuite Skills Reference Audit](modules/STAGE_05_LARKSUITE_SKILLS_REFERENCE_AUDIT.md)
3. [Stage 05 LarkSuite Skills Official Summary](modules/STAGE_05_LARKSUITE_SKILLS_OFFICIAL_SUMMARY.md)

Stage 05 Skills Extension docs:

1. [Stage 05 Skills Extension Source Of Truth](STAGE_05_SKILLS_EXTENSION_SOURCE_OF_TRUTH.md)
2. [Stage 05 Skills Extension Implementation Plan](STAGE_05_SKILLS_EXTENSION_IMPLEMENTATION_PLAN.md)
3. [Stage 05 Skills Manifest Design](STAGE_05_SKILLS_MANIFEST_DESIGN.md)
4. [Stage 05 Skills Acceptance Checklist](STAGE_05_SKILLS_ACCEPTANCE_CHECKLIST.md)

Stage 06 planning docs:

1. [Stage 06 LarkSuite Benchmark Audit](STAGE_06_LARKSUITE_BENCHMARK_AUDIT.md)
2. [Stage 06 Source Of Truth](STAGE_06_SOURCE_OF_TRUTH.md)
3. [Stage 06 Implementation Plan](STAGE_06_IMPLEMENTATION_PLAN.md)
4. [Stage 06 SDD](STAGE_06_SDD.md)
5. [Stage 06 API Data Security Contract](STAGE_06_API_DATA_SECURITY_CONTRACT.md)
6. [Stage 06 BDD And Acceptance](STAGE_06_BDD_AND_ACCEPTANCE.md)
7. [Stage 06 Progress](STAGE_06_PROGRESS.md)
8. [Stage 06 Backend Exit Audit](STAGE_06_BACKEND_EXIT_AUDIT.md)
9. [Stage 06 Remaining Risks And Next Cases](STAGE_06_REMAINING_RISKS_AND_NEXT_CASES.md)
10. [Stage 06 LarkSuite Skills Integration Design](STAGE_06_LARKSUITE_SKILLS_INTEGRATION_DESIGN.md)
11. [Stage 06 LarkSuite Skills Runtime Implementation Plan](STAGE_06_LARKSUITE_SKILLS_RUNTIME_IMPLEMENTATION_PLAN.md)
12. [Stage 06 Stage Acceptance Report](STAGE_06_STAGE_ACCEPTANCE_REPORT.md)

Stage 07 design docs:

1. [Stage 07 Mini App UI Design](STAGE_07_MINI_APP_UI_DESIGN.md)
2. [Stage07 Mini App UI Design Specification](../../docs/superpowers/specs/2026-07-10-stage07-mini-app-ui-design.md)
3. [Stage 07 Source Of Truth](STAGE_07_SOURCE_OF_TRUTH.md)
4. [Stage 07 SDD](STAGE_07_SDD.md)
5. [Stage 07 API Data Security Contract](STAGE_07_API_DATA_SECURITY_CONTRACT.md)
6. [Stage 07 BDD And Acceptance](STAGE_07_BDD_AND_ACCEPTANCE.md)
7. [Stage 07 Module Index](STAGE_07_MODULE_INDEX.md)
8. [Stage 07 Test Plan](STAGE_07_TEST_PLAN.md)
9. [Stage 07 Risk Register](STAGE_07_RISK_REGISTER.md)
10. [Stage 07 Implementation Plan](STAGE_07_IMPLEMENTATION_PLAN.md)
11. [Stage 07 Acceptance Checklist](STAGE_07_ACCEPTANCE_CHECKLIST.md)
12. [Stage 07 Progress](STAGE_07_PROGRESS.md)

Stage 02 已于 2026-07-06 冻结关闭。Stage 03 已由用户于 2026-07-06 确认转为 active，补充决策：Telegram 只收不发、Worker 使用 PostgreSQL Outbox + Redis Streams、Stage 03 暂不调用 LLM、第一批业务场景为 Telegram 收件箱 / 客户消息登记、Webhook 使用 secret token + optional allowlist、做最小客户绑定、部署到腾讯云 CVM staging、HTTPS 使用 Caddy。当前 Tasks 1-7 已完成验收；真实 staging 环境已接收 Telegram 测试消息并在 `telegram_inbox`、`outbox_events`、`ops_audit_events` 中形成证据。

Stage 04 已由用户于 2026-07-06 确认范围，并于 2026-07-07 完成最终验收。范围为：绑定管理 API、`chat_id` / `user_id` / `chat_id + user_id` 绑定、绑定后只影响新消息、无 LLM intent placeholder、`telegram_send_requests` 受控测试发送、staging 验收。最终证据见 [Stage 04 Final Acceptance Report](STAGE_04_FINAL_ACCEPTANCE_REPORT.md)。Stage 04 不做 UI、Mini App、客户群发送、OpenRouter、LangGraph、provider、资金或账户外部写入。

Stage 05 已由用户于 2026-07-07 确认进入文档阶段。范围为：真实 OpenRouter 主路径、LangGraph Supervisor + 子 Agent、多意图、多业务草稿、账户库存异常处理、customer_reply allowlisted private test chat 发送、业务 draft no-op evidence、业务处理优先的 Bitable-like views 和 Tencent Cloud staging 验收。Stage05 明确不做 UI、Mini App、RAG、生产上线、真实客户发送、客户群发送、provider 写入、资金动作、账户生产或自动替换分发。

Stage 06 已由用户于 2026-07-09 确认转向通用平台方向：通用多维表格、无代码工作台、模板/导入、Telegram Mini App 和表格数字员工。Stage06 文档包保持大任务包结构，不把阶段切成过碎任务。当前非 UI backend-readiness pass 已形成真实 OpenRouter summarize/draft、local PostgreSQL migration、真实 Telegram `@ops` backend entry、audit 和 safety close 证据。Stage06 仍不是生产发布，不接入 Feishu API，不做 Feishu API 兼容，不做真实 provider 写入、资金动作或无控制的 Telegram 群发送；Mini App UI 和生产式部署证据等待后续单独确认。

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

进入 Stage 04 代码开发前必须：

- Stage 04 文档包通过一致性检查。
- 用户确认从文档阶段进入代码开发。
- 不把真实 Bot Token、webhook secret、数据库密码、Redis 密码或 test chat allowlist 写入仓库。
- 任何腾讯云服务器操作、staging env 修改或 Telegram `sendMessage` 真实发送都必须先单独确认。

进入 Stage 05 代码开发前必须：

- Stage 05 文档包通过用户 review。
- 用户确认从文档阶段进入代码实施。
- 不把 OpenRouter key、真实 Bot Token、webhook secret、数据库密码、Redis 密码或 test chat allowlist 写入仓库。
- 任何 Tencent Cloud staging env 修改、真实 OpenRouter 调用或 Telegram `sendMessage` 真实发送都必须先单独确认。
- `PROVIDER_MODE` 保持 disabled。
- Account Inventory Agent 不生产账户、不自动替换分发账户。

进入 Stage 06 代码开发前必须：

- Stage06 文档包通过用户 review。
- 用户确认从文档阶段进入代码实施。
- 先实现通用平台资源模型，再复用或模板化历史广告业务能力。
- 不把 OpenRouter key、真实 Bot Token、webhook secret、数据库密码、Redis 密码或 test chat allowlist 写入仓库。
- 不接入 Feishu/Lark API。
- 默认禁止真实 provider 写入、资金动作和非 allowlist Telegram 发送。
- 数字员工写入默认进入 `record_change_drafts`，不得自我确认。
