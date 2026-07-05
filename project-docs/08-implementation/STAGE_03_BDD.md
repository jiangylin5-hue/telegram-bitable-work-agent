# Stage 03 Behavior Driven Development

## Status

- Document status: active BDD (confirmed by user 2026-07-06)
- Scope: Stage 03 可验收行为、测试映射和业务证据。
- Current Progress: 2026-07-06 根据用户确认的 Stage 03 方向重写 BDD。本批只写文档，不写代码。

## 1. Feature: Receive-Only Telegram Webhook

### Scenario 1.1: Valid Telegram update creates inbox record

Given:

- The staging app has a configured `TELEGRAM_WEBHOOK_SECRET`.
- A Telegram chat is allowed by allowlist or allowlist is disabled.
- Telegram sends a Bot API update to `/telegram/webhook`.
- The request includes the valid `X-Telegram-Bot-Api-Secret-Token` header.

When:

- The backend receives the update.

Then:

- One `messages` row exists.
- One `outbox_events` row exists for message processing.
- `ops_audit_events` includes message received evidence.
- `/views/telegram_inbox/records` shows the message.
- No Telegram reply is sent.

Test mapping:

- `tests/integration/test_stage03_telegram_webhook.py::test_valid_telegram_update_creates_inbox_record`

### Scenario 1.2: Duplicate Telegram update is idempotent

Given:

- A Telegram update was already processed.

When:

- The same update is posted again.

Then:

- No duplicate `messages` row is created.
- No duplicate business outbox event is created.
- API returns idempotent success.
- Audit does not claim a second business action.

Test mapping:

- `tests/integration/test_stage03_telegram_webhook.py::test_duplicate_update_is_idempotent`

### Scenario 1.3: Invalid webhook secret is rejected

Given:

- A Telegram-shaped request has an invalid secret token.

When:

- The request reaches `/telegram/webhook`.

Then:

- API returns 403.
- No business `messages` row exists.
- No outbox job exists.
- Response does not leak the real secret or raw token.

Test mapping:

- `tests/integration/test_stage03_telegram_webhook.py::test_invalid_secret_is_rejected_without_business_rows`

### Scenario 1.4: Blocked chat/user is not ingested as normal business message

Given:

- Allowlist is enabled.
- Telegram sends a valid-shaped update from a blocked `chat_id` or `user_id`.

When:

- The backend receives the update.

Then:

- The update is rejected or ignored according to configured policy.
- No normal inbox business message is created.
- Safe security audit evidence is written if the implementation records blocked attempts.

Test mapping:

- `tests/integration/test_stage03_telegram_webhook.py::test_allowlist_blocks_untrusted_chat_or_user`

## 2. Feature: Minimal Customer Binding

### Scenario 2.1: Bound chat resolves customer

Given:

- `telegram_chat_id = 1001` is actively bound to `customer_id = C1`.

When:

- A valid Telegram update arrives from chat `1001`.

Then:

- The message stores `customer_id = C1`.
- `binding_status = bound`.
- `telegram_inbox` shows the customer relation.

Test mapping:

- `tests/integration/test_stage03_customer_binding.py::test_bound_chat_resolves_customer`

### Scenario 2.2: Unbound chat enters manual binding state

Given:

- No active binding exists for the incoming chat/user.

When:

- A valid Telegram update arrives.

Then:

- The message is still recorded.
- `customer_id` is empty.
- `binding_status = needs_manual_binding`.
- `telegram_inbox` shows the message in an operator-visible state.

Test mapping:

- `tests/integration/test_stage03_customer_binding.py::test_unbound_chat_enters_manual_binding_state`

### Scenario 2.3: Inactive binding is ignored

Given:

- A binding exists but `status = inactive`.

When:

- A valid Telegram update arrives from that chat/user.

Then:

- The inactive binding is not used.
- The message is treated as unbound.

Test mapping:

- `tests/integration/test_stage03_customer_binding.py::test_inactive_binding_is_ignored`

## 3. Feature: Outbox To Redis Streams

### Scenario 3.1: Committed outbox event becomes Redis stream job

Given:

- A business transaction commits a message and outbox event.

When:

- The outbox-to-Redis bridge runs.

Then:

