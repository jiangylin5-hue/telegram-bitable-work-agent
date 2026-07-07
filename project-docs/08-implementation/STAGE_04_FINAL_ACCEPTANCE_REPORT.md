# Stage 04 Final Acceptance Report

## Status

- Document status: final acceptance report
- Scope: Stage 04 Telegram inbox operations, customer binding management, no-LLM intent placeholder, restricted test send, Bitable-like views, Tencent Cloud staging evidence and safety close.
- Current Progress: 2026-07-07 Stage 04 has passed final acceptance in the confirmed scope. Local backend suite passed with 172 passed / 17 skipped; Tencent Cloud staging ran commit `360d376`; migration reached `20260706_0011`; real Telegram update `184365902` entered `telegram_inbox` as `bound` and `intent_ready`; restricted test send request `05f46883-e4c7-4669-99cb-99a093629f70` reached `sent`; staging was restored to `TELEGRAM_SEND_MODE=dry_run`.

## 1. Result

Stage 04 在已确认范围内通过验收。

验收结论：

- Passed: Telegram binding management API and audit.
- Passed: `chat_user` API-created binding affects new real Telegram messages only.
- Passed: `telegram_inbox` projects bound message state.
- Passed: no-LLM intent placeholder writes `intent_ready` and audit evidence.
- Passed: `telegram_bindings` and `telegram_send_requests` Bitable-like views project real staging rows.
- Passed: restricted Telegram test send after human confirmation to allowlisted private test chat only.
- Passed: outbox bridge and worker processed the test-send event.
- Passed: safety close restored staging to dry-run and kept LLM/provider disabled.
- Deferred by scope: UI, Mini App, customer group send, customer reply drafts, OpenRouter/LLM, LangGraph production graph, provider writes, funds movement, production database, monitoring and production cutover.

## 2. Staging Evidence

| Item | Evidence |
| --- | --- |
| Date | 2026-07-07 |
| Environment | Tencent Cloud staging |
| Server | `VM-0-10-ubuntu`, Ubuntu 24.04.4 LTS |
| Public IP | `43.160.215.224` |
| Domain | `api.jiangtest1.online` |
| Staging commit | `360d376 Fix Stage04 staging worker send mode` |
| Services | `api`, `caddy`, `outbox-bridge`, `postgres`, `redis`, `worker` running |
| Database | PostgreSQL healthy |
| Queue | Redis healthy |
| Migration | `20260706_0010 -> 20260706_0011`; final `alembic current` returned `20260706_0011 (head)` |
| Runtime during send rehearsal | `TELEGRAM_SEND_MODE=restricted_test`, server-only private test chat allowlist present |
| Runtime after close | `TELEGRAM_SEND_MODE=dry_run`, allowlist cleared, `LLM_ENABLED=false`, `PROVIDER_MODE=disabled` |

No Telegram Bot token, webhook secret, database URL, Redis password or raw allowlist value is recorded in this report.

## 3. Binding Evidence

Staging-only test customer:

```text
customer_id=00000000-0000-4000-8000-000000000404
name=Stage04 Staging Test Customer
```

API-created binding:

```text
POST /telegram/bindings
binding_id=76413f27-7de9-4bb4-8e51-ca0ded8f46eb
binding_scope=chat_user
status=active
target=private test chat/user, redacted
```

Observed `telegram_bindings` view:

```text
view_key=telegram_bindings
binding_id=76413f27-7de9-4bb4-8e51-ca0ded8f46eb
customer_id=00000000-0000-4000-8000-000000000404
binding_scope=chat_user
status=active
```

Observed audit:

```text
telegram.binding.created
```

## 4. Real Message Evidence

After binding creation, a new private Telegram test message was sent to `@BitableAgentBot`.

Observed `telegram_inbox` view:

```text
telegram_update_id=184365902
message_id=caec8652-4495-47e5-8345-3d1c7993a15d
customer_id=00000000-0000-4000-8000-000000000404
binding_status=bound
message_type=text
text_preview=stage04 binding test 2026-07-07
processing_status=processed
outbox_status=processed
intent_status=intent_ready
trace_id=tg:184365902
```

Historical Stage 03 messages remained unchanged as `needs_manual_binding`, proving Stage 04 did not rewrite historical unbound messages.

Observed audit:

```text
message_ingested
telegram.binding.resolved
telegram.intent_placeholder.ready
telegram.message_processed
```

