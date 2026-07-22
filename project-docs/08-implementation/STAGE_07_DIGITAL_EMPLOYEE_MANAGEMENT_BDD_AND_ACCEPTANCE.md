# Stage07 Digital Employee Management BDD And Acceptance

## Status

- Status: `implemented-local` for the approved TD010 code boundary. The owning current local Browser lifecycle/workbench record is retained in [TD010 Browser Lifecycle Evidence](evidence/stage07-td010-browser-lifecycle-2026-07-16.md); `DEM-A01`--`DEM-A10` are evidence-backed but remain individually `evidenced-pending` until independent BDD acceptance. Telegram/provider/staging/production are not false local acceptance gates.
- Strict audit disposition: the documented desktop/mobile paused -> active -> paused and conflict-safe reread observation is retained and mapped in [TD010 Browser Lifecycle Evidence](evidence/stage07-td010-browser-lifecycle-2026-07-16.md). The Final Audit still controls Stage07 and no row is thereby `accepted`.
- Scope: Option A base-bound employee management, member eligibility and `draft|active|paused` transitions.

## BDD Scenarios

### DEM-A01 Safe manager directory

Given a member with existing employee update authority opens a readable Base
When they read the management directory
Then they receive only safe employee summary fields, status, access mode, counts and version
And they receive no policy JSON, runtime/provider data, trace, record/field value or hidden resource name.

### DEM-A02 Draft creation is explicit and idempotent

Given a caller has existing `digital_employee.create` and Base access
When they submit valid basic identity with an idempotency key
Then the server creates exactly one Base-bound `draft` employee at version `1`
And the response does not activate it, assign members or invoke it.

### DEM-A03 Scope is an authorized Base intersection

Given a manager edits a draft or paused employee
When they select table/view IDs
Then every ID must belong to employee Base and be currently readable by the manager
And every selected view's table must be inside selected table scope
And browser-supplied Base/table/view IDs cannot widen employee scope.

### DEM-A04 Fixed intent contract

Given a manager saves allowed intents
When the request contains an unsupported action
Then validation fails without a write or audit success
And only `summarize` and `draft_update` can be persisted by this management package.

### DEM-A05 Member assignment is eligibility, not authority

Given access mode is `assigned`
When a manager replaces member assignments
Then each member belongs to employee workspace and is active
And assignment adds no workspace/Base/view/field/record/management permission
And unassigned callers cannot discover, context-read or invoke the active employee.

### DEM-A06 Legacy workspace mode has no silent regression

Given an existing active employee predates TD010
When its additive migration completes
Then it has `access_mode=workspace` and version `1`
And current authorized callers retain the same safe contact eligibility subject to existing permissions.

### DEM-A07 Activation is a server-owned checklist

Given a draft or paused employee
When activation is requested with expected version and idempotency key
Then the server locks the employee and revalidates Base/table/view/action/member/alias invariants
And it atomically increments version, sets `active`, writes a redacted audit event and returns a safe receipt.

### DEM-A08 Pause is immediate and non-destructive

Given an active employee
When an authorized manager pauses it
Then safe contacts/context/invocations treat it as unavailable
And current records and existing record-change drafts are not changed or cancelled.

### DEM-A09 Concurrent/stale/replayed management commands fail closed

Given two management commands use the same employee
When version is stale, an idempotency key is replayed with a different request, or a concurrent command wins
Then exactly one authoritative result exists
And the losing client sees fixed reread state with no optimistic configuration.

### DEM-A10 Scope replacement discards stale management data

Given directory/detail/context/mutation reads are unresolved
When the user closes, changes Base, changes workspace or selects another employee
Then protected requests are cancelled/removed for the exact scope
And late responses cannot render, activate, pause, replace grants or open a different Base.

### DEM-A11 No prohibited expansion

Given TD010 is implemented
When migrations, routes, UI and source inventory are inspected
Then no multi-Base scope, Base reassignment, archive/delete, custom action/tool DSL, memory, knowledge, record picker, Telegram route, provider choice or external operation exists.

## Acceptance Matrix

| ID | Automated evidence required | Manual/local evidence | Not accepted by this row |
| --- | --- | --- | --- |
| DEM-A01--A04 | safe DTO/parser and Base/scope/action negative tests | manager editor has only closed controls | generic Stage06 endpoint exposure |
| DEM-A05--A06 | member grant/workspace mode and legacy migration tests | manager/member UI separation | broader member permission model |
| DEM-A07--A09 | PostgreSQL row-lock, version, idempotency, alias uniqueness and rollback matrix | activation/pause responsive observations | provider/Telegram execution |
| DEM-A10 | deferred App-flow replacement/close tests and protected-query cleanup | mobile/desktop focus return | deployment evidence |
| DEM-A11 | route/model/migration/dependency inventory | document review | future Package4 capabilities |

## Evidence Reconciliation (2026-07-14)

