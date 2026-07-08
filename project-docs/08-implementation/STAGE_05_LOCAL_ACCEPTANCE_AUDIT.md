# Stage 05 Local Acceptance Audit

## Status

- Document status: local acceptance audit draft
- Scope: Local verification evidence for Stage05 before Tencent Cloud staging rehearsal.
- Current Progress: 2026-07-08 Local acceptance audit remains the local/non-staging evidence artifact; Stage05 final acceptance is now supplemented by Tencent Cloud staging evidence in `STAGE_05_FINAL_ACCEPTANCE_REPORT.md`, `STAGE_05_ACCEPTANCE_CHECKLIST.md`, `STAGE_05_REQUIREMENT_TRACEABILITY_AUDIT.md` and `STAGE_05_PROGRESS.md`. Local evidence remains valid; staging evidence, additional real Telegram cases and safety close are no longer pending.

## 1. Purpose

This file records local verification evidence before Stage05 touches Tencent Cloud staging, real OpenRouter or real Telegram send. It must be updated after implementation and before staging rehearsal.

## 2. Required Local Evidence

| Evidence | Status | Result |
| --- | --- | --- |
| Stage05 focused tests | completed locally through redacted runtime summary pass | `pytest tests -k stage05 -v`: 82 selected passed / 190 deselected |
| Stage05 focused integration tests | completed locally through Task12 local preflight | `pytest tests -k stage05 -v`: workflow, confirmation, customer reply send, staging contract, worker and view scenarios passed |
| Stage03/Stage04 regression tests | completed locally | `pytest tests\integration\test_stage03_customer_binding.py tests\integration\test_stage03_worker_runtime.py tests\integration\test_stage04_intent_placeholder.py tests\integration\test_stage04_test_send.py tests\unit\test_stage04_bitable_views.py tests\unit\test_stage04_config.py -v`: 33 passed |
| Full backend suite | completed locally through redacted runtime summary pass | `pytest tests -q`: 255 passed / 17 skipped |
| LangGraph dependency import | completed locally | `python -c "import langgraph; from langgraph.graph import StateGraph; print('langgraph-import-ok', StateGraph.__name__)"`: `langgraph-import-ok StateGraph` |
| Alembic offline SQL | completed locally | reaches `20260707_0016` |
| Secret scan | completed locally | config names, placeholders, documented scan patterns and fake test values only |
| Documentation consistency scan | completed locally | current-state wording and traceability scan passed for local acceptance and final report docs |
| Staging env contract preflight | completed locally | `pytest tests\integration\test_stage05_staging_contract.py -v`: 5 passed |
| Requirement traceability audit | completed locally | `STAGE_05_REQUIREMENT_TRACEABILITY_AUDIT.md` maps local evidence, guarded out-of-scope items and pending staging exit gates |
| Stage05 out-of-scope runtime guard | completed locally | `pytest tests\unit\test_stage05_scope_guards.py -v`: 4 passed |
| Final report local out-of-scope confirmation | completed locally | `STAGE_05_FINAL_ACCEPTANCE_REPORT.md` records local non-occurrence evidence and staging follow-ups for out-of-scope items |
| Risk register local mitigation evidence | completed locally | `STAGE_05_RISK_REGISTER.md` records local mitigation evidence and remaining staging risk for R05-01 through R05-14 |
| Task12 evidence ledger template | completed locally | `STAGE_05_OPERATIONS_RUNBOOK.md` Section 7 defines redacted evidence fields, pass conditions and failure actions for staging rehearsal |
| Task12 pre-staging approval packet | completed locally | `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` defines exact approval boundary, still-forbidden actions, required pre-approval evidence, execution order and abort conditions |
| Task12 pre-approval evidence snapshot | completed locally | `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` records current local results: Stage05 focused 82 passed, scope guard 4 passed, staging contract 5 passed, deployment config gate 2 passed, redacted runtime summary 3 passed, full backend suite 255 passed / 17 skipped, Alembic offline SQL reaches `20260707_0016`, strict secret scan has no high-risk matches, and `git diff --check` has no whitespace errors |
| Stage05 code readiness audit | completed locally | Python AST compile over Stage05 runtime-relevant app paths returned `compiled=50` and `stage05-runtime-ast-ok`; key Stage05 module imports returned `stage05-imports-ok`; TODO/NotImplemented scan had no matches; direct provider/network scan had no action-import matches and only found the intentional sensitive-card-data rejection pattern |
| Stage05 API/OpenAPI readiness audit | completed locally | FastAPI `create_app().openapi()` generated 13 paths from 18 routes and included `/service-drafts`, `/confirmations/service-drafts/{draft_id}/actions`, `/telegram/send-requests/{request_id}/confirm` and `/views/{view_key}/records` |
| Task12 staging command/evidence map | completed locally | `STAGE_05_OPERATIONS_RUNBOOK.md` Section 4 maps Stage04/Tencent Cloud staging reuse, Stage05 runtime delta gate, command categories, API evidence request shapes, operator query boundary and safety-close evidence. It requires container-level redacted runtime proof before any real OpenRouter call. |
| Stage05 deployment config gate | completed locally | `pytest tests\unit\test_stage05_deploy_compose.py -v`: RED failed against the old compose/env shape; GREEN passed 2/2 after compose/env updates. Runtime services now keep safe defaults but accept approved real OpenRouter env; `migrate` remains LLM-off/fake and provider disabled. Stage04 compose regression `pytest tests\unit\test_stage04_deploy_compose.py -v` also passed 1/1. |
| Redacted runtime summary command | completed locally | `pytest tests\unit\test_stage05_runtime_summary.py -v`: RED failed because `app.core.runtime_summary` did not exist; GREEN passed 3/3 after adding `python -m app.core.runtime_summary`, which prints only booleans/presence/validation and omits secrets, allowlists, webhook secret and database URL |

