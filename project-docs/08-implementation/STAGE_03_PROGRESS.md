# Stage 03 Progress

## Status

- Document status: active progress log (confirmed by user 2026-07-06)
- Scope: Stage 03 子阶段进度、测试记录、风险和后续项。
- Current Progress: 2026-07-06 已开始 Stage 03 代码实施。完成 03.0 Runtime Config And Safety Defaults、Task 2 Telegram Update Parser、Task 3 Receive-Only Webhook Route：新增 Stage03 配置安全门、真实 Telegram update parser、安全 view DTO、receive-only webhook route、secret/allowlist validation 和 `telegram.message_received` outbox event；Stage03 focused tests 18 passed，全量 backend suite 103 passed / 17 skipped。

## 1. Progress Protocol

每个子阶段完成后追加：

```text
Date:
Subphase:
Status:
Completed:
Changed files:
Tests run:
Test result:
Not done:
Risks / follow-up:
Next subphase:
```

## 2. Current State

| Subphase | Status | Evidence |
| --- | --- | --- |
| 03.0 Documentation and runtime config gate | completed | Docs finalized; runtime config contract implemented and tested (`test_stage03_config.py` 8 passed; full suite 93 passed, 17 skipped) |
| 03.1 Tencent Cloud staging runtime design | documentation completed, code/deploy pending | Deployment doc exists; no server action yet |
| 03.2 Real Telegram receive-only webhook | parser and route completed, inbox projection pending under 03.3 | `test_stage03_telegram_update_parser.py` 5 passed; `test_stage03_telegram_webhook.py` 5 passed |
| 03.3 Minimal customer binding and Telegram Inbox | pending implementation | Customer binding model/service and `telegram_inbox` projection not implemented yet |
| 03.4 PostgreSQL Outbox to Redis Streams worker | pending implementation | Redis Streams bridge and durable worker not implemented yet |
| 03.5 Acceptance, rehearsal and stage close | pending | Local focused Stage 03 tests started; no Tencent Cloud staging rehearsal yet |

## 3. Progress Records

```text
Date: 2026-07-05
Subphase: Stage 03 candidate documentation bootstrap
Status: completed as candidate docs, superseded by 2026-07-06 user decisions
Completed: Created initial Stage 03 candidate source, implementation plan, SDD, BDD, acceptance checklist and progress log based on Stage 02 deferred risks.
Changed files: project-docs/08-implementation/STAGE_03_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_03_BACKEND_INTEGRATION_PLAN.md; project-docs/08-implementation/STAGE_03_SDD.md; project-docs/08-implementation/STAGE_03_BDD.md; project-docs/08-implementation/STAGE_03_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_03_PROGRESS.md.
Tests run: not applicable, docs only.
Test result: not applicable.
Not done: Candidate docs included broader runtime assumptions that required user confirmation.
Risks / follow-up: Superseded by confirmed receive-only Telegram, Redis Streams worker, no LLM, Tencent Cloud staging direction.
Next subphase: Rewrite active Stage 03 docs to match user choices.
```

```text
Date: 2026-07-06
Subphase: Stage 03 direction confirmation
Status: completed
Completed: User confirmed Stage 03 direction through multiple-choice discussion: real Telegram ingress and durable worker, receive-only Telegram, PostgreSQL Outbox + Redis Streams worker, no LLM, Telegram Inbox/customer message registration first, secret token + optional allowlist, minimal customer binding, Tencent Cloud server deployment, Caddy HTTPS, docs first/no code for current batch.
Changed files: discussion only before documentation update.
Tests run: not applicable.
Test result: not applicable.
Not done: Stage 03 implementation code has not started by user choice.
Risks / follow-up: Need ensure all Stage 03 docs remove old local-only deployment assumption and broad provider sandbox scope before code starts.
Next subphase: Stage 03 documentation finalization.
```

