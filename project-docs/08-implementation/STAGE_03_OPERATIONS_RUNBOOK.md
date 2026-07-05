# Stage 03 Operations Runbook

## Status

- Document status: active operations runbook
- Scope: Stage 03 staging 启停、配置、联调、排障、回滚和证据记录。
- Current Progress: 2026-07-06 建立运维手册。当前只写文档，不执行服务器操作。

## 1. Purpose

本手册用于 Stage 03 腾讯云 staging 环境。它不是生产运维手册，不覆盖真实资金、真实 provider 或客户生产流量。

## 2. Start Procedure

Future implementation batch should document exact commands after compose files exist. The intended sequence is:

1. Confirm server secrets exist outside git.
2. Pull latest approved branch.
3. Start PostgreSQL and Redis.
4. Run Alembic migrations.
5. Start API.
6. Start worker.
7. Start or reload Caddy.
8. Verify health endpoint.
9. Verify invalid webhook secret is rejected.
10. Ask user before setting Telegram webhook.

## 3. Stop Procedure

1. Stop Telegram webhook or pause incoming traffic if needed.
2. Stop worker first to prevent background changes.
3. Stop API.
4. Keep PostgreSQL volume unless user confirms deletion.
5. Keep logs for acceptance evidence, with secrets redacted.

## 4. Health Checks

Required checks:

- Caddy HTTPS reachable.
- API health endpoint reachable through Caddy.
- API can reach PostgreSQL.
- API or worker can reach Redis.
- Worker process is running.
- Invalid secret returns forbidden.

## 5. Webhook Setup Safety

Setting webhook is a real external write and needs explicit user confirmation.

Before setting:

- Confirm `TELEGRAM_SEND_MODE=dry_run`.
- Confirm `LLM_ENABLED=false`.
- Confirm `PROVIDER_MODE=disabled`.
- Confirm staging URL.
- Confirm Bot Token is for staging/test bot where possible.

After setting:

- Send one test message.
- Record timestamp.
- Verify inbox/audit.
- Do not leave unmonitored webhook enabled if staging is unstable.

## 6. Common Failure Handling

| Symptom | Likely Cause | Action |
| --- | --- | --- |
| Telegram webhook receives 403 | wrong secret | verify server env and setWebhook secret without logging value |
| Telegram cannot reach webhook | DNS/HTTPS/firewall | check domain, Caddy cert, Tencent security group |
| Message row exists but no worker processing | Redis/worker down | check worker logs and Redis stream length |
| Redis job exists repeatedly | worker error or ack failure | check safe error code and dead letter status |
| Inbox view empty | view projection/permission issue | check message row, customer scope and view config |
| Duplicate messages | idempotency missing | check unique update id and duplicate test |

## 7. Rollback

Rollback order:

1. Disable Telegram webhook or point it to a safe endpoint.
2. Stop worker.
3. Roll back API container/image if needed.
4. Keep database volume.
5. Record what was rolled back and why.

Do not run destructive database commands without explicit user approval.

## 8. Evidence Recording

Every staging rehearsal should record:

- date/time。
- branch/commit。
- redacted domain。
- service health result。
- webhook set status。
- test message timestamp。
- inbox record id。
- audit event id。
- tests run。
- not tested items。
- remaining risks。

## 9. Acceptance Criteria

- Operator can start, stop and inspect Stage 03 staging without guessing.
- Rollback path is clear.
- Real external webhook setup remains gated by user confirmation.
- Evidence can be copied into acceptance checklist without exposing secrets.