- One Redis Streams job exists.
- The job includes `event_id`, `trace_id`, `idempotency_key` and `message_id`.
- Outbox delivery state is updated safely.

Test mapping:

- `tests/integration/test_stage03_redis_streams_bridge.py::test_committed_outbox_event_becomes_stream_job`

### Scenario 3.2: Rolled back outbox event is not enqueued

Given:

- A transaction creates an outbox event and rolls back.

When:

- The outbox-to-Redis bridge runs.

Then:

- No Redis Streams job is created.

Test mapping:

- `tests/integration/test_stage03_redis_streams_bridge.py::test_rolled_back_outbox_event_is_not_enqueued`

### Scenario 3.3: Re-bridging does not duplicate business effect

Given:

- An outbox event was already delivered to Redis Streams.

When:

- The bridge runs again.

Then:

- The same business event is not processed twice from the application's perspective.

Test mapping:

- `tests/integration/test_stage03_redis_streams_bridge.py::test_rebridge_is_idempotent`

## 4. Feature: Durable Redis Streams Worker

### Scenario 4.1: Worker processes message registration job

Given:

- A Redis Streams job exists for a received Telegram message.

When:

- Worker runner processes one bounded iteration.

Then:

- Message `processing_status` becomes `processed`.
- Customer binding status is set or confirmed.
- `ops_audit_events` includes worker processed evidence.
- `telegram_inbox` reflects the new status.

Test mapping:

- `tests/integration/test_stage03_worker_runtime.py::test_worker_processes_message_registration_job`

### Scenario 4.2: Worker rerun is idempotent

Given:

- Worker processed a job once.

When:

- Worker processes the same event again or sees a replay.

Then:

- No duplicate message or business record is created.
- Audit does not claim a duplicate action.

Test mapping:

- `tests/integration/test_stage03_worker_runtime.py::test_worker_rerun_is_idempotent`

### Scenario 4.3: Worker failure becomes retry or dead letter

Given:

- A message processing job fails with a controlled error.

When:

- Worker retry policy is exhausted.

Then:

- The job is marked `dead_letter`.
- `telegram_inbox.processing_status = dead_letter`.
- Safe error code and audit evidence are visible.

Test mapping:

- `tests/integration/test_stage03_worker_runtime.py::test_worker_failure_becomes_dead_letter`

## 5. Feature: Bitable Telegram Inbox View

### Scenario 5.1: Inbox view has stable order and bounded result size

Given:

- More messages exist than the default view limit.

When:

- User queries `/views/telegram_inbox/records`.

Then:

- Response uses deterministic order.
- Response is capped by default limit.
- Custom limit above max is rejected or capped.
- Permission filtering and masking still apply.

Test mapping:

- `tests/unit/test_stage03_telegram_inbox_view.py::test_inbox_view_has_stable_order_and_limit`

### Scenario 5.2: Inbox view does not expose secrets or raw payload

Given:

- A message was created from a real Telegram update.

When:

- User queries the inbox view.

Then:

- The response does not include Bot token, webhook secret, raw secret header or full raw update payload.

Test mapping:

- `tests/unit/test_stage03_telegram_inbox_view.py::test_inbox_view_redacts_secret_and_raw_payload`

## 6. Feature: Tencent Cloud Staging Webhook Rehearsal

### Scenario 6.1: Real Telegram message reaches staging inbox

Given:

- Tencent Cloud CVM staging is running.
- Caddy HTTPS endpoint is configured.
- Telegram webhook is set to the staging URL after explicit user confirmation.

When:

- A real Telegram test message is sent to the bot.

Then:

- Backend receives the webhook.
- `telegram_inbox` shows the message.
- Audit evidence records the receive/process path.
- No Telegram reply is sent.

Test mapping:

- Manual staging verification recorded in `STAGE_03_ACCEPTANCE_CHECKLIST.md`.

## 7. Stage 03 BDD Acceptance

Stage 03 BDD is accepted only when:

- Every automated scenario above maps to a test before implementation is called complete.
- Manual staging scenario includes concrete timestamp, redacted endpoint and observed Bitable/audit evidence.
- No scenario requires real Telegram sending, real LLM calls, real provider writes or real funds movement.
- Every workflow ends in Bitable view/status/audit evidence.