```text
Date: 2026-07-06
Subphase: Stage 03 documentation finalization
Status: completed for docs-only batch
Completed: Rewrote Stage 03 source, implementation plan, SDD, BDD, acceptance checklist and progress around the confirmed direction. Added Stage 03 module index, Telegram webhook module design, customer binding/inbox module design, Redis Streams worker module design, API contract, database/migration design, security/permission design, test plan, Tencent Cloud staging deployment design, operations runbook and risk register.
Changed files: project-docs/08-implementation/STAGE_03_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_03_BACKEND_INTEGRATION_PLAN.md; project-docs/08-implementation/STAGE_03_SDD.md; project-docs/08-implementation/STAGE_03_BDD.md; project-docs/08-implementation/STAGE_03_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_03_PROGRESS.md; project-docs/08-implementation/STAGE_03_MODULE_INDEX.md; project-docs/08-implementation/STAGE_03_API_CONTRACT.md; project-docs/08-implementation/STAGE_03_DATABASE_AND_MIGRATION_DESIGN.md; project-docs/08-implementation/STAGE_03_SECURITY_AND_PERMISSION_DESIGN.md; project-docs/08-implementation/STAGE_03_TEST_PLAN.md; project-docs/08-implementation/STAGE_03_TENCENT_CLOUD_STAGING_DEPLOYMENT.md; project-docs/08-implementation/STAGE_03_OPERATIONS_RUNBOOK.md; project-docs/08-implementation/STAGE_03_RISK_REGISTER.md; project-docs/08-implementation/modules/STAGE_03_TELEGRAM_WEBHOOK_INGRESS.md; project-docs/08-implementation/modules/STAGE_03_CUSTOMER_BINDING_AND_INBOX.md; project-docs/08-implementation/modules/STAGE_03_REDIS_STREAMS_WORKER.md.
Tests run: rg stale-direction check; rg Stage 03 doc index check; git status --short.
Test result: stale-direction check returned no matches for `本地 docker compose|本地长生命周期|收发都真实|03\.6|pending user decision`; index check found Stage 03 docs referenced from implementation README, project docs README and Stage 03 source; git status shows only `project-docs/` changes and no backend code changes.
Not done: No Stage 03 backend code, dependencies, server deployment, DNS changes or Telegram webhook setup.
Risks / follow-up: Stage 03 implementation still requires explicit user confirmation before code, server, DNS or Telegram webhook actions.
Next subphase: User review and approval to start Stage 03 implementation.
```

```text
Date: 2026-07-06
Subphase: 03.0 Runtime Config And Safety Defaults
Status: completed
Completed: Added Stage 03 runtime settings for Telegram bot token, webhook secret, Telegram send mode, provider mode and LLM enablement. Added `validate_runtime_settings()` so staging/production require explicit `DATABASE_URL`, `REDIS_URL` and `TELEGRAM_WEBHOOK_SECRET` without requiring Bot Token for receive-only runtime. Wired validation into `create_app()` so staging fails fast before serving. Added safety validation rejecting real Telegram send mode, enabled LLM and enabled provider mode in production-like environments. Wrote TDD tests first and observed RED failures before implementation.
Changed files: backend/app/core/config.py; backend/app/main.py; backend/tests/unit/test_stage03_config.py; project-docs/08-implementation/STAGE_03_BACKEND_INTEGRATION_PLAN.md; project-docs/08-implementation/STAGE_03_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_03_PROGRESS.md.
Tests run: cd backend; pytest tests/unit/test_stage03_config.py::test_create_app_validates_staging_runtime_settings -v; cd backend; pytest tests/unit/test_stage03_config.py::test_staging_runtime_rejects_external_action_modes -v; cd backend; pytest tests/unit/test_stage03_config.py -v; cd backend; pytest tests -q.
Test result: TDD RED first failed because `validate_runtime_settings` was missing, then `create_app()` did not raise in staging, then unsafe external-action modes were not rejected. After implementation, focused tests passed, config suite 8 passed, full suite 93 passed and 17 skipped. Skips are existing Stage 02 online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL`.
Not done: No Telegram webhook route, no parser, no customer binding, no Redis Streams worker, no Tencent Cloud deployment, no DNS changes, no Telegram webhook setup, no real Telegram send, no LLM, no provider execution.
Risks / follow-up: The API runtime intentionally does not require `TELEGRAM_BOT_TOKEN` because Stage 03 is receive-only; webhook setup tooling may still need a Bot Token outside app runtime. Next code task should be Telegram update parser before route implementation.
Next subphase: Task 2 Telegram Update Parser.
```

```text
Date: 2026-07-06
Subphase: Task 2 Telegram Update Parser
Status: completed
Completed: Added Pydantic webhook payload schemas and a parser service for Telegram Bot API message updates. Parser extracts update/message/chat/user ids, message type, received timestamp, text/caption preview and file metadata for photo/document messages. Parser ignores unknown fields, does not download files, raises stable `telegram_update_invalid` errors without echoing raw payload, and exposes a safe view field DTO without raw update or secret-like fields. Followed TDD: wrote parser tests first and observed RED due missing module before implementation.
Changed files: backend/app/schemas/telegram_webhook.py; backend/app/services/telegram_update_parser.py; backend/tests/unit/test_stage03_telegram_update_parser.py; project-docs/08-implementation/STAGE_03_BACKEND_INTEGRATION_PLAN.md; project-docs/08-implementation/STAGE_03_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_03_PROGRESS.md.
Tests run: cd backend; pytest tests/unit/test_stage03_telegram_update_parser.py -v; cd backend; pytest tests/unit/test_stage03_config.py tests/unit/test_stage03_telegram_update_parser.py -v; cd backend; pytest tests -q.
Test result: Parser RED first failed with `ModuleNotFoundError: No module named 'app.services.telegram_update_parser'`. After implementation, parser suite 5 passed, combined config/parser tests 13 passed, full suite 98 passed and 17 skipped. Skips are existing Stage 02 online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL`.
Not done: No `/telegram/webhook` route, no secret header validation, no allowlist, no database writes, no outbox event, no customer binding, no Redis Streams worker, no Tencent Cloud deployment, no real Telegram webhook setup.
Risks / follow-up: Parser currently supports `message` updates first, as required by Stage 03 module doc; non-message update types remain route-level unsupported/malformed handling for Task 3. Next task is receive-only webhook route.
Next subphase: Task 3 Receive-Only Webhook Route.
```

