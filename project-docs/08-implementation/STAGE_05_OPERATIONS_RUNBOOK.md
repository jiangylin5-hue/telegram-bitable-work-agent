# Stage 05 Operations Runbook

## Status

- Document status: active operations runbook draft
- Scope: Local preflight, staging deployment, OpenRouter rehearsal, Telegram allowlisted send, evidence capture and safety close for Stage05.
- Current Progress: 2026-07-07 Runbook drafted and updated after local implementation through Task11. Local staging-contract preflight test `tests/integration/test_stage05_staging_contract.py` was added for server-env safety assumptions. No Stage05 Tencent Cloud staging operation, real OpenRouter call or real Telegram send has been executed.
- Current Progress Update: 2026-07-07 Task12 evidence ledger template and safety-close checklist were added so staging evidence can be captured as redacted, pass/fail-oriented records after explicit approval.
- Current Progress Update: 2026-07-07 Pre-staging approval packet was linked as the required approval boundary before Task12 external actions.
- Current Progress Update: 2026-07-07 Task12 staging command/evidence map was added. It reuses the Stage03/Stage04 Tencent Cloud staging pattern, records the Stage05 runtime deltas, and requires redacted runtime proof before any real OpenRouter rehearsal.
- Current Progress Update: 2026-07-07 Stage05 deployment config gate was added locally. `deploy/stage03/compose.yml` keeps safe defaults but now lets approved staging env set `LLM_ENABLED=true`, `AGENT_WORKFLOW_MODE=real_openrouter` and OpenRouter metadata for `api`, `outbox-bridge` and `worker`; `migrate` remains LLM-off/fake. `tests/unit/test_stage05_deploy_compose.py` covers this without executing staging.
- Current Progress Update: 2026-07-07 Redacted runtime summary CLI was added locally as `python -m app.core.runtime_summary`. It prints only booleans, modes, presence flags and validation status for Task12 runtime evidence, without raw secrets, raw allowlists or connection URLs.
- Current Progress Update: 2026-07-08 Local real OpenRouter workflow gate passed after the entity-key prompt contract fix. The routed draft scenario created pending-confirmation recharge and customer-reply drafts with `reply_text_present=true`; the default risk scenario safely returned `manual_review` with no draft/provider/send side effects.

## 1. Safety Rules

Before any Stage05 staging action:

- Review [Stage 05 Pre-Staging Approval Packet](STAGE_05_PRE_STAGING_APPROVAL_PACKET.md).
- Ask user for explicit approval before changing server env.
- Ask user for explicit approval before real OpenRouter call.
- Ask user for explicit approval before real Telegram send.
- Keep provider mode disabled.
- Do not record secrets or raw allowlist values in docs.
- Use private allowlisted test chat only.

## 2. Local Preflight

Run after Stage05 implementation and before staging:

```text
cd backend
pytest tests/unit/test_stage05_config.py -v
pytest tests/unit/test_stage05_router_schema.py -v
pytest tests/unit/test_stage05_child_agents.py -v
pytest tests/unit/test_stage05_account_inventory_agent.py -v
pytest tests/unit/test_stage05_bitable_views.py -v
pytest tests/integration/test_stage05_agent_workflow.py -v
pytest tests/integration/test_stage05_service_draft_confirmation.py -v
pytest tests/integration/test_stage05_customer_reply_send.py -v
pytest tests/integration/test_stage05_staging_contract.py -v
pytest tests -q
alembic upgrade head --sql
```

Secret scan:

```text
rg -n "sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_BOT_TOKEN|OPENROUTER_API_KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
```

Expected:

- Tests pass except documented online skips.
- Alembic offline SQL reaches Stage05 head.
- Scan finds placeholders only.
- Staging contract tests prove: real OpenRouter mode requires server-side key, restricted Telegram send requires bot token and allowlist, provider mode remains disabled, and safety close returns to dry-run with empty allowlist.

### 2.1 Local Real OpenRouter Workflow Gate

