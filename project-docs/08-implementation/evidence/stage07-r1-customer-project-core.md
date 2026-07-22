# Stage07 R1 Customer-Project Core Evidence

## Status

- Status: `partial R1 evidence recorded`; this is not R1 acceptance or Stage07 exit acceptance.
- Scope: existing approved Customer/Opportunity -> Project -> Task read/navigation, safe projection and current V1/template-import contracts only.
- Date: 2026-07-15.
- External side effects: none. No Telegram request, deployment, BotFather change, webhook change, database migration or production write occurred in this evidence pass.

## Scenario

The synthetic internal scenario uses one authorized workspace and one Base containing Customer, Project and Task tables. Project and Task references reuse the already-approved same-Base relation model. The observation exposes only human-readable business labels. It deliberately contains no real customer data, Telegram identity, opaque record identifier, raw field policy, saved-view configuration, provider payload or credential.

The scenario proves the current approved core, not the future group-binding model:

```text
Home
-> authorized Project Base
-> Projects saved view
-> Tasks table
-> Task Record Detail
-> close detail
-> Projects
```

## Automated Evidence

| Layer | Command scope | Result | What it establishes |
| --- | --- | --- | --- |
| Customer-project API regression | `test_stage07_customer_project_core_api.py` | `1 passed` | Same-Base relations are readable only through the configured view; viewer projection omits the internal-only field; an outsider fails closed. |
| Customer-project Mini App flow | `customer-project-core-app-flow.test.tsx` | `1 passed` | Home/Base/Project/Task/detail/return navigation renders labels, not opaque IDs or a raw error. |
| R1 current-contract backend set | Mini App, V1 builder, template/import focused unit tests | `39 passed` | Existing safe transport, view-builder and template/import behavior remain green. |
| R1 current-contract client set | navigation, record detail/mutation safety, views, builder, template/import focused tests | `11 files / 53 tests passed` | Existing client contracts remain green. |
| Disposable local PostgreSQL | V1 builder PostgreSQL tests | `11 passed` | Builder/query behavior has real PostgreSQL evidence. |
| Disposable local PostgreSQL | existing template/import security tests | `6 passed` | Existing template/import authorization/persistence boundary remains green. |
| R1 closure client subset | Customer-project/navigation/detail/V1/template-import focused tests | `8 files / 38 tests passed` | The safe core, four renderer semantics, conflict reread, controlled import input and explicit commit remain green. |
| Mini App production build | `npm.cmd run build` | passed | Current client compiles with the R1 regressions present. |

### Test-first outcome

The initial new backend fixture omitted the approved relation field from the Project view's explicit `fields` configuration. Candidate authorization and record authorization were already correct, so the test expectation was wrong for a configured-view projection. The fixture was corrected; no production code, schema, API, permission rule or migration changed.

## Built-Client In-App-Browser Observation

The Codex in-app Browser, not the user's Chrome browser, loaded the existing built Mini App against a temporary local synthetic fixture. The fixture was in-memory only and provided current safe DTO shapes; it was not a FastAPI/PostgreSQL substitute.

| Width | Direct observation |
| --- | --- |
| `1440` | One authorized workspace entry opened the Project Base. The Projects and Tasks tabs rendered. Opening the safe Task label produced exactly one Record Detail surface containing the Task and Project labels. The opaque Task/Project IDs were not rendered. Closing the detail returned to the Project row. |
| `1280` | The Base workbench, Projects/Tasks tabs and Project business label remained available. |
| `430` | The Base workbench, Projects/Tasks tabs and Project business label remained available. |
| `390` | The Base workbench, Projects/Tasks tabs and Project business label remained available. |

The final console scan returned `0` `error`/`warn` entries. The client does not provide a `Base Canvas` heading in this route, so no claim is made for that absent selector; the observation used the actual accessible Base Workbench and tabs instead.

### R1 V1 / Capability / Recovery Closure Addendum

On 2026-07-15, a second disposable loopback fixture exercised the current built bundle with synthetic safe DTOs. It did not call FastAPI, PostgreSQL, OpenRouter, Telegram Bot API, webhook, BotFather, cloud deployment or any user Chrome state.

