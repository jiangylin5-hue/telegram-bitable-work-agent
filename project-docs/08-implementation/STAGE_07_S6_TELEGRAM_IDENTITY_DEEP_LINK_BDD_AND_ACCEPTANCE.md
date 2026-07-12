# Stage07 S6 Telegram Mini App Identity and Deep-Link BDD and Acceptance

## Status

- Status: approved TD007 Option A design; S6.1 documentation is complete and implementation remains pending written implementation-plan review.
- Scope: verified Telegram Mini App identity, active binding/member resolution, safe opaque deep-link resolution and client recovery only.
- Exclusions: Bot delivery/configuration, automatic replies, memory, knowledge, personal assistant, employee lifecycle, external execution, staging/production release and Stage07 completion.

## BDD Scenarios

### S6-01 Raw Telegram launch data is verified server-side

Given a Mini App is opened from Telegram with raw `initData`
When the Mini App makes a protected request
Then it sends only the raw value in `X-Telegram-Init-Data` from memory
And the server validates the documented HMAC data-check-string with constant-time comparison before reading a user or resource.

Given a browser sends `initDataUnsafe`, an unsigned URL user ID, duplicate `hash`/`auth_date` keys, malformed user JSON, a forged hash, stale `auth_date`, future-dated `auth_date` or an overlong header
When it calls the same protected path
Then the server returns the fixed identity failure without echoing raw launch data
And no workspace, Base, record, draft, target name or cached protected state is exposed.

### S6-02 Binding is a membership lookup, not a role claim

Given a validated Telegram user has one or more active Stage06 Telegram bindings
When every binding points to an active workspace member with the same internal `user_id`
Then the identity adapter returns that user as `source='telegram_binding'`
And every later Base/view/record/draft request still resolves current active membership and normal action authorization.

Given no active binding exists, a binding references an inactive/missing member, or active bindings resolve to different internal users
When the Mini App request arrives
Then it fails closed with the stable binding-denied result
And the server never selects the first binding, the highest role or a default Base.

### S6-03 Telegram context does not become a hidden authorization channel

Given validated Mini App launch data includes `chat_instance`, `chat_type`, profile fields or a start parameter
When the identity adapter resolves a platform request
Then only the validated Telegram user maps through the existing binding/member chain
And `chat_instance`, profile fields and browser query parameters never identify a raw Telegram chat, role or resource permission.

Given a deep link was issued from a source chat
When the same subject user opens it
Then source chat context is checked only through the server-stored link/binding evidence
And the target is still authorized through current workspace/resource rules.

### S6-04 A deep link is an opaque pointer, not a bearer authorization grant

Given a trusted server workflow has minted an active, unexpired pointer for one subject Telegram user, its source-chat binding and one durable Base, view, record or record-change draft
When that exact subject launches the Mini App with the matching signed `start_param`
Then the resolver hashes the raw token, loads only its server row, confirms its current status/expiry/subject plus still-active source-chat binding and reruns resource ownership plus authorization
And it returns only a closed safe destination pointer.

Given another user receives the raw URL, the source binding/resource is deleted, membership is revoked, a field/resource permission has changed, the link is revoked or the link expires
When the resolver receives the launch
Then it returns the same safe recovery outcome without revealing which condition occurred
And no destination content is rendered or retained.

### S6-05 Link resolution is bounded and non-enumerable

Given a valid Telegram identity but a missing, malformed, unknown, expired, revoked, subject-mismatched, unauthorized or deleted token
When the browser calls `POST /mini-app/telegram/deep-links/resolve`
Then it receives `200 { outcome: 'recovery' }`
And it cannot distinguish token existence, target type, expiry reason, linked chat, workspace or resource label.

Given a raw `startapp` query hint differs from the `start_param` inside verified `initData`
When the resolver is called
Then it returns recovery and performs no target lookup after the mismatch check.

### S6-06 Resolution navigates only after an authoritative reread

Given the resolver returns a safe destination pointer
When App root handles it
Then it triggers the existing authorized Base/view/record/draft opening flow and rereads server data before rendering target content.

Given that reread returns `401`, `403`, `404`, `409`, `422`, network failure or a superseding workspace/launch context
When the request completes
Then App root clears only the documented protected keys or full state as appropriate, discards stale resolution and shows fixed recovery/denial feedback
And it never synthesizes a destination from pointer IDs or displays raw server detail.

