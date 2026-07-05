# Stage 02 Software Design Document

## Status

- Document status: active SDD draft
- Scope: Stage 02 后端内核、Bitable view、权限审计、outbox、mock Telegram、草稿确认、充值、账户库存、日报模块的软件设计
- Current Progress: 2026-07-05 扩展 bounded online PostgreSQL smoke：`tests/integration/test_online_postgres_smoke.py` 使用 disposable PostgreSQL 验证 Alembic online `upgrade head`、mock Telegram API 真实落库与跨 session 幂等、DB-backed `agent.intent_extract` 生成 draft、Bitable view 真实回读、`audit_view` 真实审计投影、`recharge_view` sales actor scoped/masked readback、customer report stale_data/risk_event persistence、confirmation success、Agent confirmation denial、customer report sales scoped-denial 和 company report sales denial 的 API/DB 事务边界、reporting API 提交、business write + outbox event rollback 原子性、inventory/recharge service 状态跃迁、readback failure 的 `customer.reply` mock outbox、database-backed outbox dispatcher success/retry/dead_letter；最新 online smoke 为 17 passed、全量 `pytest tests -v` 102 passed、Alembic offline SQL 到 `20260705_0009`、AST_OK 93 files；完整生产级在线覆盖仍为后续 hardening。

## 1. Design Goal

Stage 02 SDD 的目标是把庞大的业务系统压成一个可运行后端内核。

系统必须先证明这件事：

```text
业务从多维表格出发
-> 通过 API / Agent / worker 改变业务记录
-> 所有结果回到多维表格视图、状态、审计和执行日志
```

Stage 02 不追求一次实现完整产品，而是建立后续所有业务模块共享的底座。

## 2. Runtime Architecture

```text
FastAPI
  -> route layer
  -> service layer
  -> repository layer
  -> SQLAlchemy models
  -> PostgreSQL

Service layer
  -> audit service
  -> permission service
  -> outbox service

Outbox dispatcher
  -> mock agent handlers
  -> mock execution handlers
  -> report handlers

Bitable view API
  -> reads business tables
  -> applies record/field/view permissions
  -> returns table-shaped records
```

## 3. Module Design

### 3.1 App Core Module

Purpose: 提供应用启动、配置、数据库 session、错误模型和健康检查。

Files:

- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `backend/app/core/errors.py`
- `backend/app/api/routes/health.py`

Responsibilities:

- 创建 FastAPI app。
- 注册 routes。
- 读取环境变量。
- 提供 SQLAlchemy session dependency。
- 提供统一错误结构。

Inputs:

- Environment variables。
- HTTP requests。

Outputs:

- API response。
- DB session。

Does not do:

- 不写业务状态。
- 不调用 Agent。
- 不接真实 Telegram/provider。

Acceptance:

- `/health` 返回 `{ "status": "ok" }`。
- 不需要数据库也能启动 health check。

### 3.2 Database And Migration Module

Purpose: 定义 Stage 02 业务事实表和 Alembic migration。

Files:

- `backend/app/models/*.py`
- `backend/alembic/env.py`
- `backend/alembic/versions/*.py`

Core tables:

- `users`
- `telegram_identities`
- `customers`
- `customer_groups`
- `messages`
- `service_drafts`
- `service_records`
- `execution_tickets`
- `execution_logs`
- `ops_audit_events`
- `outbox_events`
- `table_views`
- `view_columns`
- `view_filters`
- `field_permissions`
- `automation_rules`
- `collection_records`
- `recharge_records`
- `payment_profiles`
- `account_card_bindings`
- `account_inventory`
- `account_assignments`
- `account_status_events`
- `account_assets`
- `account_daily_metrics`
- `risk_events`
- `customer_daily_reports`
- `company_daily_reports`

Does not do:

- 不加 `tenant_id`。
- 不保存 raw card / CVV。
- 不设计通用自由建表 EAV 作为事实层。

Acceptance:

- SQLAlchemy metadata 包含 Stage 02 表。
- Alembic migration 可以 upgrade。
- 表名与 `BITABLE_SCHEMA_BLUEPRINT.md` 对齐。

