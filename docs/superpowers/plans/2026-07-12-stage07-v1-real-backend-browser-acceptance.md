# Stage07 V1 Real Backend Browser Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce local, evidence-backed V1 Browser checks against real FastAPI routes and an authorized disposable PostgreSQL target; repair a discovered documented security-boundary defect with the smallest existing-contract change.

**Architecture:** Reuse the existing FastAPI development-header identity contract (`X-Stage06-User-Id`), SQLAlchemy/PostgreSQL UoW and built Vite Mini App. A temporary same-origin Node `http` proxy maps a server-set fixture role to one synthetic user header, forwards all API traffic to real FastAPI and serves no business data. It is testing infrastructure only, not a product service.

**Tech Stack:** Existing FastAPI, SQLAlchemy 2.x, Alembic, authorized local PostgreSQL, Node built-in `http`, Vite build, in-app Browser.

## Global Constraints

- Require `STAGE06_LOCAL_DATABASE_URL`; never print it and never target development, staging or production.
- Use only `v1-real-owner`, `v1-real-editor`, `v1-real-viewer` identities and reset the database after the run.
- Preserve all Stage07 API/schema/permission contracts. Inject only the existing development header server-side; never expose raw policy/configuration, URL, credential or identity to Browser state.
- Delete temporary seed/proxy scripts and logs; stop all servers and finalize Browser before reporting.
- This is local evidence only, never Telegram, staging, production or Stage07 completion evidence.

---

### Task 1: Reset the authorized local database

**Files:**

- Read: `backend/scripts/stage06_local_postgres_migration_smoke.py`
- Read: `backend/app/core/config.py`

**Interfaces:** consumes `STAGE06_LOCAL_DATABASE_URL`; produces a clean migration head `20260711_0022`.

- [x] **Step 1: Verify the local variable exists without outputting it**

```powershell
if (-not $env:STAGE06_LOCAL_DATABASE_URL) { throw 'STAGE06_LOCAL_DATABASE_URL is not configured' }
```

- [x] **Step 2: Use the existing classification-aware reset and migration**

```powershell
python scripts/stage06_local_postgres_migration_smoke.py
python -m alembic heads
```

Expected: smoke success and one `20260711_0022 (head)`.

---

### Task 2: Seed the approved V1 matrix using existing services

**Files:**

- Create temporarily: `backend/scripts/stage07_v1_real_backend_seed.py`
- Read: `backend/tests/integration/test_stage07_view_builder_postgres.py`
- Read: `backend/app/services/stage06_platform.py`

**Interfaces:** consumes `SqlAlchemyStage06PlatformUnitOfWork`, `create_workspace`, `create_base`, `create_table`, `create_field`, `initialize_relation_field`, `initialize_lookup_field`, `create_record`, `initialize_v1_view`, `replace_v1_view_members`; produces a safe JSON-only manifest of opaque resource IDs.

- [ ] **Step 1: Fail closed unless the disposable URL is configured**

```python
if not os.getenv("STAGE06_LOCAL_DATABASE_URL"):
    raise SystemExit("STAGE06_LOCAL_DATABASE_URL is required")
```

- [ ] **Step 2: Create one synthetic matrix in a committed transaction**

Create workspace/base/source and target tables; fields `Title`, `Status`, `Internal`, relation and numeric `Lookup score`; one target/source record; one private Grid V1 view; editor/viewer grants. Use only the pre-existing hidden-field convention:

```python
permission_policy={"viewer": "hidden"}
```

- [ ] **Step 3: Verify persistence before Browser work**

```powershell
python scripts/stage07_v1_real_backend_seed.py
python -m pytest -q tests/integration/test_stage07_view_builder_postgres.py tests/integration/test_stage07_view_builder_security_postgres.py -m postgres
```

Expected: safe manifest and `11 passed`.

---

### Task 3: Start real FastAPI and same-origin temporary proxy

**Files:**

- Create temporarily: `mini-app/scripts/stage07-v1-real-backend-proxy.mjs`
- Read: `mini-app/src/app/api.ts`
- Read: `backend/app/api/deps.py`

**Interfaces:** consumes FastAPI at `127.0.0.1:8001`, `mini-app/dist` and the safe seed manifest; produces proxy at `127.0.0.1:4176` where API paths are forwarded unchanged except `X-Stage06-User-Id`.

