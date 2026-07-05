# Stage 02 Progress

## Status

- Document status: active progress log
- Scope: Stage 02 子阶段完成记录、测试记录、风险和后续项
- Current Progress: 2026-07-05 Stage 02 严格审计继续推进；本轮补齐 confirmation/report 写入型 API 的 UOW commit 边界：成功确认草稿和成功生成日报后必须提交 UOW，测试仍可 dependency override。最新验证为全量测试 83 passed、Alembic offline SQL 到 `0009`、AST_OK 92 files。

## 1. Progress Protocol

每个子阶段完成后追加一条记录，格式如下：

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

Older progress records below are point-in-time snapshots. If an older record says Bitable rows are static or database-backed reads are not implemented, the current state table and latest `SQLAlchemy-backed Bitable view data source` record supersede that older risk.

| Subphase | Status | Evidence |
| --- | --- | --- |
| 0.1 Git initialization | completed | `git status --short` now returns tracked state instead of repository error |
| 0.2 Stage 02 documentation package | completed | Source, plan, SDD, BDD, module index, progress log and README are present |
| 1.1 FastAPI Skeleton | completed | `pytest tests/unit/test_health.py -v` passed |
| 1.2 Database Base And Alembic | completed | `pytest tests/unit/test_model_metadata.py -v` passed and Alembic env imports metadata |
| 1.3 Core Models | completed | Core tables registered in metadata; initial migration smoke generated SQL |
| 2.1 Bitable View API | completed | `pytest tests/unit/test_bitable_views.py -v` passed; latest 11 passed and default dependency uses SQLAlchemy-backed data source plus actor record/field permissions |
| 2.2 Permission And Audit | completed | `pytest tests/unit/test_permissions.py tests/unit/test_audit.py -v` passed |
| 2.3 Outbox | completed | `pytest tests/unit/test_outbox.py -v` passed |
| 3.1 Mock Telegram Ingestion | completed | `pytest tests/unit/test_telegram_ingestion.py tests/integration/test_mock_telegram_to_message.py -v` passed |
| 3.2 Mock Router Agent And Draft Creation | completed | `pytest tests/unit/test_mock_router_agent.py -v` passed |
| 4.1 Draft Confirmation And Ticket | completed | `pytest tests/unit/test_service_draft_state_machine.py -v` passed |
| 4.2 Recharge Execution And Readback | completed | `pytest tests/unit/test_recharge_flow.py tests/integration/test_recharge_vertical_slice.py -v` passed |
| 5.1 Inventory Records And Views | completed | `pytest tests/unit/test_account_inventory.py -v` passed; now includes status/customer query and activation tests |
| 5.2 Assignment Confirmation | completed | `pytest tests/integration/test_inventory_assignment_slice.py -v` passed; now includes Agent activation denial |
| 6.1 Metrics And Customer Report | completed | `pytest tests/unit/test_reporting.py -v` passed |
| 6.2 Company Report And Permission | completed | `pytest tests/integration/test_daily_report_slice.py -v` passed |
| 7.1 Stage 02 E2E Critical Path | completed | `pytest tests/integration/test_stage_02_e2e.py -v` passed |
| API write transaction boundaries | completed with offline limitation | `pytest tests/unit/test_service_draft_state_machine.py tests/unit/test_reporting.py -v` passed; confirmation/report successful write routes call UOW commit, online PostgreSQL verification remains environment work |

## 3. Progress Records

```text
Date: 2026-07-04
Subphase: 0.1 Git initialization
Status: completed
Completed: Initialized current workspace as a valid Git repository.
Changed files: .git/ metadata only.
Tests run: git status --short.
Test result: Command returned workspace state instead of "not a git repository".
Not done: No commit was created.
Risks / follow-up: Existing files remain untracked until the user asks for a commit.
Next subphase: 0.2 Stage documentation controls.
```

```text
Date: 2026-07-04
Subphase: 0.2 Stage documentation controls
Status: completed
Completed: Added Stage 02 source, progress, SDD, BDD, module index and implementation index; upgraded the Stage 02 plan into phase/subphase/substep execution manual.
Changed files: project-docs/README.md; project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md; project-docs/08-implementation/README.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SDD.md; project-docs/08-implementation/STAGE_02_BDD.md; project-docs/08-implementation/STAGE_02_MODULE_INDEX.md; project-docs/08-implementation/STAGE_02_PROGRESS.md.
Tests run: rg-based document presence checks; unfinished-marker scan.
Test result: Stage 02 docs are present in README and implementation index; unfinished-marker scan returned no matches.
Not done: Backend code, dependencies, migrations and business tests have not started.
Risks / follow-up: Stage 02 scope must not expand without user confirmation.
Next subphase: 1.1 FastAPI Skeleton.
```