| Scenario | Direct observation | What it does and does not prove |
| --- | --- | --- |
| Owner V1 semantics | The same authorized Project table rendered `grid`, `kanban`, `calendar` and `form`. Grid rendered the server-visible columns; Kanban rendered its server-selected status grouping; Calendar rendered the server-selected delivery date; Form rendered only the server-selected field order. Relation data appeared as the human label `示例客户`, not its synthetic identifier. | Proves rendered V1 type selection follows safe server DTOs. Server query/filter authority remains covered by API/PostgreSQL tests. |
| Owner capability controls | Owner saw the current Builder, new-view, field, record, template/import and digital-employee entries. The View Builder opened with field labels and typed controls only. | Proves client visibility for the server capability supplied by the fixture; backend denial remains proved by focused tests. |
| Viewer capability controls | A second fixture mode rendered a `viewer` workspace. The same Base remained readable, while `配置视图`, `新建视图`, `添加字段`, `新建记录` and `数字员工管理` were absent. | Proves the visible negative-control boundary for this current role mode. It does not replace owner/editor/viewer authorization tests or a real identity session. |
| `409` view conflict | A synthetic version conflict showed only the fixed Chinese retry copy, re-read the canonical view name and row label, and retained the Builder in a non-success state. The fixture's raw conflict detail and an opaque record identifier were absent from rendered text. | Proves one built-client conflict recovery path; canonicalization, version and concurrent-write authority remain API/PostgreSQL evidence. |
| Empty and denied Base | An authorized but empty Base rendered the fixed empty state and returned to Home. A distinct `403` Base route entered the fail-closed no-workspace surface. Reopening the authorized fixture route returned to Home without retaining the denied canvas. | Proves current rendered empty/denied boundaries in a synthetic local context; it is not a production sign-in or revocation test. |
| Mobile `390 x 844` | Owner Project workbench kept table/view tabs and safe row labels. The View Builder was reachable as a labelled dialog with close, field selection, query/type controls and save/cancel actions. | Proves selected mobile reachability only; it does not claim every device or every V1 invalid/F2 state. |

The fixture page's final console record contained only informational official Mini App bridge calls and no `warn` or `error` entry. The separate controlled `ImportWizard` test supplied a synthetic `File`, observed preview/mapping and explicit commit, and also rejected an unsupported extension before content left the UI. It is the approved controlled-upload alternative; no Browser-native file chooser selection is claimed.

## Boundary and Limitations

- Built-client observation proves the rendered current route with synthetic safe responses only. It does not prove identity, database state, FastAPI serialization, real PostgreSQL authorization or external Telegram behavior.
- The separate API and disposable PostgreSQL rows above are the evidence for authorization, persistence and field omission. They must not be conflated with the synthetic browser fixture.
- This pass closes the current Home/Base empty/denied rendering row, the owner/viewer Builder/Template/Import visible-entry row, the bounded view-conflict visual row and the approved controlled-import alternative. It does not close identity/session/revocation, Home queue-to-Draft Hub, cursor/error breadth, editor visual treatment, every invalid/F2 View Builder state or every device width.
- It introduces no Customer-to-Telegram-group mapping, structured Bot task creation, customer message intake, risk send, RAG, memory, files, public sharing, new schema/API/action or permission model.

## Cleanup

- Both in-app Browser sessions were finalized after observation.
- Both temporary local fixture processes were stopped and port `4179` was verified closed after the second pass.
- Both temporary fixture source files were deleted; no fixture source or local service is retained.
- No temporary browser artifact is retained as acceptance evidence.

## 2026-07-15 R1 Final Reconciliation Addendum

The former residual sentence in this document is superseded by [Stage07 R0-R3 Final Reconciliation](stage07-r0-r3-final-reconciliation.md). It does not change any product contract; it joins the remaining existing-contract evidence that was collected after the original R1 pass.

| Former residual | Additional direct evidence | Reconciled status |
| --- | --- | --- |
| verified identity/session/revocation | `test_stage07_telegram_mini_app_identity.py`, `test_stage06_identity.py` and `test_stage06_pagination.py`: `31 passed`; signed Telegram proof/binding fail-closed cases are also backed by the bounded isolated TD007/TD008 launch record | closed for the approved non-production boundary |
| Home queue-to-Draft Hub | Built-client queue -> draft -> synthetic `409` -> authoritative reread -> confirmed/audit receipt; draft app/workbench tests in the focused R2 suite | closed |
| cursor/error breadth | Built client retained the authorized first page on a retryable next-page failure and appended only the canonical next page on retry; workspace-navigation/pagination tests cover request/cancellation scope | closed |
| editor treatment and invalid/F2 View Builder states | Restricted editor opened typed Builder context; view-builder error/lifecycle/responsive tests cover fixed invalid/conflict/replacement handling. The temporary fixture intentionally had no create-write route; its fixed network boundary is documented but not counted as persistence proof. | closed for V1-1 through V1-15 |
| device breadth | Prior 1440/1280/430/390 safe core plus current owner/viewer/editor desktop and `390 x 844` Builder observations are compiled in the reconciliation record | closed for the selected-design matrix, not a claim about every device |

No production code was changed by this addendum. The final fixture was deleted and port `4181` was verified closed.
