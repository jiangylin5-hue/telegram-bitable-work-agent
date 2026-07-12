# Stage07 Technical Decision 008: S6.2 Controlled Telegram Delivery and Manual Smoke

## Status

- Decision status: **approved for local implementation** by the user on 2026-07-13. It authorizes only the documented source, migration and local verification package. BotFather/webhook configuration, secret entry, external message delivery and the manual smoke remain separately subject to explicit per-environment authority.
- Scope: one non-production, explicitly confirmed Telegram Mini App deep-link delivery and end-to-end smoke path after S6.1.
- Authority: current user instruction, `AGENTS.md`, Stage07 Source Of Truth, TD007 Option A, existing `restricted_test` send policy and Stage06 authorization/audit boundaries.
- Current implementation: `partial-local`. The closed extension, server-only create/confirm service, one-attempt Worker reservation, fixed URL-button client and configuration guard are implemented. Focused local PostgreSQL proves success, definite rejection, transport uncertainty, sequential reserved replay, rollback/replay migration and pointer revocation. Concurrent dual-Worker proof, logger-integration scan and any real Telegram operation remain open.

## Decision Required

S6.1 can validate a Telegram Mini App launch and resolve a server-issued opaque pointer, but deliberately has no delivery operation. S6.2 must deliver one opaque `startapp` link to one allowlisted private test chat without persisting a raw token, letting a generic text-send endpoint mint resources, or turning a smoke test into broadcast capability.

The platform already has an explicit confirmation path, `telegram_send_requests`, `OutboxEvent`, a Redis worker, `TelegramBotClient`, `restricted_test` mode and test-chat allowlisting. It must reuse those control points rather than add a second Bot client, direct browser send, generic Telegram route or new queue framework.

## Fixed Constraints

- The operation is permitted only in an isolated non-production environment with one human-authorized test Bot and one human-attested private test chat belonging to the named test user. Groups, channels, broadcast lists and more than one allowlisted target are excluded.
- The Bot must have a Main Mini App configured by an authorized human. The generated link is fixed to `https://t.me/{bot_username}?startapp={opaque_token}`; `{bot_username}` is configuration, never client input.
- A raw token or full URL must exist only in Worker memory while the Bot API call is made. It must not enter `TelegramSendRequest`, `OutboxEvent`, database rows, audit JSON, worker logs, exception text, browser state or test evidence.
- Existing active `Stage06TelegramBinding`, `WorkspaceMember`, destination ownership and action authorization are rechecked before confirmation and immediately before mint/send.
- `TELEGRAM_SEND_MODE=restricted_test`, exactly one `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` value, a Bot token, a webhook secret and a non-production public HTTPS Mini App URL are prerequisites. Secrets and raw IDs must not be printed, committed or placed in test fixtures.
- A delivery whose external result is uncertain is fail-closed: it is marked `delivery_unknown`, any minted deep link is revoked and it is never automatically retried. A fresh human-confirmed request is required for another outbound attempt.
- This decision authorizes no browser mint/send endpoint, public delivery UI, notification campaign, Telegram reply handling, group mention delivery, external provider action, memory, knowledge, employee lifecycle, production operation or Stage07 completion claim.

## Options

| Option | Design | Advantages | Risks and decision |
| --- | --- | --- | --- |
| A — controlled request plus Worker-side mint **(recommended)** | Extend the existing confirmed-send/Outbox/Worker architecture with one fixed S6.2 delivery kind. Persist only closed resource/binding references and a neutral message template key. The Worker reserves the one attempt, rechecks authority, mints the opaque pointer in memory, sends a fixed message with the Main Mini App URL button, and records only sanitized outcome metadata. | Reuses proven confirmation, allowlist, audit, Outbox and Bot-client seams; raw URL never persists; one-attempt fail-closed semantics contain an uncertain external call. | Requires a narrowly versioned schema/service/worker/client extension and a new guarded state machine. Requires explicit approval and external authority. |
| B — reuse generic test-send text and include URL in `message_text` | A caller builds a complete deep link and passes it through the current arbitrary-message request. | Smallest code delta. | Rejected: the raw opaque token would be retained in `telegram_send_requests.message_text`, request/audit surfaces and test doubles, contradicting TD007 S6.1 secrecy rules. |
| C — human copies a direct link and manually sends it | An operator invokes the S6.1 mint service and pastes the result into Telegram. | No delivery code. | Rejected: no controlled confirmation/allowlist enforcement at send time, no durable sanitized delivery receipt, unsafe clipboard/log exposure and no product-reusable external boundary. |

## Recommended Option A

