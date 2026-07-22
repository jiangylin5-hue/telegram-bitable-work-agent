# Stage07 R0 Product Alignment SDD

## Status

- Status: `completed`; R1 is now the active implementation/evidence substage.
- Scope: documentation-state architecture for Stage07 closure. No runtime code is designed or authorized here.

## 1. Document State Model

R0 uses a stable projection for every Stage07 row:

```text
Source contract
  -> Current implementation state
  -> Evidence state
  -> Backlog class
  -> Owning substage or later decision gate
  -> Acceptance/re-entry condition
```

`Current implementation state` may be `not-started`, `implemented-local`, `partial-local`, `accepted-bounded` or `not-applicable-after-approved-scope-change`. It is not a replacement for `Backlog class`; for example, an `implemented-local` feature may still be `requires-evidence`, while a bounded locally accepted row is `already-closed`.

## 2. Authoritative Inputs and Conflict Rule

Inputs are read in this order:

1. current user decisions recorded in this R0 package;
2. `AGENTS.md` and `IMPLEMENTATION_SOURCE_OF_TRUTH.md`;
3. `STAGE_07_SOURCE_OF_TRUTH.md`;
4. approved feature BDD/SDD/technical-decision documents;
5. `STAGE_07_ACCEPTANCE_CHECKLIST.md` and `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`;
6. sanitized evidence files, focused tests and verified command results.

When an old progress paragraph conflicts with a newer direct sanitized evidence record, R0 must add a dated correction to the active top-level document. Historical evidence is retained; it is not rewritten to pretend the earlier state never existed.

## 3. R0 Matrix Contract

The R0 matrix is document data, not a database table. Its mandatory columns are:

| Column | Rule |
| --- | --- |
| `Work ID` | Stable source row/substage identifier, such as `V1`, `TD005`, `S6I-A08`. |
| `Business relevance` | `core`, `supporting`, `safety`, or `later`. |
| `Implementation state` | Truthful current technical state; never inferred from a neighboring feature. |
| `Evidence gap` | Exact missing test, UI observation, external authority, document correction or none. |
| `Backlog class` | One R0 class from the Design document. |
| `Owner` | `R1`, `R2`, `R3`, or a named later technical decision. |
| `Acceptance condition` | Concrete command/observation/document comparison required to close it. |
| `Non-claim` | What success cannot prove. |

## 4. Privacy and External-Action Constraints

R0 documentation may name only sanitized receipt states, high-level evidence types and stable contracts. It must not record a token, Bot token, Chat/User identifier, raw Telegram update, `initData`, deep link, provider prompt/response, deployment credential, raw business record or customer content.

R0 performs no external action. In particular it does not send Telegram messages, change BotFather, alter a webhook, deploy an image, write a remote configuration, mutate production data or request a new browser session.

## 5. Boundary Between Stage07 and the Later Group-Operations Proposal

The current Stage07 code may be reused as a foundation, but the following are outside R0/R1/R2/R3 implementation authority:

- persistent Telegram `group_id -> project_id` mapping;
- internal structured Bot task-create command;
- customer message intake state machine;
- scheduled/event-driven risk alert policy;
- confirmation-controlled customer-group send;
- customer-facing Mini App authorization.

These items require a future dedicated decision because they change persistence, API contracts, actor identity, action permissions and external side effects.

## 5.1 Original-Contract Inventory Requirement

Before a row can be deferred, the R1/R2/R3 owner must read the linked original technical decision, BDD, SDD, work-surface and implementation plan. A compatible originally approved missing behavior remains implementation work even when the current closure matrix initially lists it only as an evidence gap. The matrix must be corrected before implementation starts; it must not use `contract-gated` as a shortcut around unfinished approved scope.

## 6. Verification of R0 Itself

R0 verification is documentation integrity rather than software regression:

```powershell
git diff --check
rg -n "T[B]D|TO[D]O|complete Stage07|production ready" project-docs/08-implementation/STAGE_07_R0_PRODUCT_ALIGNMENT_*.md
```

Expected results: no whitespace errors, no placeholders and no unsupported completion/production claim. Product-code tests are not rerun merely because R0 changes documentation.
