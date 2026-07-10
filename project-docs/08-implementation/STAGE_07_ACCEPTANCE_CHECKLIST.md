# Stage 07 Acceptance Checklist

## Status

- Document status: planned stage acceptance checklist
- Scope: implementation acceptance, not documentation-package approval

## Foundation

- [ ] Verified Mini App and desktop identity both resolve an active workspace member through backend verification.
- [ ] Workspace switch/session expiry/revocation clear protected client state.
- [ ] Navigation is derived from server capability data and has desktop/mobile equivalents.

## Workspace And Bitable

- [ ] Home queue rows resolve to authorized durable destinations.
- [ ] Recent Base, table, saved view and record navigation works with cursor-safe paged data.
- [ ] Grid/Kanban/Calendar/Form preserve saved semantics across desktop/mobile layouts.
- [ ] Builder/import/template controls are visible and executable only when authorized.
- [ ] Record conflicts and errors refresh authoritative state without false success.

## Governance And Security

- [ ] Management routes and data reject unauthorized users independently of client navigation.
- [ ] Hidden fields and inaccessible resources do not appear in rendered states, cache, telemetry or sanitized visual evidence.
- [ ] Audit readback is paginated and redacted.

## Digital Employees

- [ ] Team Bot and personal assistant contexts are visibly different and server-authorized.
- [ ] Personal assistant has no work context until user selection.
- [ ] Team Bot memory is user-partitioned under the separately approved contract.
- [ ] Every Bot write remains `record_change_draft` until explicit confirmation.
- [ ] Confirm/reject/replay/conflict/expired states produce one authoritative outcome and audit reference.

## Evidence

- [ ] Automated unit, integration, contract and negative security tests pass.
- [ ] Visual QA passes at 1440px, 1280px, 430px and 390px against selected design direction.
- [ ] Telegram deep-link smoke is recorded only in an approved test environment.
- [ ] Evidence is sanitized and production launch is not claimed.