### Closed Delivery Request

The proposed physical shape is one new `stage07_telegram_deep_link_deliveries` extension row with a unique foreign key to the existing `telegram_send_requests` row. The existing request retains its confirmation, Outbox and audit lineage and stores only the fixed neutral message text; the typed extension owns closed S6.2 context. This is a fixed extension of the existing send-request domain, not a generic message API. It accepts only a trusted server-side invocation with:

```text
workspace_id
source_binding_id
subject_telegram_user_id
target_chat_id
destination_kind      # base | view | record | record_change_draft
destination_id
requested_by actor
```

The extension row records a fixed `message_template = "stage07_open_secure_destination"`, an optional post-send `stage07_telegram_deep_link_id`, state and sanitized response code/message identifier. It stores neither message body, Bot username, raw URL nor raw token. The linked existing request's `message_text` is the token-free fixed neutral copy only. No Mini App browser route can create or confirm this request.

### State Model and Exactly-One-Attempt Rule

```text
requested
-> pending_confirmation
-> dispatch_reserved
-> sent
 |-> blocked | failed | delivery_unknown | cancelled
```

`pending_confirmation` uses the existing explicit human confirmation policy. The Worker transaction locks the request, independently checks the fixed single-target allowlist and source binding, sets `dispatch_reserved`, and commits before it contacts Telegram. A subsequent delivery of the same Outbox event observes `dispatch_reserved` and does not send again.

The Worker then mints the TD007 pointer, holds the raw token only in local memory, creates the official Main Mini App deep link and calls one `sendMessage` request with fixed neutral copy plus a URL button. A definite Bot API rejection becomes `failed`; successful delivery becomes `sent`; timeout, connection reset, crash-after-dispatch or database-finalization uncertainty becomes `delivery_unknown` and revokes the minted pointer. Neither `failed` nor `delivery_unknown` is retried automatically.

### Reused and New Boundaries

| Concern | Required boundary |
| --- | --- |
| request/confirmation | reuse `TelegramSendRequest` authorization, confirmation audit and Outbox patterns; create no generic Stage07 browser endpoint |
| dispatch | reuse Redis worker registration and `TelegramBotClient`; add only a typed `send_message_with_url_button` capability needed for the fixed Main Mini App link |
| identity/destination | reuse TD007 `mint_telegram_deep_link` and current Stage06 binding/member/resource authorization; no client-supplied role or target |
| persistence | persist closed IDs, status, audit references and sanitized Telegram outcome only; no raw secret/token/URL/message body |
| external configuration | existing `restricted_test` variables plus one server-owned `STAGE07_TELEGRAM_BOT_USERNAME`; Main Mini App URL and BotFather settings are human-operated prerequisites |
| recovery | fixed operator-visible state code only; users see no target content until the Mini App resolves and rereads it through S6.1 |

### Manual Smoke Contract

The smoke runs exactly once after the implementation and local tests are accepted:

1. An authorized human prepares the isolated Bot, private allowlisted test chat, HTTPS Mini App URL and required secrets without sharing secret values in chat, code or artifacts.
2. The operator creates and explicitly confirms one closed delivery request for one fixture destination and one active test binding.
3. The Worker sends one neutral message with one Main Mini App URL button. The operator verifies only the receipt status and sanitized Bot response metadata.
4. The test user opens the button inside Telegram. The Mini App validates real `initData`, resolves the deep link and rereads the permitted destination.
5. The operator records only UTC timestamps, opaque request/link IDs, fixed outcomes and relevant sanitized status codes. The link is revoked/expired, temporary fixture data is removed and no raw URL, `initData`, chat ID, message text or secret is retained in evidence.

No retry, group test, alternative target, production Bot or broader notification flow is included in this smoke.

## Approval Boundary

The user approved Option A and its implementation-plan package on 2026-07-13. It does not authorize secret disclosure, BotFather configuration, webhook registration, delivery, external send or manual smoke execution. Those actions still require a subsequent explicit per-environment authorization identifying the non-production Bot and the single private test target.

## Official Protocol References

- Telegram documents Main Mini App links with an optional `startapp` value and confirms that this value is passed to the Mini App as `start_param`: <https://core.telegram.org/bots/webapps>.
- Telegram documents the Main Mini App direct-link syntax as `t.me/<bot_username>?startapp=<start_parameter>`: <https://core.telegram.org/api/links>.
- Telegram documents `sendMessage` and Bot API webhook behavior separately; this proposal uses only the already-existing restricted Bot API send seam, not a new inbound protocol: <https://core.telegram.org/bots/api>.