```text
Date: 2026-07-04
Subphase: 1.1 FastAPI Skeleton
Status: completed
Completed: Created backend package, FastAPI create_app(), /health route, local pytest configuration and health test.
Changed files: backend/pyproject.toml; backend/app/main.py; backend/app/core/config.py; backend/app/api/routes/health.py; backend/tests/unit/test_health.py.
Tests run: cd backend; pytest tests/unit/test_health.py -v.
Test result: 1 passed in 0.30s.
Not done: No database connection, business routes, Telegram/provider integration or OpenRouter call.
Risks / follow-up: FastAPI TestClient emits a Starlette deprecation warning in the installed environment, filtered in project pytest config.
Next subphase: 1.2 Database Base And Alembic.
```

```text
Date: 2026-07-04
Subphase: 1.2 Database Base And Alembic
Status: completed
Completed: Added SQLAlchemy DeclarativeBase, timestamp/id mixins, lazy database engine/session factory, Alembic configuration and Alembic env importing Stage 02 metadata.
Changed files: backend/app/core/config.py; backend/app/core/database.py; backend/app/models/base.py; backend/alembic.ini; backend/alembic/env.py; backend/tests/unit/test_model_metadata.py.
Tests run: cd backend; pytest tests/unit/test_model_metadata.py -v.
Test result: 2 passed in 0.55s.
Not done: Did not connect to or mutate a real PostgreSQL database.
Risks / follow-up: Actual online migration still needs a provisioned PostgreSQL database in a later environment step.
Next subphase: 1.3 Core Models.
```

```text
Date: 2026-07-04
Subphase: 1.3 Core Models
Status: completed
Completed: Added users, telegram_identities, customers, customer_groups, messages, ops_audit_events and outbox_events models plus initial Alembic migration.
Changed files: backend/app/models/users.py; backend/app/models/customers.py; backend/app/models/telegram.py; backend/app/models/audit.py; backend/app/models/outbox.py; backend/app/models/__init__.py; backend/alembic/versions/20260704_0001_stage_02_core_tables.py; backend/tests/unit/test_initial_migration.py.
Tests run: cd backend; pytest tests/unit/test_initial_migration.py -v; cd backend; alembic upgrade head --sql; cd backend; pytest tests/unit -v.
Test result: migration test passed; Alembic offline SQL was generated; full unit suite 4 passed in 0.83s.
Not done: Recharge, account inventory, reporting, Bitable view API, permission service, audit service and outbox dispatcher are not implemented yet.
Risks / follow-up: `outbox_events` was defined from Stage 02 SDD/outbox pattern because the older PostgreSQL design doc lists outbox as mandatory but does not yet contain a detailed table section.
Next subphase: 2.1 Bitable View API.
```

```text
Date: 2026-07-04
Subphase: 2.1 Bitable View API
Status: completed
Completed: Added static Stage 02 view registry, view response schema, unknown view error, field masking hook and GET /views/{view_key}/records route.
Changed files: backend/app/main.py; backend/app/core/errors.py; backend/app/api/routes/views.py; backend/app/schemas/views.py; backend/app/services/bitable_views.py; backend/tests/unit/test_bitable_views.py.
Tests run: cd backend; pytest tests/unit/test_bitable_views.py -v; cd backend; pytest tests/unit -v.
Test result: Bitable view tests 3 passed in 0.30s; full unit suite 7 passed in 0.85s.
Not done: Permission service, audit write helper, database-backed view records and outbox dispatcher are not implemented yet.
Risks / follow-up: Current view API returns empty records from static registry only; database-backed records belong to later Phase 2/vertical slices.
Next subphase: 2.2 Permission And Audit.
```

```text
Date: 2026-07-04
Subphase: 2.2 Permission And Audit
Status: completed
Completed: Added Stage 02 Actor object, role/action permission checks, customer_id record scope, sensitive field masking, audit helper and API dependency placeholder for system actor.
Changed files: backend/app/services/permissions.py; backend/app/services/audit.py; backend/app/api/deps.py; backend/tests/unit/test_permissions.py; backend/tests/unit/test_audit.py.
Tests run: cd backend; pytest tests/unit/test_permissions.py tests/unit/test_audit.py -v.
Test result: 5 passed in 0.45s.
Not done: Real login/session identity, tenant_id, database-backed scope lookup and full route-level enforcement are not implemented yet.
Risks / follow-up: Current policy is static role-based configuration; later stages must connect it to persisted users and view/query paths.
Next subphase: 2.3 Outbox.
```