## 3. Commands To Record

```text
cd backend
pytest tests/unit/test_stage05_config.py tests/unit/test_stage05_router_schema.py tests/unit/test_stage05_child_agents.py tests/unit/test_stage05_account_inventory_agent.py tests/unit/test_stage05_bitable_views.py -v
pytest tests/unit/test_stage05_scope_guards.py -v
pytest tests/integration/test_stage05_agent_workflow.py tests/integration/test_stage05_service_draft_confirmation.py tests/integration/test_stage05_customer_reply_send.py tests/integration/test_stage05_worker_runtime.py -v
pytest tests/integration/test_stage05_staging_contract.py -v
pytest tests -q
python -c "import langgraph; from langgraph.graph import StateGraph; print('langgraph-import-ok', StateGraph.__name__)"
python -m app.core.runtime_summary
alembic upgrade head --sql
```

Secret scan:

```text
rg -n "sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_BOT_TOKEN|OPENROUTER_API_KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
```

## 4. Local Acceptance Result

Local/non-staging acceptance is passed for the implemented Stage05 scope through Task12 local staging-contract preflight, requirement traceability audit, out-of-scope runtime guard, final-report local out-of-scope confirmation and risk-register mitigation summary.

Skipped tests:

- 17 online PostgreSQL smoke tests were skipped because `STAGE02_ONLINE_DATABASE_URL` is not configured.

External calls:

- No real OpenRouter call was made.
- No real Telegram API call was made.
- No provider call, funds movement, customer chat send, customer group send or Tencent Cloud staging deployment was made.

Remaining acceptance:

- Tencent Cloud staging rehearsal.
- Real OpenRouter staging evidence.
- Real allowlisted private Telegram test-chat receipt.
- Staging provider-disabled evidence.
- Staging business draft no-op evidence.
- Staging account exception branch evidence.
- Safety close evidence.

## 5. Checkpoint Evidence

This section records partial evidence gathered during implementation. It does not replace the final local acceptance pass required before staging.

```text
Date: 2026-07-07
Checkpoint: 05.1 Task 1 Runtime Config And Dependency Gate
Focused tests:
  pytest tests\unit\test_stage05_config.py -v
  result: 4 passed
Focused regression:
  pytest tests\unit\test_stage03_config.py tests\unit\test_stage04_config.py tests\unit\test_llm_adapters.py tests\unit\test_stage05_config.py -v
  result: 20 passed
Full backend suite:
  pytest tests -q
  result: 176 passed / 17 skipped
Skipped reason:
  Online PostgreSQL smoke tests require STAGE02_ONLINE_DATABASE_URL.
Secret scan:
  rg -n "OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
  result: config names, placeholders, documented scan patterns and existing fake test values only; no real sk-style key or private key found.
```

