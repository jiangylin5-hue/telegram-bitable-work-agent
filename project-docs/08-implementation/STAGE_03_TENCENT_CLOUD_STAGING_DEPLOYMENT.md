# Stage 03 Tencent Cloud Staging Deployment

## Status

- Document status: active deployment design (confirmed by user 2026-07-06)
- Scope: Stage 03 腾讯云 CVM staging、Docker Compose 单机运行、Caddy HTTPS 反代、Telegram webhook 联调和部署验收边界。
- Current Progress: 2026-07-06 用户确认 Stage 03 使用腾讯云服务器部署，HTTPS 入口采用域名子域名 + Caddy 自动 HTTPS。Tasks 1-6 本地后端切片已实施；Task 7A 已新增 Stage03 Dockerfile、compose、Caddyfile、env 示例、真实 Redis adapter 代码和 worker/outbox bridge 入口。腾讯云服务器、DNS、Caddy 真实证书签发和 Telegram webhook 外部操作仍待用户确认后执行。

## 1. Deployment Goal

Stage 03 staging 的目标是给真实 Telegram webhook 提供一个安全、可回滚、可观察的联调环境：

```text
Telegram Bot API
-> https://<stage03-subdomain>/telegram/webhook
-> Caddy on Tencent Cloud CVM
-> FastAPI api container
-> PostgreSQL + Redis
-> Redis Streams worker
-> Bitable telegram_inbox view / audit
```

这个环境用于验证真实收件入口和后端异步处理闭环，不用于生产客户业务，不发送真实 Telegram 回复，不执行真实充值、绑卡、Meta、BM 或卡台动作。

## 2. Recommended Topology

| Layer | Stage 03 Decision | Notes |
| --- | --- | --- |
| Cloud | Tencent Cloud CVM | 单机 staging，后续可拆数据库和 Redis |
| Runtime | Docker Compose | 便于快速部署和回滚 |
| HTTPS | Caddy | 自动申请和续期证书 |
| API | FastAPI container | 暴露给 Caddy 内网反代 |
| Worker | Python worker container | 消费 Redis Streams |
| Database | PostgreSQL container or managed later | Stage 03 可先同机；生产化另开阶段 |
| Queue | Redis container | Streams 用于 worker 投递 |
| Domain | Dedicated subdomain | 例如 `tg-stage.example.com` |

## 3. Network And Ports

Expected public ports:

| Port | Purpose | Public |
| --- | --- | --- |
| `80` | Caddy HTTP challenge / redirect | yes |
| `443` | Caddy HTTPS | yes |

Expected private-only ports:

| Port | Purpose | Public |
| --- | --- | --- |
| `8000` | FastAPI app | no |
| `5432` | PostgreSQL | no |
| `6379` | Redis | no |

Tencent Cloud security group should only expose `80` and `443` publicly for Stage 03. SSH access, if needed, should be restricted by IP or key policy outside the app docs.

## 4. Compose Services

Planned services:

| Service | Responsibility | Health |
| --- | --- | --- |
| `caddy` | TLS and reverse proxy | HTTP health on public endpoint |
| `api` | FastAPI webhook/API | `/health` and future readiness endpoint |
| `migrate` | One-shot Alembic migration tool service | exits after `alembic upgrade head` |
| `outbox-bridge` | PostgreSQL Outbox to Redis Streams bridge | process heartbeat/logs |
| `worker` | Redis Streams consumer | process heartbeat/logs |
| `postgres` | Stage 03 database | container health check |
| `redis` | queue/cache | container health check |

Current repository deployment files:

| File | Purpose |
| --- | --- |
| `backend/Dockerfile` | Builds the FastAPI/worker runtime image from the backend package |
| `deploy/stage03/compose.yml` | Defines `api`, `migrate`, `outbox-bridge`, `worker`, `postgres`, `redis` and `caddy` |
| `deploy/stage03/Caddyfile` | Terminates HTTPS and reverse-proxies to `api:8000` |
| `deploy/stage03/env.stage03.example` | Placeholder-only environment template; copy to `.env.stage03` outside git before use |

Real server/DNS/Telegram webhook operations still require separate confirmation at execution time.

Local compose preflight can be run without creating `.env.stage03`:

```bash
cd deploy/stage03
docker compose --env-file env.stage03.example -f compose.yml config
```

This only validates compose interpolation and service shape. It does not build images, start containers, connect Redis/PostgreSQL, issue Caddy certificates or set Telegram webhook.

## 5. Caddy Route Design

Expected public route:

```text
https://<stage03-subdomain>/telegram/webhook
```

