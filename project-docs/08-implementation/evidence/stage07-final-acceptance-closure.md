# Stage07 Final Acceptance Closure Evidence

## Status

- **Status**: `historical partial-local evidence`；本地闭环验收、真实 OpenRouter provider smoke，以及受限的隔离非生产 Telegram 身份/投递/深链证据均已记录。当前整体结论以 [Stage07 Final Audit Report](../STAGE_07_FINAL_AUDIT_REPORT.md) 为准：Stage07 **未验收**。
- **Date**: 2026-07-14
- **Scope**: 当前 Stage07 实现的本地 PostgreSQL、FastAPI、Vite Mini App 与自动化回归证据。
- **Not a claim**: 本文不是 Stage07 整阶段完成、外部服务成功、staging/production 就绪或发布验收声明。

## Evidence Boundary

所有数据库与 UI 结果均来自已配置的本地 PostgreSQL `stage06_smoke` 和为本次验收建立的合成工作区数据。浏览器操作只通过 Codex 内置浏览器完成，未控制用户浏览器、Chrome 或用户既有会话。

这组证据验证已实现链路在本地真实服务栈中的行为，并在后续 S6.3 更新中追加了受限的真实 Telegram Main Mini App/深链记录；它不替代所有角色、所有路由、所有屏幕尺寸的产品走查或生产部署。

## Local UI Integration Result

| Scenario | Result | Evidence boundary |
| --- | --- | --- |
| Owner record edit | Pass | 在 1440px 桌面宽度由 Home 进入 Base 与 Record Detail，修改 `Status` 并保存；界面显示版本由 1 更新至 2。 |
| Viewer field isolation | Pass | 由 Home 进入同一 Base；受限字段表头和值均未渲染，获准字段正常可见。未记录业务字段内容。 |
| Team Bot empty-context summary | Pass | Owner 通过 Team Bot Workbench 选择空视图并生成摘要；得到安全空状态和不透明审计回执。该路径没有调用模型提供方。 |
| Narrow viewport | Pass | 在 390x844 视口下，Team Bot 对话框和审计回执均保持可访问。 |
| Browser console | Pass | 本次上述本地流程中未观察到 console error 或 warning。 |

## Regression and Persistence Evidence

| Verification | Result |
| --- | --- |
| Team Bot focused Mini App tests | 3 files, 4 tests passed |
| Team Bot service unit tests | 6 passed |
| Digital Employee management PostgreSQL tests | 4 passed |
| Stage07 PostgreSQL cross-module matrix | 16 passed, 12 deselected |
| Full backend suite | 627 passed, 17 skipped |
| Full Mini App suite | 60 files, 221 tests passed |
| Mini App production build | Passed |
| Local PostgreSQL migration replay | Passed; Alembic head `20260713_0027` |

17 个 backend skip 是历史 Stage02 online PostgreSQL smoke，原因是未配置 `STAGE02_ONLINE_DATABASE_URL`；不计入本次 Stage07 通过项。

本轮新增或加固的可验证行为如下：

- Team Bot 在 `409`/`422` 摘要失败时保留已选上下文与已输入补充说明，可重试；`404` 仍按权威缺失语义清空上下文。
- Team Bot 服务在暂停、未授权成员、跨 Base View、同一幂等键但不同请求体时，在调用提供方之前失败关闭。
- Digital Employee 生命周期并发命令在两个真实 PostgreSQL session 中竞争时，恰有一个写入成功，另一个收到 revision conflict；持久化状态、audit 与 idempotency 记录均保持单次成功语义。

## External Smoke Preflight

| Target | Preflight result | External call made |
| --- | --- | --- |
| OpenRouter | Passed: all five documented real smoke cases through `openrouter/auto` | Yes; read-only/draft-safe smoke |
| Telegram inbound entry | Passed: temporary polling received one private test mention, resolved `summarize` and one record, then restored the original webhook | Yes; approved temporary webhook switch, no outbound send |