```text
Date: 2026-07-04
Subphase: 2.3 Outbox
Status: completed
Completed: Added outbox enqueue service, in-memory repository, handler interface and dispatcher with success, retry and dead_letter handling plus dead-letter audit.
Changed files: backend/app/services/outbox.py; backend/app/repositories/outbox.py; backend/app/workers/handlers.py; backend/app/workers/outbox_dispatcher.py; backend/tests/unit/test_outbox.py.
Tests run: cd backend; pytest tests/unit/test_outbox.py -v; cd backend; pytest tests/unit -v.
Test result: Outbox tests 3 passed in 0.46s; full unit suite 15 passed in 0.78s.
Not done: SQLAlchemy repository queries, Redis Streams integration and business-specific handlers are not implemented yet.
Risks / follow-up: Dispatcher uses in-memory repository for Stage 02 unit semantics; Phase 3 must wire business message ingestion to database transaction + outbox event creation.
Next subphase: 3.1 Mock Telegram Ingestion.
```

```text
Date: 2026-07-04
Subphase: 3.1 Mock Telegram Ingestion
Status: completed
Completed: Added mock Telegram update schema, ingestion service, in-memory and SQLAlchemy unit-of-work boundaries, customer group lookup, idempotent duplicate update handling, agent.intent_extract outbox enqueue and POST /mock/telegram/updates route.
Changed files: backend/app/main.py; backend/app/schemas/telegram.py; backend/app/services/telegram_ingestion.py; backend/app/api/routes/mock_telegram.py; backend/tests/unit/test_telegram_ingestion.py; backend/tests/integration/test_mock_telegram_to_message.py.
Tests run: cd backend; pytest tests/unit/test_telegram_ingestion.py -v; cd backend; pytest tests/integration/test_mock_telegram_to_message.py -v; cd backend; pytest tests -v.
Test result: Telegram ingestion unit tests 2 passed in 0.47s; mock Telegram API integration test 1 passed in 0.80s; full suite 18 passed in 0.90s.
Not done: Mock router agent, service_drafts creation, real Telegram webhook, OpenRouter, confirmation and provider execution are not implemented.
Risks / follow-up: Integration test uses dependency-overridden in-memory unit of work; online PostgreSQL transaction verification remains for a later environment step.
Next subphase: 3.2 Mock Router Agent And Draft Creation.
```

```text
Date: 2026-07-04
Subphase: 3.2 Mock Router Agent And Draft Creation
Status: completed
Completed: Added service_drafts model and migration, deterministic mock router output schema, recharge keyword/regex router, service draft unit of work, service draft creation service, agent.intent_extract handler, and BDD integration path from mock Telegram message to draft.
Changed files: backend/app/models/service_drafts.py; backend/app/models/__init__.py; backend/alembic/versions/20260704_0002_service_drafts.py; backend/app/agents/interfaces.py; backend/app/agents/mock_router.py; backend/app/services/service_drafts.py; backend/app/services/telegram_ingestion.py; backend/app/workers/handlers.py; backend/tests/unit/test_mock_router_agent.py; backend/tests/unit/test_model_metadata.py; backend/tests/unit/test_initial_migration.py; backend/tests/integration/test_mock_telegram_to_message.py.
Tests run: cd backend; pytest tests/unit/test_mock_router_agent.py -v; cd backend; pytest tests/unit/test_model_metadata.py tests/unit/test_initial_migration.py -v; cd backend; pytest tests/unit/test_telegram_ingestion.py tests/unit/test_mock_router_agent.py tests/integration/test_mock_telegram_to_message.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql.
Test result: Mock router test 1 passed; metadata/migration tests 4 passed; Phase 3 tests 5 passed; full suite 21 passed in 0.85s; Alembic offline SQL includes 0001 and 0002 migrations.
Not done: Human confirmation, service_records, execution_tickets, recharge records, real OpenRouter and real provider execution are not implemented.
Risks / follow-up: Bitable view API still returns static empty records; database-backed view queries must be added before Stage 02 final acceptance.
Next subphase: 4.1 Draft Confirmation And Ticket.
```

```text
Date: 2026-07-04
Subphase: 4.1 Draft Confirmation And Ticket
Status: completed
Completed: Added service_records, execution_tickets and execution_logs models, draft confirmation service, human confirmation state transition, agent confirmation block, execution ticket issuance and single-use ticket state guard.
Changed files: backend/app/models/service.py; backend/app/models/__init__.py; backend/app/services/confirmation.py; backend/app/services/execution_tickets.py; backend/alembic/versions/20260704_0003_recharge_flow.py; backend/tests/unit/test_service_draft_state_machine.py; backend/tests/unit/test_model_metadata.py; backend/tests/unit/test_initial_migration.py.
Tests run: cd backend; pytest tests/unit/test_service_draft_state_machine.py -v.
Test result: 3 passed in 1.07s.
Not done: No real external execution, no real provider, no production database migration was run.
Risks / follow-up: Confirmation route API is not exposed yet; current coverage is service-level state machine.
Next subphase: 4.2 Recharge Execution And Readback.
```

