# Stage07 R0 Original Contract Inventory

## Status

- Status: `completed` original-document inventory for the approved R0-R3 closure pass; R1 is now executing against this inventory.
- Scope: every original Stage07 feature family with an approved decision, BDD/SDD, work-surface or implementation plan.
- Rule: `partial-local` is not a disposition. Each row identifies whether work is missing code, missing evidence, stale documentation, or a genuine later contract gate.

## Inventory

| ID | Original contract family | Compatible with confirmed business scenario | Observed state | Mandatory R0-R3 disposition |
| --- | --- | --- | --- | --- |
| OI-01 | Stage07 Mini App UI, App Shell, Foundation and TD001 protected query state | Yes; internal Telegram-first customer/project workspace depends on it. | Core shell, scoped state, Home and Base navigation have local implementation/evidence; identity/switch/revocation and full selected-design observation remain incomplete. | R1: complete any missing existing behavior and evidence. |
| OI-02 | TD002 writable record create/form | Yes; Project/Task creation requires safe server-writable fields. | Existing safe create-form and record-create implementation/tests exist. | R1: include in Customer/Project/Task path; repair only test-proven gap. |
| OI-03 | P2 table switch and P3 Base/Table Builder | Yes; templates and customer-project Bases require safe initialization/table selection. | P3 local implementation/evidence is bounded; P2 table switch tests exist. | R1: retain/reuse; only regression or scenario gap requires code. |
| OI-04 | F1 independent Field Builder | Yes; approved fields support Customer/Project/Task templates. | Bounded implementation and local/PostgreSQL/four-width evidence exist. | Already closed unless R1 regression reveals an approved defect. |
| OI-05 | F2 relation/lookup Builder | Yes; this is the approved relational foundation for Customer/Project/Task. | Bounded implementation and local/PostgreSQL/four-width evidence exist. | Already closed unless R1 regression reveals an approved defect. |
| OI-06 | Existing-contract Home/Bases Navigation | Yes; this is the internal operational entry. | Implemented-local with focused client/build evidence; selected full visual review remains absent. | R1 evidence completion. |
| OI-07 | V1 Saved View Builder | Yes; project health should first reuse approved views, not invent a dashboard engine. | V1-1 through V1-15 implementation/local database and partial real-backend Browser evidence exist; stale/type-invalid/full all-width role matrix remains incomplete. | R1: finish compatible V1 behavior/evidence; do not introduce public sharing/dashboard redesign. |
| OI-08 | Template/Install/Save and CSV/XLSX Import | Yes; first customers need spreadsheet migration and templates. | Code/tests/local evidence exist, but the originating BDD still says design-only; browser file-selection observation is absent. | R1: correct source document; complete compatible import/commit evidence or record exact browser limitation. |
| OI-09 | TD003 Governance Readback | Yes; managers need safe member/audit visibility. | Implemented-local; external/full visual evidence remains partial. | R2 evidence completion. |
| OI-10 | TD004 Governance Write | Yes; internal ownership and field access must remain controlled. | Local command/lifecycle matrix is implemented; terminal UI permutations remain incomplete. | R2 evidence completion; no new role model. |
| OI-11 | TD005 Draft Employee Hub | Yes; safe Project/Task summaries and change drafts are relevant. | Bounded safe contacts, context, terminal draft mechanics and local evidence exist; Browser/provider lifecycle rows remain partial. | R2: complete every approved compatible state and evidence; no generic runtime/agent expansion. |
| OI-12 | TD006 current-Canvas context binding | Yes; allows selected Project/Task context to reach fixed S5 intents. | Original BDD says in progress while later source/evidence reports the bounded bridge implemented. | R2 document correction plus regression verification. |
| OI-13 | TD009 Personal Assistant context discovery | Supporting; may assist internal project work without becoming the core loop. | Partial-local; PostgreSQL intersection/revocation, delayed replacement and visual evidence remain incomplete. | R2 completion. |
| OI-14 | TD010 Digital Employee Management | Supporting; project/sales assistant configuration is relevant. | Implemented-local; management workbench visual/real-environment claims are incomplete. | R2 completion of approved compatible UI/safety evidence. |
| OI-15 | TD011 Team Bot selected-view knowledge | Yes; one-shot project-health/sales summary is relevant. | Partial-local; exact non-empty Mini App -> provider path and final UI evidence remain incomplete. | R2 completion; no memory/RAG/files/direct write. |
| OI-16 | TD007 Telegram Mini App identity/deep link | Yes; Telegram is the daily entry channel. | Local code/evidence plus bounded isolated real signed-launch resolver/Base evidence exist; original BDD/checklist retains stale pending statements. | R3 document correction and regression verification; no new group identity. |
| OI-17 | TD008 controlled delivery/manual smoke | Yes; bounded private delivery validates existing entry only. | Local state machine plus two separately approved real sends/resolver evidence and cleanup exist; original BDD/checklist retains stale external-authority state. | R3 document correction and no-new-send verification. |
| OI-18 | S6.3 isolated acceptance deployment | Yes, as a completed non-production acceptance operation. | Isolated runtime, HTTPS, real launch evidence and cleanup are complete; Stage03 health preserved. | Already closed; retain evidence only. |
| OI-19 | Memory, RAG, files, generic direct Bot writes, group/broadcast send, public/customer Mini App, multi-Base employee scope | No current approved contract; some are valuable later but alter schema/API/permissions/external side effects. | Deliberately excluded by multiple original decisions. | `contract-gated`; do not build in R0-R3. |

