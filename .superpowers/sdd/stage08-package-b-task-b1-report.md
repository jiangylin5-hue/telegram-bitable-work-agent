# Stage08 Package B — Task B1 Report

## Scope

Implemented only the Task B1 persistence boundary: Memory models, Alembic migration, Stage06 platform UoW parity, model registry export, and focused tests. No memory policy, materializer, outbox, API, vector/RAG, provider, Telegram, network integration, frontend, or Package A work was added.

## Changed Files

- `backend/app/models/stage08_memory.py` — Added `Stage08MemoryItem` and `Stage08MemoryExtractionCandidate` with UUID/timestamp mixins, workspace foreign keys, JSONB shape checks, canonical lifecycle checks, positive version/confidence checks, unique source fingerprints, lifecycle indexes, and the MemoryItem-only `supersedes_id` foreign key.
- `backend/alembic/versions/20260718_0029_stage08_business_memory.py` — Added the persistent schema migration after `20260717_0028`.
- `backend/app/models/__init__.py` — Registered both models in the metadata import/export registry.
- `backend/app/services/stage06_platform.py` — Added the exact B1 memory/candidate add/get/lifecycle-lock/list UoW methods in the protocol, in-memory implementation, and SQLAlchemy implementation. Lists order by `created_at DESC, id DESC`; SQL lifecycle reads use `with_for_update()`.
- `backend/tests/unit/test_stage08_memory_contracts.py` — Added model contract and in-memory UoW ordering coverage.
- `backend/tests/integration/test_stage08_memory_postgres.py` — Added local PostgreSQL migration, JSONB/status/version/confidence, unique fingerprint, round-trip, ordering, and lifecycle-lock method coverage.

## TDD Evidence

### RED

Command:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k "memory"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: expected `pytest` collection failure (exit `2`): both focused test modules failed with `ModuleNotFoundError: No module named 'app.models.stage08_memory'`. This demonstrated the model/table boundary was absent before production code.

### GREEN

Command:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k "memory"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `4 passed in 4.72s` (exit `0`). The disposable local PostgreSQL fixture was available and executed the migration/constraint/round-trip tests; this is local PostgreSQL evidence only, not staging or production evidence.

## Migration Head

Command:

```powershell
Push-Location backend; python -m alembic heads; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `20260718_0029 (head)` (exit `0`).

## Fix Round 2 — Complete Column Type and Nullability Introspection

### Scope

This round resolves the remaining FR1-I-01 evidence gap only. It extends the existing PostgreSQL inspector test; no production model, Alembic migration, UoW, API, provider, Telegram, frontend, or Package A code changed.

### Added Evidence

- `stage08_memory_items`: every prescribed column is now checked for type and nullability: UUID IDs, `String(120)` `memory_type`, `String(40)` `status`, all three JSONB columns, `String(64)` fingerprint, `Integer` version, nullable UUID `supersedes_id`, and timezone-aware `DateTime` lifecycle/timestamp columns.
- `stage08_memory_extraction_candidates`: every prescribed column is now checked for type and nullability: UUID IDs, `String(120)` type, `String(40)` status, non-null `Numeric(5,4)` confidence, all three JSONB columns, `String(64)` fingerprint, `Integer` version, timezone-aware lifecycle/review/timestamp columns, and nullable UUID reviewer ID.
- The exact unique/index column and required workspace/self-FK target assertions from Fix Round 1 remain in place. Type assertions deliberately use SQLAlchemy type families and explicit declared lengths/precision/timezone/nullability, rather than unstable irrelevant PostgreSQL reflection formatting.

### RED Assessment

The newly added direct contract assertions passed on their first execution (`8 passed in 8.62s`). This is evidence that the existing B1 schema already satisfies the missing type/nullability contract; no genuine implementation failure existed to repair. No artificial schema mutation or fabricated failing assertion was introduced merely to manufacture a RED result.

### GREEN

Command:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k "memory"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `8 passed in 8.35s` (exit `0`). This is disposable local PostgreSQL evidence only, not staging or production evidence.

### Migration Head Recheck

```powershell
Push-Location backend; python -m alembic heads; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `20260718_0029 (head)` (exit `0`).

## Not Done

- No `memory_policy` mapping, confirmed-record hook, outbox event, materializer, conflict/lifecycle service, source revalidation, audit, API/schema, extraction workflow, or permissions work.
- No vector index/RAG, LangGraph, provider, Telegram, Redis, external write, frontend, Package A change, broad acceptance suite, git operation, or cleanup operation.

## Risks and Notes

- The focused test command is intentionally narrow per Task B1. Package B lifecycle/read security behavior belongs to later B2–B5 tasks.
- No temporary artifacts were created.
- No provider, Telegram, or external network call ran. The PostgreSQL fixture uses the configured disposable local database and resets its public schema.

## Fix Round 1 — Independent Review Evidence Repair

### Scope

This round addresses only the three Important test-evidence findings in `stage08-package-b-task-b1-review.md`. It changes focused tests only; no production model, migration, UoW, API, provider, Telegram, frontend, or Package A code changed.

### Added Evidence

- Lifecycle locks: the PostgreSQL test now covers both `lock_memory_item_for_lifecycle` and `lock_memory_extraction_candidate_for_lifecycle`. It captures emitted SQL and asserts a statement for each model contains `FOR UPDATE`; it then uses an independent second session plus `pg_blocking_pids` to prove that acquisition is blocked until the first session rolls back.
- Ordering parity: in-memory and PostgreSQL tests now persist two items and two candidates at the identical `created_at`, using deterministic UUID values `...0001` and `...0002`, and assert the larger ID is returned first.
- Exact persistence contract: PostgreSQL inspector tests now assert the complete column sets, JSONB/UUID/Numeric types, nullability for required and optional lifecycle/review columns, exact unique-constraint columns, exact lifecycle-index columns, workspace foreign keys, the MemoryItem self foreign key for `supersedes_id`, and its absence from candidates. Positive namespace variants prove the unique constraints are scoped by workspace and type; candidate confidence accepts both `0` and `1` and rejects both `-0.1` and `1.1`.

### RED

Command:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k "memory"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: expected focused-test RED (exit `1`): the first exact inspector assertion assumed PostgreSQL would reflect the status check as `status IN (...)`; PostgreSQL normalizes it as `status::text = ANY (...)`. A subsequent narrow RED showed PostgreSQL also exposes a unique constraint's backing index through `get_indexes()`. Neither was a production-contract defect. The test was minimally corrected to assert the canonical status literals and named exact lifecycle-index columns, while keeping exact unique-constraint assertions.

### GREEN

Command:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k "memory"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `8 passed in 8.29s` (exit `0`). This includes real disposable local PostgreSQL migration, SQL capture, concurrent blocking/unblocking, inspector, ordering, constraints, and round-trip evidence. It is not staging or production evidence.

### Migration Head Recheck

```powershell
Push-Location backend; python -m alembic heads; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `20260718_0029 (head)` (exit `0`).
