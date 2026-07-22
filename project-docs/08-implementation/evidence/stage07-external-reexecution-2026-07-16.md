# Stage07 外部实测复执行记录（2026-07-16）

## Status

- Scope: 本轮基于用户明确许可，复执行既有 Stage06/Stage07 的真实 OpenRouter provider smoke；核对 Telegram 与隔离部署的实际可执行条件。
- Authorization: 用户已明确允许真实外部写入，包括 Telegram。本记录不把该授权扩大为向未知聊天、客户群或生产环境投递。
- Safety: 不输出或持久化密钥、完整 prompt/response、Telegram 标识、webhook URL/secret 或业务记录内容；provider 脚本只使用合成内存工作区和记录。

## Approved Execution Boundary

1. 允许执行真实 OpenRouter 网络调用：`stage06_live_openrouter_smoke.py` 的一个受控 draft 场景，以及 `stage07_team_bot_live_openrouter_smoke.py` 的 Mini App 安全路由场景。
2. 两项脚本固定启用 `TELEGRAM_SEND_MODE=dry_run`、关闭完整 prompt/response 持久化，并不连接持久化业务数据库。它们产生的草稿、审计和 AgentRun 仅在进程内存中存在，进程退出后消失。
3. Telegram 实际投递仍要求一个新建或当前明确的、单一 allowlisted 非生产测试聊天，且不能复用已清理的隔离环境或历史收件人。没有这个精确目标时，不调用 `sendMessage`、不切换 webhook/polling、也不确认任何草稿。
4. 部署仍要求新的隔离主机/hostname、目标环境和部署来源选择；已清理的 S6.3 环境不得被隐式复建或重用，Stage03 不在本轮范围内。

## Expected Evidence

- OpenRouter：仅记录调用是否成功、受控场景、模型元数据是否存在、响应/审计/AgentRun 是否存在、草稿状态、确认前合成记录是否不变和脱敏断言。
- Telegram / deployment：若精确测试目标或隔离部署目标未被提供，仅记录为“not executed—target unresolved”，不能误写成失败或已完成。

## Continuation Authorization

- The user subsequently directed the agent to locate the local environment file and execute the real tests. The permitted continuation is to run the remaining existing, synthetic-data OpenRouter cases one at a time and to run the existing Telegram preflight.
- A Telegram API call, send, webhook switch or deployment remains conditional on the preflight resolving exactly one allowlisted non-production test chat and a matching user/configuration. If it does not, the failed-closed preflight result is the test result; it is not permission to auto-discover an arbitrary chat or change Bot state.

## Result

- `stage06_live_openrouter_smoke.py` completed one real `draft_update_status` provider case successfully. The returned model provider and model name were present; one `pending_confirmation` draft was created in the in-memory unit of work; the synthetic record remained unchanged before confirmation; neither raw prompt nor raw response was persisted.
- The exact Team Bot safe-route smoke was first constrained by the foreground command's 64-second tool ceiling, so that attempt is not counted as a result. A redacted background diagnostic then executed the same route to completion in `51.938` seconds: contacts, context and summary routes each returned `200`; the summary was nonempty with a citation; audit receipt and AgentRun were present; and the synthetic record remained unchanged. The diagnostic runner and its safe result were removed immediately after inspection. This identifies a command-execution time-boundary issue, not a product-route failure.
- Telegram preflight was read locally without an API call. A webhook secret is present, but there is no configured single test chat, test user, `restricted_test` delivery allowlist, or Stage07 bot username. Therefore no `sendMessage`, `getUpdates`, webhook mutation, polling switch, draft confirmation, or Telegram delivery was executed.
- No fresh isolated deployment host/hostname, environment or source target is defined. The cleaned S6.3 environment was not recreated, and Stage03 was not touched.

## Continuation Result

- The only local environment file is the ignored root `.local/stage05-real-workflow.env`; it has an OpenRouter credential and Telegram token/webhook secret, but does not have a fixed test chat or test user.
- The remaining real OpenRouter cases all passed when run independently: `summarize_basic`, `hidden_field_guard`, `unsafe_commit_refusal` and `citations_required`. Together with the earlier `draft_update_status`, the complete five-case shared runtime matrix now has current per-case real-provider results. Summary cases created no draft; both draft cases created only one in-memory `pending_confirmation` draft, and every case preserved the synthetic source record before confirmation. Raw prompts and responses were not persisted.
- The executed Telegram smoke preflight stopped before a network request because `STAGE06_TELEGRAM_TEST_CHAT_ID` is absent. The user was asked to send one bounded private-chat marker (`@ops summarize`) before a separately timed temporary-polling inbound smoke; that future operation is not yet executed.

