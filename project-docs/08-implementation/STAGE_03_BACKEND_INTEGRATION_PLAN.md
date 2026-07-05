# Stage 03 Backend Integration Plan

> Required workflow skill for implementation: use `superpowers:executing-plans` or `superpowers:subagent-driven-development` after the user explicitly confirms code development may start. The current confirmed batch is documentation only.
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first deployable Stage 03 backend integration loop: real receive-only Telegram webhook on Tencent Cloud staging, PostgreSQL Outbox, Redis Streams worker, minimal customer binding, and Bitable `telegram_inbox` evidence.

**Architecture:** Keep PostgreSQL as the business fact and outbox source of truth, use Redis Streams only as the delivery/runtime layer, and expose the webhook through Caddy HTTPS on Tencent Cloud CVM. Stage 03 deliberately keeps LLM, Telegram send, provider execution and funds movement out of the critical path.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis Streams, Docker Compose, Caddy, Tencent Cloud CVM, pytest.

## Status

- Document status: active implementation plan (confirmed by user 2026-07-06)
- Scope: Stage 03 真实 Telegram 收件入口、PostgreSQL Outbox、Redis Streams worker、最小客户绑定、多维表格 Telegram Inbox、腾讯云 CVM staging、Caddy HTTPS。
- Current Progress: 2026-07-06 根据用户 11 项选择重写 Stage 03 计划。本批只完善文档，不写代码；代码开发需要用户后续确认。

## 1. Delivery Shape

Stage 03 分为 6 个子阶段：

```text
03.0 Documentation And Stage Gate
-> 03.1 Tencent Cloud Staging Runtime Design
-> 03.2 Real Telegram Receive-Only Webhook
-> 03.3 Minimal Customer Binding And Telegram Inbox
-> 03.4 PostgreSQL Outbox To Redis Streams Worker
-> 03.5 Acceptance, Rehearsal And Stage Close
```

## 2. Non-Goals

Stage 03 不做：

- 不真实发送 Telegram 消息。
- 不调用 OpenRouter 或真实 LLM。
- 不实现 LangGraph 真实 Agent。
- 不做充值、绑卡、Meta、BM、卡台或 provider 写入。
- 不移动真实资金。
- 不做 provider sandbox gateway。
- 不做 Mini App 或完整 Web 管理台。
- 不引入 `tenant_id`。
- 不迁移到 Kubernetes 或 Temporal。

## 2.1 Required Reading Before Code

1. [AGENTS.md](../../AGENTS.md)
2. [Stage 03 Source Of Truth](STAGE_03_SOURCE_OF_TRUTH.md)
3. [Stage 03 Module Index](STAGE_03_MODULE_INDEX.md)
4. [Stage 03 SDD](STAGE_03_SDD.md)
5. [Stage 03 BDD](STAGE_03_BDD.md)
6. [Stage 03 API Contract](STAGE_03_API_CONTRACT.md)
7. [Stage 03 Database And Migration Design](STAGE_03_DATABASE_AND_MIGRATION_DESIGN.md)
8. [Stage 03 Security And Permission Design](STAGE_03_SECURITY_AND_PERMISSION_DESIGN.md)
9. [Stage 03 Test Plan](STAGE_03_TEST_PLAN.md)
10. [Stage 03 Tencent Cloud Staging Deployment](STAGE_03_TENCENT_CLOUD_STAGING_DEPLOYMENT.md)
11. [Stage 03 Operations Runbook](STAGE_03_OPERATIONS_RUNBOOK.md)
12. [Stage 03 Risk Register](STAGE_03_RISK_REGISTER.md)
13. Module docs under `modules/`.

## 2.2 Proposed Future File Structure

