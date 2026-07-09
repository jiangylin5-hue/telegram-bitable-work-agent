# Telegram 多维表格和数字员工平台项目文档

## Status

- Document status: active project document index
- Current project mode: Stage 06 backend stage accepted; next phase requires separate confirmation
- Current Progress: 2026-07-10 Stage06 backend-stage acceptance passed after correcting Stage06 files that had remained in the Stage05 worktree. Active top-level documents define a generic Feishu-like multidimensional table, no-code workspace and table-bound digital employee platform. Fresh verification covers 129 Stage06-focused tests, 402 full-backend tests, Alembic `20260710_0020`, real local PostgreSQL security/concurrency smoke and sanitized evidence. Retained external evidence covers real OpenRouter summarize/draft and Telegram backend entry. Mini App and production deployment remain later gates.
- Current Progress Update: 2026-07-08 Stage 05 functional/staging acceptance has passed with documented residual risks. Evidence covers local focused/full regression, Tencent Cloud staging migration, real OpenRouter AgentRun, real Telegram allowlisted receipt, business no-op evidence, controlled account exception, additional three-message Telegram exercise and safety close. Stage05 is not production launch and does not approve real customer/group sends, provider writes, funds movement, account production or automatic replacement. Remaining follow-up is durable commit/artifact hygiene plus optional online PostgreSQL smoke and later-stage reporting/balance support.
- Current Progress Update: 2026-07-07 Added Stage05 requirement traceability audit to the implementation document map so final acceptance can be checked requirement-by-requirement instead of inferred from local tests alone.
- Current Progress Update: 2026-07-07 Added Stage05 pre-staging approval packet to make Task12 real staging approval scope explicit before external actions.
- Current Progress Update: 2026-07-07 Synchronized Stage05 top-level indexes with the latest local evidence and clarified that the only remaining acceptance blockers are Task12 external staging evidence and safety close.
- Current Progress Update: 2026-07-08 Synchronized top-level index after Task12 staging acceptance and safety close; historical pending notes are superseded by the final Stage05 acceptance docs.

## Document Map

### Governance

- [Implementation Source Of Truth](00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md)
- [Technical Decisions](00-governance/TECHNICAL_DECISIONS.md)

### Research

- [飞书多维表格与多维表格智能体调研](00-research/FEISHU_BITABLE_AND_AGENT_RESEARCH.md)

### Product

- [迁移版立项文档：Multidimensional Table And Agent Project Initiation](01-product/MULTIDIMENSIONAL_AGENT_PROJECT_INITIATION.md) - historical
- [Telegram 多维表格和数字员工平台产品简报](01-product/TELEGRAM_MULTIDIMENSIONAL_AGENT_NEW_PROJECT_BRIEF.md)
- [Templates And Scenarios Index](01-product/BUSINESS_SCENARIOS_INDEX.md)
- [Recharge Workflow](01-product/scenarios/RECHARGE_WORKFLOW.md) - historical advertising sample input
- [Account Inventory Workflow](01-product/scenarios/ACCOUNT_INVENTORY_WORKFLOW.md) - historical advertising sample input
- [BM Invite And Account Production](01-product/scenarios/BM_INVITE_AND_ACCOUNT_PRODUCTION.md) - historical advertising sample input
- [Card Platform Workflow](01-product/scenarios/CARD_PLATFORM_WORKFLOW.md) - historical advertising sample input
- [Customer Daily Reporting](01-product/scenarios/CUSTOMER_DAILY_REPORTING.md) - historical advertising sample input
- [Spend Risk Statistics](01-product/scenarios/SPEND_RISK_STATISTICS.md) - historical advertising sample input

### Architecture

- [SDD Backend Architecture](02-architecture/SDD_BACKEND_ARCHITECTURE.md)
- [Multi-Agent Orchestration](02-architecture/MULTI_AGENT_ORCHESTRATION.md)

### Modules

- [Telegram Ingestion Module](03-modules/TELEGRAM_INGESTION_MODULE.md)
- [Bitable Schema Blueprint](03-modules/BITABLE_SCHEMA_BLUEPRINT.md)
- [Multidimensional Table Module](03-modules/MULTIDIMENSIONAL_TABLE_MODULE.md)
- [Service Draft And Confirmation Module](03-modules/SERVICE_DRAFT_AND_CONFIRMATION_MODULE.md)

### Agents

