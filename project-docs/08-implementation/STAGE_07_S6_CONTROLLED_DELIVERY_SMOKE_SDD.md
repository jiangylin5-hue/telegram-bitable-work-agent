# Stage07 S6.2 Controlled Telegram Delivery and Manual Smoke SDD

## Status and Invariants

- Status: proposed TD008 Option A; no code, migration or external operation exists.
- Scope: fixed closed-reference delivery request, explicit confirmation, one-attempt Worker dispatch and real Mini App smoke.
- Invariant: raw token/full URL exists only between `mint_telegram_deep_link` return and the single Bot client call in one Worker execution frame.
- Invariant: only one explicitly allowlisted private test chat is configured for the running non-production smoke environment.

## Architecture

```text
trusted server-only operation
  -> closed S6D request + existing authorization/audit
  -> human confirmation + existing Outbox
  -> Worker row lock / dispatch reservation
  -> binding + member + resource + allowlist recheck
  -> TD007 in-memory opaque mint
  -> fixed Bot send with one Main Mini App URL button
  -> sanitized result + audit
  -> user opens Telegram Mini App
  -> S6.1 verified identity / resolver / authorized reread
```

The request/reply interfaces stay server-owned. Mini App React code has no delivery mutation, no token mint call and no new client state. Existing S6.1 header transport remains the only browser change consumed by the smoke.

## Logical Request Contract

```py
class Stage07DeepLinkDeliveryCommand:
    workspace_id: UUID
    source_binding_id: UUID
    destination_kind: Literal["base", "view", "record", "record_change_draft"]
    destination_id: UUID
    requested_by: Stage06RequestIdentity

class Stage07DeepLinkDeliveryReceipt:
    request_id: UUID
    status: Literal[
        "pending_confirmation", "dispatch_reserved", "sent",
        "failed", "delivery_unknown", "blocked", "cancelled"
    ]
    deep_link_id: UUID | None
    outcome_code: str | None
```

`target_chat_id`, subject user and all resource-chain IDs are server-derived from the active source binding and destination. The browser receives neither command nor receipt.

## Persistence and Index Rule

The physical decision is one new `stage07_telegram_deep_link_deliveries` row keyed by its UUID with `UNIQUE(send_request_id)` to the existing `telegram_send_requests` row. It holds the closed workspace/binding/subject/target/destination context, fixed template key, dispatch state, optional minted deep-link ID and sanitized outcome. The existing request retains confirmation, Outbox and historical audit lineage and receives only the fixed neutral `message_text` for this kind.

This is the smallest additive shape that keeps historical generic send behavior unchanged and prohibits raw payload storage. No collection/search/list endpoint is in scope, so no chat/user/destination index is allowed without measured query evidence. Existing request primary-key lookup and Outbox idempotency patterns are reused.

## Worker State Rules

| Transition | Guard | Side effect |
| --- | --- | --- |
| create -> pending | trusted server actor, active binding/member, authorized destination | fixed audit only |
| pending -> confirmed | explicit authorized confirm, exact one-item allowlist | one Outbox event |
| confirmed -> reserved | Worker lock plus repeated checks | durable reservation before network |
| reserved -> sent | Bot API confirms success | save only closed link ID and sanitized message ID |
| reserved -> failed | definite Bot rejection | revoke link; no retry |
| reserved -> unknown | timeout/crash/finalization uncertainty | revoke link; no retry |
| any nonterminal -> blocked/cancelled | revocation/allowlist/authority check fails | no Bot call or future retry |

No terminal state returns to `pending_confirmation`. A new message needs a new user-confirmed request, producing a new pointer and audit lineage.

## Bot Client Contract

The future typed client method is intentionally narrow:

```py
def send_main_mini_app_link(
    *,
    chat_id: str,
    text: Literal["已生成一个受控工作区入口。"],
    button_text: Literal["打开工作区"],
    url: str,
) -> TelegramBotSendResult: ...
```

It serializes the URL only into the `reply_markup.inline_keyboard` payload for the existing Bot API call. It emits a result containing Boolean success, a numeric Telegram message ID only on success and a fixed response code on failure. It must not include request URL/body or provider error text in its returned structure.

## Configuration Contract

| Configuration | Required rule |
| --- | --- |
| `APP_ENV` | isolated non-production environment; it must satisfy the existing production-like runtime safety validation where applicable |
| `TELEGRAM_SEND_MODE` | exactly `restricted_test` |
| `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` | exactly one value, equal to the source binding target chat |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_WEBHOOK_SECRET` | present in secret manager/runtime only; never logged or committed |
| `STAGE07_TELEGRAM_BOT_USERNAME` | server-owned valid Bot username used to form Main Mini App link; no client override |
| BotFather Main Mini App | configured by authorized human to the isolated HTTPS endpoint before smoke |

## Security Review Questions Before Implementation

- Does the selected physical shape ensure every persisted string field remains token-free under unit, API, migration, worker and audit scans?
- Does a Worker crash between external send and final commit remain `delivery_unknown` with revocation and no automatic duplicate?
- Does a repeated Outbox claim stop at `dispatch_reserved` before touching the Bot client?
- Does all sender/recipient/destination authority re-evaluate at confirm and worker dispatch rather than rely on old request values?
- Does the test smoke route contain only a Main Mini App link and no custom redirect, `initDataUnsafe` or client-created destination?

## Explicit Non-Goals

No generic notification model, webhook receiver enhancement, Bot response handler, external retry engine, group policy, user history, client mutation, server-side token retrieval, raw URL audit, production environment or Stage07 completion behavior is designed here.
