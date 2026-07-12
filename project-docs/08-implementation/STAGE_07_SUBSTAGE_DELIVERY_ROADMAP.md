# Stage07 Substage Delivery Roadmap

## Status

- Document status: active Stage07 delivery roadmap
- Purpose: organize Stage07 as coherent substages rather than individual UI/API fragments
- Current active substage: S6.1 Telegram Mini App identity/deep-link local acceptance reconciliation. S5 remains partial-local with separate provider/Browser evidence gaps; S4 retains its negative-lifecycle evidence gap.

## Delivery Rule

Every substage follows one uninterrupted cycle:

1. Complete source, design, BDD, SDD, work-surface, complex-index and implementation-plan documents.
2. Obtain one approval for its technical/API/schema/permission boundary where needed.
3. Deliver backend and frontend as a coherent vertical package.
4. Run focused tests, proportional real PostgreSQL evidence, one built-UI path, cleanup and BDD-by-BDD evidence reconciliation.
5. Report functionality, changed scope, explicit exclusions, exact evidence and risks.

No local implementation is Telegram, staging, production or Stage07 completion evidence.

## Substage Map

| ID | Substage | Product outcome | Current state | Boundary |
| --- | --- | --- | --- | --- |
| S0 | Foundation and protected UI state | verified bootstrap, workspace switching, shell and safe cache/error boundary | implemented-local | existing Stage06 contracts |
| S1 | Bitable authoring and records | Base/Table, F1 field, F2 relation/lookup and Record Detail work | implemented-local / partial-local | existing builder contracts |
| S2 | Views, template and import | saved views, template/install/save, CSV/XLSX server preview/import | implemented-local / partial-local | existing contracts; Browser file upload unproven |
| S3 | Governance Readback | safe paged member directory and Base audit timeline | implemented-local; Browser external evidence pending | Technical Decision 003 |
| S4 | Governance Write | bounded member-role, field-policy and existing V1 view-grant operations | implemented-local; negative lifecycle evidence partial | Technical Decision 004 |
| S5 | Draft and Digital Employee Hub | field-filtered draft review, contacts and assistant surface | partial-local; provider/Browser/acceptance evidence pending | approved Technical Decision 005 Option A and TD006 Option A |
| S6 | Telegram identity, deep link and final acceptance | verified identity/deep link, bounded external smoke and final safety/visual matrix | S6.1 `partial-local`: implementation, focused backend/Mini App tests and PostgreSQL evidence exist; four-width target Browser and S6.2 external evidence pending | TD007 Option A plus later user authority for test bot/delivery |

## S3 Governance Readback

### Scope

- Server-authorized, cursor-paged member directory.
- Server-authorized, strict Base audit timeline.
- Existing protected QueryClient cleanup, safe error/denied states and responsive UI.
- Browser-safe DTOs that exclude trace, actor/entity identity, audit state and permission state.

### Not In Scope

- Member invitation/deactivation, role or policy write.
- Audit export/search/filtering/raw forensic details.
- Bot lifecycle, knowledge/memory, draft detail/confirmation, Telegram entry or deployment.

### Required Documents

| Artifact | Location |
| --- | --- |
| API decision | STAGE_07_TECHNICAL_DECISION_003_GOVERNANCE_SAFE_READ_MODEL.md |
| design | docs/superpowers/specs/2026-07-12-stage07-governance-readback-design.md |
| BDD / SDD | STAGE_07_GOVERNANCE_READBACK_BDD_AND_ACCEPTANCE.md / STAGE_07_GOVERNANCE_READBACK_SDD.md |
| work surface / complex index | modules/STAGE_07_GOVERNANCE_READBACK_WORK_SURFACE.md / STAGE_07_GOVERNANCE_READBACK_COMPLEX_FEATURE_INDEX.md |
| implementation plan | docs/superpowers/plans/2026-07-12-stage07-governance-readback-implementation.md |
| final evidence | evidence/stage07-governance-readback.md |

### S3 Exit Criteria

