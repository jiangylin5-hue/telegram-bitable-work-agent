# Stage07 S6.3 Isolated Acceptance Deployment SDD

## Status

- Status: `accepted-bounded-and-cleaned` on 2026-07-15.
- Scope: deploy the already approved Stage07 source snapshot as a parallel, disposable acceptance environment; expose it through one separate public HTTPS hostname; run only the existing TD007/TD008 controlled Telegram acceptance path.
- Current outcome: the isolated runtime had a captured exactly-one private target and a passing `restricted_test` preflight; API, Worker, Outbox bridge and Web served the approved HTTPS host while Stage03 remained healthy. BotFather Main Mini App configuration and two separately user-approved one-attempt TD008 requests each produced terminal `sent` receipts. The first launch exposed a missing official Telegram WebApp bridge; the bridge correction was test-first, deployed and publicly verified. The second fresh request then produced the real signed-launch resolver audit (`resolved`, `base`) and the recipient's authorized Base UI. No automatic retry occurred. Following explicit cleanup approval, the isolated Compose resources/volumes/runtime, Caddy host/backup and temporary SSH public key were removed; Stage03 was `200` before and after cleanup.
- Explicit exclusion: replacing the historical Stage03 Compose project, reusing its PostgreSQL/Redis data, production release, general user rollout, group delivery, new product API/schema/permission behavior and any broad Telegram capability.

## Purpose and Reuse Boundary

S6.3 is an operational acceptance boundary, not a new product feature. It reuses the existing mature project stack:

```text
Docker Compose -> PostgreSQL 16 + pgvector -> Redis 7
              -> FastAPI/Uvicorn -> Stage07 Worker / Outbox bridge
              -> Vite static build -> existing Caddy ingress
              -> Telegram Bot API / Main Mini App
```

The historical Stage03 project remains untouched as `telegram-bitable-stage03`. The new project is named `stage07-acceptance`, has its own directory, Compose resources, PostgreSQL volume/database, Redis volume, container names and internal network. Its API and static Mini App attach only to the existing Caddy Docker network for ingress; neither process connects to the Stage03 application containers or their database/Redis network names.

## Deployment Topology

```text
Telegram private test user
  -> Main Mini App HTTPS host
  -> existing Caddy (new host block only)
      -> stage07-web:80       static Vite assets and SPA entry
      -> stage07-api:8000     all non-static Mini App API paths
          -> stage07-acceptance-postgres
          -> stage07-acceptance-redis
          -> stage07-outbox-bridge / stage07-worker
              -> existing restricted test Bot token
```

### Network and Data Isolation

| Concern | Stage07 acceptance rule |
| --- | --- |
| Public HTTPS | one DNS A/AAAA record resolves the chosen hostname to the existing Tencent Cloud instance before Caddy activation |
| Caddy | existing Caddy retains the Stage03 host block; Stage07 adds one separately validated host block and two stable Docker aliases (`stage07-api`, `stage07-web`) |
| API / web | no host port is published; they are reachable only through the existing Caddy shared Docker network |
| PostgreSQL | a new named volume and database; migrations run only against the new database; no Stage03 database copy or connection string is used |
| Redis | a new named volume and instance; no Stage03 queue, key or worker is consumed |
| Runtime secrets | copied or injected inside the server only; never printed, archived, committed, screenshot, browser-visible or written to evidence |
| Test data | synthetic, disposable workspace/Base/table/view/record/member/binding data only; removed with the isolated Compose project and volumes after acceptance |

## Runtime Configuration Contract

The ignored remote `runtime/.env.stage07-acceptance` contains only the required runtime values. The dedicated `runtime/` directory is mode `0700`; its env file is mode `0600`; both are owned by the isolated deployment operator that executes the wrapper. Its key names are validated without displaying values.

