# Stage 02 Behavior Driven Development

## Status

- Document status: active BDD draft
- Scope: Stage 02 可验收业务行为、Gherkin 风格场景、测试映射
- Current Progress: 2026-07-05 补充 API UOW、outbox 事务行为、DB-backed `agent.intent_extract`、Telegram duplicate online 幂等、`audit_view` online 审计投影、`recharge_view` sales scoped/masked online 投影、customer report stale_data/risk_event online 验收、Agent confirmation denial API/DB 验收、customer report sales scoped-denial API/DB 验收、company report sales denial API/DB 验收和 readback failure 客户回复验收：`/service-drafts`、`/inventory/accounts`、`/confirmations/service-drafts/{draft_id}/actions`、`/reports/*` 默认使用 SQLAlchemy-backed UOW 和 DB session；confirmation/report 写入型 API 成功路径必须提交 UOW；`tests/integration/test_online_postgres_smoke.py::test_online_mock_telegram_duplicate_update_is_idempotent_across_sessions` 验证真实 PostgreSQL 下重复 update 跨 API request/session 只产生一条 message/outbox/audit；`tests/integration/test_online_postgres_smoke.py::test_online_agent_intent_extract_uses_database_uow_and_updates_draft_view` 验证 mock Telegram message 经过 DB-backed handler 生成 draft 并进入 `ai_draft_queue`；`tests/integration/test_online_postgres_smoke.py::test_online_audit_view_reads_real_audit_events` 验证 `/views/audit_view/records` 从真实 `ops_audit_events` 投影 `message_ingested` 审计；`tests/integration/test_online_postgres_smoke.py::test_online_recharge_view_scopes_and_masks_sales_actor_from_real_rows` 验证 `/views/recharge_view/records` 在真实 PostgreSQL rows 上对 sales actor 只返回授权客户记录、遮蔽 `amount`，并保留充值三段状态；`tests/integration/test_online_postgres_smoke.py::test_online_customer_report_keeps_stale_spend_unknown_and_persists_risk_event` 验证客户日报真实 API/DB 路径下 stale spend 保持 unknown、生成 `risk_events`、写 `risk_event_created` audit 并进入 `customer_daily_reports` view；`tests/integration/test_online_postgres_smoke.py::test_online_agent_confirmation_denial_persists_audit_without_business_writes` 验证 Agent 经 confirmation API 尝试确认被 403 拒绝、草稿保持 pending、不创建 service/ticket、`permission_denied` audit 真实落库并进入 `audit_view`；`tests/integration/test_online_postgres_smoke.py::test_online_customer_report_api_denies_unscoped_sales_and_persists_audit` 验证 sales 请求未授权客户日报被 403 拒绝、不创建 `customer_daily_reports`、`permission_denied` audit 真实落库并由 admin 在 `audit_view` 查回；`tests/integration/test_online_postgres_smoke.py::test_online_company_report_api_denies_sales_and_persists_audit` 验证 sales 经 company report API 被 403 拒绝、不创建 `company_daily_reports`、`permission_denied` audit 真实落库并由 admin 在 `audit_view` 查回；`tests/integration/test_online_postgres_smoke.py::test_online_business_write_and_outbox_event_rollback_atomically` 验证真实 PostgreSQL transaction rollback 后业务草稿和 outbox event 都不存在；`tests/integration/test_online_postgres_smoke.py::test_online_outbox_dispatcher_retries_then_dead_letters_database_backed_event` 验证真实 `outbox_events` retry -> dead_letter 和 audit；readback failure 相关测试验证 `customer.reply` mock outbox 及执行未成功时不能生成误导性回复；单元/集成测试可 dependency override 为 in-memory UOW。

## 1. Purpose

BDD 用来回答：

```text
业务用户如何判断这个系统真的能用？
```

所有行为都必须能映射到：

- API 行为。
- 数据库记录。
- Bitable view。
- audit event。
- 测试命令。

## 2. Feature: Mock Telegram Message To Draft

### Scenario 2.1: Known customer recharge message creates draft

Given:

- A customer exists.
- A customer Telegram group is bound.
- A mock Telegram message says: `给账户 act_1001 充值 1000 USD`.

When:

- `POST /mock/telegram/updates` receives the message.
- Outbox dispatcher handles `agent.intent_extract`.

Then:

- One `messages` record exists.
- `messages.intent_type = recharge`.
- One `service_drafts` record exists.
- Draft status is `pending_confirmation` or `needs_more_info` depending on extracted fields.
- `telegram_inbox` view shows the message.
- `ai_draft_queue` view shows the draft.
- `ops_audit_events` includes message ingestion and draft creation.

Test mapping:

- `backend/tests/integration/test_mock_telegram_to_message.py`
- `backend/tests/unit/test_mock_router_agent.py`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_agent_intent_extract_uses_database_uow_and_updates_draft_view`

### Scenario 2.2: Duplicate Telegram update is idempotent

Given:

- A mock Telegram update was already ingested.

When:

- The same update is submitted again.

Then:

- No second `messages` record is created.
- No duplicate `agent.intent_extract` outbox event is created.
- API returns idempotent success.

Test mapping:

- `backend/tests/unit/test_telegram_ingestion.py::test_duplicate_update_is_idempotent`
- `backend/tests/integration/test_mock_telegram_to_message.py::test_mock_telegram_update_api_is_idempotent`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_mock_telegram_duplicate_update_is_idempotent_across_sessions`

## 3. Feature: Human Confirmation And Execution Ticket

### Scenario 3.1: Agent cannot confirm its own draft

Given:

- A recharge draft exists.
- Actor role is `agent`.

When:

- Agent attempts to confirm draft.

Then:

- Request is rejected with `permission_denied`.
- No service record is created.
- No execution ticket is created.
- Audit event records the denied confirmation attempt.

Test mapping:

- `backend/tests/unit/test_service_draft_state_machine.py`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_agent_confirmation_denial_persists_audit_without_business_writes`

### Scenario 3.2: Authorized production user confirms executable draft

Given:

- A recharge draft has customer, account, amount, currency, and finance confirmation.
- Actor role is `production`.

When:

- Production confirms the draft.

Then:

- One `service_records` record is created.
- One `execution_tickets` record is issued.
- Ticket status is `issued`.
- Audit event records human confirmation.
- Draft is no longer executable without the ticket path.

Test mapping:

- `backend/tests/unit/test_service_draft_state_machine.py::test_production_confirmation_creates_service_record_and_ticket`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_confirmation_route_commits_service_record_ticket_and_view_state`

## 4. Feature: Recharge Vertical Slice

### Scenario 4.1: Finance confirmation is not recharge success

Given:

- A recharge record exists.
- A collection record exists.

When:

- Finance confirms collection.

Then:

- `collection_records.collection_status = confirmed`.
- `recharge_records.collection_status = confirmed`.
- `recharge_records.execution_status` is still `not_started` or `queued`, not `succeeded`.
- Customer-visible status must not say recharge succeeded.
- `ops_audit_events.event_type = collection_confirmed`.

Test mapping:

- `backend/tests/unit/test_recharge_flow.py::test_finance_confirmation_is_not_recharge_success`
- `backend/tests/integration/test_recharge_vertical_slice.py::test_confirmed_recharge_draft_runs_mock_execution_and_separate_readback_failure`

### Scenario 4.2: Mock execution writes execution log

Given:

- Recharge service record is confirmed.
- Valid execution ticket exists.

When:

- Outbox dispatcher handles `execution.recharge`.

Then:

- Mock provider adapter is called.
- `execution_logs.execution_status = succeeded`.
- `recharge_records.execution_status = succeeded`.
- A `readback.balance` outbox event is created.
- `recharge_view` shows execution status.
- `ops_audit_events.event_type = recharge_execution_succeeded`.

Test mapping:

