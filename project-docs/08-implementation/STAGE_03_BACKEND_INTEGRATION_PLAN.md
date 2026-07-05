# Stage 03 Backend Integration Plan

> Required workflow skill for implementation: use `superpowers:executing-plans` or `superpowers:subagent-driven-development`. Do not start code until `STAGE_03_SOURCE_OF_TRUTH.md` is confirmed active.

## Status

- Document status: candidate implementation plan, pending user confirmation
- Scope: Stage 03 真实 Telegram 接入、durable worker、Redis/job runtime、provider sandbox gateway、部署数据库演练、Bitable view hardening
- Current Progress: 2026-07-05 建立 Stage 03 候选执行计划，按大阶段、子阶段、子步骤拆解。当前只写文档，不写 Stage 03 业务代码。

## 1. Delivery Shape

Stage 03 分 5 个增量：

```text
03.0 Stage Gate And Config
-> 03.1 Real Telegram Webhook Ingress
-> 03.2 Durable Worker Runtime
-> 03.3 Queue Bridge And Notification Dry Run
-> 03.4 Provider Sandbox Gateway
-> 03.5 Migration Rehearsal And View Hardening
```

## 2. Non-Goals

- 不接真实 provider 写入。
- 不移动真实资金。
- 不做 Mini App 前端。
- 不引入 `tenant_id`。
- 不迁移到 Temporal。
- 不重写 Stage 02 服务层。

## 3. Phase 03.0: Stage Gate And Config

### Step 03.0.1: Freeze Stage 02

What to do:

- Ensure Stage 02 hardening batch is committed before Stage 03 code.
- Keep Stage 02 docs as historical truth.

What to change:

- Git commit only after user approval.
- No production code change.

What not to do:

- Do not mix Stage 02 fixes with Stage 03 implementation.

Expected result:

- Clean baseline commit for Stage 03.

Acceptance:

- `git status --short` after commit shows no uncommitted Stage 02 files.

### Step 03.0.2: Runtime Config Contract

What to do:

- Add documented env var contract for Telegram token, webhook secret, Redis URL, DB URL, provider mode and dry-run mode.

What to change:

- `backend/app/core/config.py`
- docs acceptance/config section
- tests for config defaults and required env behavior

What not to do:

- Do not store secrets in repo.

Expected result:

- App can distinguish `local`, `test`, `staging`, `production`.

Acceptance:

- Config tests prove missing required secrets fail only in integration runtime, not unit tests.

## 4. Phase 03.1: Real Telegram Webhook Ingress

### Step 03.1.1: Webhook Route

What to do:

- Implement `/telegram/webhook` route accepting Telegram Bot API update shape.
- Validate webhook secret/header.
- Normalize into existing Stage 02 ingestion command.

What to change:

- API route and schema files.
- Telegram adapter/parser.
- Tests for valid update, duplicate update and invalid secret.

What not to do:

- Do not send Telegram replies in the same request.

Expected result:

- Real update lands in `messages`, emits `agent.intent_extract` outbox event, and appears in `telegram_inbox`.

Acceptance:

- Integration test posts Telegram-shaped update and verifies `messages`, `outbox_events`, `ops_audit_events`, `/views/telegram_inbox/records`.

### Step 03.1.2: Webhook Error Policy

What to do:

- Define stable error responses for invalid secret, malformed update and duplicate update.

What to change:

- Error schema and tests.

What not to do:

- Do not leak token, raw secret or full raw update in error body.

Expected result:

- Operationally debuggable but safe errors.

Acceptance:

- Tests assert error code and redaction.

## 5. Phase 03.2: Durable Worker Runtime

### Step 03.2.1: Worker Entrypoint

What to do:

- Add `python -m app.workers.runner` or equivalent command.
- Load config, DB session factory and queue/outbox repository.
- Process pending jobs in a bounded loop for tests and continuous loop for runtime.

What to change:

- `backend/app/workers/runner.py`
- worker tests
- documentation command

What not to do:

- Do not require real Redis in unit tests.

Expected result:

