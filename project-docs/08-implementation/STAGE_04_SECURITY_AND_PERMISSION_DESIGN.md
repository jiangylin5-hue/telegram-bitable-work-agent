# Stage 04 Security And Permission Design

## Status

- Document status: active security and permission design
- Scope: Stage 04 binding admin permissions、restricted test send、intent placeholder safety、secret handling、view masking 和 audit。
- Current Progress: 2026-07-07 Permission actions, restricted test send runtime validation, view masking, Telegram response redaction, worker allowlist re-check, unauthorized API audits and confirm-time allowlist drift are implemented locally with automated test evidence. Staging secret/allowlist verification remains pending.

## 1. Security Goal

Stage 04 新增两个敏感能力：

- 内部人员可以管理 Telegram 与客户的绑定。
- 系统可以在人工确认后向 allowlisted test chat 真实发送 Telegram 测试消息。

安全目标是允许这些能力完成 staging 验收，同时防止：

- 错绑客户。
- 未授权人员修改绑定。
- 测试发送误发到客户群或运营群。
- Bot token 或 webhook secret 泄漏。
- LLM/provider/资金动作被误启用。

## 2. Permission Actions

Stage 04 新增 action：

| Action | Allowed roles first version | Audit on deny |
| --- | --- | --- |
| `manage_telegram_binding` | `admin`, `manager` | yes |
| `request_test_telegram_send` | `admin`, `manager` | yes |
| `confirm_test_telegram_send` | `admin`, `manager` | yes |

Agent 不允许：

- 管理 binding。
- 自己确认 test send。
- 修改 test send allowlist。
- 执行客户群发送。

## 3. Binding Security

Rules:

- `telegram_chat_id` / `telegram_user_id` 是身份线索，不等同于系统权限。
- Binding create/list/disable 必须先检查 action permission。
- Binding create 必须检查 active conflict，不允许覆盖。
- Binding disable 必须写 audit。
- New binding only affects future messages.
- Unbound and conflict messages remain hidden from customer-scoped actors.

Audit events:

| Event | When |
| --- | --- |
| `telegram.binding.created` | binding created |
| `telegram.binding.disabled` | binding disabled |
| `telegram.binding.create_conflict` | active conflict rejected |
| `permission_denied` | actor lacks action |

## 4. Restricted Test Send Security

Stage 04 real Telegram send is limited to test smoke.

Required config:

```text
TELEGRAM_SEND_MODE=restricted_test
TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=<comma-separated test chat ids>
TELEGRAM_BOT_TOKEN=<server env only>
```

Rules:

- Local default remains `TELEGRAM_SEND_MODE=dry_run`.
- Staging may use `restricted_test` only for Stage 04 test-send rehearsal.
- Startup must reject unrestricted send modes in production-like environments.
- If `TELEGRAM_SEND_MODE=restricted_test`, `TELEGRAM_BOT_TOKEN` must be present in
  server env.
- If `TELEGRAM_SEND_MODE=restricted_test`, `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` must be non-empty.
- Worker must re-check target chat against current allowlist before sending.
- Test send request must be human-confirmed.
- Test send must not accept customer group chat ids unless they are explicitly in test allowlist; Stage 04 policy says customer group chat ids must not be allowlisted.

Forbidden:

- Sending to customer groups.
- Sending to internal ops/finance groups.
- Sending as part of customer reply workflow.
- Sending without `telegram_send_requests`.
- Sending directly from webhook request.

Audit events:

| Event | When |
| --- | --- |
| `telegram.test_send.requested` | request created |
| `telegram.test_send.confirmed` | human confirms |
| `telegram.test_send.blocked` | confirm-time or worker-time allowlist/state block after a request already exists |
| `telegram.test_send.sent` | Telegram API succeeds |
| `telegram.test_send.failed` | Telegram API fails |

## 5. Intent Placeholder Safety

Rules:

- `LLM_ENABLED=false` remains default.
- Stage 04 placeholder must not call OpenRouter.
- Stage 04 placeholder must not create formal `service_drafts`.
- Placeholder audit may state message is ready for future intent extraction.
- It must not claim "intent recognized" or business action success.

Audit events:

- `telegram.intent_placeholder.ready`

Stage 04 does not emit `agent.intent.placeholder_*` events and does not enqueue a dedicated `agent.intent_extract` placeholder job. Those names are reserved for a later Agent/LLM stage only if its source of truth confirms them.

## 6. Secret Handling

Never commit or expose:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` if user treats chat ids as sensitive
- database password
- Redis password

API responses, Bitable views and logs must not include:

- Bot token。
- webhook secret。
- raw Telegram API response with excessive identity details。
- database/Redis credentials。

## 7. View Masking

Sensitive Stage 04 fields:

- `telegram_chat_id`
- `telegram_user_id`
- `target_chat_id`
- `message_text`
- `telegram_response_summary`

Admin/manager may see these in staging if needed for operations. Customer-scoped actors must not see unbound inbox rows or send request rows.

## 8. Tests

Required tests:

- Unauthorized actor cannot create/disable binding.
- Binding conflict is rejected and audited.
- Unauthorized actor cannot request/confirm test send.
- Non-allowlisted target is blocked.
- Runtime validation rejects production-like `restricted_test` without Bot token or
  allowlist before API/worker traffic.
- Test send does not happen before confirmation.
- Test send worker re-checks allowlist.
- Intent placeholder does not call LLM.
- Views do not expose secrets.

## 9. Acceptance Criteria

- Every new write path has permission check.
- Every permission denial writes audit.
- Every real test send has human confirmation and allowlist evidence.
- No customer group send occurs.
- No LLM/provider/funds path is enabled.
