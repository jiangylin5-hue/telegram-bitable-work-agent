# Stage 07 Requirement Traceability Audit

## Status

- Document status: active current-state requirement audit
- Scope: Stage07 source of truth, SDD, BDD, API/data/security contract, module documents, implementation plan, test plan and acceptance checklist mapped to current source, tests and browser evidence
- Current Progress: 2026-07-11 audit reconciled after real local PostgreSQL verification of the bounded P3 Base/Table Builder and F1 Independent Field Builder, plus an approved-TD001 direct-record mutation safety repair. The disposable migration smoke reached `20260710_0021`; three P3 and three F1 rollback/replay/concurrency/default-view cases passed, and the last recorded full backend suite passed `440` tests with only 17 historical Stage02 online-PostgreSQL skips. The repaired Mini App suite passed `14` files / `67` tests and production build; a disposable local browser run proved a delayed PATCH cannot restore an old workspace after switch. F1 duplicate-name and pending-dialog browser cases have four-width evidence. F2 relation/lookup has approved design/plan plus detailed BDD/SDD/module/index documents; safe transport and atomic relation-initializer commits exist locally, while remaining F2 code is paused for documentation review and has no acceptance evidence. V1 additional-view Builder, imports, Package 3 governance and all Package 4 Digital Employee scope remain incomplete or contract-gated.

## 1. Purpose

This audit prevents three incorrect conclusions:

1. a rendered Home or Base Canvas means Stage07 is accepted;
2. a frontend mock test proves backend authorization or Telegram identity;
3. an endpoint existing in Stage06 automatically authorizes a safe, complete Stage07 screen.

For every requirement the audit records the source, current evidence, status and the next action. It is the current decision ledger for Stage07 implementation; it does not replace the final Stage07 acceptance report.

## 2. Status Vocabulary

| Status | Meaning |
| --- | --- |
| `implemented-local` | Code and local automated/browser evidence prove the stated bounded behavior. |
| `partial-local` | Some path is implemented, but required states, semantics or security evidence are missing. |
| `existing-contract-unimplemented` | A suitable Stage06 endpoint exists but no Stage07 UI/service integration currently consumes it. |
| `approved-design-unimplemented` | User-approved detailed design and implementation plan exist, but no runtime code/evidence is yet claimed. |
| `contract-gated` | The requirement needs an unapproved schema, API, authorization, identity or retention decision. No implementation may start. |
| `external-evidence-pending` | Local implementation may exist, but approved Telegram/Mini App or production-like evidence is missing. |
| `not-implemented` | Neither safe implementation nor sufficient contract/evidence exists. |
| `guarded-out-of-scope` | The behavior is deliberately forbidden by the Stage07 source of truth. |

## 3. Current Evidence Snapshot

| Evidence | Result | Coverage limit |
| --- | --- | --- |
| Frontend unit/integration tests | `npm.cmd test -- --run` in `mini-app`: 14 files / 67 tests passed | uses mocked server responses; does not prove backend authorization. |
| Frontend production build | `npm.cmd run build`: passed | proves TypeScript/Vite build only. |
| Full backend regression | `python -m pytest -q` in `backend` with the authorised disposable local URL: 440 passed, 17 skipped | The only skips are 17 historical Stage02 online-PostgreSQL cases requiring `STAGE02_ONLINE_DATABASE_URL`; all P3/F1 local PostgreSQL cases ran. |
| Stage07 backend contract tests | `backend/tests/unit/test_stage07_mini_app_api.py` plus related Stage06 platform tests are included in full regression | current suite proves approved read models and hidden-field filtering, not all UI packages. |
| Browser desktop QA | disposable local fixtures cover the existing Home/Base flows and the F1 direct-edit success reread; the retained F1 artifact shows Grid and Record Detail converging on version 2 | fixtures are not real Telegram or backend environments; they were removed after use. |
| Browser mobile QA | F1 field creation opened from the nonempty-table trigger at `390x844`; the sheet, retry/denial states, duplicate-name local feedback and pending-dialog lock were checked at 430px and 390px | fixtures are local-only; delayed workspace/view replacement is correctly covered by an application scope-isolation test. |
| Git state | `3f291d1 docs(stage07): retain F1 direct edit evidence`; clean worktree at audit reconciliation | a commit is traceability evidence, not acceptance. |