| Scenario | Current local evidence | Current acceptance limit |
| --- | --- | --- |
| DEM-A01--A04 | `test_stage07_digital_employee_management_api.py`, service tests and strict Mini App parser/workbench tests cover closed manager DTOs, draft creation/idempotency, Base/table/view validation and fixed intents. | No user-controlled visual check of the editor is recorded. |
| DEM-A05--A06 | Service and assignment-route tests cover active same-workspace grants, unassigned denial and legacy `workspace` eligibility. Disposable PostgreSQL migration tests prove upgrade/replay and legacy active-row defaults. | This does not create a broader member-permission model. |
| DEM-A07--A09 | Service/API tests cover activation prerequisites, pause, expected-version conflict, changed-payload idempotency conflict and active alias collision. A real local PostgreSQL two-session pause race now proves exactly one persisted write, one revision conflict, one audit event and one idempotency record. | Browser management-lifecycle observation and external execution remain open. |
| DEM-A10 | Protected-query tests prove user/workspace subtree isolation and scoped cleanup; Mini App component/app-flow tests cover bounded workbench states and fixed conflict handling. | No user-controlled management-workbench desktop/mobile focus-return observation is claimed. |
| DEM-A11 | Route, migration, model and client inventory were checked against TD010's explicit non-goals; the delivered routes and controls remain closed to the documented scope. | Future Package4 capabilities still require their own decision and approval. |

Fresh commands and results:

```text
backend: python -m pytest -q tests/unit/test_stage07_digital_employee_management_models.py tests/unit/test_stage07_digital_employee_management_service.py tests/unit/test_stage07_digital_employee_management_api.py tests/unit/test_stage07_digital_employee_assignment_api.py tests/unit/test_stage07_draft_employee_hub_api.py tests/unit/test_stage07_mini_app_api.py
result: 35 passed

postgres: python -m pytest -q tests/integration/test_stage07_digital_employee_management_postgres.py tests/integration/test_stage07_draft_employee_hub_postgres.py -m postgres
result: 3 passed, 3 deselected

mini-app: npm.cmd test -- --run
result: 56 files passed, 215 tests passed

mini-app: npm.cmd run build
result: passed
```

## Failure Matrix

| Boundary | `401` | `403` | `404` | `409` | `422` / malformed / `5xx` |
| --- | --- | --- | --- | --- | --- |
| directory/context | whole protected state removed | workspace denied | exact Base/context removed | n/a | fixed retry, no old rows |
| detail | whole protected state removed | workspace denied | exact employee subtree removed | n/a | fixed retry, no policy/config leak |
| create/config/grants | whole protected state removed | workspace denied | exact resource cleanup | reread before retry | typed local input only; no success state |
| activate/pause | whole protected state removed | workspace denied | exact employee cleanup | authoritative reread | fixed retry; no optimistic lifecycle state |

## Explicitly Skipped Until Later Approval

- Multi-Base scope, Base reassignment, archive/delete and custom employee actions.
- Generic chat/memory/knowledge/record search or primary-field display algorithm.
- Telegram assignment/binding, notification/external action, real provider call, staging and production.
- The current Codex in-app Browser local-fixture management-workbench review is recorded separately; it does not substitute for real database, provider, Telegram, staging, production or independent BDD acceptance.

## 2026-07-14 Final Local Closure Update

`python -m pytest -q tests/integration/test_stage07_digital_employee_management_postgres.py -m postgres` reports `4 passed`, including the new competing lifecycle-command contention case. The cross-module Stage07 PostgreSQL matrix reports `16 passed, 12 deselected`; full backend regression reports `627 passed, 17 skipped`; full Mini App reports `60 files / 221 tests`; production build and local migration replay pass.

The added contention evidence is local PostgreSQL evidence only. It does not prove Telegram, provider, staging, production, a user-controlled management UI review or Stage07 completion. See [final local closure evidence](evidence/stage07-final-acceptance-closure.md).

## 2026-07-16 Current Local Browser Lifecycle Supplement

The previously missing manager lifecycle/workbench observation is now retained in [TD010 Browser Lifecycle Evidence](evidence/stage07-td010-browser-lifecycle-2026-07-16.md). A current Codex in-app Browser run observed the closed manager editor, one draft creation, Base-bound table/view scope, two fixed intents, assigned-member configuration, `draft -> active -> paused -> active`, fixed `409` reread recovery, manager/member entry separation, and close-focus return at desktop and `390 × 844` mobile widths.

The Browser run used a disposable loopback fixture and synthetic labels. It is direct UI evidence only; existing service/API/PostgreSQL tests remain required for idempotency, row locking, grant eligibility, legacy migration and protected-query cleanup. No Telegram, provider, real database, deployment, staging, production or user Chrome action occurred. Therefore this supplement changes no BDD row to `accepted` and does not change the Stage07 decision.
