# Stage 04 API Contract

## Status

- Document status: active API contract
- Scope: Stage 04 binding management API、restricted test send API、intent placeholder views 和相关 Bitable-like view contracts。
- Current Progress: 2026-07-07 Binding management API, send request API and Stage04 view contracts are implemented locally and mapped to the local acceptance audit. Focused Stage04 API/view tests and the full backend suite have current evidence in `STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md`; staging API evidence remains pending.

## 1. Contract Boundary

In scope:

- `POST /telegram/bindings`
- `GET /telegram/bindings`
- `POST /telegram/bindings/{binding_id}/disable`
- `POST /telegram/send-requests`
- `POST /telegram/send-requests/{request_id}/confirm`
- Existing `POST /telegram/webhook`
- Existing `/views/{view_key}/records` with new Stage 04 views

Out of scope:

- Customer-facing reply API。
- Telegram command management。
- Mini App API。
- OpenRouter / LangGraph API。
- Provider execution API。
- Customer group broadcast API。

## 2. Authentication And Actor

Stage 04 uses the existing internal actor/permission pattern. Implementation may continue with test/system actor dependency while adding explicit action checks.

Required actions:

| Action | Purpose | First allowed roles |
| --- | --- | --- |
| `manage_telegram_binding` | create/list/disable bindings | `admin`, `manager` |
| `request_test_telegram_send` | create test send request | `admin`, `manager` |
| `confirm_test_telegram_send` | approve real test send | `admin`, `manager` |

Unauthorized actions must return 403 and write `permission_denied` audit.

## 3. Binding API

### 3.1 `POST /telegram/bindings`

Request:

```json
{
  "customer_id": "00000000-0000-0000-0000-000000000001",
  "binding_scope": "chat_user",
  "telegram_chat_id": "1001",
  "telegram_user_id": "2002",
  "label": "Alice test private chat"
}
```

Validation:

- `binding_scope` must be `chat`, `user` or `chat_user`.
- `chat` requires `telegram_chat_id`.
- `user` requires `telegram_user_id`.
- `chat_user` requires both.
- `customer_id` must exist.
- Active uniqueness/conflict must be checked before insert.

Unknown customer behavior:

- If `customer_id` does not exist, the current API returns FastAPI 404 `detail`
  with the missing customer id.
- No `telegram_customer_bindings` row is created.
- No conflict or create audit is written, because the binding never reaches a
  business state transition.
- A custom stable error code such as `telegram_binding_customer_not_found` is
  not part of the confirmed Stage 04 contract yet; adding it would be an API
  contract change and should be confirmed first.

Success response:

```json
{
  "status": "created",
  "binding_id": "<uuid>",
  "customer_id": "<uuid>",
  "binding_scope": "chat_user"
}
```

Conflict response:

```json
{
  "error": {
    "code": "telegram_binding_conflict",
    "message": "Active Telegram binding already exists"
  }
}
```

### 3.2 `GET /telegram/bindings`

Permission:

- Actor must have `manage_telegram_binding`.
- Unauthorized actor returns 403 and writes `permission_denied` audit.
- Successful list is read-only and does not write audit.

Query params:

| Param | Required | Purpose |
| --- | --- | --- |
| `customer_id` | no | filter by customer |
| `telegram_chat_id` | no | filter by chat |
| `telegram_user_id` | no | filter by user |
| `status` | no | `active` / `inactive` |

Response:

```json
{
  "bindings": [
    {
      "binding_id": "<uuid>",
      "customer_id": "<uuid>",
      "binding_scope": "chat",
      "telegram_chat_id": "1001",
      "telegram_user_id": null,
      "status": "active",
      "label": "Customer group",
      "created_at": "2026-07-06T00:00:00Z",
      "updated_at": "2026-07-06T00:00:00Z"
    }
  ]
}
```

### 3.3 `POST /telegram/bindings/{binding_id}/disable`

Request:

```json
{
  "reason": "wrong customer selected"
}
```

Success response:

```json
{
  "status": "disabled",
  "binding_id": "<uuid>"
}
```

## 4. Test Send API

### 4.1 `POST /telegram/send-requests`

Request:

```json
{
  "target_chat_id": "7698059919",
  "message_text": "Stage04 test send smoke"
}
```

