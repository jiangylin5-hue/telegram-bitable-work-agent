# Stage07 R0 Product Alignment and Closure Design

## Status

- Status: `completed`; the user selected and approved the Stage07-first R0-R3 closure approach on 2026-07-15, and R0's required original-contract inventory is complete. R1 implementation/evidence is active.
- Scope: reset the Stage07 delivery order around the confirmed Telegram customer-project operating scenario, reconcile every approved Stage07 acceptance row, and prepare coherent implementation substages.
- Authorization: documentation and evidence reconciliation only. This document does **not** authorize a schema migration, API route, permission change, Telegram group write, Bot send, external deployment, or product-code change.
- Exit condition: passed. The original-contract inventory confirms that no compatible approved function has been silently deferred; R1 code/evidence is no longer blocked by R0.

## 1. Why R0 Exists

Stage07 has accumulated valid local capabilities, but they were delivered as separate Builder, View, Governance, Draft, Employee, Team Bot and Telegram decisions. A local test passing for one capability is not yet proof that a real Telegram-first delivery team can use a coherent customer-project workflow.

R0 corrects the delivery order without discarding approved work:

```text
existing local capabilities and evidence
    -> one authoritative Stage07 backlog classification
    -> customer / project / task business journey
    -> coherent R1, R2 and R3 implementation-and-acceptance substages
    -> only after Stage07 closure: a separately approved Telegram project-group expansion
```

R0 must not convert an old `partial-local` row into `complete` merely because a related feature exists. Conversely, a real external result already observed must not remain falsely recorded as blocked. Nor may R0 demote an originally approved but unfinished Stage07 feature to a later candidate merely because it is not the first customer-project screen: if it does not conflict with the confirmed business truth, it remains mandatory R1/R2/R3 implementation work.

## 2. Confirmed Product Truth

### 2.1 Target team and operating environment

The initial customer is a sales, customer-operations and delivery team that already communicates with customers and coordinates internally through Telegram. Typical examples include marketing, consulting, design, operations outsourcing and software delivery teams. They need one reliable source of truth behind Telegram conversations, rather than another detached chat assistant.

### 2.2 Primary durable objects

The product's first operating model is relational, not a single all-purpose spreadsheet:

```text
Customer / Opportunity
    -> Project
        -> Task
```

- `Customer / Opportunity` retains commercial relationship and follow-up context.
- `Project` is the operational center: customer commitment, owners, milestones, risk and delivery status.
- `Task` is the accountable work unit. It must contain Project, title, owner, due date and status.
- Existing relations, lookup and aggregation capabilities are reused rather than replaced by a new data model.

### 2.3 Task and health semantics

The confirmed initial task states are fixed: `not_started`, `in_progress`, `blocked`, `waiting_customer`, and `done` (localized labels may be shown in Chinese). A project-health view must make overdue work, near-term milestones, unassigned work, stale work, `blocked` work and `waiting_customer` work visible.

Management's initial home outcome is project health, not a generic dashboard: progress, milestones, blockers, customer confirmations and risk must be readable without opening every task.

### 2.4 Telegram boundary

One customer project Telegram group maps to one Project. Telegram is the daily notification and lightweight-action surface; the Mini App is the internal detail, table and controlled-operation surface.

The initial communication rules are:

1. Bot messages to a customer group are key-event only, never noisy synchronization of every row change.
2. Internal project groups or accountable internal members receive risk reminders first.
3. A customer-facing risk/update message requires responsible-person confirmation before send.
4. Internal members may use a structured Bot conversation to create a task only after required fields are collected and normal backend permission checks pass.
5. Customer messages may be collected, surfaced or turned into a proposed internal item, but they must not directly create an internal task.

Items 4 and 5 introduce a future direct-create/group-context contract. They are deliberately **not** R0/R1 code scope and require a future technical decision covering identity, group binding, action permission, default state, audit and abuse controls.

### 2.5 Digital employee role

The first useful employees are a Project Progress Assistant and a Sales Operations Assistant. Their safe initial behavior is to scan permitted data for explicit risk conditions and produce internal reminders, summaries or confirmation-controlled drafts. They do not receive unrestricted Telegram-send authority, raw database access, arbitrary customer-group write access or self-confirmation authority.

## 3. Stage07 Scope Classification

Every existing Stage07 item must be assigned exactly one primary class during R0. A row may reference a dependency in another class, but it may not hide behind an ambiguous `partial` label.

| Class | Meaning | R0 handling |
| --- | --- | --- |
| `already-closed` | Direct current evidence satisfies the approved bounded row. | Retain the evidence and do not reopen it unless a regression or changed contract requires it. |
| `requires-implementation` | An approved contract lacks a required behavior or defect repair. | Place it in a coherent R1/R2/R3 implementation package with BDD and a test-first plan. |
| `requires-evidence` | Approved behavior exists but its required PostgreSQL, UI, permission or external observation is absent. | Add proportional acceptance work; do not redesign the capability. |
| `requires-document-correction` | Fresh evidence exists but a checklist/source document still says pending. | Reconcile the truthful primary status and link sanitized evidence. |
| `contract-gated` | It needs a new schema, API, action, permission model, external authority or explicit scope decision. | Preserve as later candidate; do not describe it as an unfinished Stage07 defect. |
| `explicitly-deferred` | It is valuable but not necessary to close the confirmed Stage07 baseline. | Record why it is deferred and its re-entry condition; never silently delete it. |

