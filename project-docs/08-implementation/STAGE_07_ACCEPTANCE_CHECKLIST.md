# Stage 07 Acceptance Checklist

## Status

- Document status: active historical checklist; strict final audit correction recorded
- Scope: implementation acceptance, not documentation-package approval
- Current Progress: 2026-07-15 [Stage07 Final Audit Report](STAGE_07_FINAL_AUDIT_REPORT.md) finds Stage07 `not accepted`. R1/R2 local evidence and bounded Telegram/OpenRouter proof are retained, but unchecked rows and owning BDD rows remain active wherever they identify a compatible original requirement-ID evidence gap. Only a clearly marked `contract-gated` or production-only row is outside this Stage07 decision.

## Foundation

- [x] Verified Mini App and desktop identity both resolve an active workspace member through backend verification.
- [x] Workspace switch/session expiry/revocation clear protected client state.
- [x] Navigation is derived from server capability data and has desktop/mobile equivalents.

### Existing-Contract Home/Bases Navigation Closure

These checks cover only the existing-contract Home/Bases closure. They do not accept Bot/queue/management navigation, browser visual QA, Telegram, staging, production or Stage07 as a whole.

- [x] Desktop and mobile Home/Base controls invoke one memory-only route callback and expose `aria-current="page"` only for the active route.
- [x] The directory consumes only the existing strict `api.workspaceBases` `BaseSummary[]` projection and does not render Base IDs, statuses, tables, views, records or a raw error body.
- [x] Selecting a visible row reuses existing `openBase`; later Canvas authorization remains server-owned.
- [x] Empty scope has only a fixed Home action; `503` is fixed/retryable; `401`/`403` fail closed; `404` returns Home without a fabricated directory.
- [x] The directory key is user/workspace-scoped as `navigation/bases`; a delayed old-workspace result is discarded after a switch.
- [x] No API, schema, migration, permission, dependency, URL/storage, Bot, queue, assistant, knowledge or management expansion was made.
- [x] Local evidence: `4` focused Mini App files / `18` tests and one TypeScript/Vite production build pass.
- [ ] A user-controlled full-product visual review of this route remains open. This does not negate the separate 2026-07-14 Codex in-app-Browser local integration observation.

## Workspace And Bitable

- [x] Home queue rows resolve to authorized durable destinations.
- [x] Recent Base, table, saved view and record navigation works with cursor-safe paged data.
- [x] Grid/Kanban/Calendar/Form preserve saved semantics across desktop/mobile layouts.
- [x] Builder/import/template controls are visible and executable only when authorized.
- [x] Record conflicts and errors refresh authoritative state without false success.

### R1 2026-07-15 Closure Addendum

These checks concern only already-approved current contracts. The built client ran against a disposable loopback fixture with synthetic safe DTOs; persistence, authorization and concurrency assertions remain covered by the listed focused API/PostgreSQL/client tests.

- [x] Authorized Home/Base, fixed empty Base, `403` fail-closed surface and authorized Home re-entry were observed in the built client.
- [x] Owner visibly reached Builder and template/import entries; viewer visibly omitted view/schema/record/management controls.
- [x] Grid/Kanban/Calendar/Form rendered their safe server-selected semantics. At `390 x 844`, the owner workbench and View Builder dialog remained reachable.
- [x] A synthetic View `409` displayed fixed safe copy and canonical view/row reread; raw fixture detail and opaque record identifier were not rendered.
- [x] Controlled `ImportWizard` file-input tests verified preview/mapping/explicit commit and unsupported-extension rejection. This is the documented alternative to Browser-native file selection.
- [ ] Former R1 residual: backend identity/session/revocation, Home queue-to-Draft Hub, cursor/error breadth, editor visual treatment and invalid/F2/device V1 states require requirement-ID reconciliation. See [Stage07 Final Audit Report](STAGE_07_FINAL_AUDIT_REPORT.md).

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

The design and implementation plan are user-approved. V1 is `partial-local`: V1-1 through V1-15 have current typed/server/real-local-PostgreSQL and focused client evidence, while full all-width real-backend invalid/F2/role Browser coverage remains open. The current full backend regression is `600 passed, 17 skipped`; V1's dedicated PostgreSQL matrix is `11 passed`.

- [x] The client uses only typed V1 safe commands/read models; it never consumes legacy raw view `config` or `permission_policy`.
- [x] New views start private; owner/editor/viewer access intersects with active membership and underlying Base/Table/Record/Field authority.
- [x] The existing system default Grid remains the only default and cannot be changed into a private/restricted view.
- [x] Grid has server-owned visible field order, flat typed `AND` filters, at most three stable sorts and at most one eligible group field.
- [x] Kanban, Calendar and Form each enforce their type-specific group/date/form-key constraint without a client fallback.
- [x] Relation filters use F2 safe candidates; numeric lookup filter/sort is bounded; relation/lookup grouping is rejected.
- [x] Real PostgreSQL evidence proves atomic create/grant replacement/replay/concurrency/default behavior and server filter/sort before pagination.
- [ ] Browser evidence proves private/restricted sharing, owner/editor/viewer separation and all required states at 1440/1280/430/390 with safe console output.

