# Stage 03 Acceptance Checklist

## Status

- Document status: candidate acceptance checklist, pending user confirmation
- Scope: Stage 03 真实集成运行时验收
- Current Progress: 2026-07-05 建立 Stage 03 候选验收清单。当前尚未执行 Stage 03 代码验收。

## 1. Acceptance Boundary

Stage 03 验收：

- Real-shaped Telegram webhook ingress.
- Durable worker runtime.
- Outbox-to-queue bridge.
- Telegram notification dry-run.
- Provider sandbox gateway.
- PostgreSQL migration rehearsal.
- Bitable view limit/order hardening.

Stage 03 不验收：

- Real funds movement.
- Real Meta/BM/card/recharge writes.
- Telegram Mini App UI.
- Production deployment cutover.
- Temporal workflow migration.

## 2. Planned Verification Commands

| Command | Expected result | Purpose |
| --- | --- | --- |
| `cd backend; pytest tests/integration/test_telegram_webhook.py -v` | Telegram webhook tests pass | Proves real-shaped update ingress, idempotency and invalid secret rejection |
| `cd backend; pytest tests/integration/test_worker_runtime.py -v` | Worker runtime tests pass | Proves bounded worker loop, idempotency and draft creation |
| `cd backend; pytest tests/integration/test_queue_bridge.py -v` | Queue bridge tests pass | Proves committed outbox becomes queue job and rollback does not |
| `cd backend; pytest tests/integration/test_provider_sandbox_gateway.py -v` | Provider sandbox tests pass | Proves ticket-gated execution and failure mapping |
| `cd backend; pytest tests/unit/test_bitable_view_query_bounds.py -v` | View hardening tests pass | Proves limit/order behavior |
| `cd backend; alembic upgrade head --sql` | SQL includes all revisions | Proves migrations import and order |
| `cd backend; pytest tests -v` | Full backend suite passes | Proves Stage 02 + Stage 03 behavior together |

## 3. Requirement Checklist

| Requirement | Status | Evidence |
| --- | --- | --- |
| Stage 03 source confirmed active | pending | User confirmation required |
| Stage 02 hardening committed | pending | `git status --short` after commit |
| Telegram webhook route | pending | `test_telegram_webhook.py` |
| Webhook secret validation | pending | invalid secret test |
| Worker runtime entrypoint | pending | `test_worker_runtime.py` |
| Worker idempotency | pending | repeated worker run test |
| Outbox-to-queue bridge | pending | `test_queue_bridge.py` |
| Telegram notify dry-run | pending | notification worker test |
| Provider sandbox gateway | pending | `test_provider_sandbox_gateway.py` |
| Migration rehearsal | pending | recorded command output |
| Bitable view limit/order hardening | pending | view query bounds test |

## 4. Remaining Risks To Track

- Real provider writes remain intentionally excluded.
- Redis integration must not weaken outbox transaction guarantees.
- Real Telegram send should remain dry-run/sandbox until explicit confirmation.
- Migration rehearsal must not target production database.