After deterministic local tests and before any staging retry that depends on real model behavior, run [Stage 05 Local Real Workflow Env](STAGE_05_LOCAL_REAL_WORKFLOW_ENV.md).

Required properties:

- The key is stored only in the git-ignored `.local/stage05-real-workflow.env`.
- The script calls OpenRouter through the Stage05 router prompt.
- The script runs `Stage05AgentWorkflowService` with in-memory message/account data.
- The evidence contains only redacted workflow metadata, selected agents, intent types, draft summaries, account status event summaries and audit event types.
- The evidence does not contain raw key, Telegram token, raw allowlist, raw prompt or raw response.
- `PROVIDER_MODE` stays `disabled`.
- `TELEGRAM_SEND_MODE` stays `dry_run`.

Command:

```text
cd backend
python scripts/stage05_local_real_workflow.py
```

Do not proceed to staging if this workflow fails with `agent_output_invalid`, `llm_runtime_error` or any safety preflight error.

Current pass evidence after the entity-key prompt contract fix:

```text
routed draft scenario:
workflow_status=routed
model_provider=openrouter
prompt_version=stage05-router-v1
intent_types=recharge,customer_reply
service_drafts=recharge:pending_confirmation,customer_reply:pending_confirmation
provider_execution_allowed=false
send_request_created=false
reply_text_present=true

default risk scenario:
workflow_status=manual_review
intent_types=recharge,bm_invite,customer_reply,account_status_exception
service_drafts=none
provider_mode=disabled
telegram_send_mode=dry_run
```

## 3. Staging Env Variables

Server-side only:

```text
LLM_ENABLED=true
AGENT_WORKFLOW_MODE=real_openrouter
OPENROUTER_API_KEY=<server-only>
OPENROUTER_MODEL=<configured model>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
TELEGRAM_SEND_MODE=restricted_test
TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=<private test chat only>
PROVIDER_MODE=disabled
```

Never write real values into:

- git
- project docs
- screenshots with visible secrets
- shell history pasted into docs

## 4. Deployment Outline

Use the established Stage03/Stage04 Tencent Cloud staging deployment pattern, then apply only the Stage05-specific deltas approved for Task12.

This section is a command/evidence map. It is not an instruction to execute staging now. Every command here is blocked until the approval packet has been explicitly approved for the matching action subset.

### 4.1 Reused Stage04 Pattern

Stage05 inherits these Stage04 operating assumptions:

| Area | Reused pattern | Stage05 requirement |
| --- | --- | --- |
| Cloud target | Tencent Cloud single-machine staging with Docker Compose and Caddy | Same staging target only; never production |
| Public entry | Caddy HTTPS reverse proxy to FastAPI | `/health`, Telegram webhook and API views must work through HTTPS |
| Runtime services | `api`, `outbox-bridge`, `worker`, `postgres`, `redis`, `caddy` | Same services, plus Stage05 Agent workflow runtime enabled only for the rehearsal window |
| Migration | one-shot `migrate` compose service | Must reach Stage05 head `20260707_0016` before rehearsal messages |
| Telegram safety | `TELEGRAM_SEND_MODE=dry_run` by default; `restricted_test` only for private allowlisted test chat | Same rule; customer reply send may target only the approved private test chat |
| Provider safety | `PROVIDER_MODE=disabled` | Must remain disabled for the entire rehearsal |
| Evidence | redacted IDs/statuses, no secrets | Must additionally include AgentRun, draft, no-op and account exception evidence |
| Safety close | send mode returns to dry-run and allowlist is cleared | Same, plus record final LLM state and no pending unsafe sends |

### 4.2 Stage05 Runtime Delta Gate

Current repository deployment files are still the Stage03/Stage04 deployment shape:

- `deploy/stage03/compose.yml`
- `deploy/stage03/env.stage03.example`
- `deploy/stage03/Caddyfile`

Important delta:

