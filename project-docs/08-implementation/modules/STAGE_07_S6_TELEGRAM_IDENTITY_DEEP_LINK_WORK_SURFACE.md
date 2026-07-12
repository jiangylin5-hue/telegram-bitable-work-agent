# Stage07 S6 Telegram Identity and Deep-Link Work Surface

## Status

- Status: TD007 Option A documentation package; no S6 implementation started.
- Ownership: verified Mini App identity and safe durable destination handoff.
- Boundary: one coherent S6.1 surface, with S6.2 real Bot delivery/manual smoke explicitly separated.

## Functional Modules

| Module | Implements after implementation-plan review | Does not implement |
| --- | --- | --- |
| Mini App runtime adapter | reads raw official `initData` in memory and optional start hint | trust `initDataUnsafe`, profile fields or URL resource IDs |
| identity validator | official HMAC/freshness parsing and minimal validated launch object | user login UI, OIDC/JWT/session framework |
| binding identity resolver | active Telegram binding -> one active internal member `user_id` | choosing a role/default Base/binding or treating chat as permission |
| opaque link store/mint | short-lived token hash, user-bound durable destination and server-only mint | public link creation, link search/history/export or raw token persistence |
| safe resolver | closed Base/view/record/draft pointer or indistinguishable recovery | record/draft values, labels before authorization or resource enumeration |
| App handoff | authoritative target reread and fixed recovery/focus behavior | target reconstruction, optimistic navigation or local persistence |
| S6.2 delivery gate | records external prerequisites only | BotFather changes, webhook setup or message send in S6.1 |

## S6.1 User-Visible Behavior

1. A desktop/local user continues through the existing authorized bootstrap path.
2. A Telegram-launched user with valid official proof and one current binding sees the same authorized Home.
3. A valid server-issued start pointer enters a brief safe resolving state, then opens only the server-reread Base/view/record/draft.
4. Any invalid link condition yields a neutral recovery state that returns the user to Home without revealing target information.
5. Invalid Telegram proof clears protected UI state and requires a fresh supported launch; it never falls back to a development header in production-like environments.

## State Ownership

```text
Telegram runtime raw data: browser memory only
    -> request header: transport only, never query/cache/error
Validated launch: server request scope only
    -> Stage06RequestIdentity: server request scope only
Opaque link: Telegram start parameter + server token_hash row
    -> safe destination pointer: one App generation only
    -> normal target reread: existing protected query keys
```

No module retains raw input after the request. A resolver pointer cannot outlive its App generation, workspace change, denied response or unmount.

## S6.2 Explicit External Gate

S6.2 is not implementation work in this module. Before any real delivery/manual smoke, all conditions below must be true:

- user supplies explicit approval for a non-production Bot and test chat/user;
- Bot token, webhook secret, Mini App URL and `restricted_test`/allowlist configuration are present without being printed or committed;
- BotFather/main-app/direct-link configuration is completed by an authorized human;
- a safe delivery workflow is separately approved, continues to use the existing controlled notification/send policy and has no broad group send;
- evidence captures only sanitized outcome, opaque IDs and timestamps;
- test messages, generated links and temporary services are removed or documented after the smoke.

## Acceptance Ownership

This work surface owns S6-A01 through S6-A10. It contributes no evidence for memory, knowledge, employee lifecycle, general Bot conversation, automatic delivery, external execution, staging/production release or total Stage07 acceptance.
