# Stage08 C2 Long Context Task 3 Review Package

## Review Scope

- Task brief: `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-3-brief.md`
- Implementer report: `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-3-report.md`
- Review type: local verified-ingress projection only. Task 4 authority/window/purge and all C3/E work must remain absent.

## Important Worktree Condition

The shared worktree is dirty and normal git diff is incomplete. Read the complete Task 3 surface directly:

1. `backend/app/schemas/telegram_webhook.py`
2. `backend/app/services/telegram_update_parser.py`
3. `backend/app/schemas/telegram.py`
4. `backend/app/services/telegram_ingestion.py`
5. `backend/app/api/routes/telegram_webhook.py`
6. `backend/tests/unit/test_stage08_group_context_ingestion.py`
7. `backend/tests/integration/test_stage08_group_context_postgres.py` (Task 3 additions only)
8. `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-3-report.md`

## Binding Requirements

- Parse exactly one `message` or `edited_message`, carrying `new|edited`, `chat_type`, optional UTC edit timestamp only internally; public response, secret validation and allowlists remain unchanged.
- Only current verified `group`/`supergroup`, nonempty incoming body, valid sender, exactly one active Stage06 `chat_user` binding and exactly one active same-workspace mapping with valid customer/project relation can create a projection. Every ambiguous/invalid case fails closed without reading raw stored message body.
- New data produces version 1. Known edit reuses only source identity, creates next version, supersedes only prior active projection and exact edit replay is idempotent. No second `Message` for edit.
- Source identity query must not select/deserialize `raw_text`, `raw_caption` or `normalized_text`; no historic message enumeration/backfill. `content_fragment` can only be in model/private ingress/UoW/test, never public DTO/response/audit/outbox/error/trace/Memory/RAG/Provider/checkpoint.
- New source Message and projection must share one SQLAlchemy session/transaction. Constraint failures may not expose body through exception cause/parameters. No intermediate commit.
- No new route, HTTP client, Telegram outgoing behavior, Provider/LLM, Memory, RAG/vector, Redis, LangGraph, model/migration/Stage06 Platform UoW or deployment action.
- Treat default DATABASE_URL orphan revision as a recorded environment risk; assess evidence based on the approved disposable `STAGE06_LOCAL_DATABASE_URL` tests.

## Evidence to Assess

- RED: 17 failures/1 pass before C2 ingress implementation.
- Green: 37 scoped tests including 6 disposable real PostgreSQL and 5 existing webhook tests.
- Additional RED/Green for edit replay and error-privacy flush behavior.

## Expected Output

Read-only review. Return Spec Compliance, Strengths, Critical, Important, Minor and Assessment with exact file/line references. No edits. Do not request broad suite/deployment work.
