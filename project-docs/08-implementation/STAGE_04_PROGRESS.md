# Stage 04 Progress

## Status

- Document status: active progress log draft
- Scope: Stage 04 子阶段进度、测试记录、风险和后续项。
- Current Progress: 2026-07-07 Tasks 1-9 are implemented locally; full backend suite passed with 172 passed / 17 skipped after the staging compose send-mode gate test was added. Local acceptance audit is recorded in `STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md`; staging rehearsal remains pending and requires separate confirmation before any real Telegram send.

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
| 04.0 Stage04 direction and documentation | completed for docs draft | User confirmed A+B+C scope and `telegram_send_requests`; Stage04 docs created |
| 04.1 Binding Management API | completed locally | Task 1 and Task 2 focused tests passed |
| 04.2 New Message Binding And Views | completed locally | Stage04 view tests, existing view regression and new-message binding regression passed |
| 04.3 Intent Placeholder Boundary | completed locally | Intent placeholder and Stage03 worker regression tests passed |
| 04.4 Restricted Test Send | completed locally | Runtime config, model/migration, request API, client and worker tests passed |
| 04.5 Staging Rehearsal And Stage Close | pending | Local readiness audit completed; requires separate confirmation before staging env change or real Telegram send |

## 3. Progress Records

```text
Date: 2026-07-06
Subphase: Stage 04 direction confirmation
Status: completed
Completed: User selected Stage04 scope AACA ABC, clarified real send target as A, requested B and C as well, and confirmed adding `telegram_send_requests`. Final scope is binding operations, no UI, chat/user/chat_user binding, no historical replay, no LLM, local + staging validation, restricted real Telegram test send to allowlisted test chat only, plus no-LLM intent placeholder.
Changed files: discussion only.
Tests run: not applicable.
Test result: not applicable.
Not done: Stage04 docs and code not yet written at this point.
Risks / follow-up: Real Telegram test send is an external write and must remain allowlisted, human-confirmed and staging-only until another stage confirms broader send.
Next subphase: Stage04 documentation package.
```

```text
Date: 2026-07-06
Subphase: Stage 04 documentation package
Status: completed for docs draft
Completed: Created Stage04 Source Of Truth, Implementation Plan, SDD, BDD, API Contract, Database And Migration Design, Security And Permission Design, Test Plan, Acceptance Checklist, Progress, Operations Runbook, Risk Register, Module Index and module docs for Binding Management, Restricted Test Send and Intent Placeholder. Updated implementation and project indexes.
Changed files: project-docs/README.md; project-docs/08-implementation/README.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_SDD.md; project-docs/08-implementation/STAGE_04_BDD.md; project-docs/08-implementation/STAGE_04_API_CONTRACT.md; project-docs/08-implementation/STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md; project-docs/08-implementation/STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_OPERATIONS_RUNBOOK.md; project-docs/08-implementation/STAGE_04_RISK_REGISTER.md; project-docs/08-implementation/STAGE_04_MODULE_INDEX.md; project-docs/08-implementation/modules/STAGE_04_BINDING_MANAGEMENT.md; project-docs/08-implementation/modules/STAGE_04_RESTRICTED_TEST_SEND.md; project-docs/08-implementation/modules/STAGE_04_INTENT_PLACEHOLDER.md.
Tests run: rg Stage04 docs file scan; rg Stage04 index scan; rg placeholder/scope contradiction scan; git diff --check; git status --short.
Test result: Stage04 docs are present and indexed from project docs; placeholder/scope scan found no active-scope contradiction, only expected runbook safety text forbidding `LLM_ENABLED=true`; `git diff --check` reported only CRLF warnings and no whitespace errors; `git status --short` shows documentation changes only.
Not done: No backend code, migration, automated tests, staging env change or Telegram send was executed.
Risks / follow-up: User must review and confirm Stage04 docs before code implementation. Any real staging env change or Telegram test send still needs separate confirmation.
Next subphase: User review of Stage04 docs.
```

```text
Date: 2026-07-06
Subphase: 04.1 Binding Management API - Task 1 Permission Actions And Schemas
Status: completed
Completed: Added Stage04 permission actions for manager role and binding create/list/disable Pydantic schemas. Added focused tests for manager/sales permission boundaries and binding create schema validation.
Changed files: backend/app/services/permissions.py; backend/app/schemas/telegram_bindings.py; backend/tests/integration/test_stage04_binding_management.py; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/integration/test_stage04_binding_management.py -v
Test result: 4 passed.
Not done: Binding management service, API routes, conflict checks and disable audit are still pending for Task 2.
Risks / follow-up: API tests must still prove that non-manager actors cannot mutate bindings through HTTP routes.
Next subphase: 04.1 Binding Management API - Task 2 service and route.
```

