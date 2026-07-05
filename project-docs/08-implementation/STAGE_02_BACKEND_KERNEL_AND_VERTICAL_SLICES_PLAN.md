# Stage 02 Backend Kernel And Vertical Slices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable backend kernel for the Telegram Bitable work-agent system, then deliver three vertical slices: recharge, account inventory, and customer/company daily reporting.

**Architecture:** Start with a small FastAPI + SQLAlchemy + Alembic backend that treats Bitable views as the business operation layer and PostgreSQL as the fact layer. Use mock Telegram webhook and mock/sandbox execution adapters first; real Telegram and real provider writes are intentionally excluded from Stage 02.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL, pgvector-ready schema, Redis, pytest, OpenRouter-compatible LLM client behind an interface.

---

## Status

- Document status: active implementation plan draft
- Scope: Stage 02 backend kernel, mock Telegram ingestion, Bitable view API, service draft confirmation, outbox, recharge vertical slice, account inventory vertical slice, daily reporting vertical slice
- Current Progress: 2026-07-05 扩展 Stage 02 bounded online PostgreSQL smoke：`tests/integration/test_online_postgres_smoke.py` 使用 disposable PostgreSQL 验证 Alembic online `upgrade head` 到 `20260705_0009`、mock Telegram API 真实落库与跨 session 幂等、DB-backed `agent.intent_extract` 生成 draft、Bitable view 从真实 rows 回读、`audit_view` 从真实 `ops_audit_events` 投影、`recharge_view` sales actor scoped/masked readback、customer report stale_data/risk_event persistence、confirmation success、Agent confirmation denial、customer report sales scoped-denial 和 company report sales denial 的 API/DB 事务边界、reporting API 提交、business write + outbox event rollback 原子性、inventory/recharge service 状态跃迁、readback failure 的 `customer.reply` mock outbox、database-backed outbox dispatcher success/retry/dead_letter；最新 online smoke 为 17 passed、全量 `pytest tests -v` 102 passed、Alembic offline SQL 到 `20260705_0009`、AST_OK 93 files。继续按本文档、SDD、BDD 核对剩余未证明项；该 smoke 不等于生产数据库认证，真实 Telegram/provider/OpenRouter 仍不在 Stage 02 范围。

## 1. Confirmed Stage 02 Decisions

| Decision | Selected option | Meaning |
| --- | --- | --- |
| Stage 02 business scope | A+B+C | 充值闭环、账户库存、客户/公司日报都进入 Stage 02，但按切片顺序交付 |
| Telegram integration | A | 先 mock webhook，不直接接真实 Telegram Bot |
| Provider execution | A | 先 mock/sandbox adapter，不接真实 Meta/卡台/充值 provider |
| Multi-tenancy | A | 第一版不做 `tenant_id`，按单公司内部系统建模 |
| DB + Redis consistency | A | 第一版采用 outbox table，保证事务提交和异步任务投递一致 |

## 2. Stage 02 Delivery Shape

Stage 02 不同时铺开所有业务代码，而是分成 4 个连续增量：

```text
02.0 Backend Kernel
-> 02.1 Recharge Vertical Slice
-> 02.2 Account Inventory Vertical Slice
-> 02.3 Customer And Company Daily Report Vertical Slice
```

每个增量都必须满足：

- 数据写入 PostgreSQL。
- 业务结果出现在 Bitable view API。
- 关键状态变化写 `ops_audit_events`。
- 异步任务通过 outbox 进入 worker。
- 测试覆盖状态机、权限、幂等和失败路径。

## 3. Stage 02 Non-Goals

- 不接真实 Telegram Bot。
- 不接真实 Meta/BM/卡台/充值 provider。
- 不做真实资金或账户写入。
- 不做多租户 `tenant_id`。
- 不做完整前端，只提供 Bitable-like API 和最小确认 API。
- 不做完整 LLM 智能体能力，先用 deterministic mock agent / fake model 跑通工具边界。
- 不做完整财务账本、发票、对账单、结算。

## 4. Document Inputs

开发时只需要优先读这些文档：

1. [AGENTS.md](../../AGENTS.md)
2. [Implementation Source Of Truth](../00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md)
3. [Technical Decisions](../00-governance/TECHNICAL_DECISIONS.md)
4. [Bitable Schema Blueprint](../03-modules/BITABLE_SCHEMA_BLUEPRINT.md)
5. [SDD Backend Architecture](../02-architecture/SDD_BACKEND_ARCHITECTURE.md)
6. [PostgreSQL Database Design](../05-data/POSTGRES_DATABASE_DESIGN.md)
7. [Permission And Security Model](../05-data/PERMISSION_AND_SECURITY_MODEL.md)
8. [Redis Queue And Worker Design](../06-queue/REDIS_QUEUE_AND_WORKER_DESIGN.md)

Scenario and Agent docs are supporting references, not daily entry points.

## 5. Proposed Repository Structure

