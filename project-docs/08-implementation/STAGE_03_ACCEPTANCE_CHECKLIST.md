# Stage 03 Acceptance Checklist

## Status

- Document status: active acceptance checklist (confirmed by user 2026-07-06)
- Scope: Stage 03 文档、真实 Telegram 收件入口、Redis Streams worker、多维表格 Telegram Inbox 和腾讯云 staging 验收。
- Current Progress: 2026-07-06 Stage 03 已完成真实腾讯云 staging 验收。Task 1-7A 自动化验证通过；Task 7 真实 staging 验收通过：Caddy HTTPS、FastAPI、PostgreSQL、Redis、outbox bridge、worker、Telegram `setWebhook`、真实消息入 `telegram_inbox`、outbox processed 和 audit evidence 均有记录。全量 backend suite 最新代码证据为 124 passed / 17 skipped；最终报告见 `STAGE_03_FINAL_ACCEPTANCE_REPORT.md`。

## 1. Acceptance Boundary

Stage 03 验收：

- Stage 03 文档包完整且互相一致。
- Tencent Cloud CVM staging 部署方案明确。
- Caddy HTTPS 入口方案明确。
- Receive-only Telegram webhook。
- Webhook secret token validation。
- Optional chat/user allowlist。
- Minimal Telegram customer binding。
- PostgreSQL Outbox to Redis Streams bridge。
- Durable Redis Streams worker。
- Bitable `telegram_inbox` view。
- Deployment rehearsal evidence。

Stage 03 不验收：

- Real Telegram send。
- OpenRouter / real LLM。
- LangGraph production graph。
- Provider sandbox gateway。
- Real Meta/BM/card/recharge writes。
- Real funds movement。
- Telegram Mini App UI。
- Production cutover。
- Kubernetes。

## 2. Documentation Acceptance For Initial Docs Batch

初始文档批次已经完成并提交；当前 Stage 03 已转入代码实施。以下表格保留初始文档批次的验收证据，后续代码验收以第 4 节为准。

| Requirement | Status | Evidence |
| --- | --- | --- |
| Stage 03 decisions recorded | passed | `STAGE_03_SOURCE_OF_TRUTH.md` §1.1 |
| Stage 03 implementation plan rewritten | passed | `STAGE_03_BACKEND_INTEGRATION_PLAN.md` |
| Stage 03 SDD rewritten | passed | `STAGE_03_SDD.md` |
| Stage 03 BDD rewritten with test mapping | passed | `STAGE_03_BDD.md` |
| Stage 03 module index exists | passed | `STAGE_03_MODULE_INDEX.md` |
| Complex module docs exist | passed | `modules/STAGE_03_TELEGRAM_WEBHOOK_INGRESS.md`; `modules/STAGE_03_CUSTOMER_BINDING_AND_INBOX.md`; `modules/STAGE_03_REDIS_STREAMS_WORKER.md` |
| API contract exists | passed | `STAGE_03_API_CONTRACT.md` |
| Database/migration design exists | passed | `STAGE_03_DATABASE_AND_MIGRATION_DESIGN.md` |
| Security/permission design exists | passed | `STAGE_03_SECURITY_AND_PERMISSION_DESIGN.md` |
| Test plan exists | passed | `STAGE_03_TEST_PLAN.md` |
| Tencent Cloud staging deployment doc exists | passed | `STAGE_03_TENCENT_CLOUD_STAGING_DEPLOYMENT.md` |
| Operations runbook exists | passed | `STAGE_03_OPERATIONS_RUNBOOK.md` |
| Risk register exists | passed | `STAGE_03_RISK_REGISTER.md` |
| Stage 03 progress updated | passed | `STAGE_03_PROGRESS.md` |
| Index docs updated | passed | `README.md`, `project-docs/README.md` |
| No backend code changed in docs-only batch | passed | `git status --short` shows only `project-docs/` changes |
| Old local-only / pending-choice active-scope contradictions removed | passed | `rg -n "本地 docker compose|本地长生命周期|收发都真实|03\\.6|pending user decision" project-docs/08-implementation -g "STAGE_03*" -g "modules/**"` returned no matches |

## 3. Verification Commands For Code Phase

These commands are the Stage 03 implementation verification commands. Rows move from planned to evidence-backed as each task lands.