- GR-A01 through GR-A06 reconciled against fresh evidence.
- Legacy generic member/audit HTTP contracts remain unchanged.
- Prohibited audit fields are absent from wire response, parser, state, DOM, URL and telemetry.
- 401, 403, 404, cursor failure and workspace/Base replacement have explicit tested cleanup.
- Disposable local PostgreSQL and focused built-UI paths use synthetic data only.
- Temporary fixtures/services are removed; no production/Telegram claim is made.

## S4 Governance Write

### Implemented Scope

- Versioned change of an existing active member's fixed role, under server-side owner/admin target constraints.
- Versioned replacement of a field's fixed five-role `hidden/read/write` policy.
- Reuse of existing V1 restricted-view grant replacement; no second view-policy engine.

### Not In Scope

- Invitation, deactivation, owner transfer, custom role/action editor, group/per-user policy or access simulation.
- Field configuration/value changes, public view sharing, generic audit detail/export, Bot/draft/Telegram/deployment work.

### Required Documents Before Code

| Artifact | Location |
| --- | --- |
| decision | STAGE_07_TECHNICAL_DECISION_004_GOVERNANCE_WRITE_CONTRACT.md |
| design | docs/superpowers/specs/2026-07-12-stage07-governance-write-design.md |
| BDD / SDD | STAGE_07_GOVERNANCE_WRITE_BDD_AND_ACCEPTANCE.md / STAGE_07_GOVERNANCE_WRITE_SDD.md |
| work surface / complex index | modules/STAGE_07_GOVERNANCE_WRITE_WORK_SURFACE.md / STAGE_07_GOVERNANCE_WRITE_COMPLEX_FEATURE_INDEX.md |
| implementation plan | docs/superpowers/plans/2026-07-12-stage07-governance-write-implementation.md |
| final evidence | created only after implementation and reconciliation |

### Exit Criteria

- GW-A01 through GW-A08 have evidence; every rejected mutation proves no write.
- Revision migration upgrade/rollback/replay and concurrent mutations pass against disposable local PostgreSQL.
- Field visibility/write behavior remains enforced across schema, presentation, record detail, lookup and record update.
- Existing V1 grant route remains the only view-member mutation path.
- Built UI Browser evidence covers all required widths with synthetic data; cleanup is documented.

## S5 Draft and Digital Employee Hub

### Approved Scope

- Server-safe active digital-employee contacts scoped by existing workspace/Base membership.
- Explicit selected Base/view/record context for fixed `summarize` and `draft_update` intents only.
- Field-filtered immutable draft diff and revisioned/idempotent confirm/reject terminal receipts.
- Existing Stage06 LangGraph/runtime, record validation, idempotency and audit reuse through narrow Mini App adapter routes.

### Not In Scope

- employee create/edit/publish lifecycle, personal memory, knowledge source, conversation persistence or browser storage;
- Telegram alias/deep links/group handoff, notification send/external execution or production identity;
- raw runtime/record/draft config exposure, arbitrary agent tool/runtime selection or agent self-confirmation.

### Required Documents and Gate

| Artifact | Location |
| --- | --- |
| decision | STAGE_07_TECHNICAL_DECISION_005_DRAFT_EMPLOYEE_HUB.md |
| design | docs/superpowers/specs/2026-07-12-stage07-s5-draft-employee-hub-design.md |
| BDD / SDD | STAGE_07_DRAFT_EMPLOYEE_HUB_BDD_AND_ACCEPTANCE.md / STAGE_07_DRAFT_EMPLOYEE_HUB_SDD.md |
| work surface / complex index | modules/STAGE_07_DRAFT_EMPLOYEE_HUB_WORK_SURFACE.md / STAGE_07_DRAFT_EMPLOYEE_HUB_COMPLEX_FEATURE_INDEX.md |
| implementation plan | docs/superpowers/plans/2026-07-12-stage07-s5-draft-employee-hub-implementation.md |

TD005 Option A is approved for S5 implementation. It authorizes only the two draft columns, the documented measured queue-index decision, safe Mini App routes and the bounded S5 UI described here. The local I-A measurement reused the existing Base/status index and did not justify a new partial-index migration. It does not authorize S6 scope. TD006 Option A is also approved and implemented locally: App root may pass opaque current-Canvas IDs without a new route. It does not authorize a standalone picker, generic context projection, storage or S6 scope.

