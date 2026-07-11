# Stage 07 BDD And Acceptance

## Status

- Document status: active acceptance design
- Scope: user-visible UI behavior, safety and responsive acceptance
- Current Progress: Scenarios 1, 3, 4 and 5 have bounded local evidence for implemented slices; no scenario is accepted end-to-end. Scenarios 6-12 remain incomplete or contract-gated as recorded in the requirement traceability audit.

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

### Scenario F1-1: Builder Creates an Immediately Usable First Field

Given an authorised builder opens a fieldless Grid, when they create a required `status` field with valid choices, then exactly one server-owned field persists, the reread default Grid renders that column and the reread create form offers only those choices.

### Scenario F1-2: Unauthorised Member Cannot Mutate a Field

Given a member lacks `field.manage`, when they open the same table or submit a field-initialization request, then the entry is absent, the server returns generic denial before any durable write and no field name/key/policy is retained by an error or protected cache.

### Scenario F1-3: Field Builder Does Not Expose Schema Policy

Given a builder or reader loads a Canvas schema or F1 receipt, when the response arrives, then it contains no `permission_policy`, raw non-choice option, default value, technical field status or role claim; fields without read permission remain absent.

### Scenario F1-4: Choice Values Follow the Persisted Field Schema

Given a builder creates a `multi_select` field with three choices, when an authorised member creates or directly edits a record, then only a distinct subset of the returned choices is submitted and an unknown value is rejected without changing the record.

### Scenario F1-5: Field Initialization Is Atomic and Idempotent

Given a field initialization is retried with the same key and normalized payload, when the original request has completed, then the backend returns the original receipt and only one field/audit event exists; when view visibility update fails, no field, view change, completed idempotency record or F1 audit survives.

### Scenario F1-6: Concurrent Builders Preserve Field Order

Given two authorised builders add different fields to the same table concurrently, when both operations complete, then both fields exist once in consecutive server-owned order and eligible saved views display each key once.

### Scenario F1-7: F1 Mobile Builder Retains the Same Authority

Given a builder opens the Mini App at `390px` or `430px`, when they add a field, then the labelled full-screen sheet exposes relevant inputs/retry/close controls and success returns to the same authorised Grid without a desktop-only route.

### Scenario F1-8: Duplicate Feedback and Pending Dialog Stay Safe

Given the server rejects a normalized duplicate field name with `422.detail.code = duplicate_field_name`, when the builder submits it, then the Field Builder keeps the entered values and shows the fixed local message `字段名称已存在，请使用其他名称。`; it ignores `detail.message` and every unrecognised error code. Given a field request is pending, when the dialog is visible, then its close/cancel controls are disabled and it cannot expose a background workspace/view switch; the application scope-switch test proves a delayed receipt cannot restore an old workspace.

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
- [ ] F1 remains limited to approved independent field types, generated keys and safe choice metadata; F2 has its separately approved bounded contract and detailed companion BDD/SDD/module/index. V1 Saved View Builder has approved implementation in progress: V1-1/2 durability and strict schemas are local-only, while no end-to-end V1 runtime behavior is accepted.
- [ ] F1 schema/receipt/form responses exclude field policy and raw non-choice options; hidden fields remain absent.
- [ ] F1 has automated replay, rollback, concurrent-order and cross-workspace-denial evidence plus four-width visual comparison.
