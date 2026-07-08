# Stage 05 Pre-Staging Approval Packet

## Status

- Document status: active pre-staging approval packet
- Scope: Stage05 Task12 real Tencent Cloud staging approval boundary, permitted actions, forbidden actions, prerequisite evidence, execution order, evidence ledger and safety close.
- Current Progress: 2026-07-08 Approval packet served as the bounded approval entry for Task12. The approved staging rehearsal, real OpenRouter call, private allowlisted Telegram send, no-op evidence, account exception evidence and safety close were executed under this packet's allowed action subset. Production, real customer chat, customer groups, provider writes, funds movement, account production, automatic replacement and secret/raw allowlist recording remain forbidden.
- Current Progress Update: 2026-07-08 Required pre-approval local evidence was refreshed before approval; Task12 approval and real staging execution later completed under this packet's boundary.
- Current Progress Update: 2026-07-07 Code readiness evidence was refreshed: Stage05 runtime files compile through Python AST, key modules import, no TODO/FIXME/NotImplemented/stub markers were found in Stage05 runtime paths, and the direct provider/network keyword scan found only the intentional sensitive-card-data rejection pattern.
- Current Progress Update: 2026-07-07 API readiness evidence was refreshed: FastAPI app creation, OpenAPI generation and Stage05 key path presence were verified locally. This does not replace real staging API evidence.
- Current Progress Update: 2026-07-07 Task12 staging command/evidence map was added to the operations runbook and linked into this packet. The map identifies the Stage05 deployment delta that must be verified before real OpenRouter rehearsal: safe defaults remain LLM-off/fake, but an approved Stage05 server env can now reach `api`, `outbox-bridge` and `worker`; runtime proof must show `LLM_ENABLED=true` and `AGENT_WORKFLOW_MODE=real_openrouter` inside the containers before any mixed-language Telegram rehearsal message.
- Current Progress Update: 2026-07-07 Stage05 deployment config gate was added locally. `tests/unit/test_stage05_deploy_compose.py` first failed against the old compose/env shape, then passed after `deploy/stage03/compose.yml` and `deploy/stage03/env.stage03.example` were updated to keep safe defaults while allowing approved real OpenRouter rehearsal env for runtime services.
- Current Progress Update: 2026-07-07 Redacted runtime summary evidence command was added locally. `python -m app.core.runtime_summary` is the approved container command for Task12 runtime env proof and is covered by `tests/unit/test_stage05_runtime_summary.py`.
- Current Progress Update: 2026-07-08 User explicitly approved Stage05 Task12 Tencent Cloud staging rehearsal at `2026-07-08 00:15:10 +08:00` using the approval wording in Section 4. Approved actions are limited to staging deployment, Stage05 migration, server-side real OpenRouter, temporary restricted Telegram private test-chat send, business no-op evidence, controlled account exception evidence, redacted evidence capture and safety close. Production, real customer chat, customer groups, provider writes, funds movement, account production, automatic replacement and secret/raw allowlist recording remain forbidden.

## 1. Purpose

This packet turns Stage05 Task12 into an explicit approval boundary.

It does not approve anything by itself. It records exactly what the user would be approving if they later confirm Task12 real staging rehearsal.

The packet exists because Stage05 final acceptance cannot be proven by local tests alone. The source of truth requires:

- real OpenRouter evidence in Tencent Cloud staging;
- real allowlisted private Telegram test-chat receipt;
- staging service draft / no-op service evidence;
- staging account exception branch evidence;
- staging view and audit evidence;
- safety close evidence.

## 2. Approval Boundary

Approval for this packet would allow only these Stage05 Task12 actions:

| Action | Allowed only if approved | Limit |
| --- | --- | --- |
| Deploy reviewed Stage05 commit/artifact to Tencent Cloud staging | yes | Staging only, not production |
| Apply Stage05 Alembic migration on staging | yes | Must end at Stage05 head `20260707_0016` |
| Set server-side OpenRouter env for rehearsal | yes | Key stays server-side and redacted |
| Run one or more real OpenRouter calls through the Stage05 Agent workflow | yes | Staging rehearsal only; usage/cost must be recorded |
| Temporarily set Telegram send mode to `restricted_test` | yes | Private allowlisted test chat only |
| Send or confirm a `customer_reply` to the private allowlisted test chat | yes | No real customer chat or group chat |
| Confirm business drafts for no-op evidence | yes | Must create no provider ticket/write |
| Exercise controlled account exception branch | yes | Controlled fixture/test account only |
| Capture redacted evidence | yes | No secrets, raw allowlist, full prompt or raw OpenRouter response |
| Safety-close staging after rehearsal | yes | Dry-run send mode, empty allowlist, provider disabled |

## 3. Still Forbidden

Approval for Task12 does not allow:

- production deployment or production traffic;
- real customer chat send;
- customer group send;
- provider write;
- funds movement;
- account production;
- automatic replacement recommendation, reservation or distribution;
- raw card data, CVV, full card image or payment secret handling;
- raw OpenRouter prompt/response storage in docs;
- committing OpenRouter key, Telegram token, database URL, Redis password or raw allowlist values;
- UI, Mini App, RAG/pgvector runtime work;
- Agent skills/capabilities runtime registry work before main Stage05 final acceptance.