## 4. Package 1: Foundation And Session Boundary

| Requirement | Source | Status | Evidence | Remaining work / acceptance condition |
| --- | --- | --- | --- | --- |
| React/Vite/TypeScript/Tailwind/lucide baseline | Source §7; Plan cross-package gate | `implemented-local` | `mini-app/package.json`, build pass | Keep baseline unchanged. |
| Light Work Queue Atlas visual system and responsive shell | UI spec; Source §2 | `partial-local` | `AppShell.tsx`, `styles.css`, desktop/mobile QA at selected paths | Must compare 1440/1280/430/390 screenshots to accepted concepts; current no full visual fidelity ledger. |
| Server-verified bootstrap and active memberships only | Source §6; API Contract §4 | `implemented-local` | `GET /mini-app/bootstrap`, `stage07_mini_app_api` tests, App bootstrap flow | Real Mini App identity proof remains external-evidence-pending. |
| Workspace switch removes old protected model | SDD §3; App Shell module | `partial-local` | `protectedQuery.ts` has user/workspace-prefixed keys and cancellation/removal; `App.tsx` clears the old scope before target Home, invalidates request generations on session expiry and observes that latch in direct record mutations; Base/view/record/cursor queries consume cancellation signals. Application tests and a disposable browser run prove old reads or a delayed PATCH cannot restore previous workspace state. | Full real revocation/expiry integration coverage remains incomplete. |
| Desktop/mobile navigation derives from server capability | Source §5; BDD 1/2 | `partial-local` | management entries conditionally render from `capabilities` | Primary links are presentation anchors; Bases/Bots/More routes and management route behavior are incomplete. |
| Loading, denied and network states | Source §5; SDD §8 | `partial-local` | `App.tsx` loading/denied/error branches | No density-matched skeleton, retry, expired-session recovery or 401 cache purge. |
| Safe deep-link resolver | SDD §3; BDD 10 | `contract-gated` | no Mini App verified deep-link contract | Requires approved identity/deep-link decision and test-environment evidence. |

## 5. Package 2: Workspace And Bitable Work Surface