```text
Date: 2026-07-04
Subphase: 4.2 Recharge Execution And Readback
Status: completed
Completed: Added recharge_records, collection_records, mock provider adapter, collection confirmation that does not imply recharge success, mock recharge execution, execution log writing, readback.balance outbox enqueue, readback failure state and recharge vertical slice integration test.
Changed files: backend/app/models/recharge.py; backend/app/adapters/providers_mock.py; backend/app/services/recharge.py; backend/app/workers/handlers.py; backend/alembic/versions/20260704_0003_recharge_flow.py; backend/tests/unit/test_recharge_flow.py; backend/tests/integration/test_recharge_vertical_slice.py.
Tests run: cd backend; pytest tests/unit/test_recharge_flow.py -v; cd backend; pytest tests/integration/test_recharge_vertical_slice.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql.
Test result: Recharge unit tests 5 passed; recharge integration test 1 passed; full suite 31 passed in 1.41s; Alembic offline SQL includes migrations 0001, 0002 and 0003.
Not done: No real Meta/provider call, no raw payment credential handling, no database-backed API route for recharge execution, and Bitable view still needs database-backed rows.
Risks / follow-up: Current recharge vertical slice is in-memory service/integration coverage; online PostgreSQL transaction verification remains for a later environment step.
Next subphase: 5.1 Inventory Records And Views.
```

```text
Date: 2026-07-04
Subphase: 5.1 Inventory Records And Views
Status: completed
Completed: Added account inventory, account assets, account status events models, inventory account creation service, produced status event, unused account query and GET /inventory/accounts route.
Changed files: backend/app/models/accounts.py; backend/app/models/__init__.py; backend/app/services/account_inventory.py; backend/app/api/routes/inventory.py; backend/app/main.py; backend/alembic/versions/20260704_0004_account_inventory.py; backend/tests/unit/test_account_inventory.py; backend/tests/unit/test_model_metadata.py; backend/tests/unit/test_initial_migration.py.
Tests run: cd backend; pytest tests/unit/test_account_inventory.py -v.
Test result: 2 passed in 0.97s.
Not done: No real Meta account readback, no online PostgreSQL query verification, and Bitable view API remains static for some views.
Risks / follow-up: GET /inventory/accounts uses dependency-overridable unit of work; SQLAlchemy repository wiring remains for later hardening.
Next subphase: 5.2 Assignment Confirmation.
```

```text
Date: 2026-07-04
Subphase: 5.2 Assignment Confirmation
Status: completed
Completed: Added account assignment proposal, human confirmation gate, agent confirmation denial, allocated inventory transition and assigned status event.
Changed files: backend/app/services/account_inventory.py; backend/app/models/accounts.py; backend/app/services/permissions.py; backend/tests/integration/test_inventory_assignment_slice.py.
Tests run: cd backend; pytest tests/integration/test_inventory_assignment_slice.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql.
Test result: Assignment integration tests 2 passed in 0.54s; full suite 36 passed in 1.12s; Alembic offline SQL includes migration 0004.
Not done: No automatic allocation, no real Meta integration, no account activation/readback.
Risks / follow-up: Confirmed assignments currently update in-memory objects; online transactional verification remains for later environment setup.
Next subphase: 6.1 Metrics And Customer Report.
```

```text
Date: 2026-07-04
Subphase: 6.1 Metrics And Customer Report
Status: completed
Completed: Added account daily metrics, risk events, customer daily reports, report schema/route, deterministic reporting agent wrapper, customer report generation, source/freshness payloads, explicit stale_data preservation and report view fields.
Changed files: backend/app/models/reporting.py; backend/app/models/__init__.py; backend/app/services/reporting.py; backend/app/schemas/reports.py; backend/app/api/routes/reports.py; backend/app/agents/mock_reporting.py; backend/app/services/bitable_views.py; backend/app/main.py; backend/alembic/versions/20260704_0005_reporting.py; backend/tests/unit/test_reporting.py; backend/tests/unit/test_model_metadata.py; backend/tests/unit/test_initial_migration.py.
Tests run: cd backend; pytest tests/unit/test_reporting.py -v; cd backend; pytest tests/unit/test_model_metadata.py tests/unit/test_initial_migration.py -v; cd backend; pytest tests/unit/test_bitable_views.py -v.
Test result: reporting unit tests 3 passed; metadata/migration tests 7 passed; Bitable view tests 3 passed.
Not done: No real Telegram delivery, no OpenRouter call, no SQLAlchemy online repository for report routes, and no automatic report send.
Risks / follow-up: Customer report currently uses account_daily_metrics and generated risk events; recharge-record and card-binding joins remain follow-up because Stage 02 does not yet have date-aligned card binding facts.
Next subphase: 6.2 Company Report And Permission.
```

