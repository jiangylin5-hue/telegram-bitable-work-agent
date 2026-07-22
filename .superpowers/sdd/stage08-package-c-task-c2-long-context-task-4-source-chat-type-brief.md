# Stage08 Package C2 Long Context — Task 4 Source-Type Closure Brief

## Authority

The user explicitly confirmed this schema change on 2026-07-20. The approved contract is `project-docs/08-implementation/decisions/STAGE_08_C2_SOURCE_CHAT_TYPE_PROPOSAL.md`, read together with `STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md`.

## Task

Close the sole remaining Task 4 review finding: persist a trustworthy, immutable C2 source type so every later authority/window re-read can distinguish verified group/supergroup sources from channels without inferring from a chat ID or calling Telegram.

Use TDD. Write a failing focused test and run RED before production behavior; then make the minimal GREEN implementation. Do not start Task 5.

## Exact Scope

Create:

- `backend/alembic/versions/20260720_0031_stage08_group_context_source_type.py`
- `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-4-source-chat-type-report.md`

Modify only:

- `backend/app/models/stage08_group_context.py`
- `backend/app/services/telegram_ingestion.py`
- `backend/app/services/stage06_platform.py`
- `backend/app/services/stage08_group_context.py`
- `backend/tests/integration/test_stage08_group_context_postgres.py`
- `backend/tests/unit/test_stage08_group_context_ingestion.py`
- `backend/tests/unit/test_stage08_group_context_service.py`

Do not change public FastAPI routes/responses/schemas, Telegram network behavior, secrets, C1/C3, Memory/RAG/vector, Provider/LLM, Redis, LangGraph, audit/outbox, Mini App, or deployment. Do not stage/commit/reset/checkout/clean.

## Immutable Data Contract

1. Add `source_chat_type` to `stage08_group_message_projections`.
2. Database values are exactly `group`, `supergroup`, `unknown`; non-null. Existing rows migrate to `unknown`; `unknown` is never eligible for C2 Context.
3. New projection rows may only be created by current verified `group`/`supergroup` ingress and must persist the parsed type. Channel/private input creates no projection. No external `chat.type` lookup and no ID-sign heuristic.
4. The column is provenance, not user-editable state. Neither generic lifecycle purge nor Task 4 service mutates it; only migration/default and creation write it.
5. Every C2 eligibility query and count-only omission query used by `Stage08GroupContextAuthorityFactory`/window must filter to `source_chat_type IN ('group', 'supergroup')`. `unknown` and invalid types are fail-closed, with no text load.
6. The field stays internal: it cannot enter public DTO/API/webhook response/audit/outbox/trace/error/Memory/RAG/vector/Provider/AgentRun/Checkpoint. It is permitted only in ORM/migration/private services and focused tests.

## Tests

Add concrete tests for:

- migration/schema rejects illegal source type and yields a single Alembic head `20260720_0031`;
- migration/backfill behavior has `unknown` and `unknown` is not selected/read;
- verified group and supergroup new/edit projection persist their exact type;
- channel is rejected at ingress and cannot be made eligible by a negative chat ID;
- authority/window re-read excludes `unknown` without loading its fragment, while valid group/supergroup remains selectable;
- no public object or exception carries type plus private fragment/identity data.

Record genuine RED for the missing field/filter, and then run Green:

```powershell
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
Push-Location backend
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage08_group_context_service.py tests/integration/test_stage08_group_context_postgres.py
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
```

Restore `DATABASE_URL` afterwards. If its default old database still has the known orphan revision, disclose it and do not stamp/delete/repair it in this task.

## Review-Specific Security Requirements

- Do not loosen the existing C2 window freshness, deep safe-view revalidation, error redaction, source-handle-only window, expiry purge, or bounded query fixes.
- Query only eligible `group`/`supergroup` rows before body selection; use separate count-only accounting for `unknown` omission if required by status, without loading `content_fragment`.
- New column/migration must be fully reversible and scoped only to C2 projection source provenance.

## Report

Append complete RED/GREEN, migration head, local PostgreSQL evidence, static privacy scan, exclusions, risks and cleanup to `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-4-source-chat-type-report.md`. Return only status, one-line verification, concerns and report path.