- The current `deploy/stage03/compose.yml` keeps safe defaults of `LLM_ENABLED=false`, `AGENT_WORKFLOW_MODE=fake`, `AGENT_SAVE_FULL_PROMPT=false`, `AGENT_SAVE_FULL_RESPONSE=false` and `PROVIDER_MODE=disabled`.
- The runtime services `api`, `outbox-bridge` and `worker` allow approved server env to set `LLM_ENABLED=true`, `AGENT_WORKFLOW_MODE=real_openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` and `OPENROUTER_BASE_URL` for the Stage05 rehearsal window.
- The `migrate` service remains pinned to `LLM_ENABLED="false"` and `AGENT_WORKFLOW_MODE=fake`; migration must not depend on LLM or Telegram send capability.
- Stage05 real OpenRouter rehearsal requires runtime evidence of `LLM_ENABLED=true`, `AGENT_WORKFLOW_MODE=real_openrouter` and a server-side `OPENROUTER_API_KEY`.
- Therefore, before any real OpenRouter rehearsal, the operator must prove that the deployed Stage05 artifact and approved server env actually reach the containers.
- If the runtime still reports `LLM_ENABLED=false` or `AGENT_WORKFLOW_MODE` is not `real_openrouter`, stop before sending the mixed-language test message. Do not treat this as a partial pass.

Acceptable evidence for the delta gate:

```text
runtime_env_summary:
  APP_ENV: staging
  LLM_ENABLED: true
  AGENT_WORKFLOW_MODE: real_openrouter
  OPENROUTER_API_KEY_present: yes
  AGENT_SAVE_FULL_PROMPT: false
  AGENT_SAVE_FULL_RESPONSE: false
  TELEGRAM_SEND_MODE: restricted_test
  TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS_present: yes
  PROVIDER_MODE: disabled
```

Do not record the actual key, allowlist value, database URL, Redis URL, Telegram token or webhook secret.

### 4.3 Command And Evidence Map

Use `<staging-domain>`, `<reviewed-commit>`, `<draft-id>`, `<send-request-id>` and `<private-test-chat-description>` placeholders in docs. Do not paste real secrets or raw allowlist values.

