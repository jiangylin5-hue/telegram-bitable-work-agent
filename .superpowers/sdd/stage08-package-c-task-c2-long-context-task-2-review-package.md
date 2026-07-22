# Stage08 C2 Long Context Task 2 Review Package

## Review Scope

- Task brief: `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-2-brief.md`
- Implementer report: `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-2-report.md`
- Review type: model/migration/UoW/integration-test implementation only. Task 3 ingress and Task 4 authority/window must remain absent.

## Important Worktree Condition

The shared worktree is dirty and the target files can be untracked or mixed with unrelated Stage06/07 modifications. Do not treat a normal git diff as complete. Directly read this full implementation surface:

1. `backend/app/models/stage08_group_context.py`
2. `backend/alembic/versions/20260719_0030_stage08_group_context.py`
3. `backend/app/models/__init__.py` (only C2 export/registration portions)
4. `backend/app/services/stage06_platform.py` (only C2 UoW protocol/in-memory/SQLAlchemy additions)
5. `backend/tests/integration/test_stage08_group_context_postgres.py`
6. `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-2-report.md`

## Binding Requirements

- One active Stage06 `chat_user` binding maps to exactly one same-workspace customer `PlatformRecord` and one same-workspace project `PlatformRecord`; database prevents duplicate active mapping for a binding and does not silently select a row.
- Projection is mapping-bound and source-Message-bound; `content_version >= 1`, `retention_expires_at > event_at`, valid lifecycle (`active`, `superseded`, `purged`), 500-code-point limit and unique `(source_message_id, content_version)` are database-enforced as appropriate.
- UoW active list excludes expired, superseded and purged/erased projections in deterministic `event_at DESC, id DESC` order. Lifecycle locking does not lock/read raw `Message` content.
- C2 body may appear only in model/private UoW/integration test. It must not enter a public schema, API, runtime Context carrier, audit, logs, Memory, RAG/vector, AgentRun, checkpoint, Provider or outgoing Telegram path.
- No historical `Message.raw_text/raw_caption/normalized_text` read/backfill/deletion. No webhook/parser/ingress changes, no network, API route, Provider, Memory/RAG/Redis/LangGraph, user-visible authority or context-window implementation.
- Migration must extend actual revision `20260718_0029`, report one source head `20260719_0030`, and its upgrade/downgrade must be scoped to the two C2 tables/indexes/constraints.
- Evidence must distinguish the failed legacy default `DATABASE_URL` from the passing approved disposable `STAGE06_LOCAL_DATABASE_URL`; a test fixture may be real PostgreSQL but cannot hide a failed explicit migration command.

## Verification Evidence to Assess

- Genuine RED: missing `app.models.stage08_group_context`.
- GREEN on approved disposable local PostgreSQL: source head `20260719_0030`, five focused tests pass.
- Compile and static privacy scan pass.

## Expected Review Output

Read-only independent review. Return: Spec Compliance, Strengths, Critical, Important, Minor, Assessment (`PASS` only when clean), with exact file/line references. Do not edit code. Do not expand beyond Task 2 or ask for broad suite/deployment work.
