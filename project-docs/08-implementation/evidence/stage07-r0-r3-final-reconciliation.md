# Stage07 R0-R3 Final Reconciliation

## Status

- Date: 2026-07-15.
- Decision: `historical supporting evidence / not whole-stage acceptance`.
- Scope: the observed R1/R2/R3 implementation and verification slices for the compatible originally-approved Stage07 rows. It is not an initial-product acceptance baseline.
- Non-claim: this is not a production-readiness declaration, a broad Telegram authorization, a customer-facing launch, or approval for any new schema/API/permission/action.
- Supersession rule: [Stage07 Final Audit Report](../STAGE_07_FINAL_AUDIT_REPORT.md) supersedes this document as the current whole-stage decision. An older BDD/SDD/checklist row remains an active blocker when it names a compatible original requirement-ID evidence gap.

## Acceptance Boundary

The acceptance applies to the approved product loop below. Each user-visible result is rendered from an existing permission-filtered server DTO and lands in a durable record, draft, audit receipt, or authorized Base/view destination.

```text
verified Telegram or local development identity
-> authorized workspace/Base/table/view
-> Customer/Opportunity -> Project -> Task navigation
-> saved view / field / import / governance controls when capability allows
-> digital employee summary or change proposal
-> record_change_draft -> explicit confirmation -> audit
```

It does not add the future customer-group binding, customer-message intake state machine, internal Bot direct-create command, scheduled alerting, customer group send, RAG, memory, file store, public sharing, multi-Base employee scope, or production deployment. Each would alter an approved contract and remains a later technical decision.

## Evidence Discipline

| Evidence class | What was used | What it is allowed to establish | What it cannot establish |
| --- | --- | --- | --- |
| Focused backend tests | Existing service/API/identity/pagination tests plus the R1 customer-project regression and TD009 API tests | authorization, closed DTOs, failure codes, stale-result cleanup and durable service behavior | rendered visual quality or a provider interaction |
| Disposable local PostgreSQL | Existing approved V1/template-import/governance/draft/employee matrices | persistence, migrations, locks, rollback, concurrency and versioned mutation behavior | Telegram or production behavior |
| Mini App tests and build | Focused route/workbench/view-builder/governance/draft/employee/assistant/Team-Bot tests plus production build | typed client transport, visibility, safe fixed errors, retries and responsive component state | real identity/provider/network authority |
| Codex in-app Browser | Temporary loopback fixture with invented safe DTOs; no user Chrome control | rendered routes, visible capability boundaries, fixed errors and responsive reachability | FastAPI/PostgreSQL/provider/Telegram end-to-end behavior |
| Bounded external evidence | Earlier user-approved isolated TD007/TD008 Telegram flow and one real OpenRouter Team Bot safe-route smoke | signed Telegram identity/resolver/Base reread, one controlled delivery receipt, and a non-empty provider result through the approved API route | production, broad send rights, or literal Browser-to-provider tracing |

All synthetic browser fixtures used human-readable invented strings only. They were stopped, source-deleted and their loopback ports were verified closed. No secret, raw Telegram identifier, raw `initData`, opaque business record ID, raw policy, raw error body, provider prompt or provider answer is retained in this evidence.

## R1 Closure

| R1 row | Direct acceptance evidence | Result |
| --- | --- | --- |
| Identity, session and revocation | `test_stage07_telegram_mini_app_identity.py`, `test_stage06_identity.py` and `test_stage06_pagination.py` completed `31 passed`. They cover signed `initData` HMAC/freshness/duplicate/tamper rejection, active-member binding resolution, inactive/missing/ambiguous fail-closed outcomes, production header rejection and protected cursor semantics. The isolated non-production Telegram launch separately recorded signed identity -> resolver -> authoritative Base reread. | Closed for the approved identity boundary; no production claim. |
| Home queue -> Draft Hub | Built client opened the queue destination, opened one field-filtered draft, received a synthetic `409`, used the labelled reread action, then rendered the canonical confirmed state and a safe audit receipt. `draft-employee-app-flow` and `draft-employee-hub` are part of the focused client suite. | Closed; no generic automation queue or notification engine. |
| Customer/Project/Task navigation and pagination recovery | Browser evidence covers Home -> Base -> Project/Task/Record Detail and return. The second closure fixture kept the first authorized page visible after a retryable next-page failure, then appended the canonical second page after retry. `workspace-navigation` plus the cursor backend test cover cancellation, scope replacement and cursor construction. | Closed; no global search or persistent browser state. |
| Saved Views and Builder | Owner Grid/Kanban/Calendar/Form semantics, viewer control omission, owner control exposure, `409` canonical reread and mobile Builder reachability were observed. A restricted editor was able to open the typed Builder context. `view-builder-errors`, `view-builder-lifecycle` and `view-builder-responsive` cover invalid, conflict, F2-safe and replacement-state handling. A synthetic post was intentionally unsupported by the local fixture and rendered only the fixed network boundary; it is not counted as a persistence test. | Closed for the approved V1 contract; no public share/dashboard engine. |
| Template/import and F1/F2/P3 | Existing focused API/client/PostgreSQL evidence covers same-Base relations, fixed lookup aggregation, controlled preview/mapping/explicit commit and authorized builder visibility. Browser-native file chooser automation is deliberately not claimed. | Closed for approved bounded contracts. |

## R2 Closure