- [Digital Employees Index](04-agents/AGENTS_INDEX.md)
- [Operations Supervisor Agent](04-agents/OPERATIONS_SUPERVISOR_AGENT.md) - historical/preset reference
- [Message Intake Router Agent](04-agents/MESSAGE_INTAKE_ROUTER_AGENT.md) - historical/preset reference
- [Account Inventory Agent](04-agents/ACCOUNT_INVENTORY_AGENT.md) - historical/preset reference
- [Recharge And Binding Agent](04-agents/RECHARGE_AND_BINDING_AGENT.md) - historical/preset reference
- [Finance Reconciliation Agent](04-agents/FINANCE_RECONCILIATION_AGENT.md) - historical/preset reference
- [Card Resource Agent](04-agents/CARD_RESOURCE_AGENT.md) - historical/preset reference
- [Customer Reporting Agent](04-agents/CUSTOMER_REPORTING_AGENT.md) - historical/preset reference

### Data And Queue

- [PostgreSQL Database Design](05-data/POSTGRES_DATABASE_DESIGN.md)
- [Permission And Security Model](05-data/PERMISSION_AND_SECURITY_MODEL.md)
- [Redis Queue And Worker Design](06-queue/REDIS_QUEUE_AND_WORKER_DESIGN.md)

### Acceptance

- [Stage 01 Acceptance Checklist](07-acceptance/STAGE_01_ACCEPTANCE_CHECKLIST.md)

### Implementation

