# Stage07 S6.2 Controlled Telegram Delivery Implementation Plan

> **For agentic workers:** use `superpowers:executing-plans` and `superpowers:test-driven-development`. Finish each coherent task with focused evidence before starting the next one.

## Status

- Plan status: approved for local implementation on 2026-07-13 with TD008 Option A.
- External status: BotFather/Main Mini App setup, secret configuration, real message delivery and manual smoke remain `external-authority-required`.
- Scope: one server-only closed-reference request, explicit existing confirmation, one Worker-reserved attempt and a fixed Main Mini App URL button.

## Goal

Implement the smallest additive S6.2 path that can deliver a TD007 opaque pointer to exactly one configured private test chat without retaining the raw token or URL. The existing `TelegramSendRequest`, Outbox, Redis worker and `restricted_test` controls remain authoritative.

```text
trusted server command
-> closed delivery extension + neutral existing send request
-> existing explicit confirmation + one typed Outbox event
-> row-lock reservation committed before network
-> current binding/member/destination recheck
-> in-memory TD007 mint -> fixed Bot URL button
-> sent | failed | delivery_unknown + sanitized audit
```

## Fixed Boundaries

- No Mini App route, UI button, request DTO, generic text field or client-side minting is created.
- `target_chat_id`, `subject_telegram_user_id` and source binding are derived from one active `Stage06TelegramBinding`; the caller cannot supply them.
- Existing `telegram_send_requests.message_text` receives only the fixed neutral copy. Raw token, full URL, Bot username, destination label/value and provider text are absent from persistence, audit, Outbox, logs and result DTOs.
- `TELEGRAM_SEND_MODE` must be `restricted_test`; the allowlist must contain exactly one entry and equal the binding chat. Worker-side mismatch blocks before mint/send.
- The one automatic external attempt is reserved and committed before the Bot call. Duplicate/replayed work sees `dispatch_reserved`, marks the delivery `delivery_unknown`, revokes any already persisted pointer and never calls Telegram.
- A Bot rejection is `failed`; transport exception or any post-dispatch ambiguity is `delivery_unknown`. Both revoke the pointer and create no retry. The only later attempt is a fresh user-confirmed request.

## Architecture Choices

| Concern | Reused seam | Minimal addition |
| --- | --- | --- |
| request and confirmation | `TelegramSendRequest`, `confirm_test_telegram_send`, Outbox/audit patterns | one typed one-to-one `Stage07TelegramDeepLinkDelivery` extension and one server-only command service |
| authorization | `Stage06PlatformUnitOfWork`, TD007 source-binding/destination checks | public TD007 pre-mint authorization helper shared by create, confirm and Worker |
| dispatch | Stage03 Redis worker and existing `TelegramBotClient` | typed `send_main_mini_app_link` and a single event handler |
| storage | PostgreSQL/Alembic UUID/FK/row locks | unique request FK and closed state fields; no history/search index |
| client | existing S6.1 `initData`/resolver/re-read | none |

## Task 1 — Add the closed extension and migration

**Files**

- Modify: `backend/app/models/stage07_telegram.py`, `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260713_0026_stage07_telegram_deep_link_deliveries.py`
- Modify: `backend/app/services/stage06_platform.py`
- Tests: `backend/tests/unit/test_stage07_telegram_deep_link_delivery.py`, `backend/tests/integration/test_stage07_telegram_deep_link_delivery_postgres.py`

**Shape**

`Stage07TelegramDeepLinkDelivery` contains only `send_request_id` (unique FK), `workspace_id`, `source_binding_id`, `subject_telegram_user_id`, `target_chat_id`, `destination_kind`, `destination_id`, fixed `message_template`, `dispatch_state`, optional `stage07_telegram_deep_link_id`, sanitized message ID/error code, timestamps and the normal UUID key. Check constraints permit only the four TD007 kinds, fixed template and states `pending_confirmation`, `dispatch_reserved`, `sent`, `failed`, `delivery_unknown`, `blocked`, `cancelled`.

