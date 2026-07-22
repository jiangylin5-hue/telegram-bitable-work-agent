# Stage07 R0 Closure Matrix

## Status

- Status: `R0 completed; Stage07 acceptance open`; the user approved a continuous R0-R3 pass on 2026-07-15, but [STAGE_07_FINAL_AUDIT_REPORT.md](STAGE_07_FINAL_AUDIT_REPORT.md) found unresolved compatible original requirement-ID evidence. R1/R2 evidence is retained and the next coherent work is acceptance-evidence closure.
- Scope: every current Stage07 work package is mapped to an owner, a closure class and an evidence condition. This matrix changes no product contract by itself.
- Product priority: the internal Telegram-first customer-project operating scenario: `Customer/Opportunity -> Project -> Task`, project health, internal responsibility and controlled collaboration.
- Original-scope rule: a compatible function already approved by original Stage07 documents remains mandatory even if it is currently `not-started` or `partial-local`; only genuinely unapproved contract changes may move to a later decision.
- Original-contract source: [R0 Original Contract Inventory](STAGE_07_R0_ORIGINAL_CONTRACT_INVENTORY.md) records all approved feature families and is read before a row is deferred.

## Classification Key

| Class | Meaning |
| --- | --- |
| `already-closed` | Direct evidence satisfies the approved bounded row; preserve it and avoid duplicate work. |
| `requires-implementation` | An approved behavior is absent or a defect repair is necessary. |
| `requires-evidence` | Behavior exists but required UI, PostgreSQL, permission or safe external observation is absent. |
| `requires-document-correction` | Direct evidence exists but an active document still records obsolete pending state. |
| `contract-gated` | It needs a new schema, API, action permission or external authority and is not an unimplemented Stage07 defect. |
| `explicitly-deferred` | It is valuable later work but cannot block the approved Stage07 baseline. |

## R1 — Customer-Project Core and Safe Operations

| Work package / source | Current state | Class | Required closure work | Non-claim |
| --- | --- | --- | --- | --- |
| Foundation identity, scope cleanup and capability navigation | Partial R1 evidence now covers safe desktop/mobile capability navigation; identity/session/revocation visual states remain unaccepted | `requires-evidence` | Retain the synthetic four-width observation and add only the missing approved identity/session/revocation evidence. | No Telegram-group identity or production authentication. |
| Existing Home/Bases route | Built-client synthetic observation now covers authorized Home -> Base, allowed-empty Base -> fixed empty state -> Home, and a `403` Base -> fail-closed surface -> authorized Home re-entry; focused current-contract tests cover route/request state. | `already-closed` | Retain the safe R1 evidence; reopen only on a route regression. | No Bot/queue/management/production acceptance or production authentication claim. |
| Home queue durable destinations | existing safe Home queue exposes a draft destination; checklist row remains unchecked | `requires-evidence` | Add/retain focused queue-to-Draft Hub handoff, authorization and stale-result evidence; repair only if a focused test exposes a defect. | No notification engine or generic automation queue. |
| Recent Base/Table/View/Record navigation | R1 current-contract tests and built-client Project/Task/Record Detail return evidence are green; cursor/error cleanup breadth remains unaccepted | `requires-evidence` | Retain direct Customer/Project/Task navigation evidence and prove the remaining cursor/error cleanup states with the existing authorized read models; repair only a test-proven defect. | No global search or browser persistence. |
| Saved View semantic parity | Built bundle now visibly renders Grid/Kanban/Calendar/Form for an owner and a restricted viewer-safe read surface; a `409` re-read path is observed at desktop and Builder reachability at `390 x 844`. Editor visual treatment and remaining invalid/F2/device breadth are still unaccepted. | `requires-evidence` | Retain owner/viewer/type/mobile evidence; add only the approved editor/invalid/F2 breadth or a test-proven repair. | No public sharing, customer account or separate dashboard engine. |
| Authorized Builder/Import/Template entry | Owner built UI visibly exposes the capability-gated Builder and template/import entries; a viewer omits management controls. Focused client/API/PostgreSQL tests cover safe server denial and the controlled import preview/mapping/commit. | `already-closed` | Reuse R1 test and local observation evidence; Browser-native file selection is deliberately not claimed. | No new field type or connector. |
| Authoritative conflict/error reread | Built UI observed a V1 `409` showing fixed safe copy and canonical view/row re-read; focused current-contract tests cover record/detail and local validation/retry variants. | `already-closed` | Reopen only if a focused regression exposes a stale/false-success result. | No offline conflict engine. |
| P3 atomic Base/Table Builder | P3 evidence checked | `already-closed` | Reuse for scenario setup; reopen only on a regression. | Not broader Builder/import/template acceptance. |
| F1 Independent Field Builder | F1 evidence checked | `already-closed` | Reuse approved field types and safe metadata for fixtures/templates; do not repeat evidence without a regression. | No formula/rollup expansion. |
| F2 Relation/Lookup Builder | F2 evidence checked | `already-closed` | Reuse same-Base Customer/Project/Task relations and approved aggregations. | No cross-Base relation or new aggregation. |
| Template/import preview and explicit commit | Focused `ImportWizard` controlled-file test observed safe preview/mapping and explicit commit, and rejected an unsupported extension before content left the UI. The built owner surface visibly exposes the entry. | `already-closed` | Retain the controlled-upload alternative; do not claim Browser-native chooser coverage. | No CRM/ERP connector, file store or customer upload portal. |