```text
Date: 2026-07-06
Subphase: 04.1 Binding Management API - Task 2 Binding Management Service And API
Status: completed locally
Completed: Added binding management service/UOW, in-memory and SQLAlchemy adapters, POST/GET/disable API routes, active conflict rejection, permission-denied audit, create audit and disable audit. Registered the router in the FastAPI app.
Changed files: backend/app/services/telegram_binding_management.py; backend/app/api/routes/telegram_bindings.py; backend/app/main.py; backend/app/schemas/telegram_bindings.py; backend/tests/integration/test_stage04_binding_management.py; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/integration/test_stage04_binding_management.py -v
Test result: 7 passed.
Not done: Bitable views, new-message binding regression, intent placeholder, restricted test send, migration and staging rehearsal are still pending.
Risks / follow-up: SQLAlchemy path still needs online/staging verification with real PostgreSQL after migrations and deployment.
Next subphase: 04.2 New Message Binding And Views.
```

```text
Date: 2026-07-06
Subphase: 04.2 New Message Binding And Views - Task 3 Bitable Views
Status: completed locally
Completed: Added `telegram_bindings`, `telegram_send_requests` and `telegram_intent_queue` view definitions. Added Stage04 sensitive-field handling so global roles can inspect operational Telegram ids while customer-scoped actors get masking or no send-request rows.
Changed files: backend/app/services/bitable_views.py; backend/tests/unit/test_stage04_bitable_views.py; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/unit/test_stage04_bitable_views.py -v; pytest tests/unit/test_bitable_views.py -v
Test result: Stage04 view tests 2 passed; existing bitable view tests 11 passed.
Not done: New-message binding regression and no historical rewrite tests are pending.
Risks / follow-up: At Task 3 time, `telegram_send_requests` view used a future table name; Task 7 later added the model and migration.
Next subphase: 04.2 New Message Binding And Views - Task 4 new-message binding regression.
```

```text
Date: 2026-07-06
Subphase: 04.2 New Message Binding And Views - Task 4 New Message Binding Regression
Status: completed locally
Completed: Added regression tests proving new messages resolve `chat_user`, `chat` and `user` bindings, inactive bindings are ignored, and newly created bindings do not rewrite historical messages. Existing Stage03 customer binding tests still pass; no production code changes were required.
Changed files: backend/tests/integration/test_stage04_new_message_binding.py; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/integration/test_stage04_new_message_binding.py -v; pytest tests/integration/test_stage03_customer_binding.py -v
Test result: Stage04 new-message binding tests 5 passed; Stage03 customer binding tests 5 passed.
Not done: Intent placeholder, restricted test send, migration and staging rehearsal are still pending.
Risks / follow-up: SQLAlchemy/staging path must still be exercised after deployment to prove API-created bindings affect real webhook messages.
Next subphase: 04.3 Intent Placeholder Boundary.
```

```text
Date: 2026-07-06
Subphase: 04.3 Intent Placeholder Boundary - Task 5 Intent Placeholder Service
Status: completed locally
Completed: Added no-LLM intent placeholder service and wired it into the existing `telegram.message_received` worker handler. Bound unclassified messages become `intent_ready`, unbound messages stay `needs_review`, and placeholder audit is written without creating service drafts.
Changed files: backend/app/services/telegram_intent_placeholder.py; backend/app/workers/stage03_handlers.py; backend/tests/integration/test_stage04_intent_placeholder.py; backend/tests/integration/test_stage03_worker_runtime.py; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/integration/test_stage04_intent_placeholder.py tests/integration/test_stage03_worker_runtime.py tests/unit/test_stage03_worker_runtime_factory.py -v
Test result: 8 passed.
Not done: Restricted test send config, migration, send request API/client/worker and staging rehearsal are still pending.
Risks / follow-up: Online smoke expectations that assert old `intent_status` values may need review when full suite runs.
Next subphase: 04.4 Restricted Test Send - Task 6 runtime config.
```