There is no JSON payload and no target-chat/destination/history index. Add UoW methods for add/get delivery, get-by-send-request and locked Worker lookup. SQLAlchemy applies `SELECT ... FOR UPDATE`; in-memory behavior is deterministic for unit tests.

**TDD evidence**

1. Write failing metadata/migration/UoW tests for unique `send_request_id`, fixed state/kind/template constraints and `FOR UPDATE` lookup.
2. Implement model, UoW methods and additive upgrade/downgrade from `20260712_0025`.
3. Run model/unit tests and disposable PostgreSQL upgrade, downgrade, duplicate-FK and lock tests.

## Task 2 — Build the server-only request and confirmation service

**Files**

- Create: `backend/app/services/stage07_telegram_deep_link_delivery.py`
- Modify: `backend/app/services/stage07_telegram_deep_links.py`
- Modify: `backend/app/services/telegram_send_requests.py`
- Tests: `backend/tests/unit/test_stage07_telegram_deep_link_delivery.py`, `backend/tests/integration/test_stage07_telegram_deep_link_delivery_api.py`

**Interfaces**

```python
Stage07TelegramDeepLinkDeliveryCommand(
    workspace_id: UUID,
    source_binding_id: UUID,
    destination: TelegramDeepLinkDestinationInput,
)

create_stage07_telegram_deep_link_delivery(..., actor: Actor, allowed_chat_ids: tuple[str, ...])
confirm_stage07_telegram_deep_link_delivery(..., actor: Actor, request_id: UUID, allowed_chat_ids: tuple[str, ...])
```

The command is Python/server-only. It has no FastAPI route or Pydantic browser schema. The service derives the subject/chat from the exact active source binding and creates a neutral existing `TelegramSendRequest` plus its extension in the same transaction. It records a closed audit and returns only internal receipt data to the trusted server caller.

Extract a public TD007 pre-mint helper that validates user actor, source binding/member, expected workspace and destination authorization without minting a token. Use it at request creation, confirmation and Worker dispatch. Confirmation reuses `confirm_test_telegram_send` permission/audit semantics but emits `stage07.telegram_deep_link_delivery_requested`, `max_attempts=1` and a payload containing **only** `request_id`.

**TDD evidence**

1. First test one active binding creates a neutral request and closed extension with no caller-selected chat or raw URL/token.
2. Add red tests for zero/multiple/mismatched allowlist, inactive binding/member, cross-workspace or denied destination; each asserts no Outbox event and no deep link.
3. Add confirm/replay tests: one typed event, current authorization rechecked and a second confirmation rejected.
4. Implement only the closed command/confirmation path and prove source/API inventories contain no S6.2 browser route or generic sender expansion.

## Task 3 — Add the typed Bot-client URL-button capability and configuration guard

**Files**

- Modify: `backend/app/clients/telegram_bot.py`
- Modify: `backend/app/core/config.py`
- Tests: `backend/tests/unit/test_stage07_telegram_deep_link_delivery.py`, `backend/tests/unit/test_stage04_telegram_bot_client.py`, `backend/tests/unit/test_stage04_config.py`

**Implementation**

Add `send_main_mini_app_link(chat_id, url)`; text and button label are module constants, not parameters. It serializes the raw URL only into Telegram's `reply_markup.inline_keyboard` request body. Its result has only `ok`, an optional numeric message ID and fixed error code; it never returns provider text/body.

Add server-owned `STAGE07_TELEGRAM_BOT_USERNAME`. The worker enables the S6.2 handler only when it is a valid Bot username and the pre-existing restricted-test configuration is active. Do not make ordinary historical `restricted_test` sends require the new setting. The local validator reports only fixed missing/invalid codes.

**TDD evidence**

1. Red test verifies one URL button, fixed neutral text and no arbitrary markup/text method.
2. Red tests reject absent/invalid username and zero/multiple allowlist only when the S6.2 handler is requested.
3. Implement the narrow client/config behavior, including redacted response conversion and no logging of the request body.