## R2 — Internal Governance, Controlled Collaboration and Employees

| Work package / source | Current state | Class | Required closure work | Non-claim |
| --- | --- | --- | --- | --- |
| Hidden-field and inaccessible-resource rendering/cache boundary | Governance checklist hidden-resource row unchecked | `requires-evidence` | Verify owner/editor/viewer scenarios omit hidden fields/resources from rendered UI, protected cache and sanitized evidence. | No raw audit export or access simulator. |
| S3/S4 management and audit UI | local routes/matrices exist; lifecycle/UI evidence remains partial | `requires-evidence` | Verify member/audit/approved role-field-policy normal, denied and conflict states with safe error replacement. | No invitation, owner transfer, custom roles or group policy editor. |
| TD005/TD006 draft/contact lifecycle | S5 partial-local; Browser/provider row unchecked | `requires-evidence` | Verify field-filtered Project/Task draft lifecycle, terminal idempotency/replay/conflict/expiry and configured real-provider path. | No self-confirming employee or raw runtime payload. |
| TD009 personal assistant context | partial-local; PostgreSQL/revocation/delayed replacement/UI gap | `requires-evidence` | Add intersection/revocation and delayed-workspace replacement proof, then inspect selected-view safe summary UI. | No memory, knowledge, record picker, Telegram or external action. |
| TD010 employee management | implemented-local; protected workbench review incomplete | `requires-evidence` | Perform desktop/mobile management-workbench review and verify active/paused/grant restrictions in fixture. | No multi-Base scope or external action. |
| TD011 Team Bot one-shot summary | Partial R2 evidence now covers one non-empty synthetic permitted context through the existing Mini App API route and real OpenRouter, plus a separate loopback-fixture Mini App selection/rendering observation at desktop/default and `390 x 844`; literal Browser-provider UX remains unaccepted | `requires-evidence` | Retain the safe route/provider receipt and add only the remaining selected visual/recovery evidence. | No RAG, memory, files, picker, direct write or Telegram-group behavior. |
| Team Bot memory and generic direct write | unchecked Digital Employee rows and TD011 non-goals | `contract-gated` | Preserve as later decision candidates only. | Not a Stage07 defect. |

## R3 — Telegram Truth, Visual Closure and Stage Exit