## 4. Approval Text To Request

Before any Task12 external action, the approval request must name the exact allowed actions.

Recommended approval wording:

```text
确认执行 Stage05 Task12 Tencent Cloud staging rehearsal。允许在 staging 环境执行以下动作：部署 reviewed Stage05 commit/artifact，应用 Stage05 migration，启用 server-side real OpenRouter，临时启用 Telegram restricted_test send 到 private allowlisted test chat，发送/确认一条 allowlisted test reply，验证 business draft no-op evidence 和 controlled account exception evidence，采集 redacted evidence，并完成 safety close。仍禁止 production、真实客户 chat、客户群、provider write、资金动作、账户生产、自动换号和任何 secret/raw allowlist 落库或入文档。
```

If the user approves only part of the wording, execute only that approved subset and mark skipped rows in the evidence ledger.

## 5. Required Pre-Approval Evidence

Before asking for approval, local evidence must be current enough to avoid known unsafe deployment.

| Evidence | Required state before approval request |
| --- | --- |
| Focused Stage05 tests | Passing or rerun immediately before staging |
| Full backend suite | Passing except documented online PostgreSQL smoke skips, or explicitly rerun/skipped with reason |
| Staging contract tests | Passing |
| Scope guard tests | Passing |
| Alembic offline SQL | Reaches `20260707_0016` |
| Secret scan | No real key/token/private key/raw allowlist |
| Runtime code readiness | Stage05 runtime files compile, key modules import, and no unresolved TODO/NotImplemented markers are present |
| API/OpenAPI readiness | FastAPI app creates, OpenAPI generates, and Stage05 key API paths are present |
| `git diff --check` | No whitespace errors |
| Task12 command/evidence map | Operations runbook Section 4 reviewed; Stage04 deployment reuse and Stage05 runtime delta are understood |
| Stage05 deployment config gate | Runtime compose/env defaults stay safe, and approved real OpenRouter env can reach `api`, `outbox-bridge` and `worker` |
| Redacted runtime summary command | `python -m app.core.runtime_summary` exists and omits raw secrets/allowlists/connection URLs |
| Approval packet | This document reviewed |
| Operations runbook | Task12 evidence ledger ready |

Current local pre-approval evidence snapshot:

| Evidence | Latest local result |
| --- | --- |
| Focused Stage05 tests | `pytest tests -k stage05 -v`: 82 passed / 190 deselected |
| Scope guard tests | `pytest tests\unit\test_stage05_scope_guards.py -v`: 4 passed |
| Staging contract tests | `pytest tests\integration\test_stage05_staging_contract.py -v`: 5 passed |
| Full backend suite | `pytest tests -q`: 255 passed / 17 skipped |
| Skipped tests | 17 online PostgreSQL smoke tests skipped because `STAGE02_ONLINE_DATABASE_URL` is not configured |
| Alembic offline SQL | `alembic upgrade head --sql` reaches `20260707_0016` and emits `source_service_draft_id`, `send_purpose`, `message_text_summary`, `fk_tg_send_req_source_draft` and related indexes |
| Strict secret scan | No matches for high-risk private key, OpenRouter-style key, Telegram bot token or GitHub token patterns; raw allowlist assignment scan also returned no matches |
| Runtime AST compile | Python AST compile over `app/agents`, `app/services`, `app/api/routes` and `app/workers`: `compiled=50`, `stage05-runtime-ast-ok` |
| Key Stage05 module imports | Import check over supervisor, router, child agents, account inventory, workflow, confirmation and Bitable view modules: `stage05-imports-ok` |
| TODO / placeholder scan | No `TODO`, `FIXME`, `NotImplemented`, `raise NotImplementedError` or `stub` matches in Stage05 runtime paths |
| Direct provider/network scan | No direct `httpx`/`requests`/Meta/provider/client/raw-card action imports in Stage05 runtime paths; the only hit was `SENSITIVE_PAYMENT_PATTERN` in `card_binding_draft_agent.py`, which rejects card/CVV-like input |
| API/OpenAPI readiness | `create_app().openapi()` generated 13 paths from 18 routes and included `/service-drafts`, `/confirmations/service-drafts/{draft_id}/actions`, `/telegram/send-requests/{request_id}/confirm` and `/views/{view_key}/records`: `stage05-api-openapi-readiness-ok` |
| Whitespace check | `git diff --check`: no whitespace errors; Windows LF-to-CRLF warnings only |
| Task12 command/evidence map | `STAGE_05_OPERATIONS_RUNBOOK.md` Section 4 maps approval, deploy, migration, runtime env, real OpenRouter, Telegram send, views, audit and safety-close evidence. It records that safe defaults stay LLM-off/fake, while approved server env must be proven inside containers before real OpenRouter calls. |
| Stage05 deployment config gate | RED/GREEN `pytest tests\unit\test_stage05_deploy_compose.py -v`: old compose/env shape failed the Stage05 runtime override test; updated compose/env shape passed 2/2 and keeps `migrate` LLM-off/fake with `PROVIDER_MODE=disabled` |
| Redacted runtime summary command | RED/GREEN `pytest tests\unit\test_stage05_runtime_summary.py -v`: missing module failed first, then passed 3/3 after adding `app.core.runtime_summary`; direct local `python -m app.core.runtime_summary` prints JSON with no secret values |
| External actions | No Tencent Cloud staging env change, real OpenRouter call, real Telegram send, provider execution, dependency install, git staging or commit was performed |

