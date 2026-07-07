# Stage 04 Restricted Test Send Module

## Status

- Document status: active module design and local implementation note
- Scope: Telegram test send request, confirmation, allowlist enforcement and worker send behavior.
- Current Progress: 2026-07-07 Restricted test send is implemented locally through config guard, `telegram_send_requests`, request/confirm API, outbox event, Redis `request_id` projection, Telegram Bot client and worker allowlist re-check/idempotency. Real staging send remains pending and requires separate confirmation.

## 1. Purpose

Restricted Test Send proves the backend can perform a controlled Telegram `sendMessage` through the outbox/worker path.

It is not a customer reply feature and not a broadcast/notification feature.

## 2. Flow

```text
request
-> pending_confirmation
-> human confirm
-> allowlist check
-> outbox event
-> worker
-> Telegram sendMessage
-> request status + audit
```

## 3. State Machine

```text
draft
-> pending_confirmation
-> confirmed
-> queued
-> sending
-> sent
-> failed
-> blocked
-> cancelled
```

## 4. Safety Rules

- Target must be in `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`.
- Worker re-checks allowlist before send.
- Send requires `TELEGRAM_SEND_MODE=restricted_test`.
- Production-like runtime rejects `restricted_test` startup without Bot token.
- Customer group and internal ops group sends are out of scope.
- No send from webhook request.

## 5. Acceptance

- Request does not send until confirmed.
- Confirm creates outbox event.
- Non-allowlisted target is blocked.
- Fake client tests prove worker behavior.
- Staging manual test proves one real allowlisted test chat message.

## 6. Implemented Files

| Layer | File | Responsibility |
| --- | --- | --- |
| Config | `backend/app/core/config.py` | Adds `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`; validates `restricted_test` fail-closed behavior |
| Model | `backend/app/models/telegram.py` | Adds `TelegramSendRequest` |
| Migration | `backend/alembic/versions/20260706_0011_stage04_telegram_send_requests.py` | Creates `telegram_send_requests` |
| API route | `backend/app/api/routes/telegram_send_requests.py` | Exposes request and confirm endpoints |
| Schemas | `backend/app/schemas/telegram_send_requests.py` | Validates create/confirm request and mutation response |
| Service | `backend/app/services/telegram_send_requests.py` | Implements request, block, confirm and outbox creation |
| Bot client | `backend/app/clients/telegram_bot.py` | Builds Telegram `sendMessage` request and stores redacted response summary |
| Worker | `backend/app/workers/stage03_handlers.py` | Handles `telegram.test_send_requested` event |
| Worker factory | `backend/app/workers/stage03_runtime.py` | Wires send handler only when bot client is available |
| Outbox bridge | `backend/app/services/outbox.py` | Projects `request_id` into Redis stream fields |
| View | `backend/app/services/bitable_views.py` | Projects `telegram_send_requests` view |
| Tests | `backend/tests/integration/test_stage04_test_send.py` | Covers request/confirm/block/permission/worker/idempotency/failure |
| Client tests | `backend/tests/unit/test_stage04_telegram_bot_client.py` | Covers request construction and redaction |
| Config tests | `backend/tests/unit/test_stage04_config.py` | Covers fail-closed config |

## 7. Runtime Config Contract

Default local behavior:

```text
TELEGRAM_SEND_MODE=dry_run
LLM_ENABLED=false
PROVIDER_MODE=disabled
```

Restricted staging behavior:

```text
TELEGRAM_SEND_MODE=restricted_test
TELEGRAM_BOT_TOKEN=<server-only secret>
TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=<comma-separated test chat ids, not committed>
LLM_ENABLED=false
PROVIDER_MODE=disabled
```

Validation rules:

| Config state | Startup result |
| --- | --- |
| local default `dry_run` | allowed |
| staging `dry_run` with DB/Redis/webhook secret | allowed |
| staging `restricted_test` without Bot token | rejected |
| staging `restricted_test` without allowlist | rejected |
| staging `restricted_test` with token and allowlist | allowed |
| staging `real`, `broadcast`, `enabled`, or any unrestricted mode | rejected |
| `LLM_ENABLED=true` in staging | rejected |
| `PROVIDER_MODE != disabled` in staging | rejected |

Config validation must not print secret values.

## 8. Data Model

Table:

```text
telegram_send_requests
```

Fields:

| Field | Meaning |
| --- | --- |
| `id` | Request id |
| `target_chat_id` | Test chat target; sensitive operational identifier |
| `message_text` | Bounded message body |
| `status` | State machine status |
| `requested_by_actor_type` / `requested_by_actor_id` | Request actor |
| `confirmed_by_actor_type` / `confirmed_by_actor_id` | Confirmation actor |
| `confirmed_at` | Confirmation time |
| `allowlist_snapshot` | Redacted allowlist evidence, count only |
| `telegram_response_summary` | Redacted Telegram response summary |
| `last_error_code` | Safe error |
| `sent_at` | Success time |
| `trace_id` | End-to-end trace |
| `created_at` / `updated_at` | Timestamps |

