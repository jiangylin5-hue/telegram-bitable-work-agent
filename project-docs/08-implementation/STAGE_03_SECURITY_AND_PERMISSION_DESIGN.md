# Stage 03 Security And Permission Design

## Status

- Document status: active security design
- Scope: Stage 03 webhook security、allowlist、secret handling、view masking、audit 和真实外部写入边界。
- Current Progress: 2026-07-06 Stage 03 runtime safety defaults、staging fail-fast env validation、webhook secret validation、optional chat/user allowlist、`telegram_inbox` scope filtering/redaction 和 binding resolution audit 已落地并有自动化测试证据；binding admin permission API 和 worker audit 仍待后续任务或后续阶段。

## 1. Security Goal

Stage 03 的安全目标是允许真实 Telegram webhook 进入 staging，同时防止未授权来源、secret 泄露、误发送、误执行和敏感数据落表。

## 2. Trust Boundaries

| Boundary | Trusted Side | Untrusted Side | Control |
| --- | --- | --- | --- |
| Internet to Caddy | staging server | public internet | HTTPS, firewall |
| Caddy to API | internal Docker network | public internet | reverse proxy only |
| Telegram to webhook | valid Telegram request | forged request | secret token validation |
| Webhook to business rows | validated payload | raw payload | schema validation |
| Worker to database | service/UOW | direct mutation | service boundary |
| View to user | permitted fields | sensitive fields | permission/masking |

## 3. Webhook Secret

Rules:

- `TELEGRAM_WEBHOOK_SECRET` is required in staging.
- Request must include `X-Telegram-Bot-Api-Secret-Token`.
- Invalid or missing secret returns forbidden and creates no normal business message.
- Secret is never logged.
- Secret is never returned in API response.
- Secret is stored only in server environment, not in git.

## 4. Allowlist

Allowlist inputs:

- `TELEGRAM_ALLOWED_CHAT_IDS`
- `TELEGRAM_ALLOWED_USER_IDS`

Policy:

- If both lists are empty, allowlist is disabled and secret token remains the primary protection.
- If a list is configured, matching that dimension is required by implementation policy.
- Blocked source must not create normal business message rows.
- Safe blocked-attempt audit may be recorded without raw payload.

## 5. Permission Model

Stage 03 reuses Stage 02 role and field masking principles.

Rules:

- Internal operator roles can see unbound inbox messages.
- Customer-scoped or sales roles can only see messages linked to their permitted customer scope.
- Unbound messages are hidden from customer-scoped actors.
- Telegram chat/user id may be masked for roles that do not need raw ids.
- Binding changes require internal permission and audit.

## 6. External Action Safety

Stage 03 hard disables:

- Telegram real send.
- OpenRouter real LLM.
- Meta/BM/card/recharge provider writes.
- Real funds movement.

Required env defaults:

```text
TELEGRAM_SEND_MODE=dry_run
LLM_ENABLED=false
PROVIDER_MODE=disabled
```

Implementation must treat any attempt to enable those capabilities as out of Stage 03 unless user has created a new confirmed stage or extension.

## 7. Audit Events

Required audit types:

| Event | When |
| --- | --- |
| `telegram.webhook.accepted` | valid message accepted |
| `telegram.webhook.duplicate` | duplicate update ignored idempotently |
| `telegram.webhook.invalid_secret` | invalid secret rejected, if safe to record |
| `telegram.webhook.allowlist_blocked` | blocked source rejected/ignored |
| `telegram.binding.resolved` | customer binding resolved |
| `telegram.binding.unbound` | no binding found |
| `queue.redis.enqueued` | outbox event delivered to Redis |
| `worker.message.processed` | worker success |
| `worker.message.dead_letter` | worker exhausted/fatal failure |

Audit payloads must not include secrets or full raw update.

## 8. Logging

Allowed logs:

- trace id.
- event id.
- internal message id.
- safe error code.
- redacted chat/user id where useful.

Forbidden logs:

- Bot Token.
- webhook secret.
- database password.
- Redis password.
- full raw update with message text unless explicitly redacted.

## 9. Tests

Required tests:

- Missing/invalid secret fails closed in staging mode.
- Invalid secret creates no business row.
- Error response redacts secret.
- Allowlist blocks untrusted source.
- Customer-scoped actor cannot see unbound messages.
- Inbox view hides forbidden fields.
- Stage 03 config prevents real send/LLM/provider by default.

## 10. Acceptance Criteria

- Security checks happen before business writes.
- Secrets never appear in API responses, views or planned logs.
- Permission filtering applies to Stage 03 inbox.
- Real external writes remain disabled.