| Requirement | Source | Status | Evidence | Remaining work / acceptance condition |
| --- | --- | --- | --- | --- |
| Queue-first Home and recent Bases | Source §5; BDD 1 | `partial-local` | `WorkspaceHome.tsx`, approved Home endpoint | Only pending confirmation summaries and recent Bases exist. Assigned records, mentions and controlled notification queues await durable models. Queue rows do not yet resolve to DraftConfirmation. |
| Authorized Base/table/view navigation | API Contract §4; Bitable module | `implemented-local` | approved navigation endpoints; Base-open and saved-view reads are protected-query keyed by verified user/workspace; `BaseCanvas` server-returned table tabs; table-switch component/application tests and browser fixture path | P3 adds bounded Base/Table initialization below. Field/additional-view building remains separate work. |
| Grid field filtering and record navigation | BDD 3/5; API Contract §4 | `implemented-local` | filtered schema/presentation/list/detail read models; hidden-field tests; browser path | Repeat negative browser/cache inspection after later state architecture changes. |
| Saved Grid/Kanban/Calendar/Form rendering | BDD 4 | `partial-local` | `ViewSurface` dispatches all four renderers and tests cover renderer shapes | Current Kanban/Calendar are display groupings; Form is a single-record detail preview. No parity proof for saved filter/sort semantics across breakpoints. |
| Cursor-safe paging | Plan Package 2; Acceptance checklist | `implemented-local` | protected `api.viewRecords(viewId, cursor)` queries, BaseCanvas load-more control, component/application tests and desktop/390px browser QA | Cursor comes only from the server response; every fetched window receives a verified user/workspace/view/cursor key, and pages are deduplicated by record ID. |
| Server-recognized filter/sort/group actions | Bitable module; BDD 3/4 | `not-implemented` | toolbar buttons are inert in `BaseCanvas.tsx` | Existing read endpoint only accepts a saved view and cursor. Any mutation/query operation needs a documented contract decision; client-only filtering is forbidden. |
| Direct version-aware scalar edit | SDD §5; Plan Package 2 | `partial-local` | `RecordDetail.tsx`, protected record-detail opening, `PATCH /records/{id}`, exact record/view invalidation and component/application conflict tests; 401/403/404, late-403, close-cancellation and concurrent-session-failure regressions; delayed-PATCH workspace-switch browser proof | Success and 409 remove/refetch only the exact record/current first-view window before rendering authority; 401 clears all Stage07 state and active-workspace 403 fails closed. Complex typed fields remain read-only; real backend authorization/revocation evidence remains pending. |
| Record create / Form submission | Source §5; BDD 4 | `partial-local` | approved `GET /tables/{table_id}/create-form`; existing `POST /tables/{table_id}/records`; backend redaction/unsupported-required test; component/application tests; disposable-fixture desktop browser success, required validation and denied-boundary evidence | Only scalar editor types are supported. `status` / `single_select` expose validated choices only; no raw options/policies. A required inaccessible/unsupported field returns `can_create: false` rather than an impossible submission. Server type-validation errors have no safe field-key mapping yet, and actual `390x844` create browser evidence remains pending. |
| P3 atomic Base/Table Builder | Source §5; P3 Design §12; API Contract §5.2 | `implemented-local` | migration `20260710_0021`; atomic initialization services/routes; backend unit/API/security tests; Mini App panel/application tests; disposable synthetic Browser QA at actual `1280x720` and `390x844`; three real PostgreSQL rollback/concurrency/default-index cases passed on 2026-07-11 | Authorized Base+initial table/default Grid and table+default Grid are implemented; only names reach the browser; receipt navigation rereads exact authorized resources; 503 retry, 409 lock, validation, denial and zero-field states have evidence. SQLAlchemy UoW now flushes newly staged Base/Table objects before the same transaction reads them; the real database found and verified this path. Local proof does not accept wider Builder/import/template or Stage07 scope. |
| F1 independent Field Builder | Source §5; F1 Design; F1 Plan; Bitable module | `implemented-local` | safe `SafeTableField` Canvas projection; `POST /tables/{table_id}/field-initializations`; server-generated key/order/default policy; field-row lock, idempotency and sanitized audit; choice-aware create/direct edit; protected re-read/cache cleanup; backend and frontend F1 tests; four-width disposable Browser QA; retained `artifacts/stage07/f1-direct-edit-success-1440.png`; duplicate-name allowlist/pending-dialog browser runs at 1440px/1280px/430px/390px; three real PostgreSQL rollback/replay/concurrent-order/view-append cases passed on 2026-07-11; `mini-app/design-qa.md` | A corrected fixture proves direct-edit success visually. At all four widths the duplicate response retains its field value, maps only the allowlisted code and suppresses the server message; the pending dialog locks create/close/cancel. Delayed workspace replacement remains covered by the application scope-isolation test. F2/V1/import/governance/Package 4 remain out of scope. |
| F2 relation/lookup Builder | Source §5; F2 Design; F2 Plan; F2 BDD/SDD/Work Surface/Complex Index | `partial-local` | User-approved design/plan; detailed F2 BDD/SDD/module/index; local backend commits through `fe0b44f`; protected candidate/Pickers and create/direct-edit commits `09de7fc`/`a38b912`; safe Detail/Canvas rendering `0871dee`; exact candidate cleanup `3a8c2bc`/`8260154`; Builder and race repairs `9c25172`, `919cdc7`, `b22ee19`; App flow evidence `31b8784`; fresh Mini App suite `18` files / `90` tests and build pass; task reviews approved; disposable primary Browser flow passed at 1440/1280/430/390 with final console logs `[]`. | F2 PostgreSQL cases are environment-gated. The documented Browser denial/invalid/replay/nested matrix, full backend regression after final F2 reconciliation and the final F2 acceptance audit remain open. No F2 acceptance or production claim. |
| V1 additional View Builder | Source §5; Plan Package 2; Bitable module | `existing-contract-unimplemented` | Stage06 primitive views exist, but their raw config/policy responses are unsuitable for routine client navigation | Requires its own safe configuration/default-view/permission/mobile contract after F2; no V1 design or code is authorised. |
| Templates and import | Source §5; Plan Package 2 | `existing-contract-unimplemented` | `stage06_templates.py`: list, install, create/read/commit import, save Base template | No UI exists. Upload/preview/retry/error/Idempotency-Key UX and safe resource refresh must be specified; no contract expansion is assumed. |
| Mobile table preserves grid semantics | UI spec responsive rules | `partial-local` | grid remains horizontally scrollable; 390 detail QA | Needs explicit field-priority behavior, 430 QA and all four view parity QA. |