OpenRouter smoke completed all five documented cases: `summarize_basic`, `hidden_field_guard`, `citations_required`, `draft_update_status` and `unsafe_commit_refusal`. Every case passed with `record_values_unchanged_before_confirmation=true` and `raw_prompt_persisted=false` / `raw_response_persisted=false`; the two fixed draft-update cases produced a draft only, never a pre-confirmation record write. It is real provider evidence, but does not by itself prove every Team Bot non-empty-context UI-to-provider route.

An initial read-only auto-discovery attempt stopped at `409 Conflict`, identifying the active webhook/consumer. After the existing webhook secret was securely synchronized into the ignored local env and the user explicitly approved temporary polling, a second run saved the webhook configuration, used `drop_pending_updates=false`, received one matching private test mention, resolved the fixed `summarize` action with one record and restored the original webhook in `finally`. It did not send an outbound Telegram message. Raw chat/user/update/resource identifiers and webhook details are excluded from evidence.

This paragraph is historical inbound-entry evidence only. It is superseded for the bounded isolated S6.3 path by the later two separately approved TD008 deliveries, official WebApp bridge correction and signed `initData` resolver/Base reread record. It remains neither production nor broad Telegram authorization evidence.

### Telegram Closure Blockers (2026-07-14)

The initial ignored-local-env blocker for `TELEGRAM_WEBHOOK_SECRET` was resolved by secure local synchronization before the successful temporary-polling smoke. The secret value remains absent from source, evidence and chat. A later SSH read-only presence check confirms that the historical Stage03 runtime has the Bot, webhook-secret, send-mode and allowlist key names configured; it does not expose their values, exact allowlist count or authorization for the new isolated environment.

For a full non-production Telegram entry and controlled-delivery smoke, the remaining local/human-operated prerequisites are:

- the current `TELEGRAM_WEBHOOK_SECRET`, plus an isolated `STAGE06_TELEGRAM_TEST_CHAT_ID` and optionally `STAGE06_TELEGRAM_TEST_USER_ID` for a private test conversation;
- exactly one `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` value and `TELEGRAM_SEND_MODE=restricted_test` for controlled outbound delivery (the current local mode is not `restricted_test`);
- server-owned `STAGE07_TELEGRAM_BOT_USERNAME` and an authorized BotFather Main Mini App configuration pointing to an isolated public HTTPS endpoint.

The current remote presence check confirms `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` is present in historical Stage03 while `STAGE07_TELEGRAM_BOT_USERNAME` remains absent. S6.3 creates an independent runtime file and must revalidate exact-one allowlist/mode/username rules there before a delivery-capable Worker starts; historical key presence cannot substitute for that preflight.

A read-only Bot API check confirms that the configured token identifies a Bot account, but its default menu button is `commands` and contains no Web App URL. This does not conclusively query BotFather's Main Mini App profile setting, but it confirms there is no default-menu Web App to use as a substitute. An authorized human must configure/attest the isolated HTTPS Main Mini App before the S6.2 external launch test.

These values must remain in the ignored local secret/runtime configuration and must not be copied to source, evidence, screenshots or chat.

### Tencent Cloud Temporary SSH Access (2026-07-14)

The historical staging deployment document identifies a Tencent Cloud Ubuntu target, but this workstation had no SSH host configuration. Two locally discovered candidate PEM files resolve to the same key and were rejected for the conventional `ubuntu` and `root` accounts in read-only, batch-mode attempts. No remote connection was established, no remote environment file was read, and no Tencent Cloud state was changed.

The user explicitly approved a temporary, dedicated SSH public key for this acceptance run. Its private counterpart is retained only in the ignored local secret area and is not printed, committed, or reused for any other purpose. The user must install the public key only for the existing `ubuntu` account through their already authenticated terminal. No browser control is requested or used.

Once that installation is complete, the first remote action is limited to a batch-mode, read-only connectivity and sanitized configuration-presence check. Any later deployment remains constrained to the approved isolated non-production environment; production, raw secret retrieval and database mutation remain out of scope until separately evidenced and authorized. The temporary authorized-key entry must be removed after the Stage07 external acceptance result is recorded.

#### Remote Read-Only Discovery Result

