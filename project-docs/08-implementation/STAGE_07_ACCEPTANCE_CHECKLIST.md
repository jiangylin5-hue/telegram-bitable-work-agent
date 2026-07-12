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

### Bounded P3 Base/Table Builder Evidence

These checks cover only the approved P3 atomic Base/Table creation slice. They do not satisfy the broader unchecked Builder/import/template requirement above and do not accept Stage07.

- [x] An authorized Home capability opens a labelled Base panel that submits only Base and first-table display names and creates the exact Base/initial-table/default-Grid receipt path.
- [x] An authorized in-Base capability opens a labelled table panel and creates the exact new table/default-Grid path without choosing an older first list item.
- [x] New tables are visibly zero-field and do not expose fake record or field mutation; the next Field Builder substage is stated honestly.
- [x] Inline validation, retryable network/5xx error, same-key retry, `409` conflict lock, `403` denied cleanup and stale workspace-result rejection have focused automated evidence.
- [x] Disposable synthetic Browser QA verified P3 desktop behavior at actual `1280x720`, mobile sheet controls at actual `390x844`, and zero relevant final console warnings/errors; the fixture was stopped/deleted.
- [x] The P3 real-PostgreSQL rollback/concurrency/default-index tests ran against the authorised disposable `STAGE06_LOCAL_DATABASE_URL` on 2026-07-11 and passed. This is local database evidence only, not a Stage07 or production acceptance claim.

### F1 Independent Field Builder Evidence

These checks cover only approved independent field creation and its immediate record/form follow-through. They do not accept F2 relation/lookup, additional View Builder, import/template, governance or Stage07.

- [x] Authorised builders can create only the eleven approved F1 field types through a labelled desktop drawer/mobile full-screen sheet; the browser sends display data and choices only.
- [x] The F1 endpoint independently requires active membership + `field.manage`, rejects cross-workspace/extra/raw-policy/key/configuration inputs and returns only a safe receipt.
- [x] Safe Canvas schema, F1 receipt and create-form metadata contain no policy, raw non-choice options, default value, technical status or hidden field metadata.
- [x] The server generates the key/order/default policy, updates eligible explicit saved-view field lists atomically, writes sanitized audit and leaves existing record values empty.
- [x] Configured status/single/multi choices are validated server-side; multi-select works in record create and direct edit; legacy option-less fields preserve their documented compatibility.
- [x] Same-key replay and changed-payload `409` have automated evidence; the three matching real-PostgreSQL rollback/replay/concurrent-order cases ran and passed on the authorised disposable local database.
- [x] Browser QA has F1-scoped Workspace Ledger comparison and zero-console-error evidence at 1440/1280/430/390 for fieldless-to-first-field, nonempty-table add, validation/retry/denial, allowed-choice record creation and direct-edit success; the sanitized direct-edit screenshot is retained at `artifacts/stage07/f1-direct-edit-success-1440.png`. At all four widths, the duplicate-name allowlist feedback preserves the typed name and suppresses the server message, while a pending request disables create/close/cancel and keeps the dialog visible. Delayed workspace replacement remains covered by the application scope-isolation test. The matching real-PostgreSQL item above also passed.

### F2 Relation / Lookup Evidence

These checks cover only the approved F2 same-Base relation, fixed lookup and Builder/Picker slice. They do not accept V1 views, imports/templates, governance, Bot/Telegram, staging, production or Stage07 as a whole.