## 6. Package 3: Governance, Permissions And Audit

| Requirement | Source | Status | Evidence | Remaining work / acceptance condition |
| --- | --- | --- | --- | --- |
| Capability-gated management entry | Source Package 3; Governance module | `partial-local` | `AppShell` hides management entries without capabilities | Links target an unimplemented route and have no independent server read / denied-state flow. |
| Member readback | Plan Package 3 | `existing-contract-unimplemented` | `GET /workspaces/{workspace_id}/members` requires `member.read` | No UI, pagination or role/permission mutation path. |
| Role/permission editor | Source §5; BDD 11 | `contract-gated` | Stage06 exposes authorization enforcement but no approved management mutation/read model for roles or field/view policies | Requires a dedicated authorization/API decision; client must not reconstruct policy semantics. |
| Audit readback | Source Package 3; Acceptance checklist | `existing-contract-unimplemented` | `GET /bases/{base_id}/audit-events` paginates sanitized state | No UI, pagination, empty/denied handling or browser redaction evidence. |
| Management mutation cache refresh | Governance module | `not-implemented` | no management mutations/UI cache | Depends on approved management capability and a selected cache architecture. |

## 7. Package 4: Digital Employee, Draft And Telegram

| Requirement | Source | Status | Evidence | Remaining work / acceptance condition |
| --- | --- | --- | --- | --- |
| Team Bot contact directory and published lifecycle | Source §6; UI spec; BDD 6 | `contract-gated` | current Stage06 DigitalEmployee is base-bound | Requires approved workspace-scoped employee, lifecycle and contact/group binding decision. |
| Personal assistant with opt-in context | UI spec; BDD 7 | `contract-gated` | Home contains only a nonfunctional explanatory dock | Requires approved personal assistant/context/memory model; may not simulate workspace search in client state. |
| Knowledge source selection and retrieval filtering | Source §6; UI spec | `contract-gated` | no Stage07 model/evidence | Requires scope, retrieval-time permission, retention and audit decision. |
| Per-user memory partition and clear controls | Source §6; BDD 6/7 | `contract-gated` | no model/evidence | Requires schema, ownership, retention/deletion and cross-user denial decision. |
| Record-change draft review/confirm/reject | BDD 8/9; Digital Employee module | `partial-local` | Home safe queue has draft IDs/action availability; Stage06 runtime has draft endpoints | No approved Stage07 draft detail read model/UI. Primitive runtime response carries before/proposed values and trace data; direct browser use needs an explicit field-filtered contract. |
| Telegram `@` deep link/handoff | BDD 10; UI spec | `contract-gated` | Stage06 has mention/binding primitives | Mini App identity/deep-link and group/chat scope UI contract is explicitly unapproved. |

## 8. Cross-Cutting Security And Quality Gates

