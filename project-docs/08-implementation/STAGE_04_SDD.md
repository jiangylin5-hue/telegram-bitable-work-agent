# Stage 04 Software Design Document

## Status

- Document status: active SDD
- Scope: Stage 04 Telegram binding management、test send、intent placeholder、Bitable views 和 staging 验收的软件设计。
- Current Progress: 2026-07-07 SDD scope has been implemented and verified locally plus staging. Tasks 1-10 have evidence: binding management API, Bitable views, no-LLM intent placeholder, restricted test send API/model/client/worker, staging migration `20260706_0011`, real bound inbox update `184365902`, sent test request `05f46883-e4c7-4669-99cb-99a093629f70`, and post-test dry-run safety close.

## 1. Design Goal

Stage 04 在 Stage 03 的真实 Telegram receive-only runtime 上增加三个能力：

```text
Binding operations
-> new inbound message resolves customer
-> intent placeholder boundary
-> restricted test send
-> audit + Bitable evidence
```

核心设计原则：

- 绑定运营是主线。
- Test send 是受控 smoke，不是客户通知。
- Intent placeholder 是后续 Agent/LLM 的接口预留，不调用 LLM，不生成正式 `service_drafts`。
- PostgreSQL 仍是事实层；多维表格 view 是业务操作层；Redis Streams/outbox 只承载异步投递。

## 2. Runtime Components

| Component | Responsibility | Stage 04 Boundary |
| --- | --- | --- |
| Binding Management API | 创建、禁用、查询 Telegram customer binding | 仅内部认证 actor；不做 UI |
| Customer Binding Service | 复用并加固 `chat` / `user` / `chat_user` resolution | 不自动重算历史消息 |
| Telegram Inbox View | 展示 bound/unbound/conflict 和 intent placeholder 状态 | 不暴露 raw secret 或 Bot token |
| Intent Placeholder Service | 为 bound message 写入 intent-ready 状态或 placeholder outbox | 不调用 OpenRouter，不创建正式 `service_drafts` |
| Telegram Send Request Service | 创建和确认 test send request | 只允许 allowlisted test chat |
| Telegram Send Worker | 从 outbox/Redis 处理 confirmed test send | 不发客户群，不发运营群 |
| Bitable View Service | 增加 `telegram_bindings`、`telegram_send_requests`、`telegram_intent_queue` views | 继续按权限和字段脱敏输出 |
| Audit Service | 记录 binding、intent placeholder、send request、send result | 不保存 secrets |

## 3. Data Model Additions

### 3.1 `telegram_customer_bindings` hardening

Stage 03 已有 `telegram_customer_bindings`。Stage 04 不优先新增复杂组织模型，而是围绕现有表补齐操作语义。

Expected fields already present or required:

| Field | Purpose |
| --- | --- |
| `customer_id` | 绑定到客户 |
| `telegram_chat_id` | chat-level binding |
| `telegram_user_id` | user-level binding |
| `binding_scope` | `chat` / `user` / `chat_user` |
| `status` | `active` / `inactive` |
| `label` | 运维可读标签 |
| `created_by` | 创建 actor |
| `created_at` / `updated_at` | 审计时间 |

Stage 04 service rules:

- `chat_user` 优先于 `chat`，`chat` 优先于 `user`。
- 多个 active binding 命中同一优先级时返回 `binding_conflict`。
- inactive binding 不参与解析。
- 新 binding 创建不改写历史消息。
- disable binding 只影响未来消息。

### 3.2 `telegram_send_requests`

新增轻量表，用于 Stage 04 restricted test send smoke。

| Field | Purpose |
| --- | --- |
| `id` | request id |
| `target_chat_id` | Telegram test chat id |
| `message_text` | 待发送文本，限制长度 |
| `status` | `draft` / `pending_confirmation` / `confirmed` / `queued` / `sending` / `sent` / `failed` / `blocked` / `cancelled` |
| `requested_by_actor_type` | 请求者类型 |
| `requested_by_actor_id` | 请求者 id |
| `confirmed_by_actor_type` | 确认者类型 |
| `confirmed_by_actor_id` | 确认者 id |
| `confirmed_at` | 确认时间 |
| `allowlist_snapshot` | 确认时允许发送范围摘要 |
| `telegram_response_summary` | Telegram response 脱敏摘要 |
| `last_error_code` | safe error code |
| `sent_at` | 发送成功时间 |
| `trace_id` | 链路追踪 |
| `created_at` / `updated_at` | 时间戳 |

Rules:

- `target_chat_id` 必须在 `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` 中。
- `status=confirmed` 后才允许写 outbox event。
- worker 发送前必须再次校验 allowlist snapshot 和当前 allowlist。
- Telegram API response 只保存必要摘要，例如 `message_id`、`chat_id`、`date`、`ok`。
- 不保存 Bot token。
- 不作为客户回复或客户通知事实来源。

### 3.3 Intent placeholder fields

Stage 04 可复用 `messages.intent_status`，并新增/约定以下状态：