- [Stage 02 Implementation Docs Index](08-implementation/README.md)
- [Stage 02 Source Of Truth](08-implementation/STAGE_02_SOURCE_OF_TRUTH.md)
- [Stage 02 Backend Kernel And Vertical Slices Implementation Plan](08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md)
- [Stage 02 SDD](08-implementation/STAGE_02_SDD.md)
- [Stage 02 BDD](08-implementation/STAGE_02_BDD.md)
- [Stage 02 Module Index](08-implementation/STAGE_02_MODULE_INDEX.md)
- [Stage 02 Progress](08-implementation/STAGE_02_PROGRESS.md)
- [Stage 02 Final Acceptance Report](08-implementation/STAGE_02_FINAL_ACCEPTANCE_REPORT.md)
- [Stage 03 Source Of Truth](08-implementation/STAGE_03_SOURCE_OF_TRUTH.md)
- [Stage 03 Backend Integration Plan](08-implementation/STAGE_03_BACKEND_INTEGRATION_PLAN.md)
- [Stage 03 SDD](08-implementation/STAGE_03_SDD.md)
- [Stage 03 BDD](08-implementation/STAGE_03_BDD.md)
- [Stage 03 Module Index](08-implementation/STAGE_03_MODULE_INDEX.md)
- [Stage 03 API Contract](08-implementation/STAGE_03_API_CONTRACT.md)
- [Stage 03 Database And Migration Design](08-implementation/STAGE_03_DATABASE_AND_MIGRATION_DESIGN.md)
- [Stage 03 Security And Permission Design](08-implementation/STAGE_03_SECURITY_AND_PERMISSION_DESIGN.md)
- [Stage 03 Test Plan](08-implementation/STAGE_03_TEST_PLAN.md)
- [Stage 03 Tencent Cloud Staging Deployment](08-implementation/STAGE_03_TENCENT_CLOUD_STAGING_DEPLOYMENT.md)
- [Stage 03 Operations Runbook](08-implementation/STAGE_03_OPERATIONS_RUNBOOK.md)
- [Stage 03 Risk Register](08-implementation/STAGE_03_RISK_REGISTER.md)
- [Stage 03 Task 7 Readiness Audit](08-implementation/STAGE_03_TASK7_READINESS_AUDIT.md)
- [Stage 03 Acceptance Checklist](08-implementation/STAGE_03_ACCEPTANCE_CHECKLIST.md)
- [Stage 03 Progress](08-implementation/STAGE_03_PROGRESS.md)
- [Stage 03 Final Acceptance Report](08-implementation/STAGE_03_FINAL_ACCEPTANCE_REPORT.md)
- [Stage 04 Source Of Truth](08-implementation/STAGE_04_SOURCE_OF_TRUTH.md)
- [Stage 04 Implementation Plan](08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md)
- [Stage 04 SDD](08-implementation/STAGE_04_SDD.md)
- [Stage 04 BDD](08-implementation/STAGE_04_BDD.md)
- [Stage 04 Module Index](08-implementation/STAGE_04_MODULE_INDEX.md)
- [Stage 04 API Contract](08-implementation/STAGE_04_API_CONTRACT.md)
- [Stage 04 Database And Migration Design](08-implementation/STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md)
- [Stage 04 Security And Permission Design](08-implementation/STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md)
- [Stage 04 Test Plan](08-implementation/STAGE_04_TEST_PLAN.md)
- [Stage 04 Operations Runbook](08-implementation/STAGE_04_OPERATIONS_RUNBOOK.md)
- [Stage 04 Risk Register](08-implementation/STAGE_04_RISK_REGISTER.md)
- [Stage 04 Acceptance Checklist](08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md)
- [Stage 04 Local Acceptance Audit](08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md)
- [Stage 04 Progress](08-implementation/STAGE_04_PROGRESS.md)
- [Stage 04 Final Acceptance Report](08-implementation/STAGE_04_FINAL_ACCEPTANCE_REPORT.md)
- [Stage 05 Source Of Truth](08-implementation/STAGE_05_SOURCE_OF_TRUTH.md)
- [Stage 05 Implementation Plan](08-implementation/STAGE_05_IMPLEMENTATION_PLAN.md)
- [Stage 05 SDD](08-implementation/STAGE_05_SDD.md)
- [Stage 05 BDD](08-implementation/STAGE_05_BDD.md)
- [Stage 05 Module Index](08-implementation/STAGE_05_MODULE_INDEX.md)
- [Stage 05 API Contract](08-implementation/STAGE_05_API_CONTRACT.md)
- [Stage 05 Database And Migration Design](08-implementation/STAGE_05_DATABASE_AND_MIGRATION_DESIGN.md)
- [Stage 05 Security And Permission Design](08-implementation/STAGE_05_SECURITY_AND_PERMISSION_DESIGN.md)
- [Stage 05 Test Plan](08-implementation/STAGE_05_TEST_PLAN.md)
- [Stage 05 Operations Runbook](08-implementation/STAGE_05_OPERATIONS_RUNBOOK.md)
- [Stage 05 Pre-Staging Approval Packet](08-implementation/STAGE_05_PRE_STAGING_APPROVAL_PACKET.md)
- [Stage 05 Risk Register](08-implementation/STAGE_05_RISK_REGISTER.md)
- [Stage 05 Acceptance Checklist](08-implementation/STAGE_05_ACCEPTANCE_CHECKLIST.md)
- [Stage 05 Local Acceptance Audit](08-implementation/STAGE_05_LOCAL_ACCEPTANCE_AUDIT.md)
- [Stage 05 Development Detail Completion Audit](08-implementation/STAGE_05_DEVELOPMENT_DETAIL_COMPLETION_AUDIT.md)
- [Stage 05 Requirement Traceability Audit](08-implementation/STAGE_05_REQUIREMENT_TRACEABILITY_AUDIT.md)
- [Stage 05 Progress](08-implementation/STAGE_05_PROGRESS.md)
- [Stage 05 Final Acceptance Report](08-implementation/STAGE_05_FINAL_ACCEPTANCE_REPORT.md)
- [Stage 06 LarkSuite Benchmark Audit](08-implementation/STAGE_06_LARKSUITE_BENCHMARK_AUDIT.md)
- [Stage 06 Source Of Truth](08-implementation/STAGE_06_SOURCE_OF_TRUTH.md)
- [Stage 06 Implementation Plan](08-implementation/STAGE_06_IMPLEMENTATION_PLAN.md)
- [Stage 06 SDD](08-implementation/STAGE_06_SDD.md)
- [Stage 06 API Data Security Contract](08-implementation/STAGE_06_API_DATA_SECURITY_CONTRACT.md)
- [Stage 06 BDD And Acceptance](08-implementation/STAGE_06_BDD_AND_ACCEPTANCE.md)
- [Stage 06 Progress](08-implementation/STAGE_06_PROGRESS.md)
- [Stage 06 Stage Acceptance Report](08-implementation/STAGE_06_STAGE_ACCEPTANCE_REPORT.md)

## Project Boundary

本项目可以重新开发，不必严格依赖 `D:\广告saas` 的既有后端框架、Stage 文档或技术栈。

迁移版立项文档和 Stage02-05 广告业务文档只作为历史背景、实现证据和模板输入；Stage06 active truth 以通用平台文档为准。

## Product Constitution

多维表格是本项目的产品宪法。所有模板、场景、数字员工、工具和执行流程都必须从 workspace、base、table、field、record、view、permission、automation 反推。

所有 workflow 的终点必须是多维表格中的记录、状态、视图、自动化、执行日志或审计事件。只停留在 Telegram 聊天、临时 Agent memory、未落表 JSON 或口头结论里的结果，不算完成。

具体表、字段、视图、权限、自动化、Agent 起点和 workflow 落点以 [Bitable Schema Blueprint](03-modules/BITABLE_SCHEMA_BLUEPRINT.md) 为准。

## Confirmed Baseline

- Backend: Python 3.12+ + FastAPI
- ORM/Migration: SQLAlchemy 2.x + Alembic
- Database: PostgreSQL + pgvector
- Queue: Redis
- Agent orchestration: LangGraph-first
- LLM Provider: OpenRouter-compatible API
- Telegram: Bot API + Webhook + Mini App