```text
Date: 2026-07-07
Checkpoint: 05.1 Task 2 AgentRun Evidence Model And Service
Focused tests:
  pytest tests\unit\test_stage05_openrouter_evidence.py -v
  result: 5 passed
Focused regression:
  pytest tests\unit\test_llm_adapters.py tests\unit\test_model_metadata.py tests\unit\test_initial_migration.py tests\unit\test_stage05_config.py tests\unit\test_stage05_openrouter_evidence.py -v
  result: 24 passed
Migration offline SQL:
  alembic upgrade head --sql
  result: reaches 20260707_0012 and emits additive agent_runs evidence columns, message FK and indexes.
Full backend suite:
  pytest tests -q
  result: 181 passed / 17 skipped
Skipped reason:
  Online PostgreSQL smoke tests require STAGE02_ONLINE_DATABASE_URL.
Secret and whitespace checks:
  rg -n "OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
  result: config names, placeholders, documented scan patterns and fake test values only; no real sk-style key or private key found.
  git diff --check
  result: no whitespace errors; Windows LF-to-CRLF warnings only.
Design note:
  Implemented ix_agent_runs_message_id_started_at instead of ix_agent_runs_message_id_created_at because existing agent_runs uses started_at/completed_at and Stage05 avoids adding a duplicate created_at column.
```

```text
Date: 2026-07-07
Checkpoint: 05.2 Task 3 Stage05 State And Router Schema
RED test:
  pytest tests\unit\test_stage05_router_schema.py -v
  result: 6 failed as expected because app.agents.schemas, app.agents.stage05_state and app.agents.message_intake_router did not exist yet.
Focused tests:
  pytest tests\unit\test_stage05_router_schema.py -v
  result: 6 passed
Focused regression:
  pytest tests\unit\test_stage05_router_schema.py tests\unit\test_stage05_config.py tests\unit\test_stage05_openrouter_evidence.py tests\unit\test_llm_adapters.py -v
  result: 18 passed
Migration offline SQL:
  alembic upgrade head --sql
  result: reaches 20260707_0012 and emits additive agent_runs evidence columns, message FK and indexes.
Full backend suite:
  pytest tests -q
  result: 187 passed / 17 skipped
Skipped reason:
  Online PostgreSQL smoke tests require STAGE02_ONLINE_DATABASE_URL.
Secret and whitespace checks:
  rg -n "OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
  result: config names, placeholders, documented scan patterns and fake test values only; no real sk-style key or private key found.
  git diff --check
  result: no whitespace errors; Windows LF-to-CRLF warnings only.
Not covered:
  Supervisor graph execution, child Agent draft generation, persistence, worker integration, real OpenRouter calls and staging rehearsal remain later tasks.
```

```text
Date: 2026-07-07
Checkpoint: 05.2 Task 4 Supervisor Graph
RED tests:
  pytest tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 7 failed / 1 passed as expected because app.agents.stage05_supervisor, app.services.agent_workflows and the worker stage05_workflow parameter did not exist yet.
  pytest tests\integration\test_stage05_agent_workflow.py::test_workflow_maps_llm_runtime_failure_to_agent_failed -v
  result: failed as expected because agent_failed outcome did not yet expose llm_runtime_error as reason.
Focused tests:
  pytest tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 9 passed
Regression:
  pytest tests\integration\test_stage03_worker_runtime.py tests\integration\test_stage04_intent_placeholder.py -v
  result: 7 passed
Focused Stage05 regression:
  pytest tests\unit\test_stage05_router_schema.py tests\unit\test_stage05_config.py tests\unit\test_stage05_openrouter_evidence.py tests\unit\test_llm_adapters.py tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 27 passed
Full backend suite:
  pytest tests -q
  result: 196 passed / 17 skipped
Skipped reason:
  Online PostgreSQL smoke tests require STAGE02_ONLINE_DATABASE_URL.
Migration offline SQL:
  alembic upgrade head --sql
  result: reaches 20260707_0012 and emits additive agent_runs evidence columns, message FK and indexes.
Secret and whitespace checks:
  rg -n "OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
  result: config names, placeholders, documented scan patterns and fake test values only; no real sk-style key or private key found.
  git diff --check
  result: no whitespace errors; Windows LF-to-CRLF warnings only.
Not covered:
  Child Agent draft generation, service draft persistence, account inventory mutation, confirmation/send, real OpenRouter calls, Redis worker runtime and staging rehearsal remain later tasks.
```