| Status | Meaning |
| --- | --- |
| `needs_review` | 未绑定或需人工处理 |
| `intent_ready` | 已绑定且可进入后续 intent extraction |
| `intent_pending` | placeholder job 已入队或待处理 |
| `intent_placeholder_recorded` | placeholder 已记录，不代表 LLM 完成 |
| `intent_failed` | placeholder 处理失败 |

Stage 04 不写正式业务结论。任何充值、绑卡、账户、日报意图都只能作为后续 Stage 05 LLM/Agent 的输入候选。

## 4. API Design

### 4.1 Binding Management API

Endpoints:

```text
POST /telegram/bindings
GET /telegram/bindings
POST /telegram/bindings/{binding_id}/disable
```

Rules:

- Actor 必须具备 `manage_telegram_binding` action。
- 第一版只允许 `admin` / `manager`。
- Request 必须包含 `customer_id`、`binding_scope` 和对应 Telegram id。
- 创建和禁用必须写 audit。
- 禁用不存在的 binding 返回 stable error。
- 创建冲突 binding 失败或返回 conflict，不 silently overwrite。

### 4.2 Test Send API

Endpoints:

```text
POST /telegram/send-requests
POST /telegram/send-requests/{request_id}/confirm
```

Rules:

- `POST /telegram/send-requests` 创建 `pending_confirmation` request。
- `confirm` 必须由有权限 actor 执行。
- confirm 时检查 target chat 是否在 `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`。
- confirm 后写 outbox event `telegram.test_send_requested`。
- worker 执行真实 `sendMessage`。

### 4.3 Bitable Views

Stage 04 required views:

| View | Table | Purpose |
| --- | --- | --- |
| `telegram_inbox` | `messages` | 扩展展示 binding / intent placeholder 状态 |
| `telegram_bindings` | `telegram_customer_bindings` | 管理 active/inactive binding |
| `telegram_send_requests` | `telegram_send_requests` | 查看测试发送请求和结果 |
| `telegram_intent_queue` | `messages` | 查看 ready/pending placeholder 消息 |

## 5. Queue And Worker Design

### 5.1 Binding workflow

Binding operations are synchronous database writes:

```text
API request
-> permission check
-> validate binding scope
-> check active uniqueness / conflict
-> write binding
-> audit
-> commit
```

No Redis job is required for binding create/disable.

### 5.2 Intent placeholder workflow

For a newly received bound message:

```text
telegram.message_received worker
-> mark message processed
-> if binding_status = bound and intent_status = unclassified:
     set intent_status = intent_ready
     keep intent_type = null
     audit `telegram.intent_placeholder.ready`
-> audit `telegram.message_processed`
```

Stage 04 intentionally does not create a separate `agent.intent_extract.placeholder` outbox event. The placeholder is a conservative no-LLM state transition inside the existing `telegram.message_received` worker path. A later Stage 05 may add a dedicated Agent/LLM event only after the Agent and LLM design is confirmed.

### 5.3 Test send workflow

```text
send request created
-> pending_confirmation
-> human confirm
-> allowlist check
-> outbox event
-> Redis Streams
-> worker calls Telegram sendMessage
-> update telegram_send_requests
-> audit
```

Failure policy:

- Production-like `restricted_test` missing Bot token or allowlist: runtime validation
  is rejected before API/worker traffic; no request row or outbox event is created.
- Target not allowlisted: `blocked`.
- Telegram API transient failure: retry until max attempts, then `failed`.
- Telegram API permanent failure: `failed`.
- If DB update succeeds but Redis ack fails, rerun must remain idempotent.

## 6. Security Design Summary

Stage 04 opens one real external write path: restricted Telegram test send. Therefore:

- Default `TELEGRAM_SEND_MODE` remains `dry_run` locally.
- Staging may use `TELEGRAM_SEND_MODE=restricted_test` only when `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` is configured.
- Production-like startup must reject unrestricted send modes.
- Worker must never send if target chat is not allowlisted.
- Customer chat ids must not be put in the test send allowlist.
- No customer group send is in scope.
- Every send request must have human confirmation and audit.

## 7. Error Handling

| Failure | Handling |
| --- | --- |
| Binding permission denied | 403 + audit `permission_denied` |
| Binding conflicts with active row | 409 `telegram_binding_conflict` |
| Invalid binding scope | FastAPI/Pydantic 422 validation before service execution |
| Disable missing binding | 404 `telegram_binding_not_found` |
| Test send target not allowlisted | request `blocked` + audit |
| Test send confirm without permission | 403 + audit |
| Missing Bot token/allowlist in production-like restricted test mode | runtime validation rejected before serving |
| Telegram API send fails | retry or `failed` with safe error code |
| Intent placeholder handler sees LLM enabled | fail closed and audit unsafe config |

## 8. Acceptance

Stage 04 SDD is accepted only when implementation proves:

- Binding management API works for create/list/disable with audit.
- Bound new message resolves customer.
- Inactive binding is ignored.
- Conflict does not guess a customer.
- Intent placeholder produces visible status/audit without LLM call.
- Test send request requires confirmation and allowlist.
- Test send reaches allowlisted test chat in staging.
- No customer group send, LLM call, provider write or funds movement occurred.