| Work package / source | Current state | Class | Required closure work | Non-claim |
| --- | --- | --- | --- | --- |
| TD007 real identity/deep-link smoke | signed `initData` -> resolver -> Base reread observed; old checklist row stale | `requires-document-correction` | Correct source/checklist/traceability rows that still require a future smoke; retain non-production limitation. | No production or customer-group identity proof. |
| TD008 real private delivery | two separately approved one-attempt sends and resolver evidence observed; old checklist row stale | `requires-document-correction` | Correct stale delivery/resolver rows; do not send another message. | No general notification or group-send authority. |
| S6.3 isolated deployment cleanup | services/volumes/runtime/Caddy backup/key removed and Stage03 `200` verified | `already-closed` | Preserve sanitized cleanup evidence; do not recreate isolation for documentation reconciliation. | No staging/production readiness. |
| Four-width selected-design visual matrix | global visual-QA row unchecked | `requires-evidence` | Consolidate R1/R2 safe observations at 1440/1280/430/390 with role, route, allowed-data boundary and cleanup. | No claim for every feature/device. |
| Final Stage07 exit audit | global incomplete-stage row unchecked | `requires-evidence` | Reconcile every R1/R2/R3 matrix row against fresh commands/observations, verify no artifacts, and update truth documents. | Stage remains open until every in-scope row is resolved. |
| Customer group binding, internal structured Bot task creation, customer message intake, risk alerts and customer-facing send | newly discovered business requirements | `contract-gated` | Prepare a later technical decision after Stage07 closure; it must define persistence, group/member identity, API, action permission, confirmation, audit, rate limit and retry. | Not authorized in R0-R3 code. |

## Documentation-Correction Register

| Document | Required correction | Owner |
| --- | --- | --- |
| `STAGE_07_SOURCE_OF_TRUTH.md` | S6.3 resolver/cleanup and R0 boundary are already updated; retain as current top-level truth. | R0 complete |
| `STAGE_07_PROGRESS.md` | S6.3 cleanup and R0 product alignment are already recorded. | R0 complete |
| `STAGE_07_SUBSTAGE_DELIVERY_ROADMAP.md` | R0 ownership is already added; R1/R2/R3 execution entries require final reconciliation. | R3 |
| `STAGE_07_ACCEPTANCE_CHECKLIST.md` | Correct stale TD007/TD008 external-smoke rows and refresh current test counts after R1/R2. | R3 |
| `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md` | Replace stale S6 external-pending assertions and reconcile all matrix rows. | R3 |

## R0 Exit

R0 is complete: this matrix is internally consistent with the Design, BDD, SDD, source of truth, roadmap and active checklist. The user approved R0-R3 execution. R1 is active with focused Customer/Project/Task regressions, focused existing-contract backend/client/PostgreSQL checks, a successful production build and four-width safe built-client evidence. The exact boundary is recorded in [R1 Customer-Project Core Evidence](evidence/stage07-r1-customer-project-core.md); R1 itself is not yet accepted.

## 2026-07-15 R1-R3 Reconciliation Audit Correction

This section records useful implementation evidence but does **not** supersede the earlier `requires-evidence` classifications. [Stage07 Final Audit Report](STAGE_07_FINAL_AUDIT_REPORT.md) controls the current decision and lists which original requirement IDs remain unaccepted. It does not alter any approved product boundary.

| Substage | Original compatible rows reconciled | Final class | Direct closure basis |
| --- | --- | --- | --- |
| R1 | identity/scope cleanup, Home queue Draft Hub, paged Base/Table/View/Record navigation, V1 owner/viewer/editor/recovery breadth and Builder/import/template entries | `already-closed` | identity/pagination `31 passed`; focused R1 suites; built client Home/queue/draft/pagination/view Builder observations; prior real bounded Telegram identity evidence |
| R2 | hidden safe projection, governance normal/conflict/denial boundaries, draft terminal recovery, TD009 selected context, TD010 lifecycle/grants and TD011 safe Team Bot summary | `already-closed` | focused R2 backend/PostgreSQL/client/build evidence; TD009 `2` backend and `3` client tests; built governance/draft/assistant/employee observations; one existing real OpenRouter safe-route smoke |
| R3 | selected 1440/1280/430/390 visual matrix, document reconciliation, external-evidence classification, temporary resource cleanup and final audit | `already-closed` | current reconciliation record; no extra Telegram/OpenRouter/deploy operation was needed or performed |
| Later product decisions | customer group binding, customer message intake, generic Bot direct create, broad/group send, RAG/memory/files/public sharing, production rollout | `contract-gated` | outside the Stage07 approved contract; requires new user-approved technical decision |

### Current Decision

The Stage07 R0-R3 approved product scope is **not accepted**. Remaining compatible implementation/evidence work is listed in the final audit; the `contract-gated` items remain future product direction and are not silently counted as a Stage07 defect or acceptance blocker.
