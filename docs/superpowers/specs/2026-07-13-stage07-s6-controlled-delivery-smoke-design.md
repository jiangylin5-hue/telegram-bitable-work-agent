# Stage07 S6.2 Controlled Telegram Delivery and Manual Smoke Design

## Status

- Status: TD008 Option A is `partial-local` on 2026-07-13. The approved closed-request/Worker/client/migration path is implemented and locally verified; external configuration and all external delivery remain unapproved pending per-environment authority.
- Goal: deliver one server-authorized, opaque S6.1 deep link to one allowlisted non-production private test chat, then prove a real Telegram Mini App handoff without persisting the raw link.
- Scope: fixed server-side request, explicit confirmation, Outbox/Worker dispatch, real Mini App open and sanitized evidence only.

## Product Outcome

```text
trusted operator request
-> explicit confirmation
-> one reserved Worker attempt
-> in-memory S6.1 link mint
-> fixed Telegram Main Mini App URL button
-> verified initData
-> existing S6.1 resolver
-> existing authorized resource reread
```

The recipient receives a neutral "Open workspace" action, not a record label, draft content, role, raw resource ID or explanation of why the link was sent. A successful click does not grant access: it still passes TD007 identity, binding, workspace and resource reauthorization.

## Components

| Component | Responsibility | Does not do |
| --- | --- | --- |
| closed delivery service | creates/validates a fixed request from trusted server context and records confirmation | accept arbitrary browser message text, target chat or URL |
| confirmation adapter | reuses current confirmed-send and Outbox audit pattern | self-confirm, silently retry or broaden role authority |
| S6.2 Worker handler | reserves one attempt, rechecks context, mints and sends in memory, records sanitized outcome | persist raw URL/token, send to a group or retry uncertainty |
| `TelegramBotClient` extension | sends fixed neutral text with one URL button | expose an arbitrary markup/message API to clients |
| S6.1 mint/resolver | supplies an opaque one-subject pointer and verifies it at open time | act as bearer access or provide a browser mint endpoint |
| human external gate | configures the non-production Bot/Main Mini App and private test target | disclose credentials or change production state |

## Server Data and API Boundary

The future implementation adds one `stage07_telegram_deep_link_deliveries` table with a unique `send_request_id` foreign key to the existing `telegram_send_requests` row. The existing row continues to own explicit confirmation, Outbox and historical audit lineage; its text is fixed neutral copy. The new typed extension owns the following server-owned fields:

```text
delivery_kind = stage07_deep_link
workspace_id
source_stage06_telegram_binding_id
subject_telegram_user_id
destination_kind
destination_id
stage07_telegram_deep_link_id        # assigned after worker mint only
dispatch_state
message_template = stage07_open_secure_destination
sanitized_telegram_message_id         # optional successful response field
sanitized_error_code                  # fixed allowlist/error code only
```

The extension has no raw payload column. Existing free-text `message_text` is fixed to a token-free neutral template for this kind. The Outbox payload has only `request_id`; it never contains destination data, Bot username or a token. The trusted initiator is server-side only, so no new Mini App route, request DTO or UI control exists.

## Dispatch and Failure Semantics

1. Create verifies the requested actor, one active source binding, its exact subject/user/chat relationship, one active workspace member and current destination action authorization. It writes `pending_confirmation` plus sanitized audit metadata.
2. Confirm independently repeats the allowlist and current authorization checks, writes one Outbox event and emits confirmation audit.
3. Worker loads and locks the request. It requires `restricted_test`, exactly one allowlisted test-chat ID and equality with the stored target. It marks `dispatch_reserved` and commits before any network call.
4. Worker rechecks binding/member/destination. It calls the S6.1 server-only mint service, receives the raw token in the current stack frame only and composes `https://t.me/{configured_bot_username}?startapp={token}`.
5. It calls the existing Bot client with fixed Chinese neutral copy and one URL button. On confirmed success it persists only the result status plus an optional numeric Telegram message identifier. It does not store the URL or body.
6. A definitive response failure becomes `failed` and revokes the minted pointer. An ambiguous network/crash/finalization case becomes `delivery_unknown`, revokes the pointer and creates no automatic retry. A human must create a new request for a new attempt.

## Security Invariants

- The request target must be one configured allowlist element and one current active binding's `telegram_chat_id`; an external command cannot choose another chat.
- `chat_instance`, profile fields and `initDataUnsafe` never choose the send target and never bypass authorization.
- Only the Worker sees the raw URL, and only while building the Bot API JSON body. Logging, exceptions and audit serializers must redact it.
- The URL button uses the configured Main Mini App bot username and opaque `startapp` token. It exposes no workspace, resource, role or draft data.
- An outbound request does not make a token a capability. Link opening repeats TD007 verification and standard authorization.
- S6.2 is at-most-one automatic attempt per confirmation, not at-least-once delivery. Uncertain delivery prefers an expired/revoked unusable link to a duplicate notification.

## External Setup Preconditions

| Item | Owner | Verification without disclosing value |
| --- | --- | --- |
| isolated non-production deployment with public HTTPS Mini App URL | authorized operator | record environment label and URL host only |
| Main Mini App configured in BotFather for that URL | authorized Bot owner | record Boolean setup outcome and Bot username only |
| `TELEGRAM_SEND_MODE=restricted_test` | operator | configuration check reports mode only |
| Bot token, webhook secret and one test-chat allowlist item | operator | runtime preflight reports present/count only, never value/ID |
| named test user owns the allowlisted private chat and has an active binding/member | operator + test user | sanitized binding/request IDs and pass/fail only |
| `STAGE07_TELEGRAM_BOT_USERNAME` | operator | regex/normalization check; no browser input |

## Acceptance Scope

Local tests must prove request and confirmation denial, target equality, state locking, token/URL absence from persistence/audit/log DTOs, worker success/definite failure/unknown behavior, link revocation and no automatic retry. A disposable PostgreSQL test must prove the lock and rollback boundaries. Browser work remains S6.1's real Telegram UI smoke rather than a new delivery screen.

The single real smoke is accepted only after all local gates pass and the user explicitly authorizes the named non-production environment. It proves actual Bot delivery, actual Telegram `initData` verification, safe resolver and authorized reread. It does not prove group delivery, production readiness, platform-wide Telegram reliability or Stage07 exit.

## Non-Goals

- Generic message composition, notifications UI, broadcast, scheduled sends, retry queue, group/channel targets or external action framework.
- User-visible delivery history, raw audit inspection, link search/export, token recovery or a second link table.
- Bot registration, production deployment, webhook feature expansion, digital-employee publication, memory, knowledge or personal assistant implementation.
