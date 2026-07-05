# Stage 03 Behavior Driven Development

## Status

- Document status: candidate BDD, pending user confirmation
- Scope: Stage 03 可验收行为、测试映射和业务证据
- Current Progress: 2026-07-05 建立 Stage 03 BDD 草案。后续实现必须先补测试映射，再写代码。

## 1. Feature: Real Telegram Webhook Ingress

### Scenario 1.1: Valid Telegram update creates message and intent job

Given:

- A customer group is bound to a Telegram chat.
- Telegram sends a Bot API update to `/telegram/webhook`.
- The request includes a valid webhook secret.

When:

- The backend receives the update.

Then:

- One `messages` row exists.
- One `outbox_events.agent.intent_extract` row exists.
- `ops_audit_events` includes `message_ingested`.
- `/views/telegram_inbox/records` shows the message.

### Scenario 1.2: Duplicate Telegram update is idempotent

Given:

- A Telegram update was already processed.

When:

- The same update is posted again.

Then:

- No duplicate `messages` row is created.
- No duplicate intent outbox job is created.
- API returns idempotent success.

### Scenario 1.3: Invalid webhook secret is rejected

Given:

- A Telegram-shaped request has an invalid secret.

When:

- The request reaches `/telegram/webhook`.

Then:

- API returns 403.
- No `messages` row exists.
- No outbox job exists.
- No secret value is leaked.

## 2. Feature: Durable Worker Runtime

### Scenario 2.1: Worker processes intent job into draft

Given:

- A pending `agent.intent_extract` outbox/job exists.

When:

- Worker runner processes one bounded iteration.

Then:

- One `service_drafts` row exists.
- Message intent fields are updated.
- `ops_audit_events` includes `draft_created`.
- `/views/ai_draft_queue/records` shows the draft.

### Scenario 2.2: Worker rerun is idempotent

Given:

- Worker processed a job once.

When:

- Worker processes the same job again.

Then:

- No duplicate draft is created.
- Job remains processed or safely ignored.
- Audit does not claim a second business action.

## 3. Feature: Queue Bridge

### Scenario 3.1: Committed outbox event becomes queue job

Given:

- A business transaction commits an outbox event.

When:

- Outbox-to-queue bridge runs.

Then:

- One queue job is created with the same `trace_id` and `idempotency_key`.
- The outbox event records delivery state.

### Scenario 3.2: Rolled back outbox event is not enqueued

Given:

- A transaction creates an outbox event and rolls back.

When:

- Outbox-to-queue bridge runs.

Then:

- No queue job is created.

## 4. Feature: Telegram Notify Dry Run

### Scenario 4.1: Customer reply outbox is consumed without real send

Given:

- A `customer.reply` or `telegram.notify` job exists.
- `TELEGRAM_SEND_MODE = dry_run`.

When:

- Notification worker handles it.

Then:

- No real Telegram message is sent.
- Delivery attempt/audit is written.
- Relevant Bitable view or audit view shows notification state.

## 5. Feature: Provider Sandbox Gateway

### Scenario 5.1: Execution requires ticket

Given:

- A recharge execution job exists without a valid execution ticket.

When:

- Execution worker attempts to run it.

Then:

- Execution is denied.
- No sandbox provider call is made.
- Audit records permission/state denial.

### Scenario 5.2: Sandbox execution writes log and readback job

Given:

- A valid execution ticket exists.
- Provider mode is `sandbox`.

When:

- Execution worker processes `execution.recharge`.

Then:

- Sandbox adapter is called.
- `execution_logs` records sandbox response.
- `recharge_records.execution_status` is updated.
- `readback.balance` job is created.
- `recharge_view` shows the status.

### Scenario 5.3: Provider-like failure maps to retry or dead letter

Given:

- Sandbox adapter returns timeout or provider unavailable.

When:

- Worker handles the job.

Then:

- Retryable failures are retried.
- Exhausted jobs become dead letter.
- Audit and business status show failure without claiming success.

## 6. Feature: Bitable View Hardening

### Scenario 6.1: View has stable order and bounded result size

Given:

- A view has more records than the default limit.

When:

- User queries `/views/{view_key}/records`.

Then:

- Response uses deterministic order.
- Response is capped by default limit.
- Custom limit above max is rejected or capped.
- Permission filtering and masking still apply.

## 7. Stage 03 BDD Acceptance

Stage 03 BDD is accepted only when:

- Every scenario above maps to tests.
- Tests are listed in `STAGE_03_ACCEPTANCE_CHECKLIST.md`.
- No test requires real provider writes or real funds movement.
- Every workflow ends in Bitable view/status/audit evidence.

