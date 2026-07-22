# Stage07 Final Closure Validation — 2026-07-15

## Status

- Date: `2026-07-15`.
- Scope: only the already-approved Stage07 contracts and the compatible acceptance gaps listed in the Stage07 evidence matrix. This record does not authorize a new schema, API, permission model, Telegram side effect, OpenRouter invocation, server deployment or production operation.
- Result: local implementation regressions are green, and several previously incomplete safety paths are now implemented and tested. **Stage07 is still `not accepted` as a whole.** A green aggregate suite is not substituted for a BDD row that explicitly requires a real Browser, a literal Mini App-to-provider path, or a particular role/failure matrix.
- Primary ledger: [Stage07 Acceptance Evidence Matrix](stage07-acceptance-evidence-matrix.md). The final decision remains [Stage07 Final Audit Report](../STAGE_07_FINAL_AUDIT_REPORT.md).

## What This Closure Implemented

### 1. Failure-safe idempotency release

The Stage07 Team Bot and TD005 draft invocation paths reserve an idempotency record before calling a runtime/provider. A failed runtime must not leave that new reservation stuck; otherwise the caller cannot safely retry with the same key.

- `backend/app/services/stage07_team_bot_knowledge.py` now examines the SQLAlchemy instance state before cleanup. A pending, not-yet-flushed reservation is expunged; a persistent reservation is deleted; the transaction is then committed.
- `backend/app/api/routes/stage07_draft_employee_hub.py` applies the identical pending/persistent cleanup rule to the S5 draft invocation path.
- This preserves the existing fail-closed response: no direct record mutation, no raw provider detail, and no synthetic success result.

### 2. Assistant context scope intersection

The personal-assistant catalog now excludes a candidate when its configured table scope is no longer available to the caller. This closes the server-side stale-table-grant path before the Mini App receives a catalog item. The route remains a safe DTO and continues to require an allowed view plus the fixed `summarize` action.

### 3. Draft instruction and management UI safety boundaries

- The S5 draft API now enforces the server-side `instruction` maximum of `1000`, rather than relying on client-side input behavior.
- The Digital Employee Management workbench does not allow activation while local scope/view/member/action changes have not been saved and reread from the server. The user receives fixed copy asking them to save first.
- Template install conflicts keep the affected template card locked until resolution and use fixed/redacted error copy.
- Closing Template/Import clears every current user/workspace import-job protected query, not only the currently selected template query.

## Tests Run After the Implementation

All commands below ran from the Stage07 Mini App worktree. The PostgreSQL commands used the approved local disposable test target; no Tencent environment, production database or external provider was written.

| Check | Result | What it proves / does not prove |
| --- | --- | --- |
| `backend: python -m pytest -q tests/unit/test_stage07_team_bot_knowledge_service.py` | `8 passed` | Includes the red/green pending-reservation retry case. It is not a real provider call. |
| `backend: python -m pytest -q tests/integration/test_stage07_team_bot_knowledge_postgres.py::test_team_bot_postgres_provider_failure_releases_the_summary_idempotency_key -m postgres` | `1 passed` | Real local PostgreSQL confirms a provider failure releases the persisted retry key. It is not literal Mini App UI transport. |
| `backend: python -m pytest -q tests/integration/test_stage07_draft_employee_hub_postgres.py::test_s5_postgres_runtime_failure_releases_the_draft_invocation_key` | `1 passed` | Real local PostgreSQL confirms the TD005 runtime-failure retry path. This file is intentionally not selected by the repository's `-m postgres` marker expression, so the exact named test was run. |
| `backend: python -m pytest -q tests/integration/test_stage07_assistant_context_postgres.py::test_assistant_context_postgres_rechecks_employee_table_scope_after_catalog_selection` | `1 passed` | Verifies the table-grant revocation catalog omission in real local PostgreSQL. |
| focused Template/Import, protected-query and Employee Management Mini App regressions | `16 files / 56 passed` | Verifies the UI safety repairs under the existing test harness; it is not a rendered Browser acceptance review. |
| `backend: python -m pytest -q` | `651 passed, 18 skipped` | Fresh whole-backend regression. The 17 historical Stage02 online-DB skips need `STAGE02_ONLINE_DATABASE_URL`; one skip is POSIX-only shell coverage. No Stage07 test failed. |
| `mini-app: npm.cmd run test:run` | `63 files / 227 passed` | Fresh complete Mini App automated regression. |
| `mini-app: npm.cmd run build` | passed | Fresh Vite production build. |

## Local Rendered-UI Observation

An in-app Browser-only, local acceptance fixture was created through the local FastAPI API and an isolated schema in local PostgreSQL. It used synthetic workspace/Base/table/record data and the synthetic actor `stage07-browser-owner`.

Observed before the in-app Browser webview detached:

1. Bootstrap showed the synthetic workspace via the development-header identity path.
2. Home opened `Acceptance Operations`.
3. `数字员工管理` opened and created the disposable draft employee `Acceptance Summary`.
4. Selecting `Tasks` exposed the allowed `所有记录` view only after table scope selection.
5. A member was selected on the management surface.

This is narrow local evidence for a real rendered management entry/create/scope sequence. It **does not** close TD010 lifecycle, pause/restart, conflict, focus-return, mobile-width or full role-matrix acceptance. The in-app Browser webview then lost its target (`Internal error` / target closed), so no further Browser state is claimed. No user Chrome browser was controlled.

## Provider, Telegram and Deployment Boundaries

- At the time of this 2026-07-15 validation, the Team Bot OpenRouter preflight was blocked. That environmental observation is superseded by the user-authorized [2026-07-16 real Provider validation](stage07-real-openrouter-provider-validation-2026-07-16.md); do not merge that later route evidence with the missing literal rendered Mini App UI evidence.
- No Telegram send, webhook mutation, BotFather change, remote SSH write, deployment or production operation occurred in this closure.
- Historical TD007/TD008 bounded external evidence remains historical and must not be replayed merely to increase test volume.

## Remaining Strict Acceptance Gaps

The following rows remain `blocked` in the matrix and are deliberately not changed to accepted by this record:

1. V1 invalid/denied/numeric-lookup/type-invalid Browser role-width matrix (`V1-A02`, `V1-A05`, `V1-A07`, `V1-A08`, `V1-A10`).
2. Real Browser file selection plus Template/Import four-width focus/error review (`TI-A04`, `TI-A06`, `TI-A08`).
3. Governance read/write Browser denial/retry/paging/stale terminal states (`GR-A03`, `GR-A06`, `GW-A07`).
4. TD005 provider, field-filtered Browser, protected failure and four-width evidence (`DE-A03`–`DE-A05`, `DE-A08`, `DE-A09`, `CB-A06`).
5. TD009 delayed replacement/error and full Browser review; the new PostgreSQL scope-intersection proof changes only `ACD-A03` to `evidenced-pending` (`ACD-A06`–`ACD-A08`, `ACD-A10`).
6. TD010 full owning-BDD rendered lifecycle record (`DEM-A01`–`DEM-A10`).
7. TD011 literal non-empty Mini App UI -> local API -> real provider result and full reselect/error/focus matrix (`TBK-A04`–`TBK-A09`).

## Cleanup Result

The local Browser fixture was verified to target only `127.0.0.1:5432/stage06_smoke` and schema `stage07_browser_acceptance_20260715`. The Vite process on `127.0.0.1:5173` and FastAPI process on `127.0.0.1:8000` were command-line verified before stopping. The schema was dropped with an additional `information_schema` absence check; temporary PID/log/fixture files were removed; neither process remained. No persistent test fixture is retained.