```text
Date: 2026-07-07
Checkpoint: 05.3 Task 5 Draft Agents And Multi-Draft Persistence
RED tests:
  pytest tests\unit\test_stage05_child_agents.py tests\integration\test_stage05_agent_workflow.py::test_workflow_routes_bound_intent_ready_message_and_records_agent_run -v
  result: 8 failed as expected because child Agent modules, Stage05 draft candidate schema, service_drafts metadata migration and workflow draft persistence did not exist yet.
Focused tests:
  pytest tests\unit\test_stage05_child_agents.py tests\integration\test_stage05_agent_workflow.py::test_workflow_routes_bound_intent_ready_message_and_records_agent_run -v
  result: 8 passed
Workflow regression:
  pytest tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 9 passed
Existing draft compatibility regression:
  pytest tests\unit\test_mock_router_agent.py tests\unit\test_service_drafts_api.py tests\unit\test_service_draft_state_machine.py -v
  result: 16 passed
Model/migration/child focused regression:
  pytest tests\unit\test_model_metadata.py tests\unit\test_initial_migration.py tests\unit\test_stage05_child_agents.py -v
  result: 19 passed
Focused Stage05 regression:
  pytest tests\unit\test_stage05_child_agents.py tests\unit\test_stage05_router_schema.py tests\unit\test_stage05_config.py tests\unit\test_stage05_openrouter_evidence.py tests\unit\test_llm_adapters.py tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 34 passed
Migration offline SQL:
  alembic upgrade head --sql
  result: reaches 20260707_0013 and emits additive service_drafts metadata columns plus fk_service_drafts_source_agent_run_id_agent_runs.
Full backend suite:
  pytest tests -q
  result: 203 passed / 17 skipped
Skipped reason:
  Online PostgreSQL smoke tests require STAGE02_ONLINE_DATABASE_URL.
Secret and whitespace checks:
  rg -n "OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
  result: config names, placeholders, documented scan patterns and fake test values only; no real sk-style key or private key found.
  git diff --check
  result: no whitespace errors; Windows LF-to-CRLF warnings only.
Not covered:
  Service Draft API enhancement filters/response shape, account inventory mutation, confirmation/send, real OpenRouter calls, Redis worker runtime and staging rehearsal remain later tasks.
```

```text
Date: 2026-07-07
Checkpoint: 05.3 Task 6 Service Draft API Enhancements
RED tests:
  pytest tests\unit\test_service_drafts_api.py -v
  result: 3 failed / 1 passed as expected because the list API did not yet expose Stage05 response fields or support draft_type/customer_id/source_message_id/trace_id query filters.
Focused tests:
  pytest tests\unit\test_service_drafts_api.py -v
  result: 5 passed
Draft and confirmation regression:
  pytest tests\unit\test_mock_router_agent.py tests\unit\test_service_drafts_api.py tests\unit\test_service_draft_state_machine.py -v
  result: 19 passed
Stage05 draft/workflow regression:
  pytest tests\unit\test_stage05_child_agents.py tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 16 passed
Full backend suite:
  pytest tests -q
  result: 206 passed / 17 skipped
Skipped reason:
  Online PostgreSQL smoke tests require STAGE02_ONLINE_DATABASE_URL.
Migration offline SQL:
  alembic upgrade head --sql
  result: reaches 20260707_0013 and emits additive service_drafts metadata columns.
Secret and whitespace checks:
  rg -n "OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
  result: config names, placeholders, documented scan patterns and fake test values only; no real sk-style key or private key found.
  git diff --check
  result: no whitespace errors; Windows LF-to-CRLF warnings only.
Not covered:
  Account inventory mutation, confirmation/send, Bitable views, real OpenRouter calls, Redis worker runtime and staging rehearsal remain later tasks.
```