- Worker can process `agent.intent_extract`, `execution.recharge`, `readback.balance`, `telegram.notify` handlers through service layer.

Acceptance:

- Worker integration test runs bounded loop and verifies draft creation/audit persistence.

### Step 03.2.2: Worker Idempotency And Shutdown

What to do:

- Ensure repeated worker run does not duplicate business records.
- Add graceful stop signal boundary.

What to change:

- Worker runner and tests.

What not to do:

- Do not make worker mutate core tables outside service/UOW.

Expected result:

- Safe reruns and predictable shutdown.

Acceptance:

- Test runs worker twice and proves one draft/outbox result.

## 6. Phase 03.3: Queue Bridge And Notification Dry Run

### Step 03.3.1: Outbox To Redis/Job Bridge

What to do:

- Implement bridge from committed `outbox_events` to Redis/job envelope or Stage 03 durable queue abstraction.
- Preserve idempotency key and trace id.

What to change:

- queue adapter/repository
- worker queue consumer
- tests with fake Redis or test Redis

What not to do:

- Do not enqueue before DB commit.

Expected result:

- Outbox remains source of truth; Redis/job layer becomes delivery mechanism.

Acceptance:

- Test proves rollback does not enqueue job, commit does enqueue job once.

### Step 03.3.2: Telegram Notify Dry Run

What to do:

- Add `telegram.notify` handler that writes delivery attempt/audit in dry-run mode.

What to change:

- Telegram sender adapter
- notification handler
- tests

What not to do:

- Do not send real Telegram messages unless explicitly enabled in staging.

Expected result:

- Customer reply outbox from Stage 02 can be consumed without real external send.

Acceptance:

- Test consumes `customer.reply`/`telegram.notify`, writes audit and delivery status.

## 7. Phase 03.4: Provider Sandbox Gateway

### Step 03.4.1: Gateway Interface

What to do:

- Define provider gateway interface for recharge, balance readback, card binding, BM invite.
- Implement sandbox adapter only.

What to change:

- `backend/app/adapters/providers_sandbox.py`
- execution gateway service
- tests

What not to do:

- Do not call real Meta/BM/card/recharge provider.

Expected result:

- Execution worker can call provider-like adapter with execution ticket and write execution log.

Acceptance:

- Tests verify no execution without valid ticket, sandbox response writes execution log and audit.

### Step 03.4.2: Provider Failure Mapping

What to do:

- Map timeout, provider_unavailable, validation_failed, risk_blocked into retry/dead_letter/manual_review.

What to change:

- gateway errors
- worker handler tests

What not to do:

- Do not hide provider failure as success.

Expected result:

- Operator sees exact failed state in Bitable view and audit.

Acceptance:

- Tests assert retryable and non-retryable failure state transitions.

## 8. Phase 03.5: Migration Rehearsal And View Hardening

### Step 03.5.1: Migration Rehearsal

What to do:

- Run Alembic upgrade against a long-lived local/staging-like PostgreSQL database without per-test schema reset.

What to change:

- rehearsal doc/script
- acceptance checklist

What not to do:

- Do not target production database.

Expected result:

- Migration can run in an environment closer to deployment than unit/offline SQL.

Acceptance:

- Command and output recorded in Stage 03 acceptance checklist.

### Step 03.5.2: Bitable View Minimal Hardening

What to do:

- Add deterministic ordering and basic `limit` for `/views/{view_key}/records`.
- Document pagination follow-up if cursor is deferred.

What to change:

- view schema/route/service
- tests

What not to do:

- Do not build a full query builder.

Expected result:

- Views are safer for larger real datasets.

Acceptance:

- Tests prove default limit, custom limit cap and stable ordering.

## 9. Final Stage 03 Acceptance

Stage 03 can be accepted only when:

- Telegram webhook integration tests pass.
- Worker runtime integration tests pass.
- Queue bridge/dry-run notification tests pass.
- Provider sandbox gateway tests pass.
- Migration rehearsal is documented with command output.
- Bitable view hardening tests pass.
- Full backend suite passes.
- No real provider writes occurred.

