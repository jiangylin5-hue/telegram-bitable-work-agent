# Telegram 多维表格和工作智能体项目文档

## Status

- Document status: active project document index
- Current project mode: Stage 04 local implementation audited, staging rehearsal pending
- Current Progress: 2026-07-07 Stage 02 已冻结关闭；Stage 03 已完成真实腾讯云 staging 验收。Stage 04 文档已确认，Tasks 1-9 已本地实现并通过 `pytest tests -q`（172 passed / 17 skipped）；本地验收审计见 `STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md`。Task 10 Tencent Cloud staging rehearsal 已获用户确认进入，仍只允许按 allowlisted test chat 做受控测试发送，禁止客户群发、LLM、provider 和生产切换。

## Document Map

### Governance

- [Implementation Source Of Truth](00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md)
- [Technical Decisions](00-governance/TECHNICAL_DECISIONS.md)

### Research

- [飞书多维表格与多维表格智能体调研](00-research/FEISHU_BITABLE_AND_AGENT_RESEARCH.md)

### Product

- [迁移版立项文档：Multidimensional Table And Agent Project Initiation](01-product/MULTIDIMENSIONAL_AGENT_PROJECT_INITIATION.md)
- [Telegram 多维表格和工作智能体新项目产品简报](01-product/TELEGRAM_MULTIDIMENSIONAL_AGENT_NEW_PROJECT_BRIEF.md)
- [Business Scenarios Index](01-product/BUSINESS_SCENARIOS_INDEX.md)
- [Recharge Workflow](01-product/scenarios/RECHARGE_WORKFLOW.md)
- [Account Inventory Workflow](01-product/scenarios/ACCOUNT_INVENTORY_WORKFLOW.md)
- [BM Invite And Account Production](01-product/scenarios/BM_INVITE_AND_ACCOUNT_PRODUCTION.md)
- [Card Platform Workflow](01-product/scenarios/CARD_PLATFORM_WORKFLOW.md)
- [Customer Daily Reporting](01-product/scenarios/CUSTOMER_DAILY_REPORTING.md)
- [Spend Risk Statistics](01-product/scenarios/SPEND_RISK_STATISTICS.md)

### Architecture

- [SDD Backend Architecture](02-architecture/SDD_BACKEND_ARCHITECTURE.md)
- [Multi-Agent Orchestration](02-architecture/MULTI_AGENT_ORCHESTRATION.md)

### Modules

- [Telegram Ingestion Module](03-modules/TELEGRAM_INGESTION_MODULE.md)
- [Bitable Schema Blueprint](03-modules/BITABLE_SCHEMA_BLUEPRINT.md)
- [Multidimensional Table Module](03-modules/MULTIDIMENSIONAL_TABLE_MODULE.md)
- [Service Draft And Confirmation Module](03-modules/SERVICE_DRAFT_AND_CONFIRMATION_MODULE.md)

### Agents

- [Agents Index](04-agents/AGENTS_INDEX.md)
- [Operations Supervisor Agent](04-agents/OPERATIONS_SUPERVISOR_AGENT.md)
- [Message Intake Router Agent](04-agents/MESSAGE_INTAKE_ROUTER_AGENT.md)
- [Account Inventory Agent](04-agents/ACCOUNT_INVENTORY_AGENT.md)
- [Recharge And Binding Agent](04-agents/RECHARGE_AND_BINDING_AGENT.md)
- [Finance Reconciliation Agent](04-agents/FINANCE_RECONCILIATION_AGENT.md)
- [Card Resource Agent](04-agents/CARD_RESOURCE_AGENT.md)
- [Customer Reporting Agent](04-agents/CUSTOMER_REPORTING_AGENT.md)

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

## Project Boundary

本项目可以重新开发，不必严格依赖 `D:\广告saas` 的既有后端框架、Stage 文档或技术栈。

迁移版立项文档只作为业务背景、场景边界和产品方向参考；本项目后续应重新确认技术选型、系统架构、权限模型、数据库 schema、Agent 编排和实现阶段。

## Product Constitution

多维表格是本项目的底层参照。所有业务场景、Agent、工具和执行流程都必须从多维表格的 table、field、linked record、view、permission、automation 反推。

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
