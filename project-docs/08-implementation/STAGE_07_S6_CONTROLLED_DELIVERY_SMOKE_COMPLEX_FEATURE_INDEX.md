# Stage07 S6.2 Controlled Telegram Delivery and Manual Smoke Complex Feature Index

## Status

- Status: TD008 Option A is `partial-local` as of 2026-07-13. The minimum extension/migration and local state-machine evidence exist; real external proof remains absent.
- Scope: complex security/lifecycle properties of one controlled S6.2 delivery only.

| ID | Complex concern | Required invariant | Proof before acceptance | Status |
| --- | --- | --- | --- | --- |
| S6D-I01 | raw-token persistence | no persisted request/event/audit/log/DTO field contains raw token or URL | persistence/audit/fake-client checks pass; no integrated logger scan | partial-local |
| S6D-I02 | target fan-out | runtime allowlist has exactly one target equal to active source binding chat | configuration and changed-allowlist unit checks | implemented-local |
| S6D-I03 | stale authority | create, confirm and dispatch each recheck binding/member/destination actions | create/confirm unit revocation cases pass; dispatch-time PostgreSQL revocation matrix remains open | partial-local |
| S6D-I04 | duplicate external send | durable reservation precedes Bot call; duplicate claim never contacts client | local PostgreSQL sequential replay passes; simultaneous worker proof remains open | partial-local |
| S6D-I05 | uncertain send result | no automatic retry after timeout/crash/finalization uncertainty; pointer revoked | transport fault injection and PostgreSQL pointer-revocation case pass | implemented-local |
| S6D-I06 | generic message expansion | S6D accepts only fixed template and closed destination; no Mini App route | generic-confirm rejection and OpenAPI inventory pass | implemented-local |
| S6D-I07 | destination secrecy | Bot message/button has neutral copy and opaque link only | fixed-client payload and closed-request checks pass | implemented-local |
| S6D-I08 | Main Mini App correctness | generated URL uses configured Bot username and `startapp` value only in Bot payload | typed client/unit construction pass; real Telegram protocol smoke remains external | partial-local |
| S6D-I09 | real proof integrity | manual smoke uses one non-production private chat and actual `initData`/S6.1 reread | user-authorized sanitized receipt and UI observation | external-authority-required |
| S6D-I10 | cleanup | expire/revoke link; remove test fixtures/services; retain only sanitized evidence | post-smoke checklist and repository scan | external-authority-required |

## Physical Storage Decision

No additional collection index is proposed. The future migration is limited to the smallest typed delivery-request extension that supports lock-safe primary-key dispatch and an optional deep-link foreign key. Existing primary-key request lookup and Outbox idempotency are the only approved lookup paths. A target-chat/destination/history index, dashboard, search API or retention catalog requires a separate decision and measured query need.

## Failure Classification

| Class | Client-visible effect | Durable result | Link disposition |
| --- | --- | --- | --- |
| pre-dispatch denial | no delivery surface | `blocked` | not minted |
| Bot definite rejection | no retry action | `failed` | revoke |
| uncertain external completion | no retry action | `delivery_unknown` | revoke |
| successful Bot acceptance | normal Main Mini App entry only | `sent` | active for TD007 fixed TTL |
| link open denied/expired | existing generic S6.1 recovery | existing S6.1 result | recovery |

This index creates no broad Telegram history or messaging capability.
