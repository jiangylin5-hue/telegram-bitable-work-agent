# Stage08 Package C2 Long Context — Task 6 Independent Review and C3 Handoff Brief

## Authority

Execute only Task 6 in `docs/superpowers/plans/2026-07-19-stage08-package-c2-long-context-implementation.md`. This is an independent review after Tasks 1–5. Read the C2 design, D3 data contract, source-chat-type decision, C2 BDD, Task 1–5 reports, Task 5 evidence, existing code, and actual diff. Do not trust prior summaries without inspecting the files and rerunning the required verification.

## Scope

Create:

- `.superpowers/sdd/stage08-package-c-task-c2-review-package.md`
- `.superpowers/sdd/stage08-package-c-task-c2-review.md`

Only after a clean review, update C2 status/progress/checklists and C2 evidence as required by Task 6 in:

- `project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md`
- `project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md`
- `project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md`
- `docs/superpowers/plans/2026-07-19-stage08-package-c2-long-context-implementation.md`
- `.superpowers/sdd/progress.md`
- `project-docs/08-implementation/evidence/stage08-package-c2-group-history.md`

Do not modify production code, schema/migrations, tests, C1/C3, routes/API, Telegram networking, Provider/LLM, Memory/RAG/vector, Redis, LangGraph, audit/outbox, Mini App, deployment, or unrelated dirty worktree changes. Do not stage, commit, reset, checkout, clean, stamp, delete, or repair any database.

## Review Requirements

Review the actual C2 diff against D1–D6 and report findings classified as `Critical`, `Important`, or `Minor` with exact paths/lines. A clean review must establish all of the following:

1. Ingress exception only creates projections for current newly received/edited verified `group`/`supergroup`; old `Message.raw_text`, `raw_caption`, and `normalized_text` are neither read nor backfilled. Private/channel inputs remain excluded.
2. The 30d / 120 / 500 / 60k / newest 24 / newest 12k / compression-over-24k / half-life-7d rules remain bounded and fail closed. Context stays ephemeral; no digest or text crosses into a public DTO, log, error, audit, outbox, Memory, RAG/vector, Redis, Provider, LangGraph, AgentRun, or checkpoint.
3. Authority/mapping/source provenance/lifecycle revalidation remains before body selection; `unknown` cannot be selected or cause a body load; no handle/window reintroduces text or source identifier into a public representation.
4. D3 is stated truthfully: authorized local purge, expiry, known edit work; ordinary Telegram remote group deletion/revoke remains only `best_effort_group_deletion`.
5. Task 5’s shared lock is only on fresh eligible materialization; it conflicts with lifecycle purge writer, proves reader waits for a committed current outcome, and does not broaden the public contract. Assess portability risk explicitly (C2 actual database baseline is PostgreSQL; InMemory test behavior need not model database locks).
6. Package C2 closes only C2. C3 alone composes C1 + C2 and owns total budget/rendering; E alone may invoke `ContextCompressor`. C2 does not certify Package C, Stage08, provider evaluation, external Telegram activity, deployment, or production readiness.

If you find Critical or Important issues, do not alter docs to mark C2 passed. Return the findings only. If none, record the clean review and C3 handoff, preserving documented default-database orphan migration and `best_effort_group_deletion` risks.

## Independent Verification

Use a disposable approved local PostgreSQL database only. Restore `DATABASE_URL` afterwards and leave the default orphan database untouched.

Run this exact focused verification:

`$originalDatabaseUrl = $env:DATABASE_URL; $env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL; Push-Location backend; python -m alembic upgrade head; python -m alembic heads; python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage08_group_context_service.py tests/integration/test_stage08_group_context_postgres.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py; $exitCode = $LASTEXITCODE; Pop-Location; $env:DATABASE_URL = $originalDatabaseUrl; exit $exitCode`

Also independently run compileall on `app/models/stage08_group_context.py`, `app/runtime/stage08_group_context_contracts.py`, `app/services/stage08_group_context.py`, `app/services/telegram_ingestion.py`; run the C2 static scan for historical raw fields and prohibited dependencies; then run `git diff --check -- backend project-docs/08-implementation docs/superpowers`.

The static scan must be interpreted by context: identifiers present in prohibited historical raw-read paths or new forbidden integrations fail review. `content_fragment` is allowed solely in the C2 private model/private service path and focused tests; never a public DTO/log/audit renderer.

## Documentation / Return

The review package must include actual command results, files reviewed, D1–D6 disposition, data/privacy/concurrency assessment, scope exclusions, C3/E handoff, default-database risk, and cleanup. The review document must give the categorized verdict.

Return the verdict, exact verification output, changed documentation paths, remaining risks, and whether C3 may begin. Do not claim overall Stage08 or deployment completion.