| R2 row | Direct acceptance evidence | Result |
| --- | --- | --- |
| Hidden-field/resource boundary | Customer-project safe projection and existing governance tests prove field omission and denied scope behavior; the prior local FastAPI/PostgreSQL browser observation recorded viewer field omission. Current closure fixtures render only DTO labels and raw sentinel strings were absent (`0` matches). | Closed; no raw audit export or access simulator. |
| Governance S3/S4 | Built UI opened governance, selected the approved member/field-policy flow, handled a version `409` with fixed text, reread the canonical policy and never rendered the fixture raw detail. Existing governance app/workbench tests cover normal, denial and replacement behavior. | Closed; no invitation, owner transfer or custom role model. |
| TD005/TD006 draft lifecycle | Browser queue handoff/recovery above, current draft unit/PostgreSQL/client evidence and prior real OpenRouter safe draft cases cover field filtering, terminal version/idempotency/replay/concurrency, confirmation audit and no pre-confirmation record write. | Closed; no self-confirming employee or raw runtime payload. |
| TD009 personal assistant | `test_stage07_assistant_context_api.py` passed `2`; `assistant-context-app-flow` and `assistant-context-workbench` passed `3`. Browser selected the permitted assistant, then a permitted view, and rendered a fixed safe summary/citation. The selection is reread before command execution and no draft/direct-write control is exposed. | Closed; no memory/knowledge/record picker. |
| TD010 employee management | Browser inspected paused -> active read-only -> paused lifecycle at desktop and management/configuration reachability at `390 x 844`. Existing focused tests and local PostgreSQL lifecycle contention verify grants, versioning, idempotency and audit. | Closed; no multi-Base scope or external action. |
| TD011 Team Bot | The earlier one real OpenRouter safe-route invocation returned a non-empty summary, safe citation and audit/agent receipt without record mutation or raw prompt/response persistence. Browser separately observed the selected-view workbench and safe rendering. | Closed as a composed route/provider plus UI acceptance; not falsely labelled literal Browser-to-provider tracing. |

## R3 Final Audit

### Commands executed in this closure pass

```powershell
# Backend: identity, revoked/ambiguous binding and cursor safety
python -m pytest -q tests/unit/test_stage07_telegram_mini_app_identity.py tests/unit/test_stage06_identity.py tests/unit/test_stage06_pagination.py
# 31 passed

# Backend: TD009 selected-context API boundary
python -m pytest -q tests/unit/test_stage07_assistant_context_api.py
# 2 passed

# Mini App: remaining R1/R2 UI/recovery workbenches
npm.cmd run test:run -- src/test/workspace-navigation.test.tsx src/test/view-builder-errors.test.tsx src/test/view-builder-lifecycle.test.tsx src/test/view-builder-responsive.test.tsx src/test/draft-employee-app-flow.test.tsx src/test/draft-employee-hub.test.tsx src/test/governance-write-app-flow.test.tsx src/test/governance-workbench.test.tsx src/test/digital-employee-management-app-flow.test.tsx src/test/digital-employee-management-workbench.test.tsx src/test/team-bot-app-flow.test.tsx src/test/team-bot-workbench.test.tsx
# 12 files / 48 passed

# Mini App: TD009 workbench and replacement flow
npm.cmd run test:run -- src/test/assistant-context-app-flow.test.tsx src/test/assistant-context-workbench.test.tsx
# 2 files / 3 passed
```

Earlier in the same continuous R0-R3 pass, the focused R1 suites (`39` backend, `11 files / 53` client, V1 PostgreSQL `11`, template/import PostgreSQL `6`, and build) and focused R2 suites (`41` backend, R2 PostgreSQL `11`, `20 files / 62` client, and build) passed. The real Team Bot OpenRouter smoke and the bounded isolated Telegram TD007/TD008 evidence were intentionally not rerun: no owning contract changed and additional external calls are neither needed nor authorized merely to increase test volume.

### Browser/temporary-resource closure

- The Codex in-app Browser alone was used; the user's Chrome session was never controlled.
- The final fixture server was stopped, its source file was deleted, and loopback port `4181` was verified closed.
- The in-app Browser viewport was reset and its tabs were finalized.
- The final raw-sentinel check reported `draft=0`, `governance=0`, `pagination=0`; final page logs were informational official Mini App bridge events only.

## Final Decision and Residual Risk

This reconciliation preserves valid R1/R2/R3 observations, but the approved Stage07 scope is **not accepted**. The strict decision and compatible remaining work are in [Stage07 Final Audit Report](../STAGE_07_FINAL_AUDIT_REPORT.md). In particular, aggregated focused tests or fixture Browser observations do not replace an owning BDD's specific role, failure, real-PostgreSQL or literal provider-path requirement.

The following are explicitly outside this completion decision and must not be silently attached to Stage07:

1. Production/staging operation, monitoring, backups, support and rollback drills.
2. Broad or group Telegram delivery, customer-facing authorization, customer-to-project group mapping and customer-message intake.
3. RAG, long-term memory, files/URLs, public links, generic data export, arbitrary agent tools and direct record writes.
4. A future diagnostic requirement for a literal Mini App Browser gesture to the real provider. The approved safe route/provider smoke plus separately observed UI prove the current product behavior without exposing a user browser to provider credentials.

These are next-stage technical-decision candidates, not Stage07 defects.