Rules:

- Creates a request; does not send Telegram message.
- Target may be validated early against allowlist and blocked immediately.
- Text length should be bounded by implementation, recommended max 1000 chars for Stage 04.

Success response:

```json
{
  "status": "pending_confirmation",
  "request_id": "<uuid>",
  "trace_id": "tg-send:<uuid>"
}
```

Blocked response:

```json
{
  "status": "blocked",
  "request_id": "<uuid>",
  "error_code": "telegram_test_send_target_not_allowlisted"
}
```

### 4.2 `POST /telegram/send-requests/{request_id}/confirm`

Request:

```json
{
  "confirm": true
}
```

Processing:

1. Check actor can `confirm_test_telegram_send`.
2. Check request status is `pending_confirmation`.
3. Check target chat is allowlisted.
4. Write `confirmed_by`, `confirmed_at`, `allowlist_snapshot`.
5. Set `status = confirmed`.
6. Write outbox event `telegram.test_send_requested`.

Success response:

```json
{
  "status": "confirmed",
  "request_id": "<uuid>",
  "queued": true
}
```

## 5. Bitable Views

### 5.1 `/views/telegram_bindings/records`

Expected fields:

```json
{
  "record_id": "<binding-id>",
  "fields": {
    "binding_id": "<binding-id>",
    "customer_id": "<customer-id>",
    "binding_scope": "chat_user",
    "telegram_chat_id": "1001",
    "telegram_user_id": "2002",
    "status": "active",
    "label": "Alice test private chat",
    "created_by": "manager:alice",
    "created_at": "2026-07-06T00:00:00Z",
    "updated_at": "2026-07-06T00:00:00Z"
  }
}
```

### 5.2 `/views/telegram_send_requests/records`

Expected fields:

```json
{
  "record_id": "<request-id>",
  "fields": {
    "request_id": "<request-id>",
    "target_chat_id": "7698059919",
    "status": "sent",
    "requested_by_actor_id": "manager-1",
    "confirmed_by_actor_id": "manager-2",
    "telegram_response_summary": {
      "ok": true,
      "telegram_message_id": 42
    },
    "last_error_code": null,
    "sent_at": "2026-07-06T00:00:10Z",
    "trace_id": "tg-send:<uuid>"
  }
}
```

### 5.3 `/views/telegram_intent_queue/records`

Expected fields:

```json
{
  "record_id": "<message-id>",
  "fields": {
    "message_id": "<message-id>",
    "customer_id": "<customer-id>",
    "binding_status": "bound",
    "intent_status": "intent_ready",
    "intent_type": null,
    "processing_status": "processed",
    "received_at": "2026-07-06T00:00:00Z",
    "trace_id": "tg:<update-id>"
  }
}
```

## 6. Error Contract

Stable error codes:

| Code | HTTP | Meaning |
| --- | --- | --- |
| FastAPI validation error | 422 | scope/id combination invalid before service execution |
| FastAPI HTTPException detail | 404 | `customer_id` does not exist before binding creation |
| `telegram_binding_conflict` | 409 | active binding already exists |
| `telegram_binding_not_found` | 404 | binding id missing |
| `telegram_send_request_not_found` | 404 | request id missing |
| `telegram_send_request_invalid_state` | 409 | confirm/send from wrong state |
| `telegram_test_send_target_not_allowlisted` | 200 blocked or 409 on confirm | target not allowed |
| `permission_denied` | 403 | actor lacks action permission |

No error response may include Bot token, webhook secret, Redis/database credentials or full Telegram API response.

Runtime config failures are not API business errors. In production-like environments,
`TELEGRAM_SEND_MODE=restricted_test` without `TELEGRAM_BOT_TOKEN` or a non-empty
`TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` must fail runtime validation before the API or
worker serves traffic. This path does not create a `telegram_send_requests` row,
outbox event or stable API error code.

## 7. Backward Compatibility

- Existing Stage 03 webhook contract remains valid.
- Existing `/views/telegram_inbox/records` remains compatible while adding new intent fields.
- Stage 02 mock Telegram behavior must continue passing tests.
- Real Telegram send remains unavailable except through Stage 04 restricted test send request flow.
