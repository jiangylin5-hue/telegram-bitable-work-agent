# Stage 02 Acceptance Checklist

## Status

- Document status: active acceptance checklist
- Scope: Stage 02 backend kernel, mock Telegram ingestion, Bitable-like view API, confirmation, mock recharge execution, account inventory, customer/company reporting
- Current Progress: 2026-07-05 扩展 bounded online PostgreSQL smoke 验收：`tests/integration/test_online_postgres_smoke.py` 在 disposable PostgreSQL 上验证 Alembic online `upgrade head`、mock Telegram API 真实落库与跨 session 幂等、DB-backed `agent.intent_extract` 生成 draft、Bitable view 真实回读、`audit_view` 真实审计投影、confirmation API 成功提交、Agent confirmation denial 真实拒绝并提交 `permission_denied` audit、customer report sales scoped-denial 真实拒绝并提交 `permission_denied` audit、company report sales denial 真实拒绝并提交 `permission_denied` audit、business write + outbox event rollback 原子性、report API 真实聚合和提交、customer report stale_data/risk_event persistence、inventory service 真实状态跃迁、recharge service 真实执行/readback 状态、`recharge_view` sales actor 真实 PostgreSQL scoped/masked readback、readback failure 的 `customer.reply` mock outbox、outbox dispatcher database-backed success/retry/dead_letter 处理；最新验证为 online smoke 17 passed、全量 `pytest tests -v` 102 passed、Alembic offline SQL 到 `20260705_0009`、AST_OK 93 files。

## 1. Acceptance Boundary

Stage 02 只验收 mock/sandbox 后端闭环：

- Mock Telegram update can create a stored message and outbox intent event.
- Mock router agent can create a `service_drafts` record.
- Human confirmation can create `service_records` and `execution_tickets`.
- Agent cannot self-confirm executable actions.
- Mock recharge execution can create `execution_logs`.
- Recharge execution status and readback status are separate.
- Account inventory can create unused accounts, assign them only after human confirmation, activate allocated accounts only by authorized human roles, and answer assigned customer/current status through API and Bitable-shaped views.
- Customer daily report can aggregate account metrics with `source` and `freshness_at`.
- Company daily report can aggregate all customers for manager/admin.
- Sales cannot view company-level daily reports.
- Stage 02 migrations include core, draft, recharge, inventory and reporting tables.
- No `tenant_id`, raw card number, card number or CVV columns are introduced.

Stage 02 does not validate:

- Real Telegram Bot webhook.
- Real Meta/BM/card/recharge provider writes.
- Real funds movement.
- Real OpenRouter calls.
- Production/long-lived PostgreSQL migration against a managed or shared database.
- Redis Streams production worker.
- Telegram Mini App or web admin UI.

## 2. Verification Commands

Run from repository root unless noted.

| Command | Expected result | Purpose |
| --- | --- | --- |
| `cd backend; pytest tests/integration/test_stage_02_e2e.py -v` | E2E critical path passes | Proves mock Telegram -> draft -> confirmation -> mock recharge -> inventory -> reporting path |
| `cd backend; docker compose -f docker-compose.stage02-online.yml up -d` | Disposable PostgreSQL/pgvector test database is healthy on `localhost:55433` | Provides the local real PostgreSQL target for bounded online smoke tests |
| `cd backend; $env:STAGE02_ONLINE_DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:55433/stage02_online_test'; pytest tests/integration/test_online_postgres_smoke.py -v` | 17 online smoke tests pass | Proves Alembic `upgrade head` against real PostgreSQL, API write commit, Telegram duplicate idempotency across sessions, DB-backed `agent.intent_extract` draft creation, Bitable view readback including `audit_view`, sales-scoped/masked `recharge_view`, stale customer report risk evidence, confirmation success and permission-denial transaction persistence, customer/company report permission denial, business write + outbox rollback atomicity, reporting, inventory, recharge and database-backed outbox dispatcher success/retry/dead_letter paths |
| `cd backend; pytest tests -v` | Full test suite passes | Proves all Stage 02 unit/integration slices still pass together |
| `cd backend; alembic upgrade head --sql` | Offline SQL includes revisions `0001` through `0009` | Proves migrations are ordered and importable without touching a real DB |
| `cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')"` | `AST_OK ... files` | Proves Python files parse without writing `__pycache__` |

## 3. Requirement Checklist