```text
Date: 2026-07-07
Checkpoint: 05.4 Task 7 Account Inventory Agent
RED tests:
  pytest tests\unit\test_stage05_account_inventory_agent.py tests\integration\test_stage05_agent_workflow.py::test_workflow_marks_high_confidence_account_exception_status_event tests\integration\test_stage05_agent_workflow.py::test_workflow_creates_account_assignment_draft_without_assignment_side_effect -v
  result: 10 failed as expected because account_inventory_agent module, service mutation function, account status event metadata migration, workflow inventory UOW support and account_assignment draft wiring did not exist yet.
Focused tests:
  pytest tests\unit\test_stage05_account_inventory_agent.py tests\integration\test_stage05_agent_workflow.py::test_workflow_marks_high_confidence_account_exception_status_event tests\integration\test_stage05_agent_workflow.py::test_workflow_creates_account_assignment_draft_without_assignment_side_effect -v
  result: 10 passed
Inventory regression:
  pytest tests\unit\test_account_inventory.py tests\integration\test_inventory_assignment_slice.py -v
  result: 10 passed
Stage05 workflow regression:
  pytest tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 11 passed
Model/migration/account focused regression:
  pytest tests\unit\test_model_metadata.py tests\unit\test_initial_migration.py tests\unit\test_stage05_account_inventory_agent.py -v
  result: 20 passed
Focused Stage05 regression:
  pytest tests\unit\test_stage05_config.py tests\unit\test_stage05_openrouter_evidence.py tests\unit\test_stage05_router_schema.py tests\unit\test_stage05_child_agents.py tests\unit\test_stage05_account_inventory_agent.py tests\unit\test_service_drafts_api.py tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 46 passed
Migration offline SQL:
  alembic upgrade head --sql
  result: reaches 20260707_0015 and emits account_status_events confidence/risk_flags columns.
Full backend suite:
  pytest tests -q
  result: 216 passed / 17 skipped
Skipped reason:
  Online PostgreSQL smoke tests require STAGE02_ONLINE_DATABASE_URL.
Not covered:
  Confirmation/send, Bitable views, real OpenRouter calls, Redis worker runtime and staging rehearsal remain later tasks.
```

```text
Date: 2026-07-07
Checkpoint: 05.5 Task 8 Confirmation Branches
RED tests:
  pytest tests\integration\test_stage05_service_draft_confirmation.py -v
  result: 15 failed as expected because InMemoryConfirmationUnitOfWork did not accept messages/send_requests and confirm_service_draft did not accept allowed_chat_ids or implement Stage05 branch-specific behavior.
  pytest tests\integration\test_stage05_service_draft_confirmation.py::test_production_role_cannot_confirm_stage05_business_draft -v
  result: 1 failed as expected for the same missing allowed_chat_ids/Stage05 permission path.
Focused tests:
  pytest tests\integration\test_stage05_service_draft_confirmation.py -v
  result: 16 passed
Stage02 confirmation regression:
  pytest tests\unit\test_service_draft_state_machine.py tests\integration\test_recharge_vertical_slice.py tests\integration\test_stage_02_e2e.py -v
  result: 12 passed
Stage04 send regression:
  pytest tests\integration\test_stage04_test_send.py -v
  result: 13 passed
Stage05 workflow regression:
  pytest tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 11 passed
Focused Stage05 regression:
  pytest tests\unit\test_stage05_config.py tests\unit\test_stage05_openrouter_evidence.py tests\unit\test_stage05_router_schema.py tests\unit\test_stage05_child_agents.py tests\unit\test_stage05_account_inventory_agent.py tests\unit\test_service_drafts_api.py tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py tests\integration\test_stage05_service_draft_confirmation.py -v
  result: 62 passed
Combined Stage02/Stage04 regression:
  pytest tests\unit\test_service_draft_state_machine.py tests\integration\test_recharge_vertical_slice.py tests\integration\test_stage_02_e2e.py tests\integration\test_stage04_test_send.py -v
  result: 25 passed
Full backend suite:
  pytest tests -q
  result: 232 passed / 17 skipped
Migration offline SQL:
  alembic upgrade head --sql
  result: still reaches 20260707_0015; Task8 required no migration.
Secret and whitespace checks:
  rg -n "OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
  result: config names, placeholders, documented scan patterns and fake test values only; no real sk-style key or private key found.
  git diff --check
  result: no whitespace errors; Windows LF-to-CRLF warnings only.
Not covered:
  Task8 did not create persisted source_service_draft_id/send_purpose columns, did not confirm send requests, did not enqueue outbox, did not call Telegram, did not call OpenRouter and did not call providers. Customer reply send-confirm/worker path remains Task9.
```

```text
Date: 2026-07-07
Checkpoint: 05.5 Task 9 Customer Reply Send Request
RED tests:
  pytest tests\integration\test_stage05_customer_reply_send.py -v
  result: 4 failed as expected because TelegramSendRequest lacked source_service_draft_id/send_purpose/message_text_summary, customer-reply-specific audit branches and migration 20260707_0016 did not exist yet.
Focused tests:
  pytest tests\integration\test_stage05_customer_reply_send.py -v
  result: 4 passed
Confirmation/send regression:
  pytest tests\integration\test_stage04_test_send.py tests\integration\test_stage05_service_draft_confirmation.py tests\integration\test_stage05_customer_reply_send.py -v
  result: 33 passed
Model/migration/confirmation regression:
  pytest tests\unit\test_model_metadata.py tests\unit\test_initial_migration.py tests\unit\test_service_draft_state_machine.py -v
  result: 22 passed
Stage05 workflow regression:
  pytest tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v
  result: 11 passed
Full backend suite:
  pytest tests -q
  result: 236 passed / 17 skipped
Migration offline SQL:
  alembic upgrade head --sql
  first result: failed because the original FK name exceeded PostgreSQL's 63-character identifier limit.
  fixed result: reaches 20260707_0016 and emits source_service_draft_id, send_purpose, message_text_summary, fk_tg_send_req_source_draft and the Stage05 reply-send indexes.
Not covered:
  No real Telegram call, real OpenRouter call, provider execution, Tencent Cloud staging deployment or customer/customer-group send occurred. The worker send path used a fake Telegram bot client only.
```