```text
Date: 2026-07-06
Subphase: Task 3 Receive-Only Webhook Route
Status: completed for route slice
Completed: Added `POST /telegram/webhook` receive-only route. The route validates `X-Telegram-Bot-Api-Secret-Token` with constant-time comparison, applies optional `TELEGRAM_ALLOWED_CHAT_IDS` / `TELEGRAM_ALLOWED_USER_IDS` allowlists before business writes, parses Telegram-shaped message updates through the Stage 03 parser, converts accepted payloads into the existing ingestion service, and emits `telegram.message_received` outbox events instead of `agent.intent_extract`. Duplicate updates return idempotent success without duplicate messages/outbox events. Invalid secret, malformed payload and blocked allowlist paths return stable redacted errors without business rows. During full regression, restored Stage 02 default outbox idempotency key compatibility (`intent:<message_id>`) while keeping Stage 03 event-specific idempotency keys.
Changed files: backend/app/api/routes/telegram_webhook.py; backend/app/core/config.py; backend/app/main.py; backend/app/services/telegram_ingestion.py; backend/tests/integration/test_stage03_telegram_webhook.py; project-docs/08-implementation/STAGE_03_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_03_BACKEND_INTEGRATION_PLAN.md; project-docs/08-implementation/STAGE_03_SDD.md; project-docs/08-implementation/STAGE_03_BDD.md; project-docs/08-implementation/STAGE_03_API_CONTRACT.md; project-docs/08-implementation/STAGE_03_SECURITY_AND_PERMISSION_DESIGN.md; project-docs/08-implementation/STAGE_03_TEST_PLAN.md; project-docs/08-implementation/STAGE_03_MODULE_INDEX.md; project-docs/08-implementation/STAGE_03_DATABASE_AND_MIGRATION_DESIGN.md; project-docs/08-implementation/STAGE_03_OPERATIONS_RUNBOOK.md; project-docs/08-implementation/STAGE_03_RISK_REGISTER.md; project-docs/08-implementation/STAGE_03_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_03_PROGRESS.md; project-docs/08-implementation/modules/STAGE_03_TELEGRAM_WEBHOOK_INGRESS.md; project-docs/08-implementation/modules/STAGE_03_CUSTOMER_BINDING_AND_INBOX.md; project-docs/08-implementation/modules/STAGE_03_REDIS_STREAMS_WORKER.md.
Tests run: cd backend; pytest tests/integration/test_stage03_telegram_webhook.py -v; cd backend; pytest tests/unit/test_telegram_ingestion.py::test_ingest_known_group_message_creates_message_and_outbox_event -v; cd backend; pytest tests/unit/test_stage03_config.py tests/unit/test_stage03_telegram_update_parser.py tests/integration/test_stage03_telegram_webhook.py -v; cd backend; pytest tests -q.
Test result: Webhook route suite 5 passed. Initial full regression exposed a Stage 02 compatibility failure in default outbox idempotency key format; after root-cause fix, the specific regression test passed, Stage03 focused tests passed with 18 passed, and full backend suite passed with 103 passed / 17 skipped. Skips are existing online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL`.
Not done: No customer binding model/migration, no `telegram_inbox` view projection, no Redis Streams bridge, no durable worker runtime, no Tencent Cloud deployment, no DNS changes, no real Telegram webhook setup, no real Telegram send, no LLM, no provider execution.
Risks / follow-up: Route currently reuses the existing ingestion service and in-memory/SQLAlchemy UOW boundary; full Bitable `telegram_inbox` evidence remains Task 4, and Redis delivery remains Task 5/6. Need run combined/full verification before committing.
Next subphase: Task 4 Minimal Customer Binding And Telegram Inbox.
```
