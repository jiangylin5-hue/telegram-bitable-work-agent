# Stage 03 Operations Runbook

## Status

- Document status: active operations runbook
- Scope: Stage 03 staging 启停、配置、联调、排障、回滚和证据记录。
- Current Progress: 2026-07-06 运维手册已建立；Task 7A 已新增本地部署文件和运行时入口，但尚未执行腾讯云服务器、DNS、Caddy 证书签发或 Telegram webhook 设置，任何真实外部操作仍需单独确认。

## 1. Purpose

本手册用于 Stage 03 腾讯云 staging 环境。它不是生产运维手册，不覆盖真实资金、真实 provider 或客户生产流量。

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