Current `deploy/stage03/Caddyfile` shape:

```text
{$STAGE03_DOMAIN} {
    encode zstd gzip
    reverse_proxy api:8000
}
```

Rules:

- Caddy handles certificates automatically.
- The app still validates Telegram webhook secret; HTTPS alone is not sufficient.
- Caddy logs must not include Telegram Bot Token or webhook secret values.
- If a separate health endpoint is exposed, it must not reveal configuration or secrets.

## 6. Environment Variables

Required staging variables:

| Variable | Required | Secret | Purpose |
| --- | --- | --- | --- |
| `APP_ENV=staging` | yes | no | Runtime mode |
| `DATABASE_URL` | yes | yes | PostgreSQL connection |
| `REDIS_URL` | yes | yes if passworded | Redis connection |
| `TELEGRAM_BOT_TOKEN` | yes for webhook setup | yes | Used only for Telegram API setup/readiness where required |
| `TELEGRAM_WEBHOOK_SECRET` | yes | yes | Validates Telegram webhook header |
| `TELEGRAM_ALLOWED_CHAT_IDS` | optional | maybe | Comma-separated allowlist |
| `TELEGRAM_ALLOWED_USER_IDS` | optional | maybe | Comma-separated allowlist |
| `TELEGRAM_SEND_MODE=dry_run` | yes | no | Prevent real sends |
| `LLM_ENABLED=false` | yes | no | Prevent OpenRouter calls |
| `PROVIDER_MODE=disabled` | yes | no | Prevent provider writes |
| `LOG_LEVEL` | optional | no | Operational logging |

Forbidden in git:

- Real Bot Token.
- Real webhook secret.
- Database password.
- Redis password.
- SSH keys.
- TLS private keys.

## 7. Telegram Webhook Setup Boundary

Setting the Telegram webhook is a real external write. It must not happen until the user explicitly confirms.

Planned API call shape:

```text
setWebhook(url = https://<stage03-subdomain>/telegram/webhook, secret_token = <redacted>)
```

Rules:

- Use a test bot or staging bot if possible.
- Record webhook URL redacted in acceptance docs.
- Do not record Bot Token.
- Do not enable send behavior.
- If webhook setup fails, do not retry blindly with secrets in logs.

## 8. Deployment Steps For Future Staging Rehearsal

These steps are planned for Task 7 and have not been executed:

1. Provision Tencent Cloud CVM.
2. Point subdomain DNS `A` record to CVM public IP.
3. Install Docker and Docker Compose plugin.
4. Copy `deploy/stage03/env.stage03.example` to `deploy/stage03/.env.stage03` on the server and replace placeholders outside git.
5. Pull the approved branch/commit.
6. Validate compose configuration on the server:

```bash
cd deploy/stage03
docker compose --env-file .env.stage03 -f compose.yml config
```

7. Run the migration service:

```bash
cd deploy/stage03
docker compose --env-file .env.stage03 -f compose.yml --profile tools run --rm migrate
```

8. Start staging services:

```bash
cd deploy/stage03
docker compose --env-file .env.stage03 -f compose.yml up -d api outbox-bridge worker caddy
```

9. Verify Caddy obtains certificate.
10. Run health check through HTTPS.
11. Verify invalid webhook secret is rejected.
12. After explicit user confirmation, set Telegram webhook.
13. Send one real test message.
14. Verify `telegram_inbox`, `outbox_events`, Redis Streams worker logs and audit evidence.

Note: the commands above are documented runbook targets. They have not been executed in this repository session.

## 9. Rollback And Safety

Rollback expectations:

- Disable Telegram webhook or point it away from staging if messages should stop.
- Stop worker before API if preventing background processing.
- Keep PostgreSQL data volume unless explicitly approved for deletion.
- Do not delete staging database without user confirmation.
- Keep Caddy and API logs redacted.

Safety defaults:

- `TELEGRAM_SEND_MODE=dry_run`.
- `LLM_ENABLED=false`.
- `PROVIDER_MODE=disabled`.
- Only `80/443` public.
- No production credentials.

## 10. Deployment Acceptance

Deployment is accepted only when:

- Domain resolves to Tencent Cloud CVM.
- HTTPS certificate is valid.
- `/health` or equivalent returns healthy through Caddy.
- `POST /telegram/webhook` rejects invalid secret.
- Real Telegram test message creates `telegram_inbox` record after explicit webhook setup confirmation.
- Worker processes the message through Redis Streams.
- Acceptance checklist records timestamp and redacted evidence.
- No real Telegram reply, LLM call, provider write or funds movement occurred.