## Governance And Security

- [x] S3/S4 management routes and data reject unauthorized users independently of client navigation; server-side fixed actions and resource scope remain authoritative.
- [ ] Hidden fields and inaccessible resources do not appear in rendered states, cache, telemetry or sanitized visual evidence.
- [x] Audit readback is paginated and redacted through the approved S3 safe DTO; no raw forensic detail is rendered.

## Digital Employees

- [ ] Partial-local: Team Bot and personal assistant contexts are separate local workbenches/routes/DTOs/query subtrees and server-authorized in the implemented S5.3 slice; user-controlled visual review across the full product remains open.
- [x] TD009 Personal Assistant has no Home work context until a user selects an existing safe contact and a server-projected permitted view.
- [ ] Team Bot memory is user-partitioned under the separately approved contract.
- [ ] Every Bot write remains `record_change_draft` until explicit confirmation.
- [ ] Confirm/reject/replay/conflict/expired states produce one authoritative outcome and audit reference.

### S5 Bounded Draft And Digital-Employee Evidence

These rows cover only approved TD005/TD006 contact, context and draft-review paths. They do not create employee lifecycle, personal-assistant, memory, knowledge or publication scope.

- [x] Safe active contacts, fixed `summarize`/`draft_update` intents and allowlisted result transport are server-authorized; generic runtime payloads never enter Mini App state.
- [x] `draft_update` rechecks selected Base, employee View/table scope, caller-readable target and current View membership before runtime or invocation-ledger reservation.
- [x] Safe draft detail is field-filtered on every reread; confirm/reject are versioned/idempotent, confirm rechecks current field-write authority, and reject does not write a record.
- [ ] Field-filtered Browser draft lifecycle and configured real OpenRouter evidence remain required before S5 can leave `partial-local`.

### TD009 Home Personal-Assistant Context Discovery

These checks cover only the approved Home contact-to-view-to-summary slice. They do not accept the future Team Bot, employee lifecycle, memory, knowledge, record picker, Telegram or external-action surfaces.

- [x] Home opens a labelled workbench with no inferred contact, Base, view, record or persisted context.
- [x] Contacts remain the existing safe S5 projection; the server catalog returns only the active employee's current caller-readable scoped views.
- [x] The selected view is reread through the exact safe route immediately before the fixed `summarize` command; Home cannot issue `draft_update`.
- [x] Query keys are user/workspace scoped; close, selection replacement and workspace replacement invalidate assistant context state.
- [x] Only an explicit action opens the same authorized Base; the workbench has no record picker, lifecycle, memory, knowledge, migration, new permission action or external operation.
- [x] Local evidence: focused backend `17 passed`, full Mini App `51 files / 204 tests`, TypeScript/Vite production build passed.
- [ ] TD009 disposable PostgreSQL intersection/revocation, dedicated delayed workspace-replacement and user-controlled visual review remain required before this package can be promoted beyond `partial-local`.

### TD010 Digital Employee Management — Local Evidence

- [x] User approved the additive employee version/access-mode and member-grant schema/API/permission behavior and the separate detailed implementation plan before code.
- [x] Focused backend tests prove manager/use-member separation, legacy `workspace` compatibility, expected-version/idempotency conflict handling, Base/table/view scope validation, active alias collision and strict safe DTO/parser boundaries (`35 passed`).
- [x] Disposable local PostgreSQL verifies migration physical shape, downgrade/upgrade replay and legacy active-row default compatibility (`3 passed, 3 deselected`). It is not a two-session lifecycle-command contention or external environment claim.
- [x] Active/paused contact/context/invocation behavior is gated by active status and, for `assigned`, a same-workspace active member grant; no multi-Base scope, memory, knowledge, record picker, Telegram or external-action behavior is introduced.
- [x] Strict protected transport/query/workbench tests and full Mini App suite pass (`60 files / 221 tests`); production build passes.
- [x] A real two-session local PostgreSQL lifecycle-command contention test now proves one persisted pause, one revision conflict, one audit event and one idempotency record (`4 passed` dedicated PostgreSQL suite).
- [ ] User-controlled management-workbench desktop/mobile review, real Telegram/provider/staging/production evidence and whole-Stage07 exit remain open.

### S5.3 Team Bot Entry And View Knowledge — Partial Local

