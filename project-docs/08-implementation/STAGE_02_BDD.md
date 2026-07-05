# Stage 02 Behavior Driven Development

## Status

- Document status: active BDD draft
- Scope: Stage 02 可验收业务行为、Gherkin 风格场景、测试映射
- Current Progress: 2026-07-05 补充 API UOW 持久化行为验收：`/service-drafts`、`/inventory/accounts`、`/confirmations/service-drafts/{draft_id}/actions`、`/reports/*` 默认使用 SQLAlchemy-backed UOW 和 DB session；confirmation/report 写入型 API 成功路径必须提交 UOW；单元/集成测试可 dependency override 为 in-memory UOW。

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

### Scenario 2.2: Duplicate Telegram update is idempotent

Given:

- A mock Telegram update was already ingested.

When:

- The same update is submitted again.

Then:

- No second `messages` record is created.
- No duplicate `agent.intent_extract` outbox event is created.
- API returns idempotent success.

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

### Scenario 6.2: Stale data is explicit

Given:

- An account metric has stale `freshness_at`.

When:

- Customer report is generated.

Then:

- Report marks data as `stale_data`.
- Report does not convert missing or stale spend into zero.
- Risk event creation writes audit evidence.

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