Forbidden fields:

- Bot token.
- Webhook secret.
- Raw Telegram API response.
- Customer notification status.
- Provider payload.
- Any payment credential.

## 9. State Machine

Documented state set:

```text
draft
pending_confirmation
confirmed
queued
sending
sent
failed
blocked
cancelled
```

Implemented Stage04 transitions:

| From | Event | To | Notes |
| --- | --- | --- | --- |
| none | request target allowlisted | `pending_confirmation` | No Telegram API call |
| none | request target not allowlisted | `blocked` | No outbox event |
| `pending_confirmation` | manager/admin confirms and target still allowlisted | `confirmed` | Writes outbox event |
| `pending_confirmation` | confirm target no longer allowlisted | `blocked` | No send |
| `confirmed` | worker starts send | `sending` transient in memory/transaction | Worker still re-checks allowlist |
| `sending` | Telegram returns ok | `sent` | Stores response summary and `sent_at` |
| `sending` | Telegram returns not ok | `failed` | Stores safe error |
| `confirmed` | worker target not allowlisted | `blocked` | Dead-letters outbox without calling Telegram |
| `sent` | worker rerun | `sent` | Idempotent no-op; no duplicate send |

Reserved states:

- `draft`: reserved for future UI.
- `queued`: reserved if a future service wants an explicit state between confirm and worker pickup.
- `cancelled`: reserved for future cancellation API.

Any future use of reserved states must update this module, tests and API contract first.

## 10. Request API

Endpoint:

```text
POST /telegram/send-requests
```

Flow:

```text
request body
-> Pydantic validation, message text max 1000 chars
-> assert `request_test_telegram_send`
-> check `target_chat_id` against settings allowlist
-> create `telegram_send_requests`
-> if allowlisted: status `pending_confirmation`
-> if not allowlisted: status `blocked`, error `telegram_test_send_target_not_allowlisted`
-> write `telegram.test_send.requested` audit
-> commit
```

Important behavior:

- This endpoint never calls Telegram.
- This endpoint never writes outbox event.
- A non-allowlisted target still creates a blocked evidence row so operators can see the safety decision.
- The allowlist snapshot records count/decision, not the actual secret allowlist.

## 11. Confirm API

Endpoint:

```text
POST /telegram/send-requests/{request_id}/confirm
```

Flow:

```text
confirm body
-> require `confirm=true`
-> assert `confirm_test_telegram_send`
-> load request
-> require status `pending_confirmation`
-> re-check target against current allowlist
-> set confirmed actor/time
-> set status `confirmed`
-> insert outbox event `telegram.test_send_requested`
-> write `telegram.test_send.confirmed` audit
-> commit
```

Outbox event:

| Field | Value |
| --- | --- |
| `event_type` | `telegram.test_send_requested` |
| `aggregate_type` | `telegram_send_request` |
| `aggregate_id` | request id |
| `payload.request_id` | request id |
| `idempotency_key` | `telegram.test_send_requested:{request_id}` |
| `trace_id` | request trace id |

Invalid states:

- Missing request returns stable not-found error.
- Confirming anything other than `pending_confirmation` returns 409 `telegram_send_request_invalid_state`.
- Re-confirming an already confirmed request does not create another outbox event.

## 12. Worker Handler

Event:

```text
telegram.test_send_requested
```

Flow:

```text
load outbox event
-> load send request by request_id
-> if event processed and request sent: return
-> if request already sent: mark event processed, commit, return
-> require request status confirmed
-> re-check target against current allowlist
-> if blocked: set request blocked, dead-letter outbox, audit, commit
-> call Telegram Bot client sendMessage
-> if ok: set sent, response summary, sent_at, outbox processed, audit
-> if not ok: set failed, safe error, outbox dead_letter, audit
-> commit
```

Idempotency:

- If Redis ack fails after DB commit, rerun sees `status=sent` and does not call Telegram again.
- Outbox event idempotency key prevents duplicate enqueue.
- Worker allowlist re-check protects against config drift between confirm and send.

## 13. Telegram Bot Client

Client behavior:

```text
POST https://api.telegram.org/bot{token}/sendMessage
json = {"chat_id": target_chat_id, "text": message_text}
timeout = 10 seconds
```

Response summary:

| Telegram response | Stored summary |
| --- | --- |
| `{"ok": true, "result": {"message_id": 42, ...}}` | `{"ok": true, "telegram_message_id": 42}` |
| `{"ok": false, "error_code": 401, "description": "..."}` | `{"ok": false, "error_code": 401}` |