- [x] User selected the A+B documentation direction: Team Bot entry plus one permission-filtered saved-view knowledge window.
- [x] TD011/design/BDD/SDD/work-surface/complex-index document the closed contract, all state/error boundaries, no-index decision and explicit non-goals.
- [x] User approved the technical boundary and detailed plan, then instructed execution on 2026-07-14.
- [x] Partial-local TD011 implementation has four safe routes, server-side selected-view reread, 101/100 bounded runtime input, empty-context audit/replay, isolated Team Bot transport/cache/workbench and explicit Base handoff. Focused service evidence is `6 passed`; local PostgreSQL is `1 passed`; full Mini App is `60 files / 221 tests`; build passes.
- [x] Local Team Bot matrix now covers paused/ungranted/cross-Base pre-provider rejection, changed-key conflict and delayed `409`/`422` input-preserving replacement; a real local FastAPI/PostgreSQL in-app-Browser flow observed the empty-context audit receipt at desktop and narrow widths.
- [x] All five real OpenRouter smoke cases (`summarize_basic`, `hidden_field_guard`, `citations_required`, `draft_update_status`, `unsafe_commit_refusal`) pass with no pre-confirmation record change or raw prompt/response persistence; this does not substitute for a non-empty Team Bot UI-to-provider result.
- [ ] User-controlled full visual review, non-empty Team Bot UI-to-provider result, real Telegram/staging/production and whole-Stage07 acceptance remain open; see [final local closure evidence](evidence/stage07-final-acceptance-closure.md).
- [ ] No RAG/vector/files/memory/record picker/Telegram/direct-write capability may be claimed without a later approved decision.

### S6.1 Telegram Identity and Deep-Link Local Evidence

TD007 remains `partial-local` as a product package, not a delivery or production approval. The checked rows below reflect the approved local identity/resolver/client matrix plus one bounded, isolated non-production real Telegram identity/deep-link smoke. It does not accept staging, production or Stage07 as a whole.

- [x] Telegram Mini App `initData` is validated server-side with official HMAC/freshness, duplicate-input and malformed/forged rejection coverage; an invalid present Telegram proof cannot fall back to the development header.
- [x] A validated Telegram user resolves through active bindings to exactly one active internal member user or fails closed.
- [x] An opaque, subject-bound, expiring pointer is hash-only at rest; resolver success returns a closed pointer and the App rereads Base/View/Record/Draft before display.
- [x] Unknown, expired, revoked and subject-mismatched pointer paths return the same local safe recovery response; no raw token/launch data is exposed by the closed parser/fixture DOM.
- [x] Desktop/no-Telegram fallback and synthetic recovery/Record handoff were inspected at 1440/1280/430/390; recovery action is 44px and S6.1 has no public mint/send route.
- [x] S6.1 local target-reread matrix: `401`/`403` denied generation, `404`/`409`/`422`/network recovery and late unmount supersession are covered alongside cross-workspace recovery, field-policy projection, Resolver locking/concurrent-revoke, mismatch zero-lookup, persisted closed-audit and no-send inventory regressions.
- [x] One separately authorized isolated non-production Telegram Main Mini App smoke produced signed `initData` -> resolver -> authoritative Base reread evidence; the redacted resolver audit records only `resolved` and `base`. No raw launch data is retained and no production claim is made.

### S6.2 Controlled Delivery and Manual Smoke

TD008 Option A remains `partial-local` as a product package, while its S6.3 runtime/HTTPS and bounded real delivery/identity evidence is accepted. It reuses the existing confirmation/Outbox/Worker/`restricted_test` path through a typed one-to-one delivery extension. The actual Telegram launch exposed and corrected a missing official WebApp bridge; a separately approved fresh request then produced signed Mini App identity/resolver/Base reread evidence. The disposable S6.3 environment was removed after this evidence.

- [x] Closed server-only request/confirmation, fixed URL-button client, Worker reservation and terminal no-retry paths pass focused local tests.
- [x] Exactly-one private allowlist target, binding/member/destination confirm rechecks, generic-confirm rejection and no Mini App delivery/mint route pass negative tests.
- [x] A revoked binding confirmation persists `blocked` with no typed Outbox event in disposable PostgreSQL.
- [x] Disposable local PostgreSQL upgrade/downgrade/upgrade and success/definite-rejection/transport-uncertainty/sequential-reserved-replay cases pass.
- [x] A two-session PostgreSQL claimed-Worker collision makes at most one Bot call, does not call the replay client and revokes the pointer into `delivery_unknown`.
- [x] Direct Service/Worker/typed-client inventory has no logger sink; the exception route writes only fixed redacted codes.
- [x] Two separate user-approved one-attempt private deliveries provide bounded evidence: the first opened the Main Mini App and exposed the missing official bridge; after a test-first bridge correction, the second produced signed `initData` -> resolver -> authoritative Base reread. No automatic resend occurred.
- [x] Definite rejection and uncertain-send paths revoke the pointer and never retry automatically in the local fake-client and disposable-PostgreSQL terminal-state matrix.
- [x] Disposable PostgreSQL migration/lock/rollback and typed Bot URL-button tests pass.
- [x] One user-authorized non-production delivery produced a sanitized terminal `sent` receipt with Outbox `processed` and a message ID present; no retry was sent.
- [x] After the official WebApp bridge correction, one separately user-approved private delivery produced the signed Telegram `initData` -> resolver -> authoritative Base reread evidence. The persisted resolver audit is `resolved` for `base`; no raw launch data is retained.