### 3.3 Bitable View Module

Purpose: 把 PostgreSQL 业务事实输出成类似多维表格的 view records。

Files:

- `backend/app/models/bitable.py`
- `backend/app/schemas/views.py`
- `backend/app/services/bitable_views.py`
- `backend/app/services/bitable_views.py` 内的 `SqlAlchemyBitableViewDataSource`
- `backend/app/api/routes/views.py`

View keys:

- `telegram_inbox`
- `ai_draft_queue`
- `recharge_view`
- `account_inventory`
- `payment_profiles`
- `account_card_bindings`
- `customer_daily_reports`
- `company_daily_reports`
- `audit_view`

Responsibilities:

- 根据 `view_key` 找到主表和字段配置。
- 通过 SQLAlchemy metadata 定位物理事实表。
- 通过 SQLAlchemy session 读取表记录并转成 `{ id, fields }` view record。
- 执行 actor record permission：优先读取 `customer_id`，其次读取 `assigned_customer_id`；非全局角色只能看到自己 `customer_ids` 内的记录。
- 执行 field masking：view-defined sensitive fields 永远遮蔽；其余字段再叠加 role-based field permission，例如 sales 不能看到 `amount`。
- 返回统一 view response。

Response shape:

```json
{
  "view_key": "recharge_view",
  "records": [
    {
      "id": "uuid",
      "fields": {
        "status": "pending_confirmation"
      }
    }
  ],
  "trace_id": "trace-id"
}
```

Does not do:

- 不在 view API 中写业务状态。
- 不绕过权限返回敏感字段。
- 不把离线 session-double 测试描述成真实 PostgreSQL 在线验证。

Acceptance:

- 无权限字段不返回或被 mask。
- 未知 view 返回稳定错误。
- Stage 02 每条业务切片都有 view endpoint。
- 默认 `/views` dependency 使用 SQLAlchemy-backed data source。
- `tests/integration/test_online_postgres_smoke.py` 验证 `/views/telegram_inbox/records` 和 `/views/ai_draft_queue/records` 可以从真实 PostgreSQL rows 投影，其中 `ai_draft_queue` 覆盖 DB-backed `agent.intent_extract` 生成的 draft。
- `tests/integration/test_online_postgres_smoke.py::test_online_recharge_view_scopes_and_masks_sales_actor_from_real_rows` 验证 `/views/recharge_view/records` 在真实 PostgreSQL rows 上对 sales actor 执行 customer scope 过滤、`amount` 脱敏，并保留 `collection_status`、`execution_status`、`readback_status`。
- `ai_draft_queue` 保持 Bitable output field `intent_type`，物理读取 `service_drafts.draft_type`，避免视图契约和事实表字段脱节。
- SQLAlchemy-backed data source 对未知物理表返回空结果且不执行查询。
- `/views` route 注入 actor context，并对客户记录和敏感金额字段执行权限过滤。
- `recharge_view` 输出 `collection_status`、`execution_status`、`readback_status`，不得使用不存在于 `recharge_records` 的泛化 `status` 代替真实状态。

### 3.4 Permission And Audit Module

Purpose: 控制谁能看、谁能改、Agent 能读写什么，并记录审计。

Files:

- `backend/app/services/permissions.py`
- `backend/app/services/audit.py`
- `backend/app/api/deps.py`

Actor roles:

- `sales`
- `customer_service`
- `production`
- `finance`
- `manager`
- `admin`
- `agent`

Permission layers:

- record permission by `customer_id`
- field permission
- action permission
- view permission
- agent tool permission

Sensitive fields:

- amount
- balance
- spend
- tokenized payment profile
- failure reason
- raw Telegram text
- execution response summary

Does not do:

- 不做多租户。
- 不让 Telegram identity 直接变成系统权限。
- 不让 Agent 自我确认。

Acceptance:

- 权限拒绝写 audit。
- Agent context 前可执行权限过滤。
- field masking 有单元测试。

### 3.5 Outbox Module

Purpose: 保证数据库事务和异步任务投递一致。

Files:

- `backend/app/models/outbox.py`
- `backend/app/services/outbox.py`
- `backend/app/repositories/outbox.py`
- `backend/app/workers/outbox_dispatcher.py`
- `backend/app/workers/handlers.py`

Outbox statuses:

- `pending`
- `processing`
- `processed`
- `retry`
- `dead_letter`

Stage 02 event types:

- `agent.intent_extract`
- `execution.recharge`
- `readback.balance`
- `customer.reply`
- `report.customer_daily`
- `report.company_daily`

Does not do:

- 不直接使用真实 Redis 前必须先保证 outbox 语义。
- 不在业务 service 事务外创建任务意图。

Acceptance:

- 业务写入和 outbox event 同事务。
- `tests/integration/test_online_postgres_smoke.py::test_online_business_write_and_outbox_event_rollback_atomically` 必须证明真实 PostgreSQL transaction rollback 后业务草稿和 outbox event 都不存在。
- dispatcher 可重试失败事件。
- `SqlAlchemyOutboxRepository` 支持 dispatcher 从真实 `outbox_events` 表读取 ready event、更新 processed/retry/dead_letter 状态。
- `tests/integration/test_online_postgres_smoke.py::test_online_outbox_dispatcher_retries_then_dead_letters_database_backed_event` 必须验证真实 `outbox_events` retry -> dead_letter 状态、attempt counters、last_error 和 `outbox_dead_letter` audit event。
- dead letter 写 audit 或可被 view 查询。

### 3.6 Mock Telegram Ingestion Module

Purpose: 用 mock webhook 代替真实 Telegram，先跑通消息入库到 Agent 识别。

Files:

- `backend/app/schemas/telegram.py`
- `backend/app/services/telegram_ingestion.py`
- `backend/app/api/routes/mock_telegram.py`

Endpoint:

```text
POST /mock/telegram/updates
```

Responsibilities:

- 接收 mock update。
- 幂等写入 `messages`。
- 关联 `customer_groups`。
- 创建 `agent.intent_extract` outbox event。
- DB-backed `agent.intent_extract` handler 必须使用 `SqlAlchemyServiceDraftUnitOfWork` 读取真实 `messages` row、创建 `service_drafts`、更新 `messages.intent_status/intent_type`，并写入 `draft_created` audit event。

Does not do:

- 不接真实 Telegram。
- 不直接创建真实执行。
- 不把所有消息直接变服务。

Acceptance:

- 重复 update 不重复入库。
- 已绑定群消息进入 `telegram_inbox`。
- 未绑定群进入 review 状态或拒绝策略。

### 3.7 Mock Agent Module

Purpose: 先用 deterministic mock agent 验证工具边界和业务状态机，再接 OpenRouter。

Files:

- `backend/app/agents/interfaces.py`
- `backend/app/agents/mock_router.py`
- `backend/app/agents/mock_reporting.py`
- `backend/app/adapters/llm_fake.py`
- `backend/app/adapters/llm_openrouter.py`

Responsibilities:

- 把消息分类为 recharge / account_request / report_request / unknown。
- 输出结构化 draft candidate。
- 生成日报草稿。
- 记录 `agent_runs`。

Does not do:

- 不在 Stage 02 依赖真实 OpenRouter 才能跑测试。
- 不绕过 service layer 创建业务记录。

Acceptance:

- fake model 测试可离线运行。
- OpenRouter adapter 可配置但测试不要求真实 key。

### 3.8 Service Draft And Confirmation Module

Purpose: AI/Telegram 和真实执行之间的安全缓冲层。

Files:

- `backend/app/models/service.py`
- `backend/app/schemas/service_drafts.py`
- `backend/app/services/service_drafts.py`
- `backend/app/services/confirmation.py`
- `backend/app/services/execution_tickets.py`
- `backend/app/api/routes/service_drafts.py`
- `backend/app/api/routes/confirmations.py`

Draft states:

- `draft`
- `needs_more_info`
- `pending_confirmation`
- `rejected`
- `confirmed`
- `manual_review`
- `blocked`

Responsibilities:

- 创建草稿。
- 修改草稿状态。
- 执行人工确认。
- 创建 service record。
- 创建 execution ticket。
- `/service-drafts` 和 `/confirmations` API 默认使用 SQLAlchemy-backed UOW，共用 FastAPI DB session dependency；测试可覆盖为 in-memory UOW。
- `/confirmations/service-drafts/{draft_id}/actions` 的成功写入路径必须在返回响应前调用 `uow.commit()`；权限拒绝、状态冲突或未知 action 不提交。

Does not do:

- 不允许 Agent confirm。
- 不执行真实 provider。
- 不跳过 audit。

Acceptance:

- Agent 无法确认草稿。
- 人类确认后才能创建 ticket。
- ticket 只能使用一次。
- route-level 成功确认会提交 UOW，避免真实数据库 session 写入停留在未提交事务中。

### 3.9 Recharge Module

Purpose: 完成 mock 充值闭环，分离收款确认、充值执行和余额回读。

Files:

- `backend/app/models/recharge.py`
- `backend/app/schemas/recharge.py`
- `backend/app/services/recharge.py`
- `backend/app/adapters/providers_mock.py`

State dimensions:

- collection status
- execution status
- readback status

Responsibilities:

- 创建 collection record。
- 创建 recharge record。
- 财务确认收款。
- 人工确认后创建 execution ticket。
- mock 执行充值。
- 写 execution log。
- mock readback。
- 为 recharge record 创建、collection record 创建、收款确认、执行成功和 readback 失败写 audit event。
- `SqlAlchemyRechargeUnitOfWork` 支持同一 PostgreSQL transaction 内创建 recharge/collection、执行 mock recharge、写 execution log、写 readback outbox event、写 audit event，并可由 Bitable-shaped `recharge_view` 回读状态。

Does not do:

- 不接真实充值 provider。
- 不把收款确认当作充值成功。
- 不把执行成功当作 readback 成功。
- 不在 audit 中保存原始支付凭证或敏感卡信息。

Acceptance:

- 充值 request 可以从 mock Telegram 到 execution log。
- readback failed 可单独显示。
- readback failed 只能在 `execution_status = succeeded` 后标记；否则必须抛出状态错误，不能生成会误导客户的 `customer.reply`。
- readback failed 后必须创建 `customer.reply` mock outbox event，payload 明确表达“充值执行已成功，但余额回读失败，需要人工余额核验”；Stage 02 不做真实 Telegram 发送。
- 关键充值状态写入 `ops_audit_events`，至少覆盖 `recharge_record_created`、`collection_record_created`、`collection_confirmed`、`recharge_execution_succeeded`、`readback_failed`。

### 3.10 Account Inventory Module

Purpose: 管理生产账户、未启用账户、分配给客户、当前状态。

Files:

- `backend/app/models/accounts.py`
- `backend/app/schemas/inventory.py`
- `backend/app/services/account_inventory.py`
- `backend/app/api/routes/inventory.py`

Responsibilities:

- 创建库存账户。
- 查询未启用账户。
- 按 `inventory_status` 和 `assigned_customer_id` 查询库存账户。
- 提出分配建议。
- 人工确认分配。
- 在授权人员确认后将 `allocated` 账户标记为 `activated`。
- 写 `account_status_events`，覆盖 `produced`、`assigned`、`activated`。
- 在 `account_inventory` Bitable-shaped view 中输出 `assigned_customer_id`、`assigned_at`、`inventory_status`、`status_reason`。
- `/inventory/accounts` API 默认使用 SQLAlchemy-backed UOW，共用 FastAPI DB session dependency；测试可覆盖为 in-memory UOW。
- `SqlAlchemyAccountInventoryUnitOfWork` 在 add 后 flush，使同一 PostgreSQL transaction 内的 create -> propose -> confirm 状态跃迁可以读到新建库存账户和分配记录。

Does not do:

- 不无确认分配账户。
- 不允许 Agent 自行确认分配或自行激活账户。
- 不接真实 Meta 账户状态。
- 不根据 LLM 猜测账户是否已启用或可用。
- 不自动判断客户资格。