## 4. Coherent Stage07 Closure Sequence

### R0 — Truth, business alignment and acceptance reset

R0 produces a single authoritative backlog matrix and updates only top-level progress/traceability documents that are stale. It identifies duplicate or superseded external statements, including the already completed S6.3 cleanup. It does not alter product code.

### R1 — Customer-project core with existing contracts

R1 proves the already-approved platform can support the basic internal operating model using synthetic customer, project and task fixtures: relational data, safe fields, views, imports/templates, authorized navigation and a project-health presentation. It completes every compatible originally approved R1-scope behavior that is missing or half-delivered, then closes its defects and evidence gaps. It does not bind a Telegram group to a Project or introduce a direct Bot write.

### R2 — Controlled internal collaboration and management

R2 completes and closes compatible approved governance, draft, employee-management and Team Bot work that is necessary for internal teams to act safely: role/field behavior, draft terminal states, lifecycle/revocation behavior, selected-view summary safety, management UI and authoritative error recovery. It must distinguish useful Project/Sales assistant behavior from deferred generic knowledge, memory, RAG and file capabilities.

### R3 — Existing Telegram and final Stage07 evidence

R3 completes compatible unfinished original Telegram identity/deep-link/delivery and final-acceptance work, reconciles the already observed bounded result, verifies remaining safe UI/permission evidence, removes temporary artifacts and performs the final Stage07 traceability audit. It does not create new group messaging, customer task creation or external action behavior.

### Later candidate — Telegram customer-project group operations

Only after the Stage07 closure decision may a new technical-decision package propose Project-to-group binding, internal structured task creation, customer-message intake, risk scanning and confirmation-controlled customer-group sends. It is a new coherent product vertical, not a shortcut for closing old rows.

## 5. Existing Capability Reuse Map

| Confirmed need | Existing Stage07 foundation to reuse | R0 decision |
| --- | --- | --- |
| Customer/Project/Task relations | Base/Table, F2 relation/lookup, Record Detail | Verify scenario fit in R1; do not reimplement relations. |
| Project health | V1 saved views, presentation DTOs, filtered/sorted/grouped views | Close relevant V1 acceptance gaps before proposing a separate dashboard engine. |
| Fast onboarding | template/install/save and CSV/XLSX preview/mapping/commit | Close only approved import evidence; no connector platform. |
| Internal responsibility and safe changes | governance, field policies, versioned PATCH, drafts/audit | Reuse existing server authority; no client-side permission model. |
| Risk summary and follow-up | TD005/TD006/TD009/TD011 bounded employee seams | Keep summary/draft controls; do not introduce memory/RAG/direct write in Stage07. |
| Telegram entry | TD007/TD008 verified launch, opaque pointer and restricted delivery path | Treat observed S6.3 evidence as complete and cleanup as complete; no general group-send expansion. |

## 6. Explicit Non-Goals for R0 and Stage07 Closure

- Rebuilding the table platform or replacing FastAPI, SQLAlchemy, PostgreSQL, React/Vite, LangGraph, OpenRouter or Telegram Bot API integrations.
- A customer account system, customer Mini App authorization model, public links, group broadcasting or arbitrary Bot group writes.
- Memory, RAG, document/file knowledge, generic chat history, agent tool selection, raw SQL or direct database access.
- Production rollout or treating an isolated non-production Telegram result as production readiness.
- Declaring Stage07 complete before every in-scope approved row is either directly evidenced or explicitly re-scoped with user approval.

## 7. R0 Acceptance Criteria

R0 is accepted only when:

1. all existing Stage07 work packages are classified in the linked [R0 Closure Matrix](STAGE_07_R0_CLOSURE_MATRIX.md) with one primary class and an owning substage;
2. actual S6.3 evidence and cleanup are corrected in every top-level truth/checklist/traceability document that still contradicts them;
3. R1, R2 and R3 each have a bounded business purpose, exclusions, prerequisites and acceptance evidence type;
4. the future Telegram project-group vertical is explicitly marked `contract-gated`, with no code authorization implied;
5. no secret, raw Telegram identifier, raw `initData`, private URL or business record value enters any document; and
6. the user reviews this package before any R1 implementation plan or code work begins.

## 8. Original-Scope Completion Rule

The original Stage07 technical decisions, BDD, SDD, work-surface, complex-index and implementation-plan documents are still binding for compatible work. R0/R1/R2/R3 must therefore:

1. inventory every approved function that is `not-started`, `partial-local`, missing an approved state transition, or missing an approved integration path;
2. complete it in the owning R1/R2/R3 substage when its schema/API/permission boundary was already approved;
3. test and reconcile it against its original BDD, not merely against a new scenario fixture; and
4. classify it as `contract-gated` only when the requested behavior is absent from approved Stage07 documents or would materially change their approved schema/API/permission/external-action boundary.

This rule prevents the customer-project alignment from becoming an excuse to abandon unfinished Stage07 work.
