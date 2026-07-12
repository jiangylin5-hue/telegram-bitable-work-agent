# Stage07 Substage Delivery Roadmap

## Status

- Document status: active Stage07 delivery roadmap
- Purpose: organize Stage07 as coherent substages rather than individual UI/API fragments
- Current active substage: S4 Governance Write documentation and user-review gate

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
| S4 | Governance Write | bounded member-role, field-policy and existing V1 view-grant operations | proposed, awaiting review | Technical Decision 004 |
| S5 | Draft and Digital Employee Hub | field-filtered draft review, contacts and assistant surface | contract-gated | separate draft/employee/context decision |
| S6 | Telegram and final acceptance | verified identity/deep link, full safety/visual matrix and release evidence | external-evidence-pending | approved test environment and user authority |

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

### Proposed Scope

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
| implementation plan | created only after explicit approval of TD004/specification |
| final evidence | created only after implementation and reconciliation |

### Exit Criteria

- GW-A01 through GW-A08 have evidence; every rejected mutation proves no write.
- Revision migration upgrade/rollback/replay and concurrent mutations pass against disposable local PostgreSQL.
- Field visibility/write behavior remains enforced across schema, presentation, record detail, lookup and record update.
- Existing V1 grant route remains the only view-member mutation path.
- Built UI Browser evidence covers all required widths with synthetic data; cleanup is documented.

## Sequencing Guard

S4 implementation cannot start merely because S3 UI exists; TD004 requires explicit approval before its schema/API/permission changes. S5 cannot consume generic runtime payloads; it needs field-filtered draft and employee/context authority design. S6 cannot treat local header identity or disposable PostgreSQL as Telegram proof.

## Checkpoint Report

Each substage report must contain:

- Functionality implemented.
- Changed code/contract/document scope.
- Explicit non-goals.
- Exact acceptance commands and UI observation.
- Remaining risk and external evidence gap.
