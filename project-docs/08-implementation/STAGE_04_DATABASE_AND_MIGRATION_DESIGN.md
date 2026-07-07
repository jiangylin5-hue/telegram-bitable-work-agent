# Stage 04 Database And Migration Design

## Status

- Document status: active database and migration design
- Scope: Stage 04 数据库增量、迁移边界、唯一约束、敏感字段和验收。
- Current Progress: 2026-07-07 `telegram_send_requests` SQLAlchemy model and Alembic revision `20260706_0011` are implemented and verified. Local `alembic upgrade head --sql` reached `20260706_0011`; Tencent Cloud staging rebuilt the Docker image, `alembic heads` showed `20260706_0011`, migration ran `20260706_0010 -> 20260706_0011`, and `alembic current` returned `20260706_0011 (head)`.

## 1. Design Boundary

Stage 04 数据库设计只服务：

- Telegram binding management。
- New-message binding evidence。
- Intent placeholder state。
- Restricted Telegram test send smoke evidence。

Out of scope:

- Customer notification tables。
- Full reply draft system。
- Provider execution tables。
- Production database readiness。
- Multi-tenant `tenant_id`。

## 2. Schema Changes

### 2.1 `telegram_customer_bindings`

Existing Stage 03 table remains the binding source.

Stage 04 expected behavior can be implemented with existing fields:

| Field | Stage 04 Usage |
| --- | --- |
| `customer_id` | target customer |
| `telegram_chat_id` | chat binding |
| `telegram_user_id` | user binding |
| `binding_scope` | `chat` / `user` / `chat_user` |
| `status` | `active` / `inactive` |
| `label` | operator display |
| `created_by` | actor reference |
| `created_at` / `updated_at` | audit timeline |

If implementation discovers a missing `updated_at` from `TimestampMixin`, no extra field is needed. If the table lacks necessary indexes, migration may add additive indexes only.

Required uniqueness:

- active `(binding_scope, telegram_chat_id)` for `chat`;
- active `(binding_scope, telegram_user_id)` for `user`;
- active `(binding_scope, telegram_chat_id, telegram_user_id)` for `chat_user`.

### 2.2 `messages` intent placeholder fields

Stage 04 should reuse existing `messages.intent_status` and `intent_type`.

Allowed Stage 04 `intent_status` additions:

- `intent_ready`
- `intent_pending`
- `intent_placeholder_recorded`
- `intent_failed`

No migration is required if `intent_status` is free text. If check constraints exist in a later schema, update them additively.

### 2.3 `telegram_send_requests`

New table:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid primary key | request id |
| `target_chat_id` | text | sensitive by role; must be allowlisted for real send |
| `message_text` | text | bounded; may be sensitive |
| `status` | text | state machine |
| `requested_by_actor_type` | text | user/system/agent, Stage 04 expects user/system |
| `requested_by_actor_id` | text | actor id |
| `confirmed_by_actor_type` | text nullable | set on confirm |
| `confirmed_by_actor_id` | text nullable | set on confirm |
| `confirmed_at` | timestamptz nullable | set on confirm |
| `allowlist_snapshot` | jsonb nullable | redacted snapshot |
| `telegram_response_summary` | jsonb nullable | safe response summary |
| `last_error_code` | text nullable | safe error |
| `sent_at` | timestamptz nullable | set on success |
| `trace_id` | text indexed | chain tracing |
| `created_at` | timestamptz | required |
| `updated_at` | timestamptz | required |

Status values:

```text
draft
pending_confirmation
confirmed
queued
sending
sent
failed
blocked
cancelled
```

Indexes:

- `trace_id` index。
- `status + created_at` index for operator view。
- optional `target_chat_id + created_at` index for test-send review。

Do not add:

- Bot token。
- webhook secret。
- raw Telegram response。
- customer notification status。

## 3. Transactions

### 3.1 Binding create transaction

```text
permission check
-> validate customer exists
-> validate binding scope
-> check active conflict
-> insert binding
-> audit telegram.binding.created
-> commit
```

### 3.2 Binding disable transaction

```text
permission check
-> load binding
-> set status inactive
-> audit telegram.binding.disabled
-> commit
```

### 3.3 Test send request transaction

```text
permission check
-> create telegram_send_requests pending_confirmation or blocked
-> audit telegram.test_send.requested
-> commit
```

### 3.4 Test send confirm transaction

```text
permission check
-> load request
-> state check
-> allowlist check
-> set confirmed
-> insert outbox event telegram.test_send_requested
-> audit telegram.test_send.confirmed
-> commit
```

### 3.5 Test send worker transaction

```text
load outbox event and send request
-> idempotency check
-> re-check allowlist
-> call Telegram sendMessage
-> update request sent/failed/blocked
-> update outbox processed/dead_letter
-> audit
-> commit
-> ack Redis job
```

If commit succeeds but Redis ack fails, rerun must not send duplicate Telegram messages. Implementation should use request status and outbox idempotency to stop duplicate sends.

## 4. Sensitive Values

Never store:

- Telegram Bot Token。
- webhook secret。
- database password。
- Redis password。
- raw provider keys。
- raw card number / CVV。

Allowed with masking:

- `target_chat_id`。
- `message_text` for test sends。
- Telegram response summary。

Response summary must be safe:

```json
{
  "ok": true,
  "telegram_message_id": 42,
  "chat_id": "7698059919"
}
```

Do not store full Telegram API response if it contains user profile details beyond what is needed.

## 5. Migration Plan

Expected migration steps:

1. Create `telegram_send_requests`.
2. Add indexes for `status`, `trace_id`, and `created_at`.
3. Add additive indexes to `telegram_customer_bindings` only if current indexes are insufficient.
4. Do not alter or backfill historical `messages` for binding changes.
5. Run Alembic offline SQL.
6. Run staging migration before any real test send.

## 6. Tests

Required tests:

- Metadata includes `telegram_send_requests`.
- Alembic offline SQL includes new table.
- Send request state transitions are persisted.
- Binding create/disable persists and audits.
- Historical messages remain unchanged after new binding.
- Duplicate worker processing does not duplicate send.
- Non-allowlisted target remains blocked.

## 7. Acceptance Criteria

- Migration is additive.
- Stage 02 and Stage 03 tests remain passing.
- `telegram_send_requests` has enough fields to prove request, confirmation and send result.
- Sensitive values are not modeled as persisted secrets.
- Staging migration evidence is recorded before real test send.
