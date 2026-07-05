# Stage 03 Telegram Webhook Ingress Module

## Status

- Document status: active module design
- Scope: Stage 03 真实 Telegram receive-only webhook 入口。
- Current Progress: 2026-07-06 建立模块设计。当前只写文档，不写代码。

## 1. Scope

本模块负责把真实 Telegram Bot API update 安全、幂等地接入后端，并把结果落到数据库、outbox、audit 和多维表格 `telegram_inbox`。

本模块做：

- `POST /telegram/webhook` endpoint。
- Telegram secret token 校验。
- 可选 chat/user allowlist 校验。
- Telegram update payload 解析。
- update 去重。
- 调用消息入库服务。
- 写入消息接收审计。
- 写入 outbox event 供 Redis Streams bridge 后续处理。

本模块不做：

- 不发送 Telegram 回复。
- 不调用 LLM。
- 不执行充值、绑卡、Meta、卡台或 provider 操作。
- 不下载 Telegram 文件。
- 不在 API response 中返回 secret、token 或完整 raw update。

## 2. Inputs

| Input | Source | Required | Notes |
| --- | --- | --- | --- |
| Telegram update JSON | Telegram Bot API webhook | yes | 支持 message 类 update 优先 |
| `X-Telegram-Bot-Api-Secret-Token` | Telegram webhook header | yes in staging | 与 `TELEGRAM_WEBHOOK_SECRET` 比对 |
| `TELEGRAM_ALLOWED_CHAT_IDS` | environment | optional | 开启后仅允许列表内 chat |
| `TELEGRAM_ALLOWED_USER_IDS` | environment | optional | 开启后仅允许列表内 user |

## 3. Outputs

| Output | Destination | Condition |
| --- | --- | --- |
| `messages` row | PostgreSQL | valid and non-duplicate update |
| `outbox_events` row | PostgreSQL | valid message accepted |
| `ops_audit_events` row | PostgreSQL | accepted message, duplicate, rejected security event where safe |
| `telegram_inbox` record | Bitable view projection | accepted message |
| HTTP response | Telegram caller | every request |

## 4. Processing Flow

```text
HTTP request
-> verify secret token
-> parse Telegram update
-> extract update_id/message/chat/user/message_type/text preview
-> check allowlist
-> deduplicate by telegram_update_id
-> resolve preliminary customer binding
-> create message + audit + outbox in one transaction
-> return idempotent response
```

## 5. State Machine

| Current | Event | Next | Notes |
| --- | --- | --- | --- |
| none | valid update accepted | `received` | message row created |
| `received` | outbox row created | `queued` | visible in inbox |
| any | duplicate update | unchanged | idempotent success |
| none | invalid secret | none | no business row |
| none | blocked allowlist | none or security audit only | policy decided in implementation |
| none | malformed payload | none | validation error |

## 6. Security

- Secret token comparison must use constant-time comparison if available.
- Invalid secret must not create business message rows.
- Responses must not echo secret token.
- Logs must not contain Bot Token or webhook secret.
- Allowlist blocked requests must not enter normal business queue.
- Full raw update should not be exposed in `telegram_inbox`.

## 7. Bitable Endpoint

Every accepted message must appear in `telegram_inbox` with at least:

- `telegram_update_id`
- `telegram_chat_id`
- `telegram_user_id`
- `message_type`
- `text_preview`
- `binding_status`
- `processing_status`
- `received_at`

Rejected invalid-secret requests do not create inbox business records. They may create safe security audit records if the implementation has a safe audit path.

## 8. Future Files

| Purpose | File |
| --- | --- |
| Webhook route | `backend/app/api/routes/telegram_webhook.py` |
| Request/response schemas | `backend/app/schemas/telegram_webhook.py` |
| Telegram parsing helpers | `backend/app/services/telegram_update_parser.py` |
| Ingestion service extension | `backend/app/services/telegram_ingestion.py` |
| Config | `backend/app/core/config.py` |
| Tests | `backend/tests/integration/test_stage03_telegram_webhook.py` |

## 9. Tests

Required tests:

- Valid update creates message, outbox, audit and inbox view record.
- Duplicate update is idempotent.
- Invalid secret returns 403 and creates no business row.
- Missing secret in staging fails closed.
- Blocked chat/user does not create normal message.
- Malformed update returns stable error and creates no outbox.
- Error response redacts secret and raw payload.

## 10. Acceptance Criteria

- Webhook works with Telegram-shaped payload.
- Business writes occur only after security validation.
- Duplicate update does not duplicate rows or jobs.
- Every accepted message reaches Bitable `telegram_inbox`.
- No Telegram send, LLM call or provider write occurs.
