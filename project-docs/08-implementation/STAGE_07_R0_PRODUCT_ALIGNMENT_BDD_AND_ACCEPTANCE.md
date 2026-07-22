# Stage07 R0 Product Alignment BDD and Acceptance

## Status

- Status: `completed`; original-contract inventory and matrix reconciliation passed under the approved R0-R3 closure pass. R1 is active.
- Scope: Stage07 backlog truthfulness, business-scenario alignment and substage ownership.
- Non-goal: this BDD does not authorize a product feature, data mutation, remote action or external message.

## BDD Scenarios

### R0-A01 — Every approved row has one explicit closure path

Given Stage07 contains Builder, View, Governance, Draft, Employee, Team Bot and Telegram acceptance rows
When the R0 matrix is produced
Then each row is classified as `already-closed`, `requires-implementation`, `requires-evidence`, `requires-document-correction`, `contract-gated` or `explicitly-deferred`
And each row names exactly one owning R1/R2/R3 substage or a later decision gate
And no row is left as an unexplained `partial-local` statement.

### R0-A02 — Existing evidence is not lost

Given direct evidence already exists for a focused test, local PostgreSQL case, built UI observation, real provider smoke or bounded Telegram smoke
When top-level documentation is reconciled
Then it retains the evidence type and its limitation
And it never upgrades a local or isolated non-production result into staging, production or whole-stage acceptance.

### R0-A03 — Stale external state is corrected

Given S6.3's real Telegram identity/deep-link evidence and isolated-resource cleanup have been observed
When the checklist, source of truth, roadmap and traceability are reconciled
Then old statements that say those exact operations are still pending are superseded
And documents continue to state that Stage07 overall is not accepted.

### R0-A04 — The business scenario controls prioritization

Given the target team operates customer projects through Telegram
When R1/R2/R3 are sequenced
Then Customer/Opportunity, Project and Task data, project health, internal responsibility and controlled Telegram entry take precedence
And unrelated generic agent expansion does not displace those outcomes.

### R0-A05 — New group-operation behavior stays behind a decision gate

Given a future customer project group may map to one Project
When a proposal includes structured internal task creation, customer-message intake, risk alerts or a customer-facing send
Then it is labelled `contract-gated`
And implementation waits for a dedicated technical decision covering schema, API contract, identity, action permissions, confirmation policy, audit and abuse handling.

### R0-A06 — No scope is silently deleted

Given a legacy item is not needed for the customer-project closure path
When it is deprioritized
Then the matrix records it as `explicitly-deferred` with its re-entry condition
And it is not represented as completed, removed or rejected without user approval.

### R0-A07 — R1 is an existing-contract substage

Given R1 proves customer/project/task operations using existing Stage07 capabilities
When its plan is prepared
Then it reuses existing Base, relation/lookup, view, import, authorization and safe DTO services
And it introduces no Telegram group binding, Bot direct write, public-client account or new permission action.

### R0-A08 — Review is a mandatory gate

Given the R0 documents have been written and checked for conflicts
When implementation is requested
Then the user first approves the R0 document package
And only then is a detailed R1 implementation plan written.

### R0-A09 — Compatible original work cannot be silently demoted

Given an original Stage07 decision, BDD, SDD or implementation plan already approves a function, state or integration path
When R0 assigns delivery ownership
Then a `not-started` or `partial-local` compatible item is placed in R1, R2 or R3 for implementation and acceptance
And it is not relabelled as later scope merely because it is not the first Customer/Project/Task screen
And only a genuine unapproved schema, API, permission or external-action change is `contract-gated`.

## Acceptance Matrix

| ID | Required direct evidence | Completion condition |
| --- | --- | --- |
| R0-A01 | one full row matrix with owner/class/re-entry evidence | no unclassified approved row remains |
| R0-A02 | links to existing sanitized test/evidence records | evidence level and non-claim agree |
| R0-A03 | source/checklist/traceability comparison | S6.3 cleanup/external statements do not conflict |
| R0-A04 | product-truth section and R1/R2/R3 ordering | customer-project operating sequence is explicit |
| R0-A05 | future-contract entry | no product code or external write is implied |
| R0-A06 | deferred register | each deferral has rationale and re-entry gate |
| R0-A07 | R1 boundary | existing-contract reuse is explicit |
| R0-A08 | user review response | R1 plan is blocked until review approval |
| R0-A09 | original-document inventory and R1/R2/R3 ownership | no compatible approved unfinished work is silently deferred |

## Completion Evidence

- `STAGE_07_R0_ORIGINAL_CONTRACT_INVENTORY.md` records each approved family and its exact R1/R2/R3 owner or genuine future contract gate.
- `STAGE_07_R0_CLOSURE_MATRIX.md` maps all original work and distinguishes implementation/evidence/document-correction work from new-scope work.
- The first R1 synthetic Customer/Project/Task backend and Mini App regressions both pass; they prove only current-contract safe relationships, authorization and navigation, not whole-R1 acceptance.