```text
Date: 2026-07-04
Subphase: 6.2 Company Report And Permission
Status: completed
Completed: Added company daily report aggregation across customers, manager/admin company report permission action, sales denial path and permission-denied audit event.
Changed files: backend/app/services/reporting.py; backend/app/api/routes/reports.py; backend/app/services/permissions.py; backend/tests/integration/test_daily_report_slice.py.
Tests run: cd backend; pytest tests/integration/test_daily_report_slice.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: daily report integration test 1 passed; full suite 40 passed in 1.01s; Alembic offline SQL includes migration 0005; AST check returned AST_OK 75 files.
Not done: Stage 02 E2E acceptance test and acceptance checklist are not yet implemented.
Risks / follow-up: Report generation remains in-memory service coverage; online PostgreSQL transaction verification remains for a later environment step.
Next subphase: 7.1 Stage 02 E2E Critical Path.
```

```text
Date: 2026-07-04
Subphase: 7.1 Stage 02 E2E Critical Path
Status: completed
Completed: Added Stage 02 E2E critical path from mock Telegram recharge message to service draft, human confirmation, execution ticket, mock recharge execution, readback failure, account inventory assignment, customer report and company report; added Stage 02 acceptance checklist.
Changed files: backend/tests/integration/test_stage_02_e2e.py; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_PROGRESS.md.
Tests run: cd backend; pytest tests/integration/test_stage_02_e2e.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: E2E critical path 1 passed in 0.76s; full suite 42 passed in 1.04s; Alembic offline SQL includes migrations 0001 through 0005; AST check returned AST_OK 77 files.
Not done: No real Telegram/provider/OpenRouter writes; no online PostgreSQL migration run; Bitable view rows are still static/view-shaped rather than full database-backed projections.
Risks / follow-up: Next stage must decide whether to harden SQLAlchemy repositories and database-backed Bitable views before integrating real external providers.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit; do not mark the goal complete until every explicit requirement is proven.
```

```text
Date: 2026-07-04
Subphase: Strict Stage 02 audit hardening
Status: completed
Completed: Added Task 12 LLM client interface, fake structured LLM, OpenRouter-compatible adapter with injected HTTP client, agent_runs model and migration; added Bitable configuration tables and view-shaped business-row projection; expanded router intent coverage for account inventory/report/needs_review; added service draft list API; added reject/request_more_info/escalate confirmation actions and confirmations route.
Changed files: backend/app/agents/interfaces.py; backend/app/agents/mock_router.py; backend/app/adapters/llm_fake.py; backend/app/adapters/llm_openrouter.py; backend/app/models/agent.py; backend/app/models/bitable.py; backend/app/models/__init__.py; backend/app/services/agent_runs.py; backend/app/services/bitable_views.py; backend/app/services/confirmation.py; backend/app/services/permissions.py; backend/app/services/service_drafts.py; backend/app/api/routes/views.py; backend/app/api/routes/service_drafts.py; backend/app/api/routes/confirmations.py; backend/app/schemas/service_drafts.py; backend/app/core/config.py; backend/app/main.py; backend/alembic/versions/20260704_0006_agent_runs.py; backend/alembic/versions/20260704_0007_bitable_config.py; backend/tests/unit/test_llm_adapters.py; backend/tests/unit/test_bitable_views.py; backend/tests/unit/test_mock_router_agent.py; backend/tests/unit/test_service_draft_state_machine.py; backend/tests/unit/test_service_drafts_api.py; backend/tests/unit/test_model_metadata.py; backend/tests/unit/test_initial_migration.py.
Tests run: cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: full suite 57 passed in 1.28s; Alembic offline SQL includes migrations 0001 through 0007; AST check returned AST_OK 89 files.
Not done: Online PostgreSQL transaction verification is still not run; real Telegram/provider/OpenRouter calls remain excluded; remaining Stage 02 plan/SDD/BDD items still need explicit audit before goal completion.
Risks / follow-up: Bitable projection now returns injected business rows but still needs SQLAlchemy-backed repositories for production-like reads.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit.
```