| Command | Expected result | Purpose |
| --- | --- | --- |
| `cd backend; pytest tests/integration/test_stage03_telegram_webhook.py -v` | Stage 03 webhook tests pass | Proves receive-only webhook, idempotency, invalid secret and allowlist |
| `cd backend; pytest tests/integration/test_stage03_customer_binding.py -v` | Customer binding tests pass | Proves bound/unbound/inactive binding behavior |
| `cd backend; pytest tests/integration/test_stage03_redis_streams_bridge.py -v` | Queue bridge tests pass | Proves committed outbox becomes Redis Streams job and rollback does not |
| `cd backend; pytest tests/integration/test_stage03_worker_runtime.py -v` | Worker runtime tests pass | Proves bounded worker loop, idempotency and dead letter handling |
| `cd backend; pytest tests/unit/test_stage03_redis_streams_adapter.py -v` | Redis adapter contract tests pass | Proves production Redis wrapper idempotency, group read decoding and ack delegation without live Redis |
| `cd backend; pytest tests/unit/test_stage03_worker_runtime_factory.py -v` | Worker factory test passes | Proves deployment worker entrypoint wires Telegram handler |
| `cd backend; pytest tests/unit/test_stage03_outbox_bridge_runtime_factory.py -v` | Outbox bridge factory test passes | Proves deployment outbox bridge entrypoint wires repository to Redis Streams |
| `cd backend; pytest tests/unit/test_stage03_telegram_inbox_view.py -v` | Inbox view tests pass | Proves Bitable view fields, limit/order and redaction |
| `cd backend; alembic upgrade head --sql` | SQL includes all revisions | Proves migrations import and order |
| `cd backend; pytest tests -v` | Full backend suite passes | Proves Stage 02 + Stage 03 behavior together |

## 4. Implementation Requirement Checklist

| Requirement | Status | Evidence |
| --- | --- | --- |
| Stage 03 code development approved by user | passed | User goal on 2026-07-06: "开始实施，严格执行阶段开发和真源文档..." |
| Runtime config contract | passed | `pytest tests/unit/test_stage03_config.py -v` => 8 passed; `pytest tests -q` => 93 passed, 17 skipped |
| Tencent Cloud compose files or deploy docs | passed | `deploy/stage03/compose.yml`, `deploy/stage03/Caddyfile`, `deploy/stage03/env.stage03.example`, `backend/Dockerfile`; staging services running on Tencent Cloud CVM |
| Caddy HTTPS endpoint | passed | `https://api.jiangtest1.online/health` returned 200 in staging; `getWebhookInfo.ip_address=43.160.215.224`; Caddy exposes `0.0.0.0:80` and `0.0.0.0:443` |
| Telegram update parser | passed | `pytest tests/unit/test_stage03_telegram_update_parser.py -v` => 5 passed; combined config/parser tests 13 passed; full suite 98 passed, 17 skipped |
| Telegram webhook route | passed | `pytest tests/integration/test_stage03_telegram_webhook.py -v` => 5 passed |
| Webhook secret validation | passed | `test_receive_only_webhook_rejects_invalid_secret_without_business_rows` passed; no secret echoed in response |
| Allowlist behavior | passed | `test_receive_only_webhook_allowlist_blocks_untrusted_chat` passed; no business rows/outbox |
| Telegram update idempotency | passed | `test_receive_only_webhook_duplicate_update_is_idempotent` passed; one message and one outbox event |
| Full backend regression after Task 3 | superseded | See Task 4 full backend regression row |
| Minimal customer binding | passed | `pytest tests/integration/test_stage03_customer_binding.py -v` => 5 passed; covers bound, chat_user precedence, unbound, inactive and conflict |
| `telegram_inbox` view | passed | `pytest tests/unit/test_stage03_telegram_inbox_view.py -v` => 3 passed; covers fields/scope, order/limit and redaction |
| Stage 03 migration offline SQL | passed | `alembic upgrade head --sql` reaches `20260706_0010` and includes `telegram_customer_bindings` plus message inbox fields |
| Full backend regression after Task 4 | passed | `pytest tests -q` => 111 passed, 17 skipped; skips are existing online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL` |
| Outbox to Redis Streams bridge | passed | `pytest tests/integration/test_stage03_redis_streams_bridge.py -v` => 3 passed; proves committed event enqueues once, absent/rolled-back event does not enqueue, and bridge rerun is idempotent |
| Affected backend regression after Task 5 | passed | `pytest tests/unit/test_outbox.py tests/integration/test_stage03_redis_streams_bridge.py tests/integration/test_stage03_telegram_webhook.py tests/integration/test_stage03_customer_binding.py -v` => 16 passed |
| Full backend regression after Task 5 | passed | `pytest tests -q` => 114 passed, 17 skipped; skips are existing online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL` |
| Durable worker runtime | passed | `pytest tests/integration/test_stage03_worker_runtime.py -v` => 5 passed; covers bounded `run_once`, bounded continuous loop, success processing and idempotent rerun |
| Worker retry/dead letter | passed | `pytest tests/integration/test_stage03_worker_runtime.py -v` => 5 passed; covers retryable failure to `retry`, exhausted retry to `dead_letter`, audit evidence and `telegram_inbox` field visibility |
| Affected backend regression after Task 6 | passed | `pytest tests/integration/test_stage03_worker_runtime.py tests/integration/test_stage03_redis_streams_bridge.py tests/unit/test_outbox.py tests/unit/test_stage03_telegram_inbox_view.py -v` => 14 passed |
| Full backend regression after Task 6 | passed | `pytest tests -q` => 119 passed, 17 skipped; skips are existing online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL` |
| Real Redis adapter code | passed | `pytest tests/unit/test_stage03_redis_streams_adapter.py -q` => 3 passed; `redis>=5.0` declared in `backend/pyproject.toml`; adapter imports without live Redis |
| Worker runtime entrypoint factory | passed | `pytest tests/unit/test_stage03_worker_runtime_factory.py -q` => 1 passed; `python -m app.workers.stage03_runtime` entrypoint exists |
| Outbox bridge runtime entrypoint factory | passed | `pytest tests/unit/test_stage03_outbox_bridge_runtime_factory.py -q` => 1 passed; `python -m app.workers.stage03_outbox_bridge_runtime` entrypoint exists |
| Task7A focused runtime regression | passed | `pytest tests/unit/test_stage03_redis_streams_adapter.py tests/unit/test_stage03_worker_runtime_factory.py tests/unit/test_stage03_outbox_bridge_runtime_factory.py tests/integration/test_stage03_redis_streams_bridge.py tests/integration/test_stage03_worker_runtime.py -q` => 13 passed |
| Import check without `.pyc` writes | passed | `python -B -c "import app.queues.redis_streams; import app.workers.stage03_runtime; import app.workers.stage03_outbox_bridge_runtime; print('imports ok')"` => `imports ok` |
| Full backend regression after Task 7A | passed | `pytest tests -q` => 124 passed, 17 skipped; skips are existing online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL` |
| Online PostgreSQL migration rehearsal | passed | `docker compose --profile tools run --rm migrate` ran Alembic through `20260706_0010 Add Stage 03 Telegram customer bindings and inbox fields` against staging PostgreSQL |
| Live Redis runtime / staging Redis rehearsal | passed | Docker Compose shows `redis` healthy, `outbox-bridge` and `worker` running; staging `outbox_events` for real Telegram updates are `processed`; `ops_audit_events` includes `telegram.message_processed` |
| Staging real Telegram webhook rehearsal | passed | Telegram `setWebhook` returned `ok=true`; `getWebhookInfo.url=https://api.jiangtest1.online/telegram/webhook`, `pending_update_count=0`; real message `stage03 webhook test` appeared in `/views/telegram_inbox/records` |
| Safety locks during staging | passed | `.env.stage03` redacted check showed `TELEGRAM_SEND_MODE=dry_run`, `LLM_ENABLED=false`, `PROVIDER_MODE=disabled`, `STAGE03_DOMAIN=api.jiangtest1.online` |