- [ ] **Step 1: Start FastAPI locally**

```powershell
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
$env:APP_ENV = 'local'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Expected: `/health` returns `200`.

- [ ] **Step 2: Implement only this role mapping in the proxy**

```js
const actorByRole = {
  owner: 'v1-real-owner',
  editor: 'v1-real-editor',
  viewer: 'v1-real-viewer',
};
```

The proxy may copy method, path and body to FastAPI and add `X-Stage06-User-Id`. It must not log bodies, headers, raw errors or database URLs.

- [ ] **Step 3: Verify one real route before UI work**

```powershell
Invoke-WebRequest -UseBasicParsing -Headers @{ 'X-Stage06-User-Id' = 'v1-real-owner' } http://127.0.0.1:8001/mini-app/bootstrap
```

Expected: `200`; record only status and redaction assertions.

---

### Task 4: Run the missing Browser acceptance against real services

**Files:**

- Modify: `project-docs/08-implementation/evidence/stage07-v1-view-builder-ui.md`
- Modify: `project-docs/08-implementation/STAGE_07_V1_VIEW_BUILDER_BDD_AND_ACCEPTANCE.md`

**Interfaces:** consumes temporary role path and real FastAPI/PostgreSQL responses; produces evidence-backed V1-A status changes only.

- [x] **Step 1: Role boundaries**

Verify owner member controls, editor presentation save without member controls, and viewer safe read with no create/configure controls.

- [x] **Step 2: Base/Table/Field intersection**

As viewer, verify `Internal` is absent from Canvas/schema/record/detail while allowed fields render. Do not derive a hidden key from an error response.

- [ ] **Step 3: Remaining F2 and conflict behavior**

Use safe relation candidates, numeric lookup filter/sort controls and one permitted Record Detail relation edit. Verify authoritative reread and fixed local stale-version text only.

- [x] **Step 4: Console and cleanup**

Inspect page `error`, `warn`, `warning`; finalize Browser; stop servers; delete temporary sources/logs; verify ports `8001`/`4176` closed; rerun existing migration smoke to erase data.

---

### Task 5: Reconcile and commit evidence only

**Files:**

- Modify: `AGENTS.md`
- Modify: `HANDOFF.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_TEST_PLAN.md`
- Modify: `project-docs/08-implementation/STAGE_07_V1_VIEW_BUILDER_BDD_AND_ACCEPTANCE.md`
- Modify: `project-docs/08-implementation/evidence/stage07-v1-view-builder-ui.md`

**Interfaces:** consumes exact command output, Browser observations and cleanup checks; produces truthful evidence with no retained test code.

- [ ] **Step 1: Run exact regression gates**

```powershell
cd backend
python -m pytest -q tests/unit/test_stage07_view_builder_migration.py tests/unit/test_stage07_view_builder_schemas.py tests/unit/test_stage07_view_builder_validation.py tests/unit/test_stage07_view_builder_access.py tests/unit/test_stage07_view_builder_query_execution.py tests/unit/test_stage07_view_builder_api.py
python -m pytest -q tests/integration/test_stage07_view_builder_postgres.py tests/integration/test_stage07_view_builder_security_postgres.py -m postgres
cd ../mini-app
npm.cmd test -- --run
npm.cmd run build
```

Expected: `24 passed`, `11 passed`, `24 files / 114 tests`, build exit 0.

- [ ] **Step 2: Verify cleanup and integrity**

```powershell
git diff --check
Get-NetTCPConnection -LocalPort 8001,4176 -State Listen -ErrorAction SilentlyContinue
rg --files backend/scripts mini-app/scripts | Select-String -Pattern 'stage07_v1_real_backend_seed|stage07-v1-real-backend-proxy'
git status --short
```

Expected: no whitespace error, listener or temporary source. Keep any unobserved V1-A row `partial-local`.

- [ ] **Step 3: Commit documentation only**

```powershell
git add AGENTS.md HANDOFF.md docs/superpowers/plans/2026-07-12-stage07-v1-real-backend-browser-acceptance.md project-docs/08-implementation
git commit -m "docs(stage07): record V1 real backend browser evidence"
```

Do not push, deploy or claim V1/Stage07/production completion.

## Self-Review

- Covers current handoff gaps: real routes, Base/Table/Field intersection, numeric lookup/Record Detail and Browser evidence.
- Changes no product feature, migration, route, permission or dependency.