```text
Date: 2026-07-04
Subphase: Outbox schema alignment
Status: completed
Completed: Added Stage 02 plan fields to outbox_events: aggregate_type, aggregate_id, attempt_count, available_at, processed_at and last_error; enqueue_outbox_event accepts aggregate references; dispatcher syncs attempt_count, available_at, processed_at and last_error.
Changed files: backend/app/models/outbox.py; backend/app/services/outbox.py; backend/app/workers/outbox_dispatcher.py; backend/alembic/versions/20260704_0008_outbox_schema_alignment.py; backend/tests/unit/test_outbox.py; backend/tests/unit/test_initial_migration.py; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_PROGRESS.md; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: full suite 58 passed in 1.31s; Alembic offline SQL includes migrations 0001 through 0008; AST check returned AST_OK 90 files.
Not done: Online PostgreSQL transaction verification is still not run.
Risks / follow-up: Existing dispatcher remains in-process Stage 02 semantics; Redis Streams production worker remains out of scope.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit.
```

```text
Date: 2026-07-04
Subphase: Inventory status query and activation
Status: completed
Completed: Added account inventory status/customer query, authorized `allocated -> activated` transition, activated status event, Agent activation denial, inventory API assignment/status fields, and `account_inventory` Bitable-shaped view projection for assigned customer/current status.
Changed files: backend/app/services/account_inventory.py; backend/app/api/routes/inventory.py; backend/app/services/permissions.py; backend/app/services/bitable_views.py; backend/tests/unit/test_account_inventory.py; backend/tests/unit/test_bitable_views.py; backend/tests/integration/test_inventory_assignment_slice.py; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_BDD.md; project-docs/08-implementation/STAGE_02_SDD.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_PROGRESS.md; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/unit/test_account_inventory.py tests/unit/test_bitable_views.py tests/integration/test_inventory_assignment_slice.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: focused inventory/Bitable/assignment tests 14 passed in 0.98s; full suite 63 passed in 1.37s; Alembic offline SQL includes migrations 0001 through 0008; AST check returned AST_OK 90 files.
Not done: No real Meta account readback, no online PostgreSQL transaction verification, no SQLAlchemy-backed production repository for Bitable inventory rows.
Risks / follow-up: Inventory activation is an internal status transition only; later real-provider stages must map Meta/card-platform evidence into the same status event model after explicit confirmation.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit.
```

```text
Date: 2026-07-04
Subphase: Recharge audit hardening
Status: completed
Completed: Added audit events for recharge record creation, collection record creation, collection confirmation and mock recharge execution success; existing readback failure audit remains covered. Tests now assert that finance collection confirmation is not execution success and still writes audit evidence.
Changed files: backend/app/services/recharge.py; backend/tests/unit/test_recharge_flow.py; project-docs/08-implementation/STAGE_02_SDD.md; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_PROGRESS.md; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md.
Tests run: cd backend; pytest tests/unit/test_recharge_flow.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: recharge unit tests 5 passed in 0.58s; full suite 63 passed in 1.41s; Alembic offline SQL includes migrations 0001 through 0008; AST check returned AST_OK 90 files.
Not done: No real provider audit evidence and no online PostgreSQL transaction verification; those remain out of Stage 02 mock/sandbox scope or later environment verification.
Risks / follow-up: A full audit coverage matrix across every write service should be added before marking the broad Task 4 audit acceptance as complete.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit.
```

```text
Date: 2026-07-05
Subphase: Audit coverage and reporting recharge facts
Status: completed
Completed: Added audit events for Telegram message ingestion, inventory account creation/assignment/activation, customer report generation, company report generation and risk event creation; extended customer reports with same-day same-customer recharge records; extended company reports with same-day recharge amount/status summary; made missing card binding facts explicit with `card_binding_state.status = not_available_in_stage_02`.
Changed files: backend/app/services/telegram_ingestion.py; backend/app/services/account_inventory.py; backend/app/services/reporting.py; backend/tests/unit/test_telegram_ingestion.py; backend/tests/unit/test_account_inventory.py; backend/tests/integration/test_inventory_assignment_slice.py; backend/tests/unit/test_reporting.py; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SDD.md; project-docs/08-implementation/STAGE_02_BDD.md; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_PROGRESS.md.
Tests run: cd backend; pytest tests/unit/test_telegram_ingestion.py -v; cd backend; pytest tests/unit/test_reporting.py -v; cd backend; pytest tests/unit/test_account_inventory.py tests/integration/test_inventory_assignment_slice.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: telegram ingestion tests 2 passed; reporting tests 6 passed; inventory tests 8 passed; full suite 66 passed in 2.85s; Alembic offline SQL includes migrations 0001 through 0008; AST check returned AST_OK 90 files.
Not done: Real card binding state remains unavailable because Stage 02 does not yet implement `account_card_bindings`; online PostgreSQL transaction verification is still not run.
Risks / follow-up: A future card-binding slice must add `payment_profiles`/`account_card_bindings` facts before reports can include actual binding success/failure without fabrication.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit.
```