- `backend/tests/unit/test_recharge_flow.py::test_mock_execution_writes_log_and_enqueues_readback`
- `backend/tests/unit/test_recharge_flow.py::test_execution_and_readback_handlers_call_recharge_services`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_recharge_service_persists_execution_readback_and_view_status`

### Scenario 4.3: Readback failure remains separate

Given:

- Recharge execution succeeded.

When:

- Mock readback fails.

Then:

- `recharge_records.execution_status = succeeded`.
- `recharge_records.readback_status = failed`.
- `risk_events.risk_type = readback_failed` may be created.
- Customer reply must say execution succeeded but balance readback failed.
- If execution has not succeeded, the system must reject readback failure marking and must not create a customer reply.

Stage 02 representation:

- The customer reply is a `customer.reply` mock outbox event. Stage 02 does not send a real Telegram message.

Test mapping:

- `backend/tests/unit/test_recharge_flow.py::test_readback_failure_enqueues_customer_reply_with_separate_status_message`
- `backend/tests/unit/test_recharge_flow.py::test_readback_failure_requires_successful_execution_before_customer_reply`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_recharge_service_persists_execution_readback_and_view_status`

## 5. Feature: Account Inventory Vertical Slice

### Scenario 5.1: Production creates unused inventory accounts

Given:

- Actor role is `production`.

When:

- Production creates inventory account `act_2001`.

Then:

- `account_inventory.inventory_status = unused`.
- `account_status_events.event_type = produced`.
- `account_inventory` view shows the account.

Test mapping:

- `backend/tests/unit/test_account_inventory.py::test_production_creates_unused_inventory_account_with_status_event`
- `backend/tests/unit/test_account_inventory.py::test_inventory_api_returns_unused_accounts`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_inventory_services_persist_assignment_and_view_status`

### Scenario 5.2: Assignment requires human confirmation

Given:

- An unused inventory account exists.
- A customer requests an account.

When:

- Account Inventory Agent proposes assignment.

Then:

- `account_assignments.assignment_status = proposed`.
- Inventory account is not yet `allocated`.

When:

- Authorized human confirms assignment.

Then:

- `account_assignments.assignment_status = confirmed`.
- `account_inventory.inventory_status = allocated`.
- `account_status_events.event_type = assigned`.

Test mapping:

- `backend/tests/integration/test_inventory_assignment_slice.py::test_assignment_requires_human_confirmation`
- `backend/tests/integration/test_inventory_assignment_slice.py::test_agent_cannot_confirm_assignment`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_inventory_services_persist_assignment_and_view_status`

### Scenario 5.3: Inventory can answer assigned customer and activation status

Given:

- An inventory account has been assigned to a customer after human confirmation.
- The account is still in `allocated` status.

When:

- Authorized production or manager user marks the account as activated.

Then:

- `account_inventory.inventory_status = activated`.
- `account_status_events.event_type = activated`.
- `account_status_events.customer_id` keeps the assigned customer.
- Agent actor cannot perform the activation without human authority.

When:

- User queries inventory by `status` and `customer_id`.

Then:

- The API can return the assigned customer and current status.
- The `account_inventory` Bitable-shaped view includes `assigned_customer_id`, `assigned_at`, `inventory_status`, and `status_reason`.

Test mapping:

- `backend/tests/unit/test_account_inventory.py`
- `backend/tests/unit/test_bitable_views.py`
- `backend/tests/integration/test_inventory_assignment_slice.py`

## 6. Feature: Customer And Company Daily Reports

### Scenario 6.1: Customer report uses only customer data

Given:

- Customer A and Customer B both have account metrics.

When:

- Customer Reporting Agent generates Customer A report.

Then:

- `customer_daily_reports.customer_id = Customer A`.
- Report payload includes only Customer A accounts.
- Report payload excludes Customer B accounts.
- Every metric includes `source` and `freshness_at`.
- Report payload includes Customer A same-day `recharge_records`.
- Report payload excludes other customers' recharge records and other dates' recharge records.
- If Customer A has same-day `account_card_bindings`, report payload includes binding records and masked failure reason.
- If Customer A has no same-day `account_card_bindings`, `card_binding_state.status = not_available_in_stage_02`.
- `ops_audit_events.event_type = customer_daily_report_generated`.

Test mapping:

- `backend/tests/unit/test_reporting.py::test_customer_report_contains_only_requested_customer_metrics`
- `backend/tests/unit/test_reporting.py::test_customer_report_includes_same_day_recharge_records_and_binding_gap`
- `backend/tests/unit/test_reporting.py::test_customer_report_includes_same_day_card_binding_facts`
- `backend/tests/unit/test_reporting.py::test_customer_report_api_commits_generated_report`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_reporting_routes_read_facts_commit_reports_and_update_views`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_customer_report_api_denies_unscoped_sales_and_persists_audit`

### Scenario 6.2: Stale data is explicit

Given:

- An account metric has stale `freshness_at`.

When:

- Customer report is generated.

Then:

- Report marks data as `stale_data`.
- Report does not convert missing or stale spend into zero.
- Risk event creation writes audit evidence.

Test mapping:

- `backend/tests/unit/test_reporting.py::test_customer_report_keeps_stale_spend_unknown_and_creates_risk_event`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_customer_report_keeps_stale_spend_unknown_and_persists_risk_event`

### Scenario 6.3: Company report is manager/admin only

Given:

- A company daily report exists.

When:

- Actor role is `sales`.

Then:

- Access is denied or sensitive global fields are hidden.

When:

- Actor role is `manager`.

Then:

- Company report is visible.
- Company report payload includes same-day recharge amount totals by currency.
- Company report payload includes recharge execution and readback status counts.
- Company report payload includes same-day card binding status counts.
- `ops_audit_events.event_type = company_daily_report_generated`.

Test mapping:

- `backend/tests/integration/test_daily_report_slice.py::test_company_report_is_visible_to_manager_and_denied_to_sales`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_reporting_routes_read_facts_commit_reports_and_update_views`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_company_report_api_denies_sales_and_persists_audit`
- `backend/tests/unit/test_reporting.py::test_company_report_generation_writes_audit_event`
- `backend/tests/unit/test_reporting.py::test_company_report_includes_recharge_summary_for_report_date`
- `backend/tests/unit/test_reporting.py::test_company_report_includes_card_binding_summary_for_report_date`

## 7. Feature: Bitable View Completion

### Scenario 7.1: Every workflow lands in a view

Given:

- A message was ingested.
- A draft was created.
- A recharge was executed.
- An inventory account was assigned.
- A customer report was generated.

When:

- User queries Stage 02 views.

Then:

- Message appears in `telegram_inbox`.
- Draft appears in `ai_draft_queue`.
- Recharge appears in `recharge_view`.
- Inventory appears in `account_inventory`.
- Reports appear in `customer_daily_reports` and `company_daily_reports`.
- Audit appears in `audit_view`.

Test mapping:

- `backend/tests/unit/test_bitable_views.py::test_every_stage_02_view_can_return_workflow_records`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_audit_view_reads_real_audit_events`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_agent_intent_extract_uses_database_uow_and_updates_draft_view`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_reporting_routes_read_facts_commit_reports_and_update_views`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_inventory_services_persist_assignment_and_view_status`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_recharge_service_persists_execution_readback_and_view_status`

### Scenario 7.2: Default view data source reads through SQLAlchemy metadata

Given:

- A Stage 02 view maps to a registered SQLAlchemy metadata table.
- The API route resolves its default Bitable view data source.

When:

- The view service lists records for that table.

Then:

- The default data source is `SqlAlchemyBitableViewDataSource`.
- SQLAlchemy session `execute(select(table))` is used for known metadata tables.
- Returned rows are converted into `{ id, fields }` records.
- Unknown physical table names return an empty list without executing a query.
- Tests may override the dependency with in-memory or empty data sources for offline API shape checks.

Test mapping:

- `backend/tests/unit/test_bitable_views.py::test_default_view_dependency_uses_sqlalchemy_data_source`
- `backend/tests/unit/test_bitable_views.py::test_sqlalchemy_bitable_data_source_reads_metadata_table_rows`
- `backend/tests/unit/test_bitable_views.py::test_sqlalchemy_bitable_data_source_returns_empty_for_unknown_table`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_postgres_api_write_is_visible_in_bitable_view`

### Scenario 7.3: Sales view request is scoped and masked

Given:

- `recharge_view` has records for `customer-1` and `customer-2`.
- A sales actor is scoped only to `customer-1`.

When:

- The sales actor queries `GET /views/recharge_view/records`.

Then:

- The response includes only `customer-1` records.
- The response does not include `customer-2` records.
- The `amount` field is masked.
- The response includes `collection_status`, `execution_status`, and `readback_status`.
- Non-sensitive fields such as `customer_id` and `currency` remain visible.

Test mapping:

- `backend/tests/unit/test_bitable_views.py::test_view_api_applies_actor_record_scope_and_field_permissions`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_recharge_view_scopes_and_masks_sales_actor_from_real_rows`

## 8. Feature: Outbox Reliability

### Scenario 8.1: Business write and outbox event are atomic

Given:

- A service creates a draft that needs Agent handling.

When:

- Database transaction commits.

Then:

- The draft exists.
- The outbox event exists.

When:

- Database transaction rolls back.

Then:

- Neither draft nor outbox event exists.

Test mapping:

- `backend/tests/integration/test_online_postgres_smoke.py::test_online_business_write_and_outbox_event_rollback_atomically`

### Scenario 8.2: Failed outbox event retries then dead letters

Given:

- An outbox handler raises a retryable error.

When:

- Dispatcher runs.

Then:

- Attempt count increases.
- Status becomes `retry` until max attempts.
- After max attempts, status becomes `dead_letter`.
- Audit event records failure.

Test mapping:

- `backend/tests/unit/test_outbox.py::test_dispatcher_retries_then_dead_letters_and_writes_audit`
- `backend/tests/integration/test_online_postgres_smoke.py::test_online_outbox_dispatcher_retries_then_dead_letters_database_backed_event`

## 9. Feature: API Persistence Boundaries

### Scenario 9.1: Main Stage 02 APIs default to SQLAlchemy-backed UOWs

Given:

- Stage 02 API routes are created by FastAPI.
- A DB session dependency is available.

When:

- The default UOW dependency for service drafts, inventory, confirmations, or reports is resolved.

Then:

- `/service-drafts` uses `SqlAlchemyServiceDraftUnitOfWork`.
- `/inventory/accounts` uses `SqlAlchemyAccountInventoryUnitOfWork`.
- `/confirmations/service-drafts/{draft_id}/actions` uses `SqlAlchemyConfirmationUnitOfWork`.
- `/reports/*` uses `SqlAlchemyReportingUnitOfWork`.
- Tests may override these dependencies with in-memory UOWs for deterministic unit and slice coverage.

Test mapping:

- `backend/tests/unit/test_service_drafts_api.py::test_default_service_draft_dependency_uses_sqlalchemy_uow`
- `backend/tests/unit/test_account_inventory.py::test_default_inventory_dependency_uses_sqlalchemy_uow`
- `backend/tests/unit/test_service_draft_state_machine.py::test_default_confirmation_dependency_uses_sqlalchemy_uow`
- `backend/tests/unit/test_reporting.py::test_default_reporting_dependency_uses_sqlalchemy_uow`

### Scenario 9.2: Successful write APIs commit their UOW

Given:

- A confirmation action API request succeeds.
- Or a report generation API request succeeds.

When:

- The route returns a successful response.

Then:

- The route calls `uow.commit()` before returning.
- For confirmation, service records, execution tickets and audit events are in the same committed unit of work.
- For reports, generated report records, risk events when applicable, and audit events are in the same committed unit of work.
- Permission-denied, state-conflict or validation-failed paths do not claim a successful commit.

Test mapping:

- `backend/tests/unit/test_service_draft_state_machine.py::test_confirmation_api_commits_successful_action`
- `backend/tests/unit/test_reporting.py::test_customer_report_api_commits_generated_report`

## 10. BDD Acceptance

Stage 02 BDD is satisfied only when:

- Each scenario above maps to at least one unit, integration, or E2E test.
- Each test has a command in Stage 02 acceptance checklist.
- No scenario depends on real Telegram or real provider.
- All business results appear in Bitable view API.