## 6. Execution Order After Approval

Follow this order after approval. Stop immediately if a pass condition fails.

Use [Stage 05 Operations Runbook](STAGE_05_OPERATIONS_RUNBOOK.md) Section 4 as the Task12 command/evidence map. The Stage05-specific deployment delta must be checked before the first real OpenRouter call:

- current Stage03/Stage04 compose files are safe by default: runtime services default to `LLM_ENABLED=false` and `AGENT_WORKFLOW_MODE=fake`, and `migrate` remains pinned LLM-off/fake;
- runtime services can accept approved Stage05 env overrides for `LLM_ENABLED=true`, `AGENT_WORKFLOW_MODE=real_openrouter` and OpenRouter metadata;
- Stage05 real OpenRouter rehearsal requires approved runtime evidence of `LLM_ENABLED=true`, `AGENT_WORKFLOW_MODE=real_openrouter`, server-side `OPENROUTER_API_KEY` presence, `AGENT_SAVE_FULL_PROMPT=false`, `AGENT_SAVE_FULL_RESPONSE=false`, `TELEGRAM_SEND_MODE=restricted_test`, allowlist presence and `PROVIDER_MODE=disabled`;
- if the deployed containers cannot prove that state with redacted runtime summaries, stop before sending the mixed-language Telegram test message.

1. Record approval timestamp and approved action subset.
2. Confirm reviewed commit/artifact and deployment target are staging-only.
3. Deploy to Tencent Cloud staging using the established Stage04 deployment pattern.
4. Run migration and verify `alembic current` is at Stage05 head.
5. Verify service health and worker health.
6. Apply server-side env or approved deployment override for real OpenRouter and restricted Telegram test send.
7. Verify the Stage05 runtime delta inside `api` and `worker` containers with redacted settings summaries.
8. Verify provider remains disabled.
9. Send controlled mixed Chinese/English inbound Telegram test message.
10. Verify `telegram_inbox`, message status and AgentRun evidence.
11. Verify service drafts and Bitable-like views.
12. Confirm `customer_reply` only if target is the private allowlisted test chat.
13. Verify Telegram receipt in the allowlisted test chat.
14. Confirm business draft and verify service/no-op evidence.
15. Exercise account exception branch with controlled fixture/test message.
16. Verify audit events.
17. Complete the Task12 evidence ledger in `STAGE_05_OPERATIONS_RUNBOOK.md`.
18. Safety-close staging.
19. Update final acceptance report, acceptance checklist and progress log.

## 7. Abort Conditions

Stop the rehearsal and safety-close if any of these occur:

| Abort condition | Required action |
| --- | --- |
| Approval scope is unclear | Stop before staging env change |
| Deployed commit/artifact differs from reviewed Stage05 work | Stop and redeploy expected revision |
| Stage05 runtime delta cannot be proven | Stop before real OpenRouter call or mixed-language rehearsal message |
| Provider mode is not disabled | Stop and safety-close |
| Telegram send mode is not restricted to private allowlisted test chat | Stop before confirmation |
| Any target looks like a real customer chat or group chat | Stop before send |
| OpenRouter response requires raw prompt/response to debug | Stop; do not paste raw data into docs |
| Agent creates provider ticket/write path | Stop; record incident |
| Account exception attempts replacement action | Stop; record incident |
| Safety close cannot be verified | Do not mark final acceptance passed |

## 8. Evidence Output

Final staging evidence must be redacted and attached to or summarized in:

- `STAGE_05_FINAL_ACCEPTANCE_REPORT.md`
- `STAGE_05_ACCEPTANCE_CHECKLIST.md`
- `STAGE_05_REQUIREMENT_TRACEABILITY_AUDIT.md`
- `STAGE_05_PROGRESS.md`

The evidence must include the completed Task12 evidence ledger from `STAGE_05_OPERATIONS_RUNBOOK.md` Section 7.

## 9. Current Decision

Current decision: approved for the bounded Task12 action subset.

Approval timestamp: `2026-07-08 00:15:10 +08:00`.

Approved subset:

- Deploy reviewed Stage05 commit/artifact to Tencent Cloud staging.
- Apply Stage05 migration.
- Enable server-side real OpenRouter for rehearsal.
- Temporarily enable Telegram `restricted_test` send to private allowlisted test chat.
- Send/confirm one allowlisted test reply.
- Verify business draft no-op evidence.
- Verify controlled account exception evidence.
- Capture redacted evidence.
- Complete safety close.

Still forbidden:

- Production deployment or production traffic.
- Real customer chat send.
- Customer group send.
- Provider write.
- Funds movement.
- Account production.
- Automatic replacement recommendation, reservation or distribution.
- Secret/raw allowlist values in git, docs, logs or evidence.
