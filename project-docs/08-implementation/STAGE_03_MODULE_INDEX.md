# Stage 03 Module Index

## Status

- Document status: active module index
- Scope: Stage 03 复杂模块索引、模块边界、对应设计文档、预计实现文件和验收入口。
- Current Progress: 2026-07-06 根据用户要求补齐 Stage 03 阶段级模块索引。当前只写文档，不进入代码实现。

## 1. Module Reading Rule

Stage 03 开发前先看本索引，确认要改的内容属于哪个模块边界。

如果一个需求跨越多个模块，必须先确认它是否仍属于 Stage 03：

- 属于 Stage 03：在对应模块文档中补充接口、状态、权限和测试映射，再开发。
- 不属于 Stage 03：记录为后续阶段候选，不顺手开发。

## 2. Module Index

| Module | Complexity | Module Doc | Primary Future Files | Tests | Stage |
| --- | --- | --- | --- | --- | --- |
| Stage Gate And Config | medium | `STAGE_03_BACKEND_INTEGRATION_PLAN.md#3-phase-030-documentation-and-stage-gate` | `backend/app/core/config.py`, env docs | config unit tests | 03.0 |
| Tencent Cloud Staging | high | `STAGE_03_TENCENT_CLOUD_STAGING_DEPLOYMENT.md`, `STAGE_03_OPERATIONS_RUNBOOK.md` | compose/caddy docs or deployment files | manual staging rehearsal | 03.1 |
| Telegram Webhook Ingress | high | `modules/STAGE_03_TELEGRAM_WEBHOOK_INGRESS.md` | `backend/app/api/routes/telegram_webhook.py`, `backend/app/schemas/telegram_webhook.py`, `backend/app/services/telegram_ingestion.py` | webhook integration tests | 03.2 |
| Customer Binding And Telegram Inbox | high | `modules/STAGE_03_CUSTOMER_BINDING_AND_INBOX.md` | `backend/app/models/telegram.py`, `backend/app/services/customer_binding.py`, `backend/app/services/bitable_views.py` | binding and inbox view tests | 03.3 |
| Outbox To Redis Streams Worker | high | `modules/STAGE_03_REDIS_STREAMS_WORKER.md` | `backend/app/queues/redis_streams.py`, `backend/app/workers/runner.py`, `backend/app/workers/handlers.py` | queue bridge and worker tests | 03.4 |
| API Contract | medium | `STAGE_03_API_CONTRACT.md` | API route/schema files | route contract tests | 03.2 |
| Database And Migration | high | `STAGE_03_DATABASE_AND_MIGRATION_DESIGN.md` | models and Alembic versions | metadata/migration tests | 03.2 / 03.3 / 03.4 |
| Security And Permission | high | `STAGE_03_SECURITY_AND_PERMISSION_DESIGN.md` | config, webhook validation, view masking, audit service | invalid secret, allowlist, masking tests | 03.2 / 03.3 |
| Test And Acceptance | high | `STAGE_03_TEST_PLAN.md`, `STAGE_03_ACCEPTANCE_CHECKLIST.md` | test files | focused + full test suite | all |
| Risk Management | medium | `STAGE_03_RISK_REGISTER.md` | docs and issue tracking | checklist review | all |

## 3. Module Boundary Rules

- Webhook route can validate request and call services, but cannot write business state directly.
- Customer binding service can resolve customer mapping, but cannot create unrelated customer records.
- Worker can process Redis Streams jobs, but must mutate business state only through services/UOW.
- Redis Streams is a delivery layer; PostgreSQL outbox remains the source of truth.
- Bitable view service can project state, filter and mask fields, but cannot change workflow state.
- Security validation must happen before business row creation.
- Audit evidence must be written for accepted messages, rejected security events where safe, retries and dead letters.

## 4. Complex Module Split Rule

The following modules require independent module docs before implementation:

- Telegram Webhook Ingress.
- Customer Binding And Telegram Inbox.
- Outbox To Redis Streams Worker.
- Tencent Cloud Staging Deployment.
- Security And Permission.
- Database And Migration.

Module docs must include:

- Scope.
- Inputs.
- Outputs.
- State machine.
- Data/Bitable endpoint.
- Permissions and security.
- Dependencies.
- What it does not do.
- Failure handling.
- Tests.
- Acceptance Criteria.

## 5. No-Crossing Rules

- Route 不写业务规则。
- Service 不绕过 audit。
- Worker 不直接写核心表。
- Redis 不替代 PostgreSQL outbox 真源。
- View API 不写业务状态。
- Agent/LLM 不进入 Stage 03 第一批关键链路。
- External provider 不进入 Stage 03 第一批关键链路。
