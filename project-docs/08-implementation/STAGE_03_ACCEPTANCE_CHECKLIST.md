# Stage 03 Acceptance Checklist

## Status

- Document status: active acceptance checklist (confirmed by user 2026-07-06)
- Scope: Stage 03 文档、真实 Telegram 收件入口、Redis Streams worker、多维表格 Telegram Inbox 和腾讯云 staging 验收。
- Current Progress: 2026-07-06 根据用户确认的 Stage 03 方向重写验收清单。本批只验收文档一致性，不运行 Stage 03 代码测试。

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

## 2. Documentation Acceptance For Current Batch

当前用户选择的是“先只写完整 Stage 03 文档，不写代码”。因此本批验收只看文档，不要求 Stage 03 代码测试通过。

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

## 3. Planned Verification Commands For Code Phase

These commands are planned for the later implementation batch. They are not expected to pass before code is written.

| Command | Expected result | Purpose |
| --- | --- | --- |
| `cd backend; pytest tests/integration/test_stage03_telegram_webhook.py -v` | Stage 03 webhook tests pass | Proves receive-only webhook, idempotency, invalid secret and allowlist |
| `cd backend; pytest tests/integration/test_stage03_customer_binding.py -v` | Customer binding tests pass | Proves bound/unbound/inactive binding behavior |
| `cd backend; pytest tests/integration/test_stage03_redis_streams_bridge.py -v` | Queue bridge tests pass | Proves committed outbox becomes Redis Streams job and rollback does not |
| `cd backend; pytest tests/integration/test_stage03_worker_runtime.py -v` | Worker runtime tests pass | Proves bounded worker loop, idempotency and dead letter handling |
| `cd backend; pytest tests/unit/test_stage03_telegram_inbox_view.py -v` | Inbox view tests pass | Proves Bitable view fields, limit/order and redaction |
| `cd backend; alembic upgrade head --sql` | SQL includes all revisions | Proves migrations import and order |
| `cd backend; pytest tests -v` | Full backend suite passes | Proves Stage 02 + Stage 03 behavior together |

## 4. Implementation Requirement Checklist

| Requirement | Status | Evidence |
| --- | --- | --- |
| Stage 03 code development approved by user | passed | User goal on 2026-07-06: "开始实施，严格执行阶段开发和真源文档..." |
| Runtime config contract | passed | `pytest tests/unit/test_stage03_config.py -v` => 8 passed; `pytest tests -q` => 93 passed, 17 skipped |
| Tencent Cloud compose files or deploy docs | pending | deployment rehearsal |
| Caddy HTTPS endpoint | pending | staging smoke evidence |
| Telegram webhook route | pending | `test_stage03_telegram_webhook.py` |
| Webhook secret validation | pending | invalid secret test |
| Allowlist behavior | pending | blocked chat/user test |
| Telegram update idempotency | pending | duplicate update test |
| Minimal customer binding | pending | customer binding tests |
| `telegram_inbox` view | pending | inbox view tests |
| Outbox to Redis Streams bridge | pending | bridge tests |
| Durable worker runtime | pending | worker runtime tests |
| Worker retry/dead letter | pending | dead letter tests |
| Staging real Telegram webhook rehearsal | pending | manual evidence |

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

## 6. Remaining Risks To Track

- Tencent Cloud deployment introduces server security, firewall, DNS and secret management work.
- Redis Streams must not weaken PostgreSQL outbox transaction guarantees.
- Telegram receive-only scope must not accidentally send replies.
- Real Telegram Bot Token and webhook secret must stay outside git.
- Provider execution and OpenRouter LLM remain intentionally deferred.