### S6-07 No launch data or Telegram runtime is a normal desktop/local case

Given the app runs in desktop browser or approved local/test development without an official Telegram runtime
When a verified adapter or local development identity is otherwise available
Then the existing identity path continues unchanged
And no Telegram error, header, start parameter or deep-link resolver call is added.

Given staging/production has neither a verified Telegram launch nor another configured verified adapter
When a protected request occurs
Then it returns `401`; the development header never becomes a fallback.

### S6-08 Responsive recovery remains usable

Given a resolver is loading, recovers or is denied at `1440`, `1280`, `430` or `390` widths
When the user sees the App shell
Then text explains the state without exposing target details, a labelled Home/retry action is reachable, focus has a predictable destination and Telegram safe-area insets do not hide the action.

### S6-09 S6.1 does not send or publish anything

Given any identity validation or deep-link resolution path is exercised
When the operation succeeds, recovers or fails
Then it does not call `sendMessage`, `answerWebAppQuery`, a provider, external service or digital-employee write action
And it does not create a memory entry, conversation, contact publication, notification send or automatic reply.

## State Matrix

| Client-visible state | Identity state | Link state | Safe result | Required cleanup |
| --- | --- | --- | --- | --- |
| normal desktop/local | existing valid identity | absent | existing authorized Home | none beyond current rules |
| telegram home | verified and uniquely bound | absent | authorized Home | no link key created |
| resolving | verified and uniquely bound | matching active pointer | labelled pending | do not preview target |
| resolved | verified and authorized | active/live target | closed pointer then reread | discard pointer after open completes |
| recovery | verified and uniquely bound | invalid/revoked/expired/missing/denied | fixed recovery | remove exact S6 link/workspace target state |
| identity denied | forged/stale/missing production proof | not examined | fixed session recovery | remove all protected state |
| binding denied | proof valid but member mapping invalid/ambiguous | not examined | fixed denied recovery | remove S6/current workspace state |
| stale result | launch/workspace changes while resolving | any | discard result | no old target restores |

## Acceptance Matrix

| ID | Requirement | Required evidence | Status |
| --- | --- | --- |
| S6-A01 | official HMAC/freshness/duplicate input validation | pure service test vectors, malformed/future/stale/forged API tests | unevaluated |
| S6-A02 | active binding resolves exactly one member user | unit/API none/inactive/ambiguous/same-user-multiple-binding matrix | unevaluated |
| S6-A03 | normal resource authorization remains authoritative | Base/view/record/draft cross-workspace/revoked-field denial tests | unevaluated |
| S6-A04 | raw launch data never leaks | DTO/error/audit/client parser/cache/DOM negative tests | unevaluated |
| S6-A05 | opaque link hash/expiry/revocation/subject rules | migration plus disposable PostgreSQL uniqueness/race/expiry/revoke tests | unevaluated |
| S6-A06 | resolver is non-enumerable and mismatch-safe | endpoint response equivalence and no-target-lookup tests | unevaluated |
| S6-A07 | resolved target is reread and stale-safe | App query/route tests for 401/403/404/network/workspace replacement | unevaluated |
| S6-A08 | desktop fallback and four-width recovery path | component/build and synthetic Browser matrix | unevaluated |
| S6-A09 | no S6.1 delivery/external action leak | route/client inventory, mock transport negative test | unevaluated |
| S6-A10 | real Telegram manual smoke is bounded | user-authorized non-production bot/test-chat evidence, sanitized only | external-authority-required |

## Evidence Rules

- Synthetic `initData` fixtures use a test-only token and fictional user IDs. They are not credentials and must not be committed as real signed launch data.
- Disposable PostgreSQL tests reset their schema and retain no raw token, message body, Bot token or real Telegram identity in output.
- Browser evidence may use a synthetic verified adapter and fixed resolver outcomes; it does not count as a real Telegram identity smoke.
- A real manual smoke requires user authority, a non-production bot and allowlisted test chat/user. It may record only outcome, sanitized timestamps and opaque IDs; no Bot token, raw `initData`, full chat ID or message body.

## Non-Goals and Prohibited Claims

This document does not approve actual Bot configuration, link delivery, webhook registration, message sends, employee publication, memory, knowledge, broad Telegram group operation, staging/production deployment or Stage07 acceptance. No implementation report may claim a real Telegram identity or deep-link success without the separately authorized manual test evidence.