```text
backend/
  app/
    api/routes/
      telegram_webhook.py
    core/
      config.py
    queues/
      __init__.py
      redis_streams.py
    schemas/
      telegram_webhook.py
    services/
      customer_binding.py
      telegram_update_parser.py
      telegram_ingestion.py
      bitable_views.py
      outbox.py
    workers/
      runner.py
      stage03_handlers.py
    models/
      telegram.py
      outbox.py
    repositories/
      outbox.py
  tests/
    unit/
      test_stage03_config.py
      test_stage03_telegram_update_parser.py
      test_stage03_telegram_inbox_view.py
    integration/
      test_stage03_telegram_webhook.py
      test_stage03_customer_binding.py
      test_stage03_redis_streams_bridge.py
      test_stage03_worker_runtime.py
```

The file names above are the default implementation target. If existing code structure makes a different file more appropriate, the implementation must update this plan/progress with the reason before coding.

## 3. Phase 03.0: Documentation And Stage Gate

### Step 03.0.1: Freeze Stage 02

What to do:

- Treat Stage 02 as closed and frozen.
- Use `STAGE_02_FINAL_ACCEPTANCE_REPORT.md` as Stage 02 final evidence.
- Do not add new Stage 02 code or scope.

What to change:

- Stage 02 source/progress/index documentation only if needed for status clarity.

What not to do:

- Do not mix Stage 02 fixes with Stage 03 implementation.

Expected result:

- Stage 03 has a clean documentation and git baseline.

Acceptance:

- Stage 02 source says frozen/closed.
- Stage 03 docs explicitly refer to Stage 02 as historical truth.

### Step 03.0.2: Finalize Stage 03 Documentation

What to do:

- Write Stage 03 source of truth, plan, SDD, BDD, acceptance checklist, progress log and Tencent Cloud staging deployment doc.
- Convert previous candidate assumptions into confirmed decisions.
- Remove outdated local-only deployment assumptions.

What to change:

- `project-docs/08-implementation/STAGE_03_SOURCE_OF_TRUTH.md`
- `project-docs/08-implementation/STAGE_03_BACKEND_INTEGRATION_PLAN.md`
- `project-docs/08-implementation/STAGE_03_SDD.md`
- `project-docs/08-implementation/STAGE_03_BDD.md`
- `project-docs/08-implementation/STAGE_03_ACCEPTANCE_CHECKLIST.md`
- `project-docs/08-implementation/STAGE_03_PROGRESS.md`
- `project-docs/08-implementation/STAGE_03_TENCENT_CLOUD_STAGING_DEPLOYMENT.md`
- documentation indexes

What not to do:

- Do not write backend implementation code in this batch.
- Do not add dependencies.
- Do not configure real Telegram webhook.

Expected result:

- A developer can start Stage 03 implementation from docs without asking what to build first.

Acceptance:

- Every Stage 03 doc agrees on scope, exclusions, deployment and test boundary.
- Documentation consistency review finds no active-scope contradiction with the confirmed Tencent Cloud, receive-only Telegram, no-LLM and no-provider-execution decisions.

## 4. Phase 03.1: Tencent Cloud Staging Runtime Design

### Step 03.1.1: Staging Topology

What to do:

- Define a single Tencent Cloud CVM staging topology.
- Run FastAPI, worker, PostgreSQL, Redis and Caddy with Docker Compose.
- Use Caddy for HTTPS and reverse proxy.

What to change:

- Deployment documentation.
- Future compose files and env examples after code phase starts.

What not to do:

- Do not deploy to Kubernetes.
- Do not use Tencent Cloud API Gateway or load balancer in Stage 03.
- Do not store secrets in repository.

Expected result:

- The staging runtime shape is clear before code starts.

Acceptance:

- Deployment doc lists ports, services, env vars, secrets, health checks and rollback expectations.

### Step 03.1.2: Environment Contract

What to do:

- Document environment variables needed for staging.

What to change later:

- `backend/app/core/config.py`
- `.env.example` or documentation-only env template

What not to do:

- Do not commit real token, secret, database password or Redis password.

Expected result:

- Runtime can fail fast when required staging env vars are missing.