| Requirement | Source | Status | Evidence | Remaining work / acceptance condition |
| --- | --- | --- | --- | --- |
| Hidden fields never rendered or retained | BDD 5; API Contract §4/6 | `partial-local` | schema/presentation/list/detail share field-read filtering; App filters raw update response against schema | No central cache/telemetry implementation to audit; add revocation and error-state client-memory tests when cache layer is chosen. |
| Fail closed on denied/revoked/expired session | SDD §3/8; BDD 12 | `partial-local` | Bootstrap/Home, Base-open, saved-view, record-detail and cursor-continuation reads consume TanStack cancellation signals; 401 latches the session, invalidates all request generations and removes all Stage07 query state; active-workspace 403 removes only that workspace and fails closed; direct record 404 clears only exact record/current-first-window keys. Helper/application tests prove scope removal, cancellation and stale Base/view/record/PATCH protection. | A real expiry/revocation integration test remains unimplemented. |
| No raw audit/Bot/knowledge/Telegram content in client telemetry | SDD §9; API Contract §6 | `partial-local` | no telemetry integration exists | Preserve this by design; audit any future SDK/logger before use. |
| Idempotent operations | API Contract §1; P3 API Contract §5.2 | `partial-local` | P3 initialization endpoints replay same-key safe receipts and reject a different payload; Mini App tests prove one key across retryable failure and a locked `409` conflict; real PostgreSQL same-key concurrency passed on 2026-07-11 | Frontend still does not consume idempotent import/template/draft mutation paths. |
| Visual QA at 1440, 1280, 430 and 390 | Test Plan §2; Acceptance checklist | `partial-local` | F1 disposable Browser QA exercised 1440/1280 desktop and 430/390 mobile; Workspace Ledger and a rendered F1 desktop state were reviewed together; blank validation, 503 retry, 409 lock, 403 denial, the repaired 390px mobile Add Field entry, direct-edit success, duplicate-name local feedback and pending-dialog lock were observed with zero relevant console warnings/errors. The direct-edit visual is retained at `artifacts/stage07/f1-direct-edit-success-1440.png`. | This is F1-scoped visual evidence only. It does not claim full Workspace Ledger/right-assistant-rail parity or whole-stage design parity. Delayed workspace/view replacement is an application-level scope-isolation proof, not a browser action because the dialog correctly prevents it. |
| Telegram Mini App real identity/deep-link smoke | BDD evidence; Test Plan manual | `external-evidence-pending` | none | Requires approved test environment and user authority; do not use production evidence. |
| Forbidden direct AI writes/self-confirm/audit bypass | Source §7; UI spec | `guarded-out-of-scope` | no Bot mutation UI was implemented; Stage06 remains server-controlled | Keep the guard in all future Package 4 work. |

## 9. Next Work Sequencing

1. **Completed existing-contract slice:** direct record conflicts now discard stale detail/current-window state and refetch permitted authoritative data; 403/404 transition to the generic denied boundary. The component/application regression and browser fixture evidence are retained in the progress log.
2. **Approved architecture implementation complete for its approved path:** Technical Decision 001 now has a memory-only QueryClient, user/workspace key contract, cancellation/removal helpers, Base/view/record/cursor reads and direct-edit/conflict refresh. Do not expand it into persistence, governance or Package 4.
3. **P3 and F1 bounded implementation is complete locally:** their six disposable real-PostgreSQL rollback/replay/concurrency/default-view cases now pass. F1's direct-edit, duplicate-name feedback and pending-dialog lock have four-width browser evidence; delayed workspace replacement remains an application-level scope-isolation proof. Do not treat this local evidence as production proof.
4. **F2 local implementation is in progress, not accepted:** F2 has approved design/plan and separate BDD/SDD/module/index sources. Backend transport/initialization/safe read-write/evaluation and the bounded frontend Picker, Detail/Canvas and Builder paths have local evidence. Next work is the documented integration/fixture/browser matrix and environment-gated PostgreSQL evidence; no F2 acceptance is implied. V1 additional views and import/template still each need their own safe browser contract and documented interaction design. Governance and field-filtered draft detail remain separate specification work.
5. **Dedicated Package 4 approval required:** workspace Bot contacts, personal assistant, knowledge, memory, Telegram proof/deep link and lifecycle.

## 10. Exit Gate Audit

Stage07 acceptance is **not proven**. The following required exit items currently lack evidence: complete Package 2, all Package 3, all Package 4, protected-state revocation/expiry handling, four-width visual QA, approved Telegram smoke and requirement-by-requirement automated/negative tests.

No Stage07 document, commit or test result may be used to claim stage completion until this audit's incomplete and contract-gated rows have explicit implementation/evidence or a revised, user-approved scope decision.
