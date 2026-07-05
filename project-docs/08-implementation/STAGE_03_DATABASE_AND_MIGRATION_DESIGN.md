# Stage 03 Database And Migration Design

## Status

- Document status: active database design
- Scope: Stage 03 数据库增量、迁移边界、唯一约束、敏感字段和验收。
- Current Progress: 2026-07-06 数据库/迁移设计已建立并部分落地。已新增 migration `20260706_0010_stage03_customer_bindings.py`，包含 `telegram_customer_bindings`、messages Stage03 inbox fields 和 partial unique indexes；Task5 Redis bridge 和 Task6 worker runtime 复用既有 `outbox_events.status/attempts/available_at/processed_at/dispatched_at/idempotency_key/trace_id` 与 `messages.processing_status/outbox_status/last_error_code/processed_at` 字段，无新增迁移；真实在线 PostgreSQL 验证仍待后续环境。

## 1. Design Boundary

Stage 03 数据库设计只服务真实 Telegram 收件和异步处理闭环。

In scope:

- Telegram update identity and processing fields。
- Minimal Telegram customer binding table。
- Outbox delivery fields if Stage 02 schema lacks Redis delivery state。
- Worker retry/dead letter metadata if Stage 02 schema lacks needed字段。

Out of scope:

- Provider execution tables beyond Stage 02 existing schema。
- Real Telegram send delivery table。
- Full multi-tenant schema。
- Full customer organization membership。
- Card/payment raw sensitive fields。

## 2. Candidate Schema Changes

### 2.1 `messages` Extensions

If existing `messages` table lacks any required Stage 03 fields, add the minimal fields:

| Field | Purpose | Unique / Sensitive |
| --- | --- | --- |
| `telegram_update_id` | update idempotency | unique |
| `telegram_message_id` | Telegram message identity | not globally unique |
| `telegram_chat_id` | source chat | sensitive by role |
| `telegram_user_id` | source user | sensitive by role |
| `message_type` | text/photo/document/other | not sensitive |
| `text_preview` or existing body | view preview | may need masking |
| `binding_status` | bound/unbound/conflict | not sensitive |
| `processing_status` | workflow state | not sensitive |
| `processed_at` | worker timestamp | not sensitive |
| `last_error_code` | safe error code | not sensitive |

Rules:

- `telegram_update_id` is the primary idempotency key for webhook ingestion.
- If `telegram_update_id` already exists from Stage 02, reuse it.
- Do not store full raw update unless explicitly justified and masked from all views; Stage 03 should prefer normalized fields.

### 2.2 `telegram_customer_bindings`

New table if not already present:

| Field | Constraint |
| --- | --- |
| `id` | primary key |
| `customer_id` | foreign key to `customers` |
| `telegram_chat_id` | nullable, indexed |
| `telegram_user_id` | nullable, indexed |
| `binding_scope` | enum/check: `chat`, `user`, `chat_user` |
| `status` | enum/check: `active`, `inactive` |
| `label` | nullable |
| `created_by` | nullable actor reference |
| `created_at` | required |
| `updated_at` | required |

Unique constraints:

- active chat binding uniqueness for `(binding_scope, telegram_chat_id)` when scope is `chat`;
- active user binding uniqueness for `(binding_scope, telegram_user_id)` when scope is `user`;
- active chat_user binding uniqueness for `(binding_scope, telegram_chat_id, telegram_user_id)` when scope is `chat_user`.

If partial indexes are used, migration must include PostgreSQL-specific partial unique indexes.

### 2.3 `outbox_events` Extensions

If existing outbox table does not track Redis delivery, add or standardize:

| Field | Purpose |
| --- | --- |
| `delivery_status` | pending/enqueued/processed/retrying/dead_letter |
| `delivery_attempts` | retry count |
| `last_delivery_error_code` | safe error code |
| `delivered_at` | stream enqueue timestamp |
| `processed_at` | worker completion timestamp |

Rules:

- Do not remove Stage 02 outbox behavior.
- Backfill existing rows to safe default such as `pending` or existing equivalent state.

## 3. Transactions

Webhook ingestion transaction:

```text
insert/update message
-> insert audit event
-> insert outbox event
-> commit
```

Outbox bridge transaction:

```text
select pending event
-> XADD Redis stream
-> mark event enqueued
-> commit status update
```

Worker transaction:

```text
load event/message
-> check idempotency
-> update message processing status
-> write audit
-> update outbox processing status
-> commit
-> XACK Redis job
```

If database commit succeeds but Redis ack fails, worker rerun must remain idempotent.

## 4. Sensitive Values

Never store in Stage 03 tables:

- Telegram Bot Token.
- webhook secret.
- raw card number.
- CVV.
- real provider API keys.

Allowed with masking:

- Telegram chat id.
- Telegram user id.
- Message text preview.

Avoid unless explicitly approved:

- Full raw Telegram update.
- Media file content.

## 5. Migration Plan

Expected migration steps:

1. Add missing `messages` fields.
2. Create `telegram_customer_bindings`.
3. Add outbox delivery fields only if absent.
4. Add indexes for webhook idempotency and binding lookup.
5. Add check constraints for statuses.
6. Run offline SQL generation.
7. Run online migration against staging database before webhook setup.

## 6. Tests

Required tests:

- SQLAlchemy metadata includes new table/fields.
- Alembic offline SQL includes Stage 03 migration.
- Online migration can run on staging-like PostgreSQL.
- Duplicate `telegram_update_id` is prevented.
- Active binding uniqueness is enforced.
- Inactive binding does not block a new active binding if partial index strategy supports it.

## 7. Acceptance Criteria

- Migration is additive and does not break Stage 02 tests.
- New constraints support idempotency and binding correctness.
- Sensitive values are not modeled as persisted fields.
- Staging migration evidence is recorded before real webhook setup.
