# Stage 03 Software Design Document

## Status

- Document status: active SDD (confirmed by user 2026-07-06)
- Scope: Stage 03 真实 Telegram 收件入口、最小客户绑定、Redis Streams worker、多维表格 Telegram Inbox 和腾讯云 staging 运行时的软件设计。
- Current Progress: 2026-07-06 已进入 Stage 03 代码实施。Runtime config、Telegram parser 和 receive-only webhook route 已按本设计落地；customer binding、`telegram_inbox` projection、Redis Streams bridge、worker runtime 和腾讯云 staging rehearsal 仍待后续任务。

## 1. Design Goal

Stage 03 把 Stage 02 的 mock/sandbox 后端内核接入真实 Telegram 收件入口和 staging 运行时。核心路径是：

```text
Telegram Bot API
-> Tencent Cloud CVM
-> Caddy HTTPS
-> FastAPI /telegram/webhook
-> Telegram ingestion service
-> PostgreSQL messages + audit + outbox_events
-> Outbox to Redis Streams bridge
-> Redis Streams worker
-> customer binding resolution + message registration
-> Bitable telegram_inbox view
```

设计目标是形成第一个可部署、可联调、可验收的真实消息入口闭环。Stage 03 不追求“智能化”，不调用 LLM，不执行真实业务动作，也不真实回复客户。

## 2. Runtime Components

| Component | Responsibility | Stage 03 Boundary |
| --- | --- | --- |
| Caddy | TLS 自动申请、续期和 HTTPS 反向代理 | 不承载业务逻辑，不记录 secrets |
| FastAPI Webhook API | 接收 Telegram update、校验 secret/allowlist、调用 ingestion service | 不发送 Telegram 回复，不调用 LLM |
| Telegram Parser | 从 update 中提取 update/message/chat/user/text/file metadata | 不保存 raw token，不暴露完整 raw payload 到视图 |
| Customer Binding Service | 根据 chat/user 映射 customer | 只做最小绑定，不做完整多租户成员体系 |
| PostgreSQL Outbox | 业务事务后的异步事件真源 | 不被 Redis 替代 |
| Redis Streams Bridge | 把 committed outbox 事件投递到 Redis Streams | 不在事务提交前投递 |
| Worker Runtime | 消费 Redis Streams，处理消息登记状态和审计 | 不绕过 service/UOW，不调用外部 provider |
| Bitable View Service | 投影 `telegram_inbox` 视图 | 不暴露 secret、token、完整 raw update |
| Audit Service | 记录安全、入库、队列、处理、失败事件 | 不把失败伪装成成功 |

## 3. Data Model Additions

Stage 03 预计新增或加固的数据对象如下。具体字段以实现阶段迁移为准，但不得偏离此设计边界。

### 3.1 `telegram_customer_bindings`

Purpose:

- 把 Telegram chat/user 与客户记录关联起来。
- 让真实消息能进入客户维度的多维表格视图。

Key fields:

| Field | Purpose | Constraint / Sensitivity |
| --- | --- | --- |
| `id` | binding 主键 | UUID 或数据库主键 |
| `customer_id` | 关联客户 | foreign key to customers |
| `telegram_chat_id` | Telegram chat id | unique when active with binding type |
| `telegram_user_id` | Telegram user id | optional；可能为空 |
| `binding_scope` | `chat` / `user` / `chat_user` | stable enum |
| `status` | `active` / `inactive` | inactive 不用于自动归属 |
| `created_by` | 创建人或系统 actor | audit reference |
| `created_at` / `updated_at` | 时间戳 | required |

Unique rule:

- 同一 active `telegram_chat_id` 在同一 binding scope 下只能绑定一个 customer。
- 如果后续需要多租户或多品牌隔离，必须另开阶段引入 `tenant_id`。

### 3.2 Message Processing Fields

Stage 03 可以在现有 `messages` 模型上增加或标准化：

| Field | Purpose |
| --- | --- |
| `telegram_update_id` | Telegram update 去重 |
| `telegram_message_id` | Telegram message identity |
| `telegram_chat_id` | chat source |
| `telegram_user_id` | sender source |
| `customer_id` | 绑定解析结果 |
| `binding_status` | `bound` / `needs_manual_binding` / `blocked_by_allowlist` |
| `processing_status` | `received` / `queued` / `processing` / `processed` / `failed` / `dead_letter` |
| `message_type` | `text` / `photo` / `document` / `other` |
| `received_at` | Telegram message received time |

Sensitive rules:

- 不在 Bitable view 中展示 webhook secret、Bot token、完整 raw update。
- 文件、图片、语音等媒体 Stage 03 只登记 metadata，不下载和持久化原始文件。

## 4. API Design

### 4.1 `POST /telegram/webhook`

Input:

- Telegram Bot API update payload。
- Header: `X-Telegram-Bot-Api-Secret-Token`。

Processing:

1. Verify webhook secret token.
2. Parse update into supported message shape.
3. Check optional allowlist.
4. Deduplicate by `telegram_update_id`.
5. Resolve customer binding if available.
6. Insert or reuse message record.
7. Write `ops_audit_events`.
8. Write `outbox_events.telegram.message_received` or equivalent.
9. Return idempotent success.

Responses:

| Case | Response | Business Row |
| --- | --- | --- |
| Valid new update | `200 accepted` | create message + audit + outbox |
| Duplicate update | `200 duplicate_ignored` or `200 accepted` | no duplicate message |
| Invalid secret | `403 forbidden` | no business message |
| Blocked allowlist | `403 forbidden` or `202 ignored` by policy | audit only |
| Malformed payload | `422 invalid_update` | no outbox |

No response may include secret values or full raw update.

## 5. Queue And Worker Design

### 5.1 Outbox To Redis Streams

PostgreSQL remains the consistency anchor:

```text
business transaction commits
-> outbox_events row is visible
-> bridge reads pending outbox events
-> XADD redis stream with event_id/trace_id/idempotency_key
-> mark outbox delivery state
```

Redis Stream naming:

- `tg_stage03:events` for staging, or environment-prefixed equivalent.
- Consumer group: `telegram-message-workers`.
- Job payload must include `event_id`, `event_type`, `trace_id`, `idempotency_key`, `message_id`.

Rules:

- A rolled-back transaction must never produce a Redis job.
- Re-bridging the same outbox event must not create duplicate business effects.
- Redis delivery failure keeps the outbox event pending or retryable.

### 5.2 Worker Runtime

Worker responsibilities:

- Claim Redis Streams job.
- Load event and related message through service/UOW.
- Mark processing status.
- Apply rule-based message registration.
- Resolve or re-check customer binding.
- Write audit event.
- Ack successful job.
- Retry transient failure.
- Move exhausted or invalid jobs to dead letter.

Worker forbidden behavior:

- No direct SQL string writes outside repository/service layer.
- No Telegram send.
- No LLM call.
- No provider execution.
- No hidden success when handler failed.

## 6. Rule-Based Message Registration

Stage 03 rule-based processing is intentionally conservative:

| Input Condition | Result |
| --- | --- |
| bound chat/user | `binding_status = bound`, set `customer_id` |
| unbound chat/user | `binding_status = needs_manual_binding` |
| allowlist blocked | do not create normal business message; write security audit |
| text message | store text body after length and masking policy |
| non-text message | store supported metadata, set `message_type` |

Stage 03 does not infer recharge, finance, account inventory or card-platform intent through LLM. If a simple deterministic keyword is recorded, it must remain metadata only and cannot trigger execution.

## 7. Bitable View Design

### 7.1 `telegram_inbox`

Required fields:

| Field | Meaning |
| --- | --- |
| `message_id` | internal message id |
| `telegram_update_id` | update identity |
| `telegram_chat_id` | chat source, masked if needed by role |
| `telegram_user_id` | sender source, masked if needed by role |
| `customer_id` | resolved customer |
| `binding_status` | bound / needs_manual_binding / blocked |
| `message_type` | text/photo/document/other |
| `text_preview` | masked, truncated content preview |
| `processing_status` | received/queued/processing/processed/failed/dead_letter |
| `outbox_status` | pending/enqueued/processed/failed |
| `last_error_code` | safe error code |
| `received_at` | received timestamp |
| `processed_at` | worker processed timestamp |

View rules:

- Default deterministic order: newest first by `received_at`, fallback by `id`.
- Default limit and max limit must be enforced.
- Role-based field masking from Stage 02 remains applied.
- Raw payload and secret fields are never returned.

## 8. Deployment Design

Stage 03 staging runtime:

```text
Tencent Cloud CVM
-> Docker Compose
   -> caddy
   -> api
   -> worker
   -> postgres
   -> redis
```

External endpoint:

```text
https://<stage03-subdomain>/telegram/webhook
```

Detailed deployment design is maintained in [Stage 03 Tencent Cloud Staging Deployment](STAGE_03_TENCENT_CLOUD_STAGING_DEPLOYMENT.md).

## 9. Error Handling

| Failure | Handling |
| --- | --- |
| Invalid webhook secret | reject, no business message, security audit if safe |
| Allowlist blocked | reject or ignore by policy, no normal message row |
| Duplicate update | idempotent success, no duplicate outbox |
| Redis unavailable | keep outbox pending/retryable |
| Worker handler error | retry with count and safe error code |
| Exhausted retry | dead letter + audit + Bitable status |
| Unknown payload type | store metadata or reject by supported-type policy |

## 10. Acceptance

Stage 03 SDD is accepted only when implementation proves:

- Valid Telegram-shaped payload reaches `telegram_inbox`.
- Invalid secret creates no business row.
- Duplicate update is idempotent.
- Customer binding and unbound states are visible in Bitable view.
- Committed outbox event reaches Redis Streams once from a business-effect perspective.
- Worker can process and retry safely.
- Tencent Cloud staging can receive a real webhook after user confirms external configuration.
- No real Telegram sending, LLM call, provider write or funds movement occurred.