```text
Date: 2026-07-05
Subphase: Card binding facts and reporting integration
Status: completed
Completed: Added tokenized payment profile and account card binding fact models, Alembic migration 0009, metadata/migration coverage, customer report card binding records with masked failure reason, company report card binding status summary, and Bitable-shaped `payment_profiles` / `account_card_bindings` views with sensitive field masking.
Changed files: backend/app/models/cards.py; backend/app/models/__init__.py; backend/alembic/versions/20260705_0009_card_binding_facts.py; backend/app/services/reporting.py; backend/app/services/bitable_views.py; backend/tests/unit/test_model_metadata.py; backend/tests/unit/test_initial_migration.py; backend/tests/unit/test_reporting.py; backend/tests/unit/test_bitable_views.py; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SDD.md; project-docs/08-implementation/STAGE_02_BDD.md; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_PROGRESS.md.
Tests run: cd backend; pytest tests/unit/test_model_metadata.py tests/unit/test_initial_migration.py -v; cd backend; pytest tests/unit/test_reporting.py -v; cd backend; pytest tests/unit/test_bitable_views.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: metadata/migration tests 11 passed; reporting tests 8 passed; Bitable view tests 7 passed; full suite 70 passed in 3.24s; Alembic offline SQL includes migrations 0001 through 0009; AST check returned AST_OK 92 files.
Not done: No real external card binding execution; Stage 02 only stores tokenized/masked card binding facts and mock/reporting evidence.
Risks / follow-up: Later provider integration must map real Meta/card-platform binding execution into `account_card_bindings`, `execution_logs`, `ops_audit_events`, and `account_status_events`.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit.
```

```text
Date: 2026-07-05
Subphase: SQLAlchemy-backed Bitable view data source
Status: completed
Completed: Added `SqlAlchemyBitableViewDataSource` that reads registered SQLAlchemy metadata tables, converts rows into Bitable-shaped records, returns empty records for unknown physical tables, and wired the default `/views` dependency to the SQLAlchemy session while keeping test dependency overrides.
Changed files: backend/app/services/bitable_views.py; backend/app/api/routes/views.py; backend/tests/unit/test_bitable_views.py; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_02_PROGRESS.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SDD.md; project-docs/08-implementation/STAGE_02_BDD.md.
Tests run: cd backend; pytest tests/unit/test_bitable_views.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: Bitable view tests 10 passed; full suite 73 passed in 3.74s; Alembic offline SQL includes migrations 0001 through 0009; AST check returned AST_OK 92 files.
Not done: No online PostgreSQL query was executed; `/views` has SQLAlchemy-backed code and offline session-double coverage, but real database connectivity remains an environment verification item.
Risks / follow-up: Later hardening should add online PostgreSQL fixtures or a disposable database test before real provider integrations depend on live view reads.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit.
```

```text
Date: 2026-07-05
Subphase: Bitable view actor permissions
Status: completed
Completed: Wired `/views` route actor context into Bitable view response building; filtered records by actor customer scope using `customer_id` / `assigned_customer_id`; applied role-based field permission masking on top of view-defined sensitive fields, so sales can only see scoped customer records and cannot see `amount`; aligned `recharge_view` with real `recharge_records` status columns: `collection_status`, `execution_status`, `readback_status`.
Changed files: backend/app/services/bitable_views.py; backend/app/api/routes/views.py; backend/tests/unit/test_bitable_views.py; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SDD.md; project-docs/08-implementation/STAGE_02_BDD.md; project-docs/08-implementation/STAGE_02_PROGRESS.md.
Tests run: cd backend; pytest tests/unit/test_bitable_views.py::test_view_api_applies_actor_record_scope_and_field_permissions -v; cd backend; pytest tests/unit/test_bitable_views.py -v; cd backend; pytest tests -v.
Test result: New Bitable permission/status test failed first because unscoped records, raw amount and missing recharge status fields were visible; after implementation, focused test passed, Bitable view tests 11 passed, full suite 74 passed in 3.23s.
Not done: No online PostgreSQL query was executed; permission behavior is proven through route-level dependency override and in-memory data source, while SQLAlchemy-backed row reads remain covered by session-double tests.
Risks / follow-up: Later online database verification should prove the same actor filtering over real PostgreSQL rows before exposing views to real operators.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit.
```