## Task 4 — Implement reserve-before-send Worker state machine

**Files**

- Modify: `backend/app/workers/stage03_handlers.py`, `backend/app/workers/stage03_runtime.py`
- Modify: `backend/app/services/stage07_telegram_deep_link_delivery.py`
- Tests: `backend/tests/unit/test_stage07_telegram_deep_link_delivery.py`, `backend/tests/integration/test_stage07_telegram_deep_link_delivery_postgres.py`, `backend/tests/integration/test_stage03_worker_runtime.py`

**State algorithm**

1. Lock the extension/request/Event; require typed event, `confirmed` request, exact single allowlist and current TD007 pre-mint authorization. Store `dispatch_reserved` and commit before the Bot client is called.
2. In a second transaction, rerun the same checks and mint the TD007 pointer. Persist only its durable link ID before network so a crash/replay can revoke it; the raw token stays in the active Worker frame.
3. Build `https://t.me/{configured_bot_username}?startapp={raw_token}` only for `send_main_mini_app_link`.
4. On confirmed success, persist `sent`, closed message ID and processed Outbox event. On definite rejection, persist `failed`, revoke the link and dead-letter the event. On client exception, duplicate reservation, post-send finalization failure or any ambiguous state, persist `delivery_unknown`, revoke and dead-letter. It never raises a retryable error after a reservation.

The implementation must use a fresh/rolled-back SQLAlchemy transaction for the post-send uncertain-finalization path; it must not reuse a failed session to pretend the revocation succeeded. Duplicate worker work calls no Bot client.

**TDD evidence**

1. Red tests for reserve-then-client call order, duplicate replay, definite failure and thrown transport exception.
2. Red test injects a finalization failure after fake success; it observes `delivery_unknown`, pointer revocation and no second call.
3. Implement fixed code outcomes and sanitized audits. Audit assertions reject raw token, URL, Bot username, request body and provider text.
4. Real PostgreSQL two-session test proves the reservation lock and a replay cannot send twice; rollback tests prove blocked/failed/unknown state and link revocation survive.

## Task 5 — Local acceptance, documentation reconciliation and cleanup

**Commands**

```powershell
cd backend
pytest tests/unit/test_stage07_telegram_deep_link_delivery.py tests/unit/test_stage07_telegram_deep_link_api.py tests/unit/test_stage04_telegram_bot_client.py tests/unit/test_stage04_config.py tests/integration/test_stage07_telegram_deep_link_delivery_api.py tests/integration/test_stage07_telegram_deep_link_delivery_postgres.py -q
pytest -q
alembic upgrade head
alembic downgrade 20260712_0025
alembic upgrade head
```

Run the disposable local PostgreSQL subset only with the established local smoke URL. No real Bot token, public URL, chat ID, Browser fixture or external service is required for S6D-A01--A08. Run `rg`/source-inventory checks to prove no Mini App delivery/mint route and no raw link persistence.

Update TD008, BDD, SDD, work surface, complex index, source-of-truth, progress, traceability, roadmap and acceptance checklist with exact test output. Mark S6D-A09/A10 `external-authority-required`; do not configure a Bot, send a message or call Telegram while completing this task.

## Acceptance Mapping

| Acceptance | Plan task |
| --- | --- |
| S6D-A01 / A02 | Task 1 + Task 2 |
| S6D-A03 / A06 | Task 4 |
| S6D-A04 / A07 | Task 2 + Task 4 + inventory |
| S6D-A05 | Task 3 |
| S6D-A08 | Task 1 + Task 4 PostgreSQL proof |
| S6D-A09 / A10 | explicitly excluded pending per-environment authority |

## Explicit Non-Goals

No UI delivery composer/history, generic Telegram send API, retry mechanism, multi-target/group/channel send, Browser minting, BotFather/webhook mutation, employee lifecycle, memory/knowledge, provider action, staging/production action or Stage07 completion claim is part of this plan.
