# Stage09 r14 真实运行时、OpenRouter 与 Telegram Webhook 证据

## Status

- Date: 2026-07-23
- Scope: r14 原生 sealed release、真实 OpenRouter dry-run、12 case 评测、Telegram webhook 切换
- Excluded: Telegram 真实发送、chat allowlist 绑定、业务 Provider 写入、draft 确认、Stage07 UI 验收

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

## 保留项与风险

- r12/r13/r14 archive、失败 r13 release/venv 和 root-only runtime backups 暂保留为短期部署诊断与回滚证据；r11 是最近稳定回滚点。
- 当前真实 LLM 已启用但 Telegram 无发送权限。下一步需要用户触发单一绑定消息；随后应验证 webhook ingest、allowlist 收敛、send-request → confirm → worker 的真实回包和审计记录。