Acceptance:

- Config tests planned for missing/valid secret behavior.

## 5. Phase 03.2: Real Telegram Receive-Only Webhook

### Step 03.2.1: Webhook Route

What to do:

- Implement `POST /telegram/webhook`.
- Accept Telegram Bot API update payload.
- Validate `X-Telegram-Bot-Api-Secret-Token`.
- Validate optional allowlist for `chat_id` and `user_id`.
- Normalize supported message payloads into existing message ingestion service.

What to change later:

- API route and schema files.
- Telegram payload parser.
- Tests for valid update, duplicate update, invalid secret and blocked allowlist.

What not to do:

- Do not send Telegram replies from webhook request.
- Do not call LLM.
- Do not execute business actions.

Expected result:

- Real Telegram update lands in `messages`, creates an outbox event and appears in Bitable Telegram Inbox.

Acceptance:

- Integration test posts Telegram-shaped update and verifies `messages`, `outbox_events`, `ops_audit_events` and `/views/telegram_inbox/records`.

### Step 03.2.2: Error And Idempotency Policy

What to do:

- Define stable responses for invalid secret, malformed update, blocked allowlist and duplicate update.
- Ensure duplicate update returns idempotent success without duplicate business rows.

What to change later:

- Error schema, ingestion service and tests.

What not to do:

- Do not leak token, secret, full raw update or sensitive chat data in error body.

Expected result:

- Operators can debug failed webhook calls without exposing secrets.

Acceptance:

- Tests assert status code, redaction and no unintended row creation.

## 6. Phase 03.3: Minimal Customer Binding And Telegram Inbox

### Step 03.3.1: Customer Binding Model

What to do:

- Define minimal binding from Telegram `chat_id` / `user_id` to `customer_id`.
- Support active/inactive binding state.
- Record who created or changed the binding through audit.

What to change later:

- SQLAlchemy model and Alembic migration for `telegram_customer_bindings` or equivalent.
- Binding service and permission checks.
- Tests for exact match, inactive binding and unbound message.

What not to do:

- Do not design full tenant/organization membership.
- Do not implement complete group role management.

Expected result:

- Incoming messages can be attributed to a customer when binding exists.

Acceptance:

- Bound chat message shows `customer_id`.
- Unbound chat message shows `binding_status = needs_manual_binding`.

### Step 03.3.2: Telegram Inbox Bitable View

What to do:

- Define the Stage 03 fields shown in `telegram_inbox`.
- Include message identity, chat/user identity, customer binding, processing status, timestamps and audit status.

What to change later:

- Bitable view config and service projection.
- View tests for role filtering and sensitive field masking.

What not to do:

- Do not build a full query builder.
- Do not expose secrets, raw token or full raw update payload in views.

Expected result:

- Operators can see the real inbound message queue as a table.

Acceptance:

- `/views/telegram_inbox/records` returns deterministic records with Stage 03 fields.

## 7. Phase 03.4: PostgreSQL Outbox To Redis Streams Worker

### Step 03.4.1: Outbox To Redis Streams Bridge

What to do:

- Keep PostgreSQL outbox as source of truth.
- After DB commit, bridge pending outbox events into Redis Streams.
- Preserve `event_id`, `trace_id`, `idempotency_key` and event type.

What to change later:

- Redis adapter.
- Outbox delivery state.
- Tests with fake Redis or isolated Redis.

What not to do:

- Do not enqueue before DB commit.
- Do not make Redis the only source of truth.

Expected result:

- Committed outbox events become stream jobs exactly once from the business perspective.

Acceptance:

- Test proves committed event enqueues once.
- Test proves rolled-back event does not enqueue.

### Step 03.4.2: Durable Worker Runtime

What to do:

- Add worker entrypoint to consume Redis Streams.
- Process message registration jobs through service layer.
- Mark success, retry, dead letter and audit evidence.

What to change later:

