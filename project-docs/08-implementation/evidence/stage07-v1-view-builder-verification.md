# Stage07 V1 Saved View Builder Verification Evidence

## Status

- Evidence status: local automated verification passed; V1/Stage07 acceptance remains partial
- Date: 2026-07-12
- Database boundary: authorized disposable local PostgreSQL only
- Migration head observed: `20260711_0022`

## Commands And Results

| Scope | Command | Result |
| --- | --- | --- |
| focused V1 backend | `python -m pytest -q tests/unit/test_stage07_view_builder_migration.py tests/unit/test_stage07_view_builder_schemas.py tests/unit/test_stage07_view_builder_validation.py tests/unit/test_stage07_view_builder_access.py tests/unit/test_stage07_view_builder_query_execution.py tests/unit/test_stage07_view_builder_api.py` | `24 passed in 3.00s` |
| V1 real local PostgreSQL | `python -m pytest -q tests/integration/test_stage07_view_builder_postgres.py tests/integration/test_stage07_view_builder_security_postgres.py -m postgres` | `11 passed in 18.68s` |
| full backend | `python -m pytest -q` from `backend` | `512 passed, 17 skipped in 60.41s` |
| Mini App | `npm.cmd test -- --run` from `mini-app` | `24 files / 114 tests passed` |
| Mini App production build | `npm.cmd run build` from `mini-app` | passed; Vite built 1,835 modules |
| migration topology | `python -m alembic heads` from `backend` | one head: `20260711_0022` |
| documentation/temporary cleanup | `git diff --check`; port `4174` listen check | no whitespace error; no listener after fixture shutdown |

## Full Backend Skips

All 17 skipped tests are historical `backend/tests/integration/test_online_postgres_smoke.py` cases. Their documented reason is the absent `STAGE02_ONLINE_DATABASE_URL`. They are remote-online Stage02 smoke tests, not a substitute for or failure of the local PostgreSQL V1 suite.

An initial accidental full-backend invocation at the worktree root failed collection with `ModuleNotFoundError: app`, because `backend` was not the import root. No code was changed in response. The command was immediately re-run from `backend`; the successful full-backend result above is the only result used for acceptance.

## What This Evidence Proves

- V1 typed configuration, ACL, safe route and server query tests pass in the focused set.
- The authorized local PostgreSQL suite passes its migration/default/atomicity/non-disclosure/index-plan coverage.
- The full repository backend regression and Mini App test/build gates are green at the stated point in time.
- Browser-specific findings, scope and gaps are recorded separately in [stage07-v1-view-builder-ui.md](stage07-v1-view-builder-ui.md).

## What It Does Not Prove

- Telegram Mini App identity/deep-link behavior, staging or production deployment;
- a real backend browser end-to-end session or every owner/editor/viewer Browser permutation;
- public link/group/delegation, deletion/default reassignment, import/template, governance, Bot/draft-confirmation or Stage08 functionality.