| Requirement | Status | Evidence |
| --- | --- | --- |
| Git repository initialized | passed | `git status --short --branch` returns branch state |
| Backend skeleton and `/health` route | passed | `tests/unit/test_health.py` |
| SQLAlchemy metadata and Alembic env | passed | `tests/unit/test_model_metadata.py`, `tests/unit/test_initial_migration.py` |
| Bitable-like view registry, projection and permissions | passed | `tests/unit/test_bitable_views.py`; `tests/integration/test_online_postgres_smoke.py`; records can be projected from injected data source and from real PostgreSQL rows, including Telegram inbox, AI draft queue readback after DB-backed `agent.intent_extract`, `audit_view` readback from real `ops_audit_events`, and `recharge_view` sales actor readback that filters to the actor's scoped customer and masks `amount`; default `/views` dependency uses `SqlAlchemyBitableViewDataSource` over SQLAlchemy metadata; route-level actor context filters customer-scoped records and masks fields such as `amount` and `raw_text`; `ai_draft_queue` maps Bitable output field `intent_type` from physical `service_drafts.draft_type` |
| Permission and audit kernel | passed | `tests/unit/test_permissions.py`, `tests/unit/test_audit.py`, plus write-path audit/status evidence in `tests/unit/test_telegram_ingestion.py`, `tests/unit/test_service_draft_state_machine.py`, `tests/unit/test_recharge_flow.py`, `tests/unit/test_account_inventory.py`, `tests/unit/test_reporting.py`, `tests/unit/test_outbox.py`; `tests/integration/test_online_postgres_smoke.py::test_online_agent_confirmation_denial_persists_audit_without_business_writes`, `tests/integration/test_online_postgres_smoke.py::test_online_customer_report_api_denies_unscoped_sales_and_persists_audit` and `tests/integration/test_online_postgres_smoke.py::test_online_company_report_api_denies_sales_and_persists_audit` verify real PostgreSQL denial audit persistence through API and `audit_view` |
| Outbox dispatcher semantics | passed | `tests/unit/test_outbox.py`; `tests/integration/test_online_postgres_smoke.py::test_online_business_write_and_outbox_event_rollback_atomically` proves a real PostgreSQL transaction rollback removes both the business draft row and its outbox event; `tests/integration/test_online_postgres_smoke.py::test_online_outbox_dispatcher_retries_then_dead_letters_database_backed_event` proves DB-backed retry, dead_letter and `outbox_dead_letter` audit persistence |
| Mock Telegram ingestion | passed | `tests/unit/test_telegram_ingestion.py`, `tests/integration/test_mock_telegram_to_message.py`, `tests/integration/test_online_postgres_smoke.py::test_online_mock_telegram_duplicate_update_is_idempotent_across_sessions`; covers duplicate update idempotency against real PostgreSQL across separate API requests/sessions |
| Mock router to service draft | passed | `tests/unit/test_mock_router_agent.py`, `tests/integration/test_mock_telegram_to_message.py`, `tests/integration/test_online_postgres_smoke.py::test_online_agent_intent_extract_uses_database_uow_and_updates_draft_view`; covers recharge, account inventory request, report request, needs_review, and DB-backed `agent.intent_extract` creating `service_drafts`, updating `messages.intent_status`, writing `draft_created` audit, and appearing in `ai_draft_queue` |
| Human confirmation and execution ticket | passed | `tests/unit/test_service_draft_state_machine.py`; `tests/integration/test_online_postgres_smoke.py::test_online_confirmation_route_commits_service_record_ticket_and_view_state`; `tests/integration/test_online_postgres_smoke.py::test_online_agent_confirmation_denial_persists_audit_without_business_writes`; covers confirm, reject, request_more_info, escalate, API reject route, default SQLAlchemy-backed confirmation UOW writing service record, execution ticket and audit event to one session, route-level successful confirmation committing the UOW, and route-level Agent denial preserving draft state without service/ticket writes while committing `permission_denied` audit |
| LLM adapter and agent run audit | passed | `tests/unit/test_llm_adapters.py`; fake client requires no API key, OpenRouter adapter uses injected HTTP client |
| Recharge mock execution/readback split | passed | `tests/unit/test_recharge_flow.py`, `tests/integration/test_recharge_vertical_slice.py`, `tests/integration/test_online_postgres_smoke.py`; covers collection confirmation not equal to execution success, readback failure requiring prior successful execution, audit events for recharge record creation, collection creation/confirmation, execution success and readback failure, plus `customer.reply` mock outbox payload that states execution succeeded while balance readback failed |
| Account inventory assignment, activation and status query | passed | `tests/unit/test_account_inventory.py`, `tests/integration/test_inventory_assignment_slice.py`; covers unused query, assigned customer/current status query, `allocated -> activated` status/audit event, Agent activation denial, and default SQLAlchemy-backed inventory UOW |
| Customer/company reporting | passed | `tests/unit/test_reporting.py`, `tests/integration/test_daily_report_slice.py`, `tests/integration/test_online_postgres_smoke.py::test_online_reporting_routes_read_facts_commit_reports_and_update_views`, `tests/integration/test_online_postgres_smoke.py::test_online_customer_report_keeps_stale_spend_unknown_and_persists_risk_event`, `tests/integration/test_online_postgres_smoke.py::test_online_customer_report_api_denies_unscoped_sales_and_persists_audit`, `tests/integration/test_online_postgres_smoke.py::test_online_company_report_api_denies_sales_and_persists_audit`; covers customer metrics, stale data preserving spend as unknown, risk event/audit persistence, date-aligned recharge records in customer report, recharge summary in company report, date-aligned card binding records in customer report, card binding summary in company report, report-generation audit, default SQLAlchemy-backed reporting UOW, route-level successful report generation committing the UOW, unscoped sales denial for customer report API with no `customer_daily_reports` row, sales denial for company report API with no `company_daily_reports` row, and `card_binding_state.status = not_available_in_stage_02` when no binding facts exist |
| Online PostgreSQL migration and API persistence smoke | passed | `tests/integration/test_online_postgres_smoke.py`; with disposable `pgvector/pgvector:pg16` PostgreSQL on `localhost:55433`, Alembic `upgrade head` creates Stage 02 tables through `20260705_0009`; mock Telegram API writes `messages`, `outbox_events`, and `ops_audit_events`; duplicate Telegram updates remain one message and one outbox event across API requests; `/views/telegram_inbox/records` reads the real row; `/views/audit_view/records` reads the real `message_ingested` and `permission_denied` audit rows from `ops_audit_events`; DB-backed `agent.intent_extract` creates `service_drafts`, updates message intent status, writes `draft_created` audit, and `/views/ai_draft_queue/records` reads the generated draft; `/views/recharge_view/records` under a sales actor returns only scoped customer rows, masks `amount`, and exposes `collection_status`/`execution_status`/`readback_status`; customer report API keeps stale spend as unknown, creates a real `risk_events` row, writes `risk_event_created` audit, and exposes the stale payload through `/views/customer_daily_reports/records`; confirmation API commits `service_records`, `execution_tickets`, audit event, and `/views/ai_draft_queue/records` reflects confirmed status; Agent confirmation denial keeps draft pending, creates no service/ticket records, commits denial audit, and exposes it in `audit_view`; unscoped sales customer-report denial returns 403, creates no `customer_daily_reports` row, commits denial audit, and exposes it to admin in `audit_view`; sales company-report denial returns 403, creates no `company_daily_reports` row, commits denial audit, and exposes it to admin in `audit_view`; explicit rollback smoke proves business draft + outbox event disappear together; report APIs aggregate real metrics/recharge/card-binding facts; inventory service persists assignment/status events; recharge service persists collection/execution/readback plus both `readback.balance` and `customer.reply` outbox events; `SqlAlchemyOutboxRepository` lets dispatcher process real database-backed success and retry-to-dead-letter events |
| Stage 02 critical path E2E | passed after command run | `tests/integration/test_stage_02_e2e.py` |

## 4. Remaining Risks

- Bitable view API now has both offline route/unit coverage and real PostgreSQL smoke coverage for Telegram inbox, AI draft queue, audit view and sales-scoped/masked `recharge_view` readback. Broader production-scale view filtering, sorting and pagination remain later hardening work.
- Reporting now includes date-aligned `recharge_records` and `account_card_bindings` facts. Stage 02 still does not execute real external card binding; it only stores tokenized/masked facts and mock/reporting state.
- Major API route defaults now use SQLAlchemy-backed UOWs. Confirmation and reporting successful write behavior is verified against real PostgreSQL in `tests/integration/test_online_postgres_smoke.py`; inventory/recharge service paths and outbox dispatcher also have bounded real PostgreSQL coverage. Many service-level state-machine tests still use in-memory UOWs for deterministic unit coverage.
- Real external writes remain intentionally excluded from Stage 02.
