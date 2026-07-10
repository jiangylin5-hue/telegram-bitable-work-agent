# Stage 07 Implementation Plan

## Status

- Document status: detailed plan draft awaiting document-package review
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

### Deliverables

- queue-first Workspace Home, recent Base rail and durable deep links;
- Base/table/view canvas, Grid/Kanban/Calendar/Form renderers and record detail;
- desktop schema/view builder and import/template entry paths;
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
