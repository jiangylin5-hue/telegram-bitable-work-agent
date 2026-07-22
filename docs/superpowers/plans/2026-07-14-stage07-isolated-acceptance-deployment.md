# Stage07 Isolated Acceptance Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the approved Stage07 snapshot in a parallel, disposable Tencent Cloud environment and collect only the bounded TD007/TD008 external evidence without touching Stage03.

**Architecture:** Reuse the project's Docker Compose, Postgres, Redis, FastAPI, existing Worker/Outbox and Caddy topology. A second Compose project has independent state and joins the existing Caddy Docker network only through two fixed aliases. The existing Caddy keeps its Stage03 host block and receives a separately validated Stage07 host after DNS resolves.

**Tech Stack:** Docker Compose, Caddy 2, PostgreSQL 16/pgvector, Redis 7, FastAPI/Uvicorn, React/Vite static build, existing Telegram Bot API and OpenRouter adapters.

## Global Constraints

- Run only on the user-approved Tencent Cloud non-production server and preserve the existing Stage03 project/health route throughout.
- Do not print, commit, archive or document secret values, raw Telegram identifiers, raw `initData`, deep links or record values.
- Use a new named Compose project, database volume, Redis volume and remote directory; never point Stage07 `DATABASE_URL` or `REDIS_URL` to Stage03.
- Do not activate a Caddy host or invoke TD008 delivery until the hostname resolves to this server, Caddy validates, HTTPS is healthy, and the existing restricted-send preflight is green.
- Use only Codex's in-app Browser for web UI observation; never control the user's browser.
- A failed or uncertain external send is terminal and fail-closed. Never retry it automatically.

---

### Task 1: Commit deployable, non-secret topology assets and validate them locally

**Files:**
- Create: `deploy/stage07-acceptance/compose.yml`
- Create: `deploy/stage07-acceptance/Dockerfile.web`
- Create: `deploy/stage07-acceptance/nginx.conf`
- Create: `deploy/stage07-acceptance/runtime/.env.stage07-acceptance.example`
- Create: `deploy/stage07-acceptance/Caddyfile.stage07-host`
- Create: `deploy/stage07-acceptance/scripts/validate-runtime-presence.sh`
- Test: Compose interpolation and Caddy parse validation.

- [ ] Create a Compose project named `stage07-acceptance` with independent `postgres`, `redis`, `migrate`, `api`, `outbox-bridge`, `worker` and `web` services. Attach only `api`/`web` to the existing external Caddy network with aliases `stage07-api`/`stage07-web`; publish no new host ports.
- [ ] Build the web image in a Node builder stage, run `npm ci` and `npm run build`, then serve `dist` with Nginx without injecting runtime secrets.
- [ ] Set service environment solely through the ignored runtime file and explicit non-secret Compose defaults. The migration is a one-shot profile service; API/worker/outbox depend on healthy isolated Postgres/Redis.
- [ ] Provide a key-presence script that outputs only `configured`/`missing`, one-value allowlist count, send mode equality and username validity.
- [ ] Validate `docker compose --env-file runtime/.env.stage07-acceptance config` using a generated non-secret local fixture and validate the Caddy fragment in a Caddy container. Expected: zero interpolation error and one static/API host split.

### Task 2: Stage a reviewed source snapshot and provision isolated data services

**Files:**
- Create temporarily then delete: `artifacts/stage07-acceptance-source.tar.gz`
- Remote create: `/home/ubuntu/stage07-acceptance`
- Remote create: `/home/ubuntu/stage07-acceptance/runtime/.env.stage07-acceptance`

- [ ] Produce a source archive that excludes `.git`, `.local`, all `.env*`, node modules, build output, local test databases and SSH material; list the archive manifest and reject an excluded-path match before upload.
- [ ] Upload the archive and deployment assets to the new remote directory. Verify the remote tracked source revision/working tree manifest without reading Stage03 application data.
- [ ] If no private test target is configured, run the one-time capture helper only after the user sends `/stage07-bind` privately to the configured Bot. Its temporary polling snapshots/restores the webhook, accepts only private messages, writes Chat/User IDs only to the ignored Stage07 env, and emits fixed status only. A timeout/non-private message writes nothing.
- [ ] Generate isolated Postgres/Redis credentials locally on the server without printing them. Copy only the approved provider/Bot runtime keys internally from the existing server secret file; write the new URL credentials and the existing safe real-provider contract (`LLM_ENABLED=true`, `AGENT_WORKFLOW_MODE=real_openrouter`, `PROVIDER_MODE=disabled`) only to the ignored Stage07 env file.
- [ ] Start only isolated Postgres/Redis, wait for health, run `migrate` once and verify the Alembic head. Start API/Outbox/Worker/Web only after the migration succeeds. Expected: all Stage07 containers healthy; Stage03 container states unchanged.

### Task 3: Activate the parallel HTTPS host only after DNS and Caddy validation

**Files:**
- Modify remotely with backup: `/home/ubuntu/telegram-bitable-work-agent/deploy/stage03/Caddyfile`
- Retain: timestamped Caddy backup inside the same remote deploy directory

- [ ] Verify the selected hostname resolves to `43.160.215.224`; if it does not, stop at `dns-blocked` and record the missing A/AAAA record rather than altering Caddy.
- [ ] Render the Stage07 Caddy host fragment with the validated hostname. Confirm it contains no modification to the existing Stage03 host block and uses only `stage07-web` for static paths and `stage07-api` for all other paths.
- [ ] Back up the active Caddyfile, install the candidate, run `caddy validate` inside the existing Caddy container, then reload only after validation succeeds. Expected: existing API host remains `200`, new HTTPS host becomes `200`, and no new listener is opened.
- [ ] If validation, certificate issuance or either health check fails, restore the backup and reload it before any Telegram delivery work.

### Task 4: Execute the bounded real smoke, reconcile evidence and clean up

**Files:**
- Modify: `project-docs/08-implementation/evidence/stage07-final-acceptance-closure.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`

- [ ] Run the server-side safe configuration preflight. Verify `restricted_test`, exactly one allowlisted private chat, a valid Bot username and the current Main Mini App HTTPS host without displaying their values.
- [ ] Use backend services to create only a disposable authorized fixture and one active test binding. Execute exactly one explicit TD008 confirmation/Worker dispatch; record only its fixed terminal receipt.
- [ ] The human opens the one delivered button in Telegram. Use the deployed Mini App through Codex in-app Browser only for non-Telegram HTTPS/UI health; record real Telegram `initData`/resolver/reread outcome only when direct, sanitized evidence exists.
- [ ] Remove the isolated Compose project/volumes, synthetic data, Caddy host block/backup and temporary SSH key unless retention is explicitly authorized. Verify Stage03 health before and after cleanup.
- [ ] Run `git diff --check` and update every S6I/S6D/S6.1 row strictly from direct evidence. Do not mark Stage07 complete while non-S6 acceptance rows remain open.

## Plan Self-Review

- Scope coverage: isolation, artifact hygiene, independent data, Caddy/DNS, runtime safety, one-attempt delivery, real Mini App observation, rollback and evidence each have an owning task.
- External gates: DNS, BotFather, test-chat and Telegram human interaction stop safely with exact blocker status; no mock can close them.
- Product boundaries: no new product schema/API/permission model or general notification capability is introduced.
- Placeholder scan: each deployment artifact, command category and expected terminal behavior is named; secret values are intentionally excluded by the documented security contract.
