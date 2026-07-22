# Stage08 Package C3 / Task 4 — Disposable PostgreSQL Composition Evidence

## Scope and authority

Implement only C3 Task 4 from the approved C3 design and implementation plan:

- `docs/superpowers/specs/2026-07-20-stage08-c3-context-composition-design.md`
- `docs/superpowers/plans/2026-07-20-stage08-package-c3-composition-implementation.md`
- `project-docs/08-implementation/STAGE_08_PACKAGE_C_CONTEXT_BDD_AND_ACCEPTANCE.md`

The task proves the existing private C3 composer/renderer against a disposable
local PostgreSQL database. It is not permission, API, schema, migration,
Provider, Telegram, Memory-policy, RAG, LangGraph, deployment, or Package E
work.

Use only the local disposable PostgreSQL fixture and
`STAGE06_LOCAL_DATABASE_URL`; do not use the default orphaned `DATABASE_URL`,
production data, Telegram, OpenRouter, or any external provider.

## Required RED → GREEN evidence

1. Create `backend/tests/integration/test_stage08_context_composition_postgres.py`.
   Reuse the established Stage08 C1/C2 disposable PostgreSQL fixture patterns;
   every case must rollback and close its session.
2. First write and run failing tests demonstrating consumption-time re-read
   requirements after private C3 composition. Cover, at minimum:

   - C1 business relation/field visibility or record-version drift;
   - C1 eligible Memory lifecycle/source/scope drift;
   - C2 active mapping, relation, provenance/source-chat-type, retention
     expiry, and purge drift;
   - a pending (>24,000-character) C2 composite whose group state drifts;
   - a legitimate unchanged direct composite that renders C1-first and its
     authorised D6 group context in deterministic order.

   A stale/invalid C1 or any C2 drift must fail closed: no stale group body
   may be emitted. A direct composite may safely preserve fresh C1 content
   only when that remains current; document the exact expected behavior.
3. Make only a minimal correction in
   `backend/app/services/stage08_context_composition.py` if real PostgreSQL
   evidence proves C3 lacks a current-state revalidation. Do not reopen C1 or
   C2, and do not modify C1/C2 persistence, migrations, API routes, or
   permissions without stopping and reporting a narrowly demonstrated defect.
4. Run the focused C3/C2/C1 suite with the disposable database and record
   actual commands/output. A minimum target is:

   ```powershell
   $originalDatabaseUrl = $env:DATABASE_URL
   $env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
   Push-Location backend
   python -m alembic upgrade head
   python -m alembic heads
   python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py tests/integration/test_stage08_context_postgres.py tests/integration/test_stage08_group_context_postgres.py tests/integration/test_stage08_context_composition_postgres.py
   $exitCode = $LASTEXITCODE
   Pop-Location
   $env:DATABASE_URL = $originalDatabaseUrl
   exit $exitCode
   ```

   Also run compileall, a production-source privacy/external-dependency scan,
   and `git diff --check`.
5. Write actual evidence to
   `project-docs/08-implementation/evidence/stage08-package-c3-composition.md`
   and a task report to
   `.superpowers/sdd/stage08-package-c-task-c3-task-4-report.md`.
   State test counts and failures exactly. Do not claim C3 or Package C is
   complete; Task 5 independent review remains required.

## Non-negotiable boundaries

- No `Message.raw_text`, `raw_caption`, `normalized_text`, Telegram transport
  source, or group body in public DTO/safe view/exception/audit/evidence.
- The pending path must never materialize, summarize, or render group body.
- No new external service calls, no persistence side effects from composition
  or rendering, no `ContextCompressor`, no digest, no provider imports.
- Do not use schema/API/permission changes to make a test pass.
- Preserve existing dirty worktree changes; do not stage, commit, reset,
  checkout, clean, or modify unrelated files.
