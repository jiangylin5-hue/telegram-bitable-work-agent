# Stage07 S6.2 Controlled Telegram Delivery and Manual Smoke Work Surface

## Status

- Status: TD008 Option A work surface is `partial-local` as of 2026-07-13. The server-only request/confirm, Worker state machine and fixed-client seams are implemented; Bot configuration and sending remain prohibited pending separate per-environment authority.
- Ownership: one opaque deep-link handoff from a trusted server workflow to one private restricted-test chat, followed by S6.1's existing Mini App entry.

## Functional Modules

| Module | Implements after approval | Does not implement |
| --- | --- | --- |
| trusted delivery command | derives binding/subject/chat/destination from server context and records a closed request | browser request DTO, manual chat entry, arbitrary text or raw URL |
| confirmation and Outbox | reuses existing explicit confirmation/audit/event seams | self-confirmation, bulk creation, scheduled retry or batch send |
| reserved Worker dispatch | lock, recheck, one attempt, in-memory mint and sanitized result state | raw token persistence, automatic retry or multi-target fan-out |
| Bot URL button | fixed neutral text and one Main Mini App link | message templating, inline chat actions or Telegram response handling |
| external smoke | one private test user opens a real Mini App, proving S6.1 verification/reread | group send, production proof or platform-wide reliability claim |

## User-Visible Behavior

1. No Mini App user sees a delivery composer or token.
2. The authorized test user receives one neutral Telegram action labelled `打开工作区`.
3. Tapping it opens the configured Main Mini App with an opaque start parameter.
4. Valid subject and current authorization open the existing safe target; every other result is S6.1 recovery.
5. A failed or uncertain delivery creates no duplicate retry and reveals no link details to a client.

## Boundary Map

```text
server-only request/confirm
    -> existing outbox
        -> restricted Worker (one attempt)
            -> in-memory URL
                -> Telegram Bot API
                    -> Telegram Mini App runtime
                        -> existing S6.1 resolver / App reread
```

The only durable crossing value that later S6.1 consumes is the hashed deep-link row and its closed pointer state. Browser memory may contain Telegram's raw `initData` under TD007 but never the delivery request/token history.

## Explicit Exclusions

- automatic direct send from an employee, agent or browser;
- more than one test recipient, any group/channel/broadcast or public send;
- mutable content, record/draft summaries, target labels, user profile data or chat identifiers in message UI;
- external-message dashboard, retry button, token list/search/export or persistent recipient chat state;
- BotFather/webhook operations by source code, production setup or Stage07 completion claim.

## Acceptance Ownership

This surface owns S6D-A01 through S6D-A10. It contributes only one controlled external delivery and real S6.1 handoff proof. It does not accept S5 provider work, employee lifecycle, memory/knowledge, general Telegram conversation or final Stage07 release.
