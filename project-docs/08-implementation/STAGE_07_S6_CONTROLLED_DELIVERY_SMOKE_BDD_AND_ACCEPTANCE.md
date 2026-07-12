# Stage07 S6.2 Controlled Telegram Delivery and Manual Smoke BDD and Acceptance

## Status

- Status: proposed under TD008 Option A; all rows are `not-implemented` until the technical decision, implementation plan and per-environment authorization are approved.
- Scope: one fixed deep-link delivery to one private, allowlisted non-production test chat and a sanitized real Mini App smoke.
- Exclusions: browser send/mint UI, arbitrary message bodies, groups/channels/broadcasts, automatic retries, production, Telegram reply handling, provider actions and all broader Package 4 scope.

## BDD Scenarios

### S6D-01 Request contains a closed destination, never a link

Given a trusted server workflow has one active source binding, subject user, private test chat and authorized Base, view, record or record-change draft
When it creates a S6.2 delivery request
Then the request persists only closed references, the fixed template key and confirmation state
And no raw `startapp` token, URL, message body, Bot username or resource label is persisted or returned.

### S6D-02 Confirmation repeats authority and allowlist checks

Given a delivery request is pending confirmation
When a permitted operator confirms it
Then the server rechecks the current binding/member/destination and the one configured test-chat allowlist
And it creates exactly one typed Outbox event with only the request ID.

Given the configured allowlist contains zero or more than one target, differs from the request, the binding/member is inactive or destination permission has changed
When confirmation is attempted
Then it fails closed without an Outbox event, link mint or external call.

### S6D-03 Worker reserves one outbound attempt before mint/send

Given one confirmed delivery event reaches the Worker
When the Worker obtains the request lock
Then it records `dispatch_reserved` before an external Bot API call
And a repeated/claimed event observes that reservation and sends nothing.

Given the Worker cannot reserve, cannot reauthorize, cannot mint or the target is no longer allowed
When it handles the event
Then it records a fixed terminal result and sends nothing.

### S6D-04 Raw deep link is in memory only

Given a reserved delivery request passes every current check
When the Worker mints the TD007 opaque pointer
Then it creates the Main Mini App URL only in memory and sends fixed neutral text plus one URL button
And database entities, Outbox payload, audit state, exception/result DTOs and logs contain no raw token or URL.

### S6D-05 Definite and uncertain external results fail closed

Given Telegram returns a definite rejection
When the Worker finalizes the delivery
Then it records `failed`, revokes the just-minted pointer and does not retry automatically.

Given a timeout, connection reset, process interruption after reservation or post-send finalization uncertainty occurs
When the Worker reconciles the request
Then it records `delivery_unknown`, revokes the pointer and never automatically sends a second message.

### S6D-06 Real smoke proves S6.1 rather than bypassing it

Given the approved isolated Bot and private test chat receive one successful fixed delivery
When the bound test user opens the Main Mini App URL within Telegram
Then the Mini App sends actual raw `initData`, the server validates it, S6.1 resolves the opaque pointer and the ordinary authorized target reread renders
And the evidence records only sanitized outcomes, timestamps and opaque request/link IDs.

Given the recipient is not the bound subject, the binding is revoked, the pointer has expired or authorization changes before open
When the URL is opened
Then the UI receives the existing indistinguishable recovery outcome and renders no target details.

## State Matrix

| State | Persistent data allowed | External action | Required result |
| --- | --- | --- | --- |
| `pending_confirmation` | closed IDs, fixed template, audit reference | none | await explicit confirmation |
| `dispatch_reserved` | closed IDs and reservation time | none yet | duplicate event cannot send |
| `minting` (in-process only) | no raw token in persistence | none yet | raw token stack-local only |
| `sent` | closed link ID, fixed status, sanitized message ID | one Bot `sendMessage` attempt | normal S6.1 link may open during TTL |
| `failed` | fixed code and closed link ID | definite rejection only | pointer revoked; no retry |
| `delivery_unknown` | fixed code and closed link ID | result uncertain | pointer revoked; no retry |
| `blocked` / `cancelled` | fixed code | none | no link and no outbound request |

## Acceptance Matrix

| ID | Requirement | Required evidence | Status |
| --- | --- | --- | --- |
| S6D-A01 | server-only closed delivery request | unit/API negative DTO and persistence scans | not-implemented |
| S6D-A02 | confirmation rechecks exact allowlist, binding/member and resource authority | unit/API denial plus PostgreSQL rollback | not-implemented |
| S6D-A03 | one-event confirmation and lock-safe reservation | PostgreSQL concurrent confirm/worker replay cases | not-implemented |
| S6D-A04 | no raw token/URL/body persistence or audit/log leakage | service/worker/parser/source scans and negative fixtures | not-implemented |
| S6D-A05 | fixed Main Mini App URL-button Bot-client contract | client unit tests with fake HTTP transport; no real send | not-implemented |
| S6D-A06 | definite failure and unknown outcome revoke/no-retry semantics | worker state-machine and PostgreSQL tests | not-implemented |
| S6D-A07 | no browser delivery/mint route or generic message input | router/OpenAPI/client source inventory | not-implemented |
| S6D-A08 | disposable local PostgreSQL migration/index evidence | migration upgrade/downgrade, lock and rollback evidence | not-implemented |
| S6D-A09 | real one-target controlled delivery | user-authorized non-production sanitized receipt | external-authority-required |
| S6D-A10 | real Mini App `initData` -> resolver -> authorized reread | user-authorized private-chat smoke with UI inspection | external-authority-required |

## Evidence Rules

- Fake Bot clients may retain raw URLs only within the test process assertion and must not print them on failure; committed fixtures use redacted placeholders.
- Database fixtures, test evidence and audit assertions use opaque IDs and fixed status/error codes only.
- The human external smoke never copies Bot tokens, webhook secrets, raw `initData`, deep-link URL, chat ID, record values, draft values or message text into a repository document.
- The real recipient test chat is a single private target agreed by the user; a group/channel result invalidates S6D-A09 and must not be retried there.

## Non-Goals and Prohibited Claims

This document does not authorize any outgoing Telegram message, Bot configuration, webhook registration, production environment change or user-facing delivery feature. Passing a real S6D-A09/A10 smoke proves one bounded non-production path only; it is not group delivery, production readiness or Stage07 completion.
