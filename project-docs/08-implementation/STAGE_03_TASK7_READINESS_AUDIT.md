# Stage 03 Task 7 Readiness Audit

## Status

- Document status: active readiness audit
- Scope: Task 7 腾讯云 staging rehearsal 前置条件、确认项、可执行边界和验收证据。
- Current Progress: 2026-07-06 完成 Tasks 1-6 当前状态审计：本地后端 Telegram receive-only webhook、customer binding、`telegram_inbox`、outbox bridge 和 dependency-neutral worker runtime 已有自动化测试证据；真实 Redis client/live Redis runtime、Stage03 compose/Caddy 文件、腾讯云服务器、DNS 和 Telegram webhook 外部写入仍未执行，必须等待用户确认。

## 1. Purpose

本文档用于回答一个具体问题：Stage 03 是否已经可以进入 Task 7 真实 staging rehearsal。

结论：

- 可以继续做本地部署准备和文档完善。
- 不可以直接执行真实腾讯云服务器、DNS 或 Telegram webhook 操作。
- 不可以声称 Stage 03 已完成真实 Redis runtime 或 staging rehearsal。
- 真实 Redis adapter 需要先确认是否引入 `redis` / `redis.asyncio` 依赖。

## 2. Current Evidence

| Area | Status | Evidence |
| --- | --- | --- |
| Runtime config safety | passed | `test_stage03_config.py` passed in prior Task 1 evidence |
| Telegram parser | passed | `test_stage03_telegram_update_parser.py` passed in prior Task 2 evidence |
| Receive-only webhook | passed | `test_stage03_telegram_webhook.py` passed in prior Task 3 evidence |
| Customer binding | passed | `test_stage03_customer_binding.py` passed in prior Task 4 evidence |
| `telegram_inbox` projection | passed | `test_stage03_telegram_inbox_view.py` passed in prior Task 4 evidence |
| Outbox to Redis Streams bridge semantics | passed | `test_stage03_redis_streams_bridge.py` passed in prior Task 5 evidence |
| Worker runtime semantics | passed | `test_stage03_worker_runtime.py` passed in prior Task 6 evidence |
| Full backend regression | passed | Task 6 progress records `pytest tests -q` => 119 passed / 17 skipped |
| Git state | clean at audit start | `git status --short` returned no changes |