| Step | Command category | Example command shape | Evidence to record | Stop condition |
| --- | --- | --- | --- | --- |
| Approval | Human approval capture | no shell command | approval timestamp, approved action subset | approval is missing or narrower than the intended action |
| Local commit identity | local read-only git | `git rev-parse HEAD` and `git status --short` | reviewed commit hash; whether worktree has uncommitted local changes | commit/artifact cannot be identified |
| Server commit identity | server read-only git | `git rev-parse HEAD` | deployed commit before update | server is not the expected staging repo/path |
| Compose config preflight | server compose config | `cd deploy/stage03` then `docker compose --env-file .env.stage03 -f compose.yml config` | config renders; no secrets pasted into evidence | compose config fails or expands unsafe mode |
| Deploy artifact | server deploy/build | `git checkout <reviewed-commit>` then `docker compose --env-file .env.stage03 -f compose.yml build api outbox-bridge worker` | deployed commit/artifact id and build success summary | checkout/build differs from reviewed work |
| Migration | server migration | `docker compose --env-file .env.stage03 -f compose.yml --profile tools run --rm migrate` | migration command exit status and final revision | migration fails |
| Migration readback | server read-only migration state | `docker compose --env-file .env.stage03 -f compose.yml --profile tools run --rm migrate alembic current` | `20260707_0016` or later approved Stage05 head | current head is older than Stage05 |
| Service restart | server service control | `docker compose --env-file .env.stage03 -f compose.yml up -d api outbox-bridge worker caddy` | service names and start timestamp | service fails to start |
| Service health | public HTTPS/API | `curl -fsS https://<staging-domain>/health` | redacted health response and timestamp | unhealthy or unreachable |
| Runtime env proof | container read-only config check | run a redacted settings summary inside `api` and `worker` containers | booleans/presence only for Stage05 env; no values | `LLM_ENABLED=false`, no OpenRouter key, send mode not restricted, provider not disabled |
| Telegram webhook readiness | public webhook negative check or Telegram info summary | invalid-secret request should be rejected; webhook info summary may be recorded redacted | invalid secret rejected; webhook points to staging | webhook points outside staging or accepts invalid secret |
| Inbound test message | manual Telegram send to test bot | manual action from controlled test chat | Telegram update id and message id only | message came from customer/group or uncontrolled chat |
| Inbox view evidence | Bitable-like view API | `curl -fsS "https://<staging-domain>/views/telegram_inbox/records?limit=5"` | message row, `intent_status`, `agent_status`, `draft_count`, trace id | row missing or raw secret/prompt appears |
| Service draft evidence | API/view readback | `curl -fsS "https://<staging-domain>/service-drafts?trace_id=<trace-id>&limit=10"` and `/views/service_drafts/records` | draft ids, types, statuses, missing fields, risk flags | no draft evidence and no explainable agent failure |
| Agent evidence | Bitable/API/read-only redacted evidence | prefer view-derived Agent fields; if needed, operator-only read-only redacted `agent_runs` summary | AgentRun id, model, usage/cost/latency, redacted output summary | no model metadata or raw prompt/response is required to explain result |
| Customer reply confirmation | confirmation API | `POST /confirmations/service-drafts/<draft-id>/actions` with `action=confirm` | send request id, side effect `customer_reply_send_request_created` | target not allowlisted or actor lacks permission |
| Send confirmation | send API | `POST /telegram/send-requests/<send-request-id>/confirm` with `{"confirm": true}` | queued/sent/failed status and private test-chat receipt summary | target drifts from private allowlisted test chat |
| Business no-op confirmation | confirmation API | `POST /confirmations/service-drafts/<draft-id>/actions` with `action=confirm` | service record id, no execution ticket, noop execution log id/status | execution ticket/provider write appears |
| Account exception branch | controlled fixture/message plus view/API readback | use the controlled risk message and inspect `account_inventory` view | status event id, abnormal status, confidence/risk flags | auto replacement/reservation/distribution appears |
| Audit evidence | Bitable audit view or redacted operator query | inspect audit event types linked to workflow/message/draft/send | event ids/types only | audit trail missing |
| Safety close | server env/service control | set send mode dry-run, clear allowlist, provider disabled; restart affected services | dry-run, empty allowlist, provider disabled, no pending unsafe sends | cannot verify close state |

### 4.4 Redacted Runtime Summary Command

Use the built-in redacted runtime summary command. The command prints JSON with presence/booleans only. It must never print secret values.

```text
docker compose --env-file .env.stage03 -f compose.yml exec api python -m app.core.runtime_summary
docker compose --env-file .env.stage03 -f compose.yml exec worker python -m app.core.runtime_summary
```

Expected summary fields:

```json
{
  "app_env": "staging",
  "llm_enabled": true,
  "agent_workflow_mode": "real_openrouter",
  "openrouter_key_present": true,
  "openrouter_model_present": true,
  "agent_save_full_prompt": false,
  "agent_save_full_response": false,
  "telegram_send_mode": "restricted_test",
  "telegram_bot_token_present": true,
  "telegram_test_send_allowlist_present": true,
  "provider_mode": "disabled",
  "runtime_settings_valid": true,
  "validation_error": null
}
```

If the deployed containers do not show these values after an approved Stage05 env change, stop before the first real OpenRouter call. Do not work around it by pasting keys into commands, logs or docs.

The output must not contain:

- OpenRouter API key value.
- Telegram Bot token value.
- Telegram test chat allowlist value.
- Telegram webhook secret value.
- Database URL or Redis URL.

### 4.5 API Evidence Request Shapes

These request shapes are evidence examples only. Use the real staging URL and redacted IDs during an approved rehearsal.

