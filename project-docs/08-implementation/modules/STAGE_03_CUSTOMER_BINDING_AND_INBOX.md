# Stage 03 Customer Binding And Telegram Inbox Module

## Status

- Document status: active module design
- Scope: Stage 03 最小 Telegram 客户绑定和多维表格 Telegram Inbox 视图。
- Current Progress: 2026-07-06 建立模块设计。当前只写文档，不写代码。

## 1. Scope

本模块负责把 Telegram chat/user 归属到客户，并把入站消息以多维表格形式呈现给操作人员。

本模块做：

- 最小 `telegram_customer_bindings` 设计。
- active/inactive 绑定状态。
- chat/user 到 `customer_id` 的解析。
- unbound 消息进入 `needs_manual_binding` 状态。
- `telegram_inbox` 视图字段、排序、limit 和脱敏。
- 绑定创建/变更/解析审计。

本模块不做：

- 不做完整多租户 `tenant_id`。
- 不做完整客户组织成员体系。
- 不自动创建新客户。
- 不把 Telegram 群成员全部同步为用户表。
- 不基于 LLM 猜测客户。

## 2. Inputs

| Input | Source | Notes |
| --- | --- | --- |
| `telegram_chat_id` | webhook payload | 群聊/私聊核心来源 |
| `telegram_user_id` | webhook payload | 发送人来源 |
| existing customer row | `customers` table | Stage 02 已有客户事实 |
| binding records | new binding table | Stage 03 新增或标准化 |

## 3. Outputs

| Output | Destination |
| --- | --- |
| `customer_id` on message | `messages` |
| `binding_status` | `messages` / Bitable view |
| binding audit | `ops_audit_events` |
| inbox projection | `/views/telegram_inbox/records` |

## 4. Binding Resolution Rules

Resolution order:

1. Exact active `chat_user` binding.
2. Active `chat` binding.
3. Active `user` binding.
4. No match -> `needs_manual_binding`.

Rules:

- Inactive binding is ignored.
- Ambiguous active bindings must not silently pick one; mark as `binding_conflict` or fail into manual review.
- A chat-level binding is enough for Stage 03 customer attribution.
- User-level binding can be used for private messages or known individual operators.

## 5. Data Model

### `telegram_customer_bindings`

| Field | Type Concept | Required | Notes |
| --- | --- | --- | --- |
| `id` | uuid/string | yes | primary key |
| `customer_id` | FK | yes | existing customer |
| `telegram_chat_id` | string/integer | optional | required for chat/chat_user scope |
| `telegram_user_id` | string/integer | optional | required for user/chat_user scope |
| `binding_scope` | enum | yes | `chat`, `user`, `chat_user` |
| `status` | enum | yes | `active`, `inactive` |
| `label` | string | optional | human-readable note |
| `created_by` | actor id | optional | audit reference |
| `created_at` | datetime | yes | created timestamp |
| `updated_at` | datetime | yes | updated timestamp |

Uniqueness:

- One active binding per `(binding_scope, telegram_chat_id)` for chat scope.
- One active binding per `(binding_scope, telegram_user_id)` for user scope.
- One active binding per `(binding_scope, telegram_chat_id, telegram_user_id)` for chat_user scope.

## 6. `telegram_inbox` View

Required fields:

| Field | Purpose | Sensitive |
| --- | --- | --- |
| `message_id` | internal record identity | no |
| `telegram_update_id` | idempotency identity | no |
| `telegram_chat_id` | source chat | role-masked if needed |
| `telegram_user_id` | source user | role-masked if needed |
| `customer_id` | bound customer | scoped by permission |
| `binding_status` | bound/unbound/conflict | no |
| `message_type` | text/photo/document/other | no |
| `text_preview` | truncated preview | may be masked |
| `processing_status` | queued/processed/failed/dead_letter | no |
| `outbox_status` | pending/enqueued/processed/failed | no |
| `last_error_code` | safe error code | no |
| `received_at` | sort timestamp | no |
| `processed_at` | worker timestamp | no |

Forbidden fields in view:

- Bot Token.
- Webhook secret.
- Raw secret header.
- Full raw Telegram update.
- Raw payment/card/provider data.

## 7. Permissions

- Internal operator can view all inbox rows allowed by current Stage 02 role model.
- Sales/customer-scoped actor can only view records linked to permitted customer scope.
- Unbound messages should be visible only to internal roles that can perform binding or triage.
- Binding creation/change requires internal operator permission.
- Binding changes must write audit.

## 8. Future Files

| Purpose | File |
| --- | --- |
| Binding model | `backend/app/models/telegram.py` or dedicated binding model |
| Binding migration | `backend/alembic/versions/<revision>_stage03_telegram_customer_bindings.py` |
| Binding service | `backend/app/services/customer_binding.py` |
| View projection | `backend/app/services/bitable_views.py` |
| Tests | `backend/tests/integration/test_stage03_customer_binding.py` |
| View tests | `backend/tests/unit/test_stage03_telegram_inbox_view.py` |

## 9. Failure Handling

| Failure | Handling |
| --- | --- |
| No binding | message accepted, `needs_manual_binding` |
| Inactive binding | treat as unbound |
| Conflicting binding | mark conflict or manual review, no automatic customer attribution |
| Missing customer row | binding invalid, audit and manual review |
| Unauthorized actor reads row | filtered or masked by permission service |

## 10. Tests

Required tests:

- Bound chat resolves customer.
- Bound user resolves customer.
- Inactive binding ignored.
- Unbound message visible with `needs_manual_binding`.
- Conflicting binding does not silently choose customer.
- Inbox view hides forbidden fields.
- Inbox view applies role/customer scope.
- Inbox view applies stable order and limit.

## 11. Acceptance Criteria

- Incoming Telegram messages can be attributed when binding exists.
- Unbound messages remain visible for manual handling.
- No customer is guessed without binding.
- Every accepted message has a Bitable inbox endpoint.
- Sensitive Telegram and secret data are not exposed.