### Exit Criteria After Approval

- DE-A01 through DE-A10 are reconciled against fresh code, PostgreSQL, client and Browser evidence.
- Generic Stage06 runtime/draft APIs remain unchanged and never reach the browser.
- Draft field filtering, current-write recheck, terminal revision/idempotency/audit reference and no-record-write reject have real PostgreSQL evidence.
- No memory/knowledge/Telegram/publication/external-send route or persistent client state is added.
- TD006 current-Canvas bridge passes only opaque IDs; it does not query generic context or retain it after Canvas/workspace replacement.
- The pending queue returns only `pending_confirmation` rows in newest-first keyset order. Its local `512` pending / `1,536` terminal PostgreSQL measurement reuses the existing Base/status index; no S5 partial-index migration is added.
- Built-client Browser observation is still required. The local loopback fixture was unreachable from both available browser surfaces, so no visual/four-width claim is made.

## S6.1 Telegram Mini App Identity and Deep-Link Resolution

### Approved Technical Boundary

- Official Telegram raw `initData` HMAC and freshness validation only; never `initDataUnsafe` or a query-string user/role claim.
- Existing active `Stage06TelegramBinding` and `WorkspaceMember` resolve exactly one current internal `user_id`; normal Stage06 authorization remains authoritative.
- One opaque, 10-minute, subject-bound server pointer may resolve only `base`, `view`, `record` or `record_change_draft`, then existing safe target reads run again.
- Resolver returns either a closed destination pointer or indistinguishable safe recovery. It never returns token details, target labels/values before authorization, raw Telegram data or an error taxonomy.
- S6.1 has no public mint endpoint or send/delivery flow. S6.2 remains a separately user-authorized non-production Bot/test-chat operation.

### Required Documents Before Code

| Artifact | Location |
| --- | --- |
| decision | STAGE_07_TECHNICAL_DECISION_007_TELEGRAM_MINI_APP_IDENTITY_AND_DEEP_LINK.md |
| design | docs/superpowers/specs/2026-07-12-stage07-s6-telegram-identity-deep-link-design.md |
| BDD / SDD | STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_BDD_AND_ACCEPTANCE.md / STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_SDD.md |
| work surface / complex index | modules/STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_WORK_SURFACE.md / STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_COMPLEX_FEATURE_INDEX.md |
| implementation plan | created only after this package is reviewed |
| final evidence | created only after implementation; real smoke requires user authority |

### S6.1 Implementation Exit Criteria

- S6-A01 through S6-A09 have fresh local code, negative security and disposable PostgreSQL/client evidence.
- The validator, binding resolver and opaque pointer each retain no raw launch data/token/message in DTO, error, audit, cache or DOM.
- Resolver's unique token lookup, expiry/revocation and current authorization are proven against real local PostgreSQL; no unmeasured extra index is created.
- Desktop/local fallback remains functional and a 1440/1280/430/390 built UI recovery matrix is observed using synthetic fixtures.
- No send/API delivery, BotFather change, webhook registration, external provider action, memory or lifecycle feature is added.

### S6.2 External Evidence Gate

- A human with appropriate authority configures a non-production Bot, Mini App URL, webhook secret and allowlisted test chat/user.
- A separately approved controlled delivery workflow uses existing `restricted_test` policy; it cannot broaden to group/broadcast send.
- Real Telegram proof and deep-link smoke are recorded with sanitized evidence only. Failure to obtain that authority leaves S6.2 and final Stage07 acceptance unproven; it does not block S6.1 local implementation.

## Sequencing Guard

S4 is implemented only within TD004 and remains partially accepted until its documented negative lifecycle matrix is complete. S5 cannot consume generic runtime payloads; TD005 and TD006 are approved, and the current-Canvas bridge is limited to their opaque transient context. S6 cannot treat local header identity or disposable PostgreSQL as Telegram proof.

## Checkpoint Report

Each substage report must contain:

- Functionality implemented.
- Changed code/contract/document scope.
- Explicit non-goals.
- Exact acceptance commands and UI observation.
- Remaining risk and external evidence gap.