## Telegram Inbound Execution Authorization

- The user confirmed that the requested one-time marker has been sent in the displayed private Bot chat. This authorizes exactly one existing-script temporary-polling smoke: snapshot the current webhook, call `deleteWebhook` with `drop_pending_updates=false`, look only for the marker during a maximum 120-second window, acknowledge only a matching update, and restore the exact original webhook with its configured secret in `finally`.
- The operation remains read-only with respect to product data: its synthetic workspace/binding/mention resolution is in memory, it sends no reply, confirms no draft and creates no customer/group delivery. Evidence will redact Telegram identifiers, webhook URL and all raw update content.

## Telegram Inbound Attempt 1

- Result: `blocked`. Temporary polling was enabled with `drop_pending_updates=false`, no matching update was observed in the 120-second window, and the original webhook was restored successfully. No reply, group/customer send, draft confirmation, persistent product-data write, raw update persistence or identifier disclosure occurred.
- Investigation: the marker was sent before temporary polling had removed the active webhook. The observed result only proves that no matching update reached `getUpdates` during the polling window; it does not prove whether the earlier message was already consumed by the original webhook or did not match the required alias. The existing script's matcher accepts only a message containing `ops` and polls only while the webhook is temporarily disabled.
- Next minimal test: start a new single 120-second controlled polling window first, then ask the user to send the exact marker after the window is reported ready. This changes only message timing and retains the same Bot, alias, no-drop rule, restore path and in-memory synthetic resolution.

## Telegram Inbound Attempt 2

- Result: `blocked`. The fresh polling window was confirmed active before the user was prompted to send the exact marker. It again observed no matching update, retained `drop_pending_updates=false`, and restored the original webhook successfully.
- Root-cause evidence so far: timing alone did not make a matching update available. The safe result does not reveal whether no message was submitted during the window, the displayed Bot is not the Bot for the configured token, or the message did not contain the expected alias. No third polling/write attempt will be made until a read-only bot-identity boundary check and a renewed user-coordinated marker are available.
- Read-only boundary check: the configured token does correspond to the displayed private Bot, and the webhook was active after each restore with no pending-update indication. This removes bot-token mismatch and failed webhook restoration as the current explanation. The remaining unverified boundary is the marker's delivery/matcher content during the active polling window.

## Telegram Inbound Attempt 3 Control

- The user explicitly confirmed readiness before the window begins. This is the final minimal timing test: start the same 120-second polling window, verify that the runner is active, notify the user to send exactly `@ops summarize`, then inspect only the redacted terminal result.
- No code or configuration changes are introduced. A third unmatched terminal result ends the live polling sequence; a later action would require a different, separately reviewed ingress-observability method rather than another retry.

## Telegram Inbound Attempt 3 Result

- Result: `passed`. The polling runner was verified active before the user sent the exact marker. The existing entry smoke resolved the one matching private message to the permitted synthetic `summarize` action with one synthetic visible record.
- Safety result: the process forced `TELEGRAM_SEND_MODE=dry_run` and `PROVIDER_MODE=disabled`; it sent no reply, did not invoke an LLM/provider, did not confirm a draft and created no persistent product-data write. Temporary polling used `drop_pending_updates=false`, and the original webhook was restored successfully.
- Evidence boundary: this is a bounded real Telegram inbound/mention and in-memory mention-resolution result only. It neither proves a real Bot response send nor modifies the accepted TD007/TD008 deep-link delivery evidence, staging/production status or Stage07 whole-stage result.

## Live Telegram Inbound Execution

- The user confirmed that the bounded private-chat marker has been sent. One temporary-polling run is now authorized to inspect only a matching `@ops summarize` message during a 120-second window.
- The run may call Telegram `getWebhookInfo`, temporarily call `deleteWebhook` with pending updates retained, poll/acknowledge the matching message, and restore the captured webhook with the local secret. It will not call `sendMessage`, confirm any draft, change Stage03, retain Telegram identifiers, or use the matched chat as a future default target.