```text
Date: 2026-07-05
Subphase: SQLAlchemy-backed API unit-of-work defaults
Status: completed
Completed: Wired service draft list, inventory accounts, confirmation actions, and reports API dependencies to SQLAlchemy-backed UOWs by default while preserving dependency overrides for in-memory tests. Added SQLAlchemy UOWs for account inventory, confirmation, and reporting; service draft route now uses its existing SQLAlchemy UOW.
Changed files: backend/app/api/routes/service_drafts.py; backend/app/api/routes/inventory.py; backend/app/api/routes/confirmations.py; backend/app/api/routes/reports.py; backend/app/services/account_inventory.py; backend/app/services/confirmation.py; backend/app/services/reporting.py; backend/tests/unit/test_service_drafts_api.py; backend/tests/unit/test_account_inventory.py; backend/tests/unit/test_service_draft_state_machine.py; backend/tests/unit/test_reporting.py; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SDD.md; project-docs/08-implementation/STAGE_02_BDD.md; project-docs/08-implementation/STAGE_02_PROGRESS.md.
Tests run: cd backend; pytest tests/unit/test_service_drafts_api.py -v; cd backend; pytest tests/unit/test_account_inventory.py tests/integration/test_inventory_assignment_slice.py -v; cd backend; pytest tests/unit/test_service_draft_state_machine.py tests/integration/test_recharge_vertical_slice.py -v; cd backend; pytest tests/unit/test_reporting.py tests/integration/test_daily_report_slice.py -v; cd backend; pytest tests -v.
Test result: New dependency/UOW tests failed first because routes or services still used in-memory/default-missing SQLAlchemy UOWs; after implementation, service draft tests 2 passed, inventory focused tests 10 passed, confirmation focused tests 10 passed, reporting focused tests 11 passed, and full suite 81 passed in 3.00s.
Not done: No real PostgreSQL online transaction was executed; SQLAlchemy UOW behavior is proven with session doubles and existing offline Alembic SQL.
Risks / follow-up: Later environment verification should run online Alembic upgrade and API smoke tests against a disposable PostgreSQL database.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit.
```

```text
Date: 2026-07-05
Subphase: API write UOW commit boundaries
Status: completed with offline limitation
Completed: Added explicit UOW commit contract for confirmation and reporting write paths. Confirmation API now commits after successful confirm/reject/request_more_info/escalate actions. Reports API now commits after successful customer/company report generation. Added route-level tests proving successful confirmation and customer report generation call commit; tests failed first because the in-memory UOWs had no committed state, then passed after adding commit to in-memory and SQLAlchemy UOWs and calling it from routes.
Changed files: backend/app/services/confirmation.py; backend/app/api/routes/confirmations.py; backend/app/services/reporting.py; backend/app/api/routes/reports.py; backend/tests/unit/test_service_draft_state_machine.py; backend/tests/unit/test_reporting.py; project-docs/08-implementation/STAGE_02_ACCEPTANCE_CHECKLIST.md; project-docs/08-implementation/STAGE_02_SOURCE_OF_TRUTH.md; project-docs/08-implementation/STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md; project-docs/08-implementation/STAGE_02_SDD.md; project-docs/08-implementation/STAGE_02_BDD.md; project-docs/08-implementation/STAGE_02_PROGRESS.md.
Tests run: cd backend; pytest tests/unit/test_service_draft_state_machine.py::test_confirmation_api_commits_successful_action tests/unit/test_reporting.py::test_customer_report_api_commits_generated_report -v; cd backend; pytest tests/unit/test_service_draft_state_machine.py tests/unit/test_reporting.py -v; cd backend; pytest tests -v; cd backend; alembic upgrade head --sql; cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')".
Test result: New route-level commit tests failed first with missing `committed` state; after implementation, the two focused tests passed, confirmation/reporting focused tests 21 passed, full suite 83 passed in 1.67s, Alembic offline SQL includes migrations 0001 through 0009, and AST check returned AST_OK 92 files.
Not done: No online PostgreSQL transaction was executed; this proves route/UOW commit behavior with in-memory UOWs and session doubles, not a real database commit against a provisioned PostgreSQL instance.
Risks / follow-up: Later environment verification should run these write APIs against a disposable PostgreSQL database and assert persisted rows after request completion.
Next subphase: Continue strict Stage 02 plan/SDD/BDD audit; likely next hardening is online database smoke setup or remaining API transaction boundaries for service drafts/inventory if write endpoints expand.
```
