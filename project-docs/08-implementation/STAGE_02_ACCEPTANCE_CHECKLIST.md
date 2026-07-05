# Stage 02 Acceptance Checklist

## Status

- Document status: active acceptance checklist
- Scope: Stage 02 backend kernel, mock Telegram ingestion, Bitable-like view API, confirmation, mock recharge execution, account inventory, customer/company reporting
- Current Progress: 2026-07-05 Stage 02 严格审计继续推进；最新验证：全量测试 83 passed，Alembic offline SQL 包含 `0001` through `0009`，AST check 返回 `AST_OK 92 files`；本轮补齐 confirmation/report 写入型 API 的 UOW commit 边界：成功确认草稿和成功生成日报后必须提交 UOW，测试仍可 dependency override。

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
- Online PostgreSQL migration against a provisioned database.
- Redis Streams production worker.
- Telegram Mini App or web admin UI.

## 2. Verification Commands

Run from repository root unless noted.

| Command | Expected result | Purpose |
| --- | --- | --- |
| `cd backend; pytest tests/integration/test_stage_02_e2e.py -v` | E2E critical path passes | Proves mock Telegram -> draft -> confirmation -> mock recharge -> inventory -> reporting path |
| `cd backend; pytest tests -v` | Full test suite passes | Proves all Stage 02 unit/integration slices still pass together |
| `cd backend; alembic upgrade head --sql` | Offline SQL includes revisions `0001` through `0009` | Proves migrations are ordered and importable without touching a real DB |
| `cd backend; python -c "import ast, pathlib; files=list(pathlib.Path('.').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files), 'files')"` | `AST_OK ... files` | Proves Python files parse without writing `__pycache__` |

## 3. Requirement Checklist

| Requirement | Status | Evidence |
| --- | --- | --- |
| Git repository initialized | passed | `git status --short --branch` returns branch state |
| Backend skeleton and `/health` route | passed | `tests/unit/test_health.py` |
| SQLAlchemy metadata and Alembic env | passed | `tests/unit/test_model_metadata.py`, `tests/unit/test_initial_migration.py` |
| Bitable-like view registry, projection and permissions | passed with offline limitation | `tests/unit/test_bitable_views.py`; records can be projected from injected data source, including account inventory assignment/status fields, recharge collection/execution/readback status fields, and card binding/payment profile views; default `/views` dependency uses `SqlAlchemyBitableViewDataSource` over SQLAlchemy metadata; SQLAlchemy session double covers table-row reads and unknown-table no-op; route-level actor context filters customer-scoped records and masks fields such as `amount` for sales; real PostgreSQL online query remains environment verification |
| Permission and audit kernel | passed | `tests/unit/test_permissions.py`, `tests/unit/test_audit.py`, plus write-path audit/status evidence in `tests/unit/test_telegram_ingestion.py`, `tests/unit/test_service_draft_state_machine.py`, `tests/unit/test_recharge_flow.py`, `tests/unit/test_account_inventory.py`, `tests/unit/test_reporting.py`, `tests/unit/test_outbox.py` |
| Outbox dispatcher semantics | passed | `tests/unit/test_outbox.py` |
| Mock Telegram ingestion | passed | `tests/unit/test_telegram_ingestion.py`, `tests/integration/test_mock_telegram_to_message.py` |
| Mock router to service draft | passed | `tests/unit/test_mock_router_agent.py`; covers recharge, account inventory request, report request and needs_review |
| Human confirmation and execution ticket | passed | `tests/unit/test_service_draft_state_machine.py`; covers confirm, reject, request_more_info, escalate, API reject route, default SQLAlchemy-backed confirmation UOW writing service record, execution ticket and audit event to one session, and route-level successful confirmation committing the UOW |
| LLM adapter and agent run audit | passed | `tests/unit/test_llm_adapters.py`; fake client requires no API key, OpenRouter adapter uses injected HTTP client |
| Recharge mock execution/readback split | passed | `tests/unit/test_recharge_flow.py`, `tests/integration/test_recharge_vertical_slice.py`; covers collection confirmation not equal to execution success plus audit events for recharge record creation, collection creation/confirmation, execution success and readback failure |
| Account inventory assignment, activation and status query | passed | `tests/unit/test_account_inventory.py`, `tests/integration/test_inventory_assignment_slice.py`; covers unused query, assigned customer/current status query, `allocated -> activated` status/audit event, Agent activation denial, and default SQLAlchemy-backed inventory UOW |
| Customer/company reporting | passed | `tests/unit/test_reporting.py`, `tests/integration/test_daily_report_slice.py`; covers customer metrics, stale data, risk audit, date-aligned recharge records in customer report, recharge summary in company report, date-aligned card binding records in customer report, card binding summary in company report, report-generation audit, default SQLAlchemy-backed reporting UOW, route-level successful report generation committing the UOW, and `card_binding_state.status = not_available_in_stage_02` when no binding facts exist |
| Stage 02 critical path E2E | passed after command run | `tests/integration/test_stage_02_e2e.py` |

## 4. Remaining Risks

- Bitable view API now defaults to SQLAlchemy-backed metadata table reads, applies actor record/field permissions in offline route tests, and remains dependency-overridable for tests; real online PostgreSQL query verification has not been run in this environment.
- Reporting now includes date-aligned `recharge_records` and `account_card_bindings` facts. Stage 02 still does not execute real external card binding; it only stores tokenized/masked facts and mock/reporting state.
- Major API route defaults now use SQLAlchemy-backed UOWs, and confirmation/report successful write routes call `uow.commit()` before returning. Many service-level state-machine tests still use in-memory UOWs for deterministic unit coverage; online PostgreSQL transaction behavior remains a later environment verification item.
- Real external writes remain intentionally excluded from Stage 02.
