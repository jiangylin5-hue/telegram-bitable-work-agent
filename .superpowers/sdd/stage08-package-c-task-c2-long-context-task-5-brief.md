# Stage08 Package C2 Long Context — Task 5 PostgreSQL Closure Brief

## Authority and Preconditions

Implement only Task 5 from `docs/superpowers/plans/2026-07-19-stage08-package-c2-long-context-implementation.md`. Tasks 1–4 have passed their independent reviews. Read the C2 design, D3 data contract, source-chat-type decision, BDD acceptance file, Task 4 report, and the current C2 implementation before changing anything.

The approved C2 contract remains D1–D6: only newly ingested verified `group`/`supergroup` projections are readable; historical `Message` raw fields are never read or backfilled; Context is ephemeral and is not Memory; lifecycle is fail-closed; delete semantics remain `best_effort_group_deletion`.

## Task

Close C2 with real disposable local PostgreSQL lifecycle, privacy, drift, and concurrent purge/read evidence. Use TDD: add a focused test that demonstrates a real missing Task 5 guarantee and run it RED before any production correction. If the current implementation already satisfies a proposed case, retain it as verification and find a still-unproved Task 5 lifecycle/privacy guarantee; do not manufacture a failure by weakening existing code.

Do not begin Task 6 or C3.

## Exact Scope

Create:

- `project-docs/08-implementation/evidence/stage08-package-c2-group-history.md`
- `.superpowers/sdd/stage08-package-c-task-c2-report.md`

Modify:

- `backend/tests/integration/test_stage08_group_context_postgres.py`

Production files may change only if the new RED test identifies an actual C2 defect, and then only with the smallest fix in existing Task 2–4 C2 files. Do not alter C1, public API/routes/responses, schema/migrations, Telegram networking, Provider/LLM, Memory/RAG/vector, Redis, LangGraph, audit/outbox, Mini App, deployment, or unrelated worktree changes. Do not stage, commit, reset, checkout, clean, stamp, delete, or repair the default database.

## Required PostgreSQL Evidence

Starting with a valid workspace/member/chat-user binding/current group-business mapping/projection/window, independently make each later state drift and assert the previously built window cannot expose an old fragment or a serializable text/identity carrier:

1. Known edit/version supersession: an older version is not usable.
2. Retention expiry and authorized local purge: expired/purged rows cannot become readable again.
3. Mapping, member, binding, and business record relationship drift after window creation: fresh materialization must fail closed or require rebuild; it must not expose prior content.
4. Provenance drift to `unknown`: fresh materialization must not load its fragment.
5. Purge/read concurrency: coordinate two PostgreSQL sessions so the reader resolves from locked/current state and returns no stale safe output after the purge transition. Keep it deterministic and bounded; do not depend on timing sleeps as the assertion mechanism.
6. Public/safe window views, exceptions, and evidence/test diagnostics contain no `content_fragment` or source message identifier carrier.

Use current service contracts rather than internalizing text in a new DTO. Do not introduce persistent digests, logs, audit events, or cross-process state to make tests pass.

## Commands

First run the extended focused integration test RED:

```powershell
$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
Push-Location backend
python -m alembic upgrade head
python -m pytest -q tests/integration/test_stage08_group_context_postgres.py
$exitCode = $LASTEXITCODE
Pop-Location
$env:DATABASE_URL = $originalDatabaseUrl
exit $exitCode
```

Then, after the minimal GREEN correction if one is needed, run exactly:

```powershell
$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
Push-Location backend
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage08_group_context_service.py tests/integration/test_stage08_group_context_postgres.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py
$exitCode = $LASTEXITCODE
Pop-Location
$env:DATABASE_URL = $originalDatabaseUrl
exit $exitCode
```

Also run:

```powershell
Push-Location backend
python -m compileall -q app/models/stage08_group_context.py app/runtime/stage08_group_context_contracts.py app/services/stage08_group_context.py app/services/telegram_ingestion.py
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
rg -n "raw_text|raw_caption|normalized_text|TelegramBot|sendMessage|httpx|requests|OpenRouter|APIRouter|add_api_route|Redis|pgvector|LangGraph|MemoryItem|AgentRun" backend/app/models/stage08_group_context.py backend/app/runtime/stage08_group_context_contracts.py backend/app/services/stage08_group_context.py
git diff --check -- backend project-docs/08-implementation docs/superpowers
```

The known default `DATABASE_URL` orphan migration is a separate deployment-preflight risk. Restore the environment and do not modify that database.

## Reporting and Return

Write only actual results to the two evidence/report files: RED command/outcome, any minimal correction, final commands/results, Alembic head, privacy/static scan, exclusions, default-database risk, cleanup, and C3 handoff boundary.

Return a concise status, exact verification result, changed files, concerns, and report paths. Do not claim Package C/Stage08/deployment completion.