The SSH connectivity probe succeeded as the expected `ubuntu` account. The actual repository is `/home/ubuntu/telegram-bitable-work-agent`, not the initially assumed home-relative `deploy/stage03` path. Its tracked worktree is clean but detached at historical commit `fa645d9`; it does not contain the Stage07 Telegram delivery service or the Mini App package. The server also has a separately running root-owned `uvicorn` process on port `8000`.

The existing Stage03 Compose project exposes the expected service names and has the required Stage03 runtime keys present without revealing their values. `STAGE07_TELEGRAM_BOT_USERNAME` remains absent. No process, container, Compose project, configuration value, database, webhook, BotFather setting, or deployed source was changed by this discovery run.

This evidence rejects an in-place replacement of the existing Stage03 application as an acceptance tactic. A later deployment decision must choose either a fresh, parallel isolated Stage07 Compose project with its own public HTTPS entry or an explicitly approved replacement plan; neither is implicit in the SSH-access approval.

### S6.3 Isolated Deployment Preparation (2026-07-14)

The user approved the parallel isolated route. The S6.3 SDD, BDD/acceptance matrix, module work-surface, complex-index decision and implementation plan now define a new Compose project with independent PostgreSQL/Redis volumes and no host-port publication. Local Compose expansion proves the `stage07-api`/`stage07-web` Caddy aliases, isolated volume names and the absence of Stage03 PostgreSQL/Redis references. A least-privilege review removed the runtime env file from the PostgreSQL container so it never receives Telegram/OpenRouter credentials.

The Caddy host-template was validated through the existing Caddy container using stdin only; no Caddyfile write, reload, certificate request or route change occurred. The proposed `stage07.jiangtest1.online` hostname is currently DNS-unresolved. Therefore source upload, isolated service start, migration, Caddy activation, BotFather setup, controlled delivery and Mini App smoke remain blocked and are not claimed.

The DNS prerequisite subsequently resolved to the approved Tencent Cloud host and the isolated source/API image were staged without starting long-lived Stage07 services. Historical Stage03 test-target keys were found empty, so a test-first one-time private `/stage07-bind` capture helper was added. Its focused capture plus Stage06 smoke regression suite passes `25` tests; direct container startup and a read-only Bot `getWebhookInfo` probe pass without exposing a URL or identifier.

Five authorized 120-second capture attempts have now run against the real Bot. Four received no matching private marker, wrote no Chat/User/allowlist value, made no outbound send and ended `blocked`; each restored the original webhook successfully. One later attempt failed during its initial Bot API call, before webhook removal or restoration was attempted. A follow-up read-only `getWebhookInfo` call returned `200` and `ok=true`, and `getMe` confirmed that the configured public `@BitableAgentBot` has the displayed name `BitableWorkAgentBot` shown in the user-provided Telegram screenshot. The latest marker was sent during an explicitly active window but was still absent from `getUpdates`. A separate read-only SQLAlchemy ORM count inside the existing Stage03 API found three recent private `/stage07-bind` records. It exposed no raw message, Chat/User identifier, token or secret, and proves that the existing webhook—not the test user action—is the remaining route boundary. A Stage03-to-isolated target-import helper has not been implemented or authorized; this is truthful external blocked evidence, not delivery or Mini App acceptance.

### S6.3 Isolated Runtime Attempt (2026-07-14)

The remote isolated Compose configuration expanded successfully, its API/Web images built, and its independent PostgreSQL and Redis containers reached `healthy`. The isolated migration replay completed through `20260713_0027`. The delivery-capable API subsequently refused to start because the required `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` value remains empty. This is the documented fail-closed outcome for `restricted_test`, not a bypassable deployment error. The API, worker, outbox-bridge and web containers were stopped after diagnosis; no Caddy route/reload, certificate request, BotFather configuration, outbound Telegram send or Stage03 container/data change occurred. The isolated PostgreSQL/Redis services and volumes are intentionally retained only to resume the approved acceptance sequence after target bootstrap.

### S6.3 Persisted-Marker Bridge Attempt (2026-07-14)

After the user approved the documented fallback, its focused selector/writer/wrapper suite passed `31` tests with one Windows-only shell skip. The helper was staged into the isolated source, the Stage07 API image rebuilt, and the Linux wrapper passed shell syntax and invalid-argument checks. A valid fresh private candidate was selected, but the subsequent restricted-test preflight proved no target key was written.