```text
backend/
  app/
    main.py
    core/
      config.py
      database.py
      errors.py
      logging.py
      security.py
    models/
      base.py
      users.py
      customers.py
      telegram.py
      bitable.py
      service.py
      accounts.py
      recharge.py
      reporting.py
      audit.py
      outbox.py
      agent.py
    schemas/
      common.py
      views.py
      telegram.py
      service_drafts.py
      recharge.py
      inventory.py
      reports.py
    repositories/
      base.py
      views.py
      messages.py
      service_drafts.py
      recharge.py
      inventory.py
      reports.py
      outbox.py
    services/
      permissions.py
      audit.py
      outbox.py
      bitable_views.py
      telegram_ingestion.py
      service_drafts.py
      confirmation.py
      execution_tickets.py
      recharge.py
      account_inventory.py
      reporting.py
    agents/
      interfaces.py
      mock_router.py
      mock_reporting.py
    workers/
      runner.py
      outbox_dispatcher.py
      handlers.py
    adapters/
      telegram_mock.py
      providers_mock.py
      llm_openrouter.py
      llm_fake.py
    api/
      deps.py
      routes/
        health.py
        views.py
        mock_telegram.py
        service_drafts.py
        confirmations.py
        inventory.py
        reports.py
  alembic/
  tests/
    unit/
    integration/
  pyproject.toml
  alembic.ini
```

## 6. Implementation Tasks

### Task 1: Project Skeleton And Test Harness

**Files:**

- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/tests/unit/test_health.py`

- [x] Create the backend package and pytest setup.
- [x] Add FastAPI app factory and `/health` route.
- [x] Add settings object with `DATABASE_URL`, `REDIS_URL`, `APP_ENV`, `OPENROUTER_API_KEY`.
- [x] Write `test_health_returns_ok`.
- [x] Run `pytest backend/tests/unit/test_health.py -v`.
- [x] Acceptance: test passes and no database is required for health check.

### Task 2: SQLAlchemy Base, Alembic, And Core Models

**Files:**

- Create: `backend/app/models/base.py`
- Create: `backend/app/models/users.py`
- Create: `backend/app/models/customers.py`
- Create: `backend/app/models/telegram.py`
- Create: `backend/app/models/audit.py`
- Create: `backend/app/models/outbox.py`
- Create: `backend/alembic/env.py`
- Create: first Alembic migration
- Test: `backend/tests/unit/test_model_metadata.py`

- [x] Define UUID primary key mixin and timestamp mixin.
- [x] Implement `users`, `telegram_identities`, `customers`, `customer_groups`, `messages`, `ops_audit_events`, `outbox_events`.
- [x] Add outbox fields: `id`, `event_type`, `aggregate_type`, `aggregate_id`, `payload`, `status`, `attempt_count`, `available_at`, `processed_at`, `last_error`, `created_at`.
- [x] Write metadata test that asserts all expected tables exist in SQLAlchemy metadata.
- [x] Run metadata test.
- [x] Acceptance: metadata contains core tables and migration imports models without error.

### Task 3: Bitable View API Kernel

**Files:**

- Create: `backend/app/models/bitable.py`
- Create: `backend/app/schemas/views.py`
- Create: `backend/app/services/bitable_views.py`
- Create: `backend/app/api/routes/views.py`
- Test: `backend/tests/unit/test_bitable_views.py`

- [x] Implement `table_views`, `view_columns`, `view_filters`, `field_permissions`, `automation_rules` models.
- [x] Define static view registry for Stage 02 views: `telegram_inbox`, `ai_draft_queue`, `recharge_view`, `account_inventory`, `customer_daily_reports`, `company_daily_reports`, `audit_view`.
- [x] Implement `GET /views/{view_key}/records` service contract.
- [x] Apply field masking rules in response builder.
- [x] Write tests for unknown view, allowed view, and masked sensitive fields.
- [x] Implement `SqlAlchemyBitableViewDataSource` that reads registered SQLAlchemy metadata tables into Bitable-shaped records.
- [x] Wire default `/views` dependency to SQLAlchemy session while preserving dependency overrides for offline tests.
- [x] Write tests for SQLAlchemy-backed row reads, unknown physical table no-op, and default dependency wiring.
- [x] Add bounded online PostgreSQL smoke for Alembic online migration, mock Telegram API persistence, SQLAlchemy-backed Bitable view readback, and confirmation transaction persistence.
- [x] Preserve `ai_draft_queue.intent_type` view output while mapping real `service_drafts.draft_type` from PostgreSQL rows.
- [x] Wire route actor context into view response building.
- [x] Filter customer-scoped records by actor `customer_ids`.
- [x] Apply role-based field permission masking on top of view sensitive fields.
- [x] Align `recharge_view` projection with real `recharge_records` status columns: `collection_status`, `execution_status`, `readback_status`.
- [x] Add online PostgreSQL smoke proving sales actor scope/masking over real `recharge_view` rows.
- [x] Acceptance: every Stage 02 business result can be retrieved through a view-shaped response.

### Task 4: Permission And Audit Kernel

**Files:**

- Create: `backend/app/services/permissions.py`
- Create: `backend/app/services/audit.py`
- Create: `backend/app/api/deps.py`
- Test: `backend/tests/unit/test_permissions.py`
- Test: `backend/tests/unit/test_audit.py`

- [x] Implement simple Stage 02 actor model: `sales`, `production`, `finance`, `manager`, `admin`, `agent`.
- [x] Implement record scope by `customer_id` only; do not add `tenant_id` columns in Stage 02.
- [x] Implement field permission masking for amount, balance, spend, payment profile, failure reason, raw Telegram text.
- [x] Implement audit event creation helper.
- [x] Test permission allow/deny and audit event payload.
- [x] Acceptance: no service writes business state without audit/status evidence available for Stage 02 write paths.

### Task 5: Outbox Dispatcher

**Files:**

- Create: `backend/app/services/outbox.py`
- Create: `backend/app/repositories/outbox.py`
- Create: `backend/app/workers/outbox_dispatcher.py`
- Create: `backend/app/workers/handlers.py`
- Test: `backend/tests/unit/test_outbox.py`

- [x] Implement `enqueue_outbox_event` inside DB transaction.
- [x] Implement dispatcher that reads pending events and calls in-process handlers for Stage 02.
- [x] Implement `SqlAlchemyOutboxRepository` for database-backed ready-event reads and dispatcher status persistence.
- [x] Add online PostgreSQL rollback smoke proving business row and outbox event disappear together when the transaction rolls back.
- [x] Implement retry counters and dead-letter status.
- [x] Add online PostgreSQL smoke for DB-backed retry -> dead_letter and `outbox_dead_letter` audit persistence.
- [x] Test event creation, successful dispatch, retryable failure, dead letter.
- [x] Acceptance: DB commit and async intent are represented by outbox rows before any worker action.

### Task 6: Mock Telegram Ingestion

**Files:**

- Create: `backend/app/schemas/telegram.py`
- Create: `backend/app/services/telegram_ingestion.py`
- Create: `backend/app/api/routes/mock_telegram.py`
- Test: `backend/tests/unit/test_telegram_ingestion.py`
- Test: `backend/tests/integration/test_mock_telegram_to_message.py`

- [x] Implement `POST /mock/telegram/updates`.
- [x] Store `messages` with idempotency on `telegram_update_id` and `telegram_chat_id + telegram_message_id`.
- [x] Link known `customer_groups`.
- [x] Create outbox event `agent.intent_extract`.
- [x] Test duplicate update does not create duplicate message or event.
- [x] Add online PostgreSQL smoke proving duplicate update idempotency across separate API requests and DB sessions.
- [x] Acceptance: mock Telegram message appears in `telegram_inbox` view and queues intent extraction.

### Task 7: Mock Message Router Agent

**Files:**

- Create: `backend/app/agents/interfaces.py`
- Create: `backend/app/agents/mock_router.py`
- Modify: `backend/app/workers/handlers.py`
- Test: `backend/tests/unit/test_mock_router_agent.py`

- [x] Implement deterministic intent extraction for recharge, account inventory request, and report request.
- [x] Return structured result with `intent_type`, `customer_id`, `amount`, `currency`, `account_hint`, `missing_fields`, `confidence`.
- [x] Update message `intent_status`.
- [x] Create draft through service layer, not directly from worker.
- [x] Add online PostgreSQL smoke proving DB-backed `agent.intent_extract` creates draft, updates message intent fields, writes audit and appears in `ai_draft_queue`.
- [x] Test recharge phrase creates recharge draft.
- [x] Test ambiguous phrase enters `needs_review`.
- [x] Acceptance: Agent starts from `messages` and lands on `service_drafts` / message status.

### Task 8: Service Draft And Confirmation Kernel

**Files:**

- Create: `backend/app/models/service.py`
- Create: `backend/app/schemas/service_drafts.py`
- Create: `backend/app/services/service_drafts.py`
- Create: `backend/app/services/confirmation.py`
- Create: `backend/app/services/execution_tickets.py`
- Create: `backend/app/api/routes/service_drafts.py`
- Create: `backend/app/api/routes/confirmations.py`
- Test: `backend/tests/unit/test_service_draft_state_machine.py`

- [x] Implement `service_drafts`, `service_records`, `execution_tickets`.
- [x] Implement draft states: `draft`, `needs_more_info`, `pending_confirmation`, `rejected`, `confirmed`, `manual_review`, `blocked`.
- [x] Wire service draft list API default UOW to SQLAlchemy session while keeping tests dependency-overridable.
- [x] Implement confirmation actions: confirm, reject, request_more_info, escalate.
- [x] Wire confirmation API default UOW to SQLAlchemy session while keeping tests dependency-overridable.
- [x] Commit confirmation API successful write actions through the UOW before returning.
- [x] Prevent `agent` actor from confirming.
- [x] Issue `execution_ticket` only after allowed human confirmation.
- [x] Test confirm path, reject path, agent cannot confirm, ticket single-use constraints.
- [x] Acceptance: no executable action exists without human confirmation and ticket.

### Task 9: Recharge Vertical Slice

**Files:**

- Create: `backend/app/models/recharge.py`
- Create: `backend/app/schemas/recharge.py`
- Create: `backend/app/services/recharge.py`
- Create: `backend/app/adapters/providers_mock.py`
- Test: `backend/tests/unit/test_recharge_flow.py`
- Test: `backend/tests/integration/test_recharge_vertical_slice.py`

- [x] Implement `collection_records`, `recharge_records`, `execution_logs`.
- [x] Implement finance confirmation as separate state from recharge execution.
- [x] Implement mock recharge execution adapter.
- [x] Implement `SqlAlchemyRechargeUnitOfWork` for database-backed recharge, collection, execution log, outbox and audit writes.
- [x] Implement readback status separately from execution status.
- [x] Add outbox handlers for `execution.recharge` and `readback.balance`.
- [x] Add `customer.reply` mock outbox for readback failure wording without sending real Telegram messages.
- [x] Reject readback failure marking before execution has succeeded to avoid misleading customer replies.
- [x] Test collection confirmed does not mean recharge succeeded.
- [x] Test confirmed recharge creates execution log through mock adapter.
- [x] Acceptance: mock Telegram recharge request can reach execution log and readback state through APIs and views.

### Task 10: Account Inventory Vertical Slice

**Files:**

- Create: `backend/app/models/accounts.py`
- Create: `backend/app/schemas/inventory.py`
- Create: `backend/app/services/account_inventory.py`
- Create: `backend/app/api/routes/inventory.py`
- Test: `backend/tests/unit/test_account_inventory.py`
- Test: `backend/tests/integration/test_inventory_assignment_slice.py`

- [x] Implement `account_inventory`, `account_assignments`, `account_status_events`, minimal `account_assets`.
- [x] Implement create inventory account.
- [x] Implement list unused accounts through Bitable view.
- [x] Implement assignment proposal.
- [x] Require human confirmation before `assignment_status = confirmed`.
- [x] Write status event on production, assignment, activation.
- [x] Wire inventory API default UOW to SQLAlchemy session while keeping tests dependency-overridable.
- [x] Acceptance: can answer unused accounts, assigned customer, and current inventory status from API and Bitable-shaped views.

### Task 11: Customer And Company Daily Report Slice

**Files:**

- Create: `backend/app/models/reporting.py`
- Create: `backend/app/schemas/reports.py`
- Create: `backend/app/services/reporting.py`
- Create: `backend/app/api/routes/reports.py`
- Create: `backend/app/agents/mock_reporting.py`
- Test: `backend/tests/unit/test_reporting.py`
- Test: `backend/tests/integration/test_daily_report_slice.py`

- [x] Implement `account_daily_metrics`, `risk_events`, `customer_daily_reports`, `company_daily_reports`.
- [x] Generate customer report from account metrics and risk events.
- [x] Extend customer and company reports with date-aligned `recharge_records` facts.
- [x] Extend reports with real `account_card_bindings` state after that Stage 02 fact table exists; if a customer/date has no binding facts, payload explicitly marks `card_binding_state.status = not_available_in_stage_02`.
- [x] Generate company report from all customers.
- [x] Include `freshness_at` and source references for every metric.
- [x] Mark stale data explicitly.
- [x] Add online PostgreSQL smoke proving stale spend remains unknown and creates persisted risk/audit evidence.
- [x] Wire report API default UOW to SQLAlchemy session while keeping tests dependency-overridable.
- [x] Commit report API successful write actions through the UOW before returning.
- [x] Acceptance: can generate per-customer and company daily reports without leaking other customer data.

### Task 12: OpenRouter Interface Behind Feature Flag

**Files:**

- Create: `backend/app/adapters/llm_openrouter.py`
- Create: `backend/app/adapters/llm_fake.py`
- Modify: `backend/app/agents/interfaces.py`
- Test: `backend/tests/unit/test_llm_adapters.py`

- [x] Define LLM client interface with structured JSON output.
- [x] Implement fake deterministic client as test default.
- [x] Implement OpenRouter-compatible adapter without making it required in tests.
- [x] Ensure model name and prompt version are recorded in `agent_runs`.
- [x] Acceptance: tests run without OpenRouter key, production config can use OpenRouter later.

### Task 13: Stage 02 End-To-End Acceptance Flow

**Files:**

- Create: `backend/tests/integration/test_stage_02_e2e.py`
- Create: `project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md`

- [x] Write E2E test for mock Telegram recharge message to draft.
- [x] Extend E2E to human confirmation and mock execution.
- [x] Extend E2E to inventory creation and assignment.
- [x] Extend E2E to daily report generation.
- [x] Write Stage 02 acceptance checklist with commands and expected results.
- [x] Acceptance: one command can verify Stage 02 critical path.

## 7. Recommended Execution Order

1. Task 1-5: backend kernel.
2. Task 6-8: message to draft to confirmation.
3. Task 9: recharge vertical slice.
4. Task 10: account inventory vertical slice.
5. Task 11: customer/company daily report vertical slice.
6. Task 12: OpenRouter adapter behind feature flag.
7. Task 13: end-to-end acceptance.

## 8. Stage 02 Acceptance Criteria

- Mock Telegram message can create a `messages` record.
- Intent extraction can create `service_drafts`.
- Bitable view API can show Telegram inbox, AI draft queue, recharge view, account inventory view, customer report view, company report view, and audit view.
- Human confirmation can create `service_records` and `execution_tickets`.
- Mock recharge execution can create `execution_logs`.
- Recharge execution and balance readback are separate statuses.
- Account inventory can answer unused accounts, assigned accounts, assigned customer, current status.
- Customer daily report can aggregate account daily metrics with freshness.
- Company daily report can aggregate all customers for manager/admin.
- Outbox table is used before worker dispatch.
- Tests prove agent cannot self-confirm.
- Tests prove no raw card / CVV fields exist.

## 9. Open Items Deferred Beyond Stage 02

- Real Telegram Bot webhook.
- Real Meta/BM/card/recharge provider adapters.
- Telegram Mini App UI.
- Real OpenRouter prompt optimization and model routing.
- Multi-tenant `tenant_id`.
- Temporal migration.
- Advanced vector retrieval and historical SOP retrieval.

## 10. Stage 02 Phase Execution Manual

本节是实际开发时的执行手册。开发必须按阶段顺序推进，不允许跳阶段实现后面的业务。

每个子阶段完成时必须更新：

- [Stage 02 Source Of Truth](STAGE_02_SOURCE_OF_TRUTH.md) 的 `Current Progress`。
- [Stage 02 Progress](STAGE_02_PROGRESS.md) 的进度记录。
- 本文档对应 checkbox。

### Phase 0: Repository And Stage Controls

Goal: 让项目具备可追踪的 Git 状态和阶段执行入口。

Does:

- 初始化 Git。
- 建立 Stage 02 文档入口。
- 确认后续开发只从 `08-implementation` 进入。

Does not:

- 不写业务代码。
- 不安装依赖。
- 不创建迁移。

#### Subphase 0.1: Git Repository Initialization

| Item | Detail |
| --- | --- |
| What to do | 初始化当前目录为有效 Git 仓库 |
| Files changed | `.git/` metadata only |
| Not do | 不提交、不删除已有文件、不重置工作区 |
| Expected result | `git status --short` 可正常输出 |
| Acceptance | Git 不再报 `not a git repository` |
| Verification | `git status --short` |

Steps:

- [x] Inspect `.git` state.
- [x] Run `git init`.
- [x] Run `git status --short`.

#### Subphase 0.2: Stage Documentation Controls

| Item | Detail |
| --- | --- |
| What to do | 建立 Stage 02 source、progress、SDD、BDD、module index |
| Files changed | `project-docs/08-implementation/*` |
| Not do | 不修改业务 schema 之外的旧文档含义 |
| Expected result | Stage 02 有唯一执行入口 |
| Acceptance | README、source、plan、SDD、BDD、module index 均存在 |
| Verification | `rg -n "Stage 02" project-docs/08-implementation` |

Steps:

- [x] Create `STAGE_02_SOURCE_OF_TRUTH.md`.
- [x] Create `STAGE_02_PROGRESS.md`.
- [x] Create `STAGE_02_SDD.md`.
- [x] Create `STAGE_02_BDD.md`.
- [x] Create `STAGE_02_MODULE_INDEX.md`.

### Phase 1: Backend Kernel

Goal: 建立最小可运行 FastAPI 后端、测试框架、数据库模型基础和迁移基础。

Does:

- 创建 `backend/` 项目。
- 创建健康检查。
- 创建 SQLAlchemy base。
- 创建 Alembic 配置。
- 创建核心表模型。

Does not:

- 不实现业务流程。
- 不接 Telegram。
- 不接 provider。
- 不调用 OpenRouter。

#### Subphase 1.1: FastAPI Skeleton

| Item | Detail |
| --- | --- |
| What to do | 建立最小 FastAPI app 和测试框架 |
| Files changed | `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/api/routes/health.py`, `backend/tests/unit/test_health.py` |
| Not do | 不连接数据库、不建业务表 |
| Expected result | `/health` 可测试 |
| Acceptance | pytest health test 通过 |
| Verification | `cd backend; pytest tests/unit/test_health.py -v` |

Substeps:

- [x] Create package directories.
- [x] Add `pyproject.toml` with FastAPI, pytest, SQLAlchemy, Alembic dependencies.
- [x] Implement `create_app()`.
- [x] Register `/health`.
- [x] Write `test_health_returns_ok`.
- [x] Run health test.
- [x] Update `STAGE_02_PROGRESS.md`.

#### Subphase 1.2: Database Base And Alembic

| Item | Detail |
| --- | --- |
| What to do | 建立 SQLAlchemy base、session、Alembic env |
| Files changed | `backend/app/core/database.py`, `backend/app/models/base.py`, `backend/alembic/env.py`, `backend/alembic.ini` |
| Not do | 不写所有业务逻辑，不手工改生产数据库 |
| Expected result | Alembic 能导入 metadata |
| Acceptance | metadata test 通过，migration smoke 可运行 |
| Verification | `cd backend; pytest tests/unit/test_model_metadata.py -v` |

Substeps:

- [x] Write metadata test first.
- [x] Implement base model mixins.
- [x] Implement DB session factory.
- [x] Configure Alembic env to import metadata.
- [x] Run metadata test.
- [x] Update progress.

#### Subphase 1.3: Core Models

| Item | Detail |
| --- | --- |
| What to do | 实现 Stage 02 核心事实表 |
| Files changed | `backend/app/models/users.py`, `customers.py`, `telegram.py`, `audit.py`, `outbox.py` |
| Not do | 不实现 recharge/inventory/report 细节 |
| Expected result | core tables in metadata |
| Acceptance | metadata contains users/customers/messages/audit/outbox |
| Verification | `cd backend; pytest tests/unit/test_model_metadata.py -v` |

Substeps:

- [x] Add `users`.
- [x] Add `telegram_identities`.
- [x] Add `customers`.
- [x] Add `customer_groups`.
- [x] Add `messages`.
- [x] Add `ops_audit_events`.
- [x] Add `outbox_events`.
- [x] Run metadata test.
- [x] Create migration.
- [x] Run migration smoke.
- [x] Update progress.

### Phase 2: Bitable, Permission, Audit, Outbox Kernel

Goal: 建立所有业务切片共享的多维表格操作层和异步可靠投递层。

Does:

- Bitable view API。
- 字段权限过滤。
- 审计记录。
- outbox 事务内写入和 dispatcher。

Does not:

- 不实现具体业务动作。
- 不接真实 Redis 前绕过 outbox。

#### Subphase 2.1: Bitable View API

| Item | Detail |
| --- | --- |
| What to do | 实现 `GET /views/{view_key}/records` |
| Files changed | `models/bitable.py`, `schemas/views.py`, `services/bitable_views.py`, `api/routes/views.py` |
| Not do | view API 不写业务状态 |
| Expected result | 能返回 Stage 02 view-shaped response |
| Acceptance | unknown view、allowed view、masked field tests pass |
| Verification | `cd backend; pytest tests/unit/test_bitable_views.py -v` |

Substeps:

- [x] Write tests for known/unknown views.
- [x] Define static Stage 02 view registry.
- [x] Implement view response schema.
- [x] Implement field masking hook.
- [x] Add SQLAlchemy-backed data source over registered metadata tables.
- [x] Wire default route dependency to SQLAlchemy session while keeping tests dependency-overridable.
- [x] Apply actor record scope and role-based field masking in view route.
- [x] Project recharge collection/execution/readback status fields.
- [x] Add route.
- [x] Run unit tests.
- [x] Update progress.

#### Subphase 2.2: Permission And Audit

| Item | Detail |
| --- | --- |
| What to do | 实现角色、字段权限、审计 helper |
| Files changed | `services/permissions.py`, `services/audit.py`, `api/deps.py` |
| Not do | 不做 `tenant_id`，不做真实登录 |
| Expected result | service 可调用统一权限和 audit |
| Acceptance | permission denied writes audit |
| Verification | `cd backend; pytest tests/unit/test_permissions.py tests/unit/test_audit.py -v` |

Substeps:

- [x] Write permission tests.
- [x] Implement Stage 02 actor object.
- [x] Implement customer_id record scope.
- [x] Implement field masking.
- [x] Implement audit helper.
- [x] Run tests.
- [x] Update progress.

#### Subphase 2.3: Outbox

| Item | Detail |
| --- | --- |
| What to do | 实现 outbox event 和 dispatcher |
| Files changed | `services/outbox.py`, `repositories/outbox.py`, `workers/outbox_dispatcher.py`, `workers/handlers.py` |
| Not do | 不直接从 service 调 worker；不绕过 DB transaction |
| Expected result | 业务事务能留下 pending outbox event |
| Acceptance | success/retry/dead_letter tests pass |
| Verification | `cd backend; pytest tests/unit/test_outbox.py -v` |

Substeps:

- [x] Write outbox tests.
- [x] Implement enqueue inside transaction.
- [x] Implement dispatcher.
- [x] Implement retry/dead letter.
- [x] Run tests.
- [x] Update progress.

### Phase 3: Mock Telegram To Service Draft

Goal: 跑通消息入口到 AI 草稿队列。

Does:

- Mock webhook。
- Message ingestion。
- Mock router agent。
- Service draft creation。

Does not:

- 不接真实 Telegram。
- 不确认草稿。
- 不执行 provider。

#### Subphase 3.1: Mock Telegram Ingestion

| Item | Detail |
| --- | --- |
| What to do | 实现 `POST /mock/telegram/updates` |
| Files changed | `schemas/telegram.py`, `services/telegram_ingestion.py`, `api/routes/mock_telegram.py` |
| Not do | 不让 Telegram 身份等于系统权限 |
| Expected result | message 入库并创建 outbox |
| Acceptance | duplicate update idempotent |
| Verification | `cd backend; pytest tests/unit/test_telegram_ingestion.py tests/integration/test_mock_telegram_to_message.py -v` |

Substeps:

- [x] Write duplicate update test.
- [x] Implement mock update schema.
- [x] Implement message insert.
- [x] Implement customer group lookup.
- [x] Enqueue `agent.intent_extract` outbox event.
- [x] Run tests.
- [x] Update progress.

#### Subphase 3.2: Mock Router Agent And Draft Creation

| Item | Detail |
| --- | --- |
| What to do | 用 deterministic mock agent 把消息转 draft |
| Files changed | `agents/interfaces.py`, `agents/mock_router.py`, `services/service_drafts.py`, `workers/handlers.py` |
| Not do | 不调用真实 OpenRouter |
| Expected result | recharge/account/report 意图能创建 draft |
| Acceptance | recharge phrase creates `service_drafts` |
| Verification | `cd backend; pytest tests/unit/test_mock_router_agent.py -v` |

Substeps:

- [x] Write router tests.
- [x] Define agent output schema.
- [x] Implement keyword-based router.
- [x] Update `messages.intent_status`.
- [x] Create draft through service layer.
- [x] Run tests.
- [x] Update progress.

### Phase 4: Confirmation And Recharge Slice

Goal: 完成 mock 充值闭环。

Does:

- Draft confirmation。
- Execution ticket。
- Collection record。
- Recharge record。
- Mock execution。
- Execution log。
- Readback state。

Does not:

- 不接真实 provider。
- 不把收款确认当充值成功。
- 不让 Agent confirm。

#### Subphase 4.1: Draft Confirmation And Ticket

| Item | Detail |
| --- | --- |
| What to do | 实现草稿确认和 execution ticket |
| Files changed | `models/service.py`, `services/confirmation.py`, `services/execution_tickets.py`, `api/routes/confirmations.py` |
| Not do | 不执行外部动作 |
| Expected result | human confirmation creates service/ticket |
| Acceptance | agent cannot confirm; ticket single-use |
| Verification | `cd backend; pytest tests/unit/test_service_draft_state_machine.py -v` |

Substeps:

- [x] Write state machine tests.
- [x] Implement draft state transitions.
- [x] Implement human confirmation.
- [x] Block agent confirmation.
- [x] Issue ticket.
- [x] Run tests.
- [x] Update progress.

#### Subphase 4.2: Recharge Execution And Readback

| Item | Detail |
| --- | --- |
| What to do | 实现 mock 充值执行和 readback |
| Files changed | `models/recharge.py`, `services/recharge.py`, `adapters/providers_mock.py`, `workers/handlers.py` |
| Not do | 不接真实 provider，不保存敏感支付凭证 |
| Expected result | execution log and readback status written |
| Acceptance | execution success and readback failure can be separate |
| Verification | `cd backend; pytest tests/unit/test_recharge_flow.py tests/integration/test_recharge_vertical_slice.py -v` |

Substeps:

- [x] Write recharge tests.
- [x] Implement collection records.
- [x] Implement recharge records.
- [x] Implement mock provider adapter.
- [x] Implement execution handler.
- [x] Implement readback handler.
- [x] Run tests.
- [x] Update progress.

### Phase 5: Account Inventory Slice

Goal: 让系统能管理生产账户、未启用账户、分配客户和状态历史。

Does:

- Inventory account creation。
- Unused account view。
- Assignment proposal。
- Human confirmation。
- Status events。

Does not:

- 不自动分配账户。
- 不接真实 Meta。

#### Subphase 5.1: Inventory Records And Views

| Item | Detail |
| --- | --- |
| What to do | 实现账户库存表和视图 |
| Files changed | `models/accounts.py`, `services/account_inventory.py`, `api/routes/inventory.py` |
| Not do | 不做真实账户 API readback |
| Expected result | unused accounts visible |
| Acceptance | can query unused accounts |
| Verification | `cd backend; pytest tests/unit/test_account_inventory.py -v` |

Substeps:

- [x] Write inventory tests.
- [x] Implement `account_inventory`.
- [x] Implement `account_status_events`.
- [x] Add inventory view mapping.
- [x] Run tests.
- [x] Update progress.

#### Subphase 5.2: Assignment Confirmation

| Item | Detail |
| --- | --- |
| What to do | 实现账户分配建议和确认 |
| Files changed | `services/account_inventory.py`, `models/accounts.py` |
| Not do | 不允许 Agent 无确认分配 |
| Expected result | assignment proposed then confirmed by human |
| Acceptance | allocated status only after confirmation |
| Verification | `cd backend; pytest tests/integration/test_inventory_assignment_slice.py -v` |

Substeps:

- [x] Write assignment integration test.
- [x] Implement assignment proposal.
- [x] Implement confirmation.
- [x] Write status event.
- [x] Run tests.
- [x] Update progress.

#### Subphase 5.3: Inventory Status Query And Activation

| Item | Detail |
| --- | --- |
| What to do | 补齐账户库存按状态/客户查询、激活状态跃迁和 Bitable 库存视图字段 |
| Files changed | `services/account_inventory.py`, `api/routes/inventory.py`, `services/bitable_views.py`, `services/permissions.py` |
| Not do | 不接真实 Meta 账户 readback，不让 Agent 自行激活账户，不新增未验证的库存状态 |
| Expected result | 系统能回答未启用账户、已分配给谁、当前库存状态；`allocated` 账户可由授权人员标记为 `activated` |
| Acceptance | activation 写入 `account_status_events`，API 可按 `status/customer_id` 查询，Bitable-shaped `account_inventory` view 投影客户归属和状态字段 |
| Verification | `cd backend; pytest tests/unit/test_account_inventory.py tests/unit/test_bitable_views.py tests/integration/test_inventory_assignment_slice.py -v` |

Substeps:

- [x] Write account inventory status/customer query tests.
- [x] Write activation status event test.
- [x] Write Agent cannot activate integration test.
- [x] Implement `list_inventory_accounts_by_status`.
- [x] Implement `activate_inventory_account`.
- [x] Add `activate_inventory_account` permission for production/manager/admin only.
- [x] Extend `GET /inventory/accounts` with `status` and `customer_id` filters.
- [x] Extend `account_inventory` Bitable-shaped view projection with assignment/status fields.
- [x] Run focused tests.
- [x] Update progress.

### Phase 6: Reporting Slice

Goal: 生成客户日报和公司日报，且所有数字有来源和 freshness。

Does:

- Account daily metrics。
- Risk events。
- Customer daily reports。
- Company daily reports。
- Permission-filtered reports。

Does not:

- 不编造消耗。
- 不把 stale data 当 0。
- 不泄露其他客户数据。

#### Subphase 6.1: Metrics And Customer Report

| Item | Detail |
| --- | --- |
| What to do | 实现客户日报生成 |
| Files changed | `models/reporting.py`, `services/reporting.py`, `api/routes/reports.py` |
| Not do | 不自动发送真实 Telegram |
| Expected result | customer report persisted |
| Acceptance | every metric has source/freshness |
| Verification | `cd backend; pytest tests/unit/test_reporting.py -v` |

Substeps:

- [x] Write customer report tests.
- [x] Implement account daily metrics.
- [x] Implement risk events.
- [x] Implement customer report service.
- [x] Add view mapping.
- [x] Run tests.
- [x] Update progress.

#### Subphase 6.2: Company Report And Permission

| Item | Detail |
| --- | --- |
| What to do | 实现公司日报和权限过滤 |
| Files changed | `services/reporting.py`, `api/routes/reports.py`, `services/permissions.py` |
| Not do | 不让 sales 看全局敏感数据 |
| Expected result | manager/admin can view company report |
| Acceptance | sales denied or masked |
| Verification | `cd backend; pytest tests/integration/test_daily_report_slice.py -v` |

Substeps:

- [x] Write company report permission test.
- [x] Implement company report aggregation.
- [x] Apply permission filter.
- [x] Run tests.
- [x] Update progress.

### Phase 7: Stage 02 Acceptance

Goal: 用一个端到端测试证明 Stage 02 的关键路径成立。

Does:

- E2E test。
- Stage 02 acceptance checklist。
- Final progress summary。

Does not:

- 不口头声称完成。
- 不跳过失败测试。

#### Subphase 7.1: E2E Critical Path

| Item | Detail |
| --- | --- |
| What to do | 写端到端验收测试 |
| Files changed | `backend/tests/integration/test_stage_02_e2e.py`, `STAGE_02_ACCEPTANCE_CHECKLIST.md` |
| Not do | 不依赖真实 Telegram/provider |
| Expected result | one command verifies Stage 02 core |
| Acceptance | E2E passes and checklist updated |
| Verification | `cd backend; pytest tests/integration/test_stage_02_e2e.py -v` |

Substeps:

- [x] Write E2E recharge path.
- [x] Extend E2E inventory path.
- [x] Extend E2E reporting path.
- [x] Write acceptance checklist.
- [x] Run E2E.
- [x] Update progress.