The 17 skipped tests are existing online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL`; they do not prove or disprove Task 7 staging readiness.

## 3. Task 7 Required Outcomes

Task 7 from [Stage 03 Backend Integration Plan](STAGE_03_BACKEND_INTEGRATION_PLAN.md) requires:

1. Confirm with user before real server, DNS or Telegram webhook operation.
2. Deploy API, worker, PostgreSQL, Redis and Caddy to Tencent Cloud CVM.
3. Run migration against staging database.
4. Verify invalid secret rejection.
5. Confirm again before setting Telegram webhook.
6. Send one real test message.
7. Run full backend suite locally or in CI-equivalent environment.
8. Update acceptance checklist and progress.

These requirements cannot be satisfied by local unit/integration tests alone.

## 4. Blocking Confirmations

### 4.1 Technical Dependency Confirmation

Question:

```text
May the project add `redis` / `redis.asyncio` as the real Redis Streams client?
```

Why it matters:

- Task 5 and Task 6 intentionally use a queue protocol and in-memory adapter.
- Staging requires a live Redis adapter to consume real Redis Streams.
- Adding a dependency changes the backend runtime contract and must be confirmed.

Recommended answer:

- Approve `redis` Python client.
- Keep in-memory adapter for deterministic tests.
- Add integration tests around adapter behavior without requiring a live Redis by default.

### 4.2 Deployment File Confirmation

Question:

```text
May the project add Stage03 Dockerfile / compose / Caddyfile / env example files?
```

Why it matters:

- The repo currently has `backend/docker-compose.stage02-online.yml` only.
- Stage 03 deployment docs call for API, worker, PostgreSQL, Redis and Caddy services.
- Deployment files must avoid secrets and must not perform real external writes.

Recommended answer:

- Approve local repository deployment files.
- Keep real `.env` values outside git.
- Use `.env.stage03.example` or documented placeholders only.

### 4.3 External Operation Confirmation

Question:

```text
May Codex execute commands against Tencent Cloud CVM, DNS provider or Telegram Bot API?
```

Current answer:

- Not yet confirmed.

Rule:

- Even if deployment files are approved, real external operations require separate explicit confirmation at the moment of execution.

## 5. Preconditions Before Real Staging

| Precondition | Required Evidence | Current Status |
| --- | --- | --- |
| Branch pushed or server can access code | git remote/branch evidence | not checked in this audit |
| Real Redis adapter exists | tests and dependency manifest | pending confirmation |
| Stage03 compose file exists | repo file with API/worker/postgres/redis/caddy | pending |
| Caddyfile exists | repo file or server-side config | pending |
| Secret template exists | `.env.example` style placeholders only | pending |
| Staging server exists | user-provided CVM/IP/SSH path | pending user input |
| Domain/subdomain exists | user-provided DNS plan | pending user input |
| Telegram bot token available outside git | user-provided secret handling | pending user input |
| Webhook secret generated outside git | user-provided secret handling | pending user input |
| Safety env values set | `TELEGRAM_SEND_MODE=dry_run`, `LLM_ENABLED=false`, `PROVIDER_MODE=disabled` | implemented in config validation, not deployed |

## 6. What Can Be Done Before External Confirmation

Allowed without external writes:

- Add real Redis adapter behind the existing `RedisStreams` protocol after dependency confirmation.
- Add Stage03 deployment files with placeholders.
- Add `.env.stage03.example` without secrets.
- Add worker entrypoint command.
- Add deployment dry-run documentation.
- Run local tests, static checks and secret scans.

Not allowed without explicit confirmation:

- SSH into Tencent Cloud CVM.
- Change DNS.
- Call Telegram `setWebhook`.
- Store real Bot Token or webhook secret in git.
- Enable Telegram send mode.
- Enable LLM or provider mode.

## 7. Proposed Next Implementation Slice

If user approves option A:

```text
Task 7A: Real Redis Adapter And Deployment Files
-> add redis dependency
-> implement RedisStreams adapter
-> add tests for adapter contract where possible
-> add worker entrypoint factory
-> add Dockerfile / compose / Caddyfile / env example
-> update docs and acceptance checklist
-> do not deploy externally yet
```

Acceptance for Task 7A:

- Existing in-memory worker tests still pass.
- Redis adapter code imports without live Redis requirement in normal tests.
- Compose/Caddy/env files contain no real secrets.
- Full backend suite passes.
- Secret scan finds no tokens or passwords.

If user chooses documentation-only:

```text
Task 7B: Deployment Runbook Hardening
-> no new dependency
-> no deployment code
-> expand operational checklists and command templates
-> keep Stage 03 acceptance pending
```

Acceptance for Task 7B:

- Docs clearly state exact remaining decisions and external operation gates.
- No backend code changes.
- No real external writes.

## 8. Required User Choices

Please choose one:

| Choice | Meaning |
| --- | --- |
| A | Approve `redis` / `redis.asyncio` dependency and local deployment files; real server/DNS/webhook still require later confirmation |
| B | Do not add Redis dependency yet; only improve deployment docs/checklists |
| C | Pause Stage 03 implementation and do a broader stage audit or push current branch |

## 9. Non-Completion Statement

Stage 03 is not complete until:

- Real Redis runtime is wired or explicitly accepted as out of scope.
- Tencent Cloud staging rehearsal is executed and documented.
- Real Telegram test message reaches `telegram_inbox`.
- Worker processing evidence is observed in staging.
- Full backend suite is rerun after final changes.
- Acceptance checklist records pass/fail/not-tested for every Stage 03 item.