The live no-write diagnostics narrowed the defect to Linux bind-mount semantics: the existing writer correctly creates a sibling temporary file and atomically replaces the target, but cannot replace a single file that is itself a bind-mount target. This was not a Bot, Stage03 ORM, candidate-validation or receipt-parsing failure. The user selected C. The ignored runtime env was migrated to a dedicated directory owned by the isolated deployment user (`0700` directory, `0600` env file); all Compose services now resolve `runtime/.env.stage07-acceptance`, while the short-lived writer mounts only that directory. Remote Compose validation, API rebuild, wrapper invalid-argument fail-closed behavior and a temporary directory-mounted atomic-write probe passed. The actual restricted-test preflight remains intentionally blocked by the empty allowlist; Stage03 HTTPS remains `200` and no Stage07 delivery-capable service is running. No new live selection was made automatically. A further live bootstrap requires a newly opened user-authorized window and one new marker. No Stage03 database/config/webhook/container mutation, Caddy change, BotFather change or Telegram send occurred during this attempt.

如需继续外部验收，请仅在本机安全环境中配置相应变量（不要在对话中发送密钥）：`OPENROUTER_API_KEY`、`TELEGRAM_BOT_TOKEN`、`STAGE06_TELEGRAM_TEST_CHAT_ID`、`STAGE06_TELEGRAM_TEST_USER_ID`、`TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` 与 `TELEGRAM_SEND_MODE=restricted_test`，并确认测试 Bot / Mini App 配置可用。

### S6.3 Isolated Runtime, HTTPS and Provider Update (2026-07-14)

The user approved the C runtime-layout correction. The ignored isolated env now lives in a deployment-user-owned dedicated directory with mode `0700` for the directory and `0600` for the file. Compose validation, isolated API rebuild, Linux wrapper syntax, invalid-argument fail-closed behavior and a temporary directory-mounted atomic-write probe passed. One fresh user-approved `/stage07-bind` window returned only the fixed `captured` receipt. The post-write ownership restoration was required because the containerized atomic writer replaces the file as root; after restoration, the isolated restricted-test preflight passed with an exactly-one allowlist without exposing any target value.

The isolated API, Worker, Outbox bridge and Web services are running. Internal API health is `200`. A Caddy candidate that routes only explicit static paths to Web and all other paths to API validated against the active configuration before a backup/reload. The active `stage07.jiangtest1.online` HTTPS API and Web checks are `200`; `api.jiangtest1.online` remained `200` before and after. A read-only isolated-ORM count found zero Stage07 deep-link-delivery rows and zero corresponding Outbox rows. No Stage03 database/configuration/webhook/container state was changed by the isolated services, and no Telegram send occurred.

Codex's in-app Browser entered the deployed HTTPS Mini App without controlling user Chrome. Because this browser visit has no signed Telegram `initData`, the visible state was only the expected fail-closed no-workspace-access message. This is anonymous-entry evidence, not a Mini App identity/resolver/reread acceptance. The isolated API container also completed the five existing real OpenRouter safe cases (`summarize_basic`, `hidden_field_guard`, `citations_required`, `draft_update_status`, `unsafe_commit_refusal`): all passed, no record changed before confirmation, and neither raw prompt nor raw response was persisted.

BotFather Main Mini App configuration was subsequently completed. The isolated and historical runtime Token probes each returned a sanitized Bot API success and the values aligned without being printed. One synthetic Base/binding fixture was created only in the isolated database, then one user-authorized TD008 request was explicitly confirmed. The existing Outbox/Worker path produced exactly one terminal receipt: delivery and request `sent`, Outbox `processed`, one response message ID present, active pointer and no outcome error. The user supplied a Telegram screenshot of that one fixed-copy message and its `Open workspace` button.