No LLM call was enabled or required.

## 5. Restricted Test Send Evidence

Send request:

```text
POST /telegram/send-requests
request_id=05f46883-e4c7-4669-99cb-99a093629f70
initial_status=pending_confirmation
trace_id=tg-send:22a5d549-9c6a-4ec9-834b-44d745a0029a
```

Human confirmation:

```text
POST /telegram/send-requests/05f46883-e4c7-4669-99cb-99a093629f70/confirm
status=confirmed
queued=true
```

Observed `telegram_send_requests` view:

```text
request_id=05f46883-e4c7-4669-99cb-99a093629f70
status=sent
requested_by_actor_id=stage-02-system
confirmed_by_actor_id=stage-02-system
telegram_response_summary.ok=true
telegram_response_summary.telegram_message_id=4
last_error_code=null
sent_at=2026-07-07T08:49:01.613390Z
```

Observed outbox:

```text
event_type=telegram.test_send_requested
status=processed
aggregate_type=telegram_send_request
aggregate_id=05f46883-e4c7-4669-99cb-99a093629f70
```

Observed audit:

```text
telegram.test_send.requested
telegram.test_send.confirmed
telegram.test_send.sent
```

User confirmation:

```text
Private test chat received: Stage04 restricted test send 2026-07-07
```

## 6. Safety Review

| Safety Item | Result | Evidence |
| --- | --- | --- |
| Customer group send | passed | No customer group was added to allowlist; test target was user-confirmed private test chat |
| Human confirmation | passed | Send request required explicit confirm API before outbox event |
| Worker allowlist re-check | passed | Worker sent only after `restricted_test` and server allowlist were active |
| Safety close | passed | After test, staging returned to `TELEGRAM_SEND_MODE=dry_run` and allowlist was cleared |
| LLM disabled | passed | `LLM_ENABLED=false` before and after rehearsal |
| Provider disabled | passed | `PROVIDER_MODE=disabled` before and after rehearsal |
| Funds movement | passed | No funds/provider/account external execution exists in Stage 04 path |
| Secret hygiene | passed | Secrets and raw allowlist were not written to git or docs |

## 7. Automated Verification

Latest local verification before and during staging close:

```text
cd backend; pytest tests -q => 172 passed / 17 skipped
cd backend; alembic upgrade head --sql => reaches 20260706_0011 and emits COMMIT
git diff --check => no whitespace errors, only Windows LF-to-CRLF warnings
token/private-key scan => no Telegram Bot token, private key or OpenRouter sk- key
```

Skipped tests:

- 17 online PostgreSQL smoke tests remain skipped without `STAGE02_ONLINE_DATABASE_URL`.
- This is not a Stage 04 staging failure because Tencent Cloud PostgreSQL migration and real webhook/test-send paths were manually verified for this phase.
- Future disposable online DB smoke should still be rerun when available.

## 8. Out Of Scope

The following remain intentionally out of Stage 04:

- Web UI / admin page.
- Telegram Mini App.
- Telegram command-based binding management.
- Customer group sending.
- Customer reply drafts and production customer notifications.
- OpenRouter / real LLM calls.
- LangGraph production agent graph.
- Provider sandbox or real provider writes.
- Meta/BM/card/recharge execution.
- Funds movement.
- Production cutover.
- Production database design, backups/PITR, monitoring and alerting.

## 9. Remaining Risks

- Stage 04 staging test customer and binding remain in staging unless a later cleanup task disables or removes them.
- Real future customer bindings still need operator discipline; wrong binding can route future messages to the wrong customer until disabled.
- Bot token must remain server-only; previous chat-token exposure risk means rotation remains recommended if not already done.
- Stage 04 is single-node staging evidence, not production HA or load/concurrency proof.
- `intent_ready` is only a placeholder state, not AI classification.

## 10. Stage 05 Recommendation

Recommended next stage direction:

1. Decide whether Stage 05 should focus on customer binding operations UI, AI intent extraction draft queue, or customer reply draft/send workflow.
2. Keep customer-facing Telegram sends behind explicit confirmation, audit, allowlist/policy checks and dry-run-first staging.
3. Keep OpenRouter/LLM and LangGraph production routing disabled until a new Stage 05 source-of-truth is written and confirmed.
4. Keep Meta/card/recharge/provider writes and funds movement outside the next stage unless the user explicitly chooses that stage and accepts the required execution-ticket safety model.
