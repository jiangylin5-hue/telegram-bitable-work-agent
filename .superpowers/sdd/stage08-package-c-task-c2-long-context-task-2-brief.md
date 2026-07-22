# Stage08 Package C2 Long Context — Task 2 Brief

## Task

Implement Task 2, **Data Model, Migration and UoW Parity**, from `docs/superpowers/plans/2026-07-19-stage08-package-c2-long-context-implementation.md`.

Task 1 is complete and independently reviewed clean. This is the first C2 code task. Follow TDD exactly: write the focused PostgreSQL test first, run and record a genuine RED failure, then add only the minimum production code and migration to obtain GREEN.

## Product Boundary

Tables remain the real-time, auditable business-fact source of truth. This task merely establishes a versioned, permission-rechecked bridge from an active Stage06 `chat_user` binding to one customer record and one project record, plus a minimal controlled group-message projection. It must not turn group text into Memory or RAG, build a context window, expose an API, or add any outgoing Telegram/LLM/network behavior.

## Exact Scope

Create:

- `backend/app/models/stage08_group_context.py`
- `backend/alembic/versions/20260719_0030_stage08_group_context.py`
- `backend/tests/integration/test_stage08_group_context_postgres.py`

Modify only as required for ORM registration and UoW parity:

- `backend/app/models/__init__.py`
- `backend/app/services/stage06_platform.py`

Create or append only Task 2 evidence:

- `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-2-report.md`

Do **not** modify webhook schemas, parser, Telegram ingestion, API routes, Mini App, Memory service, Context C1/C3, Provider/LangGraph/RAG/vector/Redis, secrets, deployment, git index or commits. Do not alter historical `Message` rows or read their raw fields.

## Binding Contract

- `Stage08GroupBusinessContextBinding` is versioned and maps one active Stage06 `chat_user` binding to **exactly one** same-workspace customer `PlatformRecord` and **exactly one** same-workspace project `PlatformRecord`.
- Mapping nulls, duplicate active mappings, workspace drift, invalid record relation, inactive mapping, or no eligible mapping must fail closed in the later service. This task must provide the storage constraints necessary for it; it must not silently pick one mapping.
- Database contract requires at most one active mapping for a binding using a partial unique index. Preserve historical/inactive mappings for audit/lifecycle by version/status, not overwrite.
- `Stage08GroupMessageProjection` represents only a future controlled projection. It has a `Message` foreign key, mapping foreign key, bounded `content_fragment`, `content_version >= 1`, UTC `event_at`, UTC `retention_expires_at > event_at`, lifecycle `active | superseded | purged`, and a stable tiebreak/order field.
- `(source_message_id, content_version)` is unique. A later known edit can become another projection version; Task 3 implements the writer.
- The only persistent C2 body is `content_fragment`, maximum 500 Unicode code points. Do not place it in any public schema, audit, error, trace, cache, Memory, RAG/vector, AgentRun, checkpoint, or report.
- Retention is 30 days by the later writer, but Task 2 must make timestamps/constraints compatible. `event_at` follows Telegram `message.date` converted to UTC; delivery time never determines ordering.
- UoW must have matching protocol/in-memory/SQLAlchemy methods for the minimum add/get/list/lock/purge lifecycle support required by later C2 tasks. Lock mapping/projection lifecycle transitions only, never raw `Message` rows. Follow existing project UoW naming, typing and ownership patterns instead of inventing a second repository architecture.
- All IDs and times must be safe/invariant consistent with surrounding Stage06 and Stage08 models. Use PostgreSQL constraints/indexes, not Python-only validation, for essential integrity.

## Required Tests and Verification

First write the integration test with disposable real PostgreSQL fixtures that creates one workspace/base/table/customer/project, one active Stage06 `chat_user` binding and one valid C2 mapping. It must prove at least:

1. A second active mapping for the same binding is rejected at database level.
2. Valid mapping/customer/project use the same workspace and projection is linked to that mapping and a source Message.
3. Projection constraints reject `content_version < 1`, non-UTC/incompatible timestamp shape according to project conventions, `retention_expires_at <= event_at`, invalid lifecycle and duplicate `(source_message_id, content_version)`.
4. An expired, purged or superseded projection is not returned as active by the matching UoW list method.
5. Fragment length boundary accepts 500 code points and rejects 501.

Run and record:

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

The first run must be a RED failure because C2 models/UoW/migration are initially absent. After minimal implementation, run:

```powershell
Push-Location backend; python -m alembic upgrade head; python -m alembic heads; python -m pytest -q tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected GREEN evidence: exactly one Alembic head `20260719_0030` and the focused real PostgreSQL test passes. If the local PostgreSQL environment is unavailable, report the exact failure and still run safe static/compile checks; do not fake evidence.

## Dirty Worktree Rules

The shared worktree contains unrelated uncommitted Stage06/07 changes. Do not stage, commit, reset, checkout, clean, reformat broad files or modify files outside this brief. Do not claim broad suite health based on focused Task 2 tests.

## Report

Write the complete report to `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-2-report.md`, including:

- exact changed files and behavior;
- RED command/output summary, GREEN commands/output summary, migration head;
- whether real PostgreSQL evidence ran, and exact evidence count;
- static/privacy checks performed;
- explicit statement that no webhook/API/Telegram network/Provider/Memory/RAG/Context window/deployment/external write happened;
- self-review, remaining risks, and any files deliberately left for Tasks 3–5.

Return only status, one-line verification, concerns, and report path.