```text
Date: 2026-07-06
Subphase: 04.4 Restricted Test Send - Task 6 Runtime Config
Status: completed locally
Completed: Added `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` settings support and staging validation. `TELEGRAM_SEND_MODE=restricted_test` now requires `TELEGRAM_BOT_TOKEN` and non-empty test-send allowlist; unrestricted send modes are still rejected. Updated stage env example with an empty placeholder only.
Changed files: backend/app/core/config.py; backend/tests/unit/test_stage04_config.py; backend/tests/unit/test_stage03_config.py; deploy/stage03/env.stage03.example; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/unit/test_stage04_config.py tests/unit/test_stage03_config.py -v
Test result: 13 passed.
Not done: `telegram_send_requests` model/migration, request API, Telegram client, worker send handler and staging rehearsal are still pending.
Risks / follow-up: Real staging must keep the allowlist server-only and redacted from docs.
Next subphase: 04.4 Restricted Test Send - Task 7 model and migration.
```

```text
Date: 2026-07-06
Subphase: 04.4 Restricted Test Send - Task 7 `telegram_send_requests` Model And Migration
Status: completed locally
Completed: Added SQLAlchemy model and Alembic revision `20260706_0011` for `telegram_send_requests`, including request/confirmation/send-result evidence fields and indexes. Metadata tests verify the table shape and forbidden raw secret/payment columns.
Changed files: backend/app/models/telegram.py; backend/app/models/__init__.py; backend/alembic/versions/20260706_0011_stage04_telegram_send_requests.py; backend/tests/unit/test_model_metadata.py; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/unit/test_model_metadata.py -v; alembic upgrade head --sql
Test result: metadata tests 3 passed; Alembic offline SQL reached `20260706_0011` and emitted COMMIT.
Not done: Send request API, Telegram client, send worker handler and staging rehearsal are still pending.
Risks / follow-up: Online PostgreSQL migration still needs staging execution before Stage04 acceptance.
Next subphase: 04.4 Restricted Test Send - Task 8 request service and API.
```

```text
Date: 2026-07-06
Subphase: 04.4 Restricted Test Send - Task 8 Test Send Request Service And API
Status: completed locally
Completed: Added send request schemas, service/UOW, API routes and app registration. Request creation writes `telegram_send_requests` and audit only; confirm re-checks allowlist and writes `telegram.test_send_requested` outbox event; non-allowlisted targets are blocked; invalid state returns stable 409.
Changed files: backend/app/schemas/telegram_send_requests.py; backend/app/services/telegram_send_requests.py; backend/app/api/routes/telegram_send_requests.py; backend/app/main.py; backend/tests/integration/test_stage04_test_send.py; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/integration/test_stage04_test_send.py -v
Test result: 4 passed at Task 8 time; Task 9 later expanded this file to 6 passing tests with worker coverage.
Not done: Telegram Bot client, worker send handler and staging rehearsal are still pending.
Risks / follow-up: API confirm queues an outbox event only; real send remains unimplemented until Task 9 and must keep allowlist/idempotency checks in the worker.
Next subphase: 04.4 Restricted Test Send - Task 9 Telegram Bot client and worker handler.
```

```text
Date: 2026-07-06
Subphase: 04.4 Restricted Test Send - Task 9 Telegram Bot Client And Worker Handler
Status: completed locally
Completed: Added Telegram Bot `sendMessage` client with redacted response summaries, worker handler for `telegram.test_send_requested`, send idempotency guard, worker-side allowlist re-check, send result audit, outbox bridge `request_id` projection and worker factory wiring for restricted test mode.
Changed files: backend/app/clients/__init__.py; backend/app/clients/telegram_bot.py; backend/app/workers/stage03_handlers.py; backend/app/workers/stage03_runtime.py; backend/app/services/outbox.py; backend/tests/unit/test_stage04_telegram_bot_client.py; backend/tests/integration/test_stage04_test_send.py; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/unit/test_stage04_telegram_bot_client.py -v; pytest tests/integration/test_stage04_test_send.py -v; pytest tests/unit/test_stage03_worker_runtime_factory.py tests/unit/test_stage03_redis_streams_adapter.py tests/integration/test_stage03_redis_streams_bridge.py -v; pytest tests/integration/test_stage03_worker_runtime.py -v
Test result: Telegram Bot client tests 2 passed; Stage04 test send tests 6 passed at the time of Task 9; Stage03 Redis/worker regression tests 12 passed. A later local acceptance audit expanded Stage04 test send coverage to 7 passed with failed Telegram response coverage.
Not done: Staging deployment, migration execution on Tencent Cloud and real allowlisted Telegram test send are pending and require separate confirmation.
Risks / follow-up: Real Telegram send path exists in code now but remains gated by `restricted_test`, server-only allowlist, human confirmation and worker re-check.
Next subphase: 04.5 Staging Rehearsal And Stage Close.
```

