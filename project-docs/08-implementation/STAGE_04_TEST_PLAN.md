# Stage 04 Test Plan

## Status

- Document status: active test plan
- Scope: Stage 04 automated tests、manual staging rehearsal、skipped tests policy。
- Current Progress: 2026-07-07 Stage04 focused automated tests are implemented and `pytest tests -q` reports 172 passed / 17 skipped after the staging compose send-mode gate test was added. Manual Tencent Cloud staging rehearsal remains pending and is required for final Stage04 acceptance.

## 1. Test Strategy

Stage 04 uses TDD for behavior changes:

1. Write focused failing test.
2. Implement minimal code.
3. Run focused test.
4. Run affected Stage 03 regressions.
5. Run full backend suite before stage acceptance.

Manual staging is required only for the real Telegram test send path and real webhook/binding path.

## 2. Automated Test Groups

| Test group | Files | Purpose |
| --- | --- | --- |
| Binding management | `tests/integration/test_stage04_binding_management.py` | API permission, create, list, disable, not-found, conflict, audit |
| New message binding | `tests/integration/test_stage04_new_message_binding.py` | new inbound message uses active binding; inactive ignored; history unchanged |
| Intent placeholder | `tests/integration/test_stage04_intent_placeholder.py` | no LLM; no service draft; placeholder view/audit |
| Restricted test send | `tests/integration/test_stage04_test_send.py` | request, confirm, permission denial, not-found, block, fake Telegram send, idempotency |
| Runtime config | `tests/unit/test_stage04_config.py` | `restricted_test` fail-closed behavior |
| Bitable views | `tests/unit/test_stage04_bitable_views.py` | new views, masking and row-level filtering for unbound/conflict/send rows |
| Telegram client | `tests/unit/test_stage04_telegram_bot_client.py` | request build, response redaction, error mapping |

## 3. Required Regression Tests

Run these after affected tasks:

```text
cd backend; pytest tests/integration/test_stage03_customer_binding.py -v
cd backend; pytest tests/integration/test_stage03_telegram_webhook.py -v
cd backend; pytest tests/integration/test_stage03_worker_runtime.py -v
cd backend; pytest tests/unit/test_stage03_telegram_inbox_view.py -v
```

Run before final acceptance:

```text
cd backend; pytest tests -q
cd backend; alembic upgrade head --sql
git diff --check
```

## 4. Manual Staging Tests

### 4.1 Binding rehearsal

1. Deploy Stage 04 to Tencent Cloud staging.
2. Create a binding through internal API.
3. Send a new real Telegram message to bot/test chat.
4. Query `/views/telegram_inbox/records`.
5. Verify `binding_status=bound` and `customer_id` set.
6. Verify audit events.

### 4.2 Restricted test send rehearsal

1. Confirm with user before enabling `TELEGRAM_SEND_MODE=restricted_test`.
2. Configure `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` server-side only.
3. Create `telegram_send_requests` row through API.
4. Confirm through API.
5. Worker sends Telegram `sendMessage`.
6. Verify test chat receives message.
7. Verify `telegram_send_requests.status=sent`.
8. Verify audit and outbox processed evidence.

## 5. Skip Policy

The existing online PostgreSQL smoke tests may remain skipped when `STAGE02_ONLINE_DATABASE_URL` is not set. This is not Stage 04 failure if:

- Alembic offline SQL passes.
- Stage 04 focused tests pass.
- Staging migration evidence is recorded.

Do not point `STAGE02_ONLINE_DATABASE_URL` at local `ads_agent`, staging, or production.

## 6. Acceptance Criteria

- Every BDD scenario has an automated or manual evidence mapping.
- Full suite passes or skipped tests are explicitly justified.
- Manual staging test records exact date, environment, redacted endpoint and observed Bitable/audit evidence.
- No test requires customer group send, LLM call, provider write or funds movement.
