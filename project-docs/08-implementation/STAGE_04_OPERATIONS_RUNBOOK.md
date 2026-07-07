# Stage 04 Operations Runbook

## Status

- Document status: active operations runbook draft
- Scope: Stage 04 staging operations for binding rehearsal and restricted test send.
- Current Progress: 2026-07-07 Runbook remains the Task 10 staging procedure for binding rehearsal and restricted test send. It has not been executed; no staging env change, migration, or real Telegram send has been performed for Stage 04.

## 1. Operating Principles

- Do not run real staging operations without explicit user confirmation.
- Do not store secrets or real allowlist values in git.
- Do not send to customer groups.
- Do not enable OpenRouter, provider mode or funds-related execution.
- Record redacted evidence in `STAGE_04_ACCEPTANCE_CHECKLIST.md`.

## 2. Required Server Env

Stage 04 staging may add:

```text
TELEGRAM_SEND_MODE=restricted_test
TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=<server-only comma separated test chat ids>
TELEGRAM_BOT_TOKEN=<server-only bot token>
```

Existing required env remains:

```text
APP_ENV=staging
DATABASE_URL=<server-only>
REDIS_URL=<server-only>
TELEGRAM_WEBHOOK_SECRET=<server-only>
LLM_ENABLED=false
PROVIDER_MODE=disabled
```

Compose behavior:

- `api`, `outbox-bridge` and `worker` read `TELEGRAM_SEND_MODE` from server env with a safe default of `dry_run`.
- `migrate` keeps `TELEGRAM_SEND_MODE=dry_run`; migration must not depend on Telegram send capability.
- `LLM_ENABLED=false` and `PROVIDER_MODE=disabled` remain forced by compose for runtime services.

## 3. Preflight

Before Stage 04 staging rehearsal:

1. Confirm current git commit.
2. Confirm no uncommitted deployment files on server.
3. Confirm `TELEGRAM_SEND_MODE` policy with user.
4. Confirm test chat id is not a customer group or internal ops group.
5. Confirm Bot token has been rotated/stored safely if needed.
6. Run migration.
7. Verify services healthy.

Required operator access:

- SSH user and key/password must be provided through a secure out-of-repo channel.
- SSH credentials, Tencent Cloud console credentials and server `.env.stage03` contents must not be committed or pasted into project docs.
- If SSH is unavailable, Task 10 can only proceed through a user-controlled terminal session where these runbook commands are executed and redacted evidence is returned.

## 4. Binding Rehearsal

Expected flow:

```text
POST /telegram/bindings
-> GET /views/telegram_bindings/records
-> send new Telegram test message
-> GET /views/telegram_inbox/records
-> inspect audit
```

Record:

- binding id。
- customer id。
- binding scope。
- redacted chat/user id。
- new update id。
- inbox `binding_status`。
- audit event types。

## 5. Restricted Test Send Rehearsal

Expected flow:

```text
POST /telegram/send-requests
-> POST /telegram/send-requests/{id}/confirm
-> outbox bridge
-> Redis worker
-> Telegram sendMessage
-> telegram_send_requests status = sent
-> audit
```

Record:

- send request id。
- status transitions。
- target is allowlisted test chat: yes/no; do not record full allowlist if sensitive。
- Telegram response summary。
- audit event types。

## 6. Rollback

If Stage 04 deployment fails before migration:

- Stop new containers.
- Redeploy previous Stage 03 commit.

If migration succeeds but app fails:

- Keep database; do not manually delete Stage 04 tables unless user confirms.
- Redeploy previous app if backwards compatible with additive migration.
- Record risk in progress log.

If test send misconfiguration is detected:

- Set `TELEGRAM_SEND_MODE=dry_run`.
- Clear server-side `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`.
- Restart worker/API.
- Record audit and progress entry.

## 7. Forbidden Operations

- Do not use production database.
- Do not put customer group ids in test send allowlist.
- Do not send customer-facing messages.
- Do not enable `LLM_ENABLED=true`.
- Do not enable provider mode.
- Do not run destructive database reset on staging without user confirmation.