```text
Date: 2026-07-06
Subphase: Stage 04 local implementation verification
Status: completed locally
Completed: Ran full backend test suite and whitespace check after Tasks 1-9. Local implementation is ready for staging rehearsal review.
Changed files: test and implementation changes from Tasks 1-9; Stage04 docs updated with evidence.
Tests run: cd backend; pytest tests -q; git diff --check
Test result: `pytest tests -q` reported 154 passed, 17 skipped at the time of initial Tasks 1-9 verification. A later local acceptance audit after adding failed-response worker coverage reported 155 passed, 17 skipped. Skips are online PostgreSQL smoke tests requiring `STAGE02_ONLINE_DATABASE_URL`. `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings.
Not done: Tencent Cloud deployment, server migration, API-created binding verification with real webhook, and real allowlisted Telegram test send.
Risks / follow-up: Real Telegram send code now exists and must only be exercised in staging with `TELEGRAM_SEND_MODE=restricted_test`, server-only allowlist and explicit user confirmation.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 Bitable view row-level safety hardening
Status: completed locally
Completed: Added Stage04 view test proving a customer-scoped sales actor can see its own bound inbox row but cannot see unbound inbox rows, conflict inbox rows or `telegram_send_requests` rows. Updated BDD, test plan, Bitable view module, acceptance checklist and local audit evidence.
Changed files: backend/tests/unit/test_stage04_bitable_views.py; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_BDD.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/modules/STAGE_04_BITABLE_VIEWS.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/README.md; project-docs/README.md.
Tests run: cd backend; pytest tests/unit/test_stage04_bitable_views.py tests/unit/test_bitable_views.py tests/unit/test_stage03_telegram_inbox_view.py -v; cd backend; pytest tests -q.
Test result: Stage04/Stage03/Bitable view focused regression 17 passed; full backend suite 162 passed / 17 skipped.
Not done: No staging deployment, staging migration, real webhook message, or real Telegram test send was executed.
Risks / follow-up: Staging still needs real row evidence for bound inbox, intent queue and send request views after deployment.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 API error-contract and permission evidence hardening
Status: completed locally
Completed: Added tests for unauthorized binding disable, missing binding disable stable error and missing send request confirm stable error. Updated Stage04 API Contract, BDD, SDD, Test Plan, module docs, acceptance checklist and local audit to align with the implemented stable error names and current automated evidence.
Changed files: backend/tests/integration/test_stage04_binding_management.py; backend/tests/integration/test_stage04_test_send.py; project-docs/08-implementation/STAGE_04_API_CONTRACT.md; project-docs/08-implementation/STAGE_04_BDD.md; project-docs/08-implementation/STAGE_04_SDD.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/modules/STAGE_04_BINDING_MANAGEMENT.md; project-docs/08-implementation/modules/STAGE_04_RESTRICTED_TEST_SEND.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/README.md; project-docs/README.md.
Tests run: cd backend; pytest tests/integration/test_stage04_binding_management.py tests/integration/test_stage04_test_send.py -v; cd backend; pytest tests -q; git diff --check; rg Stage04 stale error-code/count scan.
Test result: Focused binding + send tests 20 passed; full backend suite 161 passed / 17 skipped; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings; stale error-code scan found no old `telegram_test_send_not_found` / `telegram_test_send_invalid_state` / `telegram_binding_invalid_scope` references in current Stage04 docs.
Not done: No staging deployment, staging migration, real webhook message, or real Telegram test send was executed.
Risks / follow-up: API validation errors still use FastAPI/Pydantic 422 validation rather than a custom Stage04 error envelope; if a custom 422 error code is desired, it should be discussed as an API contract decision before implementation.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 permission-boundary audit hardening
Status: completed locally
Completed: Added explicit permission check for `GET /telegram/bindings`, plus tests proving unauthorized binding list, test-send request and test-send confirmation are blocked and audited. Updated Stage04 API/security/module docs to match the implemented permission boundary and corrected stale intent placeholder audit naming to `telegram.intent_placeholder.ready`.
Changed files: backend/app/api/routes/telegram_bindings.py; backend/app/services/telegram_binding_management.py; backend/tests/integration/test_stage04_binding_management.py; backend/tests/integration/test_stage04_test_send.py; project-docs/08-implementation/STAGE_04_API_CONTRACT.md; project-docs/08-implementation/STAGE_04_SDD.md; project-docs/08-implementation/STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md; project-docs/08-implementation/modules/STAGE_04_BINDING_MANAGEMENT.md; project-docs/08-implementation/modules/STAGE_04_RESTRICTED_TEST_SEND.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/README.md; project-docs/README.md.
Tests run: cd backend; pytest tests/integration/test_stage04_binding_management.py -v; cd backend; pytest tests/integration/test_stage04_test_send.py -v; cd backend; pytest tests -q; cd backend; alembic upgrade head --sql; git diff --check; rg Stage04 stale implementation and placeholder audit scans.
Test result: Binding management tests 8 passed; Stage04 test send tests 9 passed; full backend suite 158 passed / 17 skipped; Alembic offline SQL reached `20260706_0011` and emitted `COMMIT`; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings; placeholder audit scan found no stale `agent.intent.placeholder_*` references.
Not done: No Tencent Cloud staging operation, staging migration, real webhook binding evidence, or real allowlisted Telegram send was executed.
Risks / follow-up: Task10 staging rehearsal remains the only Stage04 final acceptance blocker, and it still requires separate user confirmation because it changes external staging state and performs one real Telegram test send.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 local acceptance audit
Status: completed locally
Completed: Added Stage04 local acceptance audit and covered the previously untested `telegram_send_requests.status = failed` worker path. The audit maps Stage04 Source Of Truth, implementation plan tasks, Bitable endpoints and Exit Gate items to local evidence, while keeping Task 10 staging explicitly pending.
Changed files: backend/tests/integration/test_stage04_test_send.py; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_PROGRESS.md; project-docs/08-implementation/STAGE_04_MODULE_INDEX.md; project-docs/08-implementation/README.md; project-docs/README.md.
Tests run: cd backend; pytest tests/integration/test_stage04_test_send.py -v; cd backend; pytest tests -q; cd backend; alembic upgrade head --sql; git diff --check; rg Stage04 stale status/count scan.
Test result: Stage04 test send tests 7 passed; full backend suite 155 passed / 17 skipped; Alembic offline SQL reached `20260706_0011` and emitted `COMMIT`; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings; stale-status scan found only historical progress-log mentions, not active current status.
Not done: No Tencent Cloud deployment, staging migration, API-created binding verification with real webhook, or real allowlisted Telegram test send was executed.
Risks / follow-up: Staging remains an external write/change gate and requires separate user confirmation. The 17 online PostgreSQL smoke tests still require `STAGE02_ONLINE_DATABASE_URL`.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-06
Subphase: Stage 04 functional development documentation deepening
Status: completed locally
Completed: Expanded Stage04 complex module docs from summaries into detailed functional development documentation. Added standalone docs for New Message Binding and Bitable Views. Updated Binding Management, Intent Placeholder and Restricted Test Send docs with implemented files, state matrices, API/service/worker paths, permission rules, edge cases, audit contracts, Bitable endpoints, automated evidence and staging gaps. Updated module index and acceptance checklist.
Changed files: project-docs/08-implementation/modules/STAGE_04_BINDING_MANAGEMENT.md; project-docs/08-implementation/modules/STAGE_04_NEW_MESSAGE_BINDING.md; project-docs/08-implementation/modules/STAGE_04_BITABLE_VIEWS.md; project-docs/08-implementation/modules/STAGE_04_INTENT_PLACEHOLDER.md; project-docs/08-implementation/modules/STAGE_04_RESTRICTED_TEST_SEND.md; project-docs/08-implementation/STAGE_04_MODULE_INDEX.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/README.md.
Tests run: rg old Stage04 pending/planned implementation descriptions; rg new module index references; git diff --check.
Test result: No stale `No implementation yet` / `Planned:` / docs-only implementation descriptions remain in Stage04 docs scan. New module docs are indexed by implementation README, module index and acceptance checklist. `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings.
Not done: No staging operation or real Telegram send was executed.
Risks / follow-up: Keep module docs synchronized if code changes during staging fixes.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 restricted test send config/error semantics hardening
Status: completed locally
Completed: Aligned the API, SDD, security and restricted-test-send module docs with the implemented fail-closed runtime behavior: production-like `restricted_test` without Bot token or test-send allowlist is rejected by runtime validation before API/worker traffic, not represented as a send request `blocked` state. Added schema-boundary coverage proving `message_text` over 1000 chars returns FastAPI/Pydantic 422 without creating request, outbox or audit evidence.
Changed files: backend/tests/integration/test_stage04_test_send.py; project-docs/08-implementation/STAGE_04_API_CONTRACT.md; project-docs/08-implementation/STAGE_04_SDD.md; project-docs/08-implementation/STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md; project-docs/08-implementation/modules/STAGE_04_RESTRICTED_TEST_SEND.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: cd backend; pytest tests/integration/test_stage04_test_send.py tests/unit/test_stage04_config.py tests/unit/test_stage04_telegram_bot_client.py -v; cd backend; pytest tests -q; git diff --check; rg Stage04 token-missing stale API/error semantics scan.
Test result: Focused restricted-test-send/config/client tests 18 passed; full backend suite 163 passed / 17 skipped; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings; stale scan found no current `telegram_test_send_token_missing`, `Missing Bot token: blocked`, or request-level token-missing blocked/audit contract in active Stage04 docs.
Not done: No staging deployment, staging migration, server `.env` change, real webhook message, or real Telegram test send was executed.
Risks / follow-up: Task10 staging rehearsal remains pending and still requires separate user confirmation because it changes external staging state and performs one real allowlisted Telegram test send.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 binding customer existence boundary hardening
Status: completed locally
Completed: Added direct automated evidence for the documented rule that `customer_id` must exist before a Telegram binding can be created. The test proves an unknown customer returns the current FastAPI 404 detail response, creates no binding row, writes no binding audit and does not commit the in-memory UOW. Documented that a custom stable error code such as `telegram_binding_customer_not_found` is not part of the confirmed Stage04 API contract and would require separate confirmation before implementation.
Changed files: backend/tests/integration/test_stage04_binding_management.py; project-docs/08-implementation/STAGE_04_API_CONTRACT.md; project-docs/08-implementation/modules/STAGE_04_BINDING_MANAGEMENT.md; project-docs/08-implementation/STAGE_04_BDD.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: cd backend; pytest tests/integration/test_stage04_binding_management.py -v; cd backend; pytest tests -q; git diff --check.
Test result: Binding management tests 11 passed; full backend suite 164 passed / 17 skipped; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings.
Not done: Did not change the API contract to add a new stable `telegram_binding_customer_not_found` error code. Did not run staging, migrate Tencent Cloud DB, or perform any real Telegram send.
Risks / follow-up: If a stable missing-customer error envelope is desired, confirm it as an API contract change before implementation. Task10 staging rehearsal remains pending and requires separate user confirmation.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 restricted test send confirm-boundary hardening
Status: completed locally
Completed: Added direct automated evidence for two documented confirm-stage safety boundaries. `confirm=false` now has a focused test proving the API returns 400 without changing request state, creating outbox, writing audit or committing. Confirm-time allowlist drift now has a focused test proving the request becomes `blocked`, no outbox is created, a safe blocked audit is written and the route returns `telegram_test_send_target_not_allowlisted`.
Changed files: backend/tests/integration/test_stage04_test_send.py; project-docs/08-implementation/modules/STAGE_04_RESTRICTED_TEST_SEND.md; project-docs/08-implementation/STAGE_04_BDD.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: cd backend; pytest tests/integration/test_stage04_test_send.py -v; cd backend; pytest tests -q; git diff --check.
Test result: Stage04 test send tests 13 passed; full backend suite 166 passed / 17 skipped; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings.
Not done: Did not run staging, change server env, call Telegram sendMessage, broaden allowlist policy, or add customer group sending.
Risks / follow-up: Task10 staging rehearsal remains pending and requires separate user confirmation before any staging env change or real allowlisted Telegram test send.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 outbox-to-Redis request-id bridge hardening
Status: completed locally
Completed: Added direct automated evidence that a `telegram.test_send_requested` outbox event with `payload.request_id` is projected into Redis stream fields as `request_id`. This verifies the bridge between confirmed `telegram_send_requests` rows and the worker input contract, rather than only proving the request id exists in PostgreSQL outbox payload.
Changed files: backend/tests/integration/test_stage03_redis_streams_bridge.py; project-docs/08-implementation/modules/STAGE_04_RESTRICTED_TEST_SEND.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: cd backend; pytest tests/integration/test_stage03_redis_streams_bridge.py -v; cd backend; pytest tests -q; git diff --check.
Test result: Stage03 Redis bridge tests 4 passed; full backend suite 167 passed / 17 skipped; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings.
Not done: Did not run Redis against staging, deploy Tencent Cloud services, change server env, or call Telegram sendMessage.
Risks / follow-up: Real staging still needs to prove the Dockerized outbox bridge and worker process the actual Redis stream entry end to end.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 binding inactive and idempotent-disable semantics hardening
Status: completed locally
Completed: Added direct automated evidence for two binding management details already documented in the module design. First, an inactive same-scope/key binding does not block creating a later active binding. Second, disabling an already inactive binding is the current idempotent state-set behavior: the row stays inactive and audit records inactive before/after states.
Changed files: backend/tests/integration/test_stage04_binding_management.py; project-docs/08-implementation/modules/STAGE_04_BINDING_MANAGEMENT.md; project-docs/08-implementation/STAGE_04_BDD.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: cd backend; pytest tests/integration/test_stage04_binding_management.py -v; cd backend; pytest tests -q; git diff --check.
Test result: Binding management tests 13 passed; full backend suite 169 passed / 17 skipped; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings.
Not done: Did not change the API contract for inactive disable behavior, did not add stricter state-machine errors, did not run staging and did not perform any external Telegram operation.
Risks / follow-up: If later product requirements want disabling inactive bindings to return a conflict/no-op status instead of writing audit, that is a binding state-machine contract change and should be confirmed before implementation.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 binding list filter contract hardening
Status: completed locally
Completed: Added direct automated evidence for the documented `GET /telegram/bindings` filter contract. The new tests prove listing can filter by `telegram_chat_id`, `telegram_user_id` and `status`, returns HTTP 200 with `bindings: []` for empty results, does not write audit or commit on successful read-only listing, and rejects invalid `status` values with FastAPI/Pydantic 422 without audit or commit.
Changed files: backend/tests/integration/test_stage04_binding_management.py; project-docs/08-implementation/modules/STAGE_04_BINDING_MANAGEMENT.md; project-docs/08-implementation/STAGE_04_BDD.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md; project-docs/08-implementation/STAGE_04_TEST_PLAN.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: cd backend; pytest tests/integration/test_stage04_binding_management.py -v; cd backend; pytest tests -q; git diff --check.
Test result: Binding management tests 15 passed; full backend suite 171 passed / 17 skipped; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings.
Not done: Did not change the binding list API shape, did not add new filters beyond the confirmed contract, did not run staging, and did not perform any external Telegram operation.
Risks / follow-up: Real staging still needs API-created binding list evidence after deployment/migration.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 documentation status synchronization audit
Status: completed locally
Completed: Synchronized Stage04 specialist document `Current Progress` fields after the local acceptance hardening work. The update aligns API contract, BDD, SDD, database/migration, security/permission, risk, runbook and module docs with the current evidence baseline: Tasks 1-9 local readiness, `pytest tests -q` at 171 passed / 17 skipped, and Task 10 staging rehearsal still pending. Also verified that apparent Chinese mojibake was a PowerShell default-encoding display issue by reading affected files with `Get-Content -Encoding UTF8`.
Changed files: project-docs/08-implementation/STAGE_04_API_CONTRACT.md; project-docs/08-implementation/STAGE_04_BDD.md; project-docs/08-implementation/STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md; project-docs/08-implementation/STAGE_04_OPERATIONS_RUNBOOK.md; project-docs/08-implementation/STAGE_04_RISK_REGISTER.md; project-docs/08-implementation/STAGE_04_SDD.md; project-docs/08-implementation/STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md; project-docs/08-implementation/modules/STAGE_04_BINDING_MANAGEMENT.md; project-docs/08-implementation/modules/STAGE_04_BITABLE_VIEWS.md; project-docs/08-implementation/modules/STAGE_04_INTENT_PLACEHOLDER.md; project-docs/08-implementation/modules/STAGE_04_NEW_MESSAGE_BINDING.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: rg active Stage04 current-progress date scan excluding historical progress log; rg active Stage04 stale placeholder/TBD/mojibake scan excluding historical progress log; git diff --check.
Test result: Active Stage04 docs have no remaining `2026-07-06` current-progress fields outside the historical progress log; no stale placeholder/TBD/mojibake patterns were found in active Stage04 docs; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings.
Not done: Did not change application code, schema, API contract behavior, staging env, Tencent Cloud services, or Telegram send behavior.
Risks / follow-up: Task 10 remains pending and still requires user confirmation before staging migration or real allowlisted Telegram test send.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 restricted-test-send audit wording alignment
Status: completed locally
Completed: Corrected a BDD wording mismatch for non-allowlisted test-send targets. Request-time non-allowlisted targets create a blocked `telegram_send_requests` evidence row and write `telegram.test_send.requested` with `target_allowed=false`; `telegram.test_send.blocked` is reserved for confirm-time allowlist drift and worker-time allowlist re-check after a request already exists. Updated BDD, security and restricted-test-send module wording to match implemented code and focused tests.
Changed files: project-docs/08-implementation/STAGE_04_BDD.md; project-docs/08-implementation/STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md; project-docs/08-implementation/modules/STAGE_04_RESTRICTED_TEST_SEND.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: rg restricted-test-send audit wording consistency scan; rg stale request-time blocked-audit wording scan; cd backend; pytest tests/integration/test_stage04_test_send.py -v; cd backend; pytest tests/integration/test_stage04_binding_management.py -v; git diff --check.
Test result: Wording scan confirms request-time blocked target documents `telegram.test_send.requested` with `target_allowed=false`, while confirm-time and worker-time blocks document `telegram.test_send.blocked`; stale request-time blocked-audit scan had no matches. Stage04 test send tests 13 passed; binding management tests 15 passed; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings.
Not done: Did not change application code, API response shape, audit event creation behavior, staging env, Tencent Cloud services, or Telegram send behavior.
Risks / follow-up: Task 10 still needs real staging evidence for blocked/sent rows if those paths are exercised manually.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 final local preflight before Task 10
Status: completed locally
Completed: Reran the local preflight recommended before entering Task10 staging. Verified the complete backend suite, Alembic offline migration chain, whitespace diff check and token/private-key scan. Updated the local acceptance audit and acceptance checklist with the fresh preflight evidence while keeping Task10 staging explicitly pending.
Changed files: project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: cd backend; pytest tests -q; cd backend; alembic upgrade head --sql; git diff --check; rg token/private-key scan over backend/deploy/project-docs; git status --short.
Test result: Full backend suite 172 passed / 17 skipped; Alembic offline SQL reached `20260706_0011` and emitted `COMMIT`; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warnings; token/private-key scan found no Telegram Bot token, private key or OpenRouter `sk-` key. Broad database URL scan only matched documented local/disposable/example URLs.
Not done: Did not commit, push, modify staging env, deploy Tencent Cloud services, run staging migration, or call Telegram `sendMessage`.
Risks / follow-up: Task10 remains the next external gate and still requires separate user confirmation before staging migration or real allowlisted Telegram test send.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```