| Key | Required S6.3 rule |
| --- | --- |
| `APP_ENV` | an isolated non-production value accepted by the existing safety validator |
| `DATABASE_URL` / `REDIS_URL` | point only to the new `stage07-acceptance` Compose services |
| `OPENROUTER_API_KEY` | existing approved test-provider credential, runtime-only |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_WEBHOOK_SECRET` | runtime-only, copied without disclosure from the already approved test Bot configuration |
| `TELEGRAM_SEND_MODE` | exactly `restricted_test` |
| `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` | exactly one private test-chat value |
| `STAGE07_TELEGRAM_BOT_USERNAME` | one valid server-owned Bot username; no client override |
| `STAGE07_ENV_FILE` | exactly `runtime/.env.stage07-acceptance`, so every Compose command and service `env_file` resolves the same isolated file |
| `LLM_ENABLED`, `AGENT_WORKFLOW_MODE`, `PROVIDER_MODE` | retain the existing safe real-provider contract: `true`, `real_openrouter`, `disabled`; no fake result substitutes external acceptance |

## State Model and Rollback

| State | Entry condition | Allowed actions | Exit / rollback |
| --- | --- | --- | --- |
| `dns-blocked` | hostname does not resolve to the server | prepare local artifacts only | add the DNS record; do not alter Caddy |
| `staged` | signed source snapshot and non-secret Compose files are on the server | build images and validate Compose | delete isolated directory; Stage03 stays unchanged |
| `data-ready` | new PostgreSQL/Redis are healthy and migration is at the Stage07 Alembic head | create only synthetic acceptance fixture through backend services | `docker compose down -v` removes isolated data |
| `ingress-validated` | Caddy host block validates and certificate is active | run static/API health checks through HTTPS | restore exact Caddy backup and reload; no Stage03 route change |
| `bot-ready` | one allowlisted test chat, Bot username and Main Mini App hostname are configured | create/confirm exactly one TD008 request | if any guard fails, record `blocked`; do not send |
| `smoke-terminal` | one normal sent, definite failed, blocked or delivery-unknown terminal receipt exists | inspect the bounded URL in Telegram and capture sanitized outcome | no automatic second send; remove temporary key/config/data after evidence |

An uncertain external result is always `delivery_unknown`: TD008 revokes the pointer and prohibits automatic retry. A healthy deployment is not proof of a Telegram send, and a Caddy certificate is not proof of Telegram `initData` validation.

### One-Time Private Test-Target Capture

The historical runtime has no non-empty private test-chat/user configuration. Before the isolated runtime is written, a single-purpose helper may capture exactly one newly sent private `/stage07-bind` marker for the configured Bot. It reuses the existing temporary-polling safety sequence: snapshot the webhook, delete it with `drop_pending_updates=false`, poll for at most 120 seconds, accept only `chat.type == "private"`, atomically write the Chat/User IDs only into the ignored isolated runtime env file, acknowledge only the matched update, and restore the original webhook (including its secret) in `finally`.

The helper emits only fixed status, private/non-private outcome and webhook-restoration status. It never prints or persists the raw update, text, user ID, chat ID, token, webhook URL or secret outside the ignored isolated env. A timeout or non-private marker writes nothing and leaves controlled delivery blocked.

### One-Time Persisted Marker Bridge (Approved Direction)

Direct temporary polling has now failed to observe a marker that the existing Stage03 webhook demonstrably persisted. The user selected the documented persisted-marker bridge alternative. It is a strictly bounded fallback for this acceptance run, not a replacement for Telegram webhook processing.

The bridge runs a read-only SQLAlchemy ORM selection inside the already-running Stage03 API container. It may read only the existing `Message` model and only for a newly opened bind window. An eligible row must have exact text `/stage07-bind`, `message_type == "text"`, a `received_at` inside the explicit not-before/execution window, non-empty stored Chat/User IDs and `telegram_chat_id == telegram_user_id`. Exactly one candidate is required; zero, stale, non-private-equivalent, malformed or multiple candidates are `blocked`. ORM/pipeline/write errors are `failed`.

The selected values move through a protected process pipe and are passed to the existing atomic isolated-env writer. No raw target reaches stdout, logs, CLI arguments, Docker image layers, source, evidence or chat. It writes exactly the three existing target keys (`TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`, `STAGE06_TELEGRAM_TEST_CHAT_ID`, `STAGE06_TELEGRAM_TEST_USER_ID`) in the ignored mode-`0600` Stage07 runtime file; every other runtime key is retained. The only receipt is fixed status plus `source=stage03_persisted_marker`.

The first live bridge identified that a single-file Docker bind mount is incompatible with the writer's sibling-temp-file atomic replace. It wrote no target. The user selected C: migrate the ignored runtime env into dedicated `deploy/stage07-acceptance/runtime/`, retarget all Compose `env_file` defaults to `runtime/.env.stage07-acceptance`, and mount only that directory for the short-lived trusted writer. This preserves the existing tested atomic writer while preventing it from seeing the deployment source tree or any Stage03 path. The Stage03 project and every Stage03 path remain excluded. Since the atomic replacement is executed by the short-lived root container, the wrapper restores the env file to the invoking deployment user's UID/GID and mode `0600` before a `captured` receipt is accepted. The C migration, Compose validation, API rebuild and temporary directory-mounted atomic-write probe passed; the one approved fresh window subsequently returned `captured`, ownership was restored, and the isolated runtime preflight passed without displaying a target value.

No Stage03 row, outbox event, audit event, webhook setting, container, source file, runtime file, schema, API route, permission rule or index may change. The bridge cannot start a Worker, create a binding, send a Telegram message or accept a TD008 request; existing S6.3 restricted-test and confirmation gates remain mandatory.

## Bounded Ingress Contract

The existing Caddy instance receives one new host block only after its candidate configuration validates. Static paths (`/`, `/index.html`, `/assets/*`, `/favicon.ico`) resolve to `stage07-web`; all other paths resolve to `stage07-api`. This preserves the Mini App's existing same-origin root API paths and does not introduce a client API-base adapter, public proxy endpoint or CORS exception.

The host block is not activated until the hostname resolves to this server. Existing `api.jiangtest1.online` routing is not edited and no port `80`/`443` listener is added by the new Compose project.

## Acceptance Evidence Rules

- Retain only deployment state, image/source revision, migration head, health status, HTTPS status, fixed receipt state and UTC timestamps.
- Do not retain tokens, secret values, raw Bot API request/response, Telegram chat/user/message IDs, `initData`, deep-link URL/token, record values, private certificate material or runtime logs containing user data.
- A failure during build, migration, Caddy validation, health probing or smoke remains an explicit terminal evidence row; it must not be converted into a local mock.
- The target-capture helper is not a new inbound Bot feature, webhook receiver or user-facing command. It is a one-time non-production configuration bootstrap and remains unavailable to the Mini App/API surface.
- The temporary SSH public key and the Stage07 acceptance Compose project are removed after the outcome is recorded unless the user explicitly retains the environment for another bounded acceptance run.

## Explicit Non-Goals

S6.3 does not make Stage07 production-ready, does not accept incomplete V1/S3/S4 visual evidence, does not authorize Telegram group/channel delivery, does not introduce RAG/memory/files, and does not replace the final Stage07 requirement-traceability audit.
