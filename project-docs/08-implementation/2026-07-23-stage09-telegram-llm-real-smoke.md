# Stage09 Telegram 与真实 LLM 受控联调计划

## Status

- Scope: r12 runtime release 后的 Telegram webhook、单一已验证 chat 的真实测试发送、OpenRouter 真实 LLM 多 case 评测。
- Authorization: 用户已明确允许 Telegram、LLM 与外部写入；不进行群发、Provider 写入、资金操作或未确认的业务写入。
- Preconditions: r11 公网 HTTPS `/health` 已为 200；本机 `.local/stage05-real-workflow.env` 具有 Telegram bot、webhook secret 与 OpenRouter 配置。服务器当前仍为 r11 baseline，必须先通过 sealed r12 release 取得受控 profile validator。

## 运行时最小变更

阶段 A（真实 LLM dry-run）从本机受保护 env 向服务器 `/etc/stage09-p1/runtime.env` 仅同步以下值，传输过程不回显值、服务器文件继续为 root 写入和 `stage09-p1` 组可读：

- `OPENROUTER_API_KEY`、`OPENROUTER_MODEL`、`OPENROUTER_BASE_URL`
- `LLM_ENABLED=true`
- `AGENT_WORKFLOW_MODE=real_openrouter`
- `TELEGRAM_SEND_MODE=dry_run`
- `PROVIDER_MODE=disabled`
- `AGENT_SAVE_FULL_PROMPT=false`、`AGENT_SAVE_FULL_RESPONSE=false`

阶段 B（绑定单一 Telegram chat）只在用户发出唯一 nonce 后进行：同步 bot token 与 webhook secret，暂不发送消息；收到该用户的绑定消息并取得事实 chat ID 后，才把同一 ID 写入 `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` 与 `TELEGRAM_ALLOWED_CHAT_IDS`，并切换 `TELEGRAM_SEND_MODE=restricted_test`。该模式的真实 Bot API 发送仍必须经 create request、confirm、outbox/worker 与双 allowlist，不存在无约束 `real` 模式。

## 执行顺序与证据

1. 备份服务器运行时文件权限与内容摘要，写入最小变更，重启仅 Stage09 API/worker/outbox；若运行时预检或 health 失败，恢复备份并重启回滚。
2. 使用 bot token 调用 Telegram `getMe` 与 `getWebhookInfo`；若现有 webhook 不冲突，设置 r11 HTTPS `/telegram/webhook` 与 webhook secret。输出仅记录成功状态、URL 是否匹配和 pending 数，不记录 token、secret 或 chat ID。
3. 用户发出唯一带 nonce 的真实消息；在这一个绑定窗口内只接收、不自动回复或发送，验证 webhook 成功、`telegram_inbox` 投影与 audit 记录均存在。随后将事实 chat ID 写入双 allowlist，立即结束开放接收窗口；不得记录原文或 chat ID。
4. 通过受控 send-request → confirm → worker 发送一条明确标识为测试的真实 bot 消息；验证 Telegram Bot API 成功、send log/outbox/audit 状态。不得扩大 allowlist。
5. 使用既有 Stage08/Stage06 真实评测入口运行多类只读 case（表查询、上下文检索、数字员工操作建议、拒绝越权请求），分别记录 LLM invocation、命中技能/工具、是否产生受控 draft 和脱敏评分。

## 非目标与失败处理

- 不启用 `PROVIDER_MODE`，不写入第三方业务系统。
- 不保存完整 prompt、response、Telegram 原文或机密到长期日志。
- Telegram 或 OpenRouter 失败只保留脱敏 error code、trace 和状态；运行时配置异常立即恢复当前服务器备份。
- 本文完成不等于 Browser/UI、群聊上下文、所有技能或完整生产上线验收完成。

## 2026-07-23 运行时输入发现

受保护 env 的 `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` 键存在但值为空。r11 的 Stage09 运行时更新因此在写入前被拒绝，服务器 runtime 未改变。r12 允许先启用不产生 Telegram 消息写入的真实 OpenRouter dry-run；要进行 webhook 接收及受限真实发送，用户须在目标 bot 对话中发送一条唯一测试文本。系统将从收到的 webhook 取得 chat 事实、立即写入精确双 allowlist，再执行 send-request/confirm 的真实回包，不会猜测或手工编造 chat ID。