```text
Date: 2026-07-07
Subphase: Stage 04 staging compose send-mode gate fix
Status: completed locally
Completed: Fixed the Stage03/04 staging compose configuration so runtime services can actually enter Stage04 `restricted_test` mode from server-side env. `api`, `outbox-bridge` and `worker` now read `${TELEGRAM_SEND_MODE:-dry_run}`; `migrate` intentionally remains `dry_run`. Added a unit test to prevent the deployment file from regressing to hardcoded runtime dry-run for the services that must participate in restricted test send rehearsal.
Changed files: deploy/stage03/compose.yml; backend/tests/unit/test_stage04_deploy_compose.py; project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md; project-docs/08-implementation/STAGE_04_OPERATIONS_RUNBOOK.md; project-docs/08-implementation/STAGE_04_PROGRESS.md.
Tests run: cd backend; pytest tests/unit/test_stage04_deploy_compose.py tests/unit/test_stage04_config.py tests/unit/test_stage03_config.py tests/unit/test_stage03_worker_runtime_factory.py tests/integration/test_stage04_test_send.py -q; git diff --check; rg `TELEGRAM_SEND_MODE:` deploy/stage03/compose.yml.
Test result: 28 passed; compose has three runtime `${TELEGRAM_SEND_MODE:-dry_run}` entries and one migrate `dry_run` entry; `git diff --check` reported no whitespace errors, only Windows LF-to-CRLF warning for `deploy/stage03/compose.yml`.
Not done: Did not deploy, change server env, run migration, or call Telegram `sendMessage` yet.
Risks / follow-up: After amending the Stage04 commit, rerun full preflight before touching Tencent Cloud.
Next subphase: 04.5 Staging Rehearsal And Stage Close after user approval.
```