## 5. Staging Manual Verification Template

When Stage 03 implementation reaches deployment, record evidence using this template:

```text
Date:
Environment:
Tencent Cloud CVM:
Domain:
Webhook URL: https://<redacted>/telegram/webhook
Telegram bot: <redacted bot username or test bot label>
Secret token configured: yes/no, value not recorded
Allowlist mode:
Command run:
Observed API logs:
Observed worker logs:
Observed Bitable view record:
Observed audit event:
Telegram send happened: no
LLM call happened: no
Provider write happened: no
Result:
```

## 5.1 Recorded Staging Verification

```text
Date: 2026-07-06
Environment: Tencent Cloud staging
Tencent Cloud CVM: Ubuntu-NaSe, Ubuntu 24.04.4 LTS, IPv4 43.160.215.224
Domain: api.jiangtest1.online
Webhook URL: https://api.jiangtest1.online/telegram/webhook
Telegram bot: @BitableAgentBot
Secret token configured: yes, value not recorded
Allowlist mode: not configured in final redacted env output
Command run: docker compose migrate/ps; Telegram getMe/setWebhook/getWebhookInfo; PostgreSQL messages/outbox/audit queries; /views/telegram_inbox/records?limit=3
Observed API logs: Uvicorn serving; /health 200; invalid webhook secret returned 403
Observed worker logs: worker service running; worker result confirmed by database/audit evidence
Observed Bitable view record: telegram_update_id=184365901, text_preview=stage03 webhook test, binding_status=needs_manual_binding, processing_status=processed, outbox_status=processed, trace_id=tg:184365901
Observed audit event: message_ingested, telegram.binding.unbound, telegram.message_processed
Telegram send happened: no
LLM call happened: no
Provider write happened: no
Result: passed
```

## 6. Remaining Risks To Track

- Tencent Cloud deployment introduces server security, firewall, DNS and secret management work.
- Redis Streams must not weaken PostgreSQL outbox transaction guarantees.
- Telegram receive-only scope must not accidentally send replies.
- Real Telegram Bot Token and webhook secret must stay outside git.
- Provider execution and OpenRouter LLM remain intentionally deferred.
