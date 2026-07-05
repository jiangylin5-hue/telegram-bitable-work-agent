# Stage 03 Software Design Document

## Status

- Document status: candidate SDD, pending user confirmation
- Scope: Stage 03 真实集成运行时的软件设计
- Current Progress: 2026-07-05 建立 Stage 03 设计草案，聚焦真实 Telegram ingress、worker runtime、queue bridge、provider sandbox gateway、deployment config 和 Bitable view hardening。

## 1. Design Goal

Stage 03 将 Stage 02 的可测内核接入真实运行边界：

```text
Telegram webhook
-> FastAPI route
-> service layer
-> PostgreSQL transaction + outbox
-> durable worker / queue bridge
-> sandbox gateway / dry-run sender
-> execution log / audit
-> Bitable view
```

## 2. Runtime Components

| Component | Responsibility | Stage 03 Boundary |
| --- | --- | --- |
| Telegram Webhook API | 接收真实 Bot API update，校验 secret，入库消息 | 不同步回复客户 |
| Worker Runner | 持续或 bounded 处理 outbox/job | 不绕过 service layer |
| Queue Bridge | 将 committed outbox 交给 Redis/job runtime | 不在 DB commit 前投递 |
| Telegram Sender | dry-run 或 sandbox notification | 默认不真实发送 |
| Provider Gateway | sandbox provider-like execution/readback | 不真实资金/Meta 写入 |
| Migration Rehearsal | 部署级 DB upgrade 演练 | 不打生产库 |
| Bitable View Hardening | limit/order 基础约束 | 不做完整 query builder |

## 3. Data Flow: Telegram To Draft

```text
POST /telegram/webhook
-> verify webhook secret
-> normalize Telegram update
-> Telegram ingestion service
-> messages row
-> ops_audit_events.message_ingested
-> outbox_events.agent.intent_extract
-> worker runner
-> handle_agent_intent_extract
-> service_drafts row
-> ops_audit_events.draft_created
-> /views/telegram_inbox and /views/ai_draft_queue
```

Design rules:

- Duplicate update returns idempotent success.
- Invalid secret returns 403 with no business row.
- Malformed update returns stable validation error and no outbox event.

## 4. Data Flow: Worker And Queue

```text
business transaction commits outbox_events
-> outbox-to-queue bridge reads pending rows
-> Redis/job envelope preserves idempotency_key and trace_id
-> worker claims job
-> handler calls service layer
-> handler records success/retry/dead_letter
-> audit event and Bitable view reflect status
```

Design rules:

- Outbox table remains consistency anchor.
- Redis/job layer is delivery and scheduling layer.
- Worker must be idempotent and safe to rerun.
- Dead letter must be visible through audit and relevant business view.

## 5. Provider Sandbox Gateway

Gateway operations:

- `recharge.execute`
- `readback.balance`
- `card_binding.execute`
- `bm_invite.execute`

Stage 03 implementation:

- Use sandbox/fake adapter.
- Require `execution_ticket` for executable actions.
- Write `execution_logs`, `ops_audit_events` and business status.
- Map provider-like failures to retry/dead_letter/manual_review.

Forbidden:

- Real provider credentials.
- Raw card number/CVV.
- Real funds movement.
- Direct LLM/provider call bypassing gateway.

## 6. Config And Secrets

Required categories:

- `DATABASE_URL`
- `REDIS_URL`
- `APP_ENV`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_SEND_MODE`: `dry_run` / `sandbox` / later `real`
- `PROVIDER_MODE`: `mock` / `sandbox`
- `OPENROUTER_API_KEY` optional until real LLM stage

Rules:

- Tests must not require real secrets.
- Production-like runtime must fail fast if required secrets are missing.
- Secrets are never logged or returned in API errors.

## 7. Bitable View Hardening

Minimum Stage 03 hardening:

- Deterministic ordering by `created_at` when available, otherwise `id`.
- Default `limit`.
- Maximum `limit` cap.
- Permission filtering remains applied before response.

Deferred:

- Full cursor pagination.
- User-defined filters.
- Complex sort builder.

## 8. Acceptance

- Webhook tests prove real-shaped Telegram update reaches Bitable views.
- Worker tests prove durable processing and idempotency.
- Queue tests prove commit-before-enqueue.
- Sandbox provider tests prove ticket-gated execution and failure mapping.
- View tests prove limit/order behavior.
- Migration rehearsal evidence is recorded.