Acceptance:

- 可以查询哪些账户未启用。
- 可以查询账户分给谁。
- 可以查询当前状态和状态历史。
- 激活必须由 `production`、`manager` 或 `admin` 权限完成。
- `account_inventory` view 能投影客户归属和状态字段，外部账户 ID 仍按敏感字段遮蔽。

### 3.11 Reporting Module

Purpose: 生成客户日报和公司日报。

Files:

- `backend/app/models/reporting.py`
- `backend/app/schemas/reports.py`
- `backend/app/services/reporting.py`
- `backend/app/api/routes/reports.py`

Responsibilities:

- 写入 account daily metrics。
- 生成 customer daily report。
- 生成 company daily report。
- 合并同客户同日期的 `recharge_records` 到客户日报。
- 聚合报告日期内所有 `recharge_records` 到公司日报。
- 合并同客户同日期的 `account_card_bindings` 到客户日报。
- 聚合报告日期内所有 `account_card_bindings` 到公司日报。
- 标记 stale data / missing permission。
- 按权限过滤报告。
- 报告生成和风险事件生成写 audit event。
- `/reports/*` API 默认使用 SQLAlchemy-backed UOW，共用 FastAPI DB session dependency；查询 account metrics、recharge records、card bindings 时必须带 report_date 条件。
- `/reports/*` 的成功写入路径必须在返回响应前调用 `uow.commit()`；权限失败路径只允许提交 `permission_denied` audit，不得提交业务 report rows；其他生成失败或校验失败不得声称成功提交。

Does not do:

- 不编造消耗。
- 不把 stale data 当作 0。
- 不向客户泄露其他客户数据。
- 不编造绑卡结果；客户/日期没有 `account_card_bindings` facts 时，报告必须显式标记不可用。
- 不保存 raw card number、CVV 或完整卡图；`payment_profiles` 只允许 tokenized / masked payment profile。

Acceptance:

- 每个日报数值都有 source 和 freshness。
- 客户日报只包含该客户数据。
- 公司日报仅 manager/admin 可见。
- `tests/integration/test_online_postgres_smoke.py::test_online_customer_report_keeps_stale_spend_unknown_and_persists_risk_event` 验证真实 PostgreSQL API 路径中 stale spend 保持 unknown、生成 `RiskEvent`、写入 `risk_event_created` audit，并能从 `customer_daily_reports` Bitable view 回读。
- 客户日报包含同日同客户充值记录。
- 公司日报包含同日充值总额、执行状态计数和回读状态计数。
- 客户日报包含同日同客户绑卡记录，并遮蔽 `failure_reason`。
- 公司日报包含同日绑卡状态计数。
- 绑卡状态缺少事实源时返回 `not_available_in_stage_02`，不得输出成功/失败等伪事实。
- route-level 成功生成客户/公司日报会提交 UOW，避免真实数据库 session 写入停留在未提交事务中。

## 4. Cross-Cutting Error Handling

所有 service 返回稳定错误类型：

| Error | Meaning | Handling |
| --- | --- | --- |
| `validation_error` | 输入不合法 | 400 |
| `permission_denied` | 权限不足 | 403 + audit |
| `state_conflict` | 状态不允许 | 409 + audit |
| `idempotency_hit` | 幂等命中 | 返回已有记录 |
| `provider_mock_failed` | mock provider 失败 | failed / retry |
| `llm_parse_failed` | Agent 输出不合 schema | needs_review |

## 5. Testing Strategy

测试分层：

- Unit: 纯状态机、权限、字段 masking、outbox 状态。
- Integration: API + DB + service + outbox。
- E2E: mock Telegram -> draft -> confirmation -> execution/report。

Stage 02 不接受只靠手工点击验收。

## 6. SDD Acceptance Criteria

- 每个 Stage 02 模块都有边界、输入、输出、禁止项和验收方式。
- 每个复杂模块在 [Stage 02 Module Index](STAGE_02_MODULE_INDEX.md) 中有索引。
- SDD 不引入 Stage 02 范围外的真实 Telegram/provider/tenant 功能。