```text
GET https://<staging-domain>/health
GET https://<staging-domain>/views/telegram_inbox/records?limit=5
GET https://<staging-domain>/service-drafts?trace_id=<trace-id>&limit=10
GET https://<staging-domain>/views/service_drafts/records?limit=10
GET https://<staging-domain>/views/agent_review_queue/records?limit=10
GET https://<staging-domain>/views/pending_confirmation/records?limit=10
GET https://<staging-domain>/views/customer_reply_send_requests/records?limit=10
GET https://<staging-domain>/views/account_inventory/records?limit=10
```

Confirmation shapes:

```json
{
  "action": "confirm",
  "actor_type": "user",
  "actor_id": "<manager-actor-id>",
  "role": "manager",
  "reason": "approved for Stage05 staging rehearsal"
}
```

```json
{
  "confirm": true
}
```

Do not confirm a `customer_reply` unless the linked send request target has already been checked against the private test-chat allowlist.

### 4.6 Operator Query Boundary

Use Bitable-like APIs and service APIs first. If a required evidence field has no safe API yet, a human operator may capture a read-only, redacted database/query/log summary for the acceptance report.

Rules:

- The Agent must not receive raw database credentials or run ad hoc SQL.
- Operator evidence must include only ids, statuses, event types, model names, token/cost summaries and redacted summaries.
- Operator evidence must not include raw prompt, raw OpenRouter response, Bot token, OpenRouter key, database URL, Redis password, webhook secret, raw allowlist values, raw card data or customer group ids.
- If the only way to debug is to expose raw prompt/response or secrets, stop the rehearsal and record an abort reason instead of continuing.

High-level steps:

1. Confirm local commit.
2. Pull/checkout commit on staging.
3. Build/restart affected services.
4. Run migrations.
5. Check `/health`.
6. Check current env redacted.
7. Run Stage05 rehearsal.

Exact server commands depend on current deployment path and should follow the Stage04 runbook style. Record only redacted evidence.

## 5. Rehearsal Message

Use a mixed Chinese/English message similar to:

```text
帮 act_stage05_test 充值 100 USD，顺便看下 BM invite 能不能处理；如果客户问进度，就回复说我们正在确认账户和资料。
```

For account risk branch, use a controlled staging account fixture and message:

```text
这个 act_stage05_risk 账号好像被封了，先标记异常，别自动换号。
```

Do not use a real customer account or real production chat.

## 6. Evidence To Capture

Record redacted:

- Staging commit.
- Alembic revision.
- Service health.
- Telegram update id.
- Message id.
- Agent run id.
- OpenRouter model and usage summary.
- Draft ids and draft types.
- Account status event id if triggered.
- Customer reply send request id.
- Telegram send status.
- Service/no-op evidence id.
- Audit event types.
- Safety close state.

Do not record:

- Bot token.
- OpenRouter key.
- Database URL.
- Redis password.
- Raw allowlist chat id.
- Full prompt.
- Full raw OpenRouter response.

## 7. Task12 Evidence Ledger Template

Use this ledger during the approved staging rehearsal. Keep real secrets, raw allowlist values, full prompt text and full raw OpenRouter responses out of the record.

