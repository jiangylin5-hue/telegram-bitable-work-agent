# Stage 03 Final Acceptance Report

## Status

- Document status: final acceptance report
- Scope: Stage 03 真实 Telegram 收件入口、PostgreSQL Outbox、Redis Streams worker、最小客户绑定、`telegram_inbox`、腾讯云 CVM staging 和安全边界验收。
- Current Progress: 2026-07-06 Stage 03 已完成验收。真实 Telegram 消息已通过 `api.jiangtest1.online` 进入腾讯云 staging 后端，落入 PostgreSQL、outbox、worker audit 和 `telegram_inbox`；Telegram 发送、LLM 和 provider 均保持禁用。

## 1. Result

Stage 03 在已确认范围内通过验收。

验收结论：

- Passed: 真实 Telegram receive-only webhook。
- Passed: 腾讯云 CVM + Caddy HTTPS staging。
- Passed: PostgreSQL migration and persistence。
- Passed: Redis + outbox bridge + worker runtime。
- Passed: Bitable `telegram_inbox` view evidence。
- Passed: Safety locks: no Telegram send, no LLM, no provider。
- Deferred by scope: Telegram send、OpenRouter/LLM、provider execution、Mini App UI、生产发布。

## 2. Staging Evidence

| Item | Evidence |
| --- | --- |
| Date | 2026-07-06 |
| Environment | Tencent Cloud staging |
| Server | `Ubuntu-NaSe`, Ubuntu 24.04.4 LTS |
| Public IP | `43.160.215.224` |
| Domain | `api.jiangtest1.online` |
| Webhook URL | `https://api.jiangtest1.online/telegram/webhook` |
| Telegram bot | `@BitableAgentBot` |
| Webhook setup | `setWebhook` returned `{"ok":true,"result":true,"description":"Webhook was set"}` |
| Webhook info | `url=https://api.jiangtest1.online/telegram/webhook`, `pending_update_count=0`, `ip_address=43.160.215.224` |
| Services | `api`, `caddy`, `outbox-bridge`, `postgres`, `redis`, `worker` running |
| Database | PostgreSQL container healthy |
| Queue | Redis container healthy |
| Migration | Alembic ran through `20260706_0010 Add Stage 03 Telegram customer bindings and inbox fields` |
| Safety env | `TELEGRAM_SEND_MODE=dry_run`, `LLM_ENABLED=false`, `PROVIDER_MODE=disabled` |

No Telegram Bot Token, webhook secret, database password or Redis password is recorded in this report.

## 3. Real Message Evidence

Observed database rows:

| telegram_update_id | binding_status | processing_status | outbox_status | Notes |
| --- | --- | --- | --- | --- |
| `184365901` | `needs_manual_binding` | `processed` | `processed` | Real test message `stage03 webhook test` |
| `184365900` | `needs_manual_binding` | `processed` | `processed` | Real `/start` message |

Observed `telegram_inbox` view:

```text
view_key=telegram_inbox
telegram_update_id=184365901
telegram_chat_id=7698059919
telegram_user_id=7698059919
binding_status=needs_manual_binding
text_preview=stage03 webhook test
processing_status=processed
outbox_status=processed
intent_status=needs_review
trace_id=tg:184365901
```

Observed outbox evidence:

```text
event_type=telegram.message_received
status=processed
attempts=0
```

Observed audit evidence:

```text
message_ingested
telegram.binding.unbound
telegram.message_processed
```

## 4. Exit Gate Review

| Exit Gate | Result | Evidence |
| --- | --- | --- |
| HTTPS receives real Telegram webhook | passed | Telegram `getWebhookInfo` URL and real messages in DB |
| Secret token validation | passed | Invalid secret request returned 403 during staging smoke; `setWebhook` used server webhook secret |
| Effective update creates one message | passed | Real updates `184365900` and `184365901` each created one message row |
| Minimal customer binding | passed | Unbound real chat produced `needs_manual_binding`; binding tests cover bound/conflict paths |
| PostgreSQL Outbox -> Redis Streams -> worker | passed | `outbox_events.status=processed`; audit includes `telegram.message_processed` |
| Bitable endpoint | passed | `/views/telegram_inbox/records?limit=3` returned the real message |
| No Telegram send | passed | `TELEGRAM_SEND_MODE=dry_run`; no send feature in Stage 03 scope |
| No LLM | passed | `LLM_ENABLED=false` |
| No provider writes or funds movement | passed | `PROVIDER_MODE=disabled`; no provider execution code path in Stage 03 |

## 5. Automated Verification

Latest backend code verification after local database default alignment:

```text
pytest tests -q => 124 passed / 17 skipped
alembic upgrade head --sql => reaches 20260706_0010
```

Focused Task 7A runtime verification:

```text
test_stage03_redis_streams_adapter.py => 3 passed
test_stage03_worker_runtime_factory.py => 1 passed
test_stage03_outbox_bridge_runtime_factory.py => 1 passed
Task7A focused/runtime regression => 13 passed
```

Skipped tests:

- 17 existing online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL`.
- They are not Stage 03 staging failures. Task 7 separately verified online PostgreSQL through the Docker Compose staging database and Alembic migration.
- After acceptance, local development defaults were aligned to the user's PostgreSQL setup: `ads_agent` user/database for `DATABASE_URL`, plus `backend/.env.example`. This does not change staging secrets or production scope.

## 6. Not In Scope

The following remain intentionally out of Stage 03:

- Real Telegram reply sending.
- OpenRouter / real LLM calls.
- LangGraph production agent graph.
- Provider sandbox or real provider writes.
- Meta/BM/card/recharge execution.
- Funds movement.
- Telegram Mini App UI.
- Production cutover.

## 7. Remaining Risks

- Server is a single-node staging deployment, not production HA.
- Redis live rehearsal covered the Stage 03 single-message path, not load/concurrency testing.
- Local development database should use `ads_agent`; disposable online smoke tests must use `stage02_online_test` and never point at local development, staging or production databases.
- Production database readiness is not part of Stage 03. Before formal launch, the project needs a separate production DB plan covering backups/PITR, migration approval, least-privilege roles, secret management, monitoring, rollback and data retention.
- Telegram bot token was accidentally pasted in chat during setup; user was instructed to rotate/regenerate and store only in server `.env.stage03`.
- Final server commit was not reprinted in the last evidence command; Docker build/migration/runtime evidence proves deployed code path worked, but future handoff should capture `git rev-parse --short HEAD` during release notes.

## 8. Stage 04 Recommendation

Recommended next stage direction:

1. Add operator-visible customer binding management for Telegram users/chats.
2. Add authenticated internal API/admin guardrails around binding and inbox operations.
3. Decide whether Stage 04 starts with OpenRouter intent extraction, customer reporting automation, or Telegram reply draft/send confirmation.
4. Keep real provider execution, Meta/card/recharge writes and funds movement behind a later confirmation/ticket stage.
