# Stage 07 Implementation Plan

## Status

- Document status: active implementation plan; package completion remains subject to the linked requirement traceability audit
- Scope: sequence, dependencies and verification for the approved Stage07 UI
- Hard gate: no package may begin until this document package is user-reviewed; proposed schema/API/permission work needs separate explicit approval

## Goal

Deliver one responsive React/Vite Mini App and desktop browser surface that exposes the Stage06 platform safely. UI work must preserve the platform order: workspace -> Base -> table -> field/view -> record -> permission -> Bot capability -> draft -> audit.

## Package 1: UI Foundation And Session Boundary

### Deliverables

- application shell, tokenized white/cool-gray/azure design system, desktop sidebar and mobile bottom navigation;
- verified identity bootstrap adapter, workspace picker and permission-aware navigation model;
- query/cache boundary keyed by workspace and resource identity;
- shared loading, empty, denied, expired and network-error components.

### Interaction Sequence

1. Verify identity through backend adapter.
2. Resolve active workspace membership.
3. Fetch server navigation/capability model.
4. Render authorized Home route or safe failure state.
5. Clear protected cache before reauthentication or workspace switch.

### Verification

- component tests for navigation and route guard states;
- integration tests for workspace switch, 401/403 and cache clear;
- desktop/mobile visual checks with no dark/glow/card-wall drift.

## Package 2: Workspace Home And Bitable Work Surface

### Active approved-scope substage

`STAGE_07_SUBSTAGE_P2_TABLE_SWITCH_PLAN.md` defines the current existing-contract implementation: selection among already-authorized tables inside an open Base. It introduces no new contract and must complete its own test/browser/documentation gate before any builder/import/governance work begins.

### Implemented bounded P3: Base/Table Atomic Builder

`STAGE_07_SUBSTAGE_P3_BASE_TABLE_BUILDER_DESIGN.md` and `STAGE_07_SUBSTAGE_P3_BASE_TABLE_BUILDER_PLAN.md` define the separately approved P3 creation path. It is implemented with two atomic, idempotent endpoints: authorized Workspace Home creation of `Base + initial table + default Grid`, and authorized in-Base creation of `table + default Grid`. The Mini App submits only names, refetches authorized lists before receipt-driven navigation, shows an honest zero-field Grid and exposes entry points only from server capabilities.

This is deliberately narrower than the Package 2 deliverables: field creation/editing, extra view creation/editing, import/template UX, general schema administration and Package 3 governance are not completed or implied. Local full-suite/browser evidence is recorded in the P3 plan and progress log; the real-PostgreSQL P3 rollback/concurrency/index command passed on the authorised disposable local database on 2026-07-11. That evidence does not accept the wider Package 2 or Stage07 scope.

### Approved F1: Independent Field Builder

`docs/superpowers/specs/2026-07-10-stage07-f1-field-builder-design.md` and `STAGE_07_SUBSTAGE_F1_FIELD_BUILDER_PLAN.md` define the next bounded Package 2 substage. It creates only the approved independent field types through a safe atomic endpoint: the browser supplies display data and validated choices only; the server owns generated keys, default policy, durable order, saved-view visibility updates, audit and idempotent replay. F1 includes safe schema projection and choice-aware record create/direct edit so newly required choice fields are usable. Relation/lookup (F2), advanced JSON, field editing/reordering/deletion and additional views (V1) remain outside F1.

### Proposed V1: Comprehensive Saved View Builder (Awaiting Design Review)

V1 is not an implementation task yet. Its proposed package is `docs/superpowers/specs/2026-07-11-stage07-v1-saved-view-builder-design.md` plus the linked V1 BDD, SDD, work-surface and complex-feature-index documents. It covers Grid, Kanban, Calendar and Form together; private/restricted owner-editor-viewer ACL; unchanged system default Grid; typed server-only presentation semantics; and required migration/index/PostgreSQL/Browser evidence. It explicitly rejects Mini App use of the existing raw view config/policy route. User review is required before a V1 TDD implementation plan or runtime change.

### Deliverables

- queue-first Workspace Home, recent Base rail and durable deep links;
- Base/table/view canvas, Grid/Kanban/Calendar/Form renderers and record detail;
- the bounded P3 Base/Table initializer above; separately specified field/view builder and import/template entry paths;
- mobile table field priority, horizontal access and full-screen detail/editor.

### Interaction Sequence

1. Home requests server queue groups and recent Bases.
2. Each selected row resolves an authorized Base/view/record/draft destination.
3. Base canvas requests saved-view schema and paginated permitted records.
4. Record detail performs version-aware direct edits or opens an existing draft.
5. Schema/permission changes invalidate view and record caches before rerender.

### Verification

- BDD scenarios 1-5;
- Grid/Kanban/Calendar/Form parity at desktop and mobile target widths;
- cursor, conflict, hidden-field and responsive overflow tests.

## Package 3: Governance And Audit Surface

### Deliverables

- members, roles, workspace/Base/view/field permission interfaces;
- audit readback and safe pagination;
- template/import management and administrative configuration entry points.

### Interaction Sequence

1. AppShell receives management capability from backend.
2. Governance loads server-filtered admin models.
3. Permission editor references the same schema IDs as BaseCanvas.
4. Mutation receives authoritative permission state, then refreshes affected caches/capabilities.
5. Audit displays sanitized metadata only.

### Verification

- management route denial and role-spoof tests;
- hidden field and cross-workspace UI/cache negative tests;
- audit redaction inspection and pagination tests.

## Package 4: Digital Employee And Draft Surface

### Prerequisite Gate

Before implementation, approve a technical decision for workspace-level Bot contacts, employee lifecycle, scopes, knowledge sources, per-user memory partitions and Mini App identity/deep-link contract. The approval must identify schema migration, API changes, authorization rules, retention and audit behavior.

### Deliverables After Gate

- team Bot directory, private-test/published contact states and Telegram group `@` handoff;
- personal assistant with explicit removable Base/view/record context;
- field-level `record_change_draft` diff, idempotent confirm/reject and audit outcome;
- knowledge-source and memory controls consistent with approved backend contract.

### Verification

- BDD scenarios 6-12;
- caller/chat/Bot scope intersections; user-memory isolation; deep-link authorization; draft idempotency, conflict and audit evidence;
- approved test-environment Telegram Mini App smoke.

## Cross-Package Quality Gates

- React/Vite/TypeScript/Tailwind/shadcn/lucide baseline remains intact.
- Feature modules consume typed, permission-filtered view models; no raw service credentials, SQL or raw data context reaches the browser.
- Every feature includes loading, empty, denied, error and recovery design before happy-path signoff.
- Visual QA compares implementation against selected Stage07 concepts at 1440px, 1280px, 430px and 390px.
- No package is accepted solely from mocked frontend data when the corresponding Stage06 contract exists.

## Completion Sequence

1. User reviews and approves the expanded document package.
2. User separately approves the Package 4 contract decision when ready.
3. Implement packages in order with tests and review checkpoints.
4. Produce Stage07 acceptance report with sanitised evidence and remaining production risks.