```text
Date: 2026-07-07
Checkpoint: 05.6 Task 10 Bitable Views
RED tests:
  pytest tests\unit\test_stage05_bitable_views.py -v
  result: 4 failed as expected because service_drafts, agent_review_queue and customer_reply_send_requests views did not exist and telegram_inbox/account_inventory did not expose derived Stage05 evidence fields yet.
Focused tests:
  pytest tests\unit\test_stage05_bitable_views.py -v
  result: 5 passed
View regression:
  pytest tests\unit\test_bitable_views.py tests\unit\test_stage03_telegram_inbox_view.py tests\unit\test_stage04_bitable_views.py tests\unit\test_stage05_bitable_views.py -v
  result: 22 passed
Stage05 regression:
  pytest tests -k stage05 -v
  result: 68 selected passed / 190 deselected
Not covered:
  No real OpenRouter call, real Telegram call, provider execution, Tencent Cloud staging deployment or customer/customer-group send occurred. Staging API view evidence remains pending.
```

```text
Date: 2026-07-07
Checkpoint: 05.6 Task 11 Local Acceptance Audit
Focused Stage05 tests:
  pytest tests -k stage05 -v
  result: 73 passed / 190 deselected
Stage03/Stage04 regression:
  pytest tests\integration\test_stage03_customer_binding.py tests\integration\test_stage03_worker_runtime.py tests\integration\test_stage04_intent_placeholder.py tests\integration\test_stage04_test_send.py tests\unit\test_stage04_bitable_views.py tests\unit\test_stage04_config.py -v
  result: 33 passed
Full backend suite:
  pytest tests -q
  result: 246 passed / 17 skipped
Skipped reason:
  Online PostgreSQL smoke tests require STAGE02_ONLINE_DATABASE_URL.
Migration offline SQL:
  alembic upgrade head --sql
  result: reaches 20260707_0016 and emits source_service_draft_id, send_purpose, message_text_summary, fk_tg_send_req_source_draft and the Stage05 reply-send indexes.
Secret scan:
  rg -n "OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
  result: config names, placeholders, documented scan patterns and fake test values only; no real sk-style key or private key found.
Whitespace check:
  git diff --check
  result: no whitespace errors; Windows LF-to-CRLF warnings only.
Documentation consistency:
  rg stale Task10/view-pending wording under project-docs/08-implementation
  result: no stale Task10 pending wording found outside staging-pending context.
Not covered:
  No Tencent Cloud staging deployment, real OpenRouter call, real Telegram call, provider execution, customer/customer-group send or safety close occurred.
```

```text
Date: 2026-07-07
Checkpoint: 05.6 Task 12 Local Staging Contract Preflight
RED check:
  pytest tests\integration\test_stage05_staging_contract.py -v
  result: failed because the file did not exist yet.
Focused tests:
  pytest tests\integration\test_stage05_staging_contract.py -v
  result: 5 passed
Coverage:
  Validates that Stage05 staging rehearsal env can pass only with real_openrouter mode, server-side OpenRouter key, restricted Telegram test-send mode, bot token, private allowlist placeholder and provider disabled.
  Validates that provider-enabled staging env is rejected without leaking fake secret values in the error.
  Validates that LLM_ENABLED=true without AGENT_WORKFLOW_MODE=real_openrouter is rejected.
  Validates that restricted_test send without TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS is rejected.
  Validates safety-close contract: LLM disabled, TELEGRAM_SEND_MODE=dry_run, empty test send allowlist and PROVIDER_MODE=disabled.
Not covered:
  This is local configuration contract evidence only. It does not deploy to Tencent Cloud, call OpenRouter, send Telegram, or prove a real staging receipt.
```