The client must not store:

- Bot token.
- Full response body.
- Description that may include token/chat details.
- Message text echoed by Telegram.

## 14. Audit Contract

| Event | When | Required evidence |
| --- | --- | --- |
| `telegram.test_send.requested` | Request created or blocked | request id, status, target allowed boolean |
| `telegram.test_send.confirmed` | Human confirmation writes outbox | request id, status, outbox event id |
| `telegram.test_send.sent` | Worker sends successfully | request id, status, redacted response summary |
| `telegram.test_send.failed` | Worker receives failed response | request id, status, safe error |
| `telegram.test_send.blocked` | Confirm-time or worker-time target fails allowlist check after a request already exists | request id, blocked status, safe error |
| `permission_denied` | Actor lacks request/confirm action | action, role, actor type |

## 15. Bitable Evidence

`telegram_send_requests` view must show:

| State | Evidence |
| --- | --- |
| request created | `status=pending_confirmation` |
| blocked early | `status=blocked`, `last_error_code=telegram_test_send_target_not_allowlisted` |
| confirmed | `status=confirmed`, confirmed actor fields |
| sent | `status=sent`, `telegram_response_summary`, `sent_at` |
| failed | `status=failed`, `last_error_code` |

Customer-scoped actors should not see send request rows.

## 16. Failure Cases

| Failure | Handling |
| --- | --- |
| Request actor lacks permission | 403 and `permission_denied`; no request row |
| Target not in allowlist at request time | request row `blocked`; no outbox |
| Confirm actor lacks permission | 403 and `permission_denied`; no outbox |
| Request missing | 404 |
| Confirm wrong state | 409; no new outbox |
| Target removed from allowlist before confirm | request `blocked`; no outbox |
| Target removed from allowlist before worker send | request `blocked`; outbox `dead_letter`; no Telegram call |
| `restricted_test` missing Bot token or allowlist at startup | runtime validation rejected before serving; no request row, outbox or audit |
| Telegram API returns failure | request `failed`; outbox `dead_letter`; safe error only |
| Worker rerun after success | no duplicate Telegram call |

## 17. Test Evidence

| Requirement | Automated evidence |
| --- | --- |
| Request creates pending confirmation and no outbox | `test_send_request_api_creates_pending_confirmation_without_outbox` |
| Confirm queues outbox event | `test_send_request_confirm_queues_outbox_event` |
| Outbox bridge projects `request_id` into Redis stream | `test_test_send_outbox_event_projects_request_id_to_redis_stream` |
| Non-allowlisted target blocked | `test_send_request_non_allowlisted_target_is_blocked` |
| Message text max length enforced | `test_send_request_rejects_message_text_over_stage04_limit` |
| Unauthorized request actor blocked and audited | `test_send_request_sales_create_is_forbidden_and_audited` |
| Invalid confirm state rejected | `test_send_request_confirm_rejects_invalid_state` |
| `confirm=false` rejected without side effects | `test_send_request_confirm_false_is_rejected_without_side_effects` |
| Confirm-time allowlist drift blocked | `test_send_request_confirm_blocks_when_allowlist_changes` |
| Unauthorized confirm actor blocked and audited | `test_send_request_sales_confirm_is_forbidden_and_audited` |
| Missing send request returns stable error | `test_send_request_confirm_missing_request_returns_stable_error` |
| Worker sends allowlisted request once | `test_send_worker_sends_allowlisted_confirmed_request_once` |
| Worker re-checks allowlist | `test_send_worker_rechecks_allowlist_before_sending` |
| Worker records failed Telegram response | `test_send_worker_records_failed_telegram_response` |
| Client request construction | `test_telegram_bot_client_builds_send_message_request` |
| Client response redaction | `test_telegram_bot_client_redacts_response_summary` |
| Config fail-closed | `tests/unit/test_stage04_config.py` |

Focused command:

```text
cd backend; pytest tests/integration/test_stage04_test_send.py -v
cd backend; pytest tests/unit/test_stage04_telegram_bot_client.py -v
cd backend; pytest tests/unit/test_stage04_config.py -v
```

## 18. Staging Rules

Before any real Telegram send:

1. User must explicitly confirm staging rehearsal.
2. Server `.env` must set `TELEGRAM_SEND_MODE=restricted_test`.
3. Server `.env` must include Bot token and allowlist, but docs must not record their values.
4. Target must be a test chat or test private chat only.
5. Request and confirm must go through API.
6. Worker must process outbox event.
7. Evidence must be recorded with redacted target details.
8. Acceptance must state no customer group send occurred.

## 19. Not Implemented In Stage 04

- No customer replies.
- No broadcast.
- No customer group sends.
- No UI send button.
- No Telegram command-triggered sends.
- No rich media sends.
- No retries that duplicate successful sends.
- No production rollout.
