# Stage07 S5 Draft and Digital Employee Hub Implementation Plan

## Status

- Status: proposed plan. Do not execute until TD005 Option A receives explicit user approval.
- Goal: deliver the bounded S5 Hub without extending into S6 Telegram/memory/lifecycle work.

## Work Groups

### G1 — Safe Contract and Draft Transition

1. Write red unit/API tests for safe contact/draft DTO exclusion, strict invocation intent, cross-Base context denial and no raw Stage06 payload forwarding.
2. Add the approved draft revision/audit-reference migration and `SELECT ... FOR UPDATE` transition UOW methods; add the pending index only if its documented `EXPLAIN` gate is met.
3. Implement safe contact/invocation/draft endpoints, fixed error mapping and versioned idempotent confirm/reject wrappers over existing Stage06 services.
4. Run migration rollback/upgrade, focused authorization/redaction tests and disposable PostgreSQL replay/race/rollback tests.

### G2 — Protected Mini App Hub

1. Write red typed parser/query/App tests for safe contact/context/invocation/draft models, 401/403/404/409 cleanup and no raw server text.
2. Build contact/context/result/draft panels with no optimistic terminal state and safe value renderers reused from Record Detail/F2 relations.
3. Wire Home queue to safe draft detail; do not treat generic queue payload as a diff.
4. Run focused tests and production build.

### G3 — Evidence and Cleanup

1. Use synthetic disposable PostgreSQL/browser fixture only; observe one permitted summary, draft creation, confirm, reject, stale/denied paths and four target widths.
2. Run console scan, audit/redaction inspection, index measurement decision, cleanup and requirement-by-requirement DE-A01..DE-A10 reconciliation.
3. Record actual command counts and remaining external Telegram/identity risks; do not claim S6 or Stage07 completion.

## Non-Negotiable Boundaries

- Reuse existing LangGraph/Stage06 runtime and record service; do not add a framework/dependency.
- No personal memory, knowledge, employee administration/publish, Telegram handoff or external send.
- All commands are server-authorized, locked/versioned/idempotent where terminal, audited and reread.
- Implementation stops if TD005 approval differs from Option A; revise documents before code.