## Inventory Findings

1. No compatible originally approved feature family may be removed from R1/R2/R3 merely because the business priority is now Customer/Project/Task.
2. P3, F1, F2 and S6.3 have bounded direct evidence and are not reopened as new development unless a focused regression proves a defect.
3. V1, template/import, governance, Draft Hub, TD009, TD010 and TD011 retain compatible unfinished implementation/evidence obligations and are mandatory R1/R2 work.
4. TD006, TD007, TD008 and Template/Import contain stale progress statements that require R2/R3 documentation correction, not duplicate product reimplementation.
5. New customer-group behavior remains a future decision because no original Stage07 document approves its persistence, API, permission or external-send contract.

## Original-document Reconciliation Record

This is the R0 document-by-document reading record. It separates an original document's stale wording from the actual closure action; it does not upgrade any acceptance evidence.

| Original source group | R0 reading result | R1-R3 action |
| --- | --- | --- |
| TD001 protected query state; TD002 writable create | Existing approved read/edit/create code is present; identity/switch/revocation and final responsive observations are still evidence gaps. | R1 verifies the Customer/Project/Task path with current scoped query behavior. |
| Navigation closure BDD/SDD/index | `implemented-local`, with safe Base-directory tests/build but no complete selected-design review. | R1 extends only scenario regression and visual observation. |
| P3, F1 and F2 BDD/SDD/work surfaces | Bounded implementation and local/PostgreSQL evidence exist. F2 already provides same-Base relation/lookup, safe labels and direct editing. | Reuse in fixtures; reopen only for a red regression. |
| V1 BDD/SDD/work surface | BDD records V1-1 through V1-15 partial-local; its SDD still says V1-1 through V1-13 and is therefore stale. Type-invalid/stale-version/full role-width evidence remains open. | R1 completes only the approved V1 evidence/repair rows. |
| Template/import BDD/SDD/work surface | UI/code and local evidence exist, but the BDD still says “design only; no Mini App code”. | R1 verifies the authorized preview/commit path; R3 corrects stale status language. |
| TD003/S3 governance readback | The decision/SDD still says proposed, while the BDD records `implemented-local`. | R2 reconciles decision/SDD and performs safe readback rendering/cache evidence. |
| TD004/S4 governance write | Approved code is present; terminal lifecycle and visual error coverage remain partial. | R2 completes approved negative/lifecycle evidence without changing roles/actions. |
| TD005/TD006 draft hub/context binding | TD006 SDD says locally implemented while its BDD says “in progress”; TD005 has real local behavior with provider/Browser gaps. | R2 corrects the TD006 contradiction and completes only approved safe draft/context states. |
| TD009 personal assistant | The decision and BDD correctly say `partial-local`; revocation, delayed replacement, PostgreSQL and visual states remain open. | R2 completion work; no memory or new picker. |
| TD010 employee management | Implementation is local and bounded; visual review/environment claims remain open. | R2 lifecycle/grant/workbench evidence only. |
| TD011 Team Bot | Existing selected-view one-shot code is partial-local; exact non-empty Mini App-to-provider path and final UI states remain open. | R2; no RAG, memory, files or direct write. |
| TD007/S6.1 identity/deep link | Local implementation is valid and the later bounded isolated signed-launch/Base result is real, but old BDD/SDD statements still say no real Telegram smoke. | R3 corrects truthful bounded evidence and retains non-production limit. |
| TD008/S6.2 controlled delivery | Original TD/BDD/SDD still label external send as future-required, although two separately authorized one-attempt sends and resolver evidence occurred. | R3 documentation correction only; no further send/retry. |
| S6.3 isolated acceptance deployment | Its BDD/SDD correctly records accepted-bounded evidence and cleanup; Stage03 preservation is documented. | Retain evidence; do not recreate the environment. |
| Group binding, structured Bot create, customer-message intake, risk send, customer Mini App | None has an approved original schema/API/permission/external-action contract. | Remain `contract-gated` for the next stage. |

## R0 Exit Evidence

R0 is complete: this inventory, the R0 Closure Matrix and the active top-level status documents now agree that compatible original work stays owned by R1/R2/R3. Each remaining code repair is still subject to the original contract and test-first rule.
