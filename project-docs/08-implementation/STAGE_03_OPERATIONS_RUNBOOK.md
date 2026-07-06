# Stage 03 Operations Runbook

## Status

- Document status: active operations runbook
- Scope: Stage 03 staging 启停、配置、联调、排障、回滚和证据记录。
- Current Progress: 2026-07-06 运维手册已用于 Task 7 腾讯云 staging rehearsal。Docker、Compose、Caddy、PostgreSQL、Redis、API、outbox bridge、worker、Telegram webhook 和真实测试消息验收均已记录；后续任何新的真实外部操作仍需单独确认。

## 1. Purpose

本手册用于 Stage 03 腾讯云 staging 环境。它不是生产运维手册，不覆盖真实资金、真实 provider 或客户生产流量。

## 1.1 Database Environment Policy

Stage 03 之后继续开发时，数据库使用必须保持分层：

| Database | Use | Rule |
| --- | --- | --- |
| Local `ads_agent` | 本机开发、手工 API 调试、临时数据观察 | 可以执行 `alembic upgrade head`，不能用于会重置 schema 的测试 |
| Disposable `stage02_online_test` | `STAGE02_ONLINE_DATABASE_URL` online smoke tests | 只能通过 `backend/docker-compose.stage02-online.yml` 启动，测试结束可 `down -v` 删除 |
| Tencent Cloud staging DB | Stage 03 webhook 和 worker 联调 | 连接串只在服务器 `.env.stage03`，不得复用为本机测试库 |
| Production DB | 未来正式上线 | 未进入 Stage 03；上线前必须补齐生产数据库方案 |

Important:

- `test_online_postgres_smoke.py` 会重置 public schema，因此 `STAGE02_ONLINE_DATABASE_URL` 绝不能指向 `ads_agent`、staging 或 production。
- 本机开发默认连接串记录在 `backend/.env.example`，真实 `.env` 不提交。
- 正式上线前需要补充备份、恢复演练、迁移审批、最小权限账号、secret manager、监控告警和数据保留策略。

## 2. Start Procedure

Run these commands only after the user explicitly confirms real server work and staging secrets exist outside git.

1. Confirm branch/commit and secrets.

```bash
git status --short
git rev-parse --short HEAD
```

2. Prepare server env file outside git.

```bash
cd deploy/stage03
cp env.stage03.example .env.stage03
```

Then replace every `CHANGE_ME_*` value in `.env.stage03` on the server. Do not commit `.env.stage03`.

3. Validate compose configuration before starting containers.

Local placeholder-only preflight:

```bash
cd deploy/stage03
docker compose --env-file env.stage03.example -f compose.yml config
```

Server preflight after `.env.stage03` is populated:

```bash
cd deploy/stage03
docker compose --env-file .env.stage03 -f compose.yml config
```

Both commands should parse the compose file without requiring real containers to start. The local placeholder output may include `CHANGE_ME_*` values and must not be used for live deployment.

4. Run database migration.

```bash
cd deploy/stage03
docker compose --env-file .env.stage03 -f compose.yml --profile tools run --rm migrate
```

5. Start API, outbox bridge, worker and Caddy.

```bash
cd deploy/stage03
docker compose --env-file .env.stage03 -f compose.yml up -d api outbox-bridge worker caddy
```

6. Inspect status and logs.

```bash
cd deploy/stage03
docker compose --env-file .env.stage03 -f compose.yml ps
docker compose --env-file .env.stage03 -f compose.yml logs --tail=100 api outbox-bridge worker caddy
```

7. Verify health endpoint and invalid webhook secret rejection.
8. Ask user before setting Telegram webhook.

## 3. Stop Procedure

1. Stop Telegram webhook or pause incoming traffic if needed.
2. Stop worker first to prevent background changes.
3. Stop API.
4. Keep PostgreSQL volume unless user confirms deletion.
5. Keep logs for acceptance evidence, with secrets redacted.

Command target:

```bash
cd deploy/stage03
docker compose --env-file .env.stage03 -f compose.yml stop worker outbox-bridge api caddy
```

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
