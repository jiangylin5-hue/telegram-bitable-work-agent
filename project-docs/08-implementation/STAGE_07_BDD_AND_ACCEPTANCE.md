# Stage 07 BDD And Acceptance

## Status

- Document status: active acceptance design
- Scope: user-visible UI behavior, safety and responsive acceptance
- Current Progress: scenarios are specified; execution awaits implementation

## 1. BDD Scenarios

### Scenario 1: Permission-Aware Workspace Home

Given an active workspace member opens the Mini App, when bootstrap succeeds, then Home shows only server-authorized queues, Bases, Bot contacts and management navigation.

### Scenario 2: Mobile Work Queue

Given an operator uses a narrow Telegram Mini App viewport, when Home loads, then Today, draft and mention rows remain one-tap actionable without desktop sidebars or hover-only controls.

### Scenario 3: Desktop Builder Entry

Given a builder opens a Base on desktop, when the Grid view is selected, then schema, view, filter, grouping and record tools are available only to the degree the returned permissions allow.

### Scenario 4: Saved View Semantics Survive Responsive Layout

Given a saved Grid, Kanban, Calendar or Form view, when it is opened on desktop and mobile, then its underlying filter, sort, grouping and field semantics remain the same even when the mobile presentation changes.

### Scenario 5: Hidden Field Is Not Leaked

Given a member lacks a field read permission, when the member opens Home, a Base, record detail, Bot response or error state, then the hidden field's key and value are not rendered or retained in client state.

### Scenario 6: Team Bot Uses Authorized Context

Given a member opens a published team Bot from a contact or Telegram `@` handoff, when the Bot receives context, then the effective authority is the intersection of Bot configuration, caller scope and chat scope.

### Scenario 7: Personal Assistant Context Is Opt-In

Given a user opens the personal assistant, when no Base/view/record is explicitly selected, then the UI states that no workspace data is in context and does not imply a workspace search.

### Scenario 8: Bot Change Is A Field-Level Draft

Given a Bot proposes a record update, when the user opens the proposal, then affected Base/table/record, before values, proposed values, action availability and confirmation state are all visible before execution.

### Scenario 9: Draft Confirmation Is Controlled

Given a user confirms a permitted draft, when the backend accepts the request, then the UI shows the backend terminal status and audit link; when it rejects, conflicts or expires, then no success state is displayed.

### Scenario 10: Telegram Deep Link Is Safe

Given a group `@` mention provides a deep-link target, when the Mini App opens it, then identity and resource authorization are resolved before the target content is rendered; an invalid/unauthorized target shows a safe recovery route.

### Scenario 11: Governance Is Not Role-Spoofable

Given a browser changes local route or role-like state, when it tries to open governance, then the backend denial prevents member/permission/audit data from being displayed.

### Scenario 12: Session And Network Failure Do Not Leak Or Mislead

Given an expired Mini App identity, revoked membership or failed request, when the affected UI is visible, then protected cache is cleared or withheld, retry is explicit and no write is represented as complete.

## 2. Required Evidence

- desktop and mobile screenshots for each primary flow;
- automated component/integration tests for BDD scenarios;
- API-level authorization-denial tests; no UI-only permission proof;
- a real Telegram deep-link/manual smoke only in an approved test environment;
- sanitized audit and draft artifacts with no raw hidden values, prompts or Telegram message bodies.

## 3. Acceptance Checklist

- [ ] Workspace Home is queue-first and all rows land on durable authorized resources.
- [ ] Desktop builder and mobile operator pathways both work at target viewports.
- [ ] Grid/Kanban/Calendar/Form semantics match their saved server models.
- [ ] Denied, empty, loading, conflict and expiration states are intentionally designed and tested.
- [ ] Bot scopes, private assistant context and per-user memory boundaries are visible and enforced.
- [ ] Every Bot write is confirmed through `record_change_draft` with an audit outcome.
- [ ] No unapproved Stage07 contract extension is silently implemented.
