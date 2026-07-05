# Stage 03 API Contract

## Status

- Document status: active API contract
- Scope: Stage 03 receive-only Telegram webhook and related read/view contracts.
- Current Progress: 2026-07-06 `POST /telegram/webhook` receive-only contract 和 `/views/telegram_inbox/records` Stage03 projection 已按 Stage 03 范围落地并通过 focused tests；Redis Streams/worker 状态推进仍待 Task 5/6。

## 1. Contract Boundary

Stage 03 API 只承载真实 Telegram 收件入口和多维表格视图读取，不提供真实发送、执行、充值或 provider 写入 API。

In scope:

- `POST /telegram/webhook`
- Existing `/views/telegram_inbox/records`
- Existing health/readiness endpoints if required by deployment

Out of scope:

- Telegram send API。
- Customer-facing reply API。
- Recharge execution API changes。
- Provider execution API。
- Full binding admin UI API unless later explicitly确认。

## 2. `POST /telegram/webhook`

### Request Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | yes | Telegram sends JSON update |
| `X-Telegram-Bot-Api-Secret-Token` | yes in staging | Must match configured webhook secret |

### Request Body

The endpoint accepts Telegram Bot API update-like JSON. Stage 03 must support text message updates first:

```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 10,
    "date": 1783276800,
    "chat": {
      "id": -1001234567890,
      "type": "group",
      "title": "Customer Group"
    },
    "from": {
      "id": 998877,
      "is_bot": false,
      "first_name": "Alice",
      "username": "alice"
    },
    "text": "hello"
  }
}
```

Stage 03 may accept non-text metadata, but it does not need to download files.

### Successful Response

New accepted update:

```json
{
  "status": "accepted",
  "message_id": "<internal-message-id>",
  "duplicate": false
}
```

Duplicate update:

```json
{
  "status": "accepted",
  "message_id": "<existing-internal-message-id>",
  "duplicate": true
}
```

### Error Responses

Invalid secret:

```json
{
  "error": {
    "code": "telegram_webhook_forbidden",
    "message": "Forbidden"
  }
}
```

Malformed update:

```json
{
  "error": {
    "code": "telegram_update_invalid",
    "message": "Invalid Telegram update"
  }
}
```

Allowlist blocked:

```json
{
  "error": {
    "code": "telegram_source_not_allowed",
    "message": "Telegram source is not allowed"
  }
}
```

Responses must not include:

- webhook secret。
- Bot token。
- full raw update。
- raw request headers。

## 3. `/views/telegram_inbox/records`

Stage 03 uses the existing Bitable view API pattern.

Expected record fields:

```json
{
  "record_id": "<message-id>",
  "fields": {
    "message_id": "<message-id>",
    "telegram_update_id": 123456789,
    "telegram_chat_id": "-1001234567890",
    "telegram_message_id": "10",
    "telegram_user_id": "998877",
    "customer_id": "<customer-id-or-null>",
    "binding_status": "bound",
    "message_type": "text",
    "text_preview": "hello",
    "processing_status": "processed",
    "outbox_status": "processed",
    "last_error_code": null,
    "intent_status": "unclassified",
    "intent_type": null,
    "received_at": "2026-07-06T00:00:00Z",
    "processed_at": "2026-07-06T00:00:02Z",
    "trace_id": "tg:123456789"
  }
}
```

View contract:

- Supports stable default ordering.
- Applies default limit and max limit.
- Applies existing permission filtering and field masking.
- Does not expose raw payload or secrets.

## 4. Health / Readiness

Stage 03 deployment may use existing health endpoints. If readiness is added later, it should report:

- API process alive.
- Database reachable.
- Redis reachable.

It must not report:

- Telegram Bot Token.
- webhook secret.
- database password.
- Redis password.

## 5. Contract Tests

Required tests:

- Webhook valid request contract.
- Webhook duplicate request contract.
- Webhook invalid secret contract.
- Webhook malformed payload contract.
- Webhook allowlist blocked contract.
- Inbox view field contract.
- Error response redaction.

## 6. Backward Compatibility

- Existing Stage 02 APIs must keep passing tests.
- Stage 03 webhook must not change existing mock Telegram route behavior unless explicitly documented.
- Existing `/views` behavior must remain compatible while adding `telegram_inbox` fields.