### S6.3 Isolated Acceptance Deployment

S6.3 is the approved operational boundary for collecting the remaining S6 external evidence. It is a parallel non-production deployment only; it neither replaces Stage03 nor accepts production or whole Stage07.

- [x] S6.3 SDD, BDD/acceptance, work-surface, complex-index decision and implementation plan define an independent Compose project, data stores, Caddy aliases and rollback boundary.
- [x] Local Compose expansion proves independent Stage07 PostgreSQL/Redis volumes, `stage07-api`/`stage07-web` Caddy aliases and no Stage03 data-service reference; Postgres receives only its database bootstrap variables.
- [x] Candidate Caddy syntax validates through the existing Caddy container with stdin only; no active config write, reload or certificate request occurred.
- [x] DNS resolves the approved Stage07 hostname; Caddy candidate validation and active Stage07 HTTPS API/Web health are direct evidence, while Stage03 HTTPS remains healthy.
- [x] One private TD008 delivery is directly evidenced as `sent`; the recipient opened the Main Mini App, while the pre-fix missing bridge prevented resolver evidence.
- [x] The separately approved private TD008 delivery produced real signed `initData` resolver/reread evidence; the recipient observed the authorized Base and the sanitized resolver audit is `resolved`/`base`.
- [x] Following explicit cleanup approval, rollback/cleanup removed the temporary isolated Compose project/volumes/runtime, Caddy host/backup and SSH key; Stage03 health remained `200` throughout and the revoked key was rejected by batch-mode SSH.

## Evidence

- [x] Approved local unit, integration, contract and negative security suites pass: current backend `627 passed, 17 historical Stage02 online-smoke skips`; full Mini App `60 files / 221 tests`, production build, migration replay and focused Stage07 PostgreSQL evidence are recorded in [final local closure evidence](evidence/stage07-final-acceptance-closure.md).
- [ ] Visual QA passes at 1440px, 1280px, 430px and 390px against selected design direction.
- [x] The bounded TD007/TD008 isolated non-production Telegram identity/deep-link/delivery smoke is recorded; it is not staging, production, group-send or whole-stage evidence.
- [x] Recorded local evidence is sanitized and no production launch is claimed.

### P3 Evidence Boundary

- [x] P3 documentation records a synthetic-only fixture, safe receipts and cleanup, and explicitly excludes production/Telegram claims, raw policies/configuration, audit bodies, credentials, field data and real user records.
- [ ] Stage07-wide evidence remains incomplete: remaining Package 2/V1 and S3/S4/S5 Browser evidence, selected Team Bot UI-to-provider UX, contract-gated Package 4 expansion and the final exit audit still require their own evidence. The approved bounded provider and Telegram smokes are already recorded above.

## 2026-07-15 Strict Audit Correction

The earlier R0-R3 reconciliation aggregated evidence too broadly and must not supersede requirement-ID acceptance rows. [Stage07 Final Audit Report](STAGE_07_FINAL_AUDIT_REPORT.md) is the current decision.

- [ ] R1 identity/session/revocation, Home queue-to-Draft Hub, cursor retry and V1 editor/invalid/F2 treatment retain the specific V1-A02/A05/A07/A08/A10 evidence gaps named by the final audit.
- [ ] R2 governance, draft lifecycle, TD009 context discovery, TD010 lifecycle and TD011 Team Bot retain their owning BDD Browser/provider/role/failure evidence gaps.
- [x] Existing real OpenRouter safe-route evidence and bounded isolated Telegram TD007/TD008 proof are retained; neither is rerun merely for test volume.
- [x] Temporary R1/R2 loopback fixtures, servers and in-app Browser sessions were cleaned. The final fixture port `4181` is closed.
- [ ] The Stage07 R0-R3 approved product scope is **not accepted** until the compatible original requirements listed in the final audit are resolved.
- [ ] Production rollout, broad/group Telegram behavior, customer-facing group bindings, RAG/memory/files/public sharing and other contract-gated expansion are not Stage07 acceptance items. They require a new documented and user-approved decision.