- [x] Relation initialization is same-Base, atomic and idempotent: unit/API coverage and authorised disposable PostgreSQL rollback, concurrent-order and same-key replay cases pass.
- [x] Safe transport/schema/audit output exposes no raw relation/lookup configuration, target data or policy; browser candidate and relation read models use safe `{ id, label }` projection only.
- [x] Candidate search/cursor/paging remains server-composed and protected by user/workspace query state. Initial failure, stale generation, denied cleanup and cursor retry have frontend coverage.
- [x] Existing record creation/versioned PATCH enforce relation required/target/readability/duplicate/self checks. The UI maps chips to opaque IDs only and rereads authoritative output.
- [x] Same-table Picker defense-in-depth excludes the active record from a candidate page even if it is returned by a fixture; final in-app Browser assertions at 1440px and 390px recorded `Current record = 0`, `Other record = 1` and selected `Other record × = 1`. Server-side `relation_self_reference` remains the final authority.
- [x] Lookup accepts only the seven approved aggregations; unit tests cover nested/depth/cycle behavior and a real PostgreSQL safe view projects `values`, `count`, `count_distinct`, `sum`, `average`, `min` and `max` together.
- [x] Unreadable/invalid lookup hops omit the whole lookup field; numeric-empty is the sole documented `null` case. Lookup controls are read-only in Detail/Canvas.
- [x] Real PostgreSQL dependency guards detect incoming record links and relation/target field dependencies. No DELETE route/UI, automatic unlink or cascade was added.
- [x] Local Browser fixtures cover F2 primary and negative behavior at 1440/1280/430/390. The final local-origin error/warn scan was `[]`; an in-app Browser long-panel pointer limitation is documented separately and is not misreported as a new PATCH-success visual proof.
- [x] Fresh local verification is Mini App `18` files / `93` tests, production build, dedicated F2 PostgreSQL `6 passed` and full backend `477 passed, 17 historical Stage02 online-smoke skips`.

### V1 Saved View Builder Local Evidence

The design and implementation plan are user-approved. The items remain unchecked as Stage07 acceptance because V1 is only `partial-local`: focused backend `24 passed`, local PostgreSQL `11 passed`, full backend `512 passed, 17 skipped`, Mini App `24 files / 114 tests`, build and a partial four-width disposable Browser matrix are recorded in the V1 evidence documents. The Browser run did not switch rendered owner/editor/viewer identities or cover every invalid/F2/real-backend state.

- [ ] The browser uses only typed V1 safe commands/read models; it never uses legacy raw view `config` or `permission_policy`.
- [ ] New views start private; owner/editor/viewer access intersects with active membership and underlying Base/Table/Record/Field authority.
- [ ] The existing system default Grid remains the only default and cannot be changed into a private/restricted view.
- [ ] Grid has server-owned visible field order, flat typed `AND` filters, at most three stable sorts and at most one eligible group field.
- [ ] Kanban, Calendar and Form each enforce their type-specific group/date/form-key constraint without a client fallback.
- [ ] Relation filters use F2 safe candidates; numeric lookup filter/sort is bounded; relation/lookup grouping is rejected.
- [ ] Real PostgreSQL evidence proves atomic create/grant replacement/replay/concurrency/default behavior and server filter/sort before pagination.
- [ ] Browser evidence proves private/restricted sharing, owner/editor/viewer separation and all required states at 1440/1280/430/390 with safe console output.

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

### S6.1 Telegram Identity and Deep-Link Design Boundary

These items are unchecked until TD007's reviewed implementation plan and code provide their own evidence. They do not authorize Bot delivery or a production test.

- [ ] Telegram Mini App `initData` is verified server-side using official HMAC/freshness rules; `initDataUnsafe`, URL user data and development headers cannot bypass production identity.
- [ ] A validated Telegram user resolves through active bindings to exactly one active internal member user or fails closed.
- [ ] An opaque, subject-bound, expiring pointer resolves only an authorized durable Base/view/record/draft after a server reread; no raw token/launch data leaks.
- [ ] Invalid, expired, revoked, mismatched, deleted and unauthorized pointers share safe recovery without target enumeration.
- [ ] Four-width recovery UI and desktop/no-Telegram fallback have evidence; S6.1 sends no message or external action.
- [ ] A real Telegram deep-link smoke is recorded only after separately authorized non-production Bot/test-chat setup.

## Evidence

- [ ] Automated unit, integration, contract and negative security tests pass.
- [ ] Visual QA passes at 1440px, 1280px, 430px and 390px against selected design direction.
- [ ] Telegram deep-link smoke is recorded only in an approved test environment.
- [ ] Evidence is sanitized and production launch is not claimed.

### P3 Evidence Boundary

- [x] P3 documentation records a synthetic-only fixture, safe receipts and cleanup, and explicitly excludes production/Telegram claims, raw policies/configuration, audit bodies, credentials, field data and real user records.
- [ ] Stage07-wide evidence remains incomplete: all Package 2 deliverables, Package 3, Package 4, four-width visual fidelity, approved Telegram smoke and the final exit audit still require their own evidence.