The user then opened the Main Mini App. This is direct launch evidence, but not resolver acceptance: the displayed no-access state coincided with an isolated audit inspection that found no `stage07.telegram_deep_link_resolved` event and an active pointer. Root-cause inspection found that the Vite host page did not load Telegram's official `telegram-web-app.js` bridge, so `window.Telegram.WebApp.initData` was unavailable to the existing safe in-memory transport. A test-first host-page regression was added, confirmed red, then passed alongside the existing Mini App/deep-link tests (`14` related tests); the production build passed. The isolated Web image was rebuilt, its public HTML was checked for the official bridge, and Stage07/Stage03 HTTPS health remained `200`.

The original pointer's ten-minute window expired before the fixed page could be opened. TD008 forbids automatic retry, so no second message was sent. The remaining external gate is one new explicitly user-authorized private TD008 request, followed immediately by the test user's Telegram open and direct sanitized `initData`/resolver/reread observation.

### S6.3 Telegram Identity / Deep-Link Closure (2026-07-15)

The user explicitly approved one fresh TD008 request after the first pointer expired during the official-WebApp-bridge correction. This is a new closed request, not an automatic retry. The existing Worker/Outbox path emitted exactly one terminal receipt for the new request: delivery `sent`, linked request `sent`, Outbox `processed`, a response message ID present, no outcome error and an active short-lived pointer. The recipient then opened the latest Telegram button and observed the authorized fixture workspace plus its Base destination.

The isolated database holds no raw `initData`, URL, Token or Chat identifier in this evidence. A read-only sanitized inspection found the latest deep-link audit event `stage07.telegram_deep_link_resolved`, with outcome `resolved` and destination kind `base`; the endpoint requires the existing verified-launch dependency before it can write that audit. This closes only the bounded non-production TD007/TD008 identity, resolver and Base reread path. It does not prove production readiness, broad delivery, non-empty Team Bot execution, arbitrary user authorization or whole-Stage07 completion.

### S6.3 Isolated Resource Cleanup (2026-07-15)

After explicit user approval, the isolated acceptance Compose project, independent volumes, synthetic runtime directory, dedicated Caddy host block/backup and temporary SSH public key were removed. Caddy validation and reload completed before service removal. The historical Stage03 public health endpoint was `200` before the configuration mutation, after the Caddy reload, after Compose/data removal and again from an independent public-health check after key revocation. A batch-mode SSH attempt with the removed temporary key was rejected.

No Stage03 container, volume, runtime configuration, database or deployment source was removed. No Stage07 runtime secret, target identifier, raw launch value or synthetic database record was retained in the remote acceptance environment.

## 2026-07-15 Audit Correction

The R0-R3 reconciliation following this evidence was later found too broad to close the original BDD/SDD requirement IDs. This file remains historical local/external supporting evidence only. The current whole-stage decision is [Stage07 Final Audit Report](../STAGE_07_FINAL_AUDIT_REPORT.md): compatible Browser, role/failure, PostgreSQL and literal Team Bot UI-to-provider gaps remain active; production/staging, broad Telegram authorization and future contract-gated capability expansion remain outside Stage07.

## Explicitly Not Accepted

- Stage07 整阶段完成或发布就绪；
- Team Bot complete user-operated Mini App visual/provider end-to-end result；the later R2 safe-route-to-provider smoke is recorded separately and does not replace this UI acceptance.
- staging/production or broad Telegram authorization; the bounded isolated private delivery, signed `initData` / deep-link reread and Main Mini App entry are recorded above and must not be described as pending.
- staging / production 数据库、部署与可观测性；
- 所有屏幕尺寸、所有角色、所有模块路由的完整视觉与可用性验收；
- 被既有契约明确后置的 memory / RAG、批量员工操作等扩展范围。

## Cleanup and Retained Local Evidence

本轮临时 FastAPI 服务、Vite 代理和临时 seed / proxy 脚本均已停止或删除；本地端口 `127.0.0.1:8001` 与 `127.0.0.1:4176` 已无监听进程，内置浏览器会话已结束。

为便于复核，名为 Stage07 Final Acceptance 的合成工作区及其派生的本地 audit / record 数据仍保留在配置的本地测试数据库中。它不属于生产、staging 或用户业务数据；在未来共享演示、部署或更换测试库前必须删除该合成数据或重建测试数据库。