| Evidence item | Required redacted value | Pass condition | Failure action |
| --- | --- | --- | --- |
| Approval scope | Approval timestamp and allowed actions: env change, real OpenRouter, allowlisted Telegram test send | Approval explicitly covers the action being performed | Stop before touching staging |
| Staging commit | Git commit hash or deployment artifact id | Matches the reviewed Stage05 worktree/commit | Stop and redeploy the expected revision |
| Deployment timestamp | UTC or local server time | Captured before rehearsal message | Record actual time before continuing |
| Migration head | `alembic current` showing Stage05 head `20260707_0016` | Current head includes Stage05 reply-send linkage migration | Stop before message rehearsal |
| Service health | `/health` or equivalent redacted output | API and worker are healthy | Stop and inspect logs |
| Env proof: LLM | `LLM_ENABLED=true`, `AGENT_WORKFLOW_MODE=real_openrouter`, OpenRouter key present but redacted | Real OpenRouter is enabled server-side only | Stop before rehearsal message |
| Env proof: provider | `PROVIDER_MODE=disabled` | Provider writes cannot run | Stop and safety-close |
| Env proof: Telegram send | `TELEGRAM_SEND_MODE=restricted_test`, allowlist present and described as private test chat only | Only the private test chat is allowed | Stop before confirming any reply |
| Mixed-language inbound message | Telegram update id and message id only | Message is from the controlled test context | Stop if it came from a real customer/group |
| Router/AgentRun evidence | AgentRun id, model name, usage/cost/latency, redacted summary and structured result | Real model metadata is present without raw prompt/response | Mark `agent_failed` evidence if unavailable |
| Draft evidence | Draft ids, draft types, statuses and linked message id | Multiple expected draft types are created or missing fields are explainable | Record mismatch and do not force confirmation |
| Customer reply confirmation | Draft id, confirmation actor, send request id, final send status | Send request targets private allowlisted test chat only | Block send and safety-close if target drifts |
| Business no-op confirmation | Draft id, service record id, noop execution log id | Provider is `noop` and execution status is `skipped` | Stop if any provider ticket/write appears |
| Account exception branch | Controlled account fixture, status event id, status value, audit event id | Only allowed abnormal statuses are used; replacement action remains `none` | Revert/flag if status is wrong |
| View evidence | Redacted view/API evidence for `service_drafts`, `agent_review_queue`, `pending_confirmation`, `customer_reply_send_requests`, `telegram_inbox`, `account_inventory` | Records are visible with expected masking/scope | Record failed view and inspect service query |
| Audit evidence | Event ids/types for route, draft, confirmation, send/no-op and account exception where applicable | Audit trail links to workflow/message/draft/send ids | Stop final acceptance until audit is present |
| Out-of-scope confirmation | Statement that no customer/group send, provider write, funds movement, production launch, UI/Mini App or auto replacement occurred | All out-of-scope items remain false | Stop acceptance and record incident |
| Safety close | Send mode dry-run, allowlist empty, provider disabled, no pending unsafe send requests | Safety close is verified after rehearsal | Keep stage open only for incident response |

Minimum evidence package for final acceptance:

- One completed ledger row for each item above.
- Redacted command/output snippets or API/query summaries for each pass condition.
- Explicit skipped reason for any optional branch that was not exercised.
- A final statement that no secret, raw allowlist, full prompt or full raw OpenRouter response was recorded.

## 8. Safety Close

After rehearsal:

```text
TELEGRAM_SEND_MODE=dry_run
TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=
PROVIDER_MODE=disabled
```

Recommended:

- Keep `LLM_ENABLED` state recorded. If leaving OpenRouter enabled for further testing, document that state and ensure keys remain server-only.
- If no further immediate testing is needed, set `LLM_ENABLED=false` or Stage05 equivalent.

Verify:

- API/worker env shows send mode dry-run.
- Allowlist absent or empty.
- Provider disabled.
- No pending send request remains unprocessed.
- No `telegram_send_requests` row remains in a state that could later send to a non-allowlisted target.
- Final report records the safety-close timestamp and redacted evidence.

## 9. Failure Response

OpenRouter failure:

- Stop further Agent rehearsal.
- Verify `agent_failed` state and audit.
- Do not retry repeatedly without understanding cost/error.

Telegram send failure:

- Verify request status `failed` or `blocked`.
- Verify no customer/group send occurred.
- Keep dry-run close.

Unexpected provider call:

- Stop staging immediately.
- Record evidence.
- Disable provider credentials if any were active.
- Do not continue Stage05 until root cause is fixed.

Accidental customer send:

- Stop staging immediately.
- Safety close.
- Inform user with exact time and redacted evidence.
- Do not proceed until user decides next action.
