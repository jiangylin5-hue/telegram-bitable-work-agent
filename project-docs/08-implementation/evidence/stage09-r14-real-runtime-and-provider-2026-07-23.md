# Stage09 r14 真实运行时、OpenRouter 与 Telegram Webhook 证据

## Status

- Date: 2026-07-23
- Scope: r14 原生 sealed release、真实 OpenRouter dry-run、12 case 评测、Telegram webhook 切换及单聊天受控真实回执
- Excluded: 群发、第二个 Telegram 收件人、业务 Provider 写入、业务表写入、draft 确认、Stage07 UI 验收

## r14 部署结果

1. r12 本地打包发现非 shell native 资产在 Windows archive 中变为 CRLF；r13 服务器预检通过后发现 Git 没有保存部署脚本 executable bit，`systemd ExecStartPre` 返回 `203/EXEC`。两次尝试均自动回滚到 r11，服务保持 active。
2. 修复为：`deploy/stage09-native/**` 强制 LF、sealed layout 逐 native asset 拒绝 CRLF、所有部署脚本保存为 Git executable，并把 executable 检查加入 Linux release gate。
3. r14 archive 在上传前确认 native assets 均为 LF，isolation guard 的 tar mode 为 executable；本地 release/runtime/public-ingress 回归全部通过。
4. 服务器 checksum、release-layout、release-assets、native-service-assets、native-data-assets、固定迁移、systemd restart 与有界 health retry 全部通过。当前 `current` 与 `current-venv` 均为 r14，API/worker/outbox/Nginx 为 active；服务器回环和外部 HTTPS `/health` 都为 HTTP 200。

## 真实 OpenRouter 多 Case

- 首轮在 `sudo -u stage09-p1` 后保留了不可访问的 `/home/ubuntu` cwd，12 个子进程均在 Provider 调用前失败；该结果没有计入模型质量。
- 修正 cwd 为 Stage09 backend 后重跑，保存的是脱敏 JSON evidence，不保存完整 prompt、response、token 或业务原文。

| 指标 | 实测结果 |
| --- | --- |
| Case | 12 |
| 通过 | 12 |
| Provider invoked / completed | 9 / 9 |
| Usage metadata present | 8 |
| Timeout | 0 |
| 安全 gate | 全部通过 |
| 终态 | 6 completed、2 denied、1 degraded、1 cancelled、1 draft pending、1 fail-closed revoked scope |

真实 Provider 的只读、群上下文、RAG、通用建议、越权拒绝、draft 压力、取消、safe replay 与多语言场景均按预期完成或安全收敛；没有 Telegram 发送、Provider 业务写入或 draft 确认。

## Telegram Webhook

- 实测 `getMe` 成功，bot username 存在。
- 切换前 webhook 并非 Stage09；`setWebhook` 已真实成功，随后 `getWebhookInfo` 证实目标是 Stage09 endpoint、无 error、pending update 为 0。
- 服务器的 webhook secret 已以 root-only 临时 payload 同步、立即删除临时文件并重启验证；Telegram 保持 `dry_run`，所有 allowlist 仍为空。
- 因受保护 env 的测试 chat list 为空，系统不会猜测 recipient。用户发出一次绑定 nonce 后，才会读取事实 chat ID、写入完全相同的 send/receive allowlist，并执行单条 `restricted_test` 回包。

## Telegram 单聊天受控回执

### 做了什么

1. 用户向 bot 发送唯一绑定 nonce；Stage09 webhook 真实接收并持久化该消息，系统仅从该事实记录取得一个测试 chat。
2. 运行时将 receive/send 两个 allowlist 原子改为同一个单一 chat，并改为 `restricted_test`；保留真实 LLM profile、禁止 Provider 业务写入及完整 prompt/response 保存。
3. 通过既有受控 API 创建测试发送请求、显式确认，再由原生 outbox bridge 和 worker 调用 Telegram Bot API。

### 改了什么

- `/etc/stage09-p1/runtime.env` 仅增加既有 bot token、一个 receive allowlist 和完全相同的一个 send allowlist，并把发送模式改为 `restricted_test`。
- API、worker、outbox bridge 被有界重启；native isolation validator 和 loopback `/health` 通过。任何转换/健康失败会还原 root-only runtime 备份。

### 验收证据

| 检查项 | 实测结果 |
| --- | --- |
| 绑定消息 | webhook 已持久化；不在证据中保留 chat/user/message 原始值 |
| allowlist | receive=1、send=1，且两个集合相同 |
| 发送状态 | `pending_confirmation` → `confirmed` → `sent` |
| outbox | `processed`，`attempt_count=0` |
| 审计 | `telegram.test_send.requested`、`telegram.test_send.confirmed`、`telegram.test_send.sent` |
| 服务与健康 | API、worker、outbox bridge active；loopback health 成功 |

### 不做什么

- 不扩大 allowlist、不群发、不进行第二次发送；
- 不写业务记录、不确认 draft、不进行 Provider 业务写入；
- 不保存 nonce、chat ID、用户 ID、消息正文、Bot token、webhook secret、完整 prompt 或 response。

## 保留项与风险

- r12/r13/r14 archive、失败 r13 release/venv 和 root-only runtime backups 暂保留为短期部署诊断与回滚证据；r11 是最近稳定回滚点。
- 当前真实 LLM 与 Telegram 单聊天回执均已完成受控 smoke。运行时仍严格只允许该一项测试 chat；继续使用时必须保持 allowlist 收敛、走确认/outbox 路径，并在任何扩大目标或业务写入前另行定义和授权。
