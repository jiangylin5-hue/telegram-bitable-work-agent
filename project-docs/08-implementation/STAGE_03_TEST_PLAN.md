# Stage 03 Test Plan

## Status

- Document status: active test plan
- Scope: Stage 03 automated tests、manual staging verification、验收证据和不可测试项说明。
- Current Progress: 2026-07-06 已进入 Stage 03 代码实施。`test_stage03_config.py`、`test_stage03_telegram_update_parser.py`、`test_stage03_telegram_webhook.py`、`test_stage03_customer_binding.py` 和 `test_stage03_telegram_inbox_view.py` 已通过 focused verification；Redis Streams、worker、online migration rehearsal 和 staging manual verification 仍待后续任务完成。

## 1. Test Strategy

Stage 03 测试分四层：

1. Unit tests: parser、config、binding resolution、view projection。
2. Integration tests: webhook route、database writes、outbox、Redis Streams bridge、worker bounded loop。
3. Migration tests: Alembic offline SQL and online staging-like upgrade。
4. Manual staging rehearsal: Tencent Cloud + Caddy + real Telegram webhook。

所有测试必须证明业务结果落到 Bitable view/status/audit。

## 2. Planned Test Files

| Test File | Purpose |
| --- | --- |
| `backend/tests/unit/test_stage03_telegram_update_parser.py` | Telegram update parsing and safe extraction |
| `backend/tests/unit/test_stage03_config.py` | staging env requirements and disabled external actions |
| `backend/tests/unit/test_stage03_telegram_inbox_view.py` | view fields, ordering, limits, redaction |
| `backend/tests/integration/test_stage03_telegram_webhook.py` | webhook route, secret, duplicate, allowlist |
| `backend/tests/integration/test_stage03_customer_binding.py` | bound/unbound/inactive/conflict binding behavior |
| `backend/tests/integration/test_stage03_redis_streams_bridge.py` | outbox to Redis Streams delivery semantics |
| `backend/tests/integration/test_stage03_worker_runtime.py` | worker bounded loop, retry, dead letter |
| `backend/tests/integration/test_stage03_migration_rehearsal.py` | optional online migration smoke if env provided |

## 3. Planned Commands

```powershell
cd backend
pytest tests/unit/test_stage03_telegram_update_parser.py -v
pytest tests/unit/test_stage03_config.py -v
pytest tests/unit/test_stage03_telegram_inbox_view.py -v
pytest tests/integration/test_stage03_telegram_webhook.py -v
pytest tests/integration/test_stage03_customer_binding.py -v
pytest tests/integration/test_stage03_redis_streams_bridge.py -v
pytest tests/integration/test_stage03_worker_runtime.py -v
alembic upgrade head --sql
pytest tests -v
```

Expected at Stage 03 close:

- Focused Stage 03 tests pass.
- Full backend suite passes.
- Alembic offline SQL reaches latest revision.
- Manual staging evidence is recorded.

## 4. Test Data Rules

- Use fake Telegram update ids and chat/user ids in automated tests.
- Do not use real Bot Token in tests.
- Do not call Telegram network API in automated tests.
- Use fake Redis or disposable Redis for queue tests.
- Use disposable or staging-like PostgreSQL for online migration tests.
- Do not store raw card/payment data.

## 5. Manual Staging Verification

Manual verification is required because user chose腾讯云服务器 staging real webhook.

Manual test:

1. Deploy API/worker/PostgreSQL/Redis/Caddy to Tencent Cloud CVM.
2. Confirm HTTPS endpoint is valid.
3. Confirm invalid secret is rejected.
4. After explicit user approval, set Telegram webhook to staging endpoint.
5. Send one real test message.
6. Verify database row, outbox event, Redis worker processing, `telegram_inbox` view and audit.
7. Confirm no real Telegram reply was sent.
8. Record evidence in `STAGE_03_ACCEPTANCE_CHECKLIST.md`.

## 6. Regression Coverage

Stage 03 must keep Stage 02 behavior passing:

- recharge mock/sandbox tests。
- account inventory tests。
- reporting tests。
- Bitable view permissions。
- outbox tests。
- audit tests。
- online smoke if environment is available。

## 7. Not Tested Until Later

The following are explicitly not tested in Stage 03:

- Real Telegram sending.
- OpenRouter LLM behavior.
- Provider sandbox or real provider writes.
- Mini App UI.
- Production cutover.
- Kubernetes deployment.

These are not omissions; they are out of Stage 03 scope.

## 8. Acceptance Criteria

- Every BDD scenario has a matching automated test or manual staging verification.
- No completion claim is made without command output or recorded manual evidence.
- Skipped tests are listed with reason.
- Any failing test blocks Stage 03 closure unless user explicitly changes scope.