- Worker runner.
- Message registration handler.
- Retry and dead letter policy.
- Tests for bounded loop and repeated execution.

What not to do:

- Do not mutate core tables outside service/UOW.
- Do not call LLM or external providers.

Expected result:

- Worker can process Telegram ingestion events asynchronously and idempotently.

Acceptance:

- Worker integration test runs bounded loop and verifies message processing status/audit.
- Re-running worker does not duplicate business records.

## 8. Phase 03.5: Acceptance, Rehearsal And Stage Close

### Step 03.5.1: Staging Deployment Rehearsal

What to do:

- Run Stage 03 on Tencent Cloud CVM staging.
- Configure Caddy HTTPS.
- Set Telegram webhook to staging endpoint after explicit user confirmation.
- Send a real Telegram test message.

What to change later:

- Deployment evidence in acceptance checklist.

What not to do:

- Do not use production database.
- Do not send real replies.
- Do not enable provider writes.

Expected result:

- Real Telegram update reaches Bitable Telegram Inbox in staging.

Acceptance:

- Acceptance checklist records command, endpoint redaction, timestamp and observed record/audit evidence.

### Step 03.5.2: Final Verification

What to do:

- Run focused Stage 03 tests.
- Run full backend test suite.
- Record deployment and test evidence.

What to change:

- `STAGE_03_ACCEPTANCE_CHECKLIST.md`
- `STAGE_03_PROGRESS.md`

What not to do:

- Do not declare completion without evidence.

Expected result:

- Stage 03 can be closed with clear pass/fail evidence.

Acceptance:

- All Stage 03 checklist rows are passed or explicitly marked not tested with reason.
- Remaining risks are listed before moving to Stage 04.

## 9. Final Stage 03 Acceptance

Stage 03 can be accepted only when:

- Telegram webhook integration tests pass.
- Webhook secret and allowlist tests pass.
- Customer binding tests pass.
- Redis Streams bridge tests pass.
- Worker runtime and idempotency tests pass.
- `telegram_inbox` Bitable view tests pass.
- Tencent Cloud staging deployment rehearsal is documented.
- Full backend suite passes.
- No real Telegram send, real LLM call, real provider write or real funds movement occurred.

## 10. Code Phase Task Breakdown

These tasks are for the later code phase. The current user-approved batch remains documentation-only.

### Task 1: Runtime Config And Safety Defaults

**Files:**

- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_stage03_config.py`
- Docs: `STAGE_03_SECURITY_AND_PERMISSION_DESIGN.md`

- [ ] Step 1: Write config tests proving staging requires `TELEGRAM_WEBHOOK_SECRET`, `DATABASE_URL` and `REDIS_URL`.
- [ ] Step 2: Write tests proving `TELEGRAM_SEND_MODE=dry_run`, `LLM_ENABLED=false` and `PROVIDER_MODE=disabled` are Stage 03 defaults.
- [ ] Step 3: Implement minimal config fields without storing secrets in code.
- [ ] Step 4: Run `pytest tests/unit/test_stage03_config.py -v`.
- [ ] Step 5: Update `STAGE_03_PROGRESS.md` with changed files and result.

### Task 2: Telegram Update Parser

**Files:**

- Create: `backend/app/services/telegram_update_parser.py`
- Create: `backend/app/schemas/telegram_webhook.py`
- Test: `backend/tests/unit/test_stage03_telegram_update_parser.py`

- [ ] Step 1: Write parser tests for text message, non-text metadata, malformed update and redaction.
- [ ] Step 2: Implement parser returning normalized update fields.
- [ ] Step 3: Ensure parser does not expose Bot Token, secret header or full raw update to view DTOs.
- [ ] Step 4: Run `pytest tests/unit/test_stage03_telegram_update_parser.py -v`.
- [ ] Step 5: Update progress.

### Task 3: Receive-Only Webhook Route

**Files:**

- Create: `backend/app/api/routes/telegram_webhook.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/telegram_ingestion.py`
- Test: `backend/tests/integration/test_stage03_telegram_webhook.py`

- [ ] Step 1: Write failing tests for valid update, duplicate update, invalid secret and allowlist blocked source.
- [ ] Step 2: Implement route-level secret and allowlist validation.
- [ ] Step 3: Call ingestion service only after validation passes.
- [ ] Step 4: Ensure valid update creates message, audit and outbox event.
- [ ] Step 5: Run `pytest tests/integration/test_stage03_telegram_webhook.py -v`.
- [ ] Step 6: Update progress.

### Task 4: Customer Binding And Telegram Inbox

**Files:**

- Modify/Create: `backend/app/models/telegram.py`
- Create migration: `backend/alembic/versions/<next>_stage03_telegram_customer_bindings.py`
- Create: `backend/app/services/customer_binding.py`
- Modify: `backend/app/services/bitable_views.py`
- Test: `backend/tests/integration/test_stage03_customer_binding.py`
- Test: `backend/tests/unit/test_stage03_telegram_inbox_view.py`

- [ ] Step 1: Write binding tests for bound, unbound, inactive and conflict cases.
- [ ] Step 2: Write inbox view tests for fields, redaction, permission scope, stable order and limit.
- [ ] Step 3: Implement model/migration.
- [ ] Step 4: Implement binding service.
- [ ] Step 5: Implement inbox projection.
- [ ] Step 6: Run binding and view tests.
- [ ] Step 7: Run Alembic offline SQL.
- [ ] Step 8: Update progress.

### Task 5: Outbox To Redis Streams Bridge

**Files:**

- Create: `backend/app/queues/__init__.py`
- Create: `backend/app/queues/redis_streams.py`
- Modify: `backend/app/services/outbox.py`
- Modify: `backend/app/repositories/outbox.py`
- Test: `backend/tests/integration/test_stage03_redis_streams_bridge.py`

- [ ] Step 1: Write tests for committed event enqueue, rolled-back event not enqueued and bridge idempotency.
- [ ] Step 2: Implement Redis Streams adapter behind a small interface.
- [ ] Step 3: Implement outbox bridge preserving `event_id`, `trace_id` and `idempotency_key`.
- [ ] Step 4: Run queue bridge tests.
- [ ] Step 5: Update progress.

### Task 6: Durable Worker Runtime

**Files:**

- Create: `backend/app/workers/runner.py`
- Create/Modify: `backend/app/workers/stage03_handlers.py`
- Modify: `backend/app/workers/handlers.py` if reusing existing dispatcher
- Test: `backend/tests/integration/test_stage03_worker_runtime.py`

- [ ] Step 1: Write tests for bounded worker processing, idempotent rerun and dead letter.
- [ ] Step 2: Implement bounded loop for tests and continuous loop for staging.
- [ ] Step 3: Implement message registration handler through service/UOW.
- [ ] Step 4: Implement retry/dead letter status and audit.
- [ ] Step 5: Run worker tests.
- [ ] Step 6: Update progress.

### Task 7: Tencent Cloud Staging Rehearsal

**Files:**

- Create or update deployment files after user confirms server work.
- Update: `STAGE_03_ACCEPTANCE_CHECKLIST.md`
- Update: `STAGE_03_PROGRESS.md`

- [ ] Step 1: Confirm with user before any real server, DNS or Telegram webhook operation.
- [ ] Step 2: Deploy API, worker, PostgreSQL, Redis and Caddy to Tencent Cloud CVM.
- [ ] Step 3: Run migration against staging database.
- [ ] Step 4: Verify invalid secret rejection.
- [ ] Step 5: Confirm with user before setting Telegram webhook.
- [ ] Step 6: Send one real test message and record redacted evidence.
- [ ] Step 7: Run full backend suite locally or in CI-equivalent environment.
- [ ] Step 8: Update acceptance checklist and progress.
